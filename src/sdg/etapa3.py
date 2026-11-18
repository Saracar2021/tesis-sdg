"""Etapa 3 (CTGAN): utilidades puras (pandas/numpy) para el notebook ``notebooks/03_ctgan_etapa3.ipynb``.

No importa torch/sdv a propósito: así las reglas duras, la elasticidad y el piso se pueden probar
(``tests/test_etapa3.py``) en cualquiera de los dos entornos (pandas 2.x del entorno CTGAN o pandas 3.x del repo).

Fuente de las decisiones: ``docs/reporte/adenda_preregistro_ctgan.md`` (17-nov-2026). Las DESVIACIONES respecto
al texto de la adenda están marcadas con ``DESVIACIÓN`` y listadas en la cabecera del notebook.
"""
from __future__ import annotations

import calendar
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

DISCRETAS = ["cuenta_tipo", "signo", "categoria_n1", "categoria_n2", "medio_pago", "origen", "formalidad_comercio", "canal_p2p"]  # signo: añadido 17-nov (observable del clasificador)
CONTINUAS = ["monto", "ingreso_mensual"]
DERIVADAS = ["dia_mes", "mes"]
COLUMNAS_MODELO = DISCRETAS + CONTINUAS + DERIVADAS
SIN_N2 = "(sin_n2)"  # categoria_n2 vacía en la fuente (112 filas): se modela como nivel explícito

# medio_pago admitido por cuenta_tipo. Viene de ``generador.CUENTA_DE_MEDIO`` más las dos excepciones que el
# generador emite por construcción: transferencia desde/hacia billetera y el abono (transferencia) a la tarjeta.
MEDIOS_POR_CUENTA = {
    "banco": {"tarjeta_debito", "transferencia_bancaria"},
    "billetera": {"billetera_digital", "transferencia_bancaria"},
    "tarjeta_credito": {"tarjeta_credito", "transferencia_bancaria"},
}
# DESVIACIÓN (regla canal_p2p): la adenda §4 dice «canal_p2p informado en filas cuyo origen no es P2P». La
# taxonomía (regla R2) define lo contrario: canal_p2p=True marca un pago a persona CON propósito declarado, que
# se clasifica en la categoría del propósito; las filas de origen ``p2p_sin_proposito`` llevan siempre False.
# Con el texto literal, el 7,06 % de la propia fuente quedaría rechazado. Regla coherente con R2 y el generador:
ORIGENES_CANAL_P2P = {"compra", "pago_recurrente", "ingreso_no_asalariado"}
MEDIOS_CANAL_P2P = {"transferencia_bancaria", "billetera_digital"}

# Sexta regla dura (añadida el 17-nov-2026, antes de la corrida): signo incompatible con el origen. En dos orígenes
# el signo depende de la cuenta que registra el movimiento (las dos patas del mismo traslado) y en el P2P sin
# propósito lo fija el subtipo; ``transferencias_p2p.indeterminada`` admite ambos. Donde no hay signo definido
# (p. ej. pago_tarjeta registrado en billetera) esta regla no dispara: eso no es un error de signo.
SIGNO_POR_ORIGEN = {"compra": "-", "pago_recurrente": "-", "retiro": "-", "nomina": "+", "ingreso_no_asalariado": "+"}
SIGNO_POR_ORIGEN_Y_CUENTA = {("pago_tarjeta", "banco"): "-", ("pago_tarjeta", "tarjeta_credito"): "+",
                             ("recarga_billetera", "banco"): "-", ("recarga_billetera", "billetera"): "+"}
SIGNO_P2P_POR_N2 = {"enviada_persona": "-", "recibida_persona": "+"}

