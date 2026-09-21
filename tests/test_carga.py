"""Tests de src/sdg/carga.py y src/sdg/pesos.py.

Ejecutar desde la raíz:  .venv\\Scripts\\python.exe -m unittest discover -s tests -v
(unittest de la biblioteca estándar: el entorno no tiene pytest).
Los tests de datos leen data/raw (solo lectura) y comparan contra un conteo independiente (módulo csv),
no contra cifras escritas a mano.
"""
import csv
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sdg import carga  # noqa: E402
from sdg.medio_pago import estado_p438  # noqa: E402
from sdg.pesos import cortes_ponderados, distribucion, fronteras, grupo_por_cortes  # noqa: E402


def contar_area_11(mes_dir: str, modulo: str) -> tuple[int, int]:
    """(filas totales, filas con AREA == '11') leyendo con el módulo csv: verificación independiente."""
    with open(RAIZ / "data/raw/GEIH_2025" / mes_dir / f"{modulo}.csv", encoding="cp1252", newline="") as f:
        lector = csv.reader(f, delimiter=";")
        cab = next(lector)
        i = cab.index("AREA")
        total = bog = 0
        for fila in lector:
            total += 1
            bog += fila[i].strip() == "11"
    return total, bog


class TestGeih(unittest.TestCase):
    def test_fex_se_divide_por_los_meses_realmente_cargados(self):
        for meses in ([1, 2, 3], list(range(1, 12)), list(range(1, 13))):
            df = carga.cargar_geih("datos_hogar", meses=meses, columnas=["P4030S1A1"])
            self.assertEqual(df.attrs["n_meses"], len(meses))
            np.testing.assert_allclose(df["FEX"] * len(meses), df["FEX_C18"], rtol=1e-12)
            self.assertEqual(sorted(df["MES"].astype(int).unique()), meses)

    def test_dominio_bogota_es_area_11_y_coincide_con_conteo_independiente(self):
        df = carga.cargar_geih("ocupados", meses=[1], columnas=["P6430"])
        total, bog = contar_area_11("01_enero", "ocupados")
        self.assertEqual(len(df), bog)
        self.assertEqual(df.attrs["filas_nacional_validadas"], total)
        self.assertTrue((df["AREA"] == "11").all())
        todo = carga.cargar_geih("ocupados", meses=[1], dominio="todo", columnas=["P6430"])
        self.assertEqual(len(todo), total)
        self.assertGreater(len(todo), len(df))

    def test_no_usa_dpto(self):
        df = carga.cargar_geih("datos_hogar", meses=[1], columnas=["DPTO"])
        self.assertTrue((df["AREA"] == "11").all())  # el filtro es AREA; DPTO solo viaja como columna

    def test_valida_filas_contra_fuentes(self):
        with mock.patch.object(carga, "_filas_esperadas_geih", return_value=1):
            with self.assertRaises(carga.IntegridadError):
                carga.cargar_geih("datos_hogar", meses=[1], columnas=["P4030S1A1"])

    def test_argumentos_invalidos(self):
        with self.assertRaises(ValueError):
            carga.cargar_geih("datos_hogar", meses=[13])
        with self.assertRaises(ValueError):
            carga.cargar_geih("datos_hogar", meses=[])
        with self.assertRaises(ValueError):
            carga.cargar_geih("datos_hogar", dominio="colombia")
        with self.assertRaises(ValueError):
            carga.cargar_geih("no_existe")

    def test_columna_inexistente_falla(self):
        with self.assertRaises(carga.IntegridadError):
            carga.cargar_geih("datos_hogar", meses=[1], columnas=["NO_EXISTE"])

    def test_lista_de_modulos_devuelve_dict(self):
        d = carga.cargar_geih(["datos_hogar"], meses=[1], columnas=["P4030S1A1"])
        self.assertIsInstance(d, dict)
        self.assertEqual(list(d), ["datos_hogar"])
        self.assertIsInstance(carga.cargar_geih("datos_hogar", meses=[1], columnas=["P4030S1A1"]), pd.DataFrame)


