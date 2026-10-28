"""Tests del generador por reglas (WP6): src/sdg/generador.py, src/sdg/comercios.py y las tablas de docs/generador/.

Ejecutar desde la raíz:  .venv\\Scripts\\python.exe -m unittest tests.test_generador -v     (o discover -s tests)

Tres bloques:
  1. SIN microdatos ni pool: reglas puras (plan de reposición, donantes, cuentas, migración digital, contraparte), tablas versionadas
     (n2 válidos contra la taxonomía, cobertura del catálogo de comercios, parámetros con fuente) y el generador completo sobre un POOL SINTÉTICO
     construido aquí (pocas decenas de hogares). Las invariantes se prueban sobre esa muestra: esquema y enums, enlace interna↔emitida,
     efectivo no emitido, retiros que cubren el efectivo, pares de recarga y de pago de tarjeta, determinismo.
  2. Con el pool real (outputs/generador/pool/, lo escribe tools/construir_generador.py): se omite si no existe.
  3. Calibración con microdatos (sdg.gasto_enph): se omite si no hay data/raw. Comprueba invariantes y una banda amplia de reconciliación con
     GCMUG (consistencia interna, NO validación: salen del mismo insumo).
Lo que NO se prueba aquí: que el gasto o la participación digital sean los de 2025 (la participación digital no tiene fuente primaria) ni
que las plantillas imiten a los extractos reales (D14: los reales solo se usan para evaluar).
"""
import json
import re
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sdg import comercios as CM  # noqa: E402
from sdg import generador as G  # noqa: E402
from sdg import priors as PR  # noqa: E402

DIR_PARAM = RAIZ / "docs" / "generador"
RUTA_TAXONOMIA = RAIZ / "docs" / "taxonomia" / "taxonomia_gastos_colombia_v1.json"
HAY_PRIORS = PR.RUTA_PRIORS.is_file()
HAY_POOL = (G.DIR_POOL / "eventos.csv.gz").is_file() and (G.DIR_SALIDA / "mezcla_donantes.json").is_file()
HAY_MICRODATOS = (RAIZ / "data" / "raw" / "ENPH_2017" / "hogares" / "viviendas_hogares.csv").is_file()

MEDIOS = ["efectivo", "billetera_digital", "tarjeta_debito", "tarjeta_credito", "transferencia_bancaria", "fiado_credito_tienda", "bono_subsidio", "otro_nd"]
FORMALIDAD = ["formal", "informal", "pequeno_comercio_indeterminado", "no_aplica"]


def taxonomia() -> dict:
    t = json.loads(RUTA_TAXONOMIA.read_text(encoding="utf-8"))
    return {c["id"]: {s["id"] if isinstance(s, dict) else s for s in c["subtipos"]} for c in t["categorias_nivel_1"]}


def pool_sintetico(seed: int = 0, hogares_por_celda: int = 4) -> G.Pool:
    """Pool mínimo con la misma forma que el real. Los números no significan nada: solo ejercitan el código."""
    rng = np.random.default_rng(seed)
    tax = taxonomia()
    lug = pd.read_csv(DIR_PARAM / "lugares_compra.csv", dtype=str, keep_default_na=False)
    celdas = [f"{e}|Q{q}" for e in PR.ESTRATOS for q in PR.QUINTILES]
    hog, ev, rec = [], [], []
    caps = ["A11", "B11", "D11", "E11", "H11", "J11"]
    for c in celdas:
        e, q = c.split("|Q")
        for k in range(hogares_por_celda):
            d = f"H{len(hog):04d}"
            hog.append(dict(DIRECTORIO=d, FEX=float(rng.uniform(300, 3000)), estrato_agrupado=e, quintil=int(q), celda=c, con_celda=True,
                            icmdug=float(rng.uniform(0.6e6, 6e6)) if k else 0.0, factor_ipc_total=1.6))
            for cat in G.CATEGORIAS_GASTO:
                for _ in range(int(rng.integers(0, 5))):
                    f = float(rng.choice([30 / 14, 30 / 7, 1.0, 1 / 3, 1 / 12, 0.5]))
                    l = lug.sample(1, random_state=int(rng.integers(0, 10**6))).iloc[0]
                    n2 = sorted(tax[cat])[int(rng.integers(0, len(tax[cat])))]
                    ev.append(dict(DIRECTORIO=d, FEX=hog[-1]["FEX"], fuente=str(rng.choice(["diario_hogar", "cf_hogar", "personal", "menos_frecuente"])),
                                   tipo="cesta", cap=str(rng.choice(caps)), lugar=l["codigo"], clase_comercio=l["clase_comercio"], categoria_n1=cat,
                                   categoria_n2=n2, valor=float(np.exp(rng.normal(9.5, 1.0))), factor=f, factor_ipc=1.5, domicilio=int(rng.random() < 0.1)))
            if rng.random() < 0.6:
                rec.append(dict(DIRECTORIO=d, FEX=hog[-1]["FEX"], concepto="arriendo", categoria_n1="vivienda_servicios", categoria_n2="arriendo",
                                valor=float(rng.uniform(2e5, 1.2e6)), factor=1.0, factor_ipc=1.5))
            rec.append(dict(DIRECTORIO=d, FEX=hog[-1]["FEX"], concepto="energia", categoria_n1="vivienda_servicios", categoria_n2="servicios_publicos",
                            valor=float(rng.uniform(3e4, 2e5)), factor=float(rng.choice([1.0, 0.5])), factor_ipc=1.5))
            rec.append(dict(DIRECTORIO=d, FEX=hog[-1]["FEX"], concepto="internet_fijo", categoria_n1="telecom_conectividad", categoria_n2="internet_hogar_tv",
                            valor=float(rng.uniform(3e4, 1.2e5)), factor=1.0, factor_ipc=1.5))
            if rng.random() < 0.2:
                rec.append(dict(DIRECTORIO=d, FEX=hog[-1]["FEX"], concepto="cuota_vivienda", categoria_n1="obligaciones_financieras", categoria_n2="credito_formal",
                                valor=float(rng.uniform(4e5, 1.5e6)), factor=1.0, factor_ipc=1.5))
    mezcla = {c: dict(celda=0.5, quintil=0.3, bogota=0.2) for c in celdas}
    cuentas = []
    for e in PR.ESTRATOS:
        for (b, w, t), p in {(1, 0, 0): 0.3, (1, 1, 0): 0.3, (1, 1, 1): 0.2, (0, 1, 0): 0.1, (1, 0, 1): 0.1}.items():
            cuentas.append(dict(estrato_agrupado=e, banco=b, billetera=w, tc=t, p=p))
    return G.Pool(pd.DataFrame(ev)[G.COLS_EVENTOS], pd.DataFrame(rec)[G.COLS_REC], pd.DataFrame(hog)[G.COLS_HOG], mezcla, pd.DataFrame(cuentas),
                  dict(ipc_aplicado=False, modo_ipc="division"))


