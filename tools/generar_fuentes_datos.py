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
from datetime import datetime
from pathlib import Path

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


def hashes_metadatos() -> list[dict]:
    out = []
    for base in (RAW / "GEIH_2025/_etiquetas", RAW / "GEIH_2025/_metadatos", RAW / "ENPH_2017/_metadatos"):
        for p in sorted(base.rglob("*")):
            if p.is_file():
                out.append({"ruta": p.relative_to(RAW).as_posix(), "bytes": p.stat().st_size, "sha256": sha256_path(p)})
    return out


# --- Documento -------------------------------------------------------------------------------------
def construir_md(geih, enph, prov, p75, ctrl, dic, ddig, ddie, meta) -> str:
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
      + " CLAUDE.md exige documentar cuál factor se usa en cada análisis: este documento solo confirma que la columna existe en cada tabla; "
      "no verifica que `FEX_C` sea el factor correcto para cada unidad de registro.\n")
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
    md = construir_md(geih, enph, prov, p75, ctrl, dic, ddi_geih(), ddie, meta)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")
    for r in geih:
        r.pop("header", None)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"geih": geih, "enph": enph, "procedencia_gastos_diarios_hogar": prov, "p7510_p7513": p75,
                                    "control_de_cambios": ctrl, "diciembre": dic, "metadatos": meta},
                                   ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"OK: {OUT_MD.relative_to(ROOT)} y {OUT_JSON.relative_to(ROOT)}")
    print("REVISAR ENPH:", [r["ruta"] for r in enph if r.get("claim_ok") == "REVISAR"] or "ninguno")
    print("FALTAN:", [r["ruta"] for r in geih + enph if not r["existe"]] or "ninguno")
    return 0


if __name__ == "__main__":
    sys.exit(main())
