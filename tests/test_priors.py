"""Tests de src/sdg/encogimiento.py y src/sdg/priors.py (WP3).

Ejecutar desde la raíz:  .venv\\Scripts\\python.exe -m unittest tests.test_priors -v     (o discover -s tests)

Diseño en dos pasos, con tolerancias que salen de los datos y no de un número fijo:
  A. El muestreador reproduce la ESPERANZA ANALÍTICA de su propia ley (priors.json): tolerancia = z · SE_MC, con
     SE_MC = sqrt(p(1-p)/n) del Monte Carlo (z = 4 para marginales y pirámide, 5 en las comparaciones por celda, que son miles).
  B. La esperanza analítica de los priors, vuelta a nivel Bogotá con la masa de quienes respondieron, reproduce los CSV
     independientes de outputs/distribuciones/ (los genera tools/distribuciones_priors.py, otro código, sin pasar por este
     módulo): tolerancia = 2 · SE_ref, con SE_ref = sqrt(DEFF_REF · p̃(1-p̃)/n_ref), n_ref = n SIN ponderar del CSV y
     p̃ = (n·p+1)/(n+2) (para que una proporción observada de 0 no tenga error estándar 0).
     DEFF_REF = 2 es un supuesto declarado (no hay UPM, L1; es el mismo valor de la sensibilidad deff_cluster de WP3).
Lo que NO se prueba aquí: que ENPH 2016-17 sea representativo de 2025 (L4) ni que los supuestos de independencia se cumplan.
"""
import json
import math
import os
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sdg import encogimiento as E  # noqa: E402
from sdg import priors as P  # noqa: E402

DIST = RAIZ / "outputs" / "distribuciones"
RUTA_PRIORS = RAIZ / "outputs" / "priors" / "priors.json"
DEFF_REF = 2.0
N_MC = 200_000
HAY_PRIORS = RUTA_PRIORS.is_file() and DIST.is_dir()


def se_ref(p: float, n: float) -> float:
    pt = (n * p + 1) / (n + 2)
    return math.sqrt(DEFF_REF * pt * (1 - pt) / n)


def csv(nombre: str) -> pd.DataFrame:
    return pd.read_csv(DIST / nombre, dtype=str)


