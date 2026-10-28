"""Tests de src/sdg/ipc.py (WP6): actualización de pesos de 2016-17 a pesos de 2025.

Ejecutar desde la raíz:  .venv\\Scripts\\python.exe -m unittest tests.test_ipc -v
No usa datos reales: construye una serie sintética con crecimiento conocido y comprueba el factor con la fórmula escrita a mano.
"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sdg import ipc  # noqa: E402


def serie_sintetica(tasa_mensual: float = 0.004, meses_vacios: tuple = ()) -> pd.DataFrame:
    """Índices con crecimiento geométrico distinto por división (la división d crece a tasa·(1+d/20))."""
    filas = []
    for division in [ipc.TOTAL, *ipc.DIVISIONES]:
        d = 0 if division == ipc.TOTAL else int(division)
        tasa = tasa_mensual * (1 + d / 20)
        for i, mes in enumerate(pd.period_range("2016-07", "2025-12", freq="M")):
            if str(mes) in meses_vacios:
                continue
            filas.append(dict(mes=str(mes), division=division, indice=100.0 * (1 + tasa) ** i))
    return pd.DataFrame(filas)


def a_csv(df: pd.DataFrame, carpeta: Path, nombre: str = "ipc.csv") -> Path:
    ruta = carpeta / nombre
    df.to_csv(ruta, index=False)
    return ruta


class TestIPC(unittest.TestCase):
    def test_sin_archivo_devuelve_none_y_factor_uno(self):
        self.assertIsNone(ipc.cargar_serie(Path(tempfile.gettempdir()) / "no_existe_ipc.csv"))
        periodo = pd.Series(["201610", "201701"])
        f, diag = ipc.factores(None, periodo, pd.Series(["01", "04"]))
        self.assertTrue((f == 1.0).all())
        self.assertFalse(diag["aplicado"])

    def test_factor_igual_a_la_formula_a_mano(self):
        with tempfile.TemporaryDirectory() as d:
            s = ipc.cargar_serie(a_csv(serie_sintetica(), Path(d)))
        base = s[s["mes"].str.startswith("2025-")].groupby("division")["indice"].mean()
        periodo = pd.Series(["201610", "201703", "201705"])
        div = pd.Series(["01", "04", "11"])
        f, diag = ipc.factores(s, periodo, div, "division")
        for i in range(3):
            idx = s[(s["mes"] == f"{periodo[i][:4]}-{periodo[i][4:]}") & (s["division"] == div[i])]["indice"].iloc[0]
            self.assertAlmostEqual(f[i], base[div[i]] / idx, places=12)
        self.assertTrue(diag["aplicado"])
        self.assertTrue((f > 1.0).all(), "actualizar a 2025 desde 2016-17 debe multiplicar (>1)")

    def test_modo_total_usa_siempre_el_indice_general(self):
        with tempfile.TemporaryDirectory() as d:
            s = ipc.cargar_serie(a_csv(serie_sintetica(), Path(d)))
        periodo = pd.Series(["201610"] * 3)
        f_tot, _ = ipc.factores(s, periodo, pd.Series(["01", "04", "11"]), "total")
        self.assertAlmostEqual(f_tot.min(), f_tot.max(), places=12)
        f_div, _ = ipc.factores(s, periodo, pd.Series(["01", "04", "11"]), "division")
        self.assertGreater(f_div.max() - f_div.min(), 1e-3, "por división los factores deben diferir")

    def test_division_desconocida_cae_al_total_y_se_cuenta(self):
        with tempfile.TemporaryDirectory() as d:
            s = ipc.cargar_serie(a_csv(serie_sintetica(), Path(d)))
        f, diag = ipc.factores(s, pd.Series(["201610", "201610"]), pd.Series(["01", "00"]), "division")
        # "00" es el total: pertenece a la serie, no cae. Una división fuera de la serie sí:
        f2, diag2 = ipc.factores(s, pd.Series(["201610"]), pd.Series(["99"]), "division")
        self.assertEqual(diag2["filas_con_caida_al_total"], 1)
        self.assertAlmostEqual(f2.iloc[0], ipc.factores(s, pd.Series(["201610"]), pd.Series(["00"]), "total")[0].iloc[0], places=12)

    def test_mes_de_recoleccion_fuera_de_la_serie_es_error(self):
        s = serie_sintetica()
        with tempfile.TemporaryDirectory() as d:
            s = ipc.cargar_serie(a_csv(s[s["mes"] >= "2016-11"], Path(d)))        # la serie empieza después del mes de recolección
        with self.assertRaises(ipc.IPCError):
            ipc.factores(s, pd.Series(["201610"]), pd.Series(["01"]))

    def test_hueco_en_medio_de_la_serie_es_error_al_cargar(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ipc.IPCError):
                ipc.cargar_serie(a_csv(serie_sintetica(meses_vacios=("2016-10",)), Path(d)))

    def test_anio_base_incompleto_es_error(self):
        with tempfile.TemporaryDirectory() as d:
            s = ipc.cargar_serie(a_csv(serie_sintetica(meses_vacios=("2025-12",)), Path(d)))
        with self.assertRaises(ipc.IPCError):
            ipc.factores(s, pd.Series(["201610"]), pd.Series(["01"]))

    def test_formato_invalido_es_error(self):
        base = serie_sintetica()
        casos = {
            "indice_cero": base.assign(indice=np.where(base.index == 3, 0.0, base["indice"])),
            "mes_mal_formado": base.assign(mes=np.where(base.index == 3, "2016/07", base["mes"])),
            "division_fuera": base.assign(division=np.where(base.index == 3, "13", base["division"])),
            "duplicado": pd.concat([base, base.iloc[:1]], ignore_index=True),
        }
        for nombre, df in casos.items():
            with self.subTest(nombre), tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ipc.IPCError):
                    ipc.cargar_serie(a_csv(df, Path(d)))

    def test_columnas_faltantes_es_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ipc.IPCError):
                ipc.cargar_serie(a_csv(serie_sintetica().drop(columns="indice"), Path(d)))

    def test_modo_invalido(self):
        with self.assertRaises(ValueError):
            ipc.factores(None, pd.Series(["201610"]), pd.Series(["01"]), "otro")

    def test_referencia_invalida(self):
        with self.assertRaises(ValueError):
            ipc.factores(None, pd.Series(["201610"]), pd.Series(["01"]), "total", "ayer")


class TestReferencias(unittest.TestCase):
    """Periodo de referencia de los valores de ENPH: mes de recolección, promedio del campo o promedio de 2017."""

    PERIODOS = ["201607", "201609", "201612", "201703", "201706", "201609"]

    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            self.s = ipc.cargar_serie(a_csv(serie_sintetica(), Path(d)))
        self.ancho = self.s.pivot(index="mes", columns="division", values="indice")
        self.base = ipc.indice_base(self.s)[ipc.TOTAL]
        self.p = pd.Series(self.PERIODOS)
        self.div = pd.Series([ipc.TOTAL] * len(self.p))

    def _f(self, ref):
        return ipc.factores(self.s, self.p, self.div, "total", ref)

    def test_mes_de_recoleccion_es_el_valor_por_defecto_y_baja_con_el_tiempo(self):
        f, diag = ipc.factores(self.s, self.p, self.div, "total")
        self.assertEqual(diag["referencia"], "mes_recoleccion")
        esperado = [self.base / self.ancho.loc[f"{x[:4]}-{x[4:]}", ipc.TOTAL] for x in self.PERIODOS]
        np.testing.assert_allclose(f.to_numpy(), esperado, rtol=1e-12)
        self.assertGreater(f[0], f[2])
        self.assertGreater(f[2], f[4])                                  # más reciente → menos actualización

    def test_promedio_del_campo_es_un_factor_unico(self):
        f, diag = self._f("promedio_campo")
        meses = ["2016-07", "2016-09", "2016-12", "2017-03", "2017-06"]
        self.assertAlmostEqual(f.min(), f.max(), places=12)
        self.assertAlmostEqual(f.iloc[0], self.base / self.ancho.loc[meses, ipc.TOTAL].mean(), places=12)
        self.assertEqual(diag["meses_recoleccion"], ["2016-07", "2017-06", 5])

    def test_promedio_2017_es_un_factor_unico(self):
        f, _ = self._f("anio_2017")
        m17 = [f"2017-{m:02d}" for m in range(1, 13)]
        self.assertAlmostEqual(f.min(), f.max(), places=12)
        self.assertAlmostEqual(f.iloc[0], self.base / self.ancho.loc[m17, ipc.TOTAL].mean(), places=12)

    def test_las_referencias_equivalentes_del_diagnostico_coinciden_con_cada_opcion(self):
        _, d = self._f("mes_recoleccion")
        eq = d["referencias_equivalentes"]
        self.assertAlmostEqual(eq["promedio_campo"], self._f("promedio_campo")[0].iloc[0], places=12)
        self.assertAlmostEqual(eq["anio_2017"], self._f("anio_2017")[0].iloc[0], places=12)
        f, _ = self._f("mes_recoleccion")
        self.assertAlmostEqual(eq["mes_recoleccion"]["factor_min"], f.min(), places=12)
        self.assertAlmostEqual(eq["mes_recoleccion"]["factor_max"], f.max(), places=12)

    def test_con_crecimiento_constante_el_campo_queda_entre_los_extremos(self):
        f, _ = self._f("mes_recoleccion")
        medio, _ = self._f("promedio_campo")
        self.assertLess(f.min(), medio.iloc[0])
        self.assertLess(medio.iloc[0], f.max())


class TestXlsxEmpalme(unittest.TestCase):
    """Convertidor del xlsx del DANE a formato largo. Usa un xlsx sintético con la misma disposición (filas = meses, columnas = años)."""

    ANIOS = list(range(2016, 2027))

    @staticmethod
    def valor(anio, mes):
        return round(100.0 * 1.003 ** ((anio - 2018) * 12 + mes - 12), 2)                    # dic-2018 = 100

    def construir(self, carpeta, ultimo_mes_2026=9, hoja="IndicesIPC", nombres=None, hueco=None, texto=None, encabezado="Mes"):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = hoja
        for fila in ([], [], ["Total, Índice de Precios al Consumidor (IPC)"], [], ["Índices - Serie de empalme\n2003 - 2026"], [], ["Número Índice"], []):
            ws.append(fila)
        ws.append([encabezado, *self.ANIOS])
        for m, nombre in enumerate(nombres or ipc.MESES_ES, start=1):
            fila = [nombre]
            for a in self.ANIOS:
                v = self.valor(a, m)
                if a == self.ANIOS[-1] and m > ultimo_mes_2026:
                    v = None
                if hueco == (a, m):
                    v = texto
                fila.append(v)
            ws.append(fila)
        for fila in ([], ["Fuente: DANE."], ["Nota: redondeo."], ["Actualizado el 7 de Octubre de 2026"]):
            ws.append(fila)
        ruta = Path(carpeta) / "anex-IPC-sintetico.xlsx"
        wb.save(ruta)
        return ruta

    def test_lee_la_serie_larga_y_omite_los_meses_no_publicados(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = self.construir(d)
            s, meta = ipc.leer_xlsx_empalme(ruta)
            self.assertEqual(meta["sha256_xlsx"], ipc.sha256_archivo(ruta))
        self.assertEqual(list(s.columns), ["mes", "division", "indice"])
        self.assertTrue((s["division"] == ipc.TOTAL).all())
        self.assertEqual((meta["primer_mes"], meta["ultimo_mes"], meta["n_meses"]), ("2016-01", "2026-09", 10 * 12 + 9))
        self.assertAlmostEqual(float(s.loc[s["mes"] == "2020-05", "indice"].iloc[0]), self.valor(2020, 5))
        self.assertTrue(meta["base_dic_2018_igual_100"])
        self.assertEqual(meta["actualizado"], "Actualizado el 7 de Octubre de 2026")
        self.assertIn("empalme", meta["titulo"])

    def test_roundtrip_por_csv_conserva_la_serie(self):
        with tempfile.TemporaryDirectory() as d:
            s, _ = ipc.leer_xlsx_empalme(self.construir(d))
            releida = ipc.cargar_serie(a_csv(s, Path(d)))
        pd.testing.assert_frame_equal(s, releida)

    def test_base_distinta_de_dic_2018_se_registra_sin_fallar(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "x.xlsx"
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "IndicesIPC"
            ws.append(["Mes", 2018, 2019])
            for m, nombre in enumerate(ipc.MESES_ES, start=1):
                ws.append([nombre, 80.0 + m, 90.0 + m])
            wb.save(ruta)
            _, meta = ipc.leer_xlsx_empalme(ruta)
        self.assertFalse(meta["base_dic_2018_igual_100"])
        self.assertEqual(meta["indice_2018_12"], 92.0)

    def test_hoja_inexistente_es_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ipc.IPCError):
                ipc.leer_xlsx_empalme(self.construir(d, hoja="Otra"))

    def test_sin_encabezado_mes_es_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ipc.IPCError):
                ipc.leer_xlsx_empalme(self.construir(d, encabezado="Periodo"))

    def test_nombres_de_mes_distintos_son_error(self):
        malos = list(ipc.MESES_ES)
        malos[2] = "Marso"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ipc.IPCError):
                ipc.leer_xlsx_empalme(self.construir(d, nombres=malos))

    def test_hueco_en_medio_es_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ipc.IPCError):
                ipc.leer_xlsx_empalme(self.construir(d, hueco=(2019, 6), texto=None))

    def test_celda_no_numerica_es_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ipc.IPCError):
                ipc.leer_xlsx_empalme(self.construir(d, hueco=(2019, 6), texto="n.d."))


@unittest.skipUnless(ipc.RUTA_IPC.is_file(), "falta outputs/ipc/ipc_total_nacional.csv: correr tools/convertir_ipc.py")
class TestSerieReal(unittest.TestCase):
    """La serie convertida del DANE. Bandas amplias: comprueban que es la serie correcta, no el valor de un factor."""

    @classmethod
    def setUpClass(cls):
        cls.s = ipc.cargar_serie()

    def test_cubre_el_campo_de_la_enph_y_el_ano_base(self):
        meses = set(self.s["mes"])
        esperado = set(pd.period_range("2016-07", "2025-12", freq="M").astype(str))
        self.assertTrue(esperado <= meses)
        self.assertEqual(set(self.s["division"]), {ipc.TOTAL})

    def test_dic_2018_es_100_y_la_serie_crece(self):
        x = self.s.set_index("mes")["indice"]
        self.assertAlmostEqual(x["2018-12"], 100.0, places=6)
        anual = x.groupby(x.index.str[:4]).mean()
        self.assertTrue((anual.diff().dropna() > 0).all(), "el promedio anual del IPC debe crecer cada año")

    def test_factor_2017_a_2025_en_banda(self):
        f, d = ipc.factores(self.s, pd.Series(["201610", "201703"]), pd.Series([ipc.TOTAL] * 2), "total")
        self.assertTrue(((f > 1.45) & (f < 1.75)).all())
        self.assertTrue(1.45 < d["referencias_equivalentes"]["anio_2017"] < 1.75)
        self.assertTrue(d["referencias_equivalentes"]["anio_2017"] < d["referencias_equivalentes"]["promedio_campo"],
                        "el promedio de 2017 es más alto que el del campo (2016-07 a 2017-06), así que da un factor menor")

    def test_coincide_con_el_xlsx_si_esta_en_data_raw(self):
        xlsx = sorted(ipc.DIR_CRUDO.glob("anex-IPC*.xlsx"))
        if len(xlsx) != 1:
            self.skipTest("no hay exactamente un anex-IPC*.xlsx en data/raw/IPC (esa carpeta no se versiona)")
        s, _ = ipc.leer_xlsx_empalme(xlsx[0])
        pd.testing.assert_frame_equal(s, self.s)


if __name__ == "__main__":
    unittest.main()
