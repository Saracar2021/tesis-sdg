#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WP4 — Muestreo estratificado del conjunto real de test y lotes de anotación doble a ciegas.

Diseño pre-registrado en docs/datos_reales/05_prerregistro_muestreo_anotacion.md (v1.0). No modificar los
parámetros ni la heurística después de congelar: el SHA-256 de este archivo queda en el pre-registro.

Lee     : data/reales_anon/V*.csv (anonimizados). NUNCA data/reales_crudos/.
Escribe : data/reales_anon/anotacion/
            marco_muestreo.csv          todas las filas del marco con estrato, π y pesos (auditoría; NO para anotadores)
            muestra_test_clave.csv      item_id ↔ tx_id, grupo, estrato, peso (clave; NO para anotadores)
            muestra_test_clave_planb.csv  plan B: subconjunto anidado de 154 ítems (solo el mínimo m por estrato),
                                        con pesos recalculados para ese diseño (pre-registro v1.1 §12)
            lote_A1.csv / lote_A1.xlsx  anotadora 1 (6 campos), orden aleatorio propio
            lote_A2.csv / lote_A2.xlsx  anotador 2 (núcleo), orden aleatorio propio
            calibracion.csv / .xlsx     20 ítems FUERA del test, para la ronda conjunta
            _resumen_muestreo.md        parámetros, asignación, composición, SHA-256 (solo agregados)

Uso (desde la raíz del repo):
  python tools/muestreo_wp4.py            # genera; se niega a sobrescribir lotes existentes
  python tools/muestreo_wp4.py --verificar  # recalcula en memoria y compara SHA-256 con lo escrito
  python tools/muestreo_wp4.py --plan-b     # estado de A1/A2 sobre los 154 ítems del plan B; no escribe

El sorteo usa claves SHA-256(semilla:etapa:tx_id) en lugar de un generador pseudoaleatorio: tomar las n claves
más pequeñas equivale a un muestreo aleatorio simple y es idéntico en cualquier máquina y versión de numpy.
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "data" / "reales_anon"
SALIDA = ENTRADA / "anotacion"
TAXONOMIA = RAIZ / "docs" / "taxonomia" / "taxonomia_gastos_colombia_v1.json"

# ----------------------------------------------------------------------------------------- parámetros congelados
SEMILLA = 42
N_TEST = 200          # D-M1
M_MIN = 10            # mínimo por estrato (o todo lo muestreable si hay menos)
K_TOPE = 3            # máximo de filas por descriptor normalizado dentro de un estrato (etapa 1)
MES_MAX = "2026-09"   # D-M2: la serie IPC llega a 2026-09; octubre y noviembre fuera
N_CALIB = 20
VERSION_TAXONOMIA = "1.1.0"

COLUMNAS_ENTRADA = ["tx_id", "seudonimo", "mes_referencia", "fecha", "descripcion", "monto", "signo",
                    "cuenta_tipo", "proposito_declarado"]
VISIBLES = ["item_id", "cuenta_tipo", "signo", "monto", "descripcion"]   # D-M5: lo mismo que ve el clasificador
CAMPOS_A1 = ["categoria_n1", "categoria_n2", "medio_pago", "formalidad_comercio", "duda", "notas"]
CAMPOS_A2 = ["categoria_n1", "categoria_n2", "duda", "notas"]           # D-M4: núcleo

