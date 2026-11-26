#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WP4 — Acuerdo entre anotadores (Cohen's κ sobre categoria_n1) y lista de desacuerdos para adjudicar.

Pre-registro: docs/datos_reales/05_prerregistro_muestreo_anotacion.md (v1.4), §6, §12 y §13.
Convenciones de los 4 casos: docs/datos_reales/07_hoja_calibracion_casos.md (fijadas en la adjudicación, v1.4).

Lee     : data/reales_anon/anotacion/lote_A1.xlsx, lote_A2.xlsx (o .csv) y la clave del test (--clave).
Escribe : data/reales_anon/anotacion/acuerdo_<clave>/
            _reporte_acuerdo.md          κ con IC95, % de acuerdo, matriz, acuerdo por clase y por estrato (sin textos)
            matriz_confusion_A1xA2.csv   filas = A1, columnas = A2, las 16 categorías
            adjudicacion.xlsx / .csv     desacuerdos con las dos etiquetas y columnas vacías para la etiqueta final
            una_sola_anotacion.csv       ítems de la clave anotados por un solo anotador (si los hay)
            inconsistencias_n2.csv       categoria_n2 que no pertenece a su categoria_n1 (si las hay)
            correcciones_convencion.csv  ítems ACORDADOS (A1 = A2 en categoria_n1) cuya etiqueta difiere de la
                                         convención de su caso; la aplica tools/consolidar_test_wp4.py

Uso (desde la raíz del repo):
  python tools/acuerdo_wp4.py                                   # test de 200 ítems
  python tools/acuerdo_wp4.py --clave data/reales_anon/anotacion/muestra_test_clave_planb.csv   # plan B (154)

Reglas pre-registradas:
  * κ de Cohen sobre categoria_n1, solo ítems con doble anotación. Mínimo 80 en común; si hay menos, se detiene.
  * IC95 percentil por bootstrap: 2.000 réplicas, semilla 42, remuestreo por fila ESTRATIFICADO por estrato_muestreo.
  * Valores fuera de la taxonomía v1.1.0 en categoria_n1: el script se detiene y los lista (no corrige nada).
  * κ sobre las anotaciones ORIGINALES (sin calibración ni convenciones previas, v1.4 §13). Sin los ítems de los 4
    casos se reporta como dato descriptivo con el patrón pre-registrado (v1.3) y con los ampliados de la v1.4.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
VERSION_TAXONOMIA = "1.1.0"


# Rutas derivadas de RAIZ: se calculan al llamarlas (no al importar), para que un monkeypatch de RAIZ las redirija.
def ruta_anotacion():
    return RAIZ / "data" / "reales_anon" / "anotacion"


def ruta_taxonomia():
    return RAIZ / "docs" / "taxonomia" / "taxonomia_gastos_colombia_v1.json"
SEMILLA = 42
N_BOOT = 2000
MIN_COMUN = 80
CAUSAS = ["error_anotador", "ambiguedad_regla", "descripcion_insuficiente", "convencion_calibracion"]

# Patrones PRE-REGISTRADOS de los 4 casos (v1.2 §5, PSE corregido en v1.3). Fijados antes de anotar; no se cambian.
CASOS_CONVENCION = {
    "reverso_devolucion": (r"REVERSAD|ANUL\.|DEVOLUCION", None),
    # Solo pasarela o banco, sin facturador identificable (corrección v1.3, antes de anotar: la v1.2 incluía
    # también PSE con facturador, p. ej. un colegio o una telefónica, que R5 sí resuelve).
    "pse_sin_facturador": (r"^(?:CENTRAL DE C PAGO POR PSE|COMPRA (?:BANCOLOMBIA|BANCO DAVIVIENDA SA|NEQUI S\.?A\.?.*|"
                           r"TECNIPAGOS S ?A|#) ?COMPRAS Y PAGOS PSE)$", "banco"),
    "transf_billetera_sin_persona": (r"NEQUI|DAVIPLATA", "banco"),
    "compra_en_persona": (r"^(?:COMPRA EN |PAGO QR )?PERSONA$", None),
}


