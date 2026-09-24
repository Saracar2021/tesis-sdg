"""Pruebas del mapeo de categorías de Pancholi a la taxonomía v1 y de la función de Wilson (WP5)."""
import ast
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
from analisis_pancholi import wilson  # noqa: E402

MAPEO = pd.read_csv(RAIZ / "docs/taxonomia/mapeo_pancholi_taxonomia_v1.csv").fillna("")
TAXO = json.loads((RAIZ / "docs/taxonomia/taxonomia_v1_extracto.json").read_text())["categorias_nivel_1"]
FUENTE = (RAIZ / "external/pancholi/src/component/transaction.py").read_text()


def _dict_literal(nombre_var: str) -> dict:
    """Extrae un dict literal del código de Pancholi sin importarlo (no requiere sdv)."""
    for nodo in ast.walk(ast.parse(FUENTE)):
        if isinstance(nodo, ast.Assign) and any(getattr(t, "id", None) == nombre_var for t in nodo.targets):
            return {ast.literal_eval(k): v for k, v in zip(nodo.value.keys, nodo.value.values)}
    raise AssertionError(f"{nombre_var} no está en transaction.py")


CATEGORY_MAPPING = {k: ast.literal_eval(v) for k, v in _dict_literal("CATEGORY_MAPPING").items()}
BASE_ALLOCATION = set(_dict_literal("base_allocation"))


def test_toda_etiqueta_de_pancholi_esta_mapeada():
    etiquetas = BASE_ALLOCATION | set(CATEGORY_MAPPING.values())
    assert etiquetas == set(MAPEO.etiqueta_pancholi), etiquetas ^ set(MAPEO.etiqueta_pancholi)


def test_destinos_existen_en_taxonomia_v1():
    for _, r in MAPEO.iterrows():
        assert r.nivel_1_v1 in TAXO, r.nivel_1_v1
        assert r.nivel_2_v1 == "" or r.nivel_2_v1 in TAXO[r.nivel_1_v1]["subtipos"], (r.nivel_1_v1, r.nivel_2_v1)


def test_licencias_declaradas_coinciden_con_el_codigo():
    for _, r in MAPEO.iterrows():
        for lic in [x.strip() for x in r.licencias_dc_que_la_alimentan.split(";") if x.strip()]:
            assert CATEGORY_MAPPING.get(lic) == r.etiqueta_pancholi, lic
    declaradas = {x.strip() for s in MAPEO.licencias_dc_que_la_alimentan for x in s.split(";") if x.strip()}
    assert declaradas == set(CATEGORY_MAPPING)


def test_housing_es_hospedaje_no_vivienda():
    fila = MAPEO.set_index("etiqueta_pancholi").loc["housing"]
    assert fila.nivel_1_v1 != "vivienda_servicios"


def test_ninguna_etiqueta_llega_a_servicios_publicos_ni_extracto():
    assert "servicios_publicos" not in set(MAPEO.nivel_2_v1)
    assert not set(MAPEO.nivel_1_v1) & {"retiro_efectivo", "transferencias_p2p", "movimiento_propio", "ingreso"}


@pytest.mark.parametrize("x,n,inf,sup", [
    (0, 100, 0.0, 0.036994),     # cota superior = z^2/(n+z^2)
    (50, 100, 0.403832, 0.596168),
    (100, 100, 0.963006, 1.0),
])
def test_wilson_valores_conocidos(x, n, inf, sup):
    p, lo, hi = wilson(x, n)
    assert p == x / n
    assert lo == pytest.approx(inf, abs=1e-5) and hi == pytest.approx(sup, abs=1e-5)