# ================================================================================================
# 1a. reglas puras
# ================================================================================================
class TestPlanReposicion(unittest.TestCase):
    KW = dict(umbral=3, horizonte=7, multiplo=50_000, minimo=50_000, maximo=1_000_000)

    def _caso(self, rng):
        n = int(rng.integers(1, 25))
        dias = np.sort(rng.integers(1, 31, size=n))
        montos = rng.integers(1, 400, size=n) * 1000
        return dias, montos

    def test_sin_salidas_no_repone(self):
        self.assertEqual(G.plan_reposicion(np.array([], dtype=int), np.array([], dtype=int), **self.KW), [])

    def test_cubre_el_gasto_acumulado_cada_dia(self):
        rng = np.random.default_rng(1)
        for _ in range(300):
            dias, montos = self._caso(rng)
            rep = G.plan_reposicion(dias, montos, **self.KW)
            for d in np.unique(dias):
                self.assertGreaterEqual(sum(m for dd, m in rep if dd <= d), montos[dias <= d].sum(), f"día {d}: el retiro acumulado no cubre el gasto")

    def test_montos_en_multiplos_con_minimo_y_maximo(self):
        rng = np.random.default_rng(2)
        for _ in range(300):
            dias, montos = self._caso(rng)
            for d, m in G.plan_reposicion(dias, montos, **self.KW):
                self.assertEqual(m % self.KW["multiplo"], 0)
                self.assertGreaterEqual(m, self.KW["minimo"])
                self.assertLessEqual(m, self.KW["maximo"])

    def test_solo_repone_en_dias_con_salida_y_no_en_exceso(self):
        rng = np.random.default_rng(3)
        for _ in range(300):
            dias, montos = self._caso(rng)
            rep = G.plan_reposicion(dias, montos, **self.KW)
            self.assertTrue({d for d, _ in rep} <= set(dias.tolist()))
            exceso = sum(m for _, m in rep) - montos.sum()
            self.assertGreaterEqual(exceso, 0)
            self.assertLess(exceso, self.KW["multiplo"], "al cierre del mes sobra menos de un múltiplo de retiro")

    def test_gasto_grande_se_parte_en_tramos_del_maximo(self):
        rep = G.plan_reposicion(np.array([5]), np.array([2_600_000]), **self.KW)
        self.assertEqual(sum(m for _, m in rep), 2_600_000 if 2_600_000 % 50_000 == 0 else 2_650_000)
        self.assertTrue(all(m <= 1_000_000 for _, m in rep))
        self.assertEqual(len(rep), 3)

    def test_determinista(self):
        dias, montos = np.array([1, 1, 4, 9, 20]), np.array([30_000, 25_000, 80_000, 10_000, 120_000])
        self.assertEqual(G.plan_reposicion(dias, montos, **self.KW), G.plan_reposicion(dias, montos, **self.KW))


class TestRedondeo(unittest.TestCase):
    def test_redondeo_y_piso(self):
        self.assertEqual(G.redondear(np.array([149.0, 151.0, 20.0]), 100).tolist(), [100, 200, 100])


class TestAnalisisDeParametros(unittest.TestCase):
    def test_todo_parametro_declara_fuente(self):
        crudo = json.loads(G.RUTA_PARAMETROS.read_text(encoding="utf-8"))
        hojas = []

        def recorre(d, ruta):
            for k, v in d.items():
                if isinstance(v, dict) and "valor" in v:
                    hojas.append((ruta + [k], v))
                elif isinstance(v, dict):
                    recorre(v, ruta + [k])

        recorre(crudo, [])
        self.assertGreater(len(hojas), 40)
        for ruta, v in hojas:
            self.assertTrue(v.get("fuente"), f"{'.'.join(ruta)} sin fuente")

    def test_override_inexistente_es_error(self):
        with self.assertRaises(KeyError):
            G.cargar_parametros(overrides={"digital.escenarioo": "alto"})

    def test_escenarios_digitales_ordenados(self):
        par, _ = G.cargar_parametros()
        e = par["digital.escenarios"]
        self.assertLess(e["bajo"], e["base"])
        self.assertLess(e["base"], e["alto"])
        self.assertIn(par["digital.escenario"], e)