REGLAS = ["monto_no_positivo", "medio_imposible_para_cuenta", "par_n1_n2_inexistente", "canal_p2p_incoherente", "fecha_imposible",
          "signo_incompatible_con_origen"]


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV canónico (LF, sin índice) para hashear contenido, no el contenedor gzip."""
    return df.to_csv(index=False, lineterminator="\n").encode("utf-8")


def construir_tabla(tx: pd.DataFrame, perfiles: pd.DataFrame) -> pd.DataFrame:
    """Capa emitida LEFT JOIN perfiles (``ingreso_mensual``) + ``dia_mes``/``mes``. Conserva ``perfil_id`` (no entra al modelo)."""
    em = tx.loc[tx["capa"] == "emitida"].copy()
    if not perfiles["perfil_id"].is_unique:
        raise ValueError("perfil_id duplicado en perfiles: el join multiplicaría filas")
    d = em.merge(perfiles[["perfil_id", "ingreso_mensual"]], on="perfil_id", how="left", validate="many_to_one")
    if len(d) != len(em):
        raise ValueError("el join cambió el número de filas")
    if d["ingreso_mensual"].isna().any() or (d["ingreso_mensual"] <= 0).any():
        raise ValueError("ingreso_mensual faltante o no positivo tras el join")
    f = pd.to_datetime(d["fecha"], format="%Y-%m-%d")
    d["dia_mes"] = f.dt.day.astype("int64")
    d["mes"] = f.dt.month.astype("int64")
    d["anio"] = f.dt.year.astype("int64")
    d["categoria_n2"] = d["categoria_n2"].astype(object).where(d["categoria_n2"].notna(), SIN_N2)
    for c in ["cuenta_tipo", "signo", "categoria_n1", "medio_pago", "origen", "formalidad_comercio"]:
        d[c] = d[c].astype(object)
    d["canal_p2p"] = d["canal_p2p"].astype(bool)
    d["monto"] = d["monto"].astype("int64")
    d["ingreso_mensual"] = d["ingreso_mensual"].astype("float64")
    return d[["perfil_id", "anio"] + COLUMNAS_MODELO].reset_index(drop=True)


def anio_por_mes(tabla: pd.DataFrame) -> dict[int, int]:
    """Cada mes de la ventana pertenece a un único año en la fuente (12→2025, 4 y 8→2026)."""
    g = tabla.groupby("mes")["anio"].nunique()
    if (g != 1).any():
        raise ValueError("un mes aparece en más de un año: la fecha no se puede reconstruir desde (mes, dia_mes)")
    return {int(m): int(a) for m, a in tabla.groupby("mes")["anio"].first().items()}


def partir_por_perfil(tabla: pd.DataFrame, frac_holdout: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Holdout por PERFIL (no por fila): las transacciones de un perfil comparten ingreso y hábitos, así que un
    corte por fila deja los mismos perfiles a ambos lados e infla el techo train-vs-holdout."""
    ids = np.sort(tabla["perfil_id"].unique())
    rng = np.random.default_rng(seed)
    n_h = int(round(len(ids) * frac_holdout))
    en_h = set(rng.permutation(ids)[:n_h].tolist())
    m = tabla["perfil_id"].isin(en_h).to_numpy()
    return tabla.loc[~m].reset_index(drop=True), tabla.loc[m].reset_index(drop=True)


def pares_taxonomia(ruta_json: Path) -> set[tuple[str, str]]:
    tx = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    pares = set()
    for c in tx["categorias_nivel_1"]:
        for s in c["subtipos"]:
            pares.add((c["id"], s["id"] if isinstance(s, dict) else s))
    return pares


def pares_validos(ruta_json: Path, fuente: pd.DataFrame) -> set[tuple[str, str]]:
    """Pares de la taxonomía + (n1, sin subtipo) solo donde la fuente lo emite."""
    sin = fuente.loc[fuente["categoria_n2"] == SIN_N2, "categoria_n1"].unique().tolist()
    return pares_taxonomia(ruta_json) | {(n1, SIN_N2) for n1 in sin}


def violaciones(df: pd.DataFrame, pares: set[tuple[str, str]], anio_mes: dict[int, int]) -> pd.DataFrame:
    """Una columna booleana por regla dura (True = viola). Adenda §4, con la regla de canal_p2p corregida."""
    v = pd.DataFrame(index=df.index)
    v["monto_no_positivo"] = (df["monto"] <= 0).to_numpy()
    ok_medio = np.zeros(len(df), dtype=bool)
    for cta, medios in MEDIOS_POR_CUENTA.items():
        ok_medio |= ((df["cuenta_tipo"] == cta) & df["medio_pago"].isin(list(medios))).to_numpy()
    v["medio_imposible_para_cuenta"] = ~ok_medio
    par = pd.MultiIndex.from_arrays([df["categoria_n1"].astype(object), df["categoria_n2"].astype(object)])
    v["par_n1_n2_inexistente"] = ~par.isin(list(pares))
    p2p = df["canal_p2p"].astype(bool).to_numpy()
    coherente = (df["origen"].isin(list(ORIGENES_CANAL_P2P)) & df["medio_pago"].isin(list(MEDIOS_CANAL_P2P))
                 & (df["categoria_n1"] != "transferencias_p2p")).to_numpy()
    v["canal_p2p_incoherente"] = p2p & ~coherente
    mes = df["mes"].astype("int64").to_numpy()
    dia = df["dia_mes"].astype("int64").to_numpy()
    tope = np.array([calendar.monthrange(anio_mes[m], m)[1] if m in anio_mes else 0 for m in mes])
    v["fecha_imposible"] = (dia < 1) | (dia > tope)
    esperado = df["origen"].map(SIGNO_POR_ORIGEN).astype(object)
    par_oc = pd.Series(list(zip(df["origen"], df["cuenta_tipo"])), index=df.index).map(SIGNO_POR_ORIGEN_Y_CUENTA)
    esperado = esperado.where(esperado.notna(), par_oc)
    es_p2p = (df["origen"] == "p2p_sin_proposito")
    esperado = esperado.where(~es_p2p, df["categoria_n2"].map(SIGNO_P2P_POR_N2))
    v["signo_incompatible_con_origen"] = (esperado.notna() & (esperado != df["signo"].astype(object))).to_numpy()
    return v[REGLAS]