def caso_convencion_v13(desc, cuenta):
    """Caso según los patrones pre-registrados (v1.3). Solo para el κ descriptivo pre-registrado."""
    d = str(desc).upper().strip()
    for nombre, (pat, cta) in CASOS_CONVENCION.items():
        if cta is not None and cuenta != cta:
            continue
        if nombre == "transf_billetera_sin_persona" and ("PERSONA" in d or "PSE" in d):
            continue
        if re.search(pat, d):
            return nombre
    return ""


# Convenciones v1.4 (hoja 07, fijadas en la adjudicación el 26 nov, antes de ver predicciones). Definidas DESPUÉS de
# anotar: lo que se calcule con ellas se marca como tal. Orden: la primera que coincide gana.
# (caso, subcaso, patrón, cuenta o None, exige_no_persona, categoria_n1, categoria_n2, regla citada)
CONVENCIONES_V14 = [
    ("reverso_devolucion", "reverso_comercio_identificable", r"(?=.*(?:REVERSAD|ANUL\.|DEVOLUCION))(?=.*RAPPI)", None,
     False, "comidas_fuera", "domicilios_app", "caso 1: R1 (comercio identificable) + R4 (domicilio de plataforma)"),
    # Solo los reversos que la hoja nombra como «sin bien identificable». Cualquier otro reverso no tiene regla
    # automática: R1 exige decidir el bien caso a caso, así que se lista y se detiene la consolidación.
    ("reverso_devolucion", "reverso_sin_bien_identificable",
     r"^(?:DEVOLUCION|DEVOLUCION GW-SIA|REVERSADA - DLOCAL\b.*|REVERSADA - FALABELLA\b.*)$", None,
     False, "otros", "ininteligible", "caso 1: R7 (sin comercio, o pasarela/tienda que no permite saber el bien)"),
    ("reverso_devolucion", "reverso_sin_regla", r"REVERSAD|ANUL\.|DEVOLUCION", None,
     False, None, None, "caso 1: reverso no listado en la hoja; decidir con R1 (bien identificable) o R7"),
    ("pse_sin_facturador", "pse_sin_facturador", CASOS_CONVENCION["pse_sin_facturador"][0], "banco",
     False, "otros", "ininteligible", "caso 2: R7 (R5 no aplica: el texto no nombra la factura)"),
    ("compra_en_persona", "compra_o_pago_a_persona",
     r"^(?:COMPRA(?: EN)? |PAGO QR )?(?:RBM\*)?PERSONA(?: FRANQUICIA MASTER CARD)?$", None,
     False, "otros", "ininteligible", "caso 4: exclusión de transferencias_p2p (pago por bien/servicio) + R7"),
    ("compra_en_persona", "transf_persona", r"^TRANSF\b.*\bPERSONA$", None,
     False, "transferencias_p2p", "indeterminada",
     "caso 4: criterio del caso 3 (PERSONA también enmascara al titular; no distingue cuenta propia de tercero)"),
    ("transf_billetera_sin_persona", "billetera", r"^TRANSFERENCIAS?\b.*(?:NEQUI|DAVIPLATA)", "banco",
     True, "transferencias_p2p", "indeterminada", "caso 3: caso límite de movimiento_propio (sin titularidad en el texto)"),
    ("transf_billetera_sin_persona", "analogia_cuenta_otra_entidad",
     r"^(?!COMPRA).*(?:TRASLADO VIRTUAL OTROS BANCOS|BREB|REC\.INTER TFR)", "banco",
     True, "transferencias_p2p", "indeterminada", "caso 3: extensión por analogía (decisión de la investigadora)"),
]


def convencion(desc, cuenta, con_analogia=True):
    """Devuelve el dict de la convención v1.4 que aplica, o None."""
    d = str(desc).upper().strip()
    for caso, sub, pat, cta, sin_persona, n1, n2, regla in CONVENCIONES_V14:
        if cta is not None and cuenta != cta:
            continue
        if sin_persona and ("PERSONA" in d or "PSE" in d):
            continue
        if sub == "analogia_cuenta_otra_entidad" and not con_analogia:
            continue
        if re.search(pat, d):
            return {"caso": caso, "subcaso": sub, "categoria_n1": n1, "categoria_n2": n2, "regla": regla}
    return None