class TestTablas(unittest.TestCase):
    def test_n2_validos_contra_la_taxonomia(self):
        tax = taxonomia()
        for nombre in ("mapeo_coicop_taxonomia_provisional.csv", "comercios_curados.csv"):
            t = pd.read_csv(DIR_PARAM / nombre, dtype=str, keep_default_na=False)
            self.assertTrue(t["categoria_n1"].isin(list(tax)).all(), nombre)
            for r in t[t["categoria_n2"] != ""].itertuples():
                self.assertIn(r.categoria_n2, tax[r.categoria_n1], f"{nombre}: {r.categoria_n1}.{r.categoria_n2}")

    def test_mapeo_cubre_las_doce_divisiones(self):
        t = pd.read_csv(DIR_PARAM / "mapeo_coicop_taxonomia_provisional.csv", dtype=str, keep_default_na=False)
        for d in [f"{i:02d}" for i in range(0, 13)]:
            self.assertIn(d, set(t["prefijo"]), f"división {d} sin mapeo por defecto")

    def test_catalogo_cubre_las_doce_categorias_de_gasto(self):
        c = pd.read_csv(DIR_PARAM / "comercios_curados.csv", dtype=str, keep_default_na=False)
        for cat in G.CATEGORIAS_GASTO:
            self.assertTrue(((c["categoria_n1"] == cat) & (c["concepto"] == "")).any(), cat)

    def test_pesos_y_marcadores_del_catalogo(self):
        c = pd.read_csv(DIR_PARAM / "comercios_curados.csv", dtype=str, keep_default_na=False)
        self.assertTrue((c["peso"].astype(float) > 0).all())
        self.assertTrue(c["canal"].isin(["presencial", "linea", "ambos"]).all())
        self.assertFalse(c["nombre"].str.contains(r"\d{6,}").any())

    def test_cada_tipo_de_evento_tiene_plantilla_y_marcadores_conocidos(self):
        pl = CM.Plantillas(DIR_PARAM)
        esperados = {"compra_debito", "compra_credito", "pago_pse", "compra_billetera", "p2p_enviada_banco", "p2p_recibida_banco", "p2p_enviada_billetera",
                     "p2p_recibida_billetera", "retiro_atm_banco", "retiro_corresponsal_banco", "retiro_atm_billetera", "retiro_corresponsal_billetera",
                     "recarga_origen", "recarga_destino", "pago_tc_origen", "pago_tc_destino", "nomina", "ingreso_consignacion"}
        self.assertTrue(esperados <= set(pl.tipos()), esperados - set(pl.tipos()))
        for p in pl.tabla["plantilla"]:
            self.assertFalse(set(re.findall(r"\{(\w+)\}", p)) - {"C", "B", "W", "Wt", "E"}, p)

    def test_lugares_clases_y_aceptacion(self):
        l = G.cargar_lugares()
        self.assertEqual(int(l.loc["persona", "acepta_tarjeta"]), 0)
        self.assertEqual(int(l.loc["cadena", "acepta_tarjeta"]), 1)
        self.assertTrue(set(l["formalidad_comercio"]) <= set(FORMALIDAD))

    def test_permisos_digitales_cubren_las_categorias(self):
        p = pd.read_csv(DIR_PARAM / "permisos_medios_digitales.csv")
        self.assertEqual(set(p["categoria_n1"]), set(G.CATEGORIAS_GASTO))
        self.assertTrue((p[["peso_billetera", "peso_transferencia"]] >= 0).all().all())


class TestComercios(unittest.TestCase):
    def setUp(self):
        self.c = CM.Comercios(DIR_PARAM, p_sucursal=1.0)

    def _ev(self, **kw):
        base = dict(categoria_n1="alimentos_mercado", categoria_n2="supermercado_cadena", clase_comercio="cadena", linea=False, concepto="", sucursal_ok=True)
        return pd.DataFrame([base | kw] * 40)

    def test_sin_marcadores_sin_resolver(self):
        rng = np.random.default_rng(0)
        for cat in G.CATEGORIAS_GASTO:
            for clase in ("cadena", "tienda_barrio", "persona", "internet", "desconocido"):
                r = self.c.asignar(rng, self._ev(categoria_n1=cat, categoria_n2="", clase_comercio=clase, linea=clase == "internet"))
                self.assertFalse(r["comercio"].str.contains(r"[{}]").any(), (cat, clase))
                self.assertTrue((r["comercio"].str.len() > 2).all())

    def test_domicilios_salen_de_apps(self):
        rng = np.random.default_rng(0)
        r = self.c.asignar(rng, self._ev(categoria_n1="comidas_fuera", categoria_n2="domicilios_app", clase_comercio="restaurante", linea=True))
        self.assertTrue(r["comercio"].str.contains("RAPPI|DIDI|IFOOD").all())

    def test_concepto_usa_la_empresa_del_servicio(self):
        rng = np.random.default_rng(0)
        r = self.c.asignar(rng, self._ev(categoria_n1="vivienda_servicios", categoria_n2="servicios_publicos", clase_comercio="especializado", concepto="energia"))
        self.assertTrue(r["comercio"].str.contains("ENEL").all())

    def test_sucursal_solo_si_sucursal_ok(self):
        rng = np.random.default_rng(0)
        con = self.c.asignar(rng, self._ev(sucursal_ok=True))["comercio"]
        sin = self.c.asignar(rng, self._ev(sucursal_ok=False))["comercio"]
        self.assertGreater(con.str.len().mean(), sin.str.len().mean())

    def test_determinista(self):
        a = self.c.asignar(np.random.default_rng(5), self._ev())
        b = self.c.asignar(np.random.default_rng(5), self._ev())
        pd.testing.assert_frame_equal(a, b)


