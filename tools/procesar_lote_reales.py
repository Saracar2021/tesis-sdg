# -*- coding: utf-8 -*-
"""Procesa TODOS los extractos de data/reales_crudos/ -> data/reales_anon/VNN.csv (WP4, Opción A).

Qué hace
  1. Asigna cada PDF a un grupo (seudónimo) según data/reales_crudos/_lote.json (local, gitignored: los
     patrones de nombre de archivo contienen fragmentos de número de cuenta, por eso NO viven en el código).
  2. Extrae los movimientos con tools/anonimizar_extractos.py (capa de texto) o, para extractos cuya
     tabla es una imagen escaneada, con OCR (tesseract) — tipo "ocr_davivienda".
  3. Concilia cada extracto contra sus totales impresos (créditos / débitos) cuando el banco los imprime.
     Un extracto que no cuadra se reporta; no se oculta.
  4. Anonimiza (R-A personas -> PERSONA, R-B dígitos >= 6 -> #, R-C comercios intactos) y aplica además la
     lista local de nombres revisados a mano (data/reales_crudos/_nombres_enmascarar.txt, uno por línea).
  5. Deduplica SOLO los grupos marcados "dedup": true (tarjetas de crédito, cuyos extractos se solapan).
     Las cuentas de ahorro NO se deduplican: dos compras idénticas el mismo día son dos transacciones
     (la conciliación contra totales lo comprueba).

Salidas (todas en data/reales_anon/, gitignored): VNN.csv, _sospechas_VNN.md, _conciliacion.md.
Uso:  python tools/procesar_lote_reales.py            (desde la raíz del repo)
Requiere: pdfplumber, pdftotext/pdftoppm (poppler) y tesseract (solo para "ocr_davivienda").
Determinista: mismo conjunto de PDFs -> mismos CSV.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "data" / "reales_crudos"
SALIDA = RAIZ / "data" / "reales_anon"

_spec = importlib.util.spec_from_file_location("anon", RAIZ / "tools" / "anonimizar_extractos.py")
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

# ---------------------------------------------------------------------------------------------
# OCR Davivienda: "DD MM | $ 1,234.00+ | Doc | Clase de movimiento | Oficina". Desde la 2.a página
# el extracto es una imagen sin capa de texto (y la capa de la 1.a desordena la primera fila), así
# que se hace OCR de todas las páginas y se concilia contra "Más Créditos / Menos Débitos".
# ---------------------------------------------------------------------------------------------
RE_FILA_OCR = re.compile(
    r"^\s*\|?\s*(?P<d>\S{2,3})(?P<ruido>[^$]{0,60}?)\$\s*(?P<v>\d{1,3}(?:\s?,\s?\d{3})*\.\d{2})\s*(?P<s>[+\-])"
    r"\s*\|?\s*(?P<doc>\d{4})?\s*[|_=]?\s*(?P<resto>.*)$")
RE_TOT_DAV = {"cred": re.compile(r"M[áa]s\s+Cr[ée]ditos\s+\$\s*([\d,]+\.\d{2})"),
              "deb": re.compile(r"Menos\s+D[ée]bitos\s+\$\s*([\d,]+\.\d{2})")}
# Correcciones de ruido de OCR (no cambian el contenido: devuelven el texto que imprimió el banco).
FIX_OCR = [(r"^[^A-Za-z0-9]+", ""), (r"\bCompra\s*l?(?=[A-Z0-9*])", "Compra "), (r"\bPago\s*Credito", "Pago Credito"),
           (r"FRANQUICIA\s*MASTER\s+CAR[OD0]\b", "FRANQUICIA MASTER CARD"), (r"Automatic[eo0]\.", "Automatico."),
           (r"\bGravamen\s*a\s*los", "Gravamen a los"), (r"\bLiave\b", "Llave"), (r"CAC[‘'`]", "CAC*"),
           (r"\bPHARMAISIS\b", "PHARMA ISIS"), (r"\bS\.A\.COMPA", "S.A. COMPA"), (r"[|‘’©§~—_=]", " "),
           (r"\s+", " "), (r"(?:\s+(?:S[Il1]|\d{1,2}))+\s*$", ""), (r"\s+0000\s*$", "")]
NO_CONT = re.compile(r"NIT|Davivienda S\.A|P[áa]gina|Fecha|Valor|CUENTA DE AHORROS|Saldo|www\.", re.I)


def _num2(t):
    t = t[:2].translate(str.maketrans("oOlI", "0011"))
    return int(t) if t.isdigit() else None


def _limpia_ocr(desc: str) -> str:
    for a, b in FIX_OCR:
        desc = re.sub(a, b, desc)
    return desc.strip()


def _ocr_paginas(pdf: Path) -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", "300", "-gray", str(pdf), f"{td}/p"], check=True)
        out = []
        for img in sorted(Path(td).glob("p-*.pgm")):
            r = subprocess.run(["tesseract", str(img), "-", "--psm", "6", "-l", "eng", "-c", "preserve_interword_spaces=1"],
                               capture_output=True, text=True, check=True)
            out.append(r.stdout)
    return out


def extraer_ocr_davivienda(pdf: Path):
    """Devuelve (movimientos, conciliación). El año y mes salen del nombre extracto_AAAAMM."""
    mm = re.search(r"(\d{4})(\d{2})", pdf.stem)
    anio, mes = int(mm.group(1)), int(mm.group(2))
    capa = subprocess.run(["pdftotext", "-layout", "-l", "1", str(pdf), "-"], capture_output=True, text=True).stdout
    tot = {k: float(r.search(capa).group(1).replace(",", "")) for k, r in RE_TOT_DAV.items()}
    movs, prev_dia, n_imput = [], 0, 0
    for pag, texto in enumerate(_ocr_paginas(pdf), 1):
        for linea in texto.splitlines():
            m = RE_FILA_OCR.match(linea)
            lin = linea.strip()
            if m:
                d = _num2(m["d"])
                if not (d and 1 <= d <= 31) or (prev_dia and d < prev_dia):
                    d, n_imput = (prev_dia or 1), n_imput + 1   # día ilegible: el del movimiento anterior (filas ordenadas)
                prev_dia = d
                movs.append({"fecha": f"{anio}-{mes:02d}-{d:02d}", "desc_cruda": _limpia_ocr(m["resto"]),
                             "monto_c": float(m["v"].replace(",", "").replace(" ", "")), "negativo": m["s"] == "-", "pag": pag})
            elif (movs and movs[-1]["pag"] == pag and 3 <= len(lin) <= 30 and "$" not in lin and not NO_CONT.search(lin)
                  and re.fullmatch(r"[A-ZÁÉÍÓÚÑ0-9 .]+", lin) and not re.fullmatch(r"S[Il1]|[\d ]+", lin)):
                movs[-1]["desc_cruda"] = _limpia_ocr(movs[-1]["desc_cruda"] + " " + lin)  # descripción partida en dos líneas
    cred = round(sum(x["monto_c"] for x in movs if not x["negativo"]), 2)
    deb = round(sum(x["monto_c"] for x in movs if x["negativo"]), 2)
    for x in movs:
        x["monto"] = int(x.pop("monto_c"))
    conc = {"cred": cred, "cred_ext": tot["cred"], "deb": deb, "deb_ext": tot["deb"],
            "cuadra": abs(cred - tot["cred"]) < 0.01 and abs(deb - tot["deb"]) < 0.01, "fechas_imputadas": n_imput}
    return movs, conc


# ---------------------------------------------------------------------------------------------
# Capa de texto + totales impresos
# ---------------------------------------------------------------------------------------------
def totales_impresos(texto: str):
    a = re.search(r"TOTAL ABONOS \$ ([\d,]+\.\d\d)", texto)
    c = re.search(r"TOTAL CARGOS \$ ([\d,]+\.\d\d)", texto)
    if a and c:  # Bancolombia (anglo)
        return float(a.group(1).replace(",", "")), float(c.group(1).replace(",", ""))
    lineas = texto.splitlines()
    for i, l in enumerate(lineas):  # Scotiabank / Davibank: fila de resumen bajo el encabezado
        if "DEPOSITOS Y OTROS CREDITOS" in l:
            nums = re.findall(r"[\d.]+,\d\d", " ".join(lineas[i + 1:i + 4]))
            if len(nums) >= 4:
                return (float(nums[1].replace(".", "").replace(",", ".")), float(nums[2].replace(".", "").replace(",", ".")))
    return None, None


def extraer_texto(pdf: Path, g: dict):
    texto = "\n".join(A.leer_paginas(pdf, g["extractor"]))
    movs = A.parsear_extracto(texto.splitlines(), "2026-01", g.get("columna"), g["formato_fecha"], filtrar_mes=False)["movimientos"]
    conc = {"cuadra": None}
    tc, td = totales_impresos(texto)
    if tc is not None:
        cred = sum(m["monto"] for m in movs if not m["negativo"])
        deb = sum(m["monto"] for m in movs if m["negativo"])
        tol = len(movs) + 1  # los montos se truncan al peso: hasta 1 peso por fila
        conc = {"cred": cred, "cred_ext": tc, "deb": deb, "deb_ext": td, "cuadra": abs(cred - tc) <= tol and abs(deb - td) <= tol}
    return movs, conc


# ---------------------------------------------------------------------------------------------
def main():
    cfg = json.loads((CRUDOS / "_lote.json").read_text(encoding="utf-8"))
    ruta_nombres = CRUDOS / "_nombres_enmascarar.txt"
    nombres = []
    if ruta_nombres.exists():
        nombres = sorted({l.strip() for l in ruta_nombres.read_text(encoding="utf-8").splitlines()
                          if l.strip() and not l.startswith("#")}, key=len, reverse=True)
    SALIDA.mkdir(parents=True, exist_ok=True)
    contad = {"titular": 0, "persona_R_A": 0, "digitos_R_B": 0}
    por_seudo, conc_filas, sin_grupo = {}, [], []

    for pdf in sorted(CRUDOS.glob("*.pdf")):
        g = next((x for x in cfg["grupos"] if re.search(x["patron"], pdf.name)), None)
        if g is None:
            sin_grupo.append(pdf.name)
            continue
        movs, conc = extraer_ocr_davivienda(pdf) if g["tipo"] == "ocr_davivienda" else extraer_texto(pdf, g)
        conc_filas.append((g["seudonimo"], pdf.name, len(movs), conc))
        for m in movs:
            desc = A.depurar(m["desc_cruda"], nombres, contad)
            if not desc:
                continue
            por_seudo.setdefault(g["seudonimo"], {"g": g, "filas": []})["filas"].append(
                {"fecha": m["fecha"], "descripcion": desc, "monto": m["monto"], "signo": A.signo_de(m, g["regla_signo"]),
                 "cuenta_tipo": g["cuenta_tipo"]})

    total = 0
    for seudo in sorted(por_seudo):
        g, movs = por_seudo[seudo]["g"], por_seudo[seudo]["filas"]
        if g.get("dedup"):
            vistos, unicos = set(), []
            for m in movs:
                k = (m["fecha"], m["monto"], m["descripcion"])
                if k not in vistos:
                    vistos.add(k)
                    unicos.append(m)
            movs_out = unicos
        else:
            movs_out = movs
        movs_out = sorted(movs_out, key=lambda m: m["fecha"])  # sort estable: conserva el orden del extracto
        cont, filas = {}, []
        for m in movs_out:
            mes = m["fecha"][:7]
            cont[mes] = cont.get(mes, 0) + 1
            filas.append({"tx_id": f"{seudo}-{mes[2:4]}{mes[5:7]}-{cont[mes]:03d}", "seudonimo": seudo, "mes_referencia": mes,
                          "fecha": m["fecha"], "descripcion": m["descripcion"], "monto": m["monto"], "signo": m["signo"],
                          "cuenta_tipo": m["cuenta_tipo"], "proposito_declarado": ""})
        with open(SALIDA / f"{seudo}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=A.COLUMNAS)
            w.writeheader()
            w.writerows(filas)
        marcas = []
        for f in filas:
            mot = []
            if "PERSONA" in f["descripcion"]:
                mot.append("PERSONA enmascarada")
            if re.search(r"\d{4,}", f["descripcion"]):
                mot.append("dígitos")
            if A.es_posible_nombre(f["descripcion"]):
                mot.append("posible nombre de persona")
            if f["monto"] == 0:
                mot.append("monto 0 (< $1)")
            if mot:
                marcas.append((f["tx_id"], f["descripcion"], ", ".join(mot)))
        with open(SALIDA / f"_sospechas_{seudo}.md", "w", encoding="utf-8") as fh:
            fh.write(f"# Sospechas {seudo} ({g['banco']}) — revisión manual\n\nFilas: {len(filas)}. Marcadas: {len(marcas)}.\n\n"
                     "| tx_id | descripcion | motivo |\n|---|---|---|\n")
            fh.writelines(f"| {t} | {d} | {mo} |\n" for t, d, mo in marcas)
        print(f"{seudo} ({g['banco']:28}): {len(movs):4d} extraídas -> {len(filas):4d} filas | dedup={bool(g.get('dedup'))}")
        total += len(filas)

    with open(SALIDA / "_conciliacion.md", "w", encoding="utf-8") as fh:
        fh.write("# Conciliación contra totales impresos del extracto\n\n"
                 "| seudónimo | archivo | filas | créditos (extraídos / impresos) | débitos (extraídos / impresos) | cuadra |\n"
                 "|---|---|---|---|---|---|\n")
        for seudo, nom, n, c in conc_filas:
            if c["cuadra"] is None:
                fh.write(f"| {seudo} | {nom} | {n} | — | — | sin totales impresos |\n")
            else:
                fh.write(f"| {seudo} | {nom} | {n} | {c['cred']:,.2f} / {c['cred_ext']:,.2f} | {c['deb']:,.2f} / {c['deb_ext']:,.2f} | "
                         f"{'sí' if c['cuadra'] else '**NO**'} |\n")
    n_ok = sum(1 for *_, c in conc_filas if c["cuadra"])
    n_no = sum(1 for *_, c in conc_filas if c["cuadra"] is False)
    print(f"\nTOTAL filas: {total} | extractos conciliados: {n_ok} sí, {n_no} NO, {len(conc_filas) - n_ok - n_no} sin totales")
    print(f"Enmascarados: {contad}")
    for seudo, nom, n, c in conc_filas:
        if c["cuadra"] is False:
            print(f"  NO CUADRA: {seudo} {nom}")
    if sin_grupo:
        print("SIN GRUPO (no procesados):", *sin_grupo, sep="\n  ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