def caso_convencion(desc, cuenta):
    """Caso v1.4 (con extensiones). Es el que se escribe en el test y el que guía las correcciones."""
    c = convencion(desc, cuenta)
    return c["caso"] if c else ""


def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    try:
        return p.resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return str(p)


def taxonomia():
    tax = json.loads(ruta_taxonomia().read_text(encoding="utf-8"))
    if tax["metadata"]["version"] != VERSION_TAXONOMIA:
        sys.exit(f"Taxonomía {tax['metadata']['version']} ≠ {VERSION_TAXONOMIA}")
    n1 = [c["id"] for c in tax["categorias_nivel_1"]]
    n2 = {c["id"]: {(s["id"] if isinstance(s, dict) else s) for s in c["subtipos"]} for c in tax["categorias_nivel_1"]}
    return n1, n2


def leer_lote(ruta, anotador):
    if ruta.suffix.lower() == ".xlsx":
        df = pd.read_excel(ruta, sheet_name="anotacion", dtype=str)
    else:
        df = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    df = df.fillna("").apply(lambda c: c.str.strip())
    for c in ["item_id", "categoria_n1", "categoria_n2", "duda", "notas"]:
        if c not in df.columns:
            sys.exit(f"{ruta.name}: falta la columna {c}")
    if not df["item_id"].is_unique:
        sys.exit(f"{ruta.name}: item_id duplicados")
    keep = ["item_id", "categoria_n1", "categoria_n2", "duda", "notas"]
    return df[keep].rename(columns={c: f"{c}_{anotador}" for c in keep if c != "item_id"})


def kappa(a, b, etiquetas):
    """Cohen's κ (sin ponderar). Devuelve (κ, p_o, p_e); κ = nan si p_e = 1."""
    a, b = np.asarray(a), np.asarray(b)
    n = len(a)
    po = float((a == b).mean())
    pa = np.array([(a == e).sum() for e in etiquetas]) / n
    pb = np.array([(b == e).sum() for e in etiquetas]) / n
    pe = float((pa * pb).sum())
    k = float("nan") if pe >= 1 else (po - pe) / (1 - pe)
    return k, po, pe


def bootstrap_kappa(a, b, estratos, etiquetas, n_rep=N_BOOT, semilla=SEMILLA):
    rng = np.random.default_rng(semilla)
    a, b, estratos = np.asarray(a), np.asarray(b), np.asarray(estratos)
    grupos = [np.flatnonzero(estratos == e) for e in np.unique(estratos)]
    vals, nulos = [], 0
    for _ in range(n_rep):
        idx = np.concatenate([rng.choice(g, size=len(g), replace=True) for g in grupos])
        k = kappa(a[idx], b[idx], etiquetas)[0]
        if np.isnan(k):
            nulos += 1
        else:
            vals.append(k)
    if not vals:
        return (float("nan"), float("nan")), nulos
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))), nulos


def landis_koch(k):
    if np.isnan(k):
        return "no definido"
    for lim, txt in [(0.20, "pobre"), (0.40, "aceptable"), (0.60, "moderado"), (0.80, "sustancial")]:
        if k <= lim:
            return txt
    return "casi perfecto"


