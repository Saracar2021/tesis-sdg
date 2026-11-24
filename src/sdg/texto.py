"""Capa de texto del protocolo (WP6, 2.ª capa): ``descripcion`` de extracto para filas ESTRUCTURADAS.

Para qué. El CTGAN (Etapa 3) sintetiza solo columnas estructuradas (cuenta_tipo, signo, categoria_n1/n2, medio_pago,
origen, formalidad_comercio, canal_p2p, monto, ...): no produce texto. Esta capa le pone la ``descripcion`` que vería
un banco o una billetera, con las MISMAS plantillas (``docs/generador/plantillas_descriptor.csv``) y la MISMA biblioteca
de comercios (``docs/generador/comercios_curados.csv``) del generador por reglas (``sdg.comercios``). Se aplica igual
a las filas emitidas del generador por reglas y a las del CTGAN: con el texto fijo, la diferencia TSTR entre ambas
aísla la capa estructural (ablación reglas → CTGAN).

Qué hace, por fila
  1. ``tipo_evento`` desde los campos estructurales, con la misma tabla de decisión que ``sdg.generador.generar``
     (compra débito/crédito/billetera/PSE, P2P enviada/recibida, nómina, consignación, retiro ATM/corresponsal,
     pago de tarjeta, recarga). La tabla se valida contra las descripciones originales del generador por reglas
     (``validar_contra_reglas``).
  2. Latentes del comercio que el CTGAN no trae (``clase_comercio``, domicilio/en línea, ``concepto`` de los pagos
     recurrentes), sorteados del pool de eventos de la calibración ENPH 2016-17 (``outputs/generador/pool``)
     condicionados a (categoria_n1, categoria_n2), con peso FEX × frecuencia mensual. Con ``categoria_n2`` vacía se
     condiciona solo en ``categoria_n1``. Una tarjeta (débito/crédito) no se asigna a una clase de lugar sin datáfono.
  3. Comercio (``Comercios.asignar``), banco, marca de billetera y empleador (pesos de ``parametros_propios.json``),
     y plantilla (``Plantillas.descripciones``; en P2P sin propósito, restringida al subtipo ya fijado).

Límites declarados
  * D14: NADA de esta capa se calibra con el conjunto real anotado (WP4). Solo lee ``docs/generador/`` (regla propia
    y listados públicos) y ``outputs/generador/pool`` (calibración ENPH). ``agregar_texto`` rechaza rutas bajo ``data/``.
  * No hay perfil en el CTGAN: banco, billetera y empleador se sortean por FILA, no por perfil. Se aplica igual a
    las dos fuentes de la ablación, así que no sesga la comparación, pero el texto pierde la consistencia por cuenta
    que tenía el generador por reglas original.
  * La capa NO repara la estructura. Si el CTGAN emite una combinación que el generador nunca produce (p. ej.
    ``origen=retiro`` con ``categoria_n1=alimentos_mercado``), el texto sigue al evento (RETIRO ATM ...) y la
    etiqueta queda como la sintetizó el CTGAN; la fila se marca en ``incoherencia_estructural`` y se cuenta. Es
    error de la Etapa 3 y el TSTR debe cobrarlo.
  * ``formalidad_comercio`` no condiciona el comercio (no es entrada ni etiqueta del clasificador).
  * Determinista: ``SeedSequence(seed)`` en flujos nombrados; mismas entradas, semilla y versión de numpy → mismo
    resultado. El hash válido es el de la corrida con el ``.venv`` del repositorio.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sdg import carga
from sdg.comercios import CLASES_LINEA, Comercios, Plantillas, _pesos
from sdg.generador import CATEGORIAS_GASTO, DIR_PARAM, DIR_POOL, cargar_lugares, cargar_parametros

SEED = 42
FLUJOS_TEXTO = ("latentes", "comercios", "cuentas", "descriptores")
SIN_N2 = "(sin_n2)"
COLUMNAS_ESTRUCTURA = ["cuenta_tipo", "signo", "categoria_n1", "categoria_n2", "medio_pago", "origen", "canal_p2p"]
ORIGENES_COMPRA = ("compra", "pago_recurrente")
MEDIOS_TARJETA = ("tarjeta_debito", "tarjeta_credito")

# categoria_n1 que cada origen produce en el generador por reglas
N1_POR_ORIGEN = {
    "compra": set(CATEGORIAS_GASTO), "pago_recurrente": set(CATEGORIAS_GASTO),
    "nomina": {"ingreso"}, "ingreso_no_asalariado": {"ingreso"}, "p2p_sin_proposito": {"transferencias_p2p"},
    "retiro": {"retiro_efectivo"}, "pago_tarjeta": {"obligaciones_financieras"}, "recarga_billetera": {"movimiento_propio"},
}
# (cuenta_tipo, signo) admitidos por origen; compra/pago_recurrente: cualquier cuenta con signo "-"
CUENTA_SIGNO_POR_ORIGEN = {
    "nomina": {("banco", "+"), ("billetera", "+")}, "ingreso_no_asalariado": {("banco", "+"), ("billetera", "+")},
    "p2p_sin_proposito": {("banco", "+"), ("banco", "-"), ("billetera", "+"), ("billetera", "-")},
    "retiro": {("banco", "-"), ("billetera", "-")},
    "pago_tarjeta": {("banco", "-"), ("tarjeta_credito", "+")}, "recarga_billetera": {("banco", "-"), ("billetera", "+")},
}


def _flujos(seed: int) -> dict:
    return {k: np.random.default_rng(s) for k, s in zip(FLUJOS_TEXTO, np.random.SeedSequence(seed).spawn(len(FLUJOS_TEXTO)))}


def _n2(df: pd.DataFrame) -> np.ndarray:
    v = df["categoria_n2"].astype(object).where(df["categoria_n2"].notna(), "").to_numpy(dtype=object).copy()
    v[v == SIN_N2] = ""
    return v


# ---------------------------------------------------------------------------------------------- 1. tipo de evento
def tipo_evento(df: pd.DataFrame) -> np.ndarray:
    """Misma tabla de decisión que ``sdg.generador.generar`` (capa emitida)."""
    o = df["origen"].to_numpy(dtype=object)
    m = df["medio_pago"].to_numpy(dtype=object)
    c = df["cuenta_tipo"].to_numpy(dtype=object)
    s = df["signo"].to_numpy(dtype=object)
    p = df["canal_p2p"].astype(bool).to_numpy()
    n2 = _n2(df)
    wb = np.where(c == "billetera", "billetera", "banco").astype(object)   # tarjeta_credito fuera de compra → banco
    compra = np.isin(o, ORIGENES_COMPRA)
    ing = o == "ingreso_no_asalariado"
    cond = [
        compra & (m == "tarjeta_debito"), compra & (m == "tarjeta_credito"),
        compra & (m == "billetera_digital") & p, compra & (m == "billetera_digital"),
        compra & (m == "transferencia_bancaria") & p, compra,
        o == "nomina", ing & p, ing & (c == "billetera"), ing,
        (o == "p2p_sin_proposito") & (s == "-"), o == "p2p_sin_proposito",
        (o == "retiro") & (n2 == "corresponsal"), o == "retiro",
        (o == "pago_tarjeta") & (s == "-"), o == "pago_tarjeta",
        (o == "recarga_billetera") & (s == "-"), o == "recarga_billetera",
    ]
    elec = [
        "compra_debito", "compra_credito", "p2p_enviada_billetera", "compra_billetera", "p2p_enviada_banco", "pago_pse",
        "nomina", "p2p_recibida_" + wb, "p2p_recibida_billetera", "ingreso_consignacion",
        "p2p_enviada_" + wb, "p2p_recibida_" + wb, "retiro_corresponsal_" + wb, "retiro_atm_" + wb,
        "pago_tc_origen", "pago_tc_destino", "recarga_origen", "recarga_destino",
    ]
    t = np.select(cond, [np.broadcast_to(np.asarray(e, dtype=object), len(df)) for e in elec], default="")
    if (t == "").any():
        raise ValueError(f"origen sin tipo de evento: {sorted(set(o[t == '']))}")
    return t.astype(object)


def incoherencias(df: pd.DataFrame) -> np.ndarray:
    """Motivo ('' si ninguna) de las combinaciones que el generador por reglas nunca emite. Solo diagnóstico."""
    o = df["origen"].to_numpy(dtype=object)
    n1 = df["categoria_n1"].to_numpy(dtype=object)
    cs = list(zip(df["cuenta_tipo"], df["signo"]))
    ok_n1 = np.array([n in N1_POR_ORIGEN.get(x, set()) for x, n in zip(o, n1)])
    ok_cs = np.array([(x in ORIGENES_COMPRA and k[1] == "-") or (k in CUENTA_SIGNO_POR_ORIGEN.get(x, set()))
                      for x, k in zip(o, cs)])
    out = np.full(len(df), "", dtype=object)
    out[~ok_cs] = "cuenta_signo_vs_origen"
    out[~ok_n1] = "origen_vs_categoria_n1"
    out[~ok_n1 & ~ok_cs] = "origen_vs_categoria_n1+cuenta_signo"
    return out


# ---------------------------------------------------------------------------------------------- 2. latentes
def _sortear_por_grupo(rng, llaves: pd.DataFrame, tabla: pd.DataFrame, col_llave: list[str], col_valor: list[str],
                       col_peso: str, filtro=None) -> pd.DataFrame:
    """Para cada grupo de ``llaves`` (orden lexicográfico) sortea filas de ``tabla`` que comparten la llave."""
    out = pd.DataFrame(index=llaves.index, columns=col_valor, dtype=object)
    idx_tabla = tabla.groupby(col_llave, sort=True).indices
    for k, idx in sorted(llaves.groupby(list(llaves.columns), sort=True).indices.items()):
        k = k if isinstance(k, tuple) else (k,)
        cand = tabla.iloc[idx_tabla[k[:len(col_llave)]]] if k[:len(col_llave)] in idx_tabla else tabla.iloc[0:0]
        if filtro is not None and len(cand):
            cand = filtro(cand, k)
        if not len(cand):
            continue
        j = rng.choice(len(cand), size=len(idx), p=_pesos(cand[col_peso].to_numpy()))
        out.iloc[idx, :] = cand[col_valor].to_numpy()[j]
    return out


def latentes(df: pd.DataFrame, rng: np.random.Generator, eventos: pd.DataFrame, recurrentes: pd.DataFrame,
             lugares: pd.DataFrame, par: dict) -> pd.DataFrame:
    """clase_comercio, linea, concepto y sucursal_ok para las filas de compra / pago recurrente."""
    n1 = df["categoria_n1"].to_numpy(dtype=object)
    n2 = _n2(df)
    medio = df["medio_pago"].to_numpy(dtype=object)
    rec = (df["origen"] == "pago_recurrente").to_numpy()
    acepta = lugares["acepta_tarjeta"].to_dict()

    ev = eventos.assign(categoria_n2=eventos["categoria_n2"].fillna(""), peso=eventos["FEX"] * eventos["factor"])
    rc = recurrentes.assign(categoria_n2=recurrentes["categoria_n2"].fillna(""), peso=recurrentes["FEX"] * recurrentes["factor"])
    tarjeta = np.isin(medio, MEDIOS_TARJETA)

    def sin_datafono(cand, k):
        if k[-1]:                                    # el grupo paga con tarjeta: fuera las clases sin datáfono
            ok = cand["clase_comercio"].map(lambda x: acepta.get(x, 1) == 1).to_numpy()
            return cand[ok] if ok.any() else cand
        return cand

    res = pd.DataFrame({"clase_comercio": "", "domicilio": 0, "concepto": ""}, index=df.index, dtype=object)
    # eventos no recurrentes: (n1, n2) y, si no hay soporte en el pool, solo n1
    q = ~rec
    for nivel in ("n1n2", "n1"):
        pend = q & (res["clase_comercio"] == "").to_numpy()
        if not pend.any():
            break
        if nivel == "n1n2":
            ll = pd.DataFrame({"a": n1[pend], "b": n2[pend], "t": tarjeta[pend]}, index=df.index[pend])
            s = _sortear_por_grupo(rng, ll, ev, ["categoria_n1", "categoria_n2"], ["clase_comercio", "domicilio"], "peso", sin_datafono)
        else:
            ll = pd.DataFrame({"a": n1[pend], "t": tarjeta[pend]}, index=df.index[pend])
            s = _sortear_por_grupo(rng, ll, ev, ["categoria_n1"], ["clase_comercio", "domicilio"], "peso", sin_datafono)
        ok = s["clase_comercio"].notna()
        res.loc[s.index[ok], ["clase_comercio", "domicilio"]] = s.loc[ok, ["clase_comercio", "domicilio"]].to_numpy()
    # pagos recurrentes: concepto por (n1, n2) y, si no hay soporte, por n1; clase según la regla del arriendo
    for nivel in ("n1n2", "n1"):
        pend = rec & (res["concepto"] == "").to_numpy()
        if not pend.any():
            break
        if nivel == "n1n2":
            ll = pd.DataFrame({"a": n1[pend], "b": n2[pend]}, index=df.index[pend])
            s = _sortear_por_grupo(rng, ll, rc, ["categoria_n1", "categoria_n2"], ["concepto"], "peso")
        else:
            ll = pd.DataFrame({"a": n1[pend]}, index=df.index[pend])
            s = _sortear_por_grupo(rng, ll, rc, ["categoria_n1"], ["concepto"], "peso")
        ok = s["concepto"].notna()
        res.loc[s.index[ok], "concepto"] = s.loc[ok, "concepto"].to_numpy()
    conc = res["concepto"].to_numpy(dtype=object)
    u = rng.random(len(df))
    clase_rec = np.where((conc == "arriendo") & (u >= par["arriendo.p_inmobiliaria"]), "persona", "especializado")
    res.loc[rec, "clase_comercio"] = clase_rec[rec]
    res["linea"] = res["clase_comercio"].isin(CLASES_LINEA).to_numpy() | (res["domicilio"].astype(int) == 1).to_numpy()
    res["sucursal_ok"] = np.isin(medio, ["tarjeta_debito", "tarjeta_credito", "billetera_digital"]) & ~rec
    res["categoria_n1"], res["categoria_n2"] = n1, n2
    return res


# ---------------------------------------------------------------------------------------------- 3. texto
def _cargar_pool(dir_pool: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    ev = pd.read_csv(dir_pool / "eventos.csv.gz", dtype={"clase_comercio": str, "categoria_n2": str, "cap": str},
                     usecols=["FEX", "categoria_n1", "categoria_n2", "clase_comercio", "domicilio", "factor"])
    rc = pd.read_csv(dir_pool / "recurrentes.csv.gz", dtype={"concepto": str, "categoria_n2": str},
                     usecols=["FEX", "concepto", "categoria_n1", "categoria_n2", "factor"])
    return ev, rc


def _rechazar_reales(*rutas: Path) -> None:
    datos = (carga.RAIZ / "data").resolve()
    for r in rutas:
        if datos == Path(r).resolve() or datos in Path(r).resolve().parents:
            raise PermissionError(f"D14: la capa de texto no puede leer {r} (bajo data/)")


def agregar_texto(df: pd.DataFrame, seed: int = SEED, dir_param: Path = DIR_PARAM, dir_pool: Path = DIR_POOL
                  ) -> tuple[pd.DataFrame, dict]:
    """Devuelve ``df`` + descripcion, tipo_evento, fuente_etiqueta, incoherencia_estructural, y un diagnóstico."""
    _rechazar_reales(dir_param, dir_pool)
    faltan = [c for c in COLUMNAS_ESTRUCTURA if c not in df.columns]
    if faltan:
        raise KeyError(f"faltan columnas estructurales: {faltan}")
    df = df.reset_index(drop=True)
    rng = _flujos(seed)
    par, _ = cargar_parametros(dir_param / "parametros_propios.json")
    lugares = cargar_lugares(dir_param)
    eventos, recurrentes = _cargar_pool(dir_pool)
    com, pl = Comercios(dir_param, par["descriptores.p_sucursal"]), Plantillas(dir_param)
    n = len(df)

    tev = tipo_evento(df)
    p2p = df["canal_p2p"].astype(bool).to_numpy()
    compra = np.isin(df["origen"].to_numpy(dtype=object), ORIGENES_COMPRA)

    # cuentas por fila (sin perfil): banco, billetera y empleador
    r_c = rng["cuentas"]
    bancos = par["cuentas.bancos"]
    nombres = np.array(sorted(bancos), dtype=object)
    banco = nombres[r_c.choice(len(nombres), size=n, p=_pesos([bancos[k] for k in nombres]))]
    billetera = np.where(r_c.random(n) < par["cuentas.p_nequi_entre_billeteras"], "NEQUI", "DAVIPLATA").astype(object)
    empleador = com.empleador(r_c, n)

    # comercio (solo compras a comercio; las P2P con propósito no llevan comercio)
    comercio = np.full(n, "", dtype=object)
    con_comercio = compra & ~p2p
    lat = latentes(df[con_comercio], rng["latentes"], eventos, recurrentes, lugares, par)
    nom = com.asignar(rng["comercios"], lat.reset_index(drop=True))
    comercio[con_comercio] = nom["comercio"].to_numpy()
    n2 = _n2(df)
    cr = con_comercio & (n2 == "credito_formal")
    comercio[cr] = np.char.add("CUOTA CREDITO ", banco[cr].astype(str)).astype(object)

    n2_obj = np.where(df["origen"].to_numpy(dtype=object) == "p2p_sin_proposito", n2, "").astype(object)
    desc, _ = pl.descripciones(rng["descriptores"], tev, comercio, banco, billetera, empleador, n2_objetivo=n2_obj)

    out = df.copy()
    out["descripcion"] = desc
    out["tipo_evento"] = tev
    out["fuente_etiqueta"] = np.where(p2p, "declaracion_voluntario", "texto")
    out["incoherencia_estructural"] = incoherencias(df)
    ve = pd.Series(out["incoherencia_estructural"]).value_counts()
    diag = {
        "filas": n,
        "incoherencias_estructurales": {k: int(v) for k, v in ve.items() if k},
        "frac_incoherente": float((out["incoherencia_estructural"] != "").mean()),
        "comercio_sin_soporte_en_pool": int(((lat["clase_comercio"] == "") & (df.loc[con_comercio, "origen"] == "compra").to_numpy()).sum()),
        "comercio_generico_fallback_almacen": int(pd.Series(comercio[con_comercio]).str.startswith("ALMACEN ").sum()),
        "descripciones_unicas": int(out["descripcion"].nunique()),
        "descripciones_unicas_por_categoria_n1": {k: int(v) for k, v in out.groupby("categoria_n1")["descripcion"].nunique().items()},
        "fuente_etiqueta": {k: int(v) for k, v in out["fuente_etiqueta"].value_counts().items()},
        "semilla": seed,
    }
    return out, diag


# ---------------------------------------------------------------------------------------------- validación
def validar_contra_reglas(emitidas: pd.DataFrame, dir_param: Path = DIR_PARAM) -> dict:
    """Comprueba que ``tipo_evento`` reproduce la tabla de decisión del generador: la descripción ORIGINAL de cada fila
    emitida por reglas debe poder salir de alguna plantilla del tipo derivado (comercio/banco/billetera/empleador comodín)."""
    import re
    pl = Plantillas(dir_param)
    pats = {}
    for t, g in pl._por_tipo.items():
        alts = []
        for p in g["plantilla"]:
            r = re.escape(" ".join(p.split()))
            for mk in (r"\{C\}", r"\{B\}", r"\{Wt\}", r"\{W\}", r"\{E\}"):
                r = r.replace(mk, ".+")
            alts.append(r)
        pats[t] = re.compile("^(?:" + "|".join(alts) + ")$")
    tev = tipo_evento(emitidas)
    ok = np.array([bool(pats[t].match(d)) for t, d in zip(tev, emitidas["descripcion"].astype(str))])
    return {"filas": int(len(ok)), "coinciden": int(ok.sum()), "frac": float(ok.mean()),
            "ejemplos_no_coinciden": emitidas.loc[~ok, ["origen", "medio_pago", "cuenta_tipo", "signo", "canal_p2p", "descripcion"]]
            .head(10).astype(str).to_dict("records")}
