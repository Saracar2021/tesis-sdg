"""Priors bayesianos condicionados por celda estrato agrupado × quintil de ICGU (WP3, Etapa 1) y muestreo de perfiles.

Convierte las distribuciones de Bogotá urbano (con factor de expansión) en priors por celda (3 estratos × 5 quintiles = 15),
con respaldo jerárquico hacia el total urbano nacional de la ENPH en las celdas ralas (``sdg.encogimiento``). Lee SOLO vía
``sdg.carga`` y recalcula desde los microdatos: NO lee ``outputs/distribuciones/*.csv`` (esos CSV son la referencia
independiente contra la que ``tests/test_priors.py`` valida el resultado).

Qué prior sale de cada fuente (CLAUDE.md: no se cruzan INGLABO e ICGU)
  ENPH hogares      : masa de las 15 celdas, ICGU, forma de pago NC2R, medio de pago P438 por subcapítulo.
  ENPH personas     : SOLO la asociación posición ocupacional × quintil dado el estrato (decisión 4: se verificó que existe).
  GEIH 2025         : nivel por estrato de la posición ocupacional y de la formalidad (P6440, P6920, P6990 juntas; P6450),
                      y P(bancarizado | estrato) para el repeso D15.
La posición por celda usa los niveles de GEIH por estrato y la asociación con el quintil de ENPH, combinados por IPF
(se conservan las razones de momios de ENPH y se imponen los márgenes de GEIH). Supuesto declarado: esa asociación de
2016-17 se mantiene en 2025.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from sdg import carga, codigos as cod
from sdg.encogimiento import Problema, Stat, cadena, elegir_kappa, ipf, n_efectivo, stat_vacio
from sdg.pesos import cortes_ponderados, grupo_por_cortes

RAIZ = carga.RAIZ
SEED = 42
RUTA_PRIORS = RAIZ / "outputs" / "priors" / "priors.json"
REDONDEO = 12  # decimales al serializar: el hash de priors.json no depende de diferencias de último bit entre plataformas

ESTRATOS = list(carga.ESTRATO_GRUPOS)
QUINTILES = [1, 2, 3, 4, 5]
CELDAS = [(e, q) for e in ESTRATOS for q in QUINTILES]  # orden fijo: estrato bajo→alto, quintil Q1→Q5

# --- categorías ------------------------------------------------------------------------------------
NC2R_CATS = list(cod.FORMA_PAGO_NC2R)      # 1 débito, 2 crédito, 3 efectivo, 4 fiado, 5 bonos, 6 otra   (NO es el esquema de P438)
P438_CATS = list(cod.MEDIO_PAGO_P438)      # 1 débito, 2 crédito, 3 efectivo, 4 bonos, 5 cheques, 6 otro (NO es el esquema de NC2R)
# P6430 NO tiene el mismo esquema en las dos fuentes desde el código 7 (verificado en el DDI de la ENPH y en sdg.codigos):
#   GEIH 2025 : 7 = jornalero o peón, 8 = otro                                  (sdg.codigos.POSICION_OCUPACIONAL_P6430)
#   ENPH 16-17: 7 = sin remuneración en empresas de otros hogares, 8 = jornalero o peón, 9 = otro
# Se comparan solo los códigos 1-6 (idénticos) y el resto se agrupa en «otros» (en GEIH son 5 de 13 552 ocupados, 0,03 %).
POS_CATS = ["1", "2", "3", "4", "5", "6", "otros"]
POS_GEIH = {"1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "otros", "8": "otros"}
POS_ENPH = {"1": "1", "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "otros", "8": "otros", "9": "otros"}
POS_ETIQUETAS = {"1": "Obrero o empleado de empresa particular", "2": "Obrero o empleado del gobierno", "3": "Empleado doméstico",
                 "4": "Trabajador por cuenta propia", "5": "Patrón o empleador", "6": "Trabajador familiar sin remuneración",
                 "otros": "Otros (GEIH 7-8; ENPH 7-9)"}
# Formalidad (D10): componentes por separado, sin índice propio. Se muestrean JUNTOS (P6440, P6920, P6990) para no inventar
# combinaciones incoherentes (p. ej. contrato escrito y sin pensión con la frecuencia que daría la independencia).
FORM_VARS = ("P6440", "P6920", "P6990")
FORM_VALIDOS = {"P6440": list(cod.TIENE_CONTRATO_P6440), "P6920": list(cod.COTIZA_PENSION_P6920), "P6990": ["1", "2"]}  # 9 = no sabe → sin dato
FORM_CATS = [f"{a}|{b}|{c}" for a in FORM_VALIDOS["P6440"] for b in FORM_VALIDOS["P6920"] for c in FORM_VALIDOS["P6990"]]
TC_CATS = ["1", "2"]  # P6450: 1 verbal, 2 escrito (solo si P6440 == 1)

L17_MEZCLA = ("E11", "H11", "H12", "I12", "J11")  # subcapítulos que mezclan categorías de la taxonomía (L17)
P438_SIN_COLUMNA = ("J14", "K11")                 # existen en la base de artículos pero no tienen columna P438
P438_NO_VERIFICADO = ("J13",)                     # PD16


def clave(e: str, q: int) -> str:
    return f"{e}|Q{int(q)}"


def _norm(k):
    """Normaliza una clave de groupby: tuplas con cuantiles enteros y textos."""
    if isinstance(k, tuple):
        return tuple(int(x) if isinstance(x, (float, np.floating, np.integer)) else str(x) for x in k)
    return int(k) if isinstance(k, (float, np.floating, np.integer)) else str(k)


# ================================================================================================
# estadísticos ponderados
# ================================================================================================
def _stats(df: pd.DataFrame, col: str, cats: list[str], claves: list, llave: tuple[str, ...]) -> dict:
    """``{clave: Stat}`` para TODAS las claves (``stat_vacio`` si la celda no tiene filas válidas). Peso = FEX."""
    out = {c: stat_vacio(len(cats)) for c in claves}
    d = df[df[col].isin(cats)]
    if d.empty:
        return out
    for k, g in d.groupby(list(llave), observed=True):
        k = _norm(k if isinstance(k, tuple) else (k,))
        k = k if len(llave) > 1 else k[0]
        if k not in out:
            continue
        s = g.groupby(col, observed=True)["FEX"].sum().reindex(cats, fill_value=0.0).to_numpy(float)
        out[k] = Stat(s / s.sum(), n_efectivo(g["FEX"].to_numpy()), len(g), float(s.sum()))
    return out


def _stat_global(df: pd.DataFrame, col: str, cats: list[str]) -> Stat:
    d = df[df[col].isin(cats)]
    if d.empty:
        raise ValueError(f"marginal vacía para {col}")
    s = d.groupby(col, observed=True)["FEX"].sum().reindex(cats, fill_value=0.0).to_numpy(float)
    return Stat(s / s.sum(), n_efectivo(d["FEX"].to_numpy()), len(d), float(s.sum()))


def _marginal(df: pd.DataFrame, col: str, cats: list[str]) -> np.ndarray:
    return _stat_global(df, col, cats).p


@dataclass
class Familia:
    """Una variable categórica con su jerarquía de encogimiento (ver ``sdg.encogimiento.cadena``)."""
    nombre: str
    grupo: str                 # comparte κ̂ con las demás familias del mismo grupo (p. ej. los 29 subcapítulos P438)
    cats: list[str]
    raiz: np.ndarray
    niveles: list[dict]
    padre_de: list[Callable]
    unidad: str                # «hogar» o «persona ocupada»
    calib: Stat | None = None  # marginal del nivel fino (Bogotá): fija el NIVEL del padre nacional (ver encogimiento.Problema)

    def problema(self) -> Problema:
        return Problema(self.raiz, self.niveles, self.padre_de, self.calib)


def _fam_enph(nombre: str, grupo: str, df: pd.DataFrame, col: str, cats: list[str], unidad: str, sin_bogota_en_padre: bool) -> Familia:
    """raíz = marginal urbana nacional → celdas urbanas nacionales (cortes de Bogotá) → celdas de Bogotá.

    El padre nacional se recalibra al marginal de Bogotá (``calib``): aporta la forma entre celdas, no el nivel."""
    urb = df[df["urbano"] & df["estrato_g"].notna() & df["quintil"].notna()]
    padre = urb[~urb["bogota"]] if sin_bogota_en_padre else urb
    llave = ("estrato_g", "quintil")
    bog = urb[urb["bogota"]]
    return Familia(nombre, grupo, cats, _marginal(padre, col, cats),
                   [_stats(padre, col, cats, CELDAS, llave), _stats(bog, col, cats, CELDAS, llave)],
                   [lambda k: k], unidad, calib=_stat_global(bog, col, cats))


def _fam_geih_pos(oc: pd.DataFrame) -> Familia:
    """raíz = marginal de Bogotá → estrato (GEIH no tiene ICGU: no hay nivel de quintil)."""
    d = oc[oc["estrato_g"].notna() & oc["pos_g"].notna()]
    return Familia("pos_geih", "pos_geih", POS_CATS, _marginal(d, "pos_g", POS_CATS),
                   [_stats(d, "pos_g", POS_CATS, ESTRATOS, ("estrato_g",))], [], "persona ocupada")


def _fam_geih_form(nombre: str, grupo: str, oc: pd.DataFrame, col: str, cats: list[str]) -> Familia:
    """raíz = marginal de Bogotá → posición → (estrato, posición)."""
    d = oc[oc["estrato_g"].notna() & oc["pos_g"].notna()]
    claves_ep = [(e, p) for e in ESTRATOS for p in POS_CATS]
    return Familia(nombre, grupo, cats, _marginal(d, col, cats),
                   [_stats(d, col, cats, POS_CATS, ("pos_g",)), _stats(d, col, cats, claves_ep, ("estrato_g", "pos_g"))],
                   [lambda k: k[1]], "persona ocupada")


# ================================================================================================
# carga (todo vía sdg.carga)
# ================================================================================================
@dataclass
class Insumos:
    hog: pd.DataFrame                      # ENPH hogares, TODO el país (con urbano/bogota/estrato_g/quintil)
    cortes_icgu: list[float]               # cortes de quintil calculados DENTRO de Bogotá (CLAUDE.md)
    mp: pd.DataFrame                       # ENPH P438 (nacional) con celda
    pers: pd.DataFrame                     # ENPH personas con celda
    geih_oc: pd.DataFrame                  # GEIH ocupados Bogotá con estrato del hogar
    p_banc: dict                           # P(bancarizado | estrato) GEIH
    geih_hogares_n: int
    m_pers: dict                           # ENPH Bogotá: masa de personas ocupadas por quintil dentro de cada estrato
    mezcla_geih: dict                      # GEIH: participación de cada estrato en los ocupados
    familias: dict = field(default_factory=dict)
    familias_sin_bogota: dict = field(default_factory=dict)
    avisos: list = field(default_factory=list)


def _cargar_enph() -> tuple:
    h = carga.cargar_enph("viviendas_hogares", dominio="todo", columnas=["P3", "P8520S1A1", "ICGU", "NC2R_CC_P6"])
    h["bogota"] = h["DOMINIO"] == carga.DOMINIO_BOGOTA_ENPH
    h["urbano"] = h["P3"] == "1"                                   # clase 1 = cabeceras (DDI, variable P3)
    h["estrato_g"] = carga.estrato_agrupado(h["P8520S1A1"])
    h["icgu"] = carga.a_numero(h["ICGU"])
    ok = h["bogota"] & h["icgu"].notna()
    cortes = cortes_ponderados(h.loc[ok, "icgu"], h.loc[ok, "FEX"], 5)  # quintiles DENTRO de Bogotá
    h["quintil"] = grupo_por_cortes(h["icgu"], cortes)             # los mismos cortes se aplican a todo el total urbano
    celda = h[["DIRECTORIO", "bogota", "urbano", "estrato_g", "quintil"]]

    mp = carga.cargar_enph("hogares/gastos_menos_frecuentes_medio_pago.csv", dominio="todo")
    mp = carga.unir_enph_hogar(mp, celda)
    pe = carga.cargar_enph("personas/caracteristicas_generales_personas.csv", dominio="todo", columnas=["P6430", "P6440", "P6920", "P6990"])
    pe = carga.unir_enph_hogar(pe, celda)
    pe["pos_g"] = pe["P6430"].map(POS_ENPH)                         # NaN si no es ocupado o el código no está en la lista
    return h, cortes, mp, pe


def _cargar_geih() -> tuple:
    oc = carga.cargar_geih("ocupados", columnas=["P6430", "P6440", "P6450", "P6920", "P6990"])
    cols_prod = list(cod.COLUMNAS_PRODUCTO_P5222)
    dh = carga.cargar_geih("datos_hogar", columnas=["P4030S1A1", *cols_prod, "P5222S9", "P5222S10"])
    dh["estrato_g"] = carga.estrato_agrupado(dh["P4030S1A1"])
    oc = carga.unir_geih(oc, dh[[*carga.LLAVE_GEIH_HOGAR, "MES", "estrato_g"]], nivel="hogar", nombre="GEIH ocupados -> datos_hogar (estrato)")
    oc["pos_g"] = oc["P6430"].map(POS_GEIH)
    ok = np.ones(len(oc), dtype=bool)
    for v in FORM_VARS:
        ok &= oc[v].isin(FORM_VALIDOS[v]).to_numpy()
    oc["form"] = np.where(ok, oc["P6440"] + "|" + oc["P6920"] + "|" + oc["P6990"], None)
    oc["tc"] = oc["P6450"].where(oc["P6450"].isin(TC_CATS) & (oc["P6440"] == "1"))
    # P(bancarizado | estrato agrupado): hogares con ≥1 producto financiero entre los que declaran tenencia o ninguno (D15)
    tiene = np.column_stack([dh[c] == "1" for c in cols_prod]).any(axis=1)
    dh["tenencia"] = np.select([tiene, dh["P5222S9"] == "1"], ["con", "sin"], default="")
    v = dh[dh["tenencia"].isin(["con", "sin"]) & dh["estrato_g"].notna()]
    p_banc = {e: float(g.loc[g["tenencia"] == "con", "FEX"].sum() / g["FEX"].sum()) for e, g in v.groupby("estrato_g", observed=True)}
    return oc, p_banc, len(dh)


def cargar_insumos() -> Insumos:
    """Carga ENPH y GEIH vía ``sdg.carga`` y arma las familias de variables. Determinista; no escribe nada."""
    h, cortes, mp, pe = _cargar_enph()
    oc, p_banc, n_dh = _cargar_geih()

    # ocupados ENPH Bogotá: masa por quintil dentro de cada estrato (márgenes de fila del IPF)
    pb = pe[pe["bogota"] & pe["pos_g"].notna() & pe["estrato_g"].notna() & pe["quintil"].notna()]
    m_pers = {}
    for e in ESTRATOS:
        g = pb[pb["estrato_g"] == e]
        s = np.array([g.loc[g["quintil"] == q, "FEX"].sum() for q in QUINTILES], dtype=float)
        m_pers[e] = s / s.sum()
    d = oc[oc["estrato_g"].notna() & oc["pos_g"].notna()]
    w = d.groupby("estrato_g", observed=True)["FEX"].sum()
    mezcla = {e: float(w.get(e, 0.0) / w.sum()) for e in ESTRATOS}

    ins = Insumos(hog=h, cortes_icgu=cortes, mp=mp, pers=pe, geih_oc=oc, p_banc=p_banc, geih_hogares_n=n_dh, m_pers=m_pers, mezcla_geih=mezcla)
    cols = [c for c in mp.columns if c.startswith("P438")]
    if len(cols) != 29:
        raise ValueError(f"se esperaban 29 columnas P438*, hay {len(cols)}")
    for sin in (False, True):
        fam = {"nc2r": _fam_enph("nc2r", "nc2r", h, "NC2R_CC_P6", NC2R_CATS, "hogar", sin),
               "pos_enph": _fam_enph("pos_enph", "pos_enph", pe, "pos_g", POS_CATS, "persona ocupada", sin)}
        for c in cols:
            fam[f"p438:{c[4:]}"] = _fam_enph(f"p438:{c[4:]}", "p438", mp, c, P438_CATS, "hogar", sin)
        fam["pos_geih"] = _fam_geih_pos(oc)
        fam["formalidad"] = _fam_geih_form("formalidad", "formalidad", oc, "form", FORM_CATS)
        fam["tipo_contrato"] = _fam_geih_form("tipo_contrato", "tipo_contrato", oc, "tc", TC_CATS)
        (ins.familias_sin_bogota if sin else ins.familias).update(fam)
    return ins


# ================================================================================================
# estimación
# ================================================================================================
def estimar_kappas(ins: Insumos, deff: float = 1.0, sin_bogota: bool = False) -> dict:
    """κ̂ por grupo de familias (máxima verosimilitud marginal). ``{grupo: {kappa, en_frontera, perfil}}``."""
    fams = (ins.familias_sin_bogota if sin_bogota else ins.familias).values()
    grupos = sorted({f.grupo for f in fams})
    return {g: elegir_kappa([f.problema() for f in fams if f.grupo == g], deff) for g in grupos}


def posteriores(ins: Insumos, kappas: dict, deff: float = 1.0, sin_bogota: bool = False) -> dict:
    """``{familia: {clave_celda: vector}}`` con el nivel más fino de cada jerarquía."""
    fams = ins.familias_sin_bogota if sin_bogota else ins.familias
    return {n: cadena(f.raiz, f.niveles, f.padre_de, kappas[f.grupo], deff, f.calib)[-1] for n, f in fams.items()}


def inclinar_posicion(post_enph: dict, post_geih: dict, m_pers: dict) -> dict:
    """P(posición | estrato, quintil): nivel GEIH por estrato × asociación con el quintil de ENPH (IPF por estrato).

    Semilla T0[q,x] = m(q|e) · π_GEIH(x|e) · R(q,x), con R = π_ENPH(x|e,q) / π̄_ENPH(x|e) y π̄ = Σ_q m(q|e) π_ENPH(x|e,q).
    IPF fuerza filas = m(q|e) y columnas = π_GEIH(x|e): el promedio de la posición sobre los quintiles reproduce el nivel de GEIH
    y se conservan las razones de momios de ENPH. m(q|e) es la masa de PERSONAS ocupadas (no de hogares).
    """
    out = {}
    for e in ESTRATOS:
        pi_g = np.asarray(post_geih[e], dtype=float)
        m = np.asarray(m_pers[e], dtype=float)
        s = np.vstack([post_enph[(e, q)] for q in QUINTILES])
        pbar = m @ s
        r = np.divide(s, pbar[None, :], out=np.ones_like(s), where=pbar[None, :] > 0)
        t = ipf(m[:, None] * pi_g[None, :] * r, m, pi_g)
        for i, q in enumerate(QUINTILES):
            out[(e, q)] = t[i] / m[i] if m[i] > 0 else pi_g.copy()
    return out


def construir(ins: Insumos, *, kappas: dict | None = None, kappa_mult: float = 1.0, kappa_fijo: float | None = None,
              deff: float = 1.0, sin_bogota: bool = False) -> dict:
    """Todos los priors (arreglos numpy) para un escenario. El escenario base es kappa_mult=1, deff=1, sin_bogota=False."""
    if kappas is None:
        kappas = estimar_kappas(ins, deff, sin_bogota)
    k = {g: float(kappa_fijo if kappa_fijo is not None else v["kappa"] * kappa_mult) for g, v in kappas.items()}
    post = posteriores(ins, k, deff, sin_bogota)
    pos_celda = inclinar_posicion(post["pos_enph"], post["pos_geih"], ins.m_pers)
    return {"kappa": k, "kappas_detalle": kappas, "post": post, "posicion": pos_celda, "deff": deff, "sin_bogota": sin_bogota}


# ================================================================================================
# priors.json
# ================================================================================================
def _r(x):
    return [round(float(v), REDONDEO) for v in x]


def tabla_celdas(ins: Insumos) -> pd.DataFrame:
    """Masa de las 15 celdas (ENPH Bogotá, FEX, sin suavizar) y ICGU por quintil."""
    h = ins.hog[ins.hog["bogota"]]
    v = h[h["estrato_g"].notna() & h["quintil"].notna()]
    filas = []
    for (e, q) in CELDAS:
        g = v[(v["estrato_g"] == e) & (v["quintil"] == q)]
        gq = h[h["quintil"] == q]
        nac = ins.hog[ins.hog["urbano"] & (ins.hog["estrato_g"] == e) & (ins.hog["quintil"] == q)]
        filas.append(dict(estrato_agrupado=e, quintil=f"Q{q}", n=len(g), expandido=float(g["FEX"].sum()), n_icgu_cero=int((g["icgu"] == 0).sum()),
                          icgu_min_quintil=float(gq["icgu"].min()), icgu_max_quintil=float(gq["icgu"].max()), n_urbano_nacional=len(nac)))
    t = pd.DataFrame(filas)
    t["p_celda_todos"] = t["expandido"] / t["expandido"].sum()
    t["p_bancarizado_estrato"] = t["estrato_agrupado"].map(ins.p_banc)
    t["expandido_bancarizado"] = t["expandido"] * t["p_bancarizado_estrato"]
    t["p_celda_bancarizado"] = t["expandido_bancarizado"] / t["expandido_bancarizado"].sum()
    return t


def construir_priors_json(ins: Insumos, res: dict, celdas: pd.DataFrame) -> dict:
    """Serializa el escenario base. Las listas de probabilidades siguen el orden de ``categorias``."""
    post, pos, kappas, deff = res["post"], res["posicion"], res["kappas_detalle"], res["deff"]
    sub = sorted(c[4:] for c in ins.mp.columns if c.startswith("P438"))
    pj = {
        "meta": {
            "modulo": "WP3 priors", "semilla": SEED, "redondeo_decimales": REDONDEO,
            "definicion_rala": "celda rala si n_ef (Kish) < κ̂ de su familia, es decir, si el padre pesa más que la celda (PD1)",
            "encogimiento": "π_post = (n_ef·p̂ + κ·π_padre)/(n_ef + κ), jerárquico: marginal urbana nacional → celda urbana nacional (cortes de Bogotá) → celda de Bogotá (PD2); "
                            "el padre nacional se recalibra al marginal de Bogotá (aporta la forma entre celdas, no el nivel)",
            "universo_perfil": "hogar bancarizado (D15) con una persona ocupada de referencia; masa de celdas = ENPH Bogotá × P(bancarizado|estrato) GEIH",
            "medio_pago": "condicional a que el hogar compre en el subcapítulo (la probabilidad de comprar NO es parte de este módulo: PD5/WP6)",
            "p438_sin_columna": list(P438_SIN_COLUMNA), "p438_no_verificado": list(P438_NO_VERIFICADO), "p438_mezcla_categorias_L17": list(L17_MEZCLA),
            "deff_cluster": deff,
        },
        "kappa": {g: {"kappa": float(res["kappa"][g]), "en_frontera": bool(kappas[g]["en_frontera"])} for g in kappas},
        "orden_celdas": [clave(e, q) for e, q in CELDAS],
        "categorias": {
            "nc2r": {"codigos": NC2R_CATS, "etiquetas": cod.FORMA_PAGO_NC2R}, "p438": {"codigos": P438_CATS, "etiquetas": cod.MEDIO_PAGO_P438},
            "posicion": {"codigos": POS_CATS, "etiquetas": POS_ETIQUETAS}, "formalidad": {"codigos": FORM_CATS, "variables": list(FORM_VARS)},
            "tipo_contrato": {"codigos": TC_CATS, "etiquetas": cod.TIPO_CONTRATO_P6450},
        },
        "celdas": {clave(r.estrato_agrupado, int(r.quintil[1])): dict(
            estrato=r.estrato_agrupado, quintil=int(r.quintil[1]), n_hogares=int(r.n), masa_hogares=round(float(r.expandido), 6),
            p_celda_todos=round(float(r.p_celda_todos), REDONDEO), p_celda_bancarizado=round(float(r.p_celda_bancarizado), REDONDEO),
            icgu_min_quintil=float(r.icgu_min_quintil), icgu_max_quintil=float(r.icgu_max_quintil)) for r in celdas.itertuples()},
        "cortes_icgu_bogota": [float(c) for c in ins.cortes_icgu],
        "bancarizacion": {"p_bancarizado_estrato": {e: round(float(ins.p_banc[e]), REDONDEO) for e in ESTRATOS}},
        "nc2r": {clave(e, q): _r(post["nc2r"][(e, q)]) for e, q in CELDAS},
        "p438": {s: {clave(e, q): _r(post[f"p438:{s}"][(e, q)]) for e, q in CELDAS} for s in sub} | {s: None for s in P438_SIN_COLUMNA},
        "posicion": {clave(e, q): _r(pos[(e, q)]) for e, q in CELDAS},
        "posicion_nivel_geih_por_estrato": {e: _r(post["pos_geih"][e]) for e in ESTRATOS},
        "mezcla_ocupados_geih_por_estrato": {e: round(ins.mezcla_geih[e], REDONDEO) for e in ESTRATOS},
        "masa_personas_ocupadas_enph_por_quintil": {e: _r(ins.m_pers[e]) for e in ESTRATOS},
        "formalidad": {f"{e}|{p}": _r(post["formalidad"][(e, p)]) for e in ESTRATOS for p in POS_CATS},
        "tipo_contrato": {f"{e}|{p}": _r(post["tipo_contrato"][(e, p)]) for e in ESTRATOS for p in POS_CATS},
        # masa expandida (FEX) de quienes respondieron, por celda: sirve para volver de los priors por celda al marginal de Bogotá
        "masa_respuesta": {
            "nc2r": {clave(e, q): round(ins.familias["nc2r"].niveles[-1][(e, q)].w, 6) for e, q in CELDAS},
            "p438": {s: {clave(e, q): round(ins.familias[f"p438:{s}"].niveles[-1][(e, q)].w, 6) for e, q in CELDAS} for s in sub},
            "formalidad": {f"{e}|{p}": round(ins.familias["formalidad"].niveles[-1][(e, p)].w, 6) for e in ESTRATOS for p in POS_CATS},
            "tipo_contrato": {f"{e}|{p}": round(ins.familias["tipo_contrato"].niveles[-1][(e, p)].w, 6) for e in ESTRATOS for p in POS_CATS},
        },
    }
    return pj


def tabla_soporte(ins: Insumos, kappa: dict, deff: float = 1.0, sin_bogota: bool = False) -> pd.DataFrame:
    """Soporte por familia y celda (nivel más fino): n, n_ef, κ̂ y si la celda es rala (n_ef < κ̂, PD1)."""
    filas = []
    for nombre, f in (ins.familias_sin_bogota if sin_bogota else ins.familias).items():
        k = kappa[f.grupo]
        for clv, s in f.niveles[-1].items():
            if isinstance(clv, tuple) and isinstance(clv[1], int):
                e, q, p = clv[0], f"Q{clv[1]}", ""
            elif isinstance(clv, tuple):
                e, q, p = clv[0], "", clv[1]
            else:
                e, q, p = clv, "", ""
            ne = s.neff / deff
            filas.append(dict(familia=f.grupo, variable=nombre.split(":")[-1] if ":" in nombre else nombre, unidad=f.unidad, estrato_agrupado=e,
                              quintil=q, posicion=p, n=s.n, n_ef=ne, masa_expandida=s.w, kappa=k, rala=bool(ne < k),
                              peso_padre=float(k / (ne + k))))
    return pd.DataFrame(filas)


def serializar(pj: dict) -> str:
    return json.dumps(pj, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def sha256_texto(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def cargar_priors(ruta: Path | str | None = None) -> dict:
    return json.loads(Path(ruta or RUTA_PRIORS).read_text(encoding="utf-8"))


# ================================================================================================
# muestreo de perfiles
# ================================================================================================
def _categorica(u: np.ndarray, probs: np.ndarray) -> np.ndarray:
    """Índice de categoría por inversión de la cdf: primer k con cdf[k] > u. Las categorías con probabilidad 0 no se eligen."""
    cdf = np.cumsum(probs, axis=1)
    cdf[:, -1] = 1.0
    return (u[:, None] >= cdf).sum(axis=1)


def muestrear_perfiles(priors: dict, n: int, seed: int = SEED) -> pd.DataFrame:
    """``n`` perfiles de hogar bancarizado. Determinista: mismo ``priors``, ``n`` y ``seed`` → mismo DataFrame.

    Orden de sorteo (una sola matriz de uniformes, columnas fijas, por lo que los primeros n₁ perfiles de un n₂ > n₁ son idénticos):
    celda → NC2R → posición → formalidad (P6440|P6920|P6990) → tipo de contrato → un medio P438 por subcapítulo (orden alfabético).
    Los sorteos se hacen siempre, aunque la variable no aplique, para que el flujo de números aleatorios no dependa de los datos.
    Supuestos: el medio de cada subcapítulo es independiente entre subcapítulos dado la celda; las componentes de formalidad se
    sortean juntas dado (estrato, posición); P6450 solo existe si P6440 == 1; J14 y K11 (sin columna P438) salen vacías.
    """
    if n < 1:
        raise ValueError("n debe ser ≥ 1")
    orden = priors["orden_celdas"]
    sub = sorted(priors["p438"])
    rng = np.random.default_rng(seed)
    u = rng.random((n, 5 + len(sub)))

    p_cel = np.array([priors["celdas"][k]["p_celda_bancarizado"] for k in orden], dtype=float)
    p_cel = p_cel / p_cel.sum()
    ic = _categorica(u[:, 0], np.broadcast_to(p_cel, (n, len(orden))))
    est = np.array([priors["celdas"][k]["estrato"] for k in orden])[ic]
    qui = np.array([priors["celdas"][k]["quintil"] for k in orden])[ic]
    ie = np.array([ESTRATOS.index(priors["celdas"][k]["estrato"]) for k in orden])[ic]

    def por_celda(tabla: dict) -> np.ndarray:
        return np.array([tabla[k] for k in orden], dtype=float)[ic]

    nc2r = np.array(priors["categorias"]["nc2r"]["codigos"])[_categorica(u[:, 1], por_celda(priors["nc2r"]))]
    pos_cod = priors["categorias"]["posicion"]["codigos"]
    ip = _categorica(u[:, 2], por_celda(priors["posicion"]))
    pos = np.array(pos_cod)[ip]
    tabla_f = np.array([[priors["formalidad"][f"{e}|{p}"] for p in pos_cod] for e in ESTRATOS], dtype=float)
    tabla_t = np.array([[priors["tipo_contrato"][f"{e}|{p}"] for p in pos_cod] for e in ESTRATOS], dtype=float)
    form = np.array(priors["categorias"]["formalidad"]["codigos"])[_categorica(u[:, 3], tabla_f[ie, ip])]
    tc = np.array(priors["categorias"]["tipo_contrato"]["codigos"])[_categorica(u[:, 4], tabla_t[ie, ip])]
    partes = pd.Series(form).str.split("|", expand=True)
    p6440, p6920, p6990 = (partes[i].to_numpy(dtype=object) for i in range(3))
    tc = np.where(p6440 == "1", tc, None)

    sal = pd.DataFrame({
        "estrato_agrupado": est, "quintil": np.char.add("Q", qui.astype(str)),
        "icgu_min_quintil": np.array([priors["celdas"][k]["icgu_min_quintil"] for k in orden])[ic],
        "icgu_max_quintil": np.array([priors["celdas"][k]["icgu_max_quintil"] for k in orden])[ic],
        "nc2r_forma_pago": nc2r, "posicion_ocupacional": pos, "P6440": p6440, "P6450": tc, "P6920": p6920, "P6990": p6990})
    med = priors["categorias"]["p438"]["codigos"]
    for j, s in enumerate(sub):
        t = priors["p438"][s]
        if t is None:
            sal[f"p438_{s}"] = None
        else:
            sal[f"p438_{s}"] = np.array(med)[_categorica(u[:, 5 + j], por_celda(t))]
    return sal