def cuotas(marginal: pd.Series, n: int) -> pd.Series:
    """Reparto entero de ``n`` según ``marginal`` (mayor resto; desempate por nombre → determinista)."""
    p = (marginal / marginal.sum()).sort_index()
    base = np.floor(p * n).astype("int64")
    resto = (p * n - base)
    orden = sorted(p.index, key=lambda k: (-resto[k], k))
    for k in orden[: int(n - base.sum())]:
        base[k] += 1
    return base


def piso_marginales(train: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Piso: cada columna muestreada por separado (con reemplazo) del train. Conserva las marginales y destruye
    toda dependencia entre columnas."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({c: train[c].to_numpy()[rng.integers(0, len(train), size=n)] for c in COLUMNAS_MODELO})


def _pendiente(sx, sy, sxx, sxy, n):
    return (n * sxy - sx * sy) / (n * sxx - sx * sx)


def elasticidad(df: pd.DataFrame) -> float:
    """Pendiente OLS de log(monto) sobre log(ingreso_mensual), a nivel transacción (adenda §3)."""
    x = np.log(df["ingreso_mensual"].to_numpy(dtype="float64"))
    y = np.log(df["monto"].to_numpy(dtype="float64"))
    return float(_pendiente(x.sum(), y.sum(), (x * x).sum(), (x * y).sum(), len(x)))


def ic_elasticidad(df: pd.DataFrame, seed: int, b: int = 1000, conglomerado: str | None = None) -> tuple[float, float]:
    """IC 95 % percentil por bootstrap. Con ``conglomerado`` se remuestrean perfiles enteros (la fuente tiene
    1.000 ingresos distintos, no 122.211: remuestrear filas daría un IC falsamente estrecho)."""
    x = np.log(df["ingreso_mensual"].to_numpy(dtype="float64"))
    y = np.log(df["monto"].to_numpy(dtype="float64"))
    s = pd.DataFrame({"n": 1.0, "sx": x, "sy": y, "sxx": x * x, "sxy": x * y})
    if conglomerado is not None:
        s = s.groupby(df[conglomerado].to_numpy(), sort=True).sum()
    else:  # 2.000 bloques de filas contiguas barajadas ≈ bootstrap de filas, sin materializar b×n índices
        rng0 = np.random.default_rng(seed + 1)
        s = s.groupby(rng0.permutation(len(s)) % 2000).sum()
    a = s.to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(b, len(a)))
    t = a[idx].sum(axis=1)
    betas = _pendiente(t[:, 1], t[:, 2], t[:, 3], t[:, 4], t[:, 0])
    return float(np.quantile(betas, 0.025)), float(np.quantile(betas, 0.975))


UMBRAL_CONSERVA, UMBRAL_ATENUA = 0.70, 0.30


def veredicto_elasticidad(punto: float, ic: tuple[float, float], punto_train: float) -> tuple[str, float]:
    """Criterio fijado por la autora el 17-nov-2026, antes de la corrida. r = ê_ctgan / ê_train.
    NO CONSERVA: ê_ctgan ≤ 0, o el IC incluye 0, o r < 0,30. ATENÚA: 0,30 ≤ r < 0,70. CONSERVA: r ≥ 0,70 (incluye r > 1)."""
    r = punto / punto_train
    if punto <= 0 or ic[0] <= 0 or r < UMBRAL_ATENUA:
        return "NO CONSERVA", r
    return ("CONSERVA" if r >= UMBRAL_CONSERVA else "ATENÚA"), r