# ================================================================================================
# encogimiento (sin datos)
# ================================================================================================
class TestEncogimiento(unittest.TestCase):
    def test_kish_con_pesos_iguales_es_n(self):
        self.assertAlmostEqual(E.n_efectivo(np.full(37, 2.5)), 37.0)

    def test_kish_con_pesos_desiguales_es_menor_que_n(self):
        w = np.array([1.0, 1.0, 1.0, 10.0])
        self.assertLess(E.n_efectivo(w), len(w))
        self.assertAlmostEqual(E.n_efectivo(w), w.sum() ** 2 / (w ** 2).sum())

    def test_encoger_suma_uno_y_limites(self):
        p, pa = np.array([0.7, 0.2, 0.1]), np.array([0.1, 0.3, 0.6])
        r = E.encoger(p, 40.0, pa, 25.0)
        self.assertAlmostEqual(r.sum(), 1.0)
        np.testing.assert_allclose(E.encoger(p, 40.0, pa, 0.0), p)            # κ → 0: la celda
        np.testing.assert_allclose(E.encoger(p, 40.0, pa, 1e12), pa, atol=1e-9)  # κ → ∞: el padre
        np.testing.assert_allclose(E.encoger(p, 0.0, pa, 25.0), pa)             # sin datos: el padre
        # el peso del padre es κ/(n+κ)
        np.testing.assert_allclose(r, (40 * p + 25 * pa) / 65)

    def test_encoger_conserva_soporte(self):
        r = E.encoger([0.5, 0.5, 0.0], 10.0, [0.5, 0.5, 0.0], 5.0)
        self.assertEqual(r[2], 0.0)                                              # cero en celda y padre → cero
        self.assertGreater(E.encoger([0.5, 0.5, 0.0], 10.0, [0.4, 0.4, 0.2], 5.0)[2], 0.0)  # el padre aporta soporte

    def test_kappa_ml_recupera_kappa_verdadero(self):
        rng = np.random.default_rng(0)
        pi = np.array([0.5, 0.3, 0.2])
        niv = {}
        for c in range(60):
            p = rng.dirichlet(50.0 * pi)                                          # κ verdadero = 50
            conteo = rng.multinomial(400, p)
            niv[c] = E.Stat(conteo / conteo.sum(), 400.0, 400, 400.0)
        r = E.elegir_kappa([E.Problema(pi, [niv], [])])
        self.assertTrue(25 <= r["kappa"] <= 100, r["kappa"])                     # dentro de un factor 2
        self.assertFalse(r["en_frontera"])

    def test_kappa_ml_en_frontera_si_las_celdas_son_identicas_o_muy_distintas(self):
        pi = np.array([0.5, 0.5])
        iguales = {c: E.Stat(pi, 500.0, 500, 500.0) for c in range(10)}
        r = E.elegir_kappa([E.Problema(pi, [iguales], [])])
        self.assertTrue(r["en_frontera"])
        self.assertEqual(r["kappa"], E.KAPPA_GRILLA[-1])                          # celdas idénticas al padre → κ máximo
        dispares = {c: E.Stat(np.array([1.0, 0.0]) if c % 2 else np.array([0.0, 1.0]), 500.0, 500, 500.0) for c in range(10)}
        r2 = E.elegir_kappa([E.Problema(pi, [dispares], [])])
        self.assertTrue(r2["en_frontera"])
        self.assertEqual(r2["kappa"], E.KAPPA_GRILLA[0])                          # celdas opuestas al padre → κ mínimo

    def test_calibrar_nivel_alcanza_el_objetivo_y_conserva_forma(self):
        pi = np.array([[0.7, 0.2, 0.1], [0.2, 0.5, 0.3], [0.1, 0.1, 0.8]])
        w = np.array([5.0, 3.0, 0.0])                                             # una celda sin masa también se reescala
        obj = np.array([0.3, 0.3, 0.4])
        adj = E.calibrar_nivel(pi, w, obj)
        np.testing.assert_allclose(adj.sum(axis=1), 1.0)
        np.testing.assert_allclose((w[:, None] * adj).sum(axis=0) / w.sum(), obj, atol=1e-10)
        # la razón de momios entre dos celdas y dos categorías se conserva (solo cambian los niveles por columna)
        rm = lambda m: (m[0, 0] * m[1, 1]) / (m[0, 1] * m[1, 0])
        self.assertAlmostEqual(rm(pi), rm(adj))

    def test_ipf_ajusta_margenes_y_conserva_razones_de_momios(self):
        s = np.array([[1.0, 2, 3], [4, 5, 6]])
        t = E.ipf(s, [0.4, 0.6], [0.2, 0.3, 0.5])
        np.testing.assert_allclose(t.sum(axis=1), [0.4, 0.6])
        np.testing.assert_allclose(t.sum(axis=0), [0.2, 0.3, 0.5])
        self.assertAlmostEqual((s[0, 0] * s[1, 1]) / (s[0, 1] * s[1, 0]), (t[0, 0] * t[1, 1]) / (t[0, 1] * t[1, 0]))
        with self.assertRaises(ValueError):
            E.ipf(s, [0.4, 0.6], [0.2, 0.3, 0.6])                                 # márgenes incompatibles

    def test_chi2_sf_valores_criticos(self):
        for x, k in [(3.841458820694124, 1), (5.991464547107979, 2), (11.070497693516351, 5), (124.34211340400407, 100)]:
            self.assertAlmostEqual(E.chi2_sf(x, k), 0.05, places=5)
        self.assertEqual(E.chi2_sf(0.0, 3), 1.0)


