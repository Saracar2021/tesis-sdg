"""Swap a WP4 de punta a punta, con datos SIMULADOS (nunca el real; nada se escribe en data/ ni en outputs/tstr/).

1. Real simulado mínimo (tests/fixtures/real_simulado_wp4.csv: 30 filas ficticias, solo las 8 columnas de WP4):
   ruta de respaldo sin estratos ni pesos (IC por fila simple + sensibilidad por grupo).
2. Salida de tools/consolidar_test_wp4.py sobre insumos simulados (clave, lotes A1/A2 con desacuerdos y ítems de un
   solo anotador, adjudicación, reversos y correcciones por convención): esquema del pre-registro 05 v1.4 §7 y §13.
   Los insumos siguen las convenciones v1.4 de tools/acuerdo_wp4.py; los 3 reversos llegan acordados con una etiqueta
   distinta de la convención y se corrigen con un archivo de correcciones simulado (--correcciones). Verifica el diseño D-M6/D-M7:
   IC principal por fila estratificado, sensibilidad por grupo, exactitud ponderada (Hájek) y recorte P95,
   sensibilidades (a)-(d), corte texto/declaración no informativo y Δ pareado CTGAN − reglas.
Entrena un LogReg pequeño (3.000 filas) para que la prueba sea rápida.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import etapa4_tstr as base  # noqa: E402

REAL_SIMULADO = Path("tests/fixtures/real_simulado_wp4.csv")
requiere_sinteticos = pytest.mark.skipif(
    not all((RAIZ / base.FUENTES[f]).exists() for f in ("reglas", "ctgan")),
    reason="faltan los sintéticos con texto (correr tools/etapa3b_texto.py)")


@pytest.fixture
def salidas_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "SALIDA", tmp_path / "tstr")              # métricas: nunca en outputs/tstr/
    monkeypatch.setattr(base, "PRIVADO_TSTR", tmp_path / "privado")     # predicciones por ítem: nunca en data/
    return tmp_path


def _correr_dos_fuentes(tmp_path, ruta_test):
    clases, sha_tax = base.cargar_taxonomia()
    corridas = {}
    for fuente in ("reglas", "ctgan"):
        chico = tmp_path / f"train_{fuente}.csv"
        if not chico.exists():
            base.submuestra(pd.read_csv(RAIZ / base.FUENTES[fuente]), 3000).to_csv(chico, index=False)
        corridas[("tstr", fuente, "logreg")] = base.correr(fuente, chico, ruta_test, clases, sha_tax)
    return clases, corridas


# --------------------------------------------------------------------------- unidades del diseño
def test_bootstrap_estratificado_conserva_tamano_de_cada_estrato():
    est = np.array(["a"] * 5 + ["b"] * 3 + ["c"] * 2)
    for idx in base._indices_bootstrap(10, None, 20, 42, estratos=est):
        assert sorted(pd.Series(est[idx]).value_counts().to_dict().items()) == [("a", 5), ("b", 3), ("c", 2)]


def test_exactitud_ponderada_hajek_y_kish():
    y, p = np.array(["x", "x", "y", "y"]), np.array(["x", "y", "y", "y"])
    assert base.exactitud_ponderada(y, p, [1, 1, 1, 1]) == 0.75
    assert base.exactitud_ponderada(y, p, [1, 9, 1, 1]) == pytest.approx(3 / 12)
    assert base.n_efectivo_kish([1, 1, 1, 1]) == 4 and base.n_efectivo_kish([1, 9, 1, 1]) < 2


def test_columnas_de_analisis_no_entran_a_la_serializacion():
    t = pd.read_csv(RAIZ / REAL_SIMULADO)
    t2 = t.assign(peso_muestreo=999.0, estrato_muestreo="x", item_id="T999", doble_anotacion="no")
    assert base.serializar(t).equals(base.serializar(t2))


def test_monto_cero_va_al_bin_mas_bajo():
    """El marco real trae filas con monto 0: deben caer en el bin más bajo ('<1K', visto en el entrenamiento), nunca
    en -inf ni en un token inválido. bin_monto no usa log10: ubica |monto| con searchsorted sobre los bordes."""
    assert list(base.bin_monto([0, 0.0, -0.0, "0", 999.99, 1000])) == ["<1K"] * 5 + ["1K-3K"]
    t = pd.DataFrame({"cuenta_tipo": ["banco"], "signo": ["-"], "monto": [0], "descripcion": ["CUOTA MANEJO"],
                      "fecha": ["2026-09-30"]})
    d, meta = base.deflactar_test_a_2025(t)
    assert meta["deflactado"] and d["monto"].iloc[0] == 0
    assert base.serializar(d).iloc[0] == "[CUENTA=banco] [SIGNO=-] [MONTO=<1K] CUOTA MANEJO"


def test_ipc_cubre_la_ventana_del_test_real():
    """Ventana del pre-registro 05: dic-2025 a sep-2026. Ningún mes sin IPC (si faltara, deflactar aborta)."""
    meses = pd.date_range("2025-12-01", "2026-09-01", freq="MS").strftime("%Y-%m-15")
    t = pd.DataFrame({"monto": [100000] * len(meses), "fecha": meses})
    _, meta = base.deflactar_test_a_2025(t)
    assert meta["deflactado"] and 0.9 < meta["factor_min"] <= meta["factor_max"] < 1.0


def test_columnas_de_analisis_no_entran_a_la_serializacion():
    t = pd.read_csv(RAIZ / REAL_SIMULADO)
    t2 = t.assign(peso_muestreo=999.0, estrato_muestreo="x", item_id="T999", doble_anotacion="no")
    assert base.serializar(t).equals(base.serializar(t2))


# --------------------------------------------------------------------------- 1. real simulado mínimo
def test_fixture_cumple_esquema_wp4():
    t = pd.read_csv(RAIZ / REAL_SIMULADO)
    assert list(t.columns) == base.COLUMNAS_WP4 and len(t) == 30
    clases, _ = base.cargar_taxonomia()
    assert set(t[base.TARGET]) <= set(clases)


def test_deflacion_mueve_bins_en_el_borde():
    t = pd.read_csv(RAIZ / REAL_SIMULADO)
    d, meta = base.deflactar_test_a_2025(t)
    assert meta["deflactado"] and abs(meta["factor_min"] - 0.9361) < 1e-3 and abs(meta["factor_max"] - 0.9862) < 1e-3
    antes, despues = base.serializar(t), base.serializar(d)
    assert "[MONTO=10K-30K]" in antes[0] and "[MONTO=3K-10K]" in despues[0]
    assert "[MONTO=100K-300K]" in antes[10] and "[MONTO=30K-100K]" in despues[10]
    assert "[MONTO=1M-3M]" in antes[7] and "[MONTO=300K-1M]" in despues[7]


@requiere_sinteticos
def test_swap_real_simulado_minimo(salidas_temporales):
    clases, corridas = _correr_dos_fuentes(salidas_temporales, REAL_SIMULADO)
    m = corridas[("tstr", "reglas", "logreg")]
    assert m["modo"] == "tstr" and m["reportable"] and m["n_test"] == 30 and m["contrato_wp4_faltan"] == []
    assert m["entrada"]["deflactor_test"]["deflactado"] is True
    assert set(m["clases_fusionadas_a_otros"]) >= {"comidas_fuera", "ingreso", "retiro_efectivo"}
    assert m["clases_evaluadas"] == 3
    assert m["ic_principal"] == "fila"                       # sin estrato_muestreo: fila simple (con aviso)
    assert m["ic95_conglomerado"] is not None and m["bootstrap"]["sensibilidad"] == "conglomerado:voluntario_id"
    assert "exactitud_ponderada" not in m                    # sin peso_muestreo
    st = m["solo_etiqueta_por_texto"]
    assert st["n_test"] == 27 and "alimentos_mercado" in st["clases_fusionadas_a_otros"]
    assert m["sensibilidades"]["a_unica_por_descripcion"]["aplica"] is False
    rp = base.ruta_predicciones("tstr", "reglas", "logreg")
    assert rp.is_relative_to(salidas_temporales / "privado") and rp.exists()
    filas = base._ablacion("tstr", corridas, clases)
    assert len(filas) == 1 and filas[0].startswith("| Baseline")


# --------------------------------------------------------------------------- 2. consolidador WP4 sobre simulados
def _insumos_simulados(d: Path) -> dict:
    """Clave + lotes + adjudicación con el formato de tools/muestreo_wp4.py y tools/acuerdo_wp4.py (ficticios)."""
    rng = np.random.default_rng(7)
    sint = pd.read_csv(RAIZ / base.FUENTES["reglas"])
    por_clase = {"alimentos_mercado": 14, "transferencias_p2p": 14, "movimiento_propio": 12, "comidas_fuera": 12,
                 "ingreso": 5, "retiro_efectivo": 5, "transporte": 4}
    filas = []
    for c, k in por_clase.items():
        s = sint[sint[base.TARGET] == c].sample(k, random_state=1)
        filas.append(s.assign(estrato_muestreo=np.where(rng.random(k) < 0.8, c, "sin_heuristica")))
    t = pd.concat(filas, ignore_index=True)
    t.loc[t.index[:4], "descripcion"] = t.loc[t.index[4], "descripcion"]          # descripciones repetidas
    # Reversos con las formas que la hoja 07 resuelve: dos a otros.ininteligible y uno (RAPPI) a comidas_fuera.
    rev = pd.DataFrame({"descripcion": ["DEVOLUCION", "REVERSADA - FALABELLA COM S A S", "ANUL. CONSUMO NACI RAPPI APP"],
                        "monto": [52000, 89000, 15000], "signo": ["+"] * 3, "cuenta_tipo": ["tarjeta_credito"] * 3,
                        base.TARGET: ["otros"] * 3, "categoria_n2": [""] * 3, "estrato_muestreo": ["reverso_devolucion"] * 3})
    t = pd.concat([t, rev], ignore_index=True)
    t["categoria_n2"] = t["categoria_n2"].fillna("")
    # Convenciones v1.4: toda fila sintética que caiga en un caso lleva ya la etiqueta de la convención.
    import acuerdo_wp4
    es_rev = t.index >= len(t) - len(rev)
    for i, r in t.iterrows():
        cv = acuerdo_wp4.convencion(r["descripcion"], r["cuenta_tipo"])
        if cv is not None and not es_rev[i]:
            assert cv["categoria_n1"] is not None, f"sintético con reverso sin regla: {r['descripcion']}"
            t.loc[i, [base.TARGET, "categoria_n2"]] = [cv["categoria_n1"], cv["categoria_n2"]]
    n = len(t)
    meses = ["2025-12", "2026-02", "2026-05", "2026-07", "2026-09"]
    clave = pd.DataFrame({
        "item_id": [f"T{i:03d}" for i in range(1, n + 1)], "tx_id": [f"TX{i:05d}" for i in range(n)],
        "seudonimo": rng.choice(["V04", "V05", "V06", "V07", "V09", "V10"], n),
        "mes_referencia": rng.choice(meses, n), "descripcion": t["descripcion"], "monto": t["monto"].round().astype(int),
        "signo": t["signo"].map({"-": "egreso", "+": "ingreso"}), "cuenta_tipo": t["cuenta_tipo"],
        "estrato_muestreo": t["estrato_muestreo"], "descriptor_norm": t["descripcion"].str.upper().str.replace(r"[\d#]", "", regex=True)})
    clave["fecha"] = clave["mes_referencia"] + "-15"
    clave["peso_muestreo"] = np.round(np.where(rng.random(n) < 0.08, rng.uniform(80, 120, n), rng.uniform(2, 20, n)), 3)
    for c in ("N_d", "pi1", "pi2", "pi"):
        clave[c] = ""
    a1 = pd.DataFrame({"item_id": clave["item_id"], "categoria_n1": t[base.TARGET], "categoria_n2": t["categoria_n2"],
                       "duda": "", "notas": "", "medio_pago": "", "formalidad_comercio": ""})
    a2 = a1.copy()
    desac = [10, 20, 30, 40, 50, 60]
    a2.loc[desac, "categoria_n1"] = "otros"
    a2.loc[[5, 15, 25, 35, 45], ["categoria_n1", "categoria_n2"]] = ""          # ítems de un solo anotador
    adj = pd.DataFrame({"item_id": a1.loc[desac, "item_id"], "categoria_n1_final": a1.loc[desac, "categoria_n1"],
                        "categoria_n2_final": a1.loc[desac, "categoria_n2"], "causa": "error_anotador"})
    # Correcciones por convención (formato de tools/acuerdo_wp4.py): los 3 reversos, acordados como «otros» sin subtipo.
    filas_corr = []
    for i in np.flatnonzero(es_rev):
        cv = acuerdo_wp4.convencion(clave.at[i, "descripcion"], clave.at[i, "cuenta_tipo"])
        filas_corr.append({"item_id": clave.at[i, "item_id"], "etiqueta_A1": "otros", "etiqueta_A2": "otros",
                           "etiqueta_convencion": f"{cv['categoria_n1']}.{cv['categoria_n2']}", "caso": cv["caso"],
                           "regla_citada": cv["regla"],
                           "cambia": "categoria_n1" if cv["categoria_n1"] != "otros" else "solo categoria_n2"})
    corr = pd.DataFrame(filas_corr)
    rutas = {k: d / f"{k}.csv" for k in ("clave", "lote_A1", "lote_A2", "adjudicacion", "correcciones")}
    for k, df in zip(rutas, (clave, a1, a2, adj, corr)):
        df.to_csv(rutas[k], index=False)
    return rutas


@pytest.fixture
def consolidado(tmp_path, monkeypatch):
    """Corre el consolidador de WP4 con RAIZ temporal (taxonomía e IPC copiados): escribe en tmp, nunca en data/."""
    import acuerdo_wp4
    import consolidar_test_wp4 as cons
    raiz_tmp = tmp_path / "repo"
    for rel in (base.TAXONOMIA, base.IPC):
        (raiz_tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        (raiz_tmp / rel).write_bytes((RAIZ / rel).read_bytes())
    r = _insumos_simulados(tmp_path)
    monkeypatch.setattr(cons, "RAIZ", raiz_tmp)
    monkeypatch.setattr(acuerdo_wp4, "RAIZ", raiz_tmp)
    monkeypatch.setattr(base, "RAIZ", raiz_tmp)          # la verificación del consolidador usa las funciones de WP8
    cons.main(["--clave", str(r["clave"]), "--a1", str(r["lote_A1"]), "--a2", str(r["lote_A2"]),
               "--adjudicacion", str(r["adjudicacion"]), "--correcciones", str(r["correcciones"]),
               "--fecha", "SIMULADO"])
    monkeypatch.setattr(base, "RAIZ", RAIZ)
    salida = raiz_tmp / "data/reales_anon/test_real_wp4_SIMULADO.csv"
    assert salida.exists() and not (RAIZ / "data/reales_anon/test_real_wp4_SIMULADO.csv").exists()
    return salida


@requiere_sinteticos
def test_swap_salida_del_consolidador(consolidado, salidas_temporales):
    t = pd.read_csv(consolidado, keep_default_na=False)
    assert list(t.columns[:8]) == base.COLUMNAS_WP4 and set(base.COLUMNAS_ANALISIS_WP4) <= set(t.columns)
    assert (t["doble_anotacion"] == "no").sum() == 5 and (t["subgrupo_reverso"] == "si").sum() == 3
    assert (t["unica_por_descripcion"] == "no").sum() >= 4
    # Correcciones por convención (v1.4 §13.3): los 3 reversos, trazados en origen_etiqueta
    corr = t[t["origen_etiqueta"] == "acuerdo+convencion"]
    assert len(corr) == 3 and set(corr["caso_convencion"]) == {"reverso_devolucion"}
    assert sorted(corr["categoria_n1"] + "." + corr["categoria_n2"]) == [
        "comidas_fuera.domicilios_app", "otros.ininteligible", "otros.ininteligible"]

    clases, corridas = _correr_dos_fuentes(salidas_temporales, consolidado)
    m = corridas[("tstr", "reglas", "logreg")]
    assert m["n_test"] == len(t) and m["contrato_wp4_faltan"] == []
    # D-M7: principal por fila estratificado; sensibilidad por grupo de extractos (6)
    assert m["ic_principal"] == "fila_estratificado" and m["bootstrap"]["estratos"] == t["estrato_muestreo"].nunique()
    assert m["ic95_conglomerado"] is not None and m["n_grupos"] == t["voluntario_id"].nunique()
    lo, hi = m["ic95_bootstrap"]
    assert 0 <= lo <= m["f1_macro_regla_soporte"] <= hi <= 1
    # D-M6: exactitud ponderada (Hájek) con IC, Kish y recorte P95
    ew = m["exactitud_ponderada"]
    w = t["peso_muestreo"].astype(float).to_numpy()
    assert ew["n_efectivo_kish"] == pytest.approx(w.sum() ** 2 / (w ** 2).sum())
    assert ew["recorte_p95"]["p95"] == pytest.approx(np.percentile(w, 95))
    assert ew["recorte_p95"]["alerta_depende_de_pocos_descriptores"] == (abs(ew["recorte_p95"]["diferencia"]) > 0.05)
    # sensibilidades del §4
    s = m["sensibilidades"]
    assert s["a_unica_por_descripcion"]["n"] == (t["unica_por_descripcion"] == "si").sum()
    assert s["b_solo_doble_anotacion"]["n"] == (t["doble_anotacion"] == "si").sum()
    assert s["d_subgrupo_reverso"]["n"] == 3
    assert s["e_kappa_sin_casos_convencion"]["aplica"] is False
    assert m["solo_etiqueta_por_texto"]["aplica"] is False   # R2: todas las filas son etiqueta-por-texto
    prev = pd.read_csv(salidas_temporales / "tstr/tstr/reglas/logreg/prevalencias.csv")
    assert prev["pct_ponderado"].sum() == pytest.approx(1.0)
    # predicciones por ítem: ruta privada, sin texto
    p = pd.read_csv(base.ruta_predicciones("tstr", "reglas", "logreg"), keep_default_na=False)
    assert "descripcion" not in p.columns and set(p["estrato"]) == set(t["estrato_muestreo"])
    # Δ pareado: principal estratificado + sensibilidad por grupo
    filas = base._ablacion("tstr", corridas, clases)
    assert len(filas) == 1 and filas[0].count("[") == 2


@requiere_sinteticos
def test_nada_desagregado_por_grupo_en_outputs(consolidado, salidas_temporales, monkeypatch):
    """Ningún archivo bajo outputs/ (ni el .md) lleva métricas, prevalencias o matrices por grupo de extractos: ni
    columnas grupo/voluntario_id ni seudónimos de grupo. Lo desagregado por ítem/grupo va solo a data/_privado/tstr/."""
    monkeypatch.setattr(base, "RESULTADOS_MD", salidas_temporales / "resultados_tstr.md")
    clases, _ = _correr_dos_fuentes(salidas_temporales, consolidado)
    base.escribir_resultados_md(clases)
    seudonimos = set(pd.read_csv(consolidado, keep_default_na=False)["voluntario_id"])
    publicos = [p for p in (salidas_temporales / "tstr").rglob("*") if p.is_file()] + [salidas_temporales / "resultados_tstr.md"]
    assert publicos and (salidas_temporales / "tstr/tstr/ablacion.json").exists()
    for p in publicos:
        if p.suffix == ".csv" or p.name.endswith(".csv.gz"):
            cols = set(pd.read_csv(p, nrows=0).columns)
            assert not cols & {"grupo", "voluntario_id", "seudonimo"}, f"{p.name} trae columna de grupo"
        texto = pd.read_csv(p).to_csv() if p.name.endswith(".gz") else p.read_text(encoding="utf-8")
        for v in seudonimos:
            assert f'"{v}"' not in texto and f",{v}," not in texto and f" {v} " not in texto, f"{p.name} menciona {v}"
    privado = list((salidas_temporales / "privado").rglob("predicciones.csv.gz"))
    assert privado and "grupo" in pd.read_csv(privado[0], nrows=0).columns