def escribir_adjudicacion_xlsx(df, ruta, n1, n2_todos):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Protection
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "adjudicacion"
    ws.append(list(df.columns))
    for fila in df.itertuples(index=False):
        ws.append(list(fila))
    lst = wb.create_sheet("listas")
    listas = {"categoria_n1_final": n1, "categoria_n2_final": sorted(n2_todos), "causa": CAUSAS}
    for j, (nombre, vals) in enumerate(listas.items(), start=1):
        lst.cell(row=1, column=j, value=nombre)
        for i, v in enumerate(vals, start=2):
            lst.cell(row=i, column=j, value=v)
    lst.sheet_state = "hidden"
    cols = list(df.columns)
    n = len(df) + 1
    editables = {"categoria_n1_final", "categoria_n2_final", "causa", "comentario"}
    for j, (nombre, vals) in enumerate(listas.items(), start=1):
        L = lst.cell(row=1, column=j).column_letter
        dv = DataValidation(type="list", formula1=f"=listas!${L}$2:${L}${len(vals) + 1}", allow_blank=True,
                            showErrorMessage=True, error="Elige un valor de la lista.")
        letra = ws.cell(row=1, column=cols.index(nombre) + 1).column_letter
        dv.add(f"{letra}2:{letra}{max(n, 2)}")
        ws.add_data_validation(dv)
    gris = PatternFill("solid", fgColor="EEEEEE")
    for j, c in enumerate(cols, start=1):
        ws.cell(row=1, column=j).font = Font(bold=True)
        for i in range(2, n + 1):
            x = ws.cell(row=i, column=j)
            x.protection = Protection(locked=c not in editables)
            if c not in editables:
                x.fill = gris
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = \
            {"descripcion": 42, "notas_A1": 30, "notas_A2": 30, "comentario": 40}.get(c, 16)
    ws.freeze_panes = "C2"
    ws.protection.sheet = True
    wb.save(ruta)


def tabla_md(df):
    cab = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "|" + "---|" * len(df.columns)
    filas = ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([cab, sep] + filas)