# ================================================================================================
# 1b. donantes, cuentas, migración
# ================================================================================================
class TestDonantes(unittest.TestCase):
    def setUp(self):
        self.pool = pool_sintetico()

    def test_proporciones_de_la_mezcla_y_pertenencia(self):
        dn = G.Donantes(self.pool.hogares, self.pool.mezcla)
        celda = "medio (3-4)|Q3"
        d = dn.muestrear(np.random.default_rng(0), np.array([celda] * 80_000, dtype=object))
        hog = self.pool.hogares
        h = hog.set_index("DIRECTORIO")
        m = self.pool.mezcla[celda]
        # esperado exacto: los niveles quintil y Bogotá también pueden caer en la celda propia / el quintil propio, según los FEX
        f_all, f_q, f_c = hog["FEX"].sum(), hog.loc[hog["quintil"] == 3, "FEX"].sum(), hog.loc[hog["celda"] == celda, "FEX"].sum()
        esperado_celda = m["celda"] + m["quintil"] * f_c / f_q + m["bogota"] * f_c / f_all
        esperado_q = m["celda"] + m["quintil"] + m["bogota"] * f_q / f_all
        self.assertAlmostEqual((h.loc[d, "celda"] == celda).mean(), esperado_celda, delta=0.01)
        self.assertAlmostEqual((h.loc[d, "quintil"] == 3).mean(), esperado_q, delta=0.01)

    def test_pesos_fex_dentro_de_un_nivel(self):
        h = pd.DataFrame({"DIRECTORIO": ["a", "b"], "FEX": [1.0, 9.0], "celda": ["bajo (1-2)|Q1"] * 2, "con_celda": True, "icmdug": 1.0})
        dn = G.Donantes(h, {"bajo (1-2)|Q1": dict(celda=1.0, quintil=0.0, bogota=0.0)})
        d = dn.muestrear(np.random.default_rng(0), np.array(["bajo (1-2)|Q1"] * 20_000, dtype=object))
        self.assertAlmostEqual((d == "b").mean(), 0.9, delta=0.01)

    def test_exigir_ingreso_excluye_hogares_sin_ingreso(self):
        dn = G.Donantes(self.pool.hogares, self.pool.mezcla, exigir_ingreso=True)
        d = dn.muestrear(np.random.default_rng(0), np.array(["bajo (1-2)|Q1"] * 5_000, dtype=object))
        h = self.pool.hogares.set_index("DIRECTORIO")
        self.assertTrue((h.loc[d, "icmdug"] > 0).all())

    def test_celda_inexistente_en_la_mezcla_es_error(self):
        dn = G.Donantes(self.pool.hogares, self.pool.mezcla)
        with self.assertRaises(KeyError):
            dn.muestrear(np.random.default_rng(0), np.array(["xx|Q9"], dtype=object))