class TestEnph(unittest.TestCase):
    def test_encoding_sin_bom_y_txt_por_tabulador(self):
        h = carga.cargar_enph("viviendas_hogares", dominio="todo", columnas=["REGION"])
        self.assertIn("DIRECTORIO", h.columns)  # utf-8-sig: sin '﻿DIRECTORIO'
        self.assertEqual(len(h), h.attrs["filas_nacional_validadas"])
        t = carga.cargar_enph("hogares/gastos_menos_frecuentes_articulos.txt", dominio="todo", columnas=["SECUENCIA_P"])
        self.assertIn("SECUENCIA_P", t.columns)  # tab: con «;» no separaría columnas
        self.assertEqual(t.attrs["unidad"], "registro de gasto")

    def test_bogota_hogares_y_peso(self):
        h = carga.cargar_enph("viviendas_hogares", columnas=["REGION"])
        self.assertTrue((h["DOMINIO"] == "BOGOTÁ").all())
        self.assertTrue(h["DIRECTORIO"].is_unique)
        self.assertTrue((h["FEX"] > 0).all())
        self.assertEqual(h.attrs["unidad"], "hogar")

    def test_tabla_de_gasto_se_restringe_por_directorio_y_reporta_enlace(self):
        h = carga.cargar_enph("viviendas_hogares", columnas=["REGION"])
        n0 = len(carga.UNIONES)
        m = carga.cargar_enph("urbano/gastos_diarios_mercados.csv")
        self.assertTrue(set(m["DIRECTORIO"]) <= set(h["DIRECTORIO"]))
        self.assertEqual(carga.UNIONES[n0]["pct_enlazado"], 100.0)
        self.assertEqual(m.attrs["unidad"], "registro de gasto")

    def test_rural_bloqueado(self):
        with self.assertRaises(carga.DominioError):
            carga.cargar_enph("rural/gastos_personales.csv")
        with self.assertRaises(carga.DominioError):
            carga.cargar_enph("gastos_semanales")  # nombre suelto que solo existe en rural

    def test_nombre_suelto_ambiguo_resuelve_a_urbano_y_rural_solo_si_se_pide(self):
        p = carga._resolver_enph("gastos_personales_comidas_fuera", permitir_rural=False)
        self.assertEqual(p.parent.name, "urbano")
        with self.assertRaises(ValueError):  # con rural permitido hay dos candidatos: exige carpeta
            carga._resolver_enph("gastos_personales_comidas_fuera", permitir_rural=True)
        self.assertEqual(carga._resolver_enph("rural/gastos_personales.csv", permitir_rural=True).parent.name, "rural")

    def test_valida_filas_contra_fuentes(self):
        with mock.patch.object(carga, "_filas_esperadas_enph", return_value=1):
            with self.assertRaises(carga.IntegridadError):
                carga.cargar_enph("viviendas_hogares", columnas=["REGION"])


