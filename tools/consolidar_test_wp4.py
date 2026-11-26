#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WP4 — Etiqueta final (acuerdo + adjudicación) → archivo de test real para WP8 (`etapa4_tstr.py --test`).

Pre-registro: docs/datos_reales/05_prerregistro_muestreo_anotacion.md (v1.4), §7, §12 y §13.

Lee     : la clave del test (--clave), lote_A1.xlsx, lote_A2.xlsx y la adjudicación escrita por tools/acuerdo_wp4.py.
Escribe : data/reales_anon/test_real_wp4_<AAAAMMDD>[_planb].csv  y su ficha _test_real_wp4_<AAAAMMDD>[_planb].md

Uso (desde la raíz del repo):
  python tools/consolidar_test_wp4.py                       # test de 200
  python tools/consolidar_test_wp4.py --clave data/reales_anon/anotacion/muestra_test_clave_planb.csv   # plan B
  python tools/consolidar_test_wp4.py --fecha 20261126 --verificar   # recalcula y compara con el archivo existente;
                                                                     # no escribe nada

Etiqueta final de categoria_n1, por ítem:
  * acuerdo       A1 = A2
  * adjudicacion  A1 ≠ A2 → categoria_n1_final de adjudicacion.xlsx (obligatoria, con causa)
  * solo_A1 / solo_A2  un solo anotador (pre-registro §12); doble_anotacion = "no"
  * acuerdo+convencion  A1 = A2, pero la etiqueta acordada difiere de la convención de su caso (v1.4 §13.3): se usa
                        la de `correcciones_convencion.csv` (lo escribe tools/acuerdo_wp4.py). Los lotes no se tocan.
  Un ítem sin ninguna anotación, o un desacuerdo sin adjudicar, detiene el script. Al final se exige que TODOS los
  ítems de los 4 casos (convenciones v1.4 de acuerdo_wp4.py) lleven la etiqueta de su convención, también los
  adjudicados; si no, se detiene y lista cuáles.

Columnas: primero las 8 de COLUMNAS_WP4 de etapa4_tstr.py, en su orden; después las de análisis (ninguna es feature).
  `signo` se recodifica egreso → "-", ingreso → "+" (como el sintético). `monto` va tal cual (incluido 0): lo que se
  haga con monto 0 lo decide el serializador de WP8. `fuente_etiqueta = texto` y `canal_p2p = false` en todas las
  filas, por la regla R2 (ningún voluntario declaró propósito; pre-registro §6).