# ================================================================================================
# priors.json contra las referencias independientes (paso B)
# ================================================================================================
@unittest.skipUnless(HAY_PRIORS, "falta outputs/priors/priors.json: correr tools/construir_priors.py")
class TestPriorsContraReferencia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pj = P.cargar_priors(RUTA_PRIORS)
        cls.orden = cls.pj["orden_celdas"]

    def pooled(self, tabla: dict, masa: dict) -> np.ndarray:
        w = np.array([masa[k] for k in self.orden], dtype=float)
        m = np.array([tabla[k] for k in self.orden], dtype=float)
        return (w[:, None] * m).sum(axis=0) / w.sum()

    def comparar(self, esperado: np.ndarray, ref: np.ndarray, n_ref: float, nombre: str):
        for i, (a, b) in enumerate(zip(esperado, ref)):
            tol = 2 * se_ref(b, n_ref)
            self.assertLessEqual(abs(a - b), tol, f"{nombre}[cat {i}]: prior {a:.5f} vs referencia {b:.5f} (tolerancia {tol:.5f}, n_ref {n_ref:.0f})")
            if b > 0:
                self.assertGreater(a, 0.0, f"{nombre}[cat {i}]: la referencia observó la categoría pero el prior le da probabilidad 0")

    # --- estructura ---
    def _vectores(self):
        pj = self.pj
        for k, v in pj["nc2r"].items():
            yield f"nc2r|{k}", v
        for s, t in pj["p438"].items():
            if t is not None:
                for k, v in t.items():
                    yield f"p438:{s}|{k}", v
        for fam in ("posicion", "formalidad", "tipo_contrato"):
            for k, v in pj[fam].items():
                yield f"{fam}|{k}", v
        for e, v in pj["posicion_nivel_geih_por_estrato"].items():
            yield f"geih|{e}", v

    def test_cada_prior_es_una_distribucion(self):
        n = 0
        for nombre, v in self._vectores():
            v = np.array(v, dtype=float)
            n += 1
            self.assertTrue(np.isfinite(v).all(), nombre)
            self.assertTrue((v >= 0).all(), nombre)
            self.assertAlmostEqual(v.sum(), 1.0, places=9, msg=nombre)
        self.assertGreater(n, 500)

    def test_dimensiones_y_celdas(self):
        pj = self.pj
        self.assertEqual(len(self.orden), 15)
        self.assertEqual(set(self.orden), set(pj["celdas"]))
        self.assertEqual(len(pj["p438"]), 31)                                      # 29 columnas P438 + J14 y K11 explícitos
        self.assertIsNone(pj["p438"]["J14"])
        self.assertIsNone(pj["p438"]["K11"])
        self.assertEqual(sum(t is not None for t in pj["p438"].values()), 29)
        for k in self.orden:
            self.assertEqual(len(pj["nc2r"][k]), len(pj["categorias"]["nc2r"]["codigos"]))
            self.assertEqual(len(pj["posicion"][k]), len(P.POS_CATS))
        self.assertEqual(pj["meta"]["semilla"], 42)
        self.assertTrue(all(v["kappa"] > 0 for v in pj["kappa"].values()))

    def test_los_esquemas_de_codigos_no_se_mezclan(self):
        cat = self.pj["categorias"]
        self.assertEqual(cat["nc2r"]["etiquetas"]["4"], "Fiado")      # NC2R: 4 = fiado
        self.assertEqual(cat["p438"]["etiquetas"]["4"], "Bonos")      # P438: 4 = bonos
        self.assertEqual(cat["posicion"]["codigos"][-1], "otros")     # P6430: 7-9 se agrupan; los esquemas GEIH y ENPH difieren desde el 7

    # --- masas de celda, bancarización, ICGU ---
    def test_masas_de_celda_son_las_del_csv(self):
        ref = csv("enph_estrato_x_quintil.csv")
        tot = ref["expandido"].astype(float).sum()
        for r in ref.itertuples():
            c = self.pj["celdas"][P.clave(r.estrato_agrupado, int(r.quintil[1]))]
            self.assertEqual(c["n_hogares"], int(r.n))
            self.assertAlmostEqual(c["masa_hogares"] / float(r.expandido), 1.0, places=9)
            self.assertAlmostEqual(c["p_celda_todos"], float(r.expandido) / tot, places=9)

    def test_repeso_bancarizado_es_el_del_csv_y_p_banc_es_el_de_geih(self):
        ref = csv("enph_estrato_x_quintil_bancarizado.csv")
        for r in ref.itertuples():
            c = self.pj["celdas"][P.clave(r.estrato_agrupado, int(r.quintil[1]))]
            self.assertAlmostEqual(100 * c["p_celda_bancarizado"], float(r.pct_del_cruce_bancarizado), places=7)
        g = csv("geih_bancarizacion_x_estrato.csv")
        g = g[g["tenencia"] == "con_producto"].set_index("estrato_agrupado")["pct_dentro_de_estrato"].astype(float) / 100
        for e, p in self.pj["bancarizacion"]["p_bancarizado_estrato"].items():
            self.assertAlmostEqual(p, g[e], places=9)

    def test_rangos_de_icgu_por_quintil_son_los_del_csv(self):
        ref = csv("enph_ingreso_quintil.csv").set_index("quintil")
        for k, c in self.pj["celdas"].items():
            self.assertAlmostEqual(c["icgu_min_quintil"], float(ref.loc[f"Q{c['quintil']}", "icgu_min"]), places=4)
            self.assertAlmostEqual(c["icgu_max_quintil"], float(ref.loc[f"Q{c['quintil']}", "icgu_max"]), places=4)

    def test_piramide_bancarizada_suma_las_celdas_del_csv(self):
        ref = csv("enph_estrato_x_quintil_bancarizado.csv")
        ref["pct"] = ref["pct_del_cruce_bancarizado"].astype(float)
        por_e = ref.groupby("estrato_agrupado")["pct"].sum()
        for e in P.ESTRATOS:
            mio = 100 * sum(c["p_celda_bancarizado"] for c in self.pj["celdas"].values() if c["estrato"] == e)
            self.assertAlmostEqual(mio, por_e[e], places=7)

    # --- marginales de Bogotá ---
    def test_nc2r_reproduce_el_marginal_de_bogota(self):
        r = csv("enph_forma_pago_nc2r.csv")
        r = r[r["codigo"].isin(P.NC2R_CATS)].set_index("codigo")
        ref = np.array([float(r.loc[c, "% base con respuesta"]) / 100 for c in P.NC2R_CATS])
        n = r["n (sin ponderar)"].astype(float).sum()
        self.comparar(self.pooled(self.pj["nc2r"], self.pj["masa_respuesta"]["nc2r"]), ref, n, "nc2r")

    def test_p438_reproduce_el_marginal_de_bogota_por_subcapitulo(self):
        m = pd.read_csv(DIST / "enph_p438_matriz_categoria_x_medio.csv").set_index("subcapitulo")
        cols = [self.pj["categorias"]["p438"]["etiquetas"][c] for c in P.P438_CATS]
        hechos = 0
        for s, tabla in self.pj["p438"].items():
            if tabla is None:
                self.assertNotIn(s, m.index)                                          # J14 y K11 no tienen columna P438
                continue
            self.comparar(self.pooled(tabla, self.pj["masa_respuesta"]["p438"][s]), np.array([m.loc[s, c] / 100 for c in cols]),
                          float(m.loc[s, "n_con_respuesta"]), f"p438:{s}")
            hechos += 1
        self.assertEqual(hechos, 29)

    def test_masa_de_respuesta_p438_es_coherente_con_la_cobertura(self):
        """La masa en celdas no puede superar a la de la cobertura; la diferencia es, a lo sumo, la masa de los hogares sin estrato 1-6 o sin ICGU."""
        cob = pd.read_csv(DIST / "enph_p438_cobertura.csv").set_index("subcapitulo")
        total = float((cob["hogares_expandidos_con_respuesta"] / (cob["pct_hogares_bogota_con_respuesta"] / 100)).iloc[0])
        en_celdas = sum(c["masa_hogares"] for c in self.pj["celdas"].values())
        excluida = total - en_celdas
        self.assertGreaterEqual(excluida, -1e-6)
        for s, masa in self.pj["masa_respuesta"]["p438"].items():
            w, cobertura = sum(masa.values()), float(cob.loc[s, "hogares_expandidos_con_respuesta"])
            self.assertLessEqual(w, cobertura * (1 + 1e-9), s)
            self.assertGreaterEqual(w, cobertura - excluida - 1e-6, s)

    def test_posicion_reproduce_el_marginal_geih(self):
        r = csv("geih_posicion_ocupacional.csv").set_index("codigo")
        p = {c: float(r.loc[c, "% base con respuesta"]) / 100 for c in r.index}
        ref = np.array([p["1"], p["2"], p["3"], p["4"], p["5"], p["6"], p["7"] + p["8"]])   # GEIH 7 y 8 → «otros»
        pos = np.zeros(len(P.POS_CATS))
        for e in P.ESTRATOS:
            m = self.pj["masa_personas_ocupadas_enph_por_quintil"][e]
            for i, q in enumerate(P.QUINTILES):
                pos += self.pj["mezcla_ocupados_geih_por_estrato"][e] * m[i] * np.array(self.pj["posicion"][P.clave(e, q)])
        self.comparar(pos, ref, r["n (sin ponderar)"].astype(float).sum(), "posicion")

    def _joint_marginal(self, masa_clave, posiciones):
        """Marginales P6440, P6920, P6990 del prior conjunto, agregando (estrato, posición) con la masa GEIH."""
        fcat = self.pj["categorias"]["formalidad"]["codigos"]
        w = {k: self.pj["masa_respuesta"]["formalidad"][k] for k in self.pj["formalidad"] if k.split("|")[1] in posiciones}
        tot = sum(w.values())
        joint = sum(w[k] * np.array(self.pj["formalidad"][k]) for k in w) / tot
        out = {}
        for j, var in enumerate(P.FORM_VARS):
            d = {}
            for c, v in zip(fcat, joint):
                d[c.split("|")[j]] = d.get(c.split("|")[j], 0.0) + v
            out[var] = d
        return out

    def test_formalidad_reproduce_los_marginales_geih(self):
        r = csv("geih_formalidad_componentes.csv")
        mio = self._joint_marginal(None, set(P.POS_CATS))
        for var in P.FORM_VARS:
            sub = r[(r["variable"] == var) & (r["tipo"] == "respuesta")]
            n = sub["n"].astype(float).sum()
            cats = list(sub["codigo"])
            self.comparar(np.array([mio[var][c] for c in cats]), np.array([float(x) / 100 for x in sub["pct_con_respuesta"]]), n, var)

    def test_tipo_de_contrato_reproduce_el_marginal_geih(self):
        r = csv("geih_formalidad_componentes.csv")
        sub = r[(r["variable"] == "P6450") & (r["tipo"] == "respuesta")].set_index("codigo")
        w = self.pj["masa_respuesta"]["tipo_contrato"]
        pooled = sum(w[k] * np.array(self.pj["tipo_contrato"][k]) for k in w) / sum(w.values())
        ref = np.array([float(sub.loc[c, "pct_con_respuesta"]) / 100 for c in P.TC_CATS])
        self.comparar(pooled, ref, sub["n"].astype(float).sum(), "P6450")

    def test_pension_dada_la_posicion_reproduce_el_cruce_geih(self):
        r = csv("geih_posicion_x_pension.csv")
        for pos in ["1", "2", "3", "4", "5", "6"]:
            mio = self._joint_marginal(None, {pos})["P6920"]
            sub = r[r["P6430"] == pos].set_index("P6920")
            ref = np.array([float(sub.loc[c, "pct_dentro_de_posicion"]) / 100 if c in sub.index else 0.0 for c in ["1", "2", "3"]])
            self.comparar(np.array([mio[c] for c in ["1", "2", "3"]]), ref, sub["n"].astype(float).sum(), f"P6920|posición {pos}")

    def test_la_posicion_depende_del_quintil_dentro_del_estrato(self):
        """Decisión 4: la dependencia ocupación × quintil | estrato existe en ENPH; el prior no puede ser plano en el quintil."""
        for e in ("bajo (1-2)", "medio (3-4)"):
            q1, q4 = np.array(self.pj["posicion"][P.clave(e, 1)]), np.array(self.pj["posicion"][P.clave(e, 4)])
            self.assertGreater(np.abs(q1 - q4).max(), 1e-3, e)

    def test_el_prior_es_mas_ralo_en_alto_q1_q4_que_en_medio_q5(self):
        """Las celdas ralas se parecen más a su padre que a su dato: con n_ef pequeño, el peso del padre en P438 debe ser mayor."""
        s = pd.read_csv(RAIZ / "outputs" / "priors" / "soporte_celdas.csv")
        p4 = s[s["familia"] == "p438"].groupby(["estrato_agrupado", "quintil"])["peso_padre"].median()
        self.assertGreater(p4[("alto (5-6)", "Q1")], p4[("medio (3-4)", "Q5")])