@unittest.skipUnless(HAY_PRIORS, "falta outputs/priors/priors.json")
class TestCuentasYMigracion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.priors = PR.cargar_priors()
        cls.pool = pool_sintetico()
        cls.par, _ = G.cargar_parametros()

    def perfiles(self, n):
        p = PR.muestrear_perfiles(self.priors, n, 42)
        return p

    def test_cuentas_respetan_la_estructura_por_estrato(self):
        p = self.perfiles(30_000)
        cu = G.asignar_cuentas(np.random.default_rng(0), p, self.pool.cuentas, self.par)
        for e, g in cu.groupby(p["estrato_agrupado"]):
            t = self.pool.cuentas[self.pool.cuentas["estrato_agrupado"] == e]
            self.assertAlmostEqual(g["billetera"].mean(), float((t["p"] * t["billetera"]).sum()), delta=0.015)
            self.assertAlmostEqual(g["tc"].mean(), float((t["p"] * t["tc"]).sum()), delta=0.015)
        self.assertTrue(((cu["banco"] + cu["billetera"]) >= 1).all(), "todo perfil debe tener al menos una cuenta que emita")
        self.assertTrue((cu.loc[cu["tc"] == 1, "banco"] == 1).all(), "la tarjeta de crédito implica un banco")

    def test_modo_una_cuenta(self):
        p = self.perfiles(5_000)
        par = dict(self.par) | {"cuentas.modo": "una"}
        cu = G.asignar_cuentas(np.random.default_rng(0), p, self.pool.cuentas, par)
        self.assertTrue(((cu["banco"] + cu["billetera"]) == 1).all())
        self.assertTrue((cu["tc"] == 0).all())

    def test_modo_de_cuentas_invalido(self):
        with self.assertRaises(ValueError):
            G.asignar_cuentas(np.random.default_rng(0), self.perfiles(10), self.pool.cuentas, dict(self.par) | {"cuentas.modo": "tres"})

    def _eventos(self, n=60_000, seed=0):
        rng = np.random.default_rng(seed)
        E = pd.DataFrame({"perfil": rng.integers(0, 300, n), "categoria_n1": rng.choice(G.CATEGORIAS_GASTO, n), "recurrente": False,
                          "clase_comercio": rng.choice(["cadena", "tienda_barrio", "persona", "internet"], n), "concepto": "", "categoria_n2": ""})
        cu = pd.DataFrame({"banco": rng.integers(0, 2, 300), "billetera": rng.integers(0, 2, 300), "tc": 0})
        cu.loc[(cu["banco"] == 0) & (cu["billetera"] == 0), "banco"] = 1
        medio = rng.choice(["efectivo", "tarjeta_debito", "tarjeta_credito"], n, p=[0.7, 0.25, 0.05]).astype(object)
        return E, cu, medio

    def test_migracion_cumple_la_fraccion_objetivo_y_las_cuentas(self):
        permisos = pd.read_csv(DIR_PARAM / "permisos_medios_digitales.csv")
        E, cu, medio = self._eventos()
        lograda = {}
        for esc in ("bajo", "base", "alto"):
            par = dict(self.par) | {"digital.escenario": esc}
            nuevo, d = G.migracion_digital(E, medio, cu, np.random.default_rng(1), par, permisos)
            m = d.pop("_mascara")
            lograda[esc] = d["fraccion_lograda"]
            self.assertAlmostEqual(d["fraccion_lograda"], par["digital.escenarios"][esc], delta=0.01)
            self.assertFalse(np.isin(medio[m], ["tarjeta_credito"]).any(), "el crédito no migra")
            p = E["perfil"].to_numpy()
            self.assertTrue((cu["billetera"].to_numpy()[p][nuevo == "billetera_digital"] == 1).all(), "sin billetera no hay pago por billetera")
            self.assertTrue((cu["banco"].to_numpy()[p][nuevo == "transferencia_bancaria"] == 1).all(), "sin banco no hay transferencia")
        self.assertLess(lograda["bajo"], lograda["base"])
        self.assertLess(lograda["base"], lograda["alto"])

    def test_migracion_sigue_los_pesos_estructurales(self):
        # con prop_billetera = 1 solo hay migración a billetera, ∝ peso_billetera: alimentos (1,0) frente a vivienda_servicios (0,2) → razón ≈ 5
        permisos = pd.read_csv(DIR_PARAM / "permisos_medios_digitales.csv")
        pw = permisos.set_index("categoria_n1")["peso_billetera"]
        E, cu, medio = self._eventos(240_000)
        par = dict(self.par) | {"digital.prop_billetera": 1.0}
        nuevo, d = G.migracion_digital(E, medio, cu, np.random.default_rng(1), par, permisos)
        el = np.isin(medio, ["efectivo", "tarjeta_debito"]) & (cu["billetera"].to_numpy()[E["perfil"].to_numpy()] == 1)
        tasa = pd.Series(nuevo[el] != medio[el]).groupby(E.loc[el, "categoria_n1"].to_numpy()).mean()
        self.assertTrue((nuevo[nuevo != medio] == "billetera_digital").all())
        self.assertAlmostEqual(tasa["alimentos_mercado"] / tasa["vivienda_servicios"], pw["alimentos_mercado"] / pw["vivienda_servicios"], delta=0.5)
        self.assertAlmostEqual(tasa["comidas_fuera"] / tasa["educacion"], pw["comidas_fuera"] / pw["educacion"], delta=0.5)

    def test_restricciones_de_factibilidad(self):
        lugares = G.cargar_lugares()
        E = pd.DataFrame({"perfil": [0, 1, 2, 3, 4], "recurrente": False, "clase_comercio": ["cadena", "cadena", "persona", "internet", "cadena"]})
        cu = pd.DataFrame({"banco": [1, 0, 1, 1, 1], "billetera": [0, 1, 0, 0, 0], "tc": [0, 0, 0, 0, 1]})
        medio = np.array(["tarjeta_credito", "tarjeta_debito", "tarjeta_debito", "efectivo", "tarjeta_credito"], dtype=object)
        nuevo, cont = G.aplicar_restricciones(E, medio, cu, lugares, self.par)
        self.assertEqual(nuevo.tolist(), ["tarjeta_debito",       # crédito sin tarjeta → débito
                                          "billetera_digital",    # débito sin banco, con billetera
                                          "efectivo",             # tarjeta donde no hay datáfono (persona)
                                          "tarjeta_debito",       # compra por internet en efectivo → débito
                                          "tarjeta_credito"])     # crédito con tarjeta, lugar que acepta: se conserva

    def test_contraparte(self):
        E = pd.DataFrame({"clase_comercio": ["tienda_barrio", "tienda_barrio", "cadena", "persona", "ambulante", "especializado", "persona"],
                          "categoria_n2": ["", "", "", "", "", "servicio_domestico", ""], "concepto": ["", "", "", "", "", "", "arriendo"]})
        medio = np.array(["transferencia_bancaria", "billetera_digital", "transferencia_bancaria", "billetera_digital", "billetera_digital",
                          "transferencia_bancaria", "transferencia_bancaria"], dtype=object)
        self.assertEqual(G.contraparte(E, medio).tolist(), ["persona", "comercio", "comercio", "persona", "persona", "persona", "persona"])


