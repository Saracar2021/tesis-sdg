#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anonimización local de extractos bancarios reales (WP4, protocolo 02 v1.1).

EJECUCIÓN MANUAL, en el computador de la investigadora, desde la raíz del repo.
Ningún asistente lo ejecuta sobre data/reales_crudos/.

Lee     : PDF de extractos dentro de data/reales_crudos/ (rutas que pasas tú).
Escribe : SOLO dentro de data/reales_anon/:
            <seudonimo>.csv            esquema del protocolo §7 (tres campos + metadatos)
            _sospechas_<seudonimo>.md  para la revisión manual (protocolo §5)
            _trazabilidad.md           SHA-256 de original y de salida, procedencia (sin datos)

Ejemplo:
  python tools/anonimizar_extractos.py --seudonimo V07 --banco "Davibank" --tipo-cuenta banco \
      --extracto 2025-12=data/reales_crudos/originales/V07/dic.pdf \
      --extracto 2026-04=data/reales_crudos/originales/V07/abr.pdf \
      --extracto 2026-08=data/reales_crudos/originales/V07/ago.pdf \
      --titular data/reales_crudos/titulares/V07.txt \
      --regla-signo minus --columna-monto primera

Primer uso con un banco nuevo: añade --diagnostico. Imprime en CONSOLA las primeras líneas de
texto del primer PDF y los conteos, para que elijas --regla-signo y --columna-monto. No escribe nada.

Limitaciones (de frente):
  * No ha sido probado contra PDFs reales. Antes de usarlo en serio, revisa la salida con
    --diagnostico y con la revisión manual del protocolo §5.
  * Solo extrae texto. Un extracto escaneado o una captura no tiene texto: el script se detiene
    y ese caso va a transcripción manual (protocolo §4.3).
  * Si una regla no encaja con el layout, el script se detiene con error. No adivina.
  * No detecta todos los nombres propios. La revisión manual es obligatoria.
  * Este script escribe directamente en data/reales_anon/ (instrucción de la investigadora).
    El protocolo v1.1 §4.1 pedía un borrador en data/reales_crudos/extraido/ antes; aquí la
    revisión se hace sobre el CSV ya en data/reales_anon/.
