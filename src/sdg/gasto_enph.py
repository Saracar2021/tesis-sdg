"""Calibración del gasto del hogar para el generador por reglas (WP6, Etapa 2, PD5): capa interna de D15.

Convierte los registros de gasto de ENPH 2016-17 (Bogotá urbano) en un «banco de donantes»: por hogar, los eventos de compra
(cestas del diario y registros de gastos menos frecuentes) con su frecuencia mensual, su categoría de la taxonomía y su
lugar de compra, más los pagos recurrentes de la vivienda (arriendo, cuota de vivienda, servicios públicos y de conectividad).
Lee SOLO vía ``sdg.carga`` (más las tablas de parámetros de ``docs/generador/``) y escribe todo a ``outputs/generador/``.
El generador (``sdg.generador``) NO lee microdatos: lee este banco.

Decisiones de diseño (cada una es un supuesto declarado, no un hecho de la encuesta)
  Unidad de emisión. Un banco ve un cargo por compra, no una línea por artículo. En el diario, las líneas del mismo hogar, misma
    hoja (SECUENCIA_P), mismo lugar de compra y misma frecuencia forman una CESTA; su categoría es la de la línea de mayor valor
    (regla de predominancia de la taxonomía) y su valor es la suma. En los subcapítulos mensuales del Cuadernillo 3 se agrupa igual
    por (hogar, subcapítulo, lugar); en los de 3 y 12 meses cada artículo es un evento.
  Frecuencia. Cada evento lleva un factor mensual (tablas oficiales de DANE en ``docs/generador/mensualizacion_enph.csv``): es el
    número esperado de compras equivalentes en un mes. El generador lo vuelve entero por redondeo estocástico.
  Donantes. Para cada (perfil, categoría) el generador elige un hogar donante de ENPH y reproduce SUS eventos de esa categoría.
    El donante sale de la celda (estrato × quintil), del quintil o de Bogotá con la mezcla jerárquica de los priors:
    P(celda) = n_ef/(n_ef+κ), y el resto va al nivel superior con el mismo esquema. κ se estima por verosimilitud marginal
    Dirichlet-multinomial sobre el gasto mensual de cada categoría discretizado en cuantiles (mismo ``elegir_kappa`` de WP3).
    Reproduce los ceros y las colas empíricas (la lognormal sobrestima el p90 en las 12 divisiones: ver diagnóstico).
  Actualización a 2025: ``sdg.ipc`` (deflactor único: IPC total nacional, mes de recolección de cada hogar, base promedio 2025; sin serie,
    factor 1,0 y la salida se marca «sin IPC»).

Límites: ENPH no trae fecha ni día de la semana; el día de cada evento lo pone el generador. El diario tiene fatiga (menos líneas los
últimos días) que DANE no corrige y aquí tampoco. ``n_ef`` de Kish no corrige conglomeración (L1). Los servicios públicos vienen
de la pregunta «último valor pagado» y los meses a que corresponde ese pago (P10272S*), no de un diario.
"""
from __future__ import annotations

import hashlib
import json
from fractions import Fraction

import numpy as np
import pandas as pd

from sdg import carga, codigos as cod, ipc as ipc_mod
from sdg.encogimiento import Problema, Stat, elegir_kappa, n_efectivo
from sdg.pesos import cortes_ponderados, grupo_por_cortes

RAIZ = carga.RAIZ
SEED = 42
DIR_PARAM = RAIZ / "docs" / "generador"
DIR_SALIDA = RAIZ / "outputs" / "generador"
DIR_POOL = DIR_SALIDA / "pool"          # microdatos derivados (por hogar): NO se versionan (.gitignore)

CATEGORIAS_GASTO = ["alimentos_mercado", "comidas_fuera", "transporte", "vivienda_servicios", "telecom_conectividad", "salud",
                    "educacion", "entretenimiento", "vestuario_cuidado_personal", "hogar_articulos", "obligaciones_financieras", "otros"]

