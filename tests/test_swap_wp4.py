"""Swap a WP4 de punta a punta: real SIMULADO (30 filas ficticias, esquema exacto de WP4) por la ruta --test.

Verifica: contrato de columnas, deflación IPC por fecha, regla de soporte >= 10, corte con/sin filas etiquetadas por
declaración, bootstrap por voluntario y Δ pareado CTGAN − reglas. Entrena un LogReg pequeño (3.000 filas) para que
la prueba sea rápida; las salidas van a un directorio temporal, nunca a outputs/tstr/.
"""
import json
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
    # 10.300 (ago-2026) -> 9.642; 105.000 (abr-2026) -> 99.687; 1.010.000 (dic-2025) -> 996.062
    assert "[MONTO=10K-30K]" in antes[0] and "[MONTO=3K-10K]" in despues[0]
    assert "[MONTO=100K-300K]" in antes[10] and "[MONTO=30K-100K]" in despues[10]
    assert "[MONTO=1M-3M]" in antes[7] and "[MONTO=300K-1M]" in despues[7]


@requiere_sinteticos
def test_swap_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "SALIDA", tmp_path / "tstr")          # nada se escribe en outputs/tstr/
    clases, sha_tax = base.cargar_taxonomia()
    corridas = {}
    for fuente in ("reglas", "ctgan"):
        train = pd.read_csv(RAIZ / base.FUENTES[fuente])
        chico = tmp_path / f"train_{fuente}.csv"
        base.submuestra(train, 3000).to_csv(chico, index=False)
        corridas[("tstr", fuente, "logreg")] = base.correr(fuente, chico, REAL_SIMULADO, clases, sha_tax)

    m = corridas[("tstr", "reglas", "logreg")]
    assert m["modo"] == "tstr" and m["reportable"] and m["n_test"] == 30
    assert m["contrato_wp4_faltan"] == []
    assert m["entrada"]["deflactor_test"]["deflactado"] is True
    # regla de soporte: solo alimentos_mercado (11) y transferencias_p2p (10) quedan; el resto va a otros
    assert set(m["clases_fusionadas_a_otros"]) >= {"comidas_fuera", "ingreso", "retiro_efectivo"}
    assert m["clases_evaluadas"] == 3
    # corte sin filas por declaración: 27 filas, alimentos baja a 8 y también se fusiona
    st = m["solo_etiqueta_por_texto"]
    assert st["n_test"] == 27 and "alimentos_mercado" in st["clases_fusionadas_a_otros"]
    assert abs(m["frac_test_etiqueta_por_declaracion"] - 0.1) < 1e-9
    # bootstrap por voluntario
    assert m["bootstrap"]["unidad"] == "voluntario_id"
    p = pd.read_csv(tmp_path / "tstr/tstr/reglas/logreg/predicciones.csv.gz", keep_default_na=False)
    assert sorted(set(p["grupo"])) == ["V01", "V02", "V03"]
    # Δ pareado CTGAN − reglas (mismo test, mismas réplicas por voluntario)
    filas = base._ablacion("tstr", corridas, clases)
    assert len(filas) == 1 and filas[0].startswith("| Baseline")
    lo, hi = m["ic95_bootstrap"]
    assert 0 <= lo <= m["f1_macro_regla_soporte"] <= hi <= 1
