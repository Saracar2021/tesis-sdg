"""Pruebas del mapeo de la etapa 4 (LLM) de Pancholi a la taxonomía v1.1 y del criterio de mapeabilidad para WP8.

Suite del repositorio: `python -m unittest discover -s tests`. Las pruebas que leen el código del pipeline de
referencia se omiten si el clon (`external/pancholi/`, no versionado) no está presente.
"""
import ast
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))

MAP4 = pd.read_csv(RAIZ / "docs/taxonomia/mapeo_pancholi_etapa4_taxonomia_v1.csv").fillna("")
TAXO = json.loads((RAIZ / "docs/taxonomia/taxonomia_gastos_colombia_v1.json").read_text(encoding="utf-8"))
SUBT = {c["id"]: c["subtipos"] for c in TAXO["categorias_nivel_1"]}
EXTRACTO = (RAIZ / "docs/taxonomia/taxonomia_v1_extracto.json")
ETAPA4 = RAIZ / "external/pancholi/src/Data_Synthesizer/code/transaction_deepseek_synthesizer.py"
HAY_CLON = ETAPA4.exists()


class TestMapeoEtapa4(unittest.TestCase):
    def test_destinos_existen_en_taxonomia_v11(self):
        for r in MAP4.itertuples():
            self.assertIn(r.nivel_1_v1, SUBT, r.subcategoria_etapa4)
            if r.nivel_2_v1:
                self.assertIn(r.nivel_2_v1, SUBT[r.nivel_1_v1], r.subcategoria_etapa4)

    def test_sin_duplicados(self):
        self.assertFalse(MAP4.subcategoria_etapa4.duplicated().any())

    def test_hospedaje_coherente_con_etapa2(self):
        hosp = MAP4[MAP4.familia_pancholi == "Lodging"].set_index("subcategoria_etapa4").nivel_1_v1
        self.assertTrue((hosp.drop("boarding_house") == "otros").all())

    def test_extracto_v1_vigente_en_v11(self):
        ext = json.loads(EXTRACTO.read_text(encoding="utf-8"))["categorias_nivel_1"]
        self.assertEqual({k: v["subtipos"] for k, v in ext.items()}, SUBT)

    def test_ninguna_ruta_a_registros_de_extracto(self):
        prohibidas = {"retiro_efectivo", "transferencias_p2p", "movimiento_propio", "ingreso"}
        self.assertFalse(prohibidas & set(MAP4.nivel_1_v1))

    @unittest.skipUnless(HAY_CLON, "requiere el clon de Pancholi en external/pancholi")
    def test_mapeo_cubre_exactamente_sus_subcategorias(self):
        from mapeabilidad_pancholi import dict_literal
        sus = set(dict_literal(ETAPA4, "spending_categories"))
        self.assertEqual(sus, set(MAP4.subcategoria_etapa4))

    @unittest.skipUnless(HAY_CLON, "requiere el clon de Pancholi en external/pancholi")
    def test_veredicto_no_mapeable(self):
        r = json.loads((RAIZ / "outputs/pancholi/wp8_mapeabilidad.json").read_text(encoding="utf-8"))
        self.assertFalse(r["mapeable"])
        self.assertLess(r["n_clases_alcanzables"], r["n_clases_taxonomia"])
        self.assertTrue(r["veredicto_wp8"].startswith("(a)"))


class TestNormalizacionMedioPago(unittest.TestCase):
    def test_reglas(self):
        from analisis_pancholi_etapa4 import medio
        casos = {"Credit Card": "tarjeta_credito", "credit_card": "tarjeta_credito", "Debit Card": "tarjeta_debito",
                 "Visa Debit": "tarjeta_debito", "Cash": "efectivo", "Apple Pay": "billetera_digital",
                 "Bank Transfer": "transferencia_bancaria", "Gift Card": "bono_subsidio", "Check": "otro_nd"}
        for texto, esperado in casos.items():
            self.assertEqual(medio(texto), esperado, texto)


if __name__ == "__main__":
    unittest.main()