def main(argv=None):
    ap = argparse.ArgumentParser(description="κ entre anotadores y desacuerdos para adjudicar (WP4).")
    ap.add_argument("--clave", type=Path, default=None, help="por defecto: anotacion/muestra_test_clave.csv")
    ap.add_argument("--a1", type=Path, default=None, help="por defecto: anotacion/lote_A1.xlsx")
    ap.add_argument("--a2", type=Path, default=None, help="por defecto: anotacion/lote_A2.xlsx")
    ap.add_argument("--salida", type=Path, default=None, help="por defecto: anotacion/acuerdo_<nombre de la clave>/")
    a = ap.parse_args(argv)
    anot = ruta_anotacion()
    a.clave = a.clave or anot / "muestra_test_clave.csv"
    a.a1 = a.a1 or anot / "lote_A1.xlsx"
    a.a2 = a.a2 or anot / "lote_A2.xlsx"
    for p in ("clave", "a1", "a2"):
        r = getattr(a, p)
        setattr(a, p, r if r.is_absolute() else (RAIZ / r))
        if not getattr(a, p).exists():
            sys.exit(f"No existe {rel(getattr(a, p))}")
    salida = a.salida or (anot / f"acuerdo_{a.clave.stem}")
    salida = salida if salida.is_absolute() else RAIZ / salida

    n1, n2 = taxonomia()
    n2_todos = set().union(*n2.values())
    clave = pd.read_csv(a.clave, dtype=str, keep_default_na=False)
    for c in ("item_id", "estrato_muestreo", "descripcion", "cuenta_tipo", "signo", "monto"):
        if c not in clave.columns:
            sys.exit(f"{a.clave.name}: falta la columna {c}")
    l1, l2 = leer_lote(a.a1, "A1"), leer_lote(a.a2, "A2")

    ids = set(clave["item_id"])
    for nombre, l in (("A1", l1), ("A2", l2)):
        faltan = ids - set(l["item_id"])
        if faltan:
            sys.exit(f"Lote {nombre}: faltan {len(faltan)} ítems de la clave (p. ej. {sorted(faltan)[:5]})")
    m = clave.merge(l1, on="item_id", how="left").merge(l2, on="item_id", how="left").fillna("")

    # Validación de valores (no se corrige nada en silencio)
    errores = []
    for an in ("A1", "A2"):
        col = m[f"categoria_n1_{an}"]
        malos = m.loc[col.ne("") & ~col.isin(n1), ["item_id", f"categoria_n1_{an}"]]
        errores += [f"{an} {r.item_id}: '{r[1]}'" for r in malos.itertuples(index=False)]
        d = m[f"duda_{an}"]
        errores += [f"{an} {i}: duda='{v}'" for i, v in zip(m["item_id"], d) if v not in ("", "0", "1", "0.0", "1.0")]
    if errores:
        sys.exit("Valores fuera de la taxonomía v1.1.0 / de 0-1. Corrige en el lote y vuelve a correr:\n  "
                 + "\n  ".join(errores[:40]) + (f"\n  … y {len(errores) - 40} más" if len(errores) > 40 else ""))
    incons = []
    for an in ("A1", "A2"):
        for r in m.itertuples(index=False):
            c1, c2 = getattr(r, f"categoria_n1_{an}"), getattr(r, f"categoria_n2_{an}")
            if c1 and c2 and c2 not in n2.get(c1, set()):
                incons.append({"anotador": an, "item_id": r.item_id, "categoria_n1": c1, "categoria_n2": c2})

    hecho1, hecho2 = m["categoria_n1_A1"].ne(""), m["categoria_n1_A2"].ne("")
    comun = m[hecho1 & hecho2].copy()
    sola = m[hecho1 ^ hecho2].copy()
    ninguna = int((~hecho1 & ~hecho2).sum())
    if len(comun) < MIN_COMUN:
        sys.exit(f"Solo {len(comun)} ítems con doble anotación (< {MIN_COMUN} pre-registrados). No se calcula κ.")

    a1, a2 = comun["categoria_n1_A1"].to_numpy(), comun["categoria_n1_A2"].to_numpy()
    k, po, pe = kappa(a1, a2, n1)
    ic, nulos = bootstrap_kappa(a1, a2, comun["estrato_muestreo"], n1)
    comun["caso_convencion"] = [caso_convencion(d, c) for d, c in zip(comun["descripcion"], comun["cuenta_tipo"])]
    variantes = {
        "pre-registrado (v1.3)": [caso_convencion_v13(d, c) != "" for d, c in zip(comun.descripcion, comun.cuenta_tipo)],
        "v1.4: caso 4 ampliado": [convencion(d, c, con_analogia=False) is not None
                                  for d, c in zip(comun.descripcion, comun.cuenta_tipo)],
        "v1.4: caso 4 ampliado + analogía del caso 3": [convencion(d, c) is not None
                                                        for d, c in zip(comun.descripcion, comun.cuenta_tipo)],
    }
    k_sin_var = {}
    for nom, mask in variantes.items():
        sub = comun[~np.asarray(mask)]
        k_sin_var[nom] = (kappa(sub["categoria_n1_A1"], sub["categoria_n1_A2"], n1)[0] if len(sub) else float("nan"),
                          int(np.sum(mask)), len(sub))

    # Correcciones por convención: ítems con A1 = A2 en categoria_n1 cuya etiqueta acordada difiere de la convención.
    corr = []
    conv_desac = []
    sin_regla = []
    for r in comun.itertuples(index=False):
        cv = convencion(r.descripcion, r.cuenta_tipo)
        if cv is None:
            continue
        if cv["categoria_n1"] is None:
            sin_regla.append(r.item_id)
            continue
        e1 = f"{r.categoria_n1_A1}.{r.categoria_n2_A1}" if r.categoria_n2_A1 else r.categoria_n1_A1
        e2 = f"{r.categoria_n1_A2}.{r.categoria_n2_A2}" if r.categoria_n2_A2 else r.categoria_n1_A2
        ec = f"{cv['categoria_n1']}.{cv['categoria_n2']}"
        if r.categoria_n1_A1 != r.categoria_n1_A2:
            conv_desac.append({"item_id": r.item_id, "caso": cv["caso"], "etiqueta_convencion": ec})
            continue
        n2_acordada = r.categoria_n2_A1 if r.categoria_n2_A1 == r.categoria_n2_A2 else None
        if r.categoria_n1_A1 != cv["categoria_n1"] or n2_acordada != cv["categoria_n2"]:
            corr.append({"item_id": r.item_id, "etiqueta_A1": e1, "etiqueta_A2": e2, "etiqueta_convencion": ec,
                         "caso": cv["caso"], "regla_citada": cv["regla"],
                         "cambia": "categoria_n1" if r.categoria_n1_A1 != cv["categoria_n1"] else "solo categoria_n2"})

    # Matriz y acuerdo por clase (acuerdo específico positivo: 2·n_ii / (fila_i + columna_i))
    mat = pd.crosstab(pd.Categorical(a1, categories=n1), pd.Categorical(a2, categories=n1), dropna=False)
    mat.index.name, mat.columns.name = "A1", "A2"
    diag = np.diag(mat.to_numpy())
    marg = mat.sum(axis=1).to_numpy() + mat.sum(axis=0).to_numpy()
    por_clase = pd.DataFrame({"categoria_n1": n1, "n_A1": mat.sum(axis=1).to_numpy(), "n_A2": mat.sum(axis=0).to_numpy(),
                              "acuerdo_especifico": np.where(marg > 0, 2 * diag / np.maximum(marg, 1), np.nan)})
    por_clase = por_clase[(por_clase.n_A1 + por_clase.n_A2) > 0]
    por_estrato = (comun.assign(acuerdo=comun["categoria_n1_A1"].eq(comun["categoria_n1_A2"]))
                   .groupby("estrato_muestreo")["acuerdo"].agg(n="size", pct_acuerdo="mean").reset_index())

    # Salidas
    salida.mkdir(parents=True, exist_ok=True)
    mat.to_csv(salida / "matriz_confusion_A1xA2.csv", lineterminator="\n")
    desac = comun[comun["categoria_n1_A1"].ne(comun["categoria_n1_A2"])].copy()
    cols_adj = ["item_id", "caso_convencion", "cuenta_tipo", "signo", "monto", "descripcion",
                "categoria_n1_A1", "categoria_n2_A1", "duda_A1", "notas_A1",
                "categoria_n1_A2", "categoria_n2_A2", "duda_A2", "notas_A2"]
    adj = desac[cols_adj].sort_values("item_id").copy()
    for c in ("categoria_n1_final", "categoria_n2_final", "causa", "comentario"):
        adj[c] = ""
    ruta_adj = salida / "adjudicacion.xlsx"
    if ruta_adj.exists():
        print(f"AVISO: {rel(ruta_adj)} ya existe y NO se sobrescribe (podría tener adjudicaciones). "
              "Se escribe adjudicacion_nuevo.xlsx para comparar.")
        ruta_adj = salida / "adjudicacion_nuevo.xlsx"
    adj.to_csv(ruta_adj.with_suffix(".csv"), index=False, lineterminator="\n")
    escribir_adjudicacion_xlsx(adj, ruta_adj, n1, n2_todos)
    if len(sola):
        sola[["item_id", "categoria_n1_A1", "categoria_n1_A2"]].to_csv(salida / "una_sola_anotacion.csv",
                                                                         index=False, lineterminator="\n")
    if incons:
        pd.DataFrame(incons).to_csv(salida / "inconsistencias_n2.csv", index=False, lineterminator="\n")
    cols_corr = ["item_id", "etiqueta_A1", "etiqueta_A2", "etiqueta_convencion", "caso", "regla_citada", "cambia"]
    pd.DataFrame(corr, columns=cols_corr).sort_values("item_id").to_csv(
        salida / "correcciones_convencion.csv", index=False, lineterminator="\n")

    mat_nz = mat.loc[mat.sum(axis=1) > 0, mat.sum(axis=0) > 0]
    L = [f"# Acuerdo entre anotadores — WP4 (`tools/acuerdo_wp4.py`)\n",
         f"- Clave: `{rel(a.clave)}` ({len(clave)} ítems) · SHA-256 `{sha256_archivo(a.clave)}`",
         f"- Lote A1: `{rel(a.a1)}` · SHA-256 `{sha256_archivo(a.a1)}`",
         f"- Lote A2: `{rel(a.a2)}` · SHA-256 `{sha256_archivo(a.a2)}`",
         f"- Taxonomía v{VERSION_TAXONOMIA} · semilla {SEMILLA} · {N_BOOT} réplicas · numpy {np.__version__} · "
         f"pandas {pd.__version__}\n",
         "## Cobertura\n",
         f"- Doble anotación: **{len(comun)}** · solo A1: {int((hecho1 & ~hecho2).sum())} · solo A2: "
         f"{int((~hecho1 & hecho2).sum())} · sin anotar: {ninguna}",
         f"- Mínimo pre-registrado en común: {MIN_COMUN}." +
         (" **Hay ítems con una sola anotación: reportar la F1-macro también solo sobre los de doble anotación "
          "(pre-registro §4.5).**" if len(sola) else ""),
         "\n## κ de Cohen sobre `categoria_n1`\n",
         f"- **κ = {k:.3f}** (IC95 bootstrap estratificado: {ic[0]:.3f} – {ic[1]:.3f}) · {landis_koch(k)} "
         f"(Landis & Koch) · meta de la guía κ ≥ 0,61: **{'cumple' if k >= 0.61 else 'NO cumple'}**",
         f"- Acuerdo bruto p_o = {po:.3f} · acuerdo esperado por azar p_e = {pe:.3f}"
         + (f" · réplicas con κ indefinido: {nulos}" if nulos else ""),
         "- El κ usa las anotaciones **originales**: mide acuerdo **sin calibración ni convenciones previas** "
         "(pre-registro v1.4, §13). Las convenciones solo corrigen la etiqueta final.",
         "- κ sin los ítems de los 4 casos (dato descriptivo):",
         *[f"  - {nom}: κ = {v[0]:.3f} sobre {v[2]} ítems ({v[1]} excluidos)"
           + (" · patrón definido después de anotar" if "v1.4" in nom else "") for nom, v in k_sin_var.items()],
         f"- Ítems de los 4 casos (v1.4) en común: {comun['caso_convencion'].replace('', np.nan).value_counts().to_dict()}",
         f"- Correcciones por convención en ítems acordados: **{len(corr)}** "
         f"({sum(c['cambia'] == 'categoria_n1' for c in corr)} cambian `categoria_n1`) → `correcciones_convencion.csv`",
         "- Reversos sin regla automática (decidir y agregar a la hoja 07 antes de consolidar): "
         + (", ".join(sin_regla) or "ninguno"),
         "- Desacuerdos de los 4 casos (la adjudicación debe asignar la etiqueta de la convención): "
         + (", ".join(f"{c['item_id']} → {c['etiqueta_convencion']}" for c in conv_desac) or "ninguno"),
         f"- Desacuerdos para adjudicar: **{len(adj)}** → `{rel(ruta_adj)}`",
         f"- Inconsistencias `categoria_n2` ∉ `categoria_n1`: {len(incons)}"
         + (" → `inconsistencias_n2.csv` (no afectan al κ; corregir en la adjudicación)" if incons else ""),
         "\n## Matriz de confusión A1 (filas) × A2 (columnas), solo categorías usadas\n",
         tabla_md(mat_nz.reset_index().rename(columns={"index": "A1"})),
         "\n## Acuerdo específico por categoría\n",
         tabla_md(por_clase.assign(acuerdo_especifico=por_clase.acuerdo_especifico.round(3))),
         "\n## Acuerdo por estrato de muestreo (heurístico, no es etiqueta)\n",
         tabla_md(por_estrato.assign(pct_acuerdo=por_estrato.pct_acuerdo.round(3))),
         "\n> Con clases desbalanceadas, κ puede ser bajo con acuerdo bruto alto (paradoja de prevalencia): leer κ, "
         "p_o y la matriz juntos (guía v1.0 §6.4)."]
    (salida / "_reporte_acuerdo.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"κ = {k:.3f} [{ic[0]:.3f}, {ic[1]:.3f}] sobre {len(comun)} ítems · desacuerdos {len(adj)} · "
          f"reporte en {rel(salida / '_reporte_acuerdo.md')}")


if __name__ == "__main__":
    main()