# ================================================================================================
# muestreador (paso A)
# ================================================================================================
@unittest.skipUnless(HAY_PRIORS, "falta outputs/priors/priors.json: correr tools/construir_priors.py")
class TestMuestreo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pj = P.cargar_priors(RUTA_PRIORS)
        cls.s = P.muestrear_perfiles(cls.pj, N_MC, seed=42)
        cls.orden = cls.pj["orden_celdas"]

    def z(self, observado: np.ndarray, esperado: np.ndarray, n: int, limite: float, nombre: str):
        for i, (o, p) in enumerate(zip(observado, esperado)):
            if p == 0:
                self.assertEqual(o, 0.0, f"{nombre}[{i}]: categoría de probabilidad 0 fue sorteada")
                continue
            se = math.sqrt(p * (1 - p) / n)
            if se > 0:
                self.assertLessEqual(abs(o - p), limite * se, f"{nombre}[{i}]: observado {o:.5f} vs esperado {p:.5f} (SE_MC {se:.5f}, n {n})")

    def freq(self, df: pd.DataFrame, col: str, cats: list) -> np.ndarray:
        return np.array([(df[col] == c).mean() for c in cats])

    def test_determinista_y_prefijo_estable(self):
        a = P.muestrear_perfiles(self.pj, 500, seed=42)
        self.assertTrue(a.equals(P.muestrear_perfiles(self.pj, 500, seed=42)))
        self.assertTrue(P.muestrear_perfiles(self.pj, 100, seed=42).equals(a.iloc[:100].reset_index(drop=True)))
        self.assertFalse(a.equals(P.muestrear_perfiles(self.pj, 500, seed=43)))
        self.assertTrue(self.s.iloc[:500].reset_index(drop=True).equals(a))

    def test_piramide_de_estratos_de_bogota(self):
        """La pirámide muestreada es la de los hogares bancarizados del CSV (no la de todos los hogares: D15 la desplaza)."""
        ref = csv("enph_estrato_x_quintil_bancarizado.csv")
        ref["pct"] = ref["pct_del_cruce_bancarizado"].astype(float) / 100
        esperado = ref.groupby("estrato_agrupado")["pct"].sum()
        self.z(self.freq(self.s, "estrato_agrupado", P.ESTRATOS), np.array([esperado[e] for e in P.ESTRATOS]), N_MC, 4, "pirámide")

    def test_celdas_estrato_por_quintil(self):
        ref = csv("enph_estrato_x_quintil_bancarizado.csv")
        esp, obs = [], []
        for r in ref.itertuples():
            esp.append(float(r.pct_del_cruce_bancarizado) / 100)
            obs.append(((self.s["estrato_agrupado"] == r.estrato_agrupado) & (self.s["quintil"] == r.quintil)).mean())
        self.z(np.array(obs), np.array(esp), N_MC, 4, "celdas")

    def test_icgu_del_perfil_es_el_rango_de_su_quintil(self):
        g = self.s.groupby("quintil")[["icgu_min_quintil", "icgu_max_quintil"]].nunique()
        self.assertTrue((g == 1).all().all())

    def _por_celda(self, col, cats, tabla, minimo=3000, limite=5):
        hechos = 0
        for k in self.orden:
            c = self.pj["celdas"][k]
            g = self.s[(self.s["estrato_agrupado"] == c["estrato"]) & (self.s["quintil"] == f"Q{c['quintil']}")]
            if len(g) >= minimo:
                self.z(self.freq(g, col, cats), np.array(tabla[k]), len(g), limite, f"{col}|{k}")
                hechos += 1
        return hechos

    def test_nc2r_por_celda(self):
        self.assertGreaterEqual(self._por_celda("nc2r_forma_pago", P.NC2R_CATS, self.pj["nc2r"]), 10)

    def test_posicion_por_celda(self):
        self.assertGreaterEqual(self._por_celda("posicion_ocupacional", P.POS_CATS, self.pj["posicion"]), 10)

    def test_p438_por_celda_y_vacios(self):
        hechos = 0
        for s, tabla in self.pj["p438"].items():
            col = f"p438_{s}"
            if tabla is None:
                self.assertTrue(self.s[col].isna().all(), col)                      # J14 y K11: vacías, no inventadas
                continue
            self.assertTrue(self.s[col].isin(P.P438_CATS).all(), col)
            hechos += self._por_celda(col, P.P438_CATS, tabla, minimo=20000)
        self.assertGreater(hechos, 29)

    def test_formalidad_dada_estrato_y_posicion(self):
        fcat = self.pj["categorias"]["formalidad"]["codigos"]
        self.s["_form"] = self.s["P6440"] + "|" + self.s["P6920"] + "|" + self.s["P6990"]
        hechos = 0
        for e in P.ESTRATOS:
            for p in P.POS_CATS:
                g = self.s[(self.s["estrato_agrupado"] == e) & (self.s["posicion_ocupacional"] == p)]
                if len(g) >= 3000:
                    self.z(self.freq(g, "_form", fcat), np.array(self.pj["formalidad"][f"{e}|{p}"]), len(g), 5, f"formalidad|{e}|{p}")
                    h = g[g["P6440"] == "1"]
                    self.z(self.freq(h, "P6450", P.TC_CATS), np.array(self.pj["tipo_contrato"][f"{e}|{p}"]), len(h), 5, f"tipo_contrato|{e}|{p}")
                    hechos += 1
        self.assertGreaterEqual(hechos, 5)

    def test_tipo_de_contrato_solo_existe_si_hay_contrato(self):
        self.assertTrue(self.s.loc[self.s["P6440"] != "1", "P6450"].isna().all())
        self.assertTrue(self.s.loc[self.s["P6440"] == "1", "P6450"].isin(P.TC_CATS).all())

    def test_codigos_validos(self):
        self.assertTrue(self.s["nc2r_forma_pago"].isin(P.NC2R_CATS).all())
        self.assertTrue(self.s["posicion_ocupacional"].isin(P.POS_CATS).all())
        self.assertTrue(self.s["P6440"].isin(P.FORM_VALIDOS["P6440"]).all())
        self.assertTrue(self.s["P6920"].isin(P.FORM_VALIDOS["P6920"]).all())
        self.assertTrue(self.s["P6990"].isin(P.FORM_VALIDOS["P6990"]).all())