Al final se verifica el archivo con las funciones de WP8 (cargar_tabla, deflactar_test_a_2025, serializar).
"""

import argparse
import hashlib
import sys
from datetime import date
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))
import acuerdo_wp4 as ac  # noqa: E402  (mismos patrones de casos y validaciones que el κ)

COLUMNAS_WP4 = ["descripcion", "monto", "fecha", "signo", "cuenta_tipo", "categoria_n1", "fuente_etiqueta",
                "voluntario_id"]
EXTRA = ["item_id", "tx_id", "categoria_n2", "medio_pago", "formalidad_comercio", "canal_p2p", "peso_muestreo",
         "estrato_muestreo", "doble_anotacion", "origen_etiqueta", "caso_convencion", "subgrupo_reverso",
         "unica_por_descripcion"]
SIGNO = {"egreso": "-", "ingreso": "+"}


def sha(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def abs_(p):
    return p if p.is_absolute() else RAIZ / p


def leer_adjudicacion(ruta):
    if ruta.suffix.lower() == ".xlsx":
        d = pd.read_excel(ruta, sheet_name="adjudicacion", dtype=str)
    else:
        d = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    return d.fillna("").apply(lambda c: c.str.strip())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Archivo de test real para WP8 (WP4, tarea 5).")
    ap.add_argument("--clave", type=Path, default=None, help="por defecto: anotacion/muestra_test_clave.csv")
    ap.add_argument("--a1", type=Path, default=None, help="por defecto: anotacion/lote_A1.xlsx")
    ap.add_argument("--a2", type=Path, default=None, help="por defecto: anotacion/lote_A2.xlsx")
    ap.add_argument("--adjudicacion", type=Path, default=None,
                    help="por defecto: anotacion/acuerdo_<clave>/adjudicacion.xlsx")
    ap.add_argument("--correcciones", type=Path, default=None,
                    help="por defecto: anotacion/acuerdo_<clave>/correcciones_convencion.csv")
    ap.add_argument("--fecha", default=date.today().strftime("%Y%m%d"), help="AAAAMMDD para el nombre del archivo")
    ap.add_argument("--verificar", action="store_true",
                    help="recalcula el test y lo compara byte a byte (SHA-256) con el archivo existente; no escribe")
    a = ap.parse_args(argv)
    anot = RAIZ / "data" / "reales_anon" / "anotacion"          # en tiempo de ejecución (monkeypatch de RAIZ)
    a.clave = abs_(a.clave or anot / "muestra_test_clave.csv")
    a.a1 = abs_(a.a1 or anot / "lote_A1.xlsx")
    a.a2 = abs_(a.a2 or anot / "lote_A2.xlsx")
    adj_ruta = abs_(a.adjudicacion) if a.adjudicacion else anot / f"acuerdo_{a.clave.stem}" / "adjudicacion.xlsx"
    corr_ruta = abs_(a.correcciones) if a.correcciones else anot / f"acuerdo_{a.clave.stem}" / "correcciones_convencion.csv"
    planb = a.clave.stem.endswith("_planb")
    nombre = f"test_real_wp4_{a.fecha}{'_planb' if planb else ''}"
    salida = RAIZ / "data" / "reales_anon" / f"{nombre}.csv"
    if a.verificar and not salida.exists():
        sys.exit(f"--verificar: no existe {ac.rel(salida)} para comparar.")
    if salida.exists() and not a.verificar:
        sys.exit(f"Ya existe {ac.rel(salida)}: no se sobrescribe. Usa otra --fecha, --verificar, o bórralo a mano.")

    n1, n2 = ac.taxonomia()
    clave = pd.read_csv(a.clave, dtype=str, keep_default_na=False)
    l1, l2 = ac.leer_lote(a.a1, "A1"), ac.leer_lote(a.a2, "A2")
    extra_a1 = pd.read_excel(a.a1, sheet_name="anotacion", dtype=str) if a.a1.suffix == ".xlsx" \
        else pd.read_csv(a.a1, dtype=str, keep_default_na=False)
    extra_a1 = extra_a1.fillna("")[["item_id", "medio_pago", "formalidad_comercio"]].apply(lambda c: c.str.strip())
    m = clave.merge(l1, on="item_id", how="left").merge(l2, on="item_id", how="left") \
             .merge(extra_a1, on="item_id", how="left").fillna("")

    errores = []
    for an in ("A1", "A2"):
        malos = m.loc[m[f"categoria_n1_{an}"].ne("") & ~m[f"categoria_n1_{an}"].isin(n1), "item_id"]
        errores += [f"{an} {i}: categoria_n1 fuera de la taxonomía" for i in malos]
    tax = __import__("json").loads(ac.ruta_taxonomia().read_text(encoding="utf-8"))
    mp = {v["id"] for v in tax["dimension_medio_pago"]["valores"]}
    fc = {v["id"] for v in tax["dimension_formalidad_comercio"]["valores"]}
    errores += [f"A1 {i}: medio_pago '{v}'" for i, v in zip(m.item_id, m.medio_pago) if v and v not in mp]
    errores += [f"A1 {i}: formalidad_comercio '{v}'" for i, v in zip(m.item_id, m.formalidad_comercio) if v and v not in fc]
    errores += [f"{i}: signo '{v}'" for i, v in zip(m.item_id, m.signo) if v not in SIGNO]

    h1, h2 = m["categoria_n1_A1"].ne(""), m["categoria_n1_A2"].ne("")
    if (~h1 & ~h2).any():
        errores.append(f"{int((~h1 & ~h2).sum())} ítems sin ninguna anotación: "
                       f"{', '.join(m.loc[~h1 & ~h2, 'item_id'].head(10))}")
    desac = h1 & h2 & m["categoria_n1_A1"].ne(m["categoria_n1_A2"])
    adj = pd.DataFrame(columns=["item_id", "categoria_n1_final", "categoria_n2_final", "causa"])
    if desac.any():
        if not adj_ruta.exists():
            sys.exit(f"Hay {int(desac.sum())} desacuerdos y no existe {ac.rel(adj_ruta)}. Corre antes acuerdo_wp4.py.")
        adj = leer_adjudicacion(adj_ruta)
        ids_desac, ids_adj = set(m.loc[desac, "item_id"]), set(adj["item_id"])
        if ids_desac != ids_adj:
            errores.append(f"La adjudicación no corresponde a los lotes actuales (¿se editó un lote después de "
                           f"acuerdo_wp4.py?): faltan {sorted(ids_desac - ids_adj)[:10]}, sobran {sorted(ids_adj - ids_desac)[:10]}")
        for r in adj.itertuples(index=False):
            if r.categoria_n1_final not in n1:
                errores.append(f"adjudicación {r.item_id}: categoria_n1_final '{r.categoria_n1_final}' vacía o inválida")
            if r.causa not in ac.CAUSAS:
                errores.append(f"adjudicación {r.item_id}: causa '{r.causa}' vacía o inválida")
            if r.categoria_n2_final and r.categoria_n2_final not in n2.get(r.categoria_n1_final, set()):
                errores.append(f"adjudicación {r.item_id}: categoria_n2_final '{r.categoria_n2_final}' "
                               f"no pertenece a '{r.categoria_n1_final}'")
    if errores:
        sys.exit("No se escribe el test:\n  " + "\n  ".join(errores[:40])
                 + (f"\n  … y {len(errores) - 40} más" if len(errores) > 40 else ""))

    adj_i = adj.set_index("item_id")
    final_n1, final_n2, origen = [], [], []
    for r in m.itertuples(index=False):
        c1, c2 = r.categoria_n1_A1, r.categoria_n1_A2
        if c1 and c2 and c1 == c2:
            f1, o = c1, "acuerdo"
            cand = [r.categoria_n2_A1, r.categoria_n2_A2]
        elif c1 and c2:
            f1, o = adj_i.at[r.item_id, "categoria_n1_final"], "adjudicacion"
            cand = [adj_i.at[r.item_id, "categoria_n2_final"]]
        elif c1:
            f1, o, cand = c1, "solo_A1", [r.categoria_n2_A1]
        else:
            f1, o, cand = c2, "solo_A2", [r.categoria_n2_A2]
        # categoria_n2: la primera candidata válida para la etiqueta final (A1 primero); si ninguna lo es, vacía.
        f2 = next((c for c in cand if c and c in n2.get(f1, set())), "")
        final_n1.append(f1)
        final_n2.append(f2)
        origen.append(o)

    # Correcciones por convención en ítems acordados (v1.4 §13.3)
    pos = {i: k for k, i in enumerate(m["item_id"])}
    corr = pd.read_csv(corr_ruta, dtype=str, keep_default_na=False) if corr_ruta.exists() else pd.DataFrame()
    err_corr = []
    for r in corr.itertuples(index=False):
        if r.item_id not in pos:
            err_corr.append(f"{r.item_id}: no está en la clave")
            continue
        k = pos[r.item_id]
        fila = m.iloc[k]
        e1 = f"{fila.categoria_n1_A1}.{fila.categoria_n2_A1}" if fila.categoria_n2_A1 else fila.categoria_n1_A1
        e2 = f"{fila.categoria_n1_A2}.{fila.categoria_n2_A2}" if fila.categoria_n2_A2 else fila.categoria_n1_A2
        if origen[k] != "acuerdo" or (e1, e2) != (r.etiqueta_A1, r.etiqueta_A2):
            err_corr.append(f"{r.item_id}: la corrección no corresponde a los lotes actuales (¿se editó un lote?)")
            continue
        c1, _, c2 = r.etiqueta_convencion.partition(".")
        if c1 not in n1 or (c2 and c2 not in n2.get(c1, set())):
            err_corr.append(f"{r.item_id}: etiqueta_convencion '{r.etiqueta_convencion}' fuera de la taxonomía")
            continue
        final_n1[k], final_n2[k], origen[k] = c1, c2, "acuerdo+convencion"
    if err_corr:
        sys.exit("Correcciones por convención inválidas:\n  " + "\n  ".join(err_corr))

    # Todos los ítems de los 4 casos deben llevar la etiqueta de su convención (también los adjudicados)
    fuera = []
    for k, r in enumerate(m.itertuples(index=False)):
        cv = ac.convencion(r.descripcion, r.cuenta_tipo)
        if cv and cv["categoria_n1"] is None:
            fuera.append(f"{r.item_id} [{cv['caso']}] {cv['regla']}")
        elif cv and (final_n1[k], final_n2[k]) != (cv["categoria_n1"], cv["categoria_n2"]):
            fuera.append(f"{r.item_id} [{cv['caso']}] final {final_n1[k]}.{final_n2[k] or '∅'} ≠ convención "
                         f"{cv['categoria_n1']}.{cv['categoria_n2']} (origen: {origen[k]})")
    if fuera:
        sys.exit("Ítems de los 4 casos que no siguen su convención (v1.4 §13.3). Corrige la adjudicación, o vuelve a "
                 f"correr acuerdo_wp4.py si faltan correcciones ({ac.rel(corr_ruta)}):\n  " + "\n  ".join(fuera))

    caso = [ac.caso_convencion(d, c) for d, c in zip(m["descripcion"], m["cuenta_tipo"])]
    unica = ~m.sort_values("item_id")["descriptor_norm"].duplicated()
    out = pd.DataFrame({
        "descripcion": m["descripcion"],
        "monto": pd.to_numeric(m["monto"], errors="raise").astype("int64"),   # sin tocar (incluido 0)
        "fecha": m["fecha"],
        "signo": m["signo"].map(SIGNO),
        "cuenta_tipo": m["cuenta_tipo"],
        "categoria_n1": final_n1,
        "fuente_etiqueta": "texto",                    # R2: sin propósito declarado en ninguna fila
        "voluntario_id": m["seudonimo"],               # grupo de extractos, no necesariamente un titular
        "item_id": m["item_id"],
        "tx_id": m["tx_id"],
        "categoria_n2": final_n2,
        "medio_pago": m["medio_pago"],
        "formalidad_comercio": m["formalidad_comercio"],
        "canal_p2p": "false",                          # R2: solo true con propósito declarado
        "peso_muestreo": pd.to_numeric(m["peso_muestreo"]),
        "estrato_muestreo": m["estrato_muestreo"],
        "doble_anotacion": ["si" if o in ("acuerdo", "adjudicacion", "acuerdo+convencion") else "no" for o in origen],
        "origen_etiqueta": origen,
        "caso_convencion": caso,
        "subgrupo_reverso": ["si" if c == "reverso_devolucion" else "no" for c in caso],
        "unica_por_descripcion": ["si" if u else "no" for u in unica.reindex(m.index).to_numpy()],
    })[COLUMNAS_WP4 + EXTRA].sort_values("item_id", kind="mergesort").reset_index(drop=True)
    assert out["subgrupo_reverso"].eq("si").sum() == m["estrato_muestreo"].eq("reverso_devolucion").sum()

    contenido = out.to_csv(index=False, lineterminator="\n").encode("utf-8")
    if a.verificar:
        nuevo, existente = hashlib.sha256(contenido).hexdigest(), sha(salida)
        igual = nuevo == existente
        print(f"--verificar {ac.rel(salida)}: {'IDÉNTICO' if igual else 'DIFERENTE'} · existente {existente} · "
              f"recalculado {nuevo} · no se escribió nada")
        if not igual:
            import io
            viejo = pd.read_csv(salida, dtype=str, keep_default_na=False)
            nuevo_df = pd.read_csv(io.BytesIO(contenido), dtype=str, keep_default_na=False)
            if list(viejo.columns) != list(nuevo_df.columns) or len(viejo) != len(nuevo_df):
                print(f"  columnas o filas distintas: {list(viejo.columns)} / {len(viejo)} filas → "
                      f"{list(nuevo_df.columns)} / {len(nuevo_df)} filas")
            else:
                v, n_ = viejo.set_index("item_id"), nuevo_df.set_index("item_id")
                for c in v.columns:          # solo columna, item_id y valores de columnas no textuales
                    dif = v.index[v[c].ne(n_.loc[v.index, c])]
                    if len(dif):
                        muestra = "" if c == "descripcion" else " · " + ", ".join(
                            f"{i}: {v.at[i, c]!r}→{n_.at[i, c]!r}" for i in dif[:10])
                        print(f"  {c}: {len(dif)} celdas ({', '.join(dif[:10])}{' …' if len(dif) > 10 else ''}){muestra}")
        sys.exit(0 if igual else 1)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes(contenido)

    # Verificación con el código de WP8: mismo cargador, deflactor y serializador que usará --test.
    import etapa4_tstr as wp8
    clases, _ = wp8.cargar_taxonomia()
    t = wp8.cargar_tabla(salida.relative_to(RAIZ), clases, "test")
    faltan = [c for c in wp8.COLUMNAS_WP4 if c not in t.columns]
    td, meta = wp8.deflactar_test_a_2025(t)
    ser = wp8.serializar(td)
    signos = set(ser.str.extract(r"\[SIGNO=([^\]]*)\]")[0])
    cuentas = set(ser.str.extract(r"\[CUENTA=([^\]]*)\]")[0])
    problemas = []
    if len(t) != len(out):
        problemas.append(f"WP8 cargó {len(t)} de {len(out)} filas")
    if faltan:
        problemas.append(f"faltan columnas WP4 {faltan}")
    if not meta.get("deflactado"):
        problemas.append("no se deflactó")
    if not signos <= {"+", "-"}:
        problemas.append(f"tokens SIGNO {signos}")
    if not cuentas <= {"banco", "billetera", "tarjeta_credito"}:
        problemas.append(f"tokens CUENTA {cuentas}")
    if problemas:
        salida.rename(salida.with_suffix(".csv.INVALIDO"))
        sys.exit("El archivo NO pasa la verificación de WP8 (renombrado a .INVALIDO): " + "; ".join(problemas))

    w = out["peso_muestreo"]
    dist = pd.DataFrame({"n": out["categoria_n1"].value_counts(),
                         "pct_sin_ponderar": out["categoria_n1"].value_counts(normalize=True).round(3),
                         "pct_ponderado": (w.groupby(out["categoria_n1"]).sum() / w.sum()).round(3)}) \
        .fillna(0).sort_values("n", ascending=False)
    L = [f"# {nombre}\n",
         f"- Archivo: `{ac.rel(salida)}` · SHA-256 `{sha(salida)}` · {len(out)} filas",
         f"- Clave: `{ac.rel(a.clave)}` · SHA-256 `{sha(a.clave)}`",
         f"- Lote A1 SHA-256 `{sha(a.a1)}` · Lote A2 SHA-256 `{sha(a.a2)}`",
         f"- Adjudicación: " + (f"`{ac.rel(adj_ruta)}` · SHA-256 `{sha(adj_ruta)}`" if desac.any() else "no hubo desacuerdos"),
         f"- Correcciones por convención: " + (f"`{ac.rel(corr_ruta)}` · {len(corr)} filas · SHA-256 `{sha(corr_ruta)}`"
                                               if corr_ruta.exists() else "no hay archivo"),
         f"- Taxonomía v{ac.VERSION_TAXONOMIA} · pre-registro 05 v1.4\n",
         "## Verificación con `etapa4_tstr.py`\n",
         f"- `cargar_tabla`: {len(t)} filas, columnas WP4 completas · `deflactar_test_a_2025`: factor "
         f"{meta['factor_min']:.4f}–{meta['factor_max']:.4f} · tokens SIGNO {sorted(signos)} · CUENTA {sorted(cuentas)}",
         f"- Comando: `python tools/etapa4_tstr.py --test {ac.rel(salida)}`",
         "- IC principal (D-M7): bootstrap por fila, estratificado por `estrato_muestreo`. El bootstrap por grupo de "
         "extractos (`voluntario_id`) es solo una sensibilidad. Secundaria (D-M6): exactitud ponderada con "
         "`peso_muestreo`.\n",
         "## Origen de la etiqueta\n",
         f"{out['origen_etiqueta'].value_counts().to_dict()} · doble anotación: "
         f"{int(out['doble_anotacion'].eq('si').sum())}/{len(out)}",
         "\n## Subgrupos y sensibilidades pre-registradas (columnas)\n",
         f"- `caso_convencion`: {out['caso_convencion'].replace('', 'ninguno').value_counts().to_dict()}",
         f"- `subgrupo_reverso = si`: {int(out['subgrupo_reverso'].eq('si').sum())} (se reporta aparte)",
         f"- `unica_por_descripcion = si`: {int(out['unica_por_descripcion'].eq('si').sum())} (sensibilidad §4.3)",
         f"- `doble_anotacion = no`: {int(out['doble_anotacion'].eq('no').sum())} (si > 0, sensibilidad §4.5)",
         f"- Σ `peso_muestreo` = {w.sum():.1f} · monto 0: {int(out['monto'].eq(0).sum())} filas (sin modificar)",
         f"- A1 sin `medio_pago`: {int(out['medio_pago'].eq('').sum())} · sin `formalidad_comercio`: "
         f"{int(out['formalidad_comercio'].eq('').sum())} (no afectan a WP8; la guía los pide a A1)",
         "\n## Distribución de `categoria_n1`\n", ac.tabla_md(dist.reset_index().rename(columns={"index": "categoria_n1"})),
         "\n> Categorías con soporte < 10 se fusionan en `otros` en WP8 (regla de soporte)."]
    (salida.parent / f"_{nombre}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Escrito {ac.rel(salida)} ({len(out)} filas) · verificado con etapa4_tstr.py · ficha _{nombre}.md")


if __name__ == "__main__":
    main()
