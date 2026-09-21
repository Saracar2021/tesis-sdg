#!/usr/bin/env python
"""Genera docs/fuentes_datos.md y outputs/fuentes_datos.json leyendo data/raw/ (solo lectura).

Uso (desde la raíz del repo):
    .venv\\Scripts\\python.exe tools\\generar_fuentes_datos.py

Toda cifra del documento sale de este código (CLAUDE.md: cero cifras hardcodeadas). Los textos de
unidad de análisis son declaraciones; el script verifica cada una contra las llaves de los datos
y marca REVISAR si no se sostiene. No escribe nada en data/raw/ ni en data/_descargas/.
"""
from __future__ import annotations

import codecs
import csv
import hashlib
import json
import re
import statistics
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import pyreadstat

sys.path.insert(0, str(Path(__file__).resolve().parent))
import normalizar_datos as nd  # noqa: E402  (reglas de mapeo y de lectura compartidas)

csv.field_size_limit(2**31 - 1)
ROOT = nd.ROOT
RAW = nd.RAW
DESCARGAS = nd.DESCARGAS
OUT_MD = ROOT / "docs" / "fuentes_datos.md"
OUT_JSON = ROOT / "outputs" / "fuentes_datos.json"
CHUNK = 1 << 20
ANIO = "2025"
ORDEN_MODULOS = [r.destino[:-4] for r in nd.MODULOS_GEIH]
HOGAR_GEIH = ["DIRECTORIO", "SECUENCIA_P", "HOGAR"]
# ENPH: la llave de hogar es SOLO DIRECTORIO (verificado; SECUENCIA_P/SECUENCIA_ENCUESTA son contadores de registro).
KEYS_ENPH = {"DIR": ["DIRECTORIO"], "DIR+ORD": ["DIRECTORIO", "ORDEN"],
             "DIR+SE+SP": ["DIRECTORIO", "SECUENCIA_ENCUESTA", "SECUENCIA_P"],
             "DIR+SE+SP+ORD": ["DIRECTORIO", "SECUENCIA_ENCUESTA", "SECUENCIA_P", "ORDEN"]}
NOMBRE_LLAVE = {"DIR": "DIRECTORIO", "DIR+ORD": "DIRECTORIO+ORDEN", "DIR+SE+SP": "DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P",
                "DIR+SE+SP+ORD": "DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P+ORDEN"}
# Renombres ya aprobados: si el archivo aún tiene el nombre viejo, se lee igual y se avisa.
ALIAS = {"ENPH_2017/urbano/gastos_diarios_hogar.txt": "ENPH_2017/urbano/gastos_diarios.txt"}

# --- Unidad de análisis declarada (claim: hogar | persona | registro) -----------------------------
GEIH_UNIDAD = {
    "caracteristicas_generales": ("persona", "una fila por persona del hogar"),
    "datos_hogar": ("hogar", "una fila por hogar"),
    "fuerza_trabajo": ("persona", "una fila por persona (subconjunto de características generales)"),
    "migracion": ("persona", "una fila por persona"),
    "no_ocupados": ("persona", "una fila por persona no ocupada (subconjunto)"),
    "ocupados": ("persona", "una fila por persona ocupada (subconjunto)"),
    "otras_formas_trabajo": ("persona", "una fila por persona (subconjunto)"),
    "otros_ingresos": ("persona", "una fila por persona (subconjunto)"),
}
# destino -> (claim, descripción, variable del DDI que respalda qué es una fila)
ENPH_UNIDAD = {
    "ENPH_2017/hogares/viviendas_hogares.csv": ("hogar", "una fila por hogar (vivienda y hogar)", None),
    "ENPH_2017/hogares/gastos_menos_frecuentes_medio_pago.csv": ("hogar", "una fila por hogar (medio de pago, cuadernillo 3)", None),
    "ENPH_2017/hogares/gastos_menos_frecuentes_articulos.txt": ("registro", "registro de gasto: hogar × artículo o servicio (varias filas por hogar)", "P10270"),
    "ENPH_2017/personas/caracteristicas_generales_personas.csv": ("persona", "una fila por persona", None),
    "ENPH_2017/urbano/gastos_diarios_hogar.txt": ("registro", "registro de gasto diario urbano: una fila por artículo o servicio; mezcla gasto del hogar y personal (NH_CGDU_P10)", "NH_CGDU_P1"),
    "ENPH_2017/urbano/gastos_diarios_hogar_comidas_fuera.csv": ("registro", "registro de gasto: comida o alimento adquirido fuera del hogar (hogar)", "NH_CGDUCFH_P1"),
    "ENPH_2017/urbano/gastos_diarios_personales.csv": ("registro", "registro de gasto personal diario: artículo o servicio (cuadernillo 4)", "NC4_CC_P1_1"),
    "ENPH_2017/urbano/gastos_diarios_capitulo_c.txt": ("registro", "registro de gasto por alimento o grupo de alimentos (cuadernillo 2, cap. C)", "NC2_CC_P1"),
    "ENPH_2017/urbano/gastos_diarios_mercados.csv": ("registro", "registro de valor total de mercado no desagregado (cuadernillo 2)", "NC2_CC_P4S1"),
    "ENPH_2017/urbano/gastos_personales_comidas_fuera.csv": ("registro", "registro de gasto personal: comida adquirida fuera del hogar", "NH_CGPUCFH_P1"),
    "ENPH_2017/rural/gastos_personales_comidas_fuera.csv": ("registro", "registro de gasto personal rural: comida adquirida fuera del hogar", "NC2R_CA_P3"),
    "ENPH_2017/rural/gastos_personales.csv": ("registro", "registro de gasto personal rural: artículo o servicio", "NC2R_CE_P2"),
    "ENPH_2017/rural/gastos_semanales_capitulo_c.csv": ("registro", "registro de gasto semanal por alimento o grupo (cuadernillo 2, cap. C)", "NC2_CC_P1"),
    "ENPH_2017/rural/gastos_semanales_comidas_fuera.csv": ("registro", "registro de gasto semanal: comida adquirida fuera del hogar", "NH_CGPRCFH_P1"),
    "ENPH_2017/rural/gastos_semanales_mercados.csv": ("registro", "registro de valor total de mercado no desagregado (rural)", "NC2_CC_P4S1"),
    "ENPH_2017/rural/gastos_semanales.csv": ("registro", "registro de gasto semanal rural: artículo o servicio", "NC2R_CA_P3"),
}
DDI_ENPH_FILE = {  # destino -> nombre de tabla en el DDI (para etiquetas)
    "ENPH_2017/hogares/viviendas_hogares.csv": "Viviendas y hogares",
    "ENPH_2017/hogares/gastos_menos_frecuentes_medio_pago.csv": "Gastos menos frecuentes - Medio de pago",
    "ENPH_2017/hogares/gastos_menos_frecuentes_articulos.txt": "Gastos menos frecuentes - Articulos",
    "ENPH_2017/personas/caracteristicas_generales_personas.csv": "Caracteristicas generales personas",
    "ENPH_2017/urbano/gastos_diarios_hogar.txt": "Gastos diarios Urbanos",
    "ENPH_2017/urbano/gastos_diarios_hogar_comidas_fuera.csv": "Gastos diarios del hogar Urbano - Comidas preparadas fuera del hogar",
    "ENPH_2017/urbano/gastos_diarios_personales.csv": "Gastos diarios personales Urbano",
    "ENPH_2017/urbano/gastos_diarios_capitulo_c.txt": "Gastos diarios Urbano - Capitulo C",
    "ENPH_2017/urbano/gastos_diarios_mercados.csv": "Gastos diarios Urbanos - Mercados",
    "ENPH_2017/urbano/gastos_personales_comidas_fuera.csv": "Gastos personales Urbano - Comidas preparadas fuera del hogar",
    "ENPH_2017/rural/gastos_personales_comidas_fuera.csv": "Gastos personales Rural - Comidas preparadas fuera del Hogar",
    "ENPH_2017/rural/gastos_personales.csv": "Gastos personales Rural",
    "ENPH_2017/rural/gastos_semanales_capitulo_c.csv": "Gastos semanales Rural - Capitulo C",
    "ENPH_2017/rural/gastos_semanales_comidas_fuera.csv": "Gastos semanales Rural - Comidas preparadas fuera del hogar",
    "ENPH_2017/rural/gastos_semanales_mercados.csv": "Gastos semanales Rurales - Mercados",
    "ENPH_2017/rural/gastos_semanales.csv": "Gastos semanales Rurales",
}


# --- Utilidades ------------------------------------------------------------------------------------
def fn(n, d=0) -> str:
    """Miles con punto, decimales con coma."""
    if n is None:
        return "—"
    s = f"{n:,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def tabla(cab: list[str], filas: list[list]) -> str:
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    out += ["| " + " | ".join(str(c) for c in f) + " |" for f in filas]
    return "\n".join(out)