# ----------------------------------------------------------------------------------------- heurística (solo estratos)
# Herramienta de MUESTREO, no etiqueta. Palabras genéricas (verbos bancarios, cadenas y marcas nacionales);
# sin nombres de comercios pequeños ni empleadores del conjunto real. La primera regla que coincide gana.
# Cada regla: (estrato, patrón, condición sobre (cuenta_tipo, signo) o None).
REGLAS = [
    ("reverso_devolucion", r"REVERSAD|ANUL\.?|DEVOLUCION", None),
    ("retiro_efectivo", r"RETIRO|CAJERO|\bATM\b", None),
    ("obligaciones_financieras", r"PAGOS? POR PSE|PAGOS? RAPPIPAY|AJUSTE INTERES", ("tarjeta_credito", "ingreso")),
    ("obligaciones_financieras", r"PAGO (AUTOM )?TC|TARJ\.? ?CREDITO|PAGO CREDITO|GRAVAMEN|IMP/TRANS FINANC|4X1000|"
                                 r"CUOTA|SEGURO|COMIS|RETENCION|AJUSTE INTERES|AVANCE", None),
    ("ingreso", r"NOMI|NOMINA|ABONO INTERES|INTERES GENERADO|PAGO DE INTERESES|RENDIMIENTO|PAGO DE PROVEED|ABONO CUEN",
     None),
    ("movimiento_propio", r"TRANSFERENCIAS? A NEQUI|TRANSFERENCIA DESDE NEQUI|RECARGA|TRANSF\.? PROGRAMADA|DAVIPLATA|"
                          r"BREB|LLAVE|REC\.?INTER TFR|TRASLADO", None),
    ("transferencias_p2p", r"PERSONA", None),
    ("educacion", r"UNIV|COLEGIO|ICETEX|ESCUELA|INSTITUTO|ACADEMIA|PLATZI|COURSERA", None),
    ("salud", r"DROG|FARMA|CRUZ VERDE|CLINIC|MEDIC|ODONT|LABORATOR|\bEPS\b|OPTIC|SANITAS|COLSUBSIDIO", None),
    ("transporte", r"UBER|DIDI|CABIFY|TRANSMI|TRANSPORTE|TERPEL|PRIMAX|TEXACO|PEAJE|PARQUEAD|AVIANCA|LATAM|INDRIVE|"
                   r"GASOLIN|COMBUST|\bEDS\b|CAR RENTAL", None),
    ("comidas_fuera", r"RAPPI|IFOOD|CREPES|TOSTAO|CAF[EÉ]\b|JUAN VALDEZ|RESTAUR|PIZZ|BURGER|MC ?DONALD|KFC|FRISBY|"
                      r"EL CORRAL|STARBUCKS|PANADER|HELAD|SUSHI|TACO|WOK", None),
    ("alimentos_mercado", r"EXITO|CARULLA|JUMBO|OLIMPICA|\bD1\b|\bARA\b|JERONIMO MARTINS|ISIMO|OXXO|FRUVER|MERCA|"
                          r"SURTI|\bMETRO\b|ALKOSTO|MAKRO|PRICESMART|CARNES", None),
    ("telecom_conectividad", r"CLARO|MOVISTAR|TIGO|\bWOM\b|\bETB\b|INTERNET|CELULAR", None),
    ("vivienda_servicios", r"ENEL|CODENSA|ACUEDUCTO|VANTI|GAS NATURAL|ADMINISTRACION|ARRIENDO|EAAB", None),
    ("entretenimiento", r"SPOTIFY|NETFLIX|HBO|DISNEY|PRIME VIDEO|YOUTUBE|STEAM|CINE|TEATRO|\bBAR\b|LICOR|PET|MASCOT|"
                        r"APPLE\.COM|GOOGLE|PLAYSTATION|XBOX|TICKET|BOLETA", None),
    ("vestuario_cuidado_personal", r"ZARA|FALABELLA|ARTURO CALLE|KOAJ|TENNIS|NIKE|ADIDAS|PELUQ|BARBER|\bSPA\b|"
                                   r"NOVAVENTA|NATURA|YANBAL|VELEZ|STUDIO F|H Y M|H&M|MANGO|DOLLARCITY", None),
    ("hogar_articulos", r"HOMECENTER|\bEASY\b|IKEA|JAMAR|FERRETER|MINISO|SODIMAC", None),
]
_REGLAS = [(e, re.compile(p), c) for e, p, c in REGLAS]


def estrato_heuristico(desc, cuenta, signo):
    d = str(desc).upper()
    for est, rx, cond in _REGLAS:
        if cond is not None and (cuenta, signo) != cond:
            continue
        if rx.search(d):
            return est
    return "sin_heuristica"


def descriptor_normalizado(desc):
    d = re.sub(r"[#\d]+", " ", str(desc).upper())
    d = re.sub(r"[^A-ZÁÉÍÓÚÑÜ ]", " ", d)
    return re.sub(r"\s+", " ", d).strip()


def clave(etapa, ident):
    """Clave pseudoaleatoria reproducible en cualquier plataforma."""
    return hashlib.sha256(f"{SEMILLA}:{etapa}:{ident}".encode("utf-8")).hexdigest()