# ================================================================================================
# 1c. generador completo sobre pool sintético
# ================================================================================================
@unittest.skipUnless(HAY_PRIORS, "falta outputs/priors/priors.json")
class TestGeneradorSintetico(unittest.TestCase):
    N = 120

    @classmethod
    def setUpClass(cls):
        cls.priors = PR.cargar_priors()
        cls.pool = pool_sintetico()
        cls.T, cls.P, cls.info = G.generar_muestra(cls.pool, cls.priors, cls.N, 42)
        cls.em = cls.T[cls.T["capa"] == "emitida"]
        cls.it = cls.T[cls.T["capa"] == "interna"]

    def test_esquema_y_enums(self):
        T = self.T
        self.assertEqual(list(T.columns), G.COLUMNAS)
        self.assertTrue(T["tx_id"].is_unique)
        self.assertTrue(T["monto"].dtype.kind == "i" and (T["monto"] > 0).all())
        self.assertTrue(T["signo"].isin(["+", "-"]).all())
        self.assertTrue(T["capa"].isin(["interna", "emitida"]).all())
        self.assertTrue(T["medio_pago"].isin(MEDIOS).all())
        self.assertTrue(T["formalidad_comercio"].isin(FORMALIDAD).all())
        self.assertTrue(self.em["cuenta_tipo"].isin(["banco", "billetera", "tarjeta_credito"]).all())
        self.assertTrue(self.em["fuente_etiqueta"].isin(["texto", "declaracion_voluntario"]).all())
        self.assertEqual(T["canal_p2p"].dtype, bool)

    def test_categorias_y_subtipos_de_la_taxonomia(self):
        tax = taxonomia()
        self.assertTrue(self.T["categoria_n1"].isin(list(tax)).all())
        for r in self.T[self.T["categoria_n2"] != ""][["categoria_n1", "categoria_n2"]].drop_duplicates().itertuples():
            self.assertIn(r.categoria_n2, tax[r.categoria_n1])

    def test_fechas_dentro_de_la_ventana(self):
        f = pd.to_datetime(self.T["fecha"])
        meses = set(self.info["meses"])
        self.assertTrue(set(f.dt.strftime("%Y-%m")) <= meses)
        self.assertEqual(self.T["mes_referencia"].tolist(), f.dt.strftime("%Y-%m").tolist())

    def test_enlace_interna_emitida(self):
        ref = self.em[self.em["id_interno"] != ""]
        self.assertTrue(ref["id_interno"].is_unique)
        self.assertTrue(ref["id_interno"].isin(self.it["tx_id"]).all())
        pagadas = self.it[self.it["cuenta_tipo"] != ""]
        self.assertEqual(set(pagadas["tx_id"]), set(ref["id_interno"]))
        m = ref.merge(self.it, left_on="id_interno", right_on="tx_id", suffixes=("", "_i"))
        for c in ("monto", "categoria_n1", "categoria_n2", "medio_pago", "perfil_id", "fecha", "cuenta_tipo"):
            self.assertTrue((m[c] == m[f"{c}_i"]).all(), c)

    def test_el_efectivo_no_se_emite(self):
        no_emite = self.it[self.it["medio_pago"].isin(["efectivo", "fiado_credito_tienda", "bono_subsidio", "otro_nd"])]
        self.assertTrue((no_emite["cuenta_tipo"] == "").all())
        self.assertFalse(self.em["medio_pago"].isin(["efectivo", "fiado_credito_tienda", "bono_subsidio", "otro_nd"]).any())

    def test_los_retiros_cubren_el_efectivo_de_cada_perfil_mes(self):
        cash = self.it[self.it["medio_pago"].isin(["efectivo", "fiado_credito_tienda"])].groupby(["perfil_id", "mes_referencia"])["monto"].sum()
        ret = self.em[self.em["categoria_n1"] == "retiro_efectivo"].groupby(["perfil_id", "mes_referencia"])["monto"].sum()
        j = pd.concat([cash.rename("cash"), ret.rename("ret")], axis=1).fillna(0)
        self.assertTrue((j["ret"] >= j["cash"]).all())
        self.assertTrue((j.loc[j["cash"] == 0, "ret"] == 0).all(), "no hay retiros sin gasto en efectivo")

    def test_pares_de_recarga_y_de_pago_de_tarjeta(self):
        for origen, cuenta_a, cuenta_b in (("recarga_billetera", "banco", "billetera"), ("pago_tarjeta", "banco", "tarjeta_credito")):
            e = self.em[self.em["origen"] == origen]
            a = e[e["cuenta_tipo"] == cuenta_a].groupby(["perfil_id", "mes_referencia", "fecha"])["monto"].sum().sort_index()
            b = e[e["cuenta_tipo"] == cuenta_b].groupby(["perfil_id", "mes_referencia", "fecha"])["monto"].sum().sort_index()
            pd.testing.assert_series_equal(a, b, check_names=False)
            self.assertTrue((e[e["cuenta_tipo"] == cuenta_a]["signo"] == "-").all())
            self.assertTrue((e[e["cuenta_tipo"] == cuenta_b]["signo"] == "+").all())

    def test_el_pago_de_tarjeta_igual_a_las_compras_pagables(self):
        par, _ = G.cargar_parametros()
        compras = self.em[(self.em["cuenta_tipo"] == "tarjeta_credito") & (self.em["signo"] == "-") & (pd.to_datetime(self.em["fecha"]).dt.day <= par["tarjeta_credito.dia_pago"])]
        pagos = self.em[(self.em["origen"] == "pago_tarjeta") & (self.em["cuenta_tipo"] == "banco")]
        self.assertEqual(int(compras["monto"].sum()), int(pagos["monto"].sum()))

    def test_cuentas_solo_donde_el_perfil_las_tiene(self):
        tiene = self.P.set_index("perfil_id")[["tiene_banco", "tiene_billetera", "tiene_tarjeta_credito"]]
        for tipo, col in (("banco", "tiene_banco"), ("billetera", "tiene_billetera"), ("tarjeta_credito", "tiene_tarjeta_credito")):
            perf = set(self.em.loc[self.em["cuenta_tipo"] == tipo, "perfil_id"])
            self.assertTrue(all(tiene.loc[p, col] == 1 for p in perf), tipo)

    def test_p2p_con_proposito_es_declaracion_y_no_nombra_comercio(self):
        e = self.em[self.em["canal_p2p"]]
        self.assertTrue(len(e) > 0)
        self.assertTrue((e["fuente_etiqueta"] == "declaracion_voluntario").all())
        self.assertFalse(e["categoria_n1"].isin(["transferencias_p2p", "retiro_efectivo", "movimiento_propio"]).any())
        self.assertTrue(e["descripcion"].str.contains("PERSONA|NEQUI|DAVIPLATA|Nequi|Daviplata").all())
        self.assertTrue((self.em.loc[~self.em["canal_p2p"], "fuente_etiqueta"] == "texto").all())

    def test_signos_y_categorias_operativas(self):
        em = self.em
        self.assertTrue((em.loc[em["categoria_n1"] == "ingreso", "signo"] == "+").all())
        self.assertTrue((em.loc[em["categoria_n1"] == "retiro_efectivo", "signo"] == "-").all())
        self.assertTrue((em.loc[em["categoria_n1"] == "retiro_efectivo", "formalidad_comercio"] == "no_aplica").all())
        self.assertTrue(em.loc[em["origen"] == "compra", "signo"].eq("-").all())

    def test_descripciones_con_formato_anonimizado(self):
        d = self.em["descripcion"]
        self.assertFalse(d.str.contains(r"\d{6,}").any(), "secuencias de 6 o más dígitos (protocolo de anonimización R-B)")
        self.assertFalse(d.str.contains(r"[{}]").any())
        self.assertTrue((d.str.strip().str.len() > 2).all())
        self.assertTrue((self.it["descripcion"] == "").all(), "la capa interna no tiene descripción")

    def test_sin_ipc_queda_marcado(self):
        self.assertFalse(self.info["ipc_aplicado"])
        self.assertTrue(any("SIN IPC" in a for a in self.info["avisos"]))

    def test_ipc_aplicado_no_marca_aviso(self):
        pool = pool_sintetico()
        pool.meta["ipc_aplicado"] = True
        _, _, info = G.generar_muestra(pool, self.priors, 20, 42)
        self.assertTrue(info["ipc_aplicado"])
        self.assertEqual(info["avisos"], [])

    def test_determinismo_y_sensibilidad_a_la_semilla(self):
        T2, P2, _ = G.generar_muestra(self.pool, self.priors, self.N, 42)
        pd.testing.assert_frame_equal(self.T, T2)
        pd.testing.assert_frame_equal(self.P, P2)
        T3, _, _ = G.generar_muestra(self.pool, self.priors, self.N, 43)
        self.assertFalse(self.T.equals(T3))

    def test_modo_una_cuenta_solo_banco_o_billetera(self):
        T, P, info = G.generar_muestra(self.pool, self.priors, 60, 42, overrides={"cuentas.modo": "una"})
        em = T[T["capa"] == "emitida"]
        self.assertEqual(set(em["cuenta_tipo"]) - {"banco", "billetera"}, set())
        self.assertFalse((em["origen"] == "recarga_billetera").any())
        self.assertFalse((em["origen"] == "pago_tarjeta").any())

    def test_modo_por_hogar_y_escenarios_corren(self):
        for ov in ({"donantes.modo": "por_hogar"}, {"digital.escenario": "alto"}, {"digital.escenario": "bajo"}):
            with self.subTest(ov):
                T, _, info = G.generar_muestra(self.pool, self.priors, 40, 42, overrides=ov)
                self.assertGreater((T["capa"] == "emitida").sum(), 0)

    def test_mas_digital_menos_efectivo(self):
        def efectivo(esc):
            T, _, i = G.generar_muestra(self.pool, self.priors, 80, 42, overrides={"digital.escenario": esc})
            return i["capa_interna_valor_por_medio_pago"]["efectivo"]
        self.assertGreater(efectivo("bajo"), efectivo("base"))
        self.assertGreater(efectivo("base"), efectivo("alto"))

    def test_modo_donantes_invalido(self):
        with self.assertRaises(ValueError):
            G.generar_muestra(self.pool, self.priors, 10, 42, overrides={"donantes.modo": "otro"})

    def test_el_generador_no_lee_microdatos(self):
        for nombre in ("generador.py", "comercios.py"):
            src = (RAIZ / "src" / "sdg" / nombre).read_text(encoding="utf-8")
            for prohibido in ("cargar_enph", "cargar_geih", "data/raw", "reales_crudos", "reales_anon"):
                self.assertNotIn(prohibido, src, f"{nombre} no debe referirse a {prohibido} (D14 y regla del pool)")