"""

import argparse
import csv
import hashlib
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REALES_CRUDOS = (RAIZ / "data" / "reales_crudos").resolve()
REALES_ANON = RAIZ / "data" / "reales_anon"

COLUMNAS = [
    "tx_id", "seudonimo", "mes_referencia", "fecha", "descripcion",
    "monto", "signo", "cuenta_tipo", "proposito_declarado",
]
CUENTAS = ("banco", "billetera", "tarjeta_credito")

# R-C: comercios, medios y TÉRMINOS DE TRANSACCIÓN que NO se tratan como nombre de persona.
# Si todos los tokens tras un prefijo ("PAGO DE X") están aquí, no se enmascaran. Ampliar con
# cuidado: incluir una palabra que sí sea nombre propio dejaría de protegerla. Ninguno de estos
# términos financieros es un nombre, así que agregarlos no reduce la protección, solo evita
# destruir descripciones (p. ej. "PAGO DE INTERESES" -> "PAGO DE PERSONA", bug de v1.0).
NO_PERSONA = {
    # comercios y medios de pago
    "PSE", "NEQUI", "DAVIPLATA", "BANCOLOMBIA", "DAVIVIENDA", "BBVA", "BANCO", "CAJERO",
    "RAPPI", "EXITO", "FARMATODO", "NETFLIX", "UBER", "DIDI", "CABIFY", "MERCADOPAGO",
    "COLOMBIA", "BOGOTA", "CALLE", "CARRERA", "SCOTIABANK", "COLPATRIA", "SCOTIA",
    "VISA", "MASTERCARD", "TARJETA", "CREDITO", "DEBITO", "EFECTIVO",
    # términos de transacción / conceptos financieros (nunca nombres de persona)
    "INTERES", "INTERESES", "GENERADO", "RETENCION", "FUENTE", "GMF", "IVA", "IMPUESTO",
    "IMPUESTOS", "COMISION", "COMISIONES", "CUOTA", "CUOTAS", "MANEJO", "SALDO", "NOMINA",
    "SALARIO", "HONORARIOS", "ARRIENDO", "SERVICIO", "SERVICIOS", "FACTURA", "RECAUDO",
    "CONSIGNACION", "ABONO", "DEPOSITO", "TRANSFERENCIA", "TRANSF", "PAGO", "COMPRA",
    "RETIRO", "AVANCE", "CHEQUE", "SEGURO", "SEGUROS", "APORTE", "APORTES", "PENSION",
    "SALUD", "ADMINISTRACION", "MORA", "SOBREGIRO", "CESANTIAS", "PRIMA", "DIVIDENDOS",
    "RENDIMIENTO", "RENDIMIENTOS", "CAPITAL", "ABONOS", "PAGOS", "COMPRAS", "RETIROS",
    "NOMI", "PROVEEDORES", "TITULOS", "INVERSION", "CUENTA", "CUENTAS", "FONDOS",
}

# R-A: prefijos tras los que suele venir un nombre de persona. Solo se reemplaza lo que sigue
# al prefijo; el prefijo se conserva. Mayúsculas: los extractos suelen venir en mayúsculas.
RE_PERSONA = re.compile(
    r"\b(?P<pref>(?:TRANSFERENCIA (?:A|DE|DESDE|ENVIADA A|RECIBIDA DE)|TRANSF QR NEQUI|TRANSF (?:A|DE)|ENVIO (?:A|DE)|ENVIADO A|"
    r"RECIBIDO DE|PAGO (?:A|DE)|NEQUI (?:A|DE)|DAVIPLATA (?:A|DE)|CONSIGNACION (?:DE|NEQUI))\s+)"
    # v1.2: el nombre puede venir en minúsculas ("Sara Juliana") y truncado por el banco ("LUZ MELIDA O")
    r"(?P<nombre>[A-Za-zÁÉÍÓÚÑáéíóúñ]{2,}(?:\s[A-Za-zÁÉÍÓÚÑáéíóúñ]{1,}){0,3})(?![\w*])"
)
# R-D (v1.2): llaves Bre-B / correos. Un alias ("@sarac6353") o un correo identifica al titular de la
# llave; se reemplaza por el token neutro LLAVE (se sabe que es un pago por llave, no a quién).
RE_CORREO = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
RE_ALIAS = re.compile(r"(?<!\S)@[\w#.]{2,}")
# R-B: secuencias de 6 o más dígitos.
RE_DIGITOS = re.compile(r"\d{6,}")
# R-E (solo marca para revisión, no borra): patrones de dirección residencial.
RE_DIRECCION = re.compile(
    r"\b(?:CL|CALLE|CRA|CARRERA|KR|AV|AVENIDA|DG|DIAGONAL|TV|TRANSVERSAL|BLOQUE|APTO|TORRE)\b\.?\s*\d",
    re.IGNORECASE,
)
# Monto en formato colombiano (1.234,56) o anglo (1,234.56); signo '-' al inicio o al final;
# '$' opcional. Lookarounds por espacio/borde para no tomar fragmentos de números de referencia.
RE_MONTO = re.compile(
    r"(?<!\S)([-−+]?)\$?\s?(?:[-−])?((?:\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?)|(?:\d*[.,]\d{1,2})|\d+)([-−+]?)(?!\S)"
)
RE_FECHA_ISO = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})(?!\d)")
RE_FECHA_DMY = re.compile(r"^\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4}|\d{2})(?!\d)")
# Formato día-mes sin año (Davivienda "03 01" / Bancolombia "1/07"): día y mes separados por
# espacio o '/'. El año viene del mes del --extracto. Opt-in con --formato-fecha dm (evita
# falsos positivos en otros bancos).
RE_FECHA_DM = re.compile(r"^\s*(\d{1,2})[\s/]+(\d{1,2})(?=\s)")
# Tarjetas de crédito con una etiqueta antes de la fecha ISO: "Virtual 2026-04-20 COMERCIO ...".
RE_FECHA_CC = re.compile(r"^\s*\S+\s+(\d{4})-(\d{2})-(\d{2})(?=\s)")
RE_SIN_FECHA = re.compile(r"^\s*IMP/TRANS FINANC", re.IGNORECASE)
RE_INGRESO = re.compile(
    r"\b(ABONO|CONSIGNACION|RECIBIDO|RECIBIDA|DEPOSITO|INTERES|NOMINA|REEMBOLSO|REVERSION|DEVOLUCION)\b"
)
# Nombres de pila comunes. En tarjetas de crédito el beneficiario a veces es una persona natural
# (un pequeño comercio registrado a su nombre). Si la descripción empieza por uno de estos y parece
# un nombre, se MARCA para revisión manual (protocolo §5); NO se enmascara automáticamente, para no
# perder la señal de comercio. La investigadora decide en la revisión.
NOMBRES_PILA = {
    "JUAN", "LUIS", "CARLOS", "JOSE", "JORGE", "ANDRES", "DIEGO", "DAVID", "DANIEL", "SANTIAGO",
    "SEBASTIAN", "FELIPE", "CAMILO", "JULIAN", "FERNANDO", "RICARDO", "ALEJANDRO", "MIGUEL",
    "PEDRO", "PABLO", "JAVIER", "OSCAR", "MAURICIO", "GERMAN", "CESAR", "HERNAN", "GUSTAVO",
    "RAUL", "ALVARO", "WILSON", "EDWIN", "NELSON", "FABIAN", "HECTOR", "RODRIGO",
    "MARIA", "ANA", "LUISA", "LAURA", "PAULA", "CAROLINA", "DIANA", "CLAUDIA", "PATRICIA",
    "SANDRA", "MONICA", "ADRIANA", "NATALIA", "VALENTINA", "SARA", "ISABELLA", "DANIELA",
    "MANUELA", "JULIANA", "ANGELA", "BLANCA", "MARTHA", "GLORIA", "ROSA", "LUCIA", "YANIT",
    "NUBIA", "MARCELA", "LILIANA", "YESICA", "JESSICA", "KAREN", "TATIANA", "VIVIANA",
    "PAOLA", "EDGAR", "TITO", "YAIR", "SERGIO", "GERARDO", "MAGDALENA", "YANETH", "YUDY", "DEISY",
    "NAIRA", "JOVAN", "MARIO", "VICTOR", "RAFAEL", "MICHAEL", "CRISTIAN", "GEORS", "BERNABE", "LUZ",
}
# Prefijos que preceden TANTO a comercios como a personas ("PAGO QR SALSAMENTARIA" / "PAGO QR Gloria
# Yaneth"): se enmascara solo si la primera palabra es un nombre de pila y no es una marca conocida.
RE_PERSONA_COND = re.compile(
    r"\b(?P<pref>(?:PAGO QR|COMPRA EN)\s+)(?P<nombre>[A-Za-zÁÉÍÓÚÑáéíóúñ]{2,}(?:\s[A-Za-zÁÉÍÓÚÑáéíóúñ]{1,}){0,3})(?![\w*])"
)
MARCAS_CON_NOMBRE = {"JUAN VALDEZ"}


def es_posible_nombre(desc):
    """Marca (no enmascara) descripciones que parecen un nombre de persona: 2-4 palabras
    alfabéticas que empiezan por un nombre de pila común. Para la revisión manual de tarjetas."""
    toks = desc.split()
    if not (2 <= len(toks) <= 4):
        return False
    if toks[0].upper() not in NOMBRES_PILA:
        return False
    return all(re.fullmatch(r"[A-ZÁÉÍÓÚÑa-záéíóúñ]{2,}", t) for t in toks)


def leer_fecha(linea, anio_def=None, formato_fecha="auto"):
    """Devuelve (fecha, resto_de_linea) o (None, linea) si la línea no empieza con fecha.

    formato_fecha: 'auto' (ISO o DD/MM/AAAA) o 'dm' (DD MM sin año, con el año de anio_def).
    """
    if formato_fecha == "cc":
        m = RE_FECHA_CC.match(linea)
        if not m:
            return None, linea
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    elif formato_fecha == "dm":
        m = RE_FECHA_DM.match(linea)
        if not m or anio_def is None:
            return None, linea
        d, mo, y = int(m.group(1)), int(m.group(2)), anio_def
    else:
        m = RE_FECHA_ISO.match(linea)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            m = RE_FECHA_DMY.match(linea)
            if not m:
                return None, linea
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
    try:
        f = date(y, mo, d)
    except ValueError:
        return None, linea
    return f, linea[m.end():]


def valor_monto(token):
    """Normaliza un monto colombiano (1.234,56) o anglo (1,234.56), con signo '-' al inicio o al
    final. Devuelve (entero, negativo, tiene_centavos). Si hay ambos separadores, el decimal es el
    que aparece de último; si hay uno solo, 2 dígitos finales = decimales, si no = miles."""
    t = token.strip()
    neg = bool(re.match(r"^\$?\s*[-−]", t)) or t.endswith(("-", "−"))
    t = t.strip("-−+$ ").replace(" ", "").strip()
    if not t:
        return 0, neg, False
    if "." in t and "," in t:
        dec_sep = "." if t.rfind(".") > t.rfind(",") else ","
        mil_sep = "," if dec_sep == "." else "."
        entera, _, dec = t.rpartition(dec_sep)
        entera = entera.replace(mil_sep, "")
    elif "," in t:
        if re.fullmatch(r"\d*,\d{1,2}", t):
            entera, _, dec = t.rpartition(",")
        else:
            entera, dec = t.replace(",", ""), ""
    elif "." in t:
        if re.fullmatch(r"\d*\.\d{1,2}", t):
            entera, _, dec = t.rpartition(".")
        else:
            entera, dec = t.replace(".", ""), ""
    else:
        entera, dec = t, ""
    centavos = bool(dec.strip("0"))
    return int(entera or "0"), neg, centavos


RE_NO_FRAGMENTO = re.compile(r"\$|%|\d{4}-\d{2}-\d{2}|periodo|Gastos|Fecha|Valor|Total|P[áa]gina|Cupo|Saldo", re.IGNORECASE)


def _fragmento(lineas, j):
    """Línea vecina que es parte del nombre de un comercio partido (sin fecha, sin montos, corta)."""
    if not (0 <= j < len(lineas)):
        return ""
    t = lineas[j].strip()
    return t if 0 < len(t) <= 40 and not RE_NO_FRAGMENTO.search(t) else ""


def parsear_extracto(lineas, mes, columna_monto, formato_fecha="auto", filtrar_mes=True):
    """Función pura (sin archivos). Devuelve movimientos y contadores; no escribe nada.

    columna_monto: None | 'primera' | 'ultima'. Si una línea trae dos montos (valor y saldo)
    y no se eligió columna, la línea se cuenta como ambigua y el script se detiene.
    filtrar_mes: si True (CLI), descarta movimientos fuera del mes de `mes`; si False (batch),
    conserva todos con su fecha real (para deduplicar después extractos que se solapan).
    """
    res = {
        "movimientos": [], "lineas_con_fecha": 0, "fuera_de_mes": 0,
        "sin_monto": 0, "ambiguas": 0, "negativos": 0, "con_centavos": 0,
    }
    anio, mes_n = int(mes[:4]), int(mes[5:7])
    ultima = None
    for i, linea in enumerate(lineas):
        f, resto = leer_fecha(linea, anio, formato_fecha)
        if f is None and ultima is not None and RE_SIN_FECHA.match(linea):
            # Movimiento impreso sin fecha (GMF acumulado del mes): se le asigna la del anterior.
            f, resto = ultima, linea
        if f is None:
            continue
        ultima = f
        res["lineas_con_fecha"] += 1
        todos = list(RE_MONTO.finditer(resto))
        if not todos:
            res["sin_monto"] += 1
            continue
        # Se prefieren los montos con separador de miles/decimales (el valor real). Un entero
        # suelto (número de documento, código) solo cuenta si NO hay ningún monto con separador.
        con_sep = [m for m in todos if ("." in m.group(2) or "," in m.group(2))]
        cand = con_sep if con_sep else [todos[-1]]
        if len(cand) >= 2:
            if columna_monto is None:
                res["ambiguas"] += 1
                continue
            elegido = cand[0] if columna_monto == "primera" else cand[-1]
        else:
            elegido = cand[0]
        valor, neg, centavos = valor_monto(elegido.group(0))
        if neg:
            res["negativos"] += 1
        if centavos:
            res["con_centavos"] += 1
        if filtrar_mes and (f.year != anio or f.month != mes_n):
            res["fuera_de_mes"] += 1
            continue
        # Se quitan TODOS los montos de la línea (el saldo no debe quedar en la descripción).
        desc = resto
        for m in sorted(cand, key=lambda x: -x.start()):
            desc = desc[: m.start()] + " " + desc[m.end():]
        # Un número suelto al inicio de la descripción es el número de documento (columna Doc),
        # no parte del comercio: se quita.
        desc = re.sub(r"^\s*\d{1,6}\s+", " ", desc)
        if formato_fecha == "cc":
            # Tarjeta de crédito: quita las columnas de cuota e interés que siguen al comercio
            # ("... 1 de 1 0,0000% 0,00%", "N/A ..."), para dejar solo el nombre del comercio.
            desc = re.sub(r"\s+\d+\s+de\s+\d+\b.*$", "", desc)
            desc = re.sub(r"\s+N/?A\b.*$", "", desc)
            desc = re.sub(r"\s*[\d.,]+\s*%.*$", "", desc)
            if re.fullmatch(r"\s*(?:de\s+\d+)?\s*", desc):
                # Comercio largo partido en dos líneas: "SR WOK CONNECTA" / fecha + montos / "BOGOTA".
                desc = " ".join(x for x in (_fragmento(lineas, i - 1), _fragmento(lineas, i + 1)) if x)
        res["movimientos"].append(
            {"fecha": f.isoformat(), "desc_cruda": desc, "monto": valor, "negativo": neg}
        )
    return res


def depurar(desc, nombres_titular, contadores):
    """Aplica R-A, R-B y R-C. R-E solo se marca en el reporte. Devuelve la descripción depurada."""
    d = re.sub(r"\s+", " ", desc).strip()
    for nombre in nombres_titular:  # ya ordenados de más largo a más corto
        pat = re.compile(r"(?<!\w)" + re.escape(nombre) + r"(?!\w)", re.IGNORECASE)
        d, k = pat.subn("PERSONA", d)
        contadores["titular"] += k

    def _rep(m):
        toks = m.group("nombre").upper().split()
        # Si la primera palabra tras el prefijo es un concepto ("PAGO DE NOMI REPREMUNDO S A",
        # "PAGO DE INTERESES"), lo que sigue no es un nombre de persona: se conserva (R-C).
        if toks[0] in NO_PERSONA or all(t in NO_PERSONA for t in toks):
            return m.group(0)  # comercio: R-C
        contadores["persona_R_A"] += 1
        return m.group("pref") + "PERSONA"

    d = RE_PERSONA.sub(_rep, d)

    def _rep_cond(m):
        nom = m.group("nombre").upper()
        if nom.split()[0] not in NOMBRES_PILA or any(nom.startswith(x) for x in MARCAS_CON_NOMBRE):
            return m.group(0)
        contadores["persona_R_A"] += 1
        return m.group("pref") + "PERSONA"

    d = RE_PERSONA_COND.sub(_rep_cond, d)
    d = RE_CORREO.sub("LLAVE", d)
    d = RE_ALIAS.sub("LLAVE", d)
    d, k = RE_DIGITOS.subn("#", d)
    contadores["digitos_R_B"] += k
    return re.sub(r"\s+", " ", d).strip()


def signo_de(mov, regla):
    if regla == "minus":
        return "egreso" if mov["negativo"] else "ingreso"
    if regla == "tarjeta":
        # Extracto de tarjeta: compras en positivo; pagos, reversiones y anulaciones en negativo ("$-").
        return "ingreso" if mov["negativo"] else "egreso"
    # regla 'palabras': ingreso solo si la descripción trae una palabra de ingreso
    return "ingreso" if RE_INGRESO.search(mov["desc_cruda"]) else "egreso"


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 16), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_paginas(ruta, extractor="pdfplumber"):
    if extractor == "pdftotext":
        try:
            out = subprocess.run(
                ["pdftotext", "-layout", str(ruta), "-"],
                capture_output=True, text=True, timeout=120,
            )
        except FileNotFoundError:
            sys.exit("Falta pdftotext (poppler-utils). Instálalo o usa --extractor pdfplumber.")
        return [out.stdout]
    try:
        import pdfplumber
    except ImportError:
        sys.exit("Falta pdfplumber. Instálalo: python -m pip install pdfplumber")
    with pdfplumber.open(ruta) as pdf:
        return [pg.extract_text() or "" for pg in pdf.pages]


def dentro_de_crudos(ruta_texto):
    p = Path(ruta_texto)
    p = p if p.is_absolute() else (RAIZ / p)
    p = p.resolve()
    try:
        p.relative_to(REALES_CRUDOS)
    except ValueError:
        sys.exit(f"Ruta fuera de data/reales_crudos/: {ruta_texto}")
    if not p.exists():
        sys.exit(f"No existe: {ruta_texto}")
    return p


def cargar_titulares(ruta):
    if ruta is None:
        return []
    p = dentro_de_crudos(ruta)
    nombres = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return sorted(nombres, key=len, reverse=True)


def actualizar_trazabilidad(seud, filas):
    """Reemplaza las filas de este seudónimo; el archivo es determinista (no acumula duplicados)."""
    REALES_ANON.mkdir(parents=True, exist_ok=True)
    ruta = REALES_ANON / "_trazabilidad.md"
    cabecera = (
        "# Trazabilidad de extractos reales (sin datos personales)\n\n"
        "| seudonimo | mes | banco | tipo_cuenta | sha256_original | sha256_salida_csv | "
        "filas_salida | fuera_de_mes | excluidos_voluntario | fecha_recepcion | ejecutado_utc |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    previas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
    # Clave = voluntario + mes: se reemplazan solo las filas de los meses de esta corrida.
    meses = {str(f[0]) for f in filas}
    def _es_de_corrida(ln):
        return any(ln.startswith(f"| {seud} | {m} |") for m in meses)
    conservar = [ln for ln in previas if ln.startswith("|") and not _es_de_corrida(ln)
                 and not ln.startswith("|---") and not ln.startswith("| seudonimo")]
    nuevas = [f"| {seud} | " + " | ".join(str(x) for x in f) + " |" for f in filas]  # f: 10 valores
    ruta.write_text(cabecera + "\n".join(conservar + nuevas) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Anonimiza extractos reales (protocolo 02 v1.1).")
    ap.add_argument("--seudonimo", required=True, help="p. ej. V07")
    ap.add_argument("--banco", required=True, help="banco o billetera, tal como lo declara el voluntario")
    ap.add_argument("--tipo-cuenta", required=True, choices=CUENTAS)
    ap.add_argument("--extracto", action="append", required=True, metavar="AAAA-MM=RUTA.pdf")
    ap.add_argument("--regla-signo", choices=["minus", "palabras"],
                    help="minus: negativo = egreso. palabras: ingreso si la descripción trae ABONO, "
                         "CONSIGNACION, RECIBIDO, etc. Obligatoria salvo con --diagnostico.")
    ap.add_argument("--columna-monto", choices=["primera", "ultima"],
                    help="si la línea trae monto y saldo: cuál es el monto. Obligatoria si hay ambigüedad.")
    ap.add_argument("--extractor", choices=["pdfplumber", "pdftotext"], default="pdfplumber",
                    help="pdftotext (-layout) conserva columnas y limpia montos: úsalo para bancos "
                         "cuyo PDF sale mangleado con pdfplumber (p. ej. Davivienda).")
    ap.add_argument("--formato-fecha", choices=["auto", "dm", "cc"], default="auto",
                    help="auto: ISO o DD/MM/AAAA. dm: 'DD MM' o 'D/MM' sin año (año del --extracto), "
                         "p. ej. Davivienda/Bancolombia ahorros. cc: etiqueta + fecha ISO "
                         "('Virtual 2026-04-20 ...'), tarjetas de crédito.")
    ap.add_argument("--titular", help="txt con nombres a eliminar (titular y contrapartes), uno por línea; "
                                      "dentro de data/reales_crudos/")
    ap.add_argument("--excluidos", type=int, default=0,
                    help="movimientos excluidos a petición del voluntario (solo el número)")
    ap.add_argument("--fecha-recepcion", default="", help="AAAA-MM-DD, para el registro de custodia")
    ap.add_argument("--diagnostico", action="store_true", help="imprime en consola; no escribe")
    a = ap.parse_args(argv)

    if not re.fullmatch(r"V\d{2}", a.seudonimo):
        sys.exit("El seudónimo debe tener la forma V07.")

    extractos = []
    for item in a.extracto:
        if "=" not in item:
            sys.exit(f"--extracto debe ser AAAA-MM=RUTA: {item}")
        mes, ruta = item.split("=", 1)
        if not re.fullmatch(r"\d{4}-\d{2}", mes):
            sys.exit(f"Mes inválido: {mes}")
        p = dentro_de_crudos(ruta)
        if p.suffix.lower() != ".pdf":
            sys.exit(f"Solo PDF en esta versión (ver protocolo §4.2 para Excel/CSV): {ruta}")
        extractos.append((mes, p))

    titulares = cargar_titulares(a.titular)

    if a.diagnostico:
        mes, p = extractos[0]
        paginas = leer_paginas(p, a.extractor)
        lineas = "\n".join(paginas).splitlines()
        print(f"--- {p.name}: {len(paginas)} páginas, {len(lineas)} líneas de texto ---")
        if not any(t.strip() for t in paginas):
            print("Sin texto extraíble: es escaneo o captura. Ver protocolo §4.3.")
            return
        print("\n".join(lineas[:80]))
        r = parsear_extracto(lineas, mes, None, a.formato_fecha)
        print(f"\nLíneas con fecha: {r['lineas_con_fecha']} | movimientos sin ambigüedad: "
              f"{len(r['movimientos'])} | ambiguas (monto + saldo): {r['ambiguas']} | "
              f"sin monto: {r['sin_monto']} | negativos: {r['negativos']}")
        print("Elige --regla-signo y --columna-monto según lo que veas arriba. No se escribió nada.")
        return

    if a.regla_signo is None:
        sys.exit("Falta --regla-signo (usa --diagnostico primero para decidirla).")

    filas, totales = [], {"titular": 0, "persona_R_A": 0, "digitos_R_B": 0}
    por_mes = []
    hashes_orig = []
    for mes, p in extractos:
        paginas = leer_paginas(p, a.extractor)
        lineas = "\n".join(paginas).splitlines()
        if not any(t.strip() for t in paginas):
            sys.exit(f"{p.name}: sin texto (escaneo o captura). Va a transcripción manual, protocolo §4.3.")
        r = parsear_extracto(lineas, mes, a.columna_monto, a.formato_fecha)
        if r["ambiguas"]:
            sys.exit(f"{p.name}: {r['ambiguas']} líneas con monto y saldo sin --columna-monto. "
                     "Corre --diagnostico y elige la columna.")
        if not r["movimientos"]:
            # Sin esta parada, un PDF equivocado borraría en silencio las filas previas de ese mes.
            sys.exit(f"{p.name}: 0 movimientos dentro de {mes} (fuera de mes: {r['fuera_de_mes']}). "
                     "¿PDF equivocado o mes equivocado? No se escribió nada.")
        por_mes.append((mes, r))
        hashes_orig.append((mes, sha256(p)))
        print(f"{mes}: líneas con fecha {r['lineas_con_fecha']}, movimientos {len(r['movimientos'])}, "
              f"fuera de mes {r['fuera_de_mes']}, sin monto {r['sin_monto']}, negativos {r['negativos']}")

    if a.regla_signo == "minus" and sum(r["negativos"] for _, r in por_mes) == 0:
        sys.exit("La regla 'minus' no encuentra montos negativos en ningún extracto. "
                 "Revisa con --diagnostico o usa --regla-signo palabras.")

    contador_mes = {}
    for mes, r in por_mes:
        for mov in r["movimientos"]:
            contador_mes[mes] = contador_mes.get(mes, 0) + 1
            n = contador_mes[mes]
            desc = depurar(mov["desc_cruda"], titulares, totales)
            filas.append({
                "tx_id": f"{a.seudonimo}-{mes[2:4]}{mes[5:7]}-{n:03d}",
                "seudonimo": a.seudonimo,
                "mes_referencia": mes,
                "fecha": mov["fecha"],
                "descripcion": desc,
                "monto": mov["monto"],
                "signo": signo_de(mov, a.regla_signo),
                "cuenta_tipo": a.tipo_cuenta,
                "proposito_declarado": "",
            })

    if a.regla_signo == "minus":
        print("ADVERTENCIA regla 'minus': todo monto sin '-' queda como ingreso. Confirma con "
              "--diagnostico que el banco imprime '-' en TODOS los egresos. Si el extracto usa "
              "columnas separadas Débito/Crédito, esta regla es incorrecta y no debes usarla.")

    # Fusión por mes: se reemplazan solo los meses procesados; los demás meses del voluntario se conservan.
    REALES_ANON.mkdir(parents=True, exist_ok=True)
    salida = REALES_ANON / f"{a.seudonimo}.csv"
    meses_nuevos = {mes for mes, _ in por_mes}
    conservadas = []
    if salida.exists():
        with open(salida, newline="", encoding="utf-8") as fh:
            conservadas = [row for row in csv.DictReader(fh) if row["mes_referencia"] not in meses_nuevos]
    todas = conservadas + filas
    todas.sort(key=lambda r: (r["mes_referencia"], int(r["tx_id"].rsplit("-", 1)[1])))
    with open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(todas)
    hash_salida = sha256(salida)

    # Reporte de sospechas: solo descripciones YA depuradas (nunca las crudas).
    marcas = []
    for f in filas:
        flags = []
        if "PERSONA" in f["descripcion"]:
            flags.append("revisar nombre")
        if re.search(r"\d{4,}", f["descripcion"]):
            flags.append("dígitos residuales")
        if RE_DIRECCION.search(f["descripcion"]):
            flags.append("posible dirección")
        if es_posible_nombre(f["descripcion"]):
            flags.append("posible nombre de persona")
        if flags:
            marcas.append((f["tx_id"], f["descripcion"], ", ".join(flags)))
    with open(REALES_ANON / f"_sospechas_{a.seudonimo}.md", "w", encoding="utf-8") as fh:
        fh.write(f"# Sospechas — {a.seudonimo} (revisión manual, protocolo §5)\n\n")
        fh.write(f"Filas: {len(filas)}. Marcadas: {len(marcas)}. Este reporte no reemplaza la revisión.\n\n")
        fh.write("| tx_id | descripcion (ya depurada) | motivo |\n|---|---|---|\n")
        for tx, d, m in marcas:
            fh.write(f"| {tx} | {d} | {m} |\n")

    ejecutado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    filas_tr = []
    dict_r = dict(por_mes)
    for mes, h in hashes_orig:
        # Orden = columnas de la cabecera de _trazabilidad.md, tras el seudónimo.
        filas_tr.append([
            mes, a.banco, a.tipo_cuenta, h, hash_salida,
            sum(1 for f in filas if f["mes_referencia"] == mes),
            dict_r[mes]["fuera_de_mes"], a.excluidos, a.fecha_recepcion, ejecutado,
        ])
    actualizar_trazabilidad(a.seudonimo, filas_tr)

    print(f"\nEscrito: {salida.relative_to(RAIZ)} ({len(filas)} filas). Sospechas: {len(marcas)}.")
    print(f"Depuración: titular {totales['titular']}, nombres R-A {totales['persona_R_A']}, "
          f"dígitos R-B {totales['digitos_R_B']}.")
    print("Siguiente paso: revisión manual del protocolo §5 sobre ese CSV. No subir nada a git.")


if __name__ == "__main__":
    main()