def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def sha256_df(df):
    return hashlib.sha256(df.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------------------- carga y marco
def cargar():
    archivos = sorted(ENTRADA.glob("V*.csv"))
    if not archivos:
        sys.exit(f"No hay V*.csv en {ENTRADA.relative_to(RAIZ)}")
    partes = []
    for f in archivos:
        d = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8")
        faltan = [c for c in COLUMNAS_ENTRADA if c not in d.columns]
        if faltan:
            sys.exit(f"{f.name}: faltan columnas {faltan}")
        partes.append(d[COLUMNAS_ENTRADA])
    df = pd.concat(partes, ignore_index=True)
    if not df["tx_id"].is_unique:
        sys.exit("tx_id duplicados en la entrada")
    df["monto"] = pd.to_numeric(df["monto"], errors="raise").astype("int64")
    hashes = {f.name: sha256_archivo(f) for f in archivos}
    return df, hashes


def construir_marco(df):
    exclusiones = []
    resid = df["descripcion"].str.fullmatch(r"\s*de \d+\s*") | df["descripcion"].str.fullmatch(r"\s*\$?-?[\d\.,]+\s*")
    if resid.any():
        sys.exit(f"{int(resid.sum())} descripciones residuales (p. ej. 'de 1' o un monto): corrige la extracción "
                 "antes de muestrear; el diseño pre-registrado asume que no existen.")
    fuera = df["mes_referencia"] > MES_MAX
    for (g, m), n in df[fuera].groupby(["seudonimo", "mes_referencia"]).size().items():
        exclusiones.append({"motivo": f"mes > {MES_MAX} (sin IPC, D-M2)", "grupo": g, "mes": m, "filas": int(n)})
    marco = df[~fuera].copy()
    marco["descriptor_norm"] = marco["descripcion"].map(descriptor_normalizado)
    marco["estrato_muestreo"] = [estrato_heuristico(d, c, s) for d, c, s in
                                 zip(marco["descripcion"], marco["cuenta_tipo"], marco["signo"])]
    return marco.sort_values("tx_id", kind="mergesort").reset_index(drop=True), exclusiones


# ----------------------------------------------------------------------------------------- diseño en dos etapas
def etapa1_retener(marco):
    """Por (estrato, descriptor): retiene min(K_TOPE, N_d) filas por clave SHA. π1 = min(1, K/N_d)."""
    marco = marco.copy()
    marco["k1"] = [clave("etapa1", t) for t in marco["tx_id"]]
    marco["N_d"] = marco.groupby(["estrato_muestreo", "descriptor_norm"])["tx_id"].transform("size")
    marco["rango_d"] = marco.groupby(["estrato_muestreo", "descriptor_norm"])["k1"].rank(method="first")
    marco["retenida"] = marco["rango_d"] <= K_TOPE
    marco["pi1"] = (K_TOPE / marco["N_d"]).clip(upper=1.0)
    return marco


def asignar(marco, n_total=None):
    """n_h: mínimo M_MIN (o R_h), resto proporcional a N_h entre estratos con capacidad (restos mayores).
    Con n_total = 0 devuelve solo el mínimo por estrato (diseño del plan B)."""
    n_total = N_TEST if n_total is None else n_total
    N = marco.groupby("estrato_muestreo").size()
    R = marco[marco["retenida"]].groupby("estrato_muestreo").size().reindex(N.index, fill_value=0)
    if R.sum() < n_total:
        sys.exit(f"Capacidad muestreable {R.sum()} < n {n_total}")
    n = R.clip(upper=M_MIN).astype(int)
    while n.sum() < n_total:
        libre = (R - n) > 0
        resto = n_total - int(n.sum())
        cuota = N[libre] / N[libre].sum() * resto
        base = cuota.astype(int)
        faltan = resto - int(base.sum())
        orden = (cuota - base).sort_values(ascending=False, kind="mergesort").index[:faltan]
        base.loc[orden] += 1
        n.loc[libre] = (n[libre] + base).clip(upper=R[libre])
    return pd.DataFrame({"N_h": N, "R_h": R, "n_h": n})


def etapa2_seleccionar(marco, asig):
    marco = marco.copy()
    marco["k2"] = [clave("etapa2", t) for t in marco["tx_id"]]
    ret = marco[marco["retenida"]].copy()
    ret["rango_h"] = ret.groupby("estrato_muestreo")["k2"].rank(method="first")
    ret = ret.join(asig, on="estrato_muestreo")
    elegidas = set(ret.loc[ret["rango_h"] <= ret["n_h"], "tx_id"])
    marco = marco.merge(ret[["tx_id", "rango_h"]], on="tx_id", how="left")
    marco = marco.join(asig, on="estrato_muestreo")
    marco["pi2"] = marco["n_h"] / marco["R_h"]
    marco["en_test"] = marco["tx_id"].isin(elegidas)
    marco["pi"] = marco["pi1"] * marco["pi2"]
    marco["peso_muestreo"] = 1.0 / marco["pi"]
    return marco


def calibracion(marco):
    """N_CALIB ítems fuera del test y con descriptores que NO están en el test (independencia del κ).
    Reparto: uno por estrato en orden de tamaño, y se repite la vuelta hasta completar."""
    dn_test = set(marco.loc[marco["en_test"], "descriptor_norm"])
    pool = marco[~marco["en_test"] & ~marco["descriptor_norm"].isin(dn_test)].copy()
    pool["kc"] = [clave("calib", t) for t in pool["tx_id"]]
    pool = pool.sort_values("kc", kind="mergesort").drop_duplicates("descriptor_norm")
    orden = marco.groupby("estrato_muestreo").size().sort_values(ascending=False, kind="mergesort").index
    colas = {e: list(pool.loc[pool["estrato_muestreo"] == e, "tx_id"]) for e in orden}
    elegidos = []
    while len(elegidos) < N_CALIB and any(colas.values()):
        for e in orden:
            if colas[e] and len(elegidos) < N_CALIB:
                elegidos.append(colas[e].pop(0))
    return marco[marco["tx_id"].isin(elegidos)].copy()


# ----------------------------------------------------------------------------------------- lotes
def lote(filas, prefijo, etapa_orden, campos, anotador, bloque=None, con_orden=False):
    """bloque (opcional): serie 1/2 alineada con filas; el bloque 1 va primero (orden aleatorio dentro de cada bloque).
    con_orden: añade la columna visible 'orden' (1..n) para restaurar el orden si el anotador reordena."""
    out = filas[["item_id", "cuenta_tipo", "signo", "monto", "descripcion"]].copy()
    out["_b"] = 1 if bloque is None else bloque.to_numpy()
    out["_k"] = [clave(etapa_orden, i) for i in out["item_id"]]
    out = out.sort_values(["_b", "_k"], kind="mergesort").drop(columns=["_b", "_k"]).reset_index(drop=True)
    for c in campos:
        out[c] = ""
    out.insert(0, "anotador", anotador)
    if con_orden:
        out.insert(1, "orden", range(1, len(out) + 1))
    return out


def enums_taxonomia():
    """Listas cerradas de la taxonomía congelada. Se valida la versión ANTES de escribir cualquier archivo."""
    import json
    tax = json.loads(TAXONOMIA.read_text(encoding="utf-8"))
    if tax["metadata"]["version"] != VERSION_TAXONOMIA:
        sys.exit(f"Taxonomía {tax['metadata']['version']} ≠ {VERSION_TAXONOMIA}")
    n1 = [c["id"] for c in tax["categorias_nivel_1"]]
    n2 = sorted({(s["id"] if isinstance(s, dict) else s) for c in tax["categorias_nivel_1"] for s in c["subtipos"]})
    mp = [v["id"] for v in tax["dimension_medio_pago"]["valores"]]
    fc = [v["id"] for v in tax["dimension_formalidad_comercio"]["valores"]]
    return {"categoria_n1": n1, "categoria_n2": n2, "medio_pago": mp, "formalidad_comercio": fc, "duda": ["0", "1"]}


def escribir_xlsx(df, ruta, campos, listas):
    """Libro para anotar: listas desplegables con los enums de la taxonomía v1.1.0; columnas observables bloqueadas."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Protection
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "anotacion"
    ws.append(list(df.columns))
    for fila in df.itertuples(index=False):
        ws.append(list(fila))
    lst = wb.create_sheet("listas")
    for j, (nombre, vals) in enumerate(listas.items(), start=1):
        lst.cell(row=1, column=j, value=nombre)
        for i, v in enumerate(vals, start=2):
            lst.cell(row=i, column=j, value=v)
    lst.sheet_state = "hidden"

    cols = list(df.columns)
    n = len(df) + 1
    for j, (nombre, vals) in enumerate(listas.items(), start=1):
        if nombre not in campos:
            continue
        letra_lista = lst.cell(row=1, column=j).column_letter
        dv = DataValidation(type="list", formula1=f"=listas!${letra_lista}$2:${letra_lista}${len(vals) + 1}",
                            allow_blank=True, showErrorMessage=True,
                            errorTitle="Valor fuera de la taxonomía", error="Elige un valor de la lista.")
        letra = ws.cell(row=1, column=cols.index(nombre) + 1).column_letter
        dv.add(f"{letra}2:{letra}{n}")
        ws.add_data_validation(dv)

    gris = PatternFill("solid", fgColor="EEEEEE")
    for j, c in enumerate(cols, start=1):
        celda = ws.cell(row=1, column=j)
        celda.font = Font(bold=True)
        editable = c in campos
        for i in range(2, n + 1):
            x = ws.cell(row=i, column=j)
            x.protection = Protection(locked=not editable)
            if not editable:
                x.fill = gris
        ws.column_dimensions[celda.column_letter].width = {"descripcion": 48, "notas": 40}.get(c, 18)
    ws.freeze_panes = "B2"
    ws.protection.sheet = True          # sin contraseña: solo evita editar por accidente los observables
    ws.protection.formatColumns = False
    wb.save(ruta)


# ----------------------------------------------------------------------------------------- resumen
def resumen_md(df, hashes, exclusiones, marco, asig, test, calib, salidas):
    w = test["peso_muestreo"]
    kish = w.sum() ** 2 / (w ** 2).sum()
    L = [f"# Resumen del muestreo WP4 (generado por `tools/muestreo_wp4.py`)\n",
         f"- Script SHA-256: `{sha256_archivo(Path(__file__))}`",
         f"- Parámetros: semilla {SEMILLA}, n = {N_TEST}, m = {M_MIN}, k = {K_TOPE}, mes máximo {MES_MAX}, "
         f"calibración {N_CALIB}, taxonomía v{VERSION_TAXONOMIA}",
         f"- Entrada: {len(df)} filas. Marco: {len(marco)} filas, {marco['seudonimo'].nunique()} grupos de extractos.",
         f"- Muestra: {len(test)} filas · n efectivo (Kish) = {kish:.0f} · Σ pesos = {w.sum():.1f} "
         f"(esperado ≈ {len(marco)})\n",
         "## Entradas (SHA-256)\n", "| archivo | sha256 |", "|---|---|"]
    L += [f"| {k} | `{v}` |" for k, v in hashes.items()]
    L += ["\n## Exclusiones del marco\n", "| motivo | grupo | mes | filas |", "|---|---|---|---|"]
    L += [f"| {e['motivo']} | {e['grupo']} | {e['mes']} | {e['filas']} |" for e in exclusiones]
    L += ["\n## Asignación por estrato heurístico (no son etiquetas)\n",
          "| estrato | N_h | R_h (tras tope) | n_h | peso mín | peso máx |", "|---|---|---|---|---|---|"]
    pesos = test.groupby("estrato_muestreo")["peso_muestreo"].agg(["min", "max"])
    for e, r in asig.sort_values("N_h", ascending=False).iterrows():
        pm = pesos.loc[e] if e in pesos.index else {"min": float("nan"), "max": float("nan")}
        L.append(f"| {e} | {r.N_h} | {r.R_h} | {r.n_h} | {pm['min']:.1f} | {pm['max']:.1f} |")
    for var in ["seudonimo", "cuenta_tipo", "signo", "mes_referencia"]:
        ct = pd.DataFrame({"marco": marco[var].value_counts(), "muestra": test[var].value_counts()}).fillna(0)
        L += [f"\n## Composición por `{var}`\n", f"| {var} | marco | muestra |", "|---|---|---|"]
        L += [f"| {i} | {int(r.marco)} | {int(r.muestra)} |" for i, r in ct.sort_index().iterrows()]
    tb = test[test["en_planb"]]
    wb_ = tb["peso_muestreo_b"]
    L += [f"\n## Plan B (v1.1)\n", f"{len(tb)} ítems anidados (solo el mínimo m = {M_MIN} por estrato) · n efectivo "
          f"(Kish, pesos del plan B) = {wb_.sum() ** 2 / (wb_ ** 2).sum():.0f} · descriptores distintos = "
          f"{tb['descriptor_norm'].nunique()}. Son los {len(tb)} primeros de `lote_A2` por la columna `orden`."]
    L += [f"\n## Calibración\n", f"{len(calib)} ítems fuera del test, de descriptores ausentes en el test; "
          f"estratos: {calib['estrato_muestreo'].value_counts().to_dict()}",
          "\n## Salidas (SHA-256 de los CSV; los .xlsx no son deterministas byte a byte)\n",
          "| archivo | sha256 |", "|---|---|"]
    L += [f"| {k} | `{v}` |" for k, v in salidas.items()]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------------------- principal
def generar():
    df, hashes = cargar()
    marco, exclusiones = construir_marco(df)
    marco = etapa1_retener(marco)
    asig = asignar(marco)
    marco = etapa2_seleccionar(marco, asig)
    test = marco[marco["en_test"]].copy()
    assert len(test) == N_TEST, len(test)
    # item_id opaco: orden por clave SHA, no revela estrato ni grupo
    test["_k"] = [clave("item", t) for t in test["tx_id"]]
    test = test.sort_values("_k", kind="mergesort").drop(columns="_k").reset_index(drop=True)
    test["item_id"] = [f"T{i:03d}" for i in range(1, len(test) + 1)]
    # Plan B (v1.1): solo el mínimo m por estrato. Misma clave SHA y mismo rango → anidado en la muestra de 200.
    asig_b = asignar(marco, n_total=0).rename(columns={"n_h": "n_h_b"})
    test = test.join(asig_b["n_h_b"], on="estrato_muestreo")
    test["en_planb"] = test["rango_h"] <= test["n_h_b"]
    test["pi2_b"] = test["n_h_b"] / test["R_h"]
    test["peso_muestreo_b"] = 1.0 / (test["pi1"] * test["pi2_b"])
    N_PLANB = int(asig_b["n_h_b"].sum())
    assert int(test["en_planb"].sum()) == N_PLANB, "el plan B no quedó anidado en la muestra"
    calib = calibracion(marco)
    calib["_k"] = [clave("item_c", t) for t in calib["tx_id"]]
    calib = calib.sort_values("_k", kind="mergesort").drop(columns="_k").reset_index(drop=True)
    calib["item_id"] = [f"C{i:02d}" for i in range(1, len(calib) + 1)]
    assert not set(calib["tx_id"]) & set(test["tx_id"])
    assert not set(calib["descriptor_norm"]) & set(test["descriptor_norm"])

    clave_cols = ["item_id", "tx_id", "seudonimo", "mes_referencia", "fecha", "descripcion", "monto", "signo",
                  "cuenta_tipo", "estrato_muestreo", "descriptor_norm", "N_d", "pi1", "pi2", "pi", "peso_muestreo"]
    tablas = {
        "marco_muestreo.csv": marco[["tx_id", "seudonimo", "mes_referencia", "cuenta_tipo", "signo",
                                     "estrato_muestreo", "descriptor_norm", "N_d", "retenida", "pi1", "N_h", "R_h",
                                     "n_h", "pi2", "pi", "peso_muestreo", "en_test"]],
        "muestra_test_clave.csv": test[clave_cols],
        "lote_A1.csv": lote(test, "T", "orden_A1", CAMPOS_A1, "A1"),
        "lote_A2.csv": lote(test, "T", "orden_A2", CAMPOS_A2, "A2",
                            bloque=test["en_planb"].map({True: 1, False: 2}), con_orden=True),
        "muestra_test_clave_planb.csv": test.loc[test["en_planb"],
                                                 [c for c in clave_cols if c not in ("pi2", "pi", "peso_muestreo")]
                                                 + ["n_h_b", "pi2_b", "peso_muestreo_b"]]
                                        .rename(columns={"pi2_b": "pi2", "peso_muestreo_b": "peso_muestreo",
                                                         "n_h_b": "n_h"}),
        "calibracion.csv": lote(calib, "C", "orden_C", CAMPOS_A1, "A1+A2"),
        "calibracion_clave.csv": calib[["item_id", "tx_id", "seudonimo", "estrato_muestreo", "descriptor_norm"]],
    }
    assert set(tablas["lote_A1.csv"]["item_id"]) == set(tablas["lote_A2.csv"]["item_id"])
    assert (tablas["lote_A1.csv"]["item_id"] != tablas["lote_A2.csv"]["item_id"]).any(), "mismo orden A1/A2"
    primeros = set(tablas["lote_A2.csv"]["item_id"].head(N_PLANB))
    assert primeros == set(tablas["muestra_test_clave_planb.csv"]["item_id"]), "A2 no empieza por el plan B"
    for nombre in ["lote_A1.csv", "lote_A2.csv", "calibracion.csv"]:
        assert not {"tx_id", "seudonimo", "fecha", "estrato_muestreo", "peso_muestreo"} & set(tablas[nombre].columns)
    return df, hashes, exclusiones, marco, asig, test, calib, tablas


def main(argv=None):
    ap = argparse.ArgumentParser(description="Muestreo WP4 y lotes de anotación (pre-registro 05).")
    ap.add_argument("--verificar", action="store_true", help="recalcula y compara con lo escrito; no escribe")
    ap.add_argument("--forzar", action="store_true", help="sobrescribe lotes que cambiaron (¡borra anotaciones!)")
    ap.add_argument("--plan-b", action="store_true", help="estado de A1/A2 sobre los ítems del plan B; no escribe")
    a = ap.parse_args(argv)

    df, hashes, exclusiones, marco, asig, test, calib, tablas = generar()
    salidas = {k: sha256_df(v) for k, v in tablas.items()}

    if a.plan_b:
        ids = set(tablas["muestra_test_clave_planb.csv"]["item_id"])
        print(f"Plan B: {len(ids)} ítems (los {len(ids)} primeros de lote_A2 por la columna 'orden').")
        for an in ("A1", "A2"):
            ruta = SALIDA / f"lote_{an}.xlsx"
            if not ruta.exists():
                print(f"  {an}: no existe {ruta.name}")
                continue
            x = pd.read_excel(ruta, sheet_name="anotacion", dtype=str).fillna("")
            hecho = x[x["item_id"].isin(ids) & x["categoria_n1"].str.strip().ne("")]
            faltan = sorted(ids - set(hecho["item_id"]))
            print(f"  {an}: {len(hecho)}/{len(ids)} con categoria_n1 · faltan {len(faltan)}"
                  + (f": {', '.join(faltan[:20])}{' …' if len(faltan) > 20 else ''}" if faltan else ""))
        print("Si se activa el plan B, los pasos de κ y adjudicación usan muestra_test_clave_planb.csv "
              "(pesos del diseño de 154); los 46 ítems restantes no entran al test.")
        return

    if a.verificar:
        mal = [k for k, h in salidas.items() if not (SALIDA / k).exists() or sha256_archivo(SALIDA / k) != h]
        print("OK: salidas idénticas" if not mal else f"DIFERENCIAS en {mal}")
        sys.exit(1 if mal else 0)

    listas = enums_taxonomia()
    SALIDA.mkdir(parents=True, exist_ok=True)
    # Escritura idempotente: un archivo con contenido idéntico no se toca (ni su .xlsx, que puede tener anotaciones).
    # Un lote que cambió solo se sobrescribe con --forzar.
    libros = {"lote_A1.csv": CAMPOS_A1, "lote_A2.csv": CAMPOS_A2, "calibracion.csv": CAMPOS_A1}
    cambian = [k for k in tablas if not (SALIDA / k).exists() or sha256_archivo(SALIDA / k) != salidas[k]]
    bloqueados = [k for k in cambian if k in libros and (SALIDA / k.replace(".csv", ".xlsx")).exists()]
    if bloqueados and not a.forzar:
        sys.exit(f"Cambiarían {bloqueados} y ya tienen .xlsx (podría haber anotaciones). Revisa y usa --forzar.")
    for k in cambian:
        (SALIDA / k).write_bytes(tablas[k].to_csv(index=False, lineterminator="\n").encode("utf-8"))
        if k in libros:
            escribir_xlsx(tablas[k], SALIDA / k.replace(".csv", ".xlsx"), libros[k], listas)
    print(f"Archivos escritos: {cambian or 'ninguno (todo idéntico)'}")
    (SALIDA / "_resumen_muestreo.md").write_text(
        resumen_md(df, hashes, exclusiones, marco, asig, test, calib, salidas), encoding="utf-8")
    w = test["peso_muestreo"]
    print(f"Marco {len(marco)} · test {len(test)} · calibración {len(calib)} · n_ef Kish {w.sum()**2/(w**2).sum():.0f}")
    print(f"Escrito en {SALIDA.relative_to(RAIZ)}. Entrega a A2 SOLO lote_A2.xlsx (y calibracion.xlsx en la sesión).")


if __name__ == "__main__":
    main()