# ================================================================================================
# 2. pool real
# ================================================================================================
@unittest.skipUnless(HAY_PRIORS and HAY_POOL, "falta el pool real: correr tools/construir_generador.py")
class TestPoolReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = G.cargar_pool()
        cls.priors = PR.cargar_priors()
        cls.T, cls.P, cls.info = G.generar_muestra(cls.pool, cls.priors, 200, 42)

    def test_la_mezcla_suma_uno_y_cubre_las_quince_celdas(self):
        self.assertEqual(len(self.pool.mezcla), 15)
        for c, m in self.pool.mezcla.items():
            self.assertAlmostEqual(m["celda"] + m["quintil"] + m["bogota"], 1.0, places=9, msg=c)
            self.assertGreaterEqual(m["bogota"], 0.0)

    def test_pool_coherente(self):
        ev, rec, hog = self.pool.eventos, self.pool.recurrentes, self.pool.hogares
        self.assertTrue((ev["valor"] > 0).all() and (ev["factor"] > 0).all() and (ev["FEX"] > 0).all())
        self.assertTrue(set(ev["categoria_n1"]) <= set(G.CATEGORIAS_GASTO))
        self.assertTrue(set(ev["DIRECTORIO"]) <= set(hog["DIRECTORIO"]))
        self.assertTrue(set(rec["DIRECTORIO"]) <= set(hog["DIRECTORIO"]))
        self.assertTrue(hog["DIRECTORIO"].is_unique)

    def test_la_muestra_cumple_las_invariantes_basicas(self):
        T = self.T
        self.assertTrue(T["tx_id"].is_unique and (T["monto"] > 0).all())
        em, it = T[T["capa"] == "emitida"], T[T["capa"] == "interna"]
        self.assertEqual(set(it.loc[it["cuenta_tipo"] != "", "tx_id"]), set(em.loc[em["id_interno"] != "", "id_interno"]))
        self.assertGreaterEqual(self.info["efectivo"]["retiros_sobre_gasto_efectivo"], 1.0)
        self.assertLessEqual(self.info["efectivo"]["retiros_sobre_gasto_efectivo"], 1.25)

    def test_gasto_sobre_ingreso_en_orden_de_magnitud_de_enph(self):
        r = self.info["gasto_sobre_ingreso_por_perfil"]
        self.assertGreater(r["mediana"], 0.5)
        self.assertLess(r["mediana"], 1.6)

    def test_migracion_cerca_del_objetivo(self):
        m = self.info["medios"]["migracion"]
        self.assertAlmostEqual(m["fraccion_lograda"], m["fraccion_objetivo"], delta=0.02)


