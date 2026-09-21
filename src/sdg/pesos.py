"""Tablas ponderadas: cuantiles con FEX, distribuciones con «sin dato» explícito (sin imputar)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def cortes_ponderados(x: pd.Series, w: pd.Series, k: int = 5) -> list[float]:
    """Puntos de corte de los ``k`` grupos: c_j = menor valor x con F_w(x) ≥ j/k, j = 1..k-1 (F_w = cdf ponderada)."""
    d = pd.DataFrame({"x": pd.to_numeric(x), "w": pd.to_numeric(w)}).dropna().sort_values("x")
    if d.empty or (d["w"] <= 0).any():
        raise ValueError("cortes_ponderados: sin datos o pesos no positivos")
    cdf = d["w"].cumsum().to_numpy() / d["w"].sum()
    xs = d["x"].to_numpy()
    return [float(xs[np.searchsorted(cdf, j / k - 1e-12, side="left")]) for j in range(1, k)]


def grupo_por_cortes(x: pd.Series, cortes: list[float]) -> pd.Series:
    """1..k según ``cortes``: x ≤ c_1 → 1; c_{j-1} < x ≤ c_j → j; x > c_{k-1} → k. Los iguales al corte van al grupo inferior."""
    n = pd.to_numeric(x)
    g = pd.Series(np.searchsorted(np.asarray(cortes), n.to_numpy(dtype=float), side="left") + 1, index=x.index, dtype="float")
    return g.where(n.notna())


def distribucion(df: pd.DataFrame, col: str, *, peso: str = "FEX", etiquetas: dict[str, str] | None = None,
                 motivos_sin_dato: dict[str, str] | None = None, validos: list[str] | None = None) -> pd.DataFrame:
    """Distribución ponderada de ``col`` con filas explícitas «sin dato» (nunca se imputa).

    ``validos``: códigos que entran a la BASE CON RESPUESTA (por defecto, las claves de ``etiquetas``).
    Todo lo demás se reporta aparte: ``motivos_sin_dato`` (código → motivo), vacío → «sin dato (vacío)»,
    y cualquier otro código → «código fuera de lista». Columnas:
    n (sin ponderar), expandido (suma de pesos), pct_con_respuesta (solo filas válidas; NaN en sin dato), pct_total.
    """
    etiquetas = etiquetas or {}
    motivos = motivos_sin_dato or {}
    validos = list(etiquetas) if validos is None else validos
    s = df[col].astype("object").where(df[col].notna(), "").astype(str)
    w = df[peso].astype(float)
    tot_w, tot_n = float(w.sum()), len(df)
    filas = []
    resp_w = float(w[s.isin(validos)].sum())
    for cod in validos:
        m = s == cod
        filas.append(dict(codigo=cod, categoria=etiquetas.get(cod, cod), tipo="respuesta", n=int(m.sum()), expandido=float(w[m].sum())))
    otros = sorted(set(s[~s.isin(validos)]))
    for cod in otros:
        m = s == cod
        if cod == "":
            cat = "sin dato (vacío)"
        elif cod in motivos:
            cat = f"sin dato: {motivos[cod]}"
        else:
            cat = "código fuera de lista"
        filas.append(dict(codigo=cod, categoria=cat, tipo="sin_dato", n=int(m.sum()), expandido=float(w[m].sum())))
    t = pd.DataFrame(filas)
    t["pct_con_respuesta"] = np.where(t["tipo"] == "respuesta", 100 * t["expandido"] / resp_w if resp_w else np.nan, np.nan)
    t["pct_total"] = 100 * t["expandido"] / tot_w
    return t


def cruce(df: pd.DataFrame, fila: str, col: str, *, peso: str = "FEX") -> pd.DataFrame:
    """Cruce de dos categóricas con n sin ponderar y suma de pesos por celda (solo filas con ambas presentes)."""
    d = df[[fila, col, peso]].dropna(subset=[fila, col])
    g = d.groupby([fila, col], observed=True)
    return pd.DataFrame({"n": g.size(), "expandido": g[peso].sum()}).reset_index()


def fronteras(x: pd.Series, w: pd.Series, cortes: list[float], k: int = 5) -> pd.DataFrame:
    """Diagnóstico de amontonamiento en cada frontera de grupo (para declarar la limitación, sin cambiar los cortes).

    Por corte c_j: ``masa_en_el_valor_pct`` = % del peso exactamente en c_j; ``masa_bajo_el_valor_pct`` = % estrictamente por debajo;
    ``fraccion_del_monton_bajo_objetivo`` = (j/k·100 − masa_bajo) / masa_en_el_valor, es decir, en qué punto DEL MONTÓN cae el
    percentil objetivo (0 = justo al inicio, 1 = justo al final): cerca de los extremos la frontera es inestable ante cualquier
    perturbación de la muestra o de los pesos. ``sobrepaso_pp`` = cdf en c_j − objetivo.
    """
    d = pd.DataFrame({"x": pd.to_numeric(x), "w": pd.to_numeric(w)}).dropna()
    tot = float(d["w"].sum())
    filas = []
    for j, c in enumerate(cortes, 1):
        objetivo = 100 * j / k
        en = d["x"] == c
        bajo = 100 * float(d.loc[d["x"] < c, "w"].sum()) / tot
        masa = 100 * float(d.loc[en, "w"].sum()) / tot
        filas.append(dict(corte=f"c{j}", valor=float(c), objetivo_pct=objetivo, masa_bajo_el_valor_pct=bajo, masa_en_el_valor_pct=masa,
                          cdf_hasta_el_valor_pct=bajo + masa, sobrepaso_pp=bajo + masa - objetivo, n_en_el_valor=int(en.sum()),
                          fraccion_del_monton_bajo_objetivo=(objetivo - bajo) / masa if masa > 0 else np.nan))
    return pd.DataFrame(filas)