# ================================================================================================
# reconstrucción desde los microdatos (lenta: ~25 s) — el priors.json del repo debe ser el que sale de los datos
# ================================================================================================
HAY_DATOS = (RAIZ / "data" / "raw" / "ENPH_2017").is_dir() and (RAIZ / "data" / "raw" / "GEIH_2025").is_dir()


@unittest.skipUnless(HAY_PRIORS and HAY_DATOS and not os.environ.get("SDG_SALTAR_RECONSTRUCCION"),
                     "faltan data/raw o priors.json (o SDG_SALTAR_RECONSTRUCCION=1)")
class TestReconstruccion(unittest.TestCase):
    def test_priors_json_coincide_con_la_reconstruccion(self):
        ins = P.cargar_insumos()
        res = P.construir(ins)
        nuevo = P.serializar(P.construir_priors_json(ins, res, P.tabla_celdas(ins)))
        self.assertEqual(P.sha256_texto(nuevo), P.sha256_texto(RUTA_PRIORS.read_text(encoding="utf-8")),
                         "outputs/priors/priors.json está desactualizado: correr tools/construir_priors.py")

    def test_cortes_de_quintil_son_los_de_bogota(self):
        ins = P.cargar_insumos()
        ref = csv("enph_ingreso_quintil.csv")
        # el quintil k queda delimitado por los cortes; el máximo observado de Q1..Q4 no puede superar su corte
        for k, c in enumerate(ins.cortes_icgu, start=1):
            self.assertLessEqual(float(ref.loc[ref["quintil"] == f"Q{k}", "icgu_max"].iloc[0]), c + 1e-6)


if __name__ == "__main__":
    unittest.main()