# ================================================================================================
# 3. calibración con microdatos
# ================================================================================================
@unittest.skipUnless(HAY_MICRODATOS, "faltan los microdatos de ENPH en data/raw")
class TestCalibracionGastoEnph(unittest.TestCase):
    """Corre ``gasto_enph.construir`` una vez (≈ 30 s). Invariantes y bandas amplias: la reconciliación con GCMUG es consistencia, no validación."""

    @classmethod
    def setUpClass(cls):
        from sdg import gasto_enph as GE
        cls.GE = GE
        cls.R = GE.construir()

    def test_eventos_validos(self):
        ev = self.R["eventos"]
        self.assertTrue((ev["valor"] > 0).all() and (ev["factor"] > 0).all() and (ev["FEX"] > 0).all())
        self.assertTrue(set(ev["categoria_n1"]) <= set(self.GE.CATEGORIAS_GASTO))
        tax = taxonomia()
        for r in ev[ev["categoria_n2"] != ""][["categoria_n1", "categoria_n2"]].drop_duplicates().itertuples():
            self.assertIn(r.categoria_n2, tax[r.categoria_n1], f"{r.categoria_n1}.{r.categoria_n2}")

    def test_todo_valor_tiene_prefijo_de_mapeo(self):
        ev = self.R["eventos"]
        sin = ev.loc[ev["prefijo_mapeo"] == "", "valor"].mul(ev["factor"]).sum() / ev["valor"].mul(ev["factor"]).sum()
        self.assertLess(sin, 0.001, "las divisiones por defecto deben cubrir todo código con división 00-12")

    def test_mezcla_y_kappa(self):
        k = self.R["kappa"]
        self.assertGreater(k["kappa"], 1.0)
        self.assertFalse(k["en_frontera"], "κ en el borde de la rejilla: ampliar la rejilla o revisar")
        for c, m in self.R["mezcla"].items():
            self.assertAlmostEqual(m["celda"] + m["quintil"] + m["bogota"], 1.0, places=9)
            self.assertEqual(m["rala"], m["n_ef_celda"] < k["kappa"])

    def test_reconciliacion_con_gcmug_en_banda_amplia(self):
        r = self.R["diag"]["reconciliacion_gcmug"]["agregado_eventos_mas_recurrentes_sobre_gcmug"]
        self.assertGreater(r, 0.8)
        self.assertLess(r, 1.25)

    def test_sin_serie_de_ipc_el_factor_es_uno_y_se_declara(self):
        from sdg import ipc
        if ipc.RUTA_IPC.is_file():
            self.skipTest("hay serie de IPC en data/raw/IPC: el factor ya no es 1,0")
        self.assertTrue((self.R["eventos"]["factor_ipc"] == 1.0).all())
        self.assertFalse(self.R["diag"]["ipc"]["aplicado"])

    def test_estructura_de_cuentas_suma_uno_por_estrato(self):
        c = self.R["cuentas"]
        s = c.groupby("estrato_agrupado")["p"].sum()
        self.assertTrue(np.allclose(s.to_numpy(), 1.0))
        self.assertTrue(((c["tc"] == 0) | (c["banco"] == 1)).all(), "tarjeta de crédito sin banco debe haberse vuelto banco implícito")

    def test_servicios_publicos_presentes(self):
        conceptos = set(self.R["recurrentes"]["concepto"])
        self.assertTrue({"arriendo", "energia", "acueducto", "gas_natural"} <= conceptos)

    def test_cestas_agrupan_lineas(self):
        for nombre, d in self.R["diag"]["diarios"].items():
            self.assertLessEqual(d["cestas"], d["filas_compra_valor_positivo"], nombre)
            self.assertAlmostEqual(d["valor_cestas"], d["valor_lineas"], delta=1e-6 * d["valor_lineas"], msg=f"{nombre}: la cesta debe conservar el valor")


if __name__ == "__main__":
    unittest.main()