class TestUniones(unittest.TestCase):
    def setUp(self):
        self.izq = pd.DataFrame({"K": ["1", "2", "3", "4"], "a": list("wxyz")})

    def test_reporta_pct_y_devuelve_mismas_filas(self):
        der = pd.DataFrame({"K": ["1", "2", "3", "4", "5"], "b": list("vwxyz")})
        n0 = len(carga.UNIONES)
        out = carga.unir(self.izq, der, ["K"], nombre="prueba")
        self.assertEqual(len(out), 4)
        self.assertEqual(carga.UNIONES[n0]["pct_enlazado"], 100.0)
        self.assertEqual(out.attrs["union"]["pct_der_usado"], 80.0)

    def test_falla_bajo_el_umbral_y_reporta_el_pct_real(self):
        der = pd.DataFrame({"K": ["1", "2"], "b": ["p", "q"]})
        n0 = len(carga.UNIONES)
        with self.assertRaises(carga.UnionError):
            carga.unir(self.izq, der, ["K"], nombre="parcial")
        self.assertEqual(carga.UNIONES[n0]["pct_enlazado"], 50.0)

    def test_el_umbral_es_un_piso_configurable(self):
        der = pd.DataFrame({"K": ["1", "2", "3"], "b": list("pqr")})  # 75 %
        self.assertEqual(len(carga.unir(self.izq, der, ["K"], umbral=70.0)), 4)

    def test_lado_derecho_duplicado_falla(self):
        der = pd.DataFrame({"K": ["1", "1", "2", "3", "4"], "b": list("pqrst")})
        with self.assertRaises(carga.UnionError):
            carga.unir(self.izq, der, ["K"])

    def test_columnas_repetidas_fallan(self):
        der = pd.DataFrame({"K": ["1", "2", "3", "4"], "a": list("pqrs")})
        with self.assertRaises(carga.UnionError):
            carga.unir(self.izq, der, ["K"])

    def test_geih_persona_y_hogar_enlazan_100_por_ciento(self):
        oc = carga.cargar_geih("ocupados", meses=[1], columnas=["P6430"])
        cg = carga.cargar_geih("caracteristicas_generales", meses=[1], columnas=["P3271"])
        dh = carga.cargar_geih("datos_hogar", meses=[1], columnas=["P4030S1A1"])
        n0 = len(carga.UNIONES)
        carga.unir_geih(oc, cg, "persona", columnas_der=["P3271"])
        carga.unir_geih(oc, dh, "hogar", columnas_der=["P4030S1A1"])
        self.assertEqual([u["pct_enlazado"] for u in carga.UNIONES[n0:]], [100.0, 100.0])

    def test_geih_apilado_varios_meses_enlaza_100_y_no_duplica(self):
        """Con meses apilados la unión (llave + MES) no cambia filas y enlaza 100 %; la llave de hogar sola es única."""
        oc = carga.cargar_geih("ocupados", meses=[1, 2], columnas=["P6430"])
        dh = carga.cargar_geih("datos_hogar", meses=[1, 2], columnas=["P4030S1A1"])
        self.assertFalse(dh.duplicated(carga.LLAVE_GEIH_HOGAR).any())
        out = carga.unir_geih(oc, dh, "hogar", columnas_der=["P4030S1A1"])
        self.assertEqual(len(out), len(oc))
        self.assertEqual(carga.UNIONES[-1]["pct_enlazado"], 100.0)

    def test_enph_gasto_a_hogar_por_directorio_100(self):
        h = carga.cargar_enph("viviendas_hogares", columnas=["REGION", "ICGU"])
        m = carga.cargar_enph("urbano/gastos_diarios_mercados.csv")
        n0 = len(carga.UNIONES)
        out = carga.unir_enph_hogar(m, h, columnas_der=["ICGU"])
        self.assertEqual(len(out), len(m))
        self.assertEqual(carga.UNIONES[-1]["pct_enlazado"], 100.0)
        self.assertGreater(len(carga.UNIONES), n0)


class TestEstratoAgrupado(unittest.TestCase):
    def test_agrupacion_1_2_3_4_5_6(self):
        s = pd.Series(["1", "2", "3", "4", "5", "6", 1, 3.0, " 5 "])
        g = carga.estrato_agrupado(s).astype(str).tolist()
        b, m, a = carga.ESTRATO_GRUPOS
        self.assertEqual(g, [b, b, m, m, a, a, b, m, a])

    def test_codigos_que_no_son_estrato_quedan_sin_grupo(self):
        s = pd.Series(["0", "9", "", " ", "7", "2.5", "abc"])
        g = carga.estrato_agrupado(s)
        self.assertTrue(g.isna().all())

    def test_devuelve_categorica_ordenada_y_conserva_indice(self):
        s = pd.Series(["6", "1"], index=[10, 20])
        g = carga.estrato_agrupado(s)
        self.assertEqual(list(g.index), [10, 20])
        self.assertTrue(g.cat.ordered)
        self.assertEqual(list(g.cat.categories), list(carga.ESTRATO_GRUPOS))


