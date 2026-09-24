"""Pruebas del mapeo de categorías de Pancholi a la taxonomía v1 y de la función de Wilson.

Se integran con la suite del repositorio (`python -m unittest discover -s tests`): sin dependencia
de pytest. Las pruebas que necesitan el clon del pipeline de referencia (`external/pancholi/`, no
versionado) se omiten automáticamente cuando el clon no está presente.
"""
import ast
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
from analisis_pancholi import wilson  # noqa: E402

MAPEO = pd.read_csv(RAIZ / "docs/taxonomia/mapeo_pancholi_taxonomia_v1.csv").fillna("")
TAXO = json.loads((RAIZ / "docs/taxonomia/taxonomia_v1_extracto.json").read_text(encoding="utf-8"))["categorias_nivel_1"]

FUENTE_PATH = RAIZ / "external/pancholi/src/component/transaction.py"
HAY_CLON = FUENTE_PATH.exists()


def _dict_literal(fuente: str, nombre_var: str) -> dict:
    """Extrae un dict literal del código de Pancholi sin importarlo (no requiere sdv)."""
    for nodo in ast.walk(ast.parse(fuente)):
        if isinstance(nodo, ast.Assign) and any(getattr(t, "id", None) == nombre_var for t in nodo.targets):
            return {ast.literal_eval(k): v for k, v in zip(nodo.value.keys, nodo.value.values)}
    raise AssertionError(f"{nombre_var} no está en transaction.py")


if HAY_CLON:
    _F = FUENTE_PATH.read_text(encoding="utf-8")
    CATEGORY_MAPPING = {k: ast.literal_eval(v) for k, v in _dict_literal(_F, "CATEGORY_MAPPING").items()}
    BASE_ALLOCATION = set(_dict_literal(_F, "base_allocation"))


class TestMapeoTaxonomia(unittest.TestCase):
    """Solo necesitan el CSV de mapeo y la taxonomía (versionados)."""

    def test_destinos_existen_en_taxonomia_v1(self):
        for _, r in MAPEO.iterrows():
            self.assertIn(r.nivel_1_v1, TAXO)
            self.assertTrue(r.nivel_2_v1 == "" or r.nivel_2_v1 in TAXO[r.nivel_1_v1]["subtipos"],
                            (r.nivel_1_v1, r.nivel_2_v1))

    def test_housing_es_hospedaje_no_vivienda(self):
        fila = MAPEO.set_index("etiqueta_pancholi").loc["housing"]
        self.assertNotEqual(fila.nivel_1_v1, "vivienda_servicios")

    def test_ninguna_etiqueta_llega_a_servicios_publicos_ni_extracto(self):
        self.assertNotIn("servicios_publicos", set(MAPEO.nivel_2_v1))
        self.assertFalse(set(MAPEO.nivel_1_v1) & {"retiro_efectivo", "transferencias_p2p",
                                                  "movimiento_propio", "ingreso"})


@unittest.skipUnless(HAY_CLON, "clon del pipeline de referencia ausente (external/pancholi/)")
class TestMapeoContraCodigo(unittest.TestCase):
    """Contrastan el mapeo contra el código de Pancholi; requieren el clon."""

    def test_toda_etiqueta_de_pancholi_esta_mapeada(self):
        etiquetas = BASE_ALLOCATION | set(CATEGORY_MAPPING.values())
        self.assertEqual(etiquetas, set(MAPEO.etiqueta_pancholi), etiquetas ^ set(MAPEO.etiqueta_pancholi))

    def test_licencias_declaradas_coinciden_con_el_codigo(self):
        for _, r in MAPEO.iterrows():
            for lic in [x.strip() for x in r.licencias_dc_que_la_alimentan.split(";") if x.strip()]:
                self.assertEqual(CATEGORY_MAPPING.get(lic), r.etiqueta_pancholi, lic)
        declaradas = {x.strip() for s in MAPEO.licencias_dc_que_la_alimentan for x in s.split(";") if x.strip()}
        self.assertEqual(declaradas, set(CATEGORY_MAPPING))


class TestWilson(unittest.TestCase):
    def test_wilson_valores_conocidos(self):
        casos = [(0, 100, 0.0, 0.036994), (50, 100, 0.403832, 0.596168), (100, 100, 0.963006, 1.0)]
        for x, n, inf, sup in casos:
            with self.subTest(x=x, n=n):
                p, lo, hi = wilson(x, n)
                self.assertEqual(p, x / n)
                self.assertAlmostEqual(lo, inf, places=5)
                self.assertAlmostEqual(hi, sup, places=5)


if __name__ == "__main__":
    unittest.main()