DIARIOS = (
    dict(nombre="diario_hogar", archivo="urbano/gastos_diarios_hogar.txt", tabla="diario_hogar", cod="NH_CGDU_P1", forma="NH_CGDU_P5",
         valor="NH_CGDU_P8", lugar="NH_CGDU_P7B1379", frec="NH_CGDU_P9", domicilio=None),
    dict(nombre="cf_hogar", archivo="urbano/gastos_diarios_hogar_comidas_fuera.csv", tabla="diario_hogar", cod="NH_CGDUCFH_P1_1",
         forma="NH_CGDUCFH_P3", valor="NH_CGDUCFH_P5", lugar="NH_CGDUCFH_P4", frec="NH_CGDUCFH_P6", domicilio="NH_CGDUCFH_P8"),
    dict(nombre="personal", archivo="urbano/gastos_diarios_personales.csv", tabla="diario_personal", cod="NC4_CC_P1_1",
         forma="NC4_CC_P3", valor="NC4_CC_P5", lugar="NC4_CC_P4", frec="NC4_CC_P6", domicilio=None),
    dict(nombre="cf_personal", archivo="urbano/gastos_personales_comidas_fuera.csv", tabla="diario_personal", cod="NH_CGPUCFH_P1_S1",
         forma="NH_CGPUCFH_P3", valor="NH_CGPUCFH_P5", lugar="NH_CGPUCFH_P4", frec="NH_CGPUCFH_P6", domicilio="NH_CGPUCFH_P8"),
)
FORMA_COMPRA = "1"        # FORMA_ADQUISICION_INFERIDA (sdg.codigos): 1 = compra (inferido, no impreso en el cuadernillo)
DOMICILIO_SI = "1"        # NH_CGDUCFH_P8 / NH_CGPUCFH_P8: «marque con una X si lo adquirió a domicilio» (1 = marcado)

# Servicios públicos y de conectividad: P10272S{i}A1 = último valor pagado, A2 = meses a que corresponde (Cuadernillo 3, 3.C13)
SERVICIOS = {1: ("acueducto", "vivienda_servicios", "servicios_publicos", "04"), 2: ("aseo", "vivienda_servicios", "servicios_publicos", "04"),
             3: ("alcantarillado", "vivienda_servicios", "servicios_publicos", "04"), 4: ("energia", "vivienda_servicios", "servicios_publicos", "04"),
             5: ("alumbrado", "vivienda_servicios", "servicios_publicos", "04"), 6: ("gas_natural", "vivienda_servicios", "servicios_publicos", "04"),
             7: ("telefono_fijo", "telecom_conectividad", "plan_pospago", "08"), 8: ("internet_fijo", "telecom_conectividad", "internet_hogar_tv", "08"),
             9: ("television", "telecom_conectividad", "internet_hogar_tv", "09")}
VALOR_MIN_VALIDO = 100    # Cuadernillo 3: «superior a 100; 98 incluido en otro servicio; 99 no sabe; 00 no paga»
MESES_VALIDOS = range(1, 61)

N_BINS_KAPPA = 8
MIN_POSITIVOS_KAPPA = 100


# ================================================================================================
# parámetros (tablas versionadas en docs/generador/)
# ================================================================================================
def _frac(x: str) -> float:
    return float(Fraction(x.strip()))