class TestPesos(unittest.TestCase):
    def test_cortes_y_grupos_con_pesos_iguales(self):
        x = pd.Series(range(1, 11))
        w = pd.Series([1.0] * 10)
        c = cortes_ponderados(x, w, 5)
        self.assertEqual(c, [2.0, 4.0, 6.0, 8.0])
        self.assertEqual(grupo_por_cortes(x, c).astype(int).tolist(), [1, 1, 2, 2, 3, 3, 4, 4, 5, 5])

    def test_los_pesos_mueven_los_cortes(self):
        x = pd.Series([1, 2, 3, 4, 5])
        w = pd.Series([1, 1, 1, 1, 6.0])  # el 5 pesa 60 %
        c = cortes_ponderados(x, w, 5)
        self.assertEqual(c, [2.0, 4.0, 5.0, 5.0])  # cdf = .1,.2,.3,.4,1 → el 60 % superior colapsa en el valor 5

    def test_distribucion_sin_dato_explicito_y_bases(self):
        df = pd.DataFrame({"c": ["1", "1", "3", "", "9", "7"], "FEX": [1.0, 1, 2, 4, 1, 1]})
        t = distribucion(df, "c", etiquetas={"1": "uno", "3": "tres"}, motivos_sin_dato={"9": "nueve"})
        r = t.set_index("codigo")
        self.assertAlmostEqual(r.loc["1", "pct_con_respuesta"], 50.0)  # 2 de 4 (base con respuesta = 1 y 3)
        self.assertAlmostEqual(r.loc["3", "pct_con_respuesta"], 50.0)
        self.assertAlmostEqual(r.loc["", "pct_total"], 100 * 4 / 10)
        self.assertTrue(np.isnan(r.loc["", "pct_con_respuesta"]))
        self.assertEqual(r.loc["9", "categoria"], "sin dato: nueve")
        self.assertEqual(r.loc["7", "categoria"], "código fuera de lista")
        self.assertAlmostEqual(t["pct_total"].sum(), 100.0)
        self.assertEqual(int(t["n"].sum()), len(df))


    def test_fronteras_miden_la_masa_del_monton_y_donde_cae_el_objetivo(self):
        # 10 valores de peso 1; el 3 tiene peso 4 (monton): total 13. cdf: 1→1/13, 2→2/13, 3→6/13, ...
        x = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        w = pd.Series([1, 1, 4, 1, 1, 1, 1, 1, 1, 1], dtype=float)
        c = cortes_ponderados(x, w, 5)
        f = fronteras(x, w, c, 5).set_index("corte")
        self.assertEqual(f.loc["c1", "valor"], 3.0)  # 20 % = 2.6/13 cae dentro del monton en 3
        self.assertAlmostEqual(f.loc["c1", "masa_en_el_valor_pct"], 100 * 4 / 13)
        self.assertAlmostEqual(f.loc["c1", "masa_bajo_el_valor_pct"], 100 * 2 / 13)
        self.assertAlmostEqual(f.loc["c1", "fraccion_del_monton_bajo_objetivo"], (20 - 100 * 2 / 13) / (100 * 4 / 13))
        self.assertTrue((f["masa_en_el_valor_pct"] > 0).all())


class TestEstadoP438(unittest.TestCase):
    def test_cuatro_estados(self):
        base = pd.Series([True, True, False, False])
        medio = pd.Series([True, False, False, True])
        self.assertEqual(estado_p438(base, medio).tolist(), ["responde", "no_respuesta", "no_aplica", "medio_sin_base"])


if __name__ == "__main__":
    unittest.main()
