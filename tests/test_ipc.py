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

    def test_mes_de_recoleccion_faltante_es_error(self):
        with tempfile.TemporaryDirectory() as d:
            s = ipc.cargar_serie(a_csv(serie_sintetica(meses_vacios=("2016-10",)), Path(d)))
        with self.assertRaises(ipc.IPCError):
            ipc.factores(s, pd.Series(["201610"]), pd.Series(["01"]))

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


if __name__ == "__main__":
    unittest.main()