class Parametros:
    """Tablas de ``docs/generador/`` ya parseadas."""

    def __init__(self, dir_param=DIR_PARAM):
        m = pd.read_csv(dir_param / "mensualizacion_enph.csv", dtype=str, keep_default_na=False)
        m["factor"] = m["factor"].map(_frac)
        self.tablas = {t: dict(zip(g["codigo_frecuencia"], g["factor"])) for t, g in m.groupby("tabla")}
        self.mensualizacion = m
        caps = pd.read_csv(dir_param / "periodo_referencia_caps.csv", dtype=str, keep_default_na=False)
        self.cap_tabla = dict(zip(caps["cap"], caps["tabla"]))
        mp = pd.read_csv(dir_param / "mapeo_coicop_taxonomia_provisional.csv", dtype=str, keep_default_na=False)
        self.mapeo = mp
        self._mapa = {L: dict(zip(g["prefijo"], zip(g["categoria_n1"], g["categoria_n2"]))) for L, g in mp.groupby(mp["prefijo"].str.len())}
        lug = pd.read_csv(dir_param / "lugares_compra.csv", dtype=str, keep_default_na=False)
        self.lugares = lug.set_index("codigo")
        self.parametros_propios = json.loads((dir_param / "parametros_propios.json").read_text(encoding="utf-8"))

    def categoria(self, cod8: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Prefijo más largo gana. Devuelve (categoria_n1, categoria_n2, prefijo_usado); sin prefijo → 'otros'."""
        cat = pd.Series(np.nan, index=cod8.index, dtype=object)
        n2 = pd.Series("", index=cod8.index, dtype=object)
        pref = pd.Series("", index=cod8.index, dtype=object)
        for L in sorted(self._mapa):
            clave = cod8.str[:L]
            hit = clave.map(self._mapa[L])
            usa = hit.notna()
            cat = cat.where(~usa, hit[usa].map(lambda t: t[0]))
            n2 = n2.where(~usa, hit[usa].map(lambda t: t[1]))
            pref = pref.where(~usa, clave[usa])
        return cat.fillna("otros"), n2, pref

    def clase_lugar(self, lugar: pd.Series) -> pd.Series:
        return lugar.map(self.lugares["clase_comercio"]).fillna("otro")


def refinar_n2(cat: pd.Series, n2: pd.Series, clase: pd.Series, domicilio: pd.Series) -> pd.Series:
    """Subtipo de nivel 2 que depende del lugar de compra o del domicilio (el resto viene del mapeo). Reglas propias, declaradas."""
    out = n2.copy()
    m = cat == "alimentos_mercado"
    out[m & clase.isin(["cadena"])] = "supermercado_cadena"
    out[m & clase.isin(["plaza", "feria"])] = "plaza_fruver"
    out[m & clase.isin(["internet", "catalogo"])] = "domicilio_mercado"
    out[m & ~clase.isin(["cadena", "plaza", "feria", "internet", "catalogo"])] = "tienda_barrio"
    m = cat == "comidas_fuera"
    out[m] = "restaurante_local"
    out[m & (clase == "ambulante")] = "comida_callejera"
    out[m & (domicilio == 1)] = "domicilios_app"
    m = (cat == "transporte") & (n2 == "publico_masivo")
    out[m & clase.isin(["persona", "internet"])] = "apps_taxi"
    return out


# ================================================================================================
# hogares
# ================================================================================================
def construir_hogares() -> tuple[pd.DataFrame, list]:
    """Hogares ENPH de Bogotá con celda estrato × quintil de ICGU (mismos cortes y definición que WP3)."""
    h = carga.cargar_enph("hogares/viviendas_hogares.csv", dominio="bogota",
                          columnas=["P8520S1A1", "ICGU", "ICMDUG", "GCMUG", "PERIODO", "P5140", "P5100S4"])
    h["icgu"] = carga.a_numero(h["ICGU"])
    ok = h["icgu"].notna()
    cortes = cortes_ponderados(h.loc[ok, "icgu"], h.loc[ok, "FEX"], 5)
    h["quintil"] = grupo_por_cortes(h["icgu"], cortes)
    h["estrato_agrupado"] = carga.estrato_agrupado(h["P8520S1A1"]).astype(object)
    h["icmdug"] = carga.a_numero(h["ICMDUG"])
    h["gcmug"] = carga.a_numero(h["GCMUG"])
    h["arriendo"] = carga.a_numero(h["P5140"])
    h["cuota_vivienda"] = carga.a_numero(h["P5100S4"])
    h["con_celda"] = h["estrato_agrupado"].notna() & h["quintil"].notna()
    h["celda"] = np.where(h["con_celda"], h["estrato_agrupado"].astype(str) + "|Q" + h["quintil"].fillna(0).astype(int).astype(str), "")
    cols = ["DIRECTORIO", "FEX", "estrato_agrupado", "quintil", "celda", "con_celda", "PERIODO", "icgu", "icmdug", "gcmug", "arriendo", "cuota_vivienda"]
    return h[cols].reset_index(drop=True), cortes


# ================================================================================================
# eventos
# ================================================================================================
def _factor_frecuencia(frec: pd.Series, tabla: dict, defecto: float) -> tuple[pd.Series, int]:
    f = frec.map(tabla)
    n_def = int(f.isna().sum())
    return f.fillna(defecto), n_def


def eventos_diarios(P: Parametros, diag: dict) -> pd.DataFrame:
    partes = []
    for spec in DIARIOS:
        cols = ["SECUENCIA_P", spec["cod"], spec["forma"], spec["valor"], spec["lugar"], spec["frec"], *([spec["domicilio"]] if spec["domicilio"] else [])]
        d = carga.cargar_enph(spec["archivo"], dominio="bogota", columnas=cols)
        d = d.rename(columns={spec["cod"]: "cod", spec["forma"]: "forma", spec["valor"]: "valor_txt", spec["lugar"]: "lugar", spec["frec"]: "frec"})
        d["domicilio"] = (d[spec["domicilio"]] == DOMICILIO_SI).astype(int) if spec["domicilio"] else 0
        d["valor"] = carga.a_numero(d["valor_txt"])
        n0 = len(d)
        d = d[(d["forma"] == FORMA_COMPRA) & (d["valor"] > 0)].copy()
        d["cod8"] = d["cod"].str.zfill(8)
        d["factor"], n_def = _factor_frecuencia(d["frec"], P.tablas[spec["tabla"]], 1.0)
        # canasta: hogar × hoja del diario × lugar × factor. Se ordena por valor para que la línea predominante sea la primera.
        d = d.sort_values("valor", ascending=False, kind="mergesort")
        b = d.groupby(["DIRECTORIO", "SECUENCIA_P", "lugar", "factor"], sort=False).agg(
            valor=("valor", "sum"), cod8=("cod8", "first"), domicilio=("domicilio", "max"), n_lineas=("valor", "size"), FEX=("FEX", "first")).reset_index()
        b["fuente"], b["tipo"], b["cap"] = spec["nombre"], "cesta", ""
        diag["diarios"][spec["nombre"]] = dict(filas_leidas=n0, filas_compra_valor_positivo=int(len(d)), filas_sin_frecuencia_factor_1=n_def,
                                               cestas=int(len(b)), valor_lineas=float((d["valor"] * d["factor"]).sum()),
                                               valor_cestas=float((b["valor"] * b["factor"]).sum()))
        partes.append(b.drop(columns=["SECUENCIA_P"]))
    return pd.concat(partes, ignore_index=True)


def eventos_menos_frecuentes(P: Parametros, diag: dict) -> pd.DataFrame:
    a = carga.cargar_enph("hogares/gastos_menos_frecuentes_articulos.txt", dominio="bogota",
                          columnas=["CAP", "P10270", "FORMA", "VALOR", "P10270S2", "P10270S3"])
    n0 = len(a)
    a = a.rename(columns={"P10270": "cod", "FORMA": "forma", "P10270S2": "lugar", "P10270S3": "frec"})
    a["valor"] = carga.a_numero(a["VALOR"])
    a = a[(a["forma"] == FORMA_COMPRA) & (a["valor"] > 0)].copy()
    a["cod8"] = a["cod"].str.zfill(8)
    a["tabla"] = a["CAP"].map(P.cap_tabla).fillna("menos_frecuentes_T12")
    diag["menos_frecuentes"] = dict(filas_leidas=n0, filas_compra_valor_positivo=int(len(a)),
                                    caps_sin_tabla_asignada=sorted(set(a.loc[~a["CAP"].isin(P.cap_tabla), "CAP"])))
    a["factor"] = np.nan
    defectos = {"menos_frecuentes_T3": 1.0, "menos_frecuentes_T4": 1 / 3}
    n_def = {}
    for t in ("menos_frecuentes_T3", "menos_frecuentes_T4"):
        m = a["tabla"] == t
        a.loc[m, "factor"], n_def[t] = _factor_frecuencia(a.loc[m, "frec"], P.tablas[t], defectos[t])
    m12 = a["tabla"] == "menos_frecuentes_T12"
    a.loc[m12, "factor"] = P.tablas["menos_frecuentes_T12"]["*"]
    diag["menos_frecuentes"]["filas_sin_frecuencia_con_factor_por_defecto"] = n_def
    a = a.sort_values("valor", ascending=False, kind="mergesort")
    agrupar = a["tabla"].isin(P.parametros_propios["calibracion"]["agrupar_tablas"]["valor"])
    g = a[agrupar].groupby(["DIRECTORIO", "CAP", "lugar", "factor"], sort=False).agg(
        valor=("valor", "sum"), cod8=("cod8", "first"), n_lineas=("valor", "size"), FEX=("FEX", "first")).reset_index()
    g["tipo"] = "cesta_mensual"
    s = a[~agrupar][["DIRECTORIO", "CAP", "lugar", "factor", "valor", "cod8", "FEX"]].copy()
    s["n_lineas"], s["tipo"] = 1, "articulo"
    ev = pd.concat([g, s], ignore_index=True)
    ev["domicilio"], ev["fuente"], ev["cap"] = 0, "menos_frecuente", ev.pop("CAP")
    diag["menos_frecuentes"].update(eventos=int(len(ev)), valor_lineas=float((a["valor"] * a["factor"]).sum()),
                                    valor_eventos=float((ev["valor"] * ev["factor"]).sum()))
    return ev


def completar_eventos(ev: pd.DataFrame, P: Parametros, hog: pd.DataFrame, serie_ipc, modo_ipc: str, diag: dict, referencia_ipc: str = "mes_recoleccion") -> pd.DataFrame:
    """Categoría, subtipo, clase de comercio, factor IPC. Todo determinista."""
    ev = ev.copy()
    cat, n2, pref = P.categoria(ev["cod8"])
    ev["clase_comercio"] = P.clase_lugar(ev["lugar"])
    ev["categoria_n1"], ev["prefijo_mapeo"] = cat, pref
    ev["categoria_n2"] = refinar_n2(cat, n2, ev["clase_comercio"], ev["domicilio"])
    ev["division"] = np.where(ev["cod8"].str[:2].isin(ipc_mod.DIVISIONES), ev["cod8"].str[:2], ipc_mod.TOTAL)
    periodo = ev["DIRECTORIO"].map(hog.set_index("DIRECTORIO")["PERIODO"])
    ev["factor_ipc"], diag["ipc"] = ipc_mod.factores(serie_ipc, periodo, ev["division"], modo_ipc, referencia_ipc)
    return ev


def recurrentes(hog: pd.DataFrame, P: Parametros, serie_ipc, modo_ipc: str, diag: dict, referencia_ipc: str = "mes_recoleccion") -> pd.DataFrame:
    """Arriendo, cuota de vivienda y servicios públicos/conectividad: pagos recurrentes con probabilidad mensual = 1/meses del pago."""
    cols = [f"P10272S{i}A{j}" for i in SERVICIOS for j in (1, 2)]
    mp = carga.cargar_enph("hogares/gastos_menos_frecuentes_medio_pago.csv", dominio="bogota", columnas=cols)
    filas = []
    for i, (concepto, cat, n2, div) in SERVICIOS.items():
        v = carga.a_numero(mp[f"P10272S{i}A1"])
        m = carga.a_numero(mp[f"P10272S{i}A2"])
        valido = v > VALOR_MIN_VALIDO
        meses = m.where(m.isin(list(MESES_VALIDOS)), 1.0)           # 97 («inferior al mes») y vacío → 1 mes (declarado)
        d = pd.DataFrame({"DIRECTORIO": mp["DIRECTORIO"], "FEX": mp["FEX"], "concepto": concepto, "categoria_n1": cat, "categoria_n2": n2,
                          "valor": v, "factor": 1.0 / meses, "division": div})[valido]
        diag["recurrentes"][concepto] = dict(hogares_con_valor=int(valido.sum()), meses_modal=float(meses[valido].mode().iloc[0]) if valido.any() else None,
                                             pct_pago_cada_mes=float(100 * (meses[valido] == 1).mean()) if valido.any() else None)
        filas.append(d)
    h = hog.set_index("DIRECTORIO")
    for concepto, col, cat, n2, div in (("arriendo", "arriendo", "vivienda_servicios", "arriendo", "04"),
                                        ("cuota_vivienda", "cuota_vivienda", "obligaciones_financieras", "credito_formal", ipc_mod.TOTAL)):
        v = h[col]
        d = pd.DataFrame({"DIRECTORIO": h.index, "FEX": h["FEX"].to_numpy(), "concepto": concepto, "categoria_n1": cat, "categoria_n2": n2,
                          "valor": v.to_numpy(), "factor": 1.0, "division": div})
        d = d[d["valor"] > 0]
        diag["recurrentes"][concepto] = dict(hogares_con_valor=int(len(d)))
        filas.append(d)
    r = pd.concat(filas, ignore_index=True)
    periodo = r["DIRECTORIO"].map(h["PERIODO"])
    r["factor_ipc"], _ = ipc_mod.factores(serie_ipc, periodo, r["division"], modo_ipc, referencia_ipc)
    return r


# ================================================================================================
# κ de los donantes (verosimilitud marginal Dirichlet-multinomial, como WP3)
# ================================================================================================
def _stat_bins(bins: np.ndarray, w: np.ndarray, k: int) -> Stat:
    s = np.bincount(bins, weights=w, minlength=k)
    return Stat(s / s.sum(), n_efectivo(w), len(w), float(s.sum()))


def estimar_kappa(hog: pd.DataFrame, totales: pd.DataFrame) -> dict:
    """κ̂ común a las categorías: gasto mensual del hogar en cada categoría → 0 o uno de ``N_BINS_KAPPA`` cuantiles ponderados."""
    h = hog[hog["con_celda"]].reset_index(drop=True)
    tot = totales.reindex(h["DIRECTORIO"]).fillna(0.0).reset_index(drop=True)
    w = h["FEX"].to_numpy(dtype=float)
    celdas = sorted(h["celda"].unique())
    quin = lambda c: int(c.split("|Q")[1])
    problemas, usadas, omitidas = [], [], []
    for c in totales.columns:
        x = tot[c].to_numpy(dtype=float)
        pos = x > 0
        if pos.sum() < MIN_POSITIVOS_KAPPA:
            omitidas.append(c)
            continue
        cortes = cortes_ponderados(pd.Series(x[pos]), pd.Series(w[pos]), N_BINS_KAPPA)
        bins = np.where(pos, grupo_por_cortes(pd.Series(x), cortes).fillna(0).to_numpy().astype(int), 0)
        k = N_BINS_KAPPA + 1
        raiz = _stat_bins(bins, w, k).p
        niv_q = {q: _stat_bins(bins[h["quintil"].to_numpy() == q], w[h["quintil"].to_numpy() == q], k) for q in range(1, 6)}
        niv_c = {cl: _stat_bins(bins[(h["celda"] == cl).to_numpy()], w[(h["celda"] == cl).to_numpy()], k) for cl in celdas}
        problemas.append(Problema(raiz, [niv_q, niv_c], [None, quin], None))
        usadas.append(c)
    res = elegir_kappa(problemas)
    res["categorias_usadas"], res["categorias_omitidas"] = usadas, omitidas
    res["n_bins"] = N_BINS_KAPPA
    return res


def pesos_mezcla(hog: pd.DataFrame, kappa: float) -> dict:
    """Probabilidad de que el donante salga de la celda, del quintil o de Bogotá, por celda: P(celda)=n/(n+κ); el resto se reparte igual hacia arriba."""
    h = hog[hog["con_celda"]]
    n_q = {q: n_efectivo(g["FEX"].to_numpy()) for q, g in h.groupby("quintil")}
    out = {}
    for cl, g in h.groupby("celda"):
        n_c = n_efectivo(g["FEX"].to_numpy())
        q = int(cl.split("|Q")[1])
        pc = n_c / (n_c + kappa)
        pq = (1 - pc) * n_q[q] / (n_q[q] + kappa)
        out[cl] = {"celda": pc, "quintil": pq, "bogota": 1 - pc - pq, "n_ef_celda": n_c, "n_ef_quintil": n_q[q],
                   "n_hogares_celda": int(len(g)), "rala": bool(n_c < kappa)}
    return out


# ================================================================================================
# estructura de cuentas (GEIH 2025, P5222): banco / billetera / tarjeta de crédito por estrato
# ================================================================================================
def estructura_cuentas() -> tuple[pd.DataFrame, dict]:
    """P(banco, billetera, TC | estrato, hogar bancarizado con ≥ 1 cuenta que pueda emitir movimientos). GEIH 2025, FEX/12.

    banco = cuenta corriente o de ahorros (S1, S2); billetera = plataforma móvil (S11); TC = tarjeta de crédito (S7).
    Un hogar con TC y sin banco se trata como con banco (la tarjeta se paga desde una cuenta): ``banco_implicito``.
    Los hogares «bancarizados» sin ninguna de las tres (solo CDT, préstamos u «otro») no generan extractos y se excluyen del universo emisor.
    El diccionario GEIH no dice a qué población se restringe P5222 (sdg.codigos): se declara no verificado.
    """
    prod = list(cod.COLUMNAS_PRODUCTO_P5222)
    dh = carga.cargar_geih("datos_hogar", columnas=["P4030S1A1", *prod, "P5222S9", "P5222S10"])
    dh["estrato"] = carga.estrato_agrupado(dh["P4030S1A1"]).astype(object)
    tiene = np.column_stack([dh[c] == "1" for c in prod]).any(axis=1)
    banco = (dh["P5222S1"] == "1") | (dh["P5222S2"] == "1")
    bill = dh["P5222S11"] == "1"
    tc = dh["P5222S7"] == "1"
    emisor = tiene & (banco | bill | tc) & dh["estrato"].notna()
    implicito = emisor & tc & ~banco
    d = dh[emisor].copy()
    d["banco"] = (banco | tc)[emisor].astype(int)
    d["billetera"] = bill[emisor].astype(int)
    d["tc"] = tc[emisor].astype(int)
    filas = []
    for e, g in d.groupby("estrato"):
        tot = g["FEX"].sum()
        for (b, bi, t), gg in g.groupby(["banco", "billetera", "tc"]):
            filas.append(dict(estrato_agrupado=e, banco=int(b), billetera=int(bi), tc=int(t), p=float(gg["FEX"].sum() / tot),
                              expandido=float(gg["FEX"].sum()), n=int(len(gg)), n_ef=float(n_efectivo(gg["FEX"].to_numpy()))))
    tabla = pd.DataFrame(filas)
    diag = dict(hogares_geih_filas=int(len(dh)), bancarizados=int(tiene.sum()), universo_emisor=int(emisor.sum()),
                bancarizados_sin_cuenta_emisora=int((tiene & ~(banco | bill | tc)).sum()), banco_implicito=int(implicito.sum()),
                marginales_por_estrato={e: dict(billetera=float(g.loc[g.billetera == 1, "p"].sum()), tc=float(g.loc[g.tc == 1, "p"].sum()),
                                                solo_billetera=float(g.loc[(g.banco == 0), "p"].sum())) for e, g in tabla.groupby("estrato_agrupado")})
    return tabla, diag


# ================================================================================================
# orquestación
# ================================================================================================
def sha256_archivo(ruta) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def construir(modo_ipc: str = "total", ruta_ipc=None, referencia_ipc: str = "mes_recoleccion") -> dict:
    """Calibración completa en memoria. Determinista (no usa aleatoriedad)."""
    P = Parametros()
    serie = ipc_mod.cargar_serie(ruta_ipc)
    diag: dict = {"diarios": {}, "recurrentes": {}}
    hog, cortes = construir_hogares()
    diag["hogares"] = dict(n_bogota=int(len(hog)), n_con_celda=int(hog["con_celda"].sum()), n_sin_celda=int((~hog["con_celda"]).sum()),
                           cortes_icgu_bogota=[float(c) for c in cortes], n_icgu_cero=int((hog["icgu"] == 0).sum()))
    ev = pd.concat([eventos_diarios(P, diag), eventos_menos_frecuentes(P, diag)], ignore_index=True)
    ev = completar_eventos(ev, P, hog, serie, modo_ipc, diag, referencia_ipc)
    ev = ev.merge(hog[["DIRECTORIO", "con_celda"]], on="DIRECTORIO", how="left")
    diag["cobertura_mapeo"] = (ev.assign(valor_mes=ev["valor"] * ev["factor"]).groupby(["prefijo_mapeo", "categoria_n1"])["valor_mes"].sum()
                               .reset_index().sort_values("valor_mes", ascending=False))
    rec = recurrentes(hog, P, serie, modo_ipc, diag, referencia_ipc)
    # hogares: ingreso monetario disponible actualizado con el IPC total (mismo factor que el gasto del hogar)
    f_tot, _ = ipc_mod.factores(serie, hog["PERIODO"], pd.Series(ipc_mod.TOTAL, index=hog.index), "total", referencia_ipc)
    hog = hog.assign(factor_ipc_total=f_tot.to_numpy())
    # totales por hogar y categoría (pesos de 2016-17, sin IPC) para κ y para la reconciliación con GCMUG
    ev["mensual"] = ev["valor"] * ev["factor"]
    totales = ev.pivot_table(index="DIRECTORIO", columns="categoria_n1", values="mensual", aggfunc="sum", fill_value=0.0)
    for c in CATEGORIAS_GASTO:
        if c not in totales.columns:
            totales[c] = 0.0
    totales = totales[CATEGORIAS_GASTO]
    kappa = estimar_kappa(hog, totales)
    mezcla = pesos_mezcla(hog, kappa["kappa"])
    cuentas, diag_cuentas = estructura_cuentas()
    # reconciliación con GCMUG (validación, no calibración)
    rec_mes = rec.assign(m=rec["valor"] * rec["factor"]).groupby("DIRECTORIO")["m"].sum()
    h = hog.set_index("DIRECTORIO")
    base = totales.sum(axis=1).reindex(h.index).fillna(0.0)
    con_rec = base + rec_mes.reindex(h.index).fillna(0.0)
    w = h["FEX"]
    diag["reconciliacion_gcmug"] = dict(
        agregado_eventos_sobre_gcmug=float(np.average(base, weights=w) / np.average(h["gcmug"].fillna(0), weights=w)),
        agregado_eventos_mas_recurrentes_sobre_gcmug=float(np.average(con_rec, weights=w) / np.average(h["gcmug"].fillna(0), weights=w)),
        media_mensual_eventos=float(np.average(base, weights=w)), media_mensual_recurrentes=float(np.average(rec_mes.reindex(h.index).fillna(0.0), weights=w)),
        media_mensual_gcmug=float(np.average(h["gcmug"].fillna(0), weights=w)),
        nota="validación contra el consolidado de DANE, no calibración; ambos salen del mismo insumo (consistencia, no prueba)")
    return dict(P=P, hogares=hog, eventos=ev, recurrentes=rec, totales=totales, kappa=kappa, mezcla=mezcla, cuentas=cuentas,
                diag=diag, diag_cuentas=diag_cuentas, ipc_serie=serie, modo_ipc=modo_ipc, referencia_ipc=referencia_ipc)