def limpio(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<!\[CDATA\[|\]\]>", "", s)).strip()


def sha256_path(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while c := f.read(CHUNK):
            h.update(c)
    return h.hexdigest()


def analizar_bytes(path: Path) -> dict:
    """SHA-256 + encoding real (decodificación estricta, sin chardet)."""
    h = hashlib.sha256()
    dec8 = codecs.getincrementaldecoder("utf-8")("strict")
    ok8, bom, altos, primero = True, False, set(), True
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            body = chunk
            if primero:
                bom = chunk[:3] == b"\xef\xbb\xbf"
                body = chunk[3:] if bom else chunk
                primero = False
            h.update(chunk)
            altos |= set(body.translate(None, bytes(range(128))))
            if ok8:
                try:
                    dec8.decode(chunk)
                except UnicodeDecodeError:
                    ok8 = False
    if ok8:
        try:
            dec8.decode(b"", final=True)
        except UnicodeDecodeError:
            ok8 = False
    indef_cp1252 = bool(altos & {0x81, 0x8D, 0x8F, 0x90, 0x9D})
    if bom and ok8:
        etiqueta = "UTF-8 con BOM" + (" (solo ASCII)" if not altos else " (con acentos)")
    elif not altos:
        etiqueta = "ASCII"
    elif ok8:
        etiqueta = "UTF-8"
    elif not indef_cp1252:
        etiqueta = "cp1252 (bytes " + ", ".join(f"0x{b:02X}" for b in sorted(altos)) + ")"
    else:
        etiqueta = "indeterminado"
    return {"sha256": h.hexdigest(), "bytes": path.stat().st_size, "bom": bom, "utf8_valido": ok8,
            "cp1252_valido": not indef_cp1252, "encoding": etiqueta}


def lectura_ok(clave: str, a: dict) -> bool:
    enc = nd.LECTURA[clave]["encoding"]
    if enc == "cp1252":
        return a["cp1252_valido"]
    if enc == "utf-8-sig":
        return a["utf8_valido"]
    return a["utf8_valido"] and not a["bom"]


def contar_csv(path: Path, enc: str, sep: str) -> dict:
    with open(path, "r", encoding=enc, newline="") as f:
        rd = csv.reader(f, delimiter=sep)
        header = next(rd)
        filas = ragged = 0
        for r in rd:
            filas += 1
            if len(r) != len(header):
                ragged += 1
    with open(path, "rb") as f:
        f.seek(-1, 2)
        termina_nl = f.read(1) in (b"\n", b"\r")
    return {"header": header, "filas": filas, "columnas": len(header), "irregulares": ragged,
            "termina_en_salto": termina_nl}


def claves(path: Path, enc: str, sep: str, cols: list[str]) -> pd.DataFrame:
    pres = pd.read_csv(path, sep=sep, encoding=enc, nrows=0).columns
    return pd.read_csv(path, sep=sep, encoding=enc, dtype=str, usecols=[c for c in cols if c in pres],
                       keep_default_na=False)


def distintos(df: pd.DataFrame, cols: list[str]):
    return int(df[cols].drop_duplicates().shape[0]) if all(c in df.columns for c in cols) else None


def verificar_claim(claim: str, hog_u: bool, per_u) -> str:
    if claim == "hogar":
        return "CONSISTENTE" if hog_u else "REVISAR"
    if claim == "persona":
        return "CONSISTENTE" if per_u else "REVISAR"
    return "CONSISTENTE" if per_u is False else "REVISAR"  # registro: la llave hogar+ORDEN NO es única


def verificar_claim_enph(claim: str, r: dict) -> str:
    u = r["llaves_unicas"]
    if not r["dir_en_hogares"]:
        return "REVISAR"
    if claim == "hogar":
        return "CONSISTENTE" if "DIR" in u else "REVISAR"
    if claim == "persona":
        return "CONSISTENTE" if "DIR+ORD" in u and "DIR" not in u else "REVISAR"
    return "CONSISTENTE" if "DIR" not in u and "DIR+SE+SP" in u else "REVISAR"  # registro


def cargar_log() -> dict:
    if not nd.LOG.exists():
        return {}
    return {a["destino"]: a for a in json.loads(nd.LOG.read_text(encoding="utf-8"))["archivos"]}


# --- DDI -------------------------------------------------------------------------------------------
def ddi_enph() -> tuple[dict, dict]:
    t = (RAW / "ENPH_2017/_metadatos/DANE-DIMPE-ENPH-2016-2017.xml").read_text(encoding="utf-8")
    fid = {m.group(1): limpio(re.search(r"<fileName>(.*?)</fileName>", m.group(2), re.S).group(1)).replace(".NSDstat", "")
           for m in re.finditer(r'<fileDscr ID="(F\d+)"[^>]*>(.*?)</fileDscr>', t, re.S)}
    labs = {}
    for m in re.finditer(r'<var ID="[^"]*"[^>]*name="([^"]+)"[^>]*files="([^"]+)"[^>]*>(.*?)</var>', t, re.S):
        lb = re.search(r"<labl[^>]*>(.*?)</labl>", m.group(3), re.S)
        labs[(fid.get(m.group(2), m.group(2)), m.group(1))] = limpio(lb.group(1)) if lb else ""
    casos = sorted(set(re.findall(r"<caseQnty>\s*(\d+)\s*</caseQnty>", t)))
    return labs, {"caseQnty_valores": casos}


def ddi_geih() -> dict:
    t = (RAW / "GEIH_2025/_metadatos/DANE-DIMPE-GEIH-2025.xml").read_text(encoding="utf-8")
    titulo = limpio(re.search(r"<titl>(.*?)</titl>", t, re.S).group(1))
    anios = sorted(set(re.findall(r"aplica para el (\d{4})", t)))
    casos = sorted(set(re.findall(r"<caseQnty>\s*(\d+)\s*</caseQnty>", t)))
    return {"titulo": titulo, "anio_estructura": anios, "caseQnty_valores": casos}


def texto_pdf(p: Path, primera_pagina=False) -> str | None:
    cmd = ["pdftotext", "-enc", "UTF-8"] + (["-l", "1"] if primera_pagina else []) + [str(p), "-"]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


# --- Procesamiento de archivos ---------------------------------------------------------------------
def procesar_geih(log: dict) -> list[dict]:
    regs, cg_llaves, ref_header = [], {}, {}
    for num, mes in enumerate(nd.MESES, start=1):
        for mod in ORDEN_MODULOS:
            rel = f"GEIH_2025/{num:02d}_{mes}/{mod}.csv"
            p = RAW / rel
            claim, texto = GEIH_UNIDAD[mod]
            r = {"mes": mes, "num_mes": num, "modulo": mod, "ruta": rel, "unidad": claim,
                 "unidad_texto": texto, "existe": p.exists()}
            if not p.exists():
                regs.append(r)
                continue
            rule = nd.LECTURA["GEIH_csv"]
            r.update(analizar_bytes(p))
            r["lectura_ok"] = lectura_ok("GEIH_csv", r)
            r["sep"] = rule["sep"]
            r.update(contar_csv(p, rule["encoding"], rule["sep"]))
            df = claves(p, rule["encoding"], rule["sep"], HOGAR_GEIH + ["ORDEN", "MES", "PERIODO"])
            r["hogares"] = distintos(df, HOGAR_GEIH)
            pk = HOGAR_GEIH + ["ORDEN"]
            r["personas"] = distintos(df, pk)
            r["llave_unica_hogar"] = r["hogares"] == r["filas"]
            r["llave_unica_persona"] = (r["personas"] == r["filas"]) if r["personas"] is not None else None
            r["mes_ok"] = set(df["MES"].unique()) == {f"{num:02d}"}
            r["periodo_ok"] = bool(df["PERIODO"].str.startswith(ANIO).all())
            r["claim_ok"] = verificar_claim(claim, r["llave_unica_hogar"], r["llave_unica_persona"])
            if claim == "persona":
                llave = df["DIRECTORIO"] + "|" + df["SECUENCIA_P"] + "|" + df["HOGAR"] + "|" + df["ORDEN"]
                if mod == "caracteristicas_generales":
                    cg_llaves[mes] = set(llave)
                r["_llave"] = llave
            ref_header.setdefault(mod, r["header"])
            r["header_igual_enero"] = r["header"] == ref_header[mod]
            a = log.get(rel)
            r["sha_log"] = a["sha256"] if a else None
            r["sha_coincide_log"] = bool(a and a["sha256"] == r["sha256"])
            r["zip"] = a["zip"] if a else None
            regs.append(r)
    for r in regs:
        llave = r.pop("_llave", None)
        if llave is not None and r["modulo"] != "caracteristicas_generales":
            r["llaves_en_cg"] = bool(set(llave) <= cg_llaves[r["mes"]])
    return regs


def procesar_enph(log: dict, labs: dict) -> list[dict]:
    regs = []
    enc_h = nd.LECTURA["ENPH_csv"]
    hog = pd.read_csv(RAW / "ENPH_2017/hogares/viviendas_hogares.csv", sep=";", encoding=enc_h["encoding"], dtype=str,
                      usecols=["DIRECTORIO", "SECUENCIA_P"], keep_default_na=False)
    dirs_hogares = set(hog["DIRECTORIO"])
    pares_hogares = set(zip(hog["DIRECTORIO"], hog["SECUENCIA_P"]))
    for regla in nd.ENPH_REGLAS:
        rel = regla.destino
        efectivo = rel if (RAW / rel).exists() else ALIAS.get(rel, rel)
        p = RAW / efectivo
        claim, texto, var = ENPH_UNIDAD[rel]
        clave = f"ENPH_{Path(rel).suffix[1:]}"
        r = {"ruta": rel, "ruta_efectiva": efectivo, "renombre_pendiente": efectivo != rel,
             "unidad": claim, "unidad_texto": texto, "existe": p.exists(), "lectura": clave}
        if not p.exists():
            regs.append(r)
            continue
        rule = nd.LECTURA[clave]
        r.update(analizar_bytes(p))
        r["lectura_ok"] = lectura_ok(clave, r)
        r["sep"] = rule["sep"]
        r.update(contar_csv(p, rule["encoding"], rule["sep"]))
        cols = [c.lstrip("﻿") for c in r["header"]]
        r["columnas_fex"] = [c for c in cols if c.upper().startswith("FEX")]
        df = claves(p, rule["encoding"], rule["sep"], ["DIRECTORIO", "SECUENCIA_ENCUESTA", "SECUENCIA_P", "ORDEN"])
        r["hogares"] = distintos(df, ["DIRECTORIO"])
        r["dir_en_hogares"] = set(df["DIRECTORIO"]) <= dirs_hogares
        r["llaves_unicas"] = [k for k, c in KEYS_ENPH.items() if distintos(df, c) == r["filas"]]
        r["llave_minima_unica"] = NOMBRE_LLAVE[r["llaves_unicas"][0]] if r["llaves_unicas"] else "ninguna"
        r["filas_por_hogar"] = round(r["filas"] / r["hogares"], 3) if r["hogares"] else None
        # efecto de aplicar a ENPH la regla de unión de GEIH (DIRECTORIO+SECUENCIA_P)
        r["pct_filas_enlazan_dir_sp"] = round(100 * sum(1 for t in zip(df["DIRECTORIO"], df["SECUENCIA_P"]) if t in pares_hogares) / r["filas"], 2)
        r["claim_ok"] = verificar_claim_enph(claim, r)
        tabla_ddi = DDI_ENPH_FILE[rel]
        r["ddi_variable"] = var
        r["ddi_etiqueta"] = labs.get((tabla_ddi, var)) if var else None
        a = log.get(rel) or log.get(efectivo)
        r["sha_log"] = a["sha256"] if a else None
        r["sha_coincide_log"] = bool(a and a["sha256"] == r["sha256"])
        r["zip"] = a["zip"] if a else None
        del r["header"]
        regs.append(r)
    return regs


def procedencia_gdh(enph: list[dict]) -> dict:
    """Evidencia de integridad de gastos_diarios_hogar.txt (descarga del 20 sep 2026)."""
    reg = next(r for r in enph if r["ruta"].endswith("gastos_diarios_hogar.txt"))
    zp = DESCARGAS / "Gastos diarios Urbanos.zip"
    out = {"zip": zp.name, "zip_bytes": zp.stat().st_size, "zip_sha256": sha256_path(zp),
           "zip_mtime": datetime.fromtimestamp(zp.stat().st_mtime).isoformat(timespec="seconds"),
           "txt_sha256": reg.get("sha256"), "txt_filas": reg.get("filas"), "txt_columnas": reg.get("columnas")}
    with zipfile.ZipFile(zp) as zf:
        out["crc_zip_ok"] = zf.testzip() is None
        txt = next(i for i in zf.infolist() if i.filename.lower().endswith(".txt"))
        sav = next(i for i in zf.infolist() if i.filename.lower().endswith(".sav"))
        out["txt_miembro_fecha"] = "%04d-%02d-%02d %02d:%02d" % txt.date_time[:5]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "x.sav"
            with zf.open(sav) as src, open(tmp, "wb") as dst:
                while c := src.read(CHUNK):
                    dst.write(c)
            _, meta = pyreadstat.read_sav(str(tmp), metadataonly=True)
        out["sav_filas"], out["sav_columnas"] = meta.number_rows, meta.number_columns
    out["txt_igual_sav"] = (out["sav_filas"], out["sav_columnas"]) == (reg.get("filas"), reg.get("columnas"))
    out["irregulares"], out["termina_en_salto"] = reg.get("irregulares"), reg.get("termina_en_salto")
    return out


def p75xx(enph: list[dict], labs: dict) -> dict:
    perso = "Caracteristicas generales personas"
    fam = {}
    for pref in ("P7510", "P7513"):
        cols = sorted(k[1] for k in labs if k[0] == perso and k[1].startswith(pref))
        fam[pref] = {"columnas": cols, "ejemplo": {c: labs[(perso, c)] for c in cols[:1]}}
    hog = RAW / "ENPH_2017/hogares/viviendas_hogares.csv"
    enc = nd.LECTURA["ENPH_csv"]
    cab_h = [c for c in pd.read_csv(hog, sep=";", encoding=enc["encoding"], nrows=0).columns] if hog.exists() else []
    cab_p = list(pd.read_csv(RAW / "ENPH_2017/personas/caracteristicas_generales_personas.csv", sep=";",
                             encoding=enc["encoding"], nrows=0).columns)
    otros = {}
    for r in enph:
        if r["existe"] and not r["ruta"].endswith(("viviendas_hogares.csv", "caracteristicas_generales_personas.csv")):
            c = pd.read_csv(RAW / r["ruta_efectiva"], sep=nd.LECTURA[r["lectura"]]["sep"],
                            encoding=nd.LECTURA[r["lectura"]]["encoding"], nrows=0).columns
            if any(x.startswith(("P7510", "P7513")) for x in c):
                otros[r["ruta"]] = True
    for pref in ("P7510", "P7513"):
        fam[pref]["en_personas"] = sum(c.startswith(pref) for c in cab_p)
        fam[pref]["en_hogares"] = sum(c.startswith(pref) for c in cab_h)
        fam[pref]["exacta_en_personas"] = pref in cab_p
    fam["otros_archivos"] = sorted(otros)
    return fam


def control_de_cambios() -> dict:
    d = RAW / "GEIH_2025/_metadatos"
    wb = openpyxl.load_workbook(d / "CONTROL DE CAMBIOS FORMULARIO GEIH.xlsx", read_only=True, data_only=True)
    instr = " ".join(str(c) for r in wb["Instructivo"].iter_rows(values_only=True) for c in r if c)
    rango = re.search(r"desde el año (\d{4}) hasta el (\d{4})", instr)
    tipos = ["IC", "EC", "IP", "EP", "IA", "EA", "O"]
    bloques, actual = [], None
    for i, r in enumerate(wb["Cambios Formulario"].iter_rows(values_only=True), start=1):
        if i < 9:
            continue
        if r[0] or r[1] or r[2]:
            actual = {"anio": str(r[0]).strip(), "trimestre": str(r[1]).strip(),
                      "etapas": re.sub(r"\s+", " ", str(r[2])).strip(), "por_tipo": {}, "n": 0}
            bloques.append(actual)
        if actual and any(r[3:10]):
            actual["n"] += 1
            for k, t in enumerate(tipos):
                if r[3 + k]:
                    actual["por_tipo"][t] = actual["por_tipo"].get(t, 0) + 1
    form = texto_pdf(d / "FORMULARIO_GEIH.pdf", primera_pagina=True)
    etapas = re.search(r"Etapas\s+(\d{4})\s*-\s*(\d{4})\.\s*([^\n]+)", form) if form else None
    man = texto_pdf(d / "ManualRecoleccion-GEIH-2025.pdf")
    anios_man = re.findall(r"enero\s*[–-]\s*diciembre\s*(\d{4})", man, re.I) if man else []
    return {"rango_instructivo": rango.groups() if rango else None, "bloques": bloques,
            "hay_entradas_2025": any(b["anio"] == ANIO for b in bloques),
            "formulario_etapas": (etapas.group(1), etapas.group(2), etapas.group(3).strip().rstrip(".")) if etapas else None,
            "manual_anio": max(set(anios_man), key=anios_man.count) if anios_man else None}


def analisis_diciembre(geih: list[dict]) -> dict:
    por_mes = {}
    for num, mes in enumerate(nd.MESES, start=1):
        base = RAW / f"GEIH_2025/{num:02d}_{mes}"
        enc, sep = nd.LECTURA["GEIH_csv"]["encoding"], nd.LECTURA["GEIH_csv"]["sep"]
        cg = pd.read_csv(base / "caracteristicas_generales.csv", sep=sep, encoding=enc, dtype=str,
                         usecols=["PERIODO", "CLASE", "DPTO", "FEX_C18"], keep_default_na=False)
        hg = pd.read_csv(base / "datos_hogar.csv", sep=sep, encoding=enc, dtype=str,
                         usecols=["CLASE", "DPTO"], keep_default_na=False)
        fex = pd.to_numeric(cg["FEX_C18"].str.replace(",", "."), errors="raise")
        semanas = cg["PERIODO"].value_counts().sort_index()
        por_mes[mes] = {"personas": len(cg), "hogares": len(hg), "pers_por_hogar": len(cg) / len(hg),
                        "fex_personas_M": float(fex.sum() / 1e6), "n_semanas": int(semanas.size),
                        "semanas": [p[-2:] for p in semanas.index], "filas_ultima_semana": int(semanas.iloc[-1]), "filas_semanas_previas_media": float(semanas.iloc[:-1].mean()),
                        "clase_personas": cg["CLASE"].value_counts().to_dict(), "clase_hogares": hg["CLASE"].value_counts().to_dict(),
                        "dpto_hogares": hg["DPTO"].value_counts().to_dict(), "dpto_personas": cg["DPTO"].value_counts().to_dict()}
    otros = [m for m in nd.MESES if m != "diciembre"]
    med = lambda k: statistics.median(por_mes[m][k] for m in otros)  # noqa: E731
    res = {"por_mes": {m: {k: v for k, v in d.items() if not k.startswith(("clase", "dpto"))} for m, d in por_mes.items()},
           "mediana_otros": {k: med(k) for k in ("personas", "hogares", "pers_por_hogar")}}
    res["dic_minimo_pers_por_hogar"] = por_mes["diciembre"]["pers_por_hogar"] == min(d["pers_por_hogar"] for d in por_mes.values())
    res["fex_creciente"] = all(por_mes[a]["fex_personas_M"] < por_mes[b]["fex_personas_M"] for a, b in zip(nd.MESES, nd.MESES[1:]))
    res["hogares_min_mes"] = min(nd.MESES, key=lambda m: por_mes[m]["hogares"])
    for nivel in ("personas", "hogares"):
        clases = {}
        for c in sorted(por_mes["diciembre"][f"clase_{nivel}"]):
            v = {m: por_mes[m][f"clase_{nivel}"].get(c, 0) for m in nd.MESES}
            oth = [v[m] for m in otros]
            clases[c] = {"dic": v["diciembre"], "media_otros": statistics.mean(oth), "min_otros": min(oth), "max_otros": max(oth)}
        res[f"clase_{nivel}"] = clases
        dptos = sorted(por_mes["diciembre"][f"dpto_{nivel}"])
        bajo = 0
        for dp in dptos:
            oth = [por_mes[m][f"dpto_{nivel}"].get(dp, 0) for m in otros]
            bajo += por_mes["diciembre"][f"dpto_{nivel}"].get(dp, 0) < min(oth)
        res[f"dptos_bajo_su_minimo_{nivel}"] = {"n": int(bajo), "de": len(dptos)}
    rank = {}
    for mod in ORDEN_MODULOS:
        f = {r["mes"]: r["filas"] for r in geih if r["modulo"] == mod and r.get("filas")}
        orden = sorted(f, key=f.get)
        rank[mod] = {"dic_es_minimo": orden[0] == "diciembre", "posicion_desde_abajo": orden.index("diciembre") + 1,
                     "menores_que_dic": [m for m in orden if f[m] < f["diciembre"]]}
    res["ranking_modulos"] = rank
    met = texto_pdf(RAW / "GEIH_2025/_metadatos/METODOLOGÍA GENERAL GRAN ENCUESTA INTEGRADA DE HOGARES GEIH.pdf")
    if met:
        m = re.search(r"mensualmente ([\d\.]+) hogares en las 32 ciudades capitales de departamento y ([\d\.]+) en el resto",
                      re.sub(r"\s+", " ", met))
        if m:
            a, b = (int(x.replace(".", "")) for x in m.groups())
            res["diseno_hogares_mes"] = {"capitales": a, "resto": b, "total": a + b}
    return res


# --- Verificaciones previas: Bogotá (código, tamaño de submuestra, cruce estrato × quintil, prefijo NC2R_) -----------
def _norm(s: str) -> str:
    return " ".join(nd.tokens(s))


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.strip().str.replace(",", ".", regex=False), errors="coerce")


def cuantiles_ponderados(x, w, k: int = 5):
    """Cortes ponderados en j/k (el menor valor cuyo peso acumulado alcanza j/k); empates quedan en el mismo grupo."""
    orden = np.argsort(x, kind="mergesort")
    xs, cw = x[orden], np.cumsum(w[orden]) / w.sum()
    cortes = [xs[min(int(np.searchsorted(cw, j / k, side="left")), len(xs) - 1)] for j in range(1, k)]
    q = 1 + sum((x > c).astype(int) for c in cortes)
    return q, [float(c) for c in cortes]


def cruce_estrato_quintil(df: pd.DataFrame, est: str, ing: str, w: str, estratos: list[str], k: int = 5) -> dict:
    """Cuantiles ponderados dentro del subconjunto; las celdas se cuentan SIN ponderar (observaciones)."""
    d = df[df[est].isin(estratos) & df[ing].notna() & df[w].notna()].reset_index(drop=True)
    q, cortes = cuantiles_ponderados(d[ing].to_numpy(float), d[w].to_numpy(float), k)
    d["quintil"] = q
    ct = pd.crosstab(d[est], d["quintil"]).reindex(index=estratos, columns=range(1, k + 1), fill_value=0)
    peso = d.groupby("quintil")[w].sum().reindex(range(1, k + 1)).fillna(0)
    return {"n": int(len(d)), "cortes": cortes, "tabla": {e: [int(v) for v in ct.loc[e]] for e in estratos},
            "celdas": int(ct.size), "celdas_menos_30": int((ct < 30).to_numpy().sum()), "celdas_vacias": int((ct == 0).to_numpy().sum()),
            "minimo": int(ct.to_numpy().min()), "pct_peso_por_quintil": [round(float(100 * v / peso.sum()), 1) for v in peso]}


def bogota_codigos() -> dict:
    d = RAW / "GEIH_2025/_metadatos"
    ws = openpyxl.load_workbook(d / "Diccionario de datos - GEIH 2025.xlsx", read_only=True, data_only=True)["Plantilla Diccionario de Datos"]
    actual, hall, tablas, clase = None, {"AREA": [], "DPTO": []}, set(), set()
    for i, r in enumerate(ws.iter_rows(values_only=True), start=1):
        c = [("" if x is None else str(x).replace("\n", " ").strip()) for x in r]
        tablas |= {x for x in c if re.fullmatch(r"SAS\d+NAL\d{4}", x)}
        nz = [x for x in c if x]
        if not nz:
            continue
        if len(c) > 4 and re.fullmatch(r"[A-Z][A-Z0-9_]+", c[4]):  # el nombre de la variable está en la 5.ª columna
            actual = c[4]
            if actual == "CLASE":  # el primer par código/nombre viene en la misma fila de la variable
                for j in range(len(c) - 1):
                    if re.fullmatch(r"\d", c[j]) and re.fullmatch(r"[A-Za-z]+", c[j + 1]):
                        clase.add(f"{c[j]} {c[j + 1]}")
        elif len(nz) == 2 and re.fullmatch(r"\d{1,2}", nz[0]):  # fila de la lista de códigos: solo (código, nombre)
            if actual in hall and "bogota" in _norm(nz[1]):
                hall[actual].append({"fila": i, "codigo": nz[0], "nombre": nz[1]})
            elif actual == "CLASE" and re.fullmatch(r"[A-Za-z]+", nz[1]):
                clase.add(f"{nz[0]} {nz[1]}")
    ddi_t = (d / "DANE-DIMPE-GEIH-2025.xml").read_text(encoding="utf-8")
    ddi = {}
    for v in ("AREA", "DPTO", "CLASE", "P4030S1A1"):
        m = re.search(rf'<var ID="[^"]*"[^>]*name="{v}"[^>]*>(.*?)</var>', ddi_t, re.S)
        ddi[v] = [limpio(re.sub(r"<[^>]+>", " ", x)) for x in re.findall(r"<catgry>(.*?)</catgry>", m.group(1), re.S)]
    sav = next((RAW / "GEIH_2025/_etiquetas").glob("Caracter*.SAV"))
    _, meta = pyreadstat.read_sav(str(sav), metadataonly=True)
    return {"diccionario": {v: {"apariciones": len(h), "filas": [x["fila"] for x in h][:3],
                                "codigos": sorted({x["codigo"] for x in h}), "nombres": sorted({x["nombre"] for x in h})} for v, h in hall.items()},
            "diccionario_clase": sorted(clase), "diccionario_etapas": sorted({t[-4:] for t in tablas}),
            "ddi_bogota": {v: [c for c in ddi[v] if "bogot" in _norm(c)] for v in ("AREA", "DPTO")},
            "ddi_clase": ddi["CLASE"], "ddi_estrato": ddi["P4030S1A1"],
            "sav_etiquetas_valor": {v: len(meta.variable_value_labels.get(v, {})) for v in ("AREA", "DPTO", "CLASE")}}


def bogota_geih(cod_area: str, cod_dpto: str, estratos: list[str]) -> dict:
    enc, sep = nd.LECTURA["GEIH_csv"]["encoding"], nd.LECTURA["GEIH_csv"]["sep"]
    meses, pool, cruces_mes = [], [], []
    for num, mes in enumerate(nd.MESES, start=1):
        b = RAW / f"GEIH_2025/{num:02d}_{mes}"
        h = pd.read_csv(b / "datos_hogar.csv", sep=sep, encoding=enc, dtype=str, keep_default_na=False,
                        usecols=["DIRECTORIO", "SECUENCIA_P", "HOGAR", "AREA", "DPTO", "CLASE", "P4030S1A1"])
        o = pd.read_csv(b / "ocupados.csv", sep=sep, encoding=enc, dtype=str, keep_default_na=False,
                        usecols=["DIRECTORIO", "SECUENCIA_P", "HOGAR", "AREA", "DPTO", "INGLABO", "FEX_C18"])
        meses.append({"mes": mes, "hogares_area": int((h.AREA == cod_area).sum()), "ocupados_area": int((o.AREA == cod_area).sum()),
                      "hogares_dpto": int((h.DPTO == cod_dpto).sum()), "ocupados_dpto": int((o.DPTO == cod_dpto).sum()),
                      "hogares_dpto_fuera_area": int(((h.DPTO == cod_dpto) & (h.AREA != cod_area)).sum()),
                      "area_no_contenida_en_dpto": int(((h.AREA == cod_area) & (h.DPTO != cod_dpto)).sum())})
        m = o[o.AREA == cod_area].merge(h[h.AREA == cod_area][["DIRECTORIO", "SECUENCIA_P", "HOGAR", "P4030S1A1"]],
                                        on=["DIRECTORIO", "SECUENCIA_P", "HOGAR"], how="left", validate="many_to_one")
        m["ingreso"], m["peso"], m["mes"] = _num(m["INGLABO"]), _num(m["FEX_C18"]) / 12, mes
        pool.append(m)
        cruces_mes.append(cruce_estrato_quintil(m, "P4030S1A1", "ingreso", "peso", estratos))
    P = pd.concat(pool)
    res = {"meses": meses, "n_ocupados": len(P), "sin_estrato": int((~P.P4030S1A1.isin(estratos)).sum()),
           "sin_ingreso": int(P.ingreso.isna().sum()), "ingreso_cero": int((P.ingreso == 0).sum()),
           "cruce_12m": cruce_estrato_quintil(P, "P4030S1A1", "ingreso", "peso", estratos)}
    menos = [c["celdas_menos_30"] for c in cruces_mes]
    res["cruce_un_mes"] = {"celdas_menos_30_min": min(menos), "mediana": statistics.median(menos), "max": max(menos), "celdas": cruces_mes[0]["celdas"]}
    return res


def bogota_enph(estratos: list[str]) -> dict:
    E = RAW / "ENPH_2017"
    v = pd.read_csv(E / "hogares/viviendas_hogares.csv", sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False,
                    usecols=["DIRECTORIO", "REGION", "DOMINIO", "P3", "P8520S1A1", "IT", "ICGU", "ICMUG", "ICMDUG", "FEX_C", "NC2R_CC_P5", "NC2R_CC_P6"])
    dom = sorted({x for x in v.DOMINIO.unique() if _norm(x) == "bogota"})
    reg = sorted({x for x in v.REGION.unique() if _norm(x) == "bogota"})
    b = v[v.DOMINIO.isin(dom)].copy()
    pers = pd.read_csv(E / "personas/caracteristicas_generales_personas.csv", sep=";", encoding="utf-8-sig", dtype=str,
                       keep_default_na=False, usecols=["DIRECTORIO"])
    ddi_t = (E / "_metadatos/DANE-DIMPE-ENPH-2016-2017.xml").read_text(encoding="utf-8")
    dominios = re.search(r"dominios de estudio:\s*32 ciudades de departamento:(.{0,400})", re.sub(r"\s+", " ", ddi_t), re.I)
    b["estrato"], b["peso"] = b.P8520S1A1.str.strip(), _num(b.FEX_C)
    res = {"dominio_valores": dom, "region_valores": reg, "hogares_bogota": len(b), "hogares_total": len(v),
           "personas_bogota": int(pers.DIRECTORIO.isin(set(b.DIRECTORIO)).sum()), "personas_total": len(pers),
           "p3_en_bogota": b.P3.value_counts().to_dict(), "region_igual_dominio": bool((v.DOMINIO.isin(dom) == v.REGION.isin(reg)).all()),
           "ddi_lista_dominios_menciona_bogota": bool(dominios and "bogot" in _norm(dominios.group(1))),
           "ddi_region_qstn_menciona_bogota": bool(re.search(r"<qstnLit>\s*<!\[CDATA\[[^\]]*BOGOT[^\]]*\]\]>\s*</qstnLit>", ddi_t, re.I)),
           "estrato_valores": b.estrato.replace("", "(vacío)").value_counts().to_dict()}
    res["sin_estrato_valido"] = int((~b.estrato.isin(estratos)).sum())
    for ing in ("ICGU", "IT", "ICMUG", "ICMDUG"):
        b[ing + "_n"] = _num(b[ing])
    res["ingreso_cero_ICGU"] = int((b.ICGU_n == 0).sum())
    res["cruces"] = {ing: cruce_estrato_quintil(b, "estrato", ing + "_n", "peso", estratos) for ing in ("ICGU", "IT", "ICMUG", "ICMDUG")}
    labs = {}
    for ing in ("ICGU", "IT", "ICMUG", "ICMDUG", "P8520S1A1", "NC2R_CC_P5"):
        m = re.search(rf'<var ID="[^"]*"[^>]*name="{ing}"[^>]*files="F27"[^>]*>(.*?)</var>', ddi_t, re.S)
        labs[ing] = limpio(re.search(r"<labl[^>]*>(.*?)</labl>", m.group(1), re.S).group(1))
        if ing == "P8520S1A1":
            res["ddi_estrato_categorias"] = len(re.findall(r"<catgry>", m.group(1)))
    res["etiquetas_ddi"] = labs
    # NC2R_CC_P6 / P5: relleno por clase (P3) en toda la muestra y en Bogotá
    for var in ("NC2R_CC_P5", "NC2R_CC_P6"):
        lleno = v[var].str.strip() != ""
        res[f"relleno_{var}"] = {"por_P3": {c: {"llenos": int(lleno[v.P3 == c].sum()), "hogares": int((v.P3 == c).sum())} for c in sorted(v.P3.unique())},
                                 "bogota": {"llenos": int(lleno[v.DOMINIO.isin(dom)].sum()), "hogares": len(b)}}
    res["NC2R_CC_P6_valores"] = v.NC2R_CC_P6.str.strip().replace("", "(vacío)").value_counts().to_dict()
    return res


def nc2r(enph: list[dict]) -> dict:
    ddi_t = (RAW / "ENPH_2017/_metadatos/DANE-DIMPE-ENPH-2016-2017.xml").read_text(encoding="utf-8")
    m = re.search(r'<var ID="[^"]*"[^>]*name="NC2R_CC_P6"[^>]*files="(F\d+)"[^>]*>(.*?)</var>', ddi_t, re.S)
    ddi_ids = {a: limpio(re.search(r"<fileName>(.*?)</fileName>", b, re.S).group(1)).replace(".NSDstat", "")
               for a, b in re.findall(r'<fileDscr ID="(F\d+)"[^>]*>(.*?)</fileDscr>', ddi_t, re.S)}
    res = {"ddi_tabla": ddi_ids[m.group(1)], "ddi_etiqueta": limpio(re.search(r"<labl[^>]*>(.*?)</labl>", m.group(2), re.S).group(1)),
           "ddi_categorias": [limpio(re.sub(r"<[^>]+>", " ", c)) for c in re.findall(r"<catgry>(.*?)</catgry>", m.group(2), re.S)]}
    files, sin_r = {}, []
    for r in enph:
        if not r["existe"]:
            continue
        rule = nd.LECTURA[r["lectura"]]
        cols = [c.lstrip("﻿") for c in pd.read_csv(RAW / r["ruta_efectiva"], sep=rule["sep"], encoding=rule["encoding"], nrows=0).columns]
        if any(c.startswith("NC2R_") for c in cols):
            files[r["ruta"]] = sorted({re.match(r"(NC2R_[A-Z0-9]+)", c).group(1) for c in cols if c.startswith("NC2R_")})
        if r["ruta"].startswith("ENPH_2017/rural/") and any(c.startswith("NC2_") for c in cols):
            sin_r.append(r["ruta"])
    res["archivos_con_NC2R"] = files
    res["archivo_de_NC2R_CC_P6"] = [k for k in files if "NC2R_CC" in files[k]]
    res["archivos_rurales_con_NC2_sin_R"] = sin_r
    cdir = RAW / "ENPH_2017/_metadatos"
    textos = {"Cuadernillo 2 rural": texto_pdf(cdir / "CUADERNILLOS/Cuadernillo 2 rural.pdf"),
              "Cuadernillo 2 urbano": texto_pdf(cdir / "CUADERNILLOS/Cuadernillo 2 urbano.pdf")}
    res["pregunta_en_cuadernillo"] = {k: (re.search(r"2\.\s*(La principal forma de pago[^\n]*?fue:)", t).group(1) if t and re.search(r"2\.\s*(La principal forma de pago[^\n]*?fue:)", t) else None) for k, t in textos.items()}
    docs = [cdir / "Ficha_metodologica_ENPH.pdf", cdir / "Metodologia_ENPH.pdf", cdir / "MANUAL_ENPH.pdf", cdir / "boletin-enph-2017.pdf",
            cdir / "Encuesta Nacional de Presupuestos de los Hogares - ENPH.pdf"] + sorted((cdir / "CUADERNILLOS").glob("*.pdf"))
    menciones = definiciones = 0
    res["bogota_en_cuadernillos"] = sum(len(re.findall(r"bogot", texto_pdf(p) or "", re.I)) for p in sorted((cdir / "CUADERNILLOS").glob("*.pdf")))
    res["n_cuadernillos"] = len(list((cdir / "CUADERNILLOS").glob("*.pdf")))
    for p in docs:
        t = texto_pdf(p) or ""
        menciones += len(re.findall(r"NC2R", t))
        definiciones += len(re.findall(r"NC2R_?\s*(?:=|:|significa|corresponde|es el prefijo|equivale)", t, re.I))
    res["menciones_en_pdfs"], res["definiciones_del_prefijo_en_pdfs"], res["n_pdfs"] = menciones, definiciones, len(docs)
    fp: dict[str, list[str]] = {}
    for mm in re.finditer(r'<var ID="[^"]*"[^>]*name="([^"]+)"[^>]*files="(F\d+)"[^>]*>(.*?)</var>', ddi_t, re.S):
        lb = re.search(r"<labl[^>]*>(.*?)</labl>", mm.group(3), re.S)
        if lb and re.search(r"forma de pago|medio de pago", lb.group(1), re.I):
            fp.setdefault(ddi_ids[mm.group(2)], []).append(mm.group(1))
    res["variables_forma_de_pago"] = {k: {"n": len(v), "ejemplos": v[:4]} for k, v in fp.items()}
    return res


def _huellas(P: pd.DataFrame, edad_fn) -> pd.DataFrame:
    g = P.dropna(subset=["edad"]).assign(e=lambda d: edad_fn(d["edad"])).groupby("k")
    fp = g.apply(lambda x: (x["DPTO"].iloc[0], x["AREA"].iloc[0], tuple(sorted(zip(x["P3271"], x["e"])))), include_groups=False)
    return pd.DataFrame({"fp": fp, "n": g.size(), "m": P.groupby("k")["m"].first()})


def _tasa_pares(df: pd.DataFrame) -> dict:
    """Pares de hogares con la misma huella: mismo mes vs. meses distintos, normalizados por los pares posibles del mismo estrato."""
    grp: dict = defaultdict(Counter)
    estr: dict = defaultdict(Counter)
    for fp, mm in zip(df["fp"], df["m"]):
        grp[fp][mm] += 1
        estr[(fp[0], fp[1])][mm] += 1
    same = sum(c * (c - 1) // 2 for cnt in grp.values() for c in cnt.values())
    cross = sum(a * b for cnt in grp.values() for m1, a in cnt.items() for m2, b in cnt.items() if m1 < m2)
    pos_same = sum(c * (c - 1) // 2 for cnt in estr.values() for c in cnt.values())
    pos_cross = sum(a * b for cnt in estr.values() for m1, a in cnt.items() for m2, b in cnt.items() if m1 < m2)
    rs, rc = same / pos_same, cross / pos_cross
    return {"hogares": int(len(df)), "pares_mismo_mes": int(same), "pares_entre_meses": int(cross), "tasa_mismo_mes": rs,
            "tasa_entre_meses": rc, "razon": (rc / rs) if rs else None}


def rotacion_geih(cod_area: str) -> dict:
    enc, sep = nd.LECTURA["GEIH_csv"]["encoding"], nd.LECTURA["GEIH_csv"]["sep"]
    H, P = [], []
    for num, mes in enumerate(nd.MESES, start=1):
        b = RAW / f"GEIH_2025/{num:02d}_{mes}"
        h = pd.read_csv(b / "datos_hogar.csv", sep=sep, encoding=enc, dtype=str, keep_default_na=False,
                        usecols=["DIRECTORIO", "SECUENCIA_P", "HOGAR", "AREA", "DPTO"])
        c = pd.read_csv(b / "caracteristicas_generales.csv", sep=sep, encoding=enc, dtype=str, keep_default_na=False,
                        usecols=["DIRECTORIO", "SECUENCIA_P", "HOGAR", "ORDEN", "AREA", "DPTO", "P3271", "P6040"])
        h["m"], c["m"] = num, num
        H.append(h)
        P.append(c)
    H, P = pd.concat(H, ignore_index=True), pd.concat(P, ignore_index=True)
    H["k"] = H.DIRECTORIO + "|" + H.SECUENCIA_P + "|" + H.HOGAR
    P["k"] = P.DIRECTORIO + "|" + P.SECUENCIA_P + "|" + P.HOGAR
    P["kp"] = P.k + "|" + P.ORDEN
    P["edad"] = pd.to_numeric(P.P6040, errors="coerce")

    def resumen(Hs: pd.DataFrame, Ps: pd.DataFrame) -> dict:
        mk, md, mp = Hs.groupby("k").m.nunique(), Hs.groupby("DIRECTORIO").m.nunique(), Ps.groupby("kp").m.nunique()
        return {"filas_hogares": int(len(Hs)), "directorios_unicos": int(Hs.DIRECTORIO.nunique()), "hogares_unicos": int(Hs.k.nunique()),
                "meses_por_hogar": {int(k): int(v) for k, v in mk.value_counts().sort_index().items()},
                "meses_por_directorio": {int(k): int(v) for k, v in md.value_counts().sort_index().items()},
                "media_meses_por_hogar": float(mk.mean()), "filas_personas": int(len(Ps)), "personas_unicas": int(Ps.kp.nunique()),
                "meses_por_persona": {int(k): int(v) for k, v in mp.value_counts().sort_index().items()}}
    res = {"nacional": resumen(H, P), "bogota": resumen(H[H.AREA == cod_area], P[P.AREA == cod_area])}
    dirn = pd.to_numeric(H.DIRECTORIO)
    rangos = dirn.groupby(H.m).agg(["min", "max", "count"])
    pasos = {}
    for m in range(1, 13):
        x = np.sort(dirn[H.m == m].unique())
        pasos[m] = float(np.mean(np.diff(x) == 1))
    res["directorio_por_mes"] = [{"mes": nd.MESES[m - 1], "min": int(rangos.loc[m, "min"]), "max": int(rangos.loc[m, "max"]),
                                  "pct_pasos_de_1": round(100 * pasos[m], 1)} for m in range(1, 13)]
    res["meses_con_rango_solapado_con_el_siguiente"] = [nd.MESES[m - 1] for m in range(1, 12) if rangos.loc[m, "max"] >= rangos.loc[m + 1, "min"]]
    res["filas_con_directorio_compartido_en_el_mismo_mes"] = int(H.duplicated(["DIRECTORIO", "m"], keep=False).sum())
    res["hogar_igual_secuencia_p"] = bool((H.HOGAR == H.SECUENCIA_P).all())
    res["hogares_con_hogar_mayor_a_1"] = int((H.HOGAR != "1").sum())
    cols_h = list(pd.read_csv(RAW / "GEIH_2025/01_enero/datos_hogar.csv", sep=sep, encoding=enc, nrows=0).columns)
    cols_c = list(pd.read_csv(RAW / "GEIH_2025/01_enero/caracteristicas_generales.csv", sep=sep, encoding=enc, nrows=0).columns)
    res["columnas_de_segmento"] = [c for c in cols_h + cols_c if re.search(r"SEG|UPM|CONGL|MANZ|SECC|PSU|UNIDAD", c, re.I)]
    # Prueba independiente del identificador: huella de composición (DPTO, AREA, sexo y edad de los miembros)
    ex, co = _huellas(P, lambda e: e), _huellas(P, lambda e: e // 5)
    res["huellas"] = {f"{ming}p_{nom}": _tasa_pares(d[d.n >= ming]) for ming in (3, 4) for nom, d in (("edad_exacta", ex), ("edad_tramos_5", co))}
    # citas de la documentación
    met = re.sub(r"\s+", " ", texto_pdf(RAW / "GEIH_2025/_metadatos/METODOLOGÍA GENERAL GRAN ENCUESTA INTEGRADA DE HOGARES GEIH.pdf") or "")
    fic = re.sub(r"\s+", " ", texto_pdf(RAW / "GEIH_2025/_metadatos/FICHA METODOLÓGICA GRAN ENCUESTA INTEGRADA DE HOGARES.pdf") or "")
    def busca(t, pat):
        m = re.search(pat, t)
        return m.group(0) if m else None
    res["citas"] = {
        "agotamiento": busca(met, r"El agotamiento de la fuente aparece cuando se encuesta al hogar en repetidas ocasiones\. Para evitar este inconveniente, se procede a rotar la medida de tamaño cada año\."),
        "ficha_rotacion": busca(fic, r"El mantenimiento de la muestra se da mediante una rotación[^.]*\."),
        "usm": busca(met, r"Unidades Secundarias de Muestreo \(USM\): Son conglomerados de 10 viviendas contiguas en promedio[^.]{0,260}\."),
        "trimestrales": busca(met, r"se generan muestras trimestrales[^.]*\.")}
    return res


def enph_cruce_agrupado(estratos: list[str]) -> dict:
    v = pd.read_csv(RAW / "ENPH_2017/hogares/viviendas_hogares.csv", sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False,
                    usecols=["DIRECTORIO", "DOMINIO", "P3", "P8520S1A1", "ICGU", "FEX_C"])
    pares = [estratos[i:i + 2] for i in range(0, len(estratos), 2)]
    mapa = {e: f"{p[0]}-{p[-1]}" for p in pares for e in p}
    grupos = [f"{p[0]}-{p[-1]}" for p in pares]
    dom = sorted({x for x in v.DOMINIO.unique() if _norm(x) == "bogota"})
    v["grupo"], v["ing"], v["w"] = v.P8520S1A1.str.strip().map(mapa), _num(v.ICGU), _num(v.FEX_C)
    v["uno"] = 1.0
    res = {"grupos": grupos}
    for nombre, sub in (("Bogotá", v[v.DOMINIO.isin(dom)]), ("Urbano nacional (P3=1, incluye Bogotá)", v[v.P3 == "1"])):
        sub = sub.copy()
        res[nombre] = {"hogares": int(len(sub)), "sin_grupo": int(sub.grupo.isna().sum()),
                       "cuantiles_ponderados": cruce_estrato_quintil(sub, "grupo", "ing", "w", grupos),
                       "cuantiles_sin_ponderar": cruce_estrato_quintil(sub, "grupo", "ing", "uno", grupos)}
    return res


def forma_pago_bogota(categorias: list[str]) -> dict:
    v = pd.read_csv(RAW / "ENPH_2017/hogares/viviendas_hogares.csv", sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False,
                    usecols=["DOMINIO", "P3", "NC2R_CC_P6", "FEX_C"])
    dom = sorted({x for x in v.DOMINIO.unique() if _norm(x) == "bogota"})
    b = v[v.DOMINIO.isin(dom)].copy()
    b["c"], b["w"] = b.NC2R_CC_P6.str.strip(), _num(b.FEX_C)
    cods = [c.split(maxsplit=1)[0] for c in categorias]
    resp = b[b.c.isin(cods)]
    wt = float(resp.w.sum())
    filas = [{"codigo": c.split(maxsplit=1)[0], "categoria": c.split(maxsplit=1)[1], "hogares_muestra": int((resp.c == c.split(maxsplit=1)[0]).sum()),
              "pct_hogares_expandido": round(100 * float(resp.w[resp.c == c.split(maxsplit=1)[0]].sum()) / wt, 2)} for c in categorias]
    return {"filas": filas, "hogares_bogota": int(len(b)), "hogares_con_respuesta": int(len(resp)), "hogares_sin_respuesta": int(len(b) - len(resp)),
            "pct_sin_respuesta_ponderado": round(100 * float(b.w[~b.c.isin(cods)].sum()) / float(b.w.sum()), 2),
            "hogares_expandidos_con_respuesta": round(wt), "valores_fuera_de_categorias": int((~b.c.isin(cods) & (b.c != "")).sum())}


def cuadernillos_pago() -> dict:
    d = RAW / "ENPH_2017/_metadatos/CUADERNILLOS"
    out = {}
    for p in sorted(d.glob("Cuadernillo*.pdf")):
        t = re.sub(r"\s+", " ", texto_pdf(p) or "")
        frases = re.findall(r"(?:La principal forma de pago|El medio de pago usado principalmente)[^:]{0,140}:", t)
        cap = re.search(r"D\.\s*GASTOS (?:DIARIOS|SEMANALES DEL HOGAR)[^.]{0,150}?(?:\)|Incluye[^)]*\))", t, re.I)
        out[p.stem] = {"n_preguntas_pago": len(frases), "primera": frases[0] if frases else None, "en_este_cuadernillo": len(re.findall(r"en este cuadernillo", t, re.I)),
                       "recoge_al_recoger": bool(re.search(r"el día que recoja este cuadernillo", t, re.I)),
                       "periodo": next((q for q in ("los catorce días", "la semana pasada") if re.search(q, t, re.I)), None),
                       "capitulos": sorted({m.group(1) for m in re.finditer(r"\b([A-D]1?)\. (?:CARACTER[ÍI]STICAS DEL GASTO EN ALIMENTOS|GASTOS DIARIOS|GASTOS SEMANALES|COMIDAS PREPARADAS)", t)}),
                       "este_subcapitulo": len(re.findall(r"este subcap[ií]tulo", t, re.I)), "capitulo_D": cap.group(0) if cap else None}
    return out


def hashes_metadatos() -> list[dict]:
    out = []
    for base in (RAW / "GEIH_2025/_etiquetas", RAW / "GEIH_2025/_metadatos", RAW / "ENPH_2017/_metadatos"):
        for p in sorted(base.rglob("*")):
            if p.is_file():
                out.append({"ruta": p.relative_to(RAW).as_posix(), "bytes": p.stat().st_size, "sha256": sha256_path(p)})
    return out


# --- Documento -------------------------------------------------------------------------------------
def _tabla_cruce(c: dict, estratos: list[str]) -> str:
    return tabla(["Estrato \\ Quintil"] + [f"Q{q}" for q in range(1, 6)] + ["Total"],
                 [[e] + [("**" + str(v) + "**" if v < 30 else str(v)) for v in c["tabla"][e]] + [sum(c["tabla"][e])] for e in estratos])


def construir_seccion_bogota(bog: dict) -> str:
    cod, g, e, n, est = bog["codigos"], bog["geih"], bog["enph"], bog["nc2r"], bog["estratos"]
    L: list[str] = []
    A = L.append
    dA, dD = cod["diccionario"]["AREA"], cod["diccionario"]["DPTO"]
    ca, cd = bog["cod_area"], bog["cod_dpto"]
    m = g["meses"]
    fmt_c = lambda c: f"{c['celdas_menos_30']} de {c['celdas']}"  # noqa: E731
    A("## 10. Verificaciones previas: Bogotá\n")
    A("Las tres se hicieron antes de escribir código de análisis. Los códigos se leen de las fuentes (no se escriben a mano).\n")
    A("### 10.1 ¿Qué variable identifica a Bogotá?\n")
    A(tabla(["Base", "Variable", "Valor de Bogotá", "Fuente (cita)", "Estado"], [
        ["GEIH 2025", "`AREA` (identificador de área metropolitana / ciudad)", f"`{ca}`",
         f"Diccionario de datos GEIH 2025, hoja «Plantilla Diccionario de Datos», fila {dA['filas'][0]}: «{dA['codigos'][0]} | {dA['nombres'][0]}» (se repite en {dA['apariciones']} tablas del diccionario). DDI GEIH: «{'; '.join(cod['ddi_bogota']['AREA'])}».",
         "CONCORDANTE" if dA["codigos"] == [ca] and cod["ddi_bogota"]["AREA"][0].split()[0] == ca else "REVISAR"],
        ["GEIH 2025", "`DPTO` (identificador de departamento)", f"`{cd}`",
         f"Diccionario, fila {dD['filas'][0]}: «{dD['codigos'][0]} | {dD['nombres'][0]}» ({dD['apariciones']} tablas). DDI GEIH: «{'; '.join(cod['ddi_bogota']['DPTO'])}».",
         "CONCORDANTE" if dD["codigos"] == [cd] and cod["ddi_bogota"]["DPTO"][0].split()[0] == cd else "REVISAR"],
        ["ENPH 2016-2017", "`DOMINIO` (en `viviendas_hogares.csv`)", "texto `" + "`, `".join(e["dominio_valores"]) + "`",
         "No existe código numérico: en el CSV y en el `.sav` el valor es texto y el DDI no lista categorías. Respaldo: la lista de «dominios de estudio: 32 ciudades de departamento» del DDI "
         + ("menciona Bogotá" if e["ddi_lista_dominios_menciona_bogota"] else "NO menciona Bogotá") + ".", "TEXTO, sin código"],
        ["ENPH 2016-2017", "`REGION` (idéntico a `DOMINIO` para Bogotá)", "texto `" + "`, `".join(e["region_valores"]) + "`",
         "El DDI lista las regiones en el texto de la pregunta («" + ("…BOGOTÁ…" if e["ddi_region_qstn_menciona_bogota"] else "sin Bogotá") + "»). "
         + ("`REGION` y `DOMINIO` seleccionan exactamente los mismos hogares." if e["region_igual_dominio"] else "`REGION` y `DOMINIO` NO coinciden."), "TEXTO, sin código"]]))
    A(f"\n**Lo que NO pude confirmar.** Los {n['n_cuadernillos']} cuadernillos de ENPH mencionan «Bogotá» {n['bogota_en_cuadernillos']} veces (son formularios en blanco, sin listas de códigos de dominio), así que no sirven de respaldo para ese valor. "
      f"Los `.SAV` de enero de GEIH traen {cod['sav_etiquetas_valor']['AREA']} etiquetas de valor para `AREA`, {cod['sav_etiquetas_valor']['DPTO']} para `DPTO` y {cod['sav_etiquetas_valor']['CLASE']} para `CLASE`; "
      "la fuente de los códigos de GEIH es el diccionario (y el DDI), no el SAV.\n")
    A("**Precisión en GEIH: `AREA` y `DPTO` no son lo mismo.**\n")
    fuera = sum(x["hogares_dpto_fuera_area"] for x in m)
    A(f"- `AREA == '{ca}'` es siempre un subconjunto de `DPTO == '{cd}'` (hogares con `AREA` de Bogotá fuera de `DPTO` de Bogotá: {sum(x['area_no_contenida_en_dpto'] for x in m)}). "
      f"`DPTO == '{cd}'` agrega {fn(fuera)} hogares en los 12 meses (rurales, `CLASE` de resto, con `AREA` vacía).")
    A("- Para comparar con **ENPH urbano** (todo Bogotá en ENPH es «Cabeceras»: `P3` = " + ", ".join(f"{k}: {fn(v)}" for k, v in e["p3_en_bogota"].items()) + ") "
      f"el equivalente es `AREA == '{ca}'`. `DPTO == '{cd}'` incluye la zona rural de Bogotá D.C.")
    A("- `CLASE` está etiquetada distinto según la fuente: diccionario «" + "; ".join(cod["diccionario_clase"]) + "» vs. DDI «" + "; ".join(cod["ddi_clase"]) + "». No usar la etiqueta para filtrar; usar los códigos.")
    A(f"- El diccionario de GEIH tiene todos sus códigos de tabla en la etapa **{', '.join(cod['diccionario_etapas'])}** (2024): es la misma versión 2024 del formulario, otro indicio del pendiente de comparabilidad semántica de §7.\n")

    A("### 10.2 Tamaño de la submuestra de Bogotá (sin ponderar)\n")
    A("Son tamaños muestrales (observaciones), no poblaciones expandidas.\n")
    A(tabla(["ENPH 2016-2017", "Bogotá", "Total ENPH", "% del total"], [
        ["Hogares (`viviendas_hogares`, `DOMINIO`)", fn(e["hogares_bogota"]), fn(e["hogares_total"]), fn(100 * e["hogares_bogota"] / e["hogares_total"], 1) + " %"],
        ["Personas (`caracteristicas_generales_personas`, por `DIRECTORIO`)", fn(e["personas_bogota"]), fn(e["personas_total"]), fn(100 * e["personas_bogota"] / e["personas_total"], 1) + " %"]]))
    A("\n" + tabla(["Mes", f"Hogares `AREA={ca}`", f"Ocupados `AREA={ca}`", f"Hogares `DPTO={cd}`", f"Ocupados `DPTO={cd}`"],
                   [[x["mes"], fn(x["hogares_area"]), fn(x["ocupados_area"]), fn(x["hogares_dpto"]), fn(x["ocupados_dpto"])] for x in m]
                   + [["**12 meses**"] + [f"**{fn(sum(x[k] for x in m))}**" for k in ("hogares_area", "ocupados_area", "hogares_dpto", "ocupados_dpto")],
                      ["mín–máx mensual"] + [f"{fn(min(x[k] for x in m))}–{fn(max(x[k] for x in m))}" for k in ("hogares_area", "ocupados_area", "hogares_dpto", "ocupados_dpto")]]))
    A("\n*Ocupados* = filas de `ocupados.csv` (personas ocupadas). Los meses no son muestras independientes de hogares distintos: hay rotación de segmentos, y este documento no verificó cuántos hogares se repiten entre meses.\n")

    A("### 10.3 Cruce estrato × quintil de ingreso (solo Bogotá)\n")
    A("Los cuantiles se calculan **ponderados por el factor de expansión** dentro de Bogotá; los conteos de celda son **observaciones sin ponderar**. "
      "Los empates de ingreso quedan en el mismo quintil, por lo que los quintiles no son exactamente del 20 % (ver «% de peso»). "
      "**Se hicieron dos cruces porque la pregunta no decía cuál fuente; son unidades distintas y no comparables entre sí.** Celda «pequeña» = menos de 30 observaciones (en negrita).\n")
    ce = e["cruces"]["ICGU"]
    A(f"**A) ENPH — hogares de Bogotá** (unidad: hogar/unidad de gasto). Estrato: `P8520S1A1` («{e['etiquetas_ddi']['P8520S1A1']}»). "
      f"Ingreso: `ICGU` («{e['etiquetas_ddi']['ICGU']}»), ponderado con `FEX_C`. {fn(ce['n'])} de {fn(e['hogares_bogota'])} hogares entran al cruce "
      f"(excluidos por estrato fuera de {'–'.join([est[0], est[-1]])} o vacío: {e['sin_estrato_valido']}; hogares con `ICGU` = 0 incluidos: {e['ingreso_cero_ICGU']}).\n")
    A(_tabla_cruce(ce, est))
    A(f"\n**Celdas con menos de 30 observaciones: {fmt_c(ce)}** (vacías: {ce['celdas_vacias']}; mínimo: {ce['minimo']}). Cortes del quintil (ICGU, COP): {', '.join(fn(c) for c in ce['cortes'])}. "
      f"% de peso por quintil: {', '.join(fn(p, 1) for p in ce['pct_peso_por_quintil'])}.")
    A("Sensibilidad a la variable de ingreso (celdas < 30): " + "; ".join(f"`{k}` {fmt_c(v)}" for k, v in e["cruces"].items()) + ".\n")
    cg = g["cruce_12m"]
    A(f"**B) GEIH — ocupados de Bogotá (`AREA={ca}`), 12 meses apilados** (unidad: persona ocupada; pesos `FEX_C18/12`). Estrato: `P4030S1A1` del hogar («{'; '.join(cod['ddi_estrato'][:3])}…», DDI GEIH). "
      f"Ingreso: `INGLABO` (ingresos laborales de la persona, **no** ingreso del hogar). {fn(cg['n'])} de {fn(g['n_ocupados'])} ocupados entran "
      f"(sin estrato válido: {fn(g['sin_estrato'])}; sin ingreso: {fn(g['sin_ingreso'])}; con ingreso 0 incluidos: {fn(g['ingreso_cero'])}).\n")
    A(_tabla_cruce(cg, est))
    A(f"\n**Celdas con menos de 30 observaciones: {fmt_c(cg)}** (vacías: {cg['celdas_vacias']}; mínimo: {cg['minimo']}). "
      f"Si se usara **un solo mes** (cruce mensual): entre {g['cruce_un_mes']['celdas_menos_30_min']} y {g['cruce_un_mes']['max']} de {g['cruce_un_mes']['celdas']} celdas con menos de 30 (mediana {fn(g['cruce_un_mes']['mediana'])}).\n")
    A("**Decisiones mías que conviene que confirmes:** (1) quintiles calculados dentro de Bogotá, no sobre el total nacional; (2) ingreso del hogar completo (`ICGU`) en ENPH pero solo ingreso laboral individual en GEIH, porque en los 8 módulos GEIH no construí un ingreso del hogar; "
      "(3) estratos válidos = 1 a 6 (se excluyen `0` y vacío); para ENPH el DDI no trae categorías de `P8520S1A1` ("
      + str(e["ddi_estrato_categorias"]) + " categorías) y el Cuadernillo 1 solo dice «Estrato para tarifa», así que asumo que sus códigos son los del DDI de GEIH para la misma pregunta (`P4030S1A1`): **supuesto no verificado en ENPH**.\n")

    ag = bog["agrupado"]
    A(f"**C) ENPH — estrato agrupado en 3 ({', '.join(ag['grupos'])}) × 5 quintiles de `ICGU`.** Los conteos de celda son observaciones **sin ponderar**. "
      "Los cortes de quintil se calcularon con `FEX_C` (regla de CLAUDE.md); como sensibilidad se reporta también el resultado con cortes **sin ponderar**. "
      "Los quintiles se calculan dentro de cada población (Bogotá; urbano nacional).\n")
    for nombre in [k for k in ag if k != "grupos"]:
        c = ag[nombre]
        cw, cu = c["cuantiles_ponderados"], c["cuantiles_sin_ponderar"]
        A(f"*{nombre}* — {fn(cw['n'])} de {fn(c['hogares'])} hogares entran al cruce (estrato fuera de 1–6 o vacío: {fn(c['sin_grupo'])}).\n")
        A(_tabla_cruce(cw, ag["grupos"]))
        A(f"\n**Celdas con menos de 30 observaciones: {fmt_c(cw)}** con cortes ponderados (mínimo {cw['minimo']}); con cortes sin ponderar: {fmt_c(cu)} (mínimo {cu['minimo']}).\n")

    A("### 10.4 Prefijo `NC2R_` y la variable `NC2R_CC_P6`\n")
    r6 = e["relleno_NC2R_CC_P6"]
    urb, bog_ = r6["por_P3"].get("1", {}), r6["bogota"]
    A(f"**Respuesta corta: no está confirmado que `NC2R_` signifique «cuadernillo 2 rural», y para `NC2R_CC_P6` los datos lo contradicen.**\n")
    A(f"- **Dónde vive:** `{', '.join(n['archivo_de_NC2R_CC_P6'])}` (tabla DDI «{n['ddi_tabla']}»), **no** en un archivo rural de gasto. Un hogar por fila.")
    A(f"- **Etiqueta exacta (DDI):** «{n['ddi_etiqueta']}». Categorías: " + "; ".join(n["ddi_categorias"]) + ".")
    A("- **Pregunta en los cuadernillos:** " + " | ".join(f"{k}: «{v}»" for k, v in n["pregunta_en_cuadernillo"].items())
      + ". La etiqueta del DDI coincide con la redacción del cuadernillo **urbano** («comprar los bienes…»), no con la del rural («comprar o adquirir los bienes…»).")
    A(f"- **A quién se le aplicó (datos):** viene rellena en {fn(urb.get('llenos'))} de {fn(urb.get('hogares'))} hogares urbanos (`P3`=1) y en {fn(bog_['llenos'])} de {fn(bog_['hogares'])} hogares de Bogotá; "
      "por clase: " + "; ".join(f"`P3`={k}: {fn(v['llenos'])}/{fn(v['hogares'])}" for k, v in r6["por_P3"].items()) + ". Es decir, **no es exclusiva de hogares rurales**.")
    A(f"- **Documentación del prefijo:** {n['menciones_en_pdfs']} menciones de «NC2R» en {n['n_pdfs']} PDFs de ENPH (listado de variables), pero {n['definiciones_del_prefijo_en_pdfs']} definiciones del prefijo. No está documentado.")
    A("- **Evidencia a favor de «rural»:** las demás familias `NC2R_*` (" + ", ".join(f"`{p}`" for p in sorted({x for v in n["archivos_con_NC2R"].values() for x in v if x != 'NC2R_CC'})) + ") viven en archivos rurales de gasto (" + ", ".join(f"`{k.split('/')[-1]}`" for k in n["archivos_con_NC2R"] if "/rural/" in k) + ").")
    A("- **Evidencia en contra de que la «R» sea una regla:** archivos rurales que usan `NC2_` **sin** «R» (" + ", ".join(f"`{k.split('/')[-1]}`" for k in n["archivos_rurales_con_NC2_sin_R"]) + "); y `NC2R_CC_*` está poblada en hogares urbanos.")
    A("- **Hipótesis compatible con todo lo anterior (no documentada):** el DANE unificó en una sola columna de `viviendas_hogares` la respuesta de las preguntas equivalentes de los cuadernillos 2 urbano y rural, y la nombró con el prefijo rural. "
      "Explicaría por qué está rellena en hogares urbanos y por qué la etiqueta usa la redacción urbana. No la puedo verificar con los archivos disponibles.")
    A("- **Conclusión operativa:** tratar `NC2R_` como un nombre heredado de la codificación del cuadernillo 2, no como un indicador de área. Para filtrar por área usar `P3`/`DOMINIO`, nunca el prefijo.")
    fp = n["variables_forma_de_pago"]
    A("- **Relevante para la tesis (forma de pago):** variables con «forma/medio de pago» en su etiqueta DDI: " + "; ".join(f"«{k}»: {v['n']} (p. ej. {', '.join('`' + x + '`' for x in v['ejemplos'])})" for k, v in fp.items()) + ".\n")

    cp = bog["cuadernillos_pago"]
    A("### 10.5 ¿A qué cuadernillo se refiere «los bienes mencionados en este cuadernillo»?\n")
    A("**Al cuadernillo 2 (versión urbana o rural, según el hogar). No al cuadernillo 3.** Comparación del texto de los cinco cuadernillos:\n")
    A(tabla(["Cuadernillo", "Preguntas de forma/medio de pago", "Primera redacción", "«en este cuadernillo»", "«este subcapítulo»"], [
        [k, v["n_preguntas_pago"], (f"«{v['primera']}»" if v["primera"] else "—"), v["en_este_cuadernillo"], v["este_subcapitulo"]] for k, v in cp.items()]))
    u, r = cp.get("Cuadernillo 2 urbano", {}), cp.get("Cuadernillo 2 rural", {})
    A("\n- **Cuadernillo 2 urbano:** la pregunta cierra el diario"
      + (" (el encuestador la hace «el día que recoja este cuadernillo diligenciado»)" if u.get("recoge_al_recoger") else "")
      + (f"; el periodo de referencia de la pregunta anterior es «{u['periodo']}»" if u.get("periodo") else "")
      + (f". Capítulos con encabezado detectado: {', '.join(u['capitulos'])}. Capítulo D: «{u['capitulo_D']}»." if u.get("capitulos") and u.get("capitulo_D") else "."))
    A("- **Cuadernillo 2 rural:** misma pregunta con «comprar o adquirir»"
      + (f"; periodo de referencia «{r['periodo']}»" if r.get("periodo") else "")
      + (f". Capítulo D: «{r['capitulo_D']}»." if r.get("capitulo_D") else "."))
    c3 = cp.get("Cuadernillo 3", {})
    A(f"- **Cuadernillo 3 (gastos menos frecuentes):** no comparte la pregunta. Pregunta el medio de pago **por subcapítulo** («este subcapítulo», {c3.get('este_subcapitulo')} menciones), "
      "que en los datos son las variables `P438*` del archivo `hogares/gastos_menos_frecuentes_medio_pago.csv`; no es `NC2R_CC_P6`.")
    c4 = cp.get("Cuadernillo 4", {})
    A(f"- **Cuadernillo 4 (gastos diarios personales):** {c4.get('n_preguntas_pago', '—')} preguntas de forma de pago; sus diarios personales quedan fuera de `NC2R_CC_P6`. "
      "Ojo: el capítulo D del cuadernillo 2 incluye «los gastos personales de quien diligencia/brinda la información», así que la respuesta puede abarcar parte del gasto personal de esa persona.")
    A("- **Alcance real de la respuesta:** una sola respuesta por hogar sobre los bienes registrados en el cuadernillo 2 (gastos frecuentes: alimentos, comidas fuera del hogar y demás diario/semanal). "
      "**No cubre todo el gasto del hogar** (los menos frecuentes son del cuadernillo 3).")
    p5 = e["etiquetas_ddi"]["NC2R_CC_P5"]
    A(f"- **Matiz sobre las etiquetas DDI:** `NC2R_CC_P5` dice «{p5}» ("
      + ("redacción del cuadernillo **rural**: «semana pasada»" if "semana pasada" in p5.lower() else "sin «semana pasada»")
      + f"), mientras `NC2R_CC_P6` usa la redacción **urbana**. Es coherente con una columna que reúne las respuestas de ambos cuadernillos, pero mezcla periodos de referencia distintos ({u.get('periodo')} en el urbano; {r.get('periodo')} en el rural).\n")

    fpb = bog["forma_pago"]
    A("### 10.6 Forma de pago principal en Bogotá (hogares, expandido con `FEX_C`)\n")
    A("Enunciado correcto: **«% de hogares cuya forma de pago principal es X»**. No es un % de transacciones ni de gasto: es una respuesta por hogar, sobre los bienes del cuadernillo 2.\n")
    A(tabla(["Código", "Forma de pago principal", "Hogares en la muestra", "% de hogares (expandido)"],
            [[f["codigo"], f["categoria"], fn(f["hogares_muestra"]), fn(f["pct_hogares_expandido"], 2) + " %"] for f in fpb["filas"]]
            + [["", "**Total con respuesta**", f"**{fn(fpb['hogares_con_respuesta'])}**", "**100,00 %**"]]))
    A(f"\nBase: {fn(fpb['hogares_con_respuesta'])} de {fn(fpb['hogares_bogota'])} hogares de Bogotá con respuesta ({fn(fpb['hogares_expandidos_con_respuesta'])} hogares expandidos). "
      f"Sin respuesta: {fn(fpb['hogares_sin_respuesta'])} hogares ({fn(fpb['pct_sin_respuesta_ponderado'], 2)} % expandido); no están en el denominador de la tabla. "
      f"Valores fuera de las 6 categorías: {fn(fpb['valores_fuera_de_categorias'])}. "
      "La expansión con `FEX_C` no corrige la no respuesta del ítem, y no se calcularon errores estándar (el archivo no trae identificador de segmento). Con categorías de pocos hogares en la muestra, el % expandido es poco fiable.\n")
    return "\n".join(L) + "\n"


def construir_seccion_rotacion(bog: dict) -> str:
    rot = bog["rotacion"]
    n, b = rot["nacional"], rot["bogota"]
    ci = rot["citas"]
    L: list[str] = []
    A = L.append
    A("## 11. Rotación de la muestra GEIH y apilamiento de 12 meses\n")
    A("### 11.1 Qué documenta el DANE\n")
    for k, etq in (("agotamiento", "Metodología general (mantenimiento de la muestra)"), ("ficha_rotacion", "Ficha metodológica (texto extraído del PDF; el PDF trae letras recortadas)"),
                   ("usm", "Metodología general (unidades de muestreo)"), ("trimestrales", "Metodología general (pertinencia y desgaste de la fuente)")):
        if ci[k]:
            A(f"- **{etq}:** «{ci[k]}»")
    A("\n**Lectura.** La rotación documentada es **anual** (se cambia la «medida de tamaño» o segmento cada año) y el DANE reconoce que el desgaste aparece cuando el hogar se encuesta «en repetidas ocasiones». "
      "**No documenta** cuántas veces ni en qué meses se vuelve a visitar un hogar dentro de un mismo año. Las unidades de muestreo son segmentos de ~10 viviendas donde se encuestan todos los hogares.\n")
    A("### 11.2 Qué muestran los archivos públicos de 2025\n")
    def fila(etq, k, f=fn):
        return [etq, f(n[k]), f(b[k])]
    A(tabla(["Medida (`datos_hogar` de los 12 meses apilados)", "Nacional", f"Bogotá (`AREA={bog['cod_area']}`)"], [
        fila("Filas de hogares apiladas", "filas_hogares"), fila("Hogares únicos (`DIRECTORIO`+`SECUENCIA_P`+`HOGAR`)", "hogares_unicos"),
        fila("`DIRECTORIO` únicos (viviendas)", "directorios_unicos"),
        ["Filas por hogar único", fn(n["filas_hogares"] / n["hogares_unicos"], 3), fn(b["filas_hogares"] / b["hogares_unicos"], 3)],
        ["Meses en que aparece cada hogar (nº de meses: nº de hogares)", "; ".join(f"{k}: {fn(v)}" for k, v in n["meses_por_hogar"].items()), "; ".join(f"{k}: {fn(v)}" for k, v in b["meses_por_hogar"].items())],
        ["Meses por hogar: media", fn(n["media_meses_por_hogar"], 2), fn(b["media_meses_por_hogar"], 2)],
        ["Meses en que aparece cada `DIRECTORIO`", "; ".join(f"{k}: {fn(v)}" for k, v in n["meses_por_directorio"].items()), "; ".join(f"{k}: {fn(v)}" for k, v in b["meses_por_directorio"].items())],
        fila("Filas de personas apiladas", "filas_personas"), fila("Personas únicas (llave de hogar + `ORDEN`)", "personas_unicas")]))
    A(f"\n**Un hogar típico aparece en {', '.join(str(k) for k in n['meses_por_hogar'])} mes.** "
      f"La diferencia entre filas de hogares y `DIRECTORIO` únicos ({fn(n['filas_hogares'] - n['directorios_unicos'])}) viene de viviendas con más de un hogar **dentro del mismo mes** "
      f"({fn(rot['filas_con_directorio_compartido_en_el_mismo_mes'])} filas comparten `DIRECTORIO` con otra del mismo mes), no de repeticiones entre meses. "
      f"`HOGAR` es idéntico a `SECUENCIA_P` en {'todas' if rot['hogar_igual_secuencia_p'] else 'NO todas'} las filas.\n")
    A("### 11.3 Por qué eso no basta: `DIRECTORIO` parece un contador por mes\n")
    A(tabla(["Mes", "`DIRECTORIO` mínimo", "`DIRECTORIO` máximo", "% de pasos de +1 entre valores ordenados"],
            [[x["mes"], fn(x["min"]), fn(x["max"]), fn(x["pct_pasos_de_1"], 1) + " %"] for x in rot["directorio_por_mes"]]))
    sol = rot["meses_con_rango_solapado_con_el_siguiente"]
    A(f"\nLos rangos son bloques consecutivos y crecientes en el tiempo" + (f" (solo se solapan los rangos de: {', '.join(sol)})" if sol else "") + ". "
      "Es compatible con un número asignado por orden de extracción (hipótesis; no está documentado) y no con un identificador persistente de vivienda. "
      "Por tanto, que ningún `DIRECTORIO` se repita entre meses **no prueba por sí solo** que los hogares no se repitan: podría ser un efecto del identificador.\n")
    A("### 11.4 Prueba independiente del identificador (composición del hogar)\n")
    A("Huella del hogar = (`DPTO`, `AREA`, sexo y edad de sus miembros). Si hubiera hogares repetidos entre meses, los pares con la misma huella serían **más frecuentes entre meses distintos que dentro del mismo mes**. "
      "Se compara la tasa de pares iguales (sobre los pares posibles del mismo estrato) en ambos casos:\n")
    A(tabla(["Hogares comparados", "Edad", "Hogares", "Pares iguales, mismo mes", "Pares iguales, meses distintos", "Razón (entre meses / mismo mes)", "Nota"], [
        [k.split("_")[0].replace("p", " o más personas"), "exacta" if "exacta" in k else "tramos de 5 años", fn(v["hogares"]), fn(v["pares_mismo_mes"]), fn(v["pares_entre_meses"]),
         fn(v["razon"], 2), "pocos pares: razón inestable" if v["pares_mismo_mes"] < 30 else ""] for k, v in rot["huellas"].items()]))
    A("\nUna razón cercana a 1 significa que no hay exceso de coincidencias entre meses. La prueba detectaría una repetición sustancial de hogares, pero no repeticiones aisladas ni hogares cuya composición cambió entre visitas (nacimientos, cambios de edad de más de un tramo, mudanzas).\n")
    A("### 11.5 Conclusión e implicaciones\n")
    A("**Estado: PENDIENTE (parcial).** Lo verificado y lo no verificado, por separado:\n")
    A(f"- **Verificado en los archivos:** hogares únicos = filas apiladas ({fn(n['hogares_unicos'])} en el país; {fn(b['hogares_unicos'])} en Bogotá); ningún hogar en más de un mes; "
      "la prueba por composición no muestra exceso de coincidencias entre meses.")
    A("- **No verificado:** que el diseño no vuelva a visitar hogares dentro del año. El DANE solo documenta rotación anual de segmentos y el identificador no es persistente; la frecuencia de revisita no está escrita en ningún documento del repositorio.")
    fx = bog["fex_personas_M"]
    A("- **Apilar los 12 meses:** no hay duplicados que eliminar y no corresponde deduplicar por `DIRECTORIO` (los extra son hogares de la misma vivienda). "
      "No se detectó nada que lo contradiga: cada fila-hogar puede tratarse como un hogar distinto, con las salvedades de más abajo.")
    A(f"- **`FEX_C18 / 12`:** la suma mensual de `FEX_C18` (personas) va de {fn(fx[0], 3)} a {fn(fx[1], 3)} millones: es casi constante y crece de mes a mes, coherente con la calibración mensual que menciona la Metodología (no verifiqué cómo se construye `FEX_C18`). "
      "Dividir entre 12 da el promedio anual de 12 cortes mensuales, y esa aritmética no depende de que haya rotación. En principio, si hubiera hogares repetidos lo afectado sería la varianza, no el peso.")
    A(f"- **Lo que sí importa (conglomerados):** la metodología define segmentos de ~10 viviendas donde se encuestan todos los hogares, lo que induce correlación dentro del segmento. "
      f"Los archivos **no traen identificador de segmento ni de UPM** (columnas buscadas: {', '.join(rot['columnas_de_segmento']) or 'ninguna'}), así que no se pueden calcular errores estándar de diseño y los ingenuos subestiman la incertidumbre.")
    A("- **Para la partición train/test (CTGAN, TSTR):** no se detectaron hogares repetidos, así que no se espera filtración por repetición; pero las viviendas vecinas comparten características (hipótesis, no verificada). "
      "Como sensibilidad se podría particionar por bloques de `DIRECTORIO` o por mes; la decisión es tuya.")
    A("- **CLAUDE.md:** la regla `FEX_C18 / 12` sigue vigente. Conviene añadir la nota «GEIH 2025 público: sin panel detectable ni identificador de segmento».\n")
    return "\n".join(L) + "\n"


def texto_fex_enph() -> str:
    """Estado de la verificación de FEX_C (ENPH) a partir de outputs/fex_enph_verificacion.json."""
    ruta = ROOT / "outputs" / "fex_enph_verificacion.json"
    if not ruta.exists():
        return ("\n**`FEX_C` (ENPH): NO VERIFICADO.** Este documento solo confirma que la columna existe en cada tabla. "
                "Ejecutar `tools/verificar_fex_enph.py`.\n")
    v = json.loads(ruta.read_text(encoding="utf-8"))
    ok = all(r["directorios_con_fex_no_constante"] == 0 and r["fex_nulos"] == 0
             and r["filas_fex_igual_a_hogares"] == r["filas"] for r in v.values())
    filas = [[f"`{k}`", fn(r["filas"]), fn(r["directorios"]), fn(r["directorios_con_fex_no_constante"]),
              fn(r["pct_filas_fex_igual_a_hogares"], 2) + " %"] for k, r in v.items()]
    return (
        "\n**`FEX_C` (ENPH): " + ("VERIFICADO como factor del hogar/vivienda" if ok else "REVISAR: NO es uniforme por hogar") + ".** "
        "Fuente documental: `Metodologia_ENPH.pdf`, §2.2.4.1 (Procedimiento de estimación): la calibración se hace «a nivel de vivienda» y "
        "«a la vivienda corresponde un único factor de expansión». Contraste empírico (`tools/verificar_fex_enph.py`, "
        "`outputs/fex_enph_verificacion.json`): en cada tabla `FEX_C` debe ser constante dentro de `DIRECTORIO` e igual al de "
        "`viviendas_hogares`. Se verificaron las tablas de hogares, personas y urbano (**rural fuera de alcance, no verificado**).\n\n"
        + tabla(["Archivo", "Filas", "DIRECTORIO distintos", "DIRECTORIO con FEX_C no constante", "% filas con FEX_C = el de hogares"], filas)
        + "\n\n**Alcance del resultado.** `FEX_C` es un factor de hogar: sirve para estimar por hogar (una fila por hogar) y para personas "
        "(el factor del hogar se aplica a cada miembro). En tablas de registros de gasto, cada fila lleva el factor de su hogar: para "
        "cifras por hogar hay que agregar primero a hogar; ponderar filas de gasto sueltas no da un total de gasto sin ese paso. "
        "No se verificó contra un total poblacional externo.\n")


def construir_md(geih, enph, prov, p75, ctrl, dic, ddig, ddie, meta, bog) -> str:
    L: list[str] = []
    A = L.append
    faltan_g = [r for r in geih if not r["existe"]]
    revisar_g = [r for r in geih if r["existe"] and not (r["sha_coincide_log"] and r["header_igual_enero"] and r["mes_ok"]
                                                         and r["periodo_ok"] and r["filas"] > 0 and r["lectura_ok"]
                                                         and r["irregulares"] == 0 and r["claim_ok"] == "CONSISTENTE")]
    faltan_e = [r for r in enph if not r["existe"]]
    ren = [r for r in enph if r.get("renombre_pendiente")]
    g_ok = [r for r in geih if r["existe"]]
    n_g_id = sum(1 for m in ORDEN_MODULOS if all(r["header_igual_enero"] for r in g_ok if r["modulo"] == m))
    dm, mo = dic["por_mes"]["diciembre"], dic["mediana_otros"]

    A("# Fuentes de datos — referencia de integridad\n")
    A("> Generado por `tools/generar_fuentes_datos.py` desde `data/raw/` (solo lectura). Todas las cifras salen de código; "
      "las mismas están en `outputs/fuentes_datos.json`. Para regenerar: "
      "`.venv\\Scripts\\python.exe tools\\generar_fuentes_datos.py`.\n")
    if ren:
        A("> **AVISO — renombre pendiente:** " + ", ".join(f"`{r['ruta_efectiva']}` debe renombrarse a `{r['ruta']}`" for r in ren)
          + ". Este documento se generó leyendo el nombre viejo; los SHA-256 y conteos no cambian con el renombre.\n")
    A("## 0. Reglas de lectura (fijas)\n")
    A(tabla(["Grupo", "Encoding de carga", "Separador", "Nota"], [
        ["GEIH `.csv`", "`cp1252`", "`;`", "Decodifica todo ASCII; los pocos bytes no ASCII son 0xD1/0xF1 (Ñ/ñ). Nunca UTF-8."],
        ["ENPH `.csv`", "`utf-8-sig`", "`;`", "Trae BOM; con `utf-8` la primera columna sale como `\\ufeffDIRECTORIO`."],
        ["ENPH `.txt`", "`utf-8`", "tab", "ASCII, sin BOM. Conservan la extensión `.txt`."]]))
    A("\nLos archivos se extrajeron **tal cual** (bytes intactos); el SHA-256 de cada uno coincide con el del contenido del zip "
      "(`outputs/normalizar_datos_log.json`). La columna «Encoding detectado» es el real, por decodificación estricta (sin chardet, "
      "que dio `CP874`/`Big5` sobre archivos cp1252).\n")

    A("## 1. Riesgos metodológicos y pendientes\n")
    A(tabla(["#", "Tema", "Estado", "Resumen"], [
        ["1", "Comparabilidad **estructural** GEIH", "VERIFICADO",
         f"Los encabezados de las {len(g_ok)} tablas son idénticos entre meses (mismas columnas, mismo orden): {n_g_id} de {len(ORDEN_MODULOS)} módulos, 12/12 meses."],
        ["2", "Comparabilidad **semántica** GEIH (redacción/definición de preguntas)", "PENDIENTE",
         "El control de cambios de `_metadatos/` no cubre 2025; ver §7. No se puede afirmar ni descartar."],
        ["3", "Menos filas en diciembre", "PENDIENTE (no explicado)", "Diferencia pequeña y difusa; la documentación disponible no la explica; ver §8."],
        ["4", "`gastos_diarios_hogar.txt`", "VERIFICADO (autoconsistencia)", "Descarga fresca del 20 sep 2026; conteo de referencia en §5. No hay cifra oficial contra la cual cotejar."],
        ["5", "Unidad de análisis y **llave de hogar** ENPH", "RIESGO (afecta una regla de CLAUDE.md)",
         f"Solo {sum(r['unidad'] != 'registro' for r in enph)} de {len(enph)} archivos son una fila por hogar/persona; los otros {sum(r['unidad'] == 'registro' for r in enph)} son registros de gasto. "
         "En ENPH el hogar se identifica solo por `DIRECTORIO`; la regla de unión `DIRECTORIO + SECUENCIA_P + HOGAR` es de GEIH y en ENPH pierde filas (ver §4)."],
        ["6", "DDI de GEIH desactualizado", "RIESGO", f"Título «{ddig['titulo']}», «estructura … aplica para el {', '.join(ddig['anio_estructura'])}», `caseQnty` = {', '.join(ddig['caseQnty_valores'])}. No usar como fuente de conteos ni de etiquetas 2025."],
        ["7", "Definición de Bogotá", "RIESGO",
         f"En GEIH, `AREA={bog['cod_area']}` (urbano) y `DPTO={bog['cod_dpto']}` (incluye zona rural) no son equivalentes; en ENPH solo existe el texto `{bog['enph']['dominio_valores'][0]}` (sin código). Ver §10.1."],
        ["8", "Tamaño de muestra de Bogotá", "RIESGO",
         f"Cruce estrato × quintil: {bog['enph']['cruces']['ICGU']['celdas_menos_30']} de {bog['enph']['cruces']['ICGU']['celdas']} celdas con <30 observaciones en ENPH ({fn(bog['enph']['hogares_bogota'])} hogares); "
         f"{bog['geih']['cruce_12m']['celdas_menos_30']} de {bog['geih']['cruce_12m']['celdas']} en GEIH con 12 meses apilados y {bog['geih']['cruce_un_mes']['celdas_menos_30_min']}–{bog['geih']['cruce_un_mes']['max']} con un solo mes. Ver §10.3."],
        ["9", "Prefijo `NC2R_`", "RIESGO", "No está documentado y `NC2R_CC_P6` viene rellena en hogares urbanos: no usar el prefijo para filtrar por área. Ver §10.4."],
        ["10", "Rotación / independencia de los 12 meses de GEIH", "PENDIENTE (parcial)",
         f"Ningún hogar aparece en más de un mes ({fn(bog['rotacion']['nacional']['hogares_unicos'])} hogares únicos = filas apiladas), pero `DIRECTORIO` es un contador por mes y la frecuencia de revisita no está documentada; "
         "sin identificador de segmento no hay errores estándar de diseño. `FEX_C18/12` sigue siendo válido. Ver §11."],
    ]))
    A("\n**Sobre 1 y 2 (son dos cosas distintas).** Que los nombres y el orden de columnas coincidan sostiene el apilamiento *técnico* de los 12 meses. "
      "No sostiene la comparabilidad *semántica*: un cambio de redacción de una pregunta, de una alternativa de respuesta o de una definición no altera el nombre de la columna. "
      "Esa revisión depende del control de cambios del formulario, y ese documento no llega a 2025 (§7).\n")

    A("## 2. Verificación GEIH 2025: 12 meses × 8 módulos\n")
    A("`OK` = existe, SHA-256 igual al del zip, encabezado idéntico al de enero, `MES` y `PERIODO` (2025) coherentes con la carpeta, ≥1 fila, "
      "sin filas irregulares, decodifica con la regla fija y la unidad declarada es consistente con las llaves. `FALTA` = no existe. `REVISAR` = existe pero falla algún control.\n")
    filas = []
    for num, mes in enumerate(nd.MESES, start=1):
        fila = [f"{num:02d}_{mes}"]
        for mod in ORDEN_MODULOS:
            r = next(x for x in geih if x["num_mes"] == num and x["modulo"] == mod)
            if not r["existe"]:
                fila.append("FALTA")
            elif r in revisar_g:
                fila.append("REVISAR")
            else:
                fila.append("OK")
        filas.append(fila)
    A(tabla(["Mes"] + ORDEN_MODULOS, filas))
    A(f"\nResumen: {len(g_ok) - len(revisar_g)} OK, {len(revisar_g)} REVISAR, {len(faltan_g)} FALTA (de {len(geih)}). "
      f"`n_meses` = {len({r['mes'] for r in g_ok})}.\n")
    A("**ENPH 2016-2017 (16 archivos):**\n")
    A(tabla(["Archivo", "Estado"], [[f"`{r['ruta']}`", "FALTA" if not r["existe"] else
                                     ("OK" if (r["sha_coincide_log"] and r["lectura_ok"] and r["irregulares"] == 0 and r["claim_ok"] == "CONSISTENTE") else "REVISAR")]
                                    for r in enph]))
    A("\nCriterio de `OK` en ENPH: existe, SHA-256 igual al del zip, decodifica con la regla fija, sin filas irregulares y unidad declarada consistente con las llaves (§4).\n")

    A("## 3. GEIH 2025 — detalle por archivo (96)\n")
    A("Unidad: `persona` = una fila por (`DIRECTORIO`, `SECUENCIA_P`, `HOGAR`, `ORDEN`); `hogar` = una fila por (`DIRECTORIO`, `SECUENCIA_P`, `HOGAR`). "
      "Factor de expansión: `FEX_C18` (presente en los 8 módulos); al apilar los 12 meses, `FEX_C18 / 12`.\n")
    A(tabla(["Módulo", "Unidad de análisis", "Columnas", "Filas (mín–máx)", "Encabezado igual 12/12", "Llave única 12/12", "Llaves ⊂ CG 12/12"], [
        [m, GEIH_UNIDAD[m][1],
         next(r["columnas"] for r in g_ok if r["modulo"] == m),
         f"{fn(min(r['filas'] for r in g_ok if r['modulo'] == m))}–{fn(max(r['filas'] for r in g_ok if r['modulo'] == m))}",
         "sí" if all(r["header_igual_enero"] for r in g_ok if r["modulo"] == m) else "NO",
         "sí" if all(r["claim_ok"] == "CONSISTENTE" for r in g_ok if r["modulo"] == m) else "NO",
         "n/a" if m in ("caracteristicas_generales", "datos_hogar") else ("sí" if all(r.get("llaves_en_cg") for r in g_ok if r["modulo"] == m) else "NO")]
        for m in ORDEN_MODULOS]))
    A("\n")
    A(tabla(["Mes", "Módulo", "Ruta destino", "Unidad", "Filas", "Cols", "SHA-256", "Encoding detectado", "Sep"], [
        [r["mes"], r["modulo"], f"`{r['ruta']}`", r["unidad"], fn(r.get("filas")), r.get("columnas", "—"),
         f"`{r['sha256']}`" if r["existe"] else "—", r.get("encoding", "—"), "`;`" if r["existe"] else "—"] for r in geih]))
    A("\n")

    A("## 4. ENPH 2016-2017 — unidad de análisis y llaves (16 archivos)\n")
    n_reg = sum(r["unidad"] == "registro" for r in enph if r["existe"])
    A(f"**{n_reg} de los {len(enph)} archivos son registros de gasto: ninguno es una fila por hogar.**\n")
    A("**Llave de hogar en ENPH = `DIRECTORIO` (verificado).** En `viviendas_hogares` hay una fila por `DIRECTORIO` y `SECUENCIA_P` y `SECUENCIA_ENCUESTA` valen siempre 1; "
      "y todo `DIRECTORIO` de los 16 archivos existe en `viviendas_hogares` (columna «DIRECTORIO ⊂ hogares»). "
      "En las tablas de gasto `SECUENCIA_ENCUESTA`, `SECUENCIA_P` y `ORDEN` se comportan como **contadores de registro** (la columna «Llave mínima única» muestra cuáles bastan para identificar una fila), no identifican al hogar. "
      "El DDI no documenta qué identifica `ORDEN` en las tablas de gasto: **no asumir que es la persona**. "
      "Llave única de un registro de gasto: `DIRECTORIO + SECUENCIA_ENCUESTA + SECUENCIA_P`.\n")
    A("**Aviso sobre CLAUDE.md.** La regla de unión «`DIRECTORIO + SECUENCIA_P + HOGAR (+ORDEN)`» es de GEIH (ENPH no tiene columna `HOGAR`). "
      "Aplicada a ENPH, `DIRECTORIO + SECUENCIA_P` solo enlaza la fracción de filas de la columna «% filas que enlazan» con `viviendas_hogares`; el resto se perdería en silencio. "
      "Para ENPH se debe unir por `DIRECTORIO`, con conciencia de que es uno-a-muchos.\n")
    A(tabla(["Archivo", "Unidad declarada", "Filas", "Hogares (`DIRECTORIO`)", "Filas por hogar", "DIRECTORIO ⊂ hogares", "Llave mínima única", "% filas que enlazan (DIR+SEC_P)", "Verificación", "Variable DDI que define la fila"], [
        [f"`{r['ruta']}`", r["unidad_texto"], fn(r.get("filas")), fn(r.get("hogares")), fn(r.get("filas_por_hogar"), 2),
         "sí" if r.get("dir_en_hogares") else "NO", r.get("llave_minima_unica", "—"), fn(r.get("pct_filas_enlazan_dir_sp"), 2) + " %", r.get("claim_ok", "—"),
         f"`{r['ddi_variable']}` = «{r['ddi_etiqueta']}»" if r.get("ddi_variable") else "—"] for r in enph]))
    A("\n**Factor de expansión ENPH.** " + (
        "Los 16 archivos traen `FEX_C`." if all(r.get("columnas_fex") == ["FEX_C"] for r in enph if r["existe"])
        else "Columnas FEX por archivo: " + "; ".join(f"{r['ruta']}: {r.get('columnas_fex')}" for r in enph if r["existe"]))
      + " CLAUDE.md exige documentar cuál factor se usa en cada análisis.\n")
    A(texto_fex_enph())
    A(tabla(["Archivo", "Zip origen", "Filas", "Cols", "SHA-256", "Encoding detectado", "Carga", "Sep"], [
        [f"`{r['ruta']}`", f"`{r.get('zip')}`", fn(r.get("filas")), r.get("columnas", "—"), f"`{r['sha256']}`" if r["existe"] else "—",
         r.get("encoding", "—"), f"`{nd.LECTURA[r['lectura']]['encoding']}`", "tab" if r.get("sep") == "\t" else "`;`"] for r in enph]))
    A("\n")

    A("## 5. Procedencia de `urbano/gastos_diarios_hogar.txt`\n")
    A("- **Declarado por Sara Cárdenas (2026-09-20):** es una descarga fresca del DANE del 20 sep 2026 y reemplaza la copia anterior, "
      "sobre la que existía una sospecha de truncamiento. Esa declaración no se puede verificar desde los archivos; lo que sí se midió:\n")
    A(tabla(["Evidencia", "Valor"], [
        ["Zip origen", f"`{prov['zip']}` ({fn(prov['zip_bytes'])} B)"],
        ["SHA-256 del zip", f"`{prov['zip_sha256']}`"],
        ["Fecha de modificación del zip en `_descargas/`", prov["zip_mtime"]],
        ["Fecha interna del `.txt` dentro del zip", prov["txt_miembro_fecha"]],
        ["SHA-256 del `.txt`", f"`{prov['txt_sha256']}`"],
        ["**Filas (cifra de referencia)**", f"**{fn(prov['txt_filas'])}** filas × {prov['txt_columnas']} columnas"],
        ["Prueba CRC del zip (`testzip`)", "OK" if prov["crc_zip_ok"] else "FALLA"],
        ["Filas × columnas del `.sav` del mismo zip", f"{fn(prov['sav_filas'])} × {prov['sav_columnas']} (" + ("coincide con el `.txt`" if prov["txt_igual_sav"] else "NO coincide") + ")"],
        ["Filas con nº de campos distinto al encabezado", fn(prov["irregulares"])],
        ["El archivo termina en salto de línea", "sí" if prov["termina_en_salto"] else "NO"]]))
    A("\n**Alcance.** La cifra es de *autoconsistencia* (CRC del zip, `.txt` = `.sav`, sin filas cortadas, cierre limpio). "
      f"No existe una cifra oficial contra la cual cotejarla: el DDI declara `caseQnty` = {', '.join(ddie['caseQnty_valores'])} (marcador vacío). "
      "Un truncamiento que afecte igual al `.txt` y al `.sav` de un mismo zip no se detectaría con estas pruebas. "
      "No se conserva la copia anterior, así que no se puede comparar contra ella. "
      "La fecha interna del `.txt` es la de creación por el DANE, no la de descarga; la fecha de descarga solo se apoya en la de modificación del zip.\n")

    A("## 6. `P7510` y `P7513` en ENPH\n")
    per = "ENPH_2017/personas/caracteristicas_generales_personas.csv"
    A(f"Viven en **`{per}`** (Caracteristicas generales personas, cuadernillo 1). **No** están en `hogares/viviendas_hogares.csv` "
      f"(P7510: {p75['P7510']['en_hogares']} columnas; P7513: {p75['P7513']['en_hogares']}) ni en ningún otro archivo ENPH"
      + (f" (salvo: {', '.join(p75['otros_archivos'])})" if p75["otros_archivos"] else "") + ".\n")
    A(f"No existen columnas llamadas exactamente `P7510` o `P7513`: son familias con sufijos. "
      f"`P7510*`: {p75['P7510']['en_personas']} columnas; `P7513*`: {p75['P7513']['en_personas']}. Etiqueta DDI de ejemplo: "
      f"`{next(iter(p75['P7510']['ejemplo']))}` = «{next(iter(p75['P7510']['ejemplo'].values()))}»; "
      f"`{next(iter(p75['P7513']['ejemplo']))}` = «{next(iter(p75['P7513']['ejemplo'].values()))}». "
      "Los sufijos `S#` son ítems (a, b, c…) y `S#A1` su valor. Unidad: persona, con referencia de 12 meses.\n")

    A("## 7. Control de cambios del formulario GEIH (comparabilidad semántica)\n")
    rg = ctrl["rango_instructivo"]
    A(f"Fuente: `GEIH_2025/_metadatos/CONTROL DE CAMBIOS FORMULARIO GEIH.xlsx`. Su instructivo dice cubrir «desde el año {rg[0]} hasta el {rg[1]}».\n")
    A(tabla(["Año", "Trimestre", "Etapas", "Cambios", "Por tipo"], [[b["anio"], b["trimestre"], b["etapas"], b["n"],
                                                                     ", ".join(f"{k}: {v}" for k, v in b["por_tipo"].items())] for b in ctrl["bloques"]]))
    A("\nTipos: IC/EC = ingresa/elimina capítulo; IP/EP = pregunta; IA/EA = alternativa de respuesta; O = otro.\n")
    fe = ctrl["formulario_etapas"]
    A("**Conclusión: PENDIENTE — no hay evidencia sobre 2025.**\n")
    A(f"- Entradas de 2025 en el control de cambios: **{'sí' if ctrl['hay_entradas_2025'] else 'ninguna'}**. El último bloque es {ctrl['bloques'][-1]['anio']} (etapas {ctrl['bloques'][-1]['etapas']}).")
    A(f"- El `FORMULARIO_GEIH.pdf` de `_metadatos/` es de las etapas {fe[0]}–{fe[1]} ({fe[2]}), es decir, **2024**, no 2025." if fe else "- No se pudo leer la portada del `FORMULARIO_GEIH.pdf` (falta `pdftotext`).")
    A(f"- Solo el Manual de Recolección es de {ctrl['manual_anio']}. Busqué en su texto («novedad», «cambios al formulario», «modificación», «versión», «respecto a 2024», «a partir de») "
      "y no trae un listado de cambios frente a 2024." if ctrl["manual_anio"] else "- No se pudo determinar el año del Manual de Recolección (falta `pdftotext`).")
    A("- Por tanto **no se puede afirmar que el formulario no cambió durante 2025**, ni que sí. Riesgo: cambios de redacción, alternativas de respuesta "
      "o definiciones (que no alteran el nombre de la columna) podrían afectar el apilamiento de los 12 meses, sobre todo en `ocupados`, `fuerza_trabajo` y `otros_ingresos`.")
    A("- Para cerrarlo hace falta el control de cambios o el formulario de las etapas 2501–2512 (o confirmación del DANE). "
      "Mientras tanto, tratar cualquier variable de opinión/definición como no verificada entre meses.\n")

    A("## 8. Diciembre 2025 tiene menos filas\n")
    d_p, d_h = dic["por_mes"]["diciembre"]["personas"], dm["hogares"]
    A(f"Diciembre: {fn(d_p)} personas (mediana de los otros 11 meses: {fn(mo['personas'])}, razón {fn(d_p / mo['personas'], 3)}) y "
      f"{fn(d_h)} hogares (mediana {fn(mo['hogares'])}, razón {fn(d_h / mo['hogares'], 3)}). La diferencia es de {fn(mo['personas'] - d_p)} personas y {fn(mo['hogares'] - d_h)} hogares.\n")
    rk = dic["ranking_modulos"]
    A(tabla(["Módulo", "Diciembre = mes con menos filas", "Posición desde abajo", "Meses con menos filas que diciembre"], [
        [m, "sí" if rk[m]["dic_es_minimo"] else "no", rk[m]["posicion_desde_abajo"], ", ".join(rk[m]["menores_que_dic"]) or "—"] for m in ORDEN_MODULOS]))
    A("\nEs decir, **«proporcional en todos los módulos» no se sostiene del todo**: diciembre es el mínimo solo en los módulos donde la tabla dice «sí».\n")
    A("**Dónde está la diferencia**\n")
    cp, ch = dic["clase_personas"], dic["clase_hogares"]
    A(tabla(["CLASE (DANE)", "Personas dic", "Media otros", "Mín. otros", "Hogares dic", "Media otros", "Mín. otros"], [
        [c, fn(cp[c]["dic"]), fn(cp[c]["media_otros"]), fn(cp[c]["min_otros"]), fn(ch[c]["dic"]), fn(ch[c]["media_otros"]), fn(ch[c]["min_otros"])] for c in cp]))
    A(f"\n- Personas por hogar en diciembre: {fn(dm['pers_por_hogar'], 3)} (mediana otros: {fn(mo['pers_por_hogar'], 3)}); "
      f"{'es el valor más bajo del año' if dic['dic_minimo_pers_por_hogar'] else 'no es el más bajo del año'}. "
      f"El mes con menos hogares es **{dic['hogares_min_mes']}**, no diciembre.")
    A(f"- Departamentos por debajo de su propio mínimo de los otros meses: {dic['dptos_bajo_su_minimo_personas']['n']} de {dic['dptos_bajo_su_minimo_personas']['de']} (personas); "
      f"{dic['dptos_bajo_su_minimo_hogares']['n']} de {dic['dptos_bajo_su_minimo_hogares']['de']} (hogares). Diferencia difusa, sin un solo departamento que la explique.")
    A(f"- Semanas de recolección: diciembre tiene {dm['n_semanas']} (`PERIODO` {dm['semanas'][0]}–{dm['semanas'][-1]}). Filas de la última semana: {fn(dm['filas_ultima_semana'])} "
      f"(otros meses de 4 semanas: {fn(min(v['filas_ultima_semana'] for k, v in dic['por_mes'].items() if k != 'diciembre' and v['n_semanas'] == 4))}–"
      f"{fn(max(v['filas_ultima_semana'] for k, v in dic['por_mes'].items() if k != 'diciembre' and v['n_semanas'] == 4))}). No falta una semana completa.")
    A(f"- Suma de `FEX_C18` (personas), millones: diciembre {fn(dm['fex_personas_M'], 3)}; crece cada mes: {'sí' if dic['fex_creciente'] else 'no'}. "
      "Los factores compensan el menor n, así que los totales expandidos no caen; sí aumenta la varianza.")
    if "diseno_hogares_mes" in dic:
        dh = dic["diseno_hogares_mes"]
        hs = [v["hogares"] for v in dic["por_mes"].values()]
        A(f"- Diseño (Metodología general §2.2.11): «en promedio se espera encuestar mensualmente {fn(dh['capitales'])} hogares en las 32 ciudades capitales … y {fn(dh['resto'])} en el resto» "
          f"= {fn(dh['total'])} (la frase está cortada en el propio PDF). Observado: {fn(min(hs))}–{fn(max(hs))} hogares por mes, **todos los meses** por debajo de esa media.")
    A("\n**Conclusión: PENDIENTE — no se puede calificar ni de «esperado por diseño» ni de anomalía.**\n")
    A("- Búsqueda manual con `pdftotext` (no automatizada en este script): en la Metodología general busqué diciembre, festivos, vacaciones, temporada, rotación y muestra mensual/trimestral; "
      "en la Ficha metodológica y el Manual de Recolección 2025, diciembre, festivos, vacaciones y temporada. No encontré ninguna referencia a un tamaño de muestra distinto para diciembre "
      "(las menciones a diciembre son históricas o de encabezado). El texto disponible da una media mensual, sin decir si varía por mes; y la frase clave está cortada en el PDF, así que la ausencia de una regla mensual no está demostrada.")
    A(f"- Lo observado es pequeño ({fn((d_p / mo['personas'] - 1) * 100, 1)} % en personas, {fn((d_h / mo['hogares'] - 1) * 100, 1)} % en hogares), más marcado en cabeceras (CLASE 1) y con menor tamaño de hogar; no falta ninguna semana ni un departamento. "
      "Podría ser variación de cobertura o de respuesta en época de fin de año, pero **eso es una hipótesis, no algo que los datos o la documentación confirmen**.")
    A("- Para cerrarlo: la tasa de respuesta/cobertura de diciembre 2025 en el boletín técnico del DANE, o una consulta al DANE. "
      "Impacto práctico: con `FEX_C18 / 12` los totales no se distorsionan; se recomienda una prueba de sensibilidad excluyendo diciembre antes de fijar priors definitivos.\n")

    A("## 9. Metadatos y etiquetas (integridad)\n")
    A("`_etiquetas/` contiene los `.SAV` de **enero** (única fuente de etiquetas de valor para GEIH; no se verificó que las etiquetas sean iguales en los otros 11 meses).\n")
    A(tabla(["Ruta", "Bytes", "SHA-256"], [[f"`{m['ruta']}`", fn(m["bytes"]), f"`{m['sha256']}`"] for m in meta]))
    A("")
    A(construir_seccion_bogota(bog))
    A(construir_seccion_rotacion(bog))
    return "\n".join(L) + "\n"


def main() -> int:
    log = cargar_log()
    labs, ddie = ddi_enph()
    geih = procesar_geih(log)
    enph = procesar_enph(log, labs)
    prov = procedencia_gdh(enph)
    p75 = p75xx(enph, labs)
    ctrl = control_de_cambios()
    dic = analisis_diciembre(geih)
    meta = hashes_metadatos()
    codigos = bogota_codigos()
    cod_area, cod_dpto = codigos["diccionario"]["AREA"]["codigos"][0], codigos["diccionario"]["DPTO"]["codigos"][0]
    estratos = [c.split()[0] for c in codigos["ddi_estrato"] if not re.search(r"pirata|no sabe|no informa", c, re.I)]
    bog = {"codigos": codigos, "cod_area": cod_area, "cod_dpto": cod_dpto, "estratos": estratos,
           "geih": bogota_geih(cod_area, cod_dpto, estratos), "enph": bogota_enph(estratos), "nc2r": nc2r(enph)}
    bog["agrupado"] = enph_cruce_agrupado(estratos)
    bog["cuadernillos_pago"] = cuadernillos_pago()
    bog["forma_pago"] = forma_pago_bogota(bog["nc2r"]["ddi_categorias"])
    bog["rotacion"] = rotacion_geih(cod_area)
    fex = [v["fex_personas_M"] for v in dic["por_mes"].values()]
    bog["fex_personas_M"] = (min(fex), max(fex))
    md = construir_md(geih, enph, prov, p75, ctrl, dic, ddi_geih(), ddie, meta, bog)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")
    for r in geih:
        r.pop("header", None)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"geih": geih, "enph": enph, "procedencia_gastos_diarios_hogar": prov, "p7510_p7513": p75,
                                    "control_de_cambios": ctrl, "diciembre": dic, "bogota": bog, "metadatos": meta},
                                   ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"OK: {OUT_MD.relative_to(ROOT)} y {OUT_JSON.relative_to(ROOT)}")
    print("REVISAR ENPH:", [r["ruta"] for r in enph if r.get("claim_ok") == "REVISAR"] or "ninguno")
    print("FALTAN:", [r["ruta"] for r in geih + enph if not r["existe"]] or "ninguno")
    return 0


if __name__ == "__main__":
    sys.exit(main())
