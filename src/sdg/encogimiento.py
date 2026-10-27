"""Encogimiento jerárquico Dirichlet-multinomial, tamaño efectivo de Kish e IPF (WP3, PD1 y PD2).

Solo ``numpy`` y ``math``: no lee datos y no usa aleatoriedad (todo es determinista). Lo usa ``sdg.priors``.

Modelo (forma cerrada). Para una celda con proporciones observadas ponderadas ``p̂`` y tamaño efectivo ``n`` (Kish), y una
distribución «padre» ``π_pa``:

    π_post = (n · p̂ + κ · π_pa) / (n + κ)

es la media posterior de un Dirichlet(κ · π_pa) tras observar los conteos efectivos ``n · p̂``. ``κ`` es el peso del padre
en «observaciones». Se estima por máxima verosimilitud marginal (Dirichlet-multinomial) sobre ``KAPPA_GRILLA``; si el
óptimo cae en un extremo de la rejilla se informa como tal (``en_frontera``), no se oculta.

Umbral de soporte (PD1): una celda es «rala» si ``n_ef < κ̂``, es decir, si el padre pesa más que la propia celda en la
posterior. No es un número fijo: sale de cuánto se parecen las celdas entre sí.

Límites declarados: ``n_ef`` de Kish corrige por pesos desiguales pero NO por conglomeración (UPM, L1), así que es
optimista; ``deff`` permite la sensibilidad. El Dirichlet-multinomial con conteos efectivos no enteros se evalúa con
``lgamma`` (es una cuasi-verosimilitud, no un modelo generativo exacto de la encuesta).
"""
from __future__ import annotations

import math
from typing import Callable, NamedTuple, Sequence

import numpy as np

KAPPA_GRILLA: tuple[float, ...] = tuple(float(k) for k in np.logspace(0, 4, 41))  # 1 … 10 000, 10 puntos por década
PISO_PADRE = 1e-9  # solo para evaluar lgamma cuando el padre tiene ceros; nunca se usa para fabricar masa en un prior


class Stat(NamedTuple):
    """Resumen ponderado de una celda: proporciones (suman 1; ceros si ``n == 0``), n efectivo de Kish, n sin ponderar
    y masa expandida (suma de pesos de las filas válidas)."""
    p: np.ndarray
    neff: float
    n: int
    w: float = 0.0


def stat_vacio(k: int) -> Stat:
    return Stat(np.zeros(k), 0.0, 0)


def n_efectivo(w) -> float:
    """Tamaño efectivo de Kish: (Σw)² / Σw². Con pesos iguales vale n."""
    w = np.asarray(w, dtype=float)
    if w.size == 0:
        return 0.0
    s2 = float((w ** 2).sum())
    return float(w.sum()) ** 2 / s2 if s2 > 0 else 0.0


def encoger(p_hat, neff: float, padre, kappa: float) -> np.ndarray:
    """Media posterior (n·p̂ + κ·π_pa)/(n + κ). ``neff <= 0`` → el padre. κ=0 → p̂; κ→∞ → el padre."""
    padre = np.asarray(padre, dtype=float)
    if neff <= 0:
        return padre.copy()
    p_hat = np.asarray(p_hat, dtype=float)
    return (neff * p_hat + kappa * padre) / (neff + kappa)


def log_evidencia_dm(conteos, alfa) -> float:
    """log de la evidencia Dirichlet-multinomial SIN el coeficiente multinomial (constante respecto de κ)."""
    conteos = np.asarray(conteos, dtype=float)
    alfa = np.maximum(np.asarray(alfa, dtype=float), PISO_PADRE)
    a0, n = float(alfa.sum()), float(conteos.sum())
    return math.lgamma(a0) - math.lgamma(a0 + n) + sum(math.lgamma(a + c) - math.lgamma(a) for a, c in zip(alfa, conteos))


Nivel = dict  # {clave: Stat}


class Problema(NamedTuple):
    """Una jerarquía a encoger. ``calib``: ``Stat`` del marginal del nivel más fino (p. ej. Bogotá) para recalibrar el padre.

    Sin ``calib``, el padre fija el NIVEL de la variable: encoger hacia un padre con otro nivel (p. ej. el total nacional, con
    más efectivo y menos tarjeta que Bogotá) desplaza el marginal del nivel fino aunque sus celdas tengan datos. Con ``calib``,
    el padre solo aporta la FORMA entre celdas: se reescala por categoría hasta que su promedio, ponderado por la masa de las
    celdas finas, sea el marginal fino (encogido hacia la raíz con el mismo κ para no fabricar ceros).
    """
    raiz: np.ndarray
    niveles: list
    padre_de: list
    calib: Stat | None = None


def calibrar_nivel(pi_celdas, w, objetivo, tol: float = 1e-12, max_iter: int = 10_000) -> np.ndarray:
    """Reescala por columnas las distribuciones de las celdas (filas de ``pi_celdas``) y renormaliza cada fila hasta que su
    promedio ponderado por ``w`` sea ``objetivo``. Conserva la forma relativa entre celdas; las celdas con ``w = 0`` reciben los
    mismos factores. Una categoría con objetivo > 0 pero sin masa en ninguna celda recibe el objetivo (caso raro: sensibilidad)."""
    pi = np.array(pi_celdas, dtype=float)
    w, objetivo = np.asarray(w, dtype=float), np.asarray(objetivo, dtype=float)
    if w.sum() <= 0:
        return pi
    sin_masa = (pi.sum(axis=0) == 0) & (objetivo > 0)
    pi[:, sin_masa] = objetivo[sin_masa]
    pi /= pi.sum(axis=1, keepdims=True)
    b = np.ones(pi.shape[1])
    for _ in range(max_iter):
        adj = pi * b[None, :]
        adj /= adj.sum(axis=1, keepdims=True)
        prom = (w[:, None] * adj).sum(axis=0) / w.sum()
        if np.abs(prom - objetivo).max() < tol:
            return adj
        b *= np.divide(objetivo, prom, out=np.ones_like(b), where=prom > 0)
    raise RuntimeError(f"calibrar_nivel: sin convergencia en {max_iter} iteraciones")


def _calibrar_previo(previo: dict, ultimo: Nivel, padre_ult: Callable, raiz, calib: Stat, kappa: float, deff: float) -> dict:
    """Recalibra los posteriores del nivel previo al marginal fino (``calib``), ponderando por la masa de los hijos."""
    claves = list(previo)
    w = np.zeros(len(claves))
    idx = {k: i for i, k in enumerate(claves)}
    for hijo, s in ultimo.items():
        w[idx[padre_ult(hijo)]] += s.w
    if w.sum() <= 0 or calib.neff <= 0:
        return previo
    objetivo = encoger(calib.p, calib.neff / deff, raiz, kappa)
    adj = calibrar_nivel(np.vstack([previo[k] for k in claves]), w, objetivo)
    return {k: adj[i] for i, k in enumerate(claves)}


def cadena(raiz, niveles: Sequence[Nivel], padre_de: Sequence[Callable], kappa: float, deff: float = 1.0, calib: Stat | None = None) -> list[dict]:
    """Posteriores jerárquicos de cada nivel (del más agregado al más fino).

    ``raiz``: distribución fija de partida. ``niveles[i]``: ``{clave: Stat}`` con TODAS las claves esperadas (``stat_vacio``
    si no hay datos). ``padre_de[i-1]``: clave del nivel ``i`` → clave del nivel ``i-1``. ``deff`` divide el n efectivo.
    ``calib``: ver ``Problema``; se aplica sobre el penúltimo nivel antes de encoger el último.
    """
    post: list[dict] = []
    for i, nivel in enumerate(niveles):
        if calib is not None and i > 0 and i == len(niveles) - 1:
            post[i - 1] = _calibrar_previo(post[i - 1], nivel, padre_de[i - 1], raiz, calib, kappa, deff)
        d = {}
        for clave, s in nivel.items():
            padre = np.asarray(raiz, dtype=float) if i == 0 else post[i - 1][padre_de[i - 1](clave)]
            d[clave] = encoger(s.p, s.neff / deff, padre, kappa)
        post.append(d)
    return post


def loglik_kappa(problemas: Sequence[Problema], kappa: float, deff: float = 1.0) -> float:
    """Log-evidencia marginal total de ``κ``: suma sobre los problemas y las celdas del nivel más fino."""
    total = 0.0
    for pr in problemas:
        raiz, niveles, padre_de, calib = pr
        previos = cadena(raiz, niveles[:-1], padre_de[:-1], kappa, deff) if len(niveles) > 1 else []
        if previos and calib is not None:
            previos[-1] = _calibrar_previo(previos[-1], niveles[-1], padre_de[-1], raiz, calib, kappa, deff)
        for clave, s in niveles[-1].items():
            if s.neff <= 0:
                continue
            padre = np.asarray(raiz, dtype=float) if not previos else previos[-1][padre_de[-1](clave)]
            total += log_evidencia_dm(s.neff / deff * s.p, kappa * padre)
    return total


def elegir_kappa(problemas: Sequence[Problema], deff: float = 1.0, grilla: Sequence[float] = KAPPA_GRILLA) -> dict:
    """κ̂ por máxima verosimilitud marginal sobre la rejilla. Empates → el menor κ (determinista).

    Devuelve ``{kappa, en_frontera, perfil: [(κ, loglik), …]}``.
    """
    perfil = [(float(k), loglik_kappa(problemas, float(k), deff)) for k in grilla]
    i = int(np.argmax([ll for _, ll in perfil]))
    return {"kappa": perfil[i][0], "en_frontera": i in (0, len(perfil) - 1), "perfil": perfil}


def ipf(semilla, filas, columnas, tol: float = 1e-12, max_iter: int = 10_000) -> np.ndarray:
    """Reajuste proporcional iterativo (raking): fuerza márgenes de fila ``filas`` y de columna ``columnas`` conservando
    las razones de momios (odds ratios) de ``semilla``. Filas/columnas con margen 0 quedan en 0. Exige Σfilas = Σcolumnas."""
    t = np.array(semilla, dtype=float)
    filas, columnas = np.asarray(filas, dtype=float), np.asarray(columnas, dtype=float)
    if not math.isclose(filas.sum(), columnas.sum(), rel_tol=1e-9):
        raise ValueError(f"ipf: márgenes incompatibles (Σfilas={filas.sum()} ≠ Σcolumnas={columnas.sum()})")
    if ((t.sum(axis=1) == 0) & (filas > 0)).any() or ((t.sum(axis=0) == 0) & (columnas > 0)).any():
        raise ValueError("ipf: una fila o columna con margen positivo no tiene masa en la semilla (no hay solución)")
    for _ in range(max_iter):
        sf = t.sum(axis=1)
        t *= np.divide(filas, sf, out=np.zeros_like(filas), where=sf > 0)[:, None]
        sc = t.sum(axis=0)
        t *= np.divide(columnas, sc, out=np.zeros_like(columnas), where=sc > 0)[None, :]
        if np.abs(t.sum(axis=1) - filas).max() < tol:
            return t
    raise RuntimeError(f"ipf: sin convergencia en {max_iter} iteraciones")


def chi2_sf(x: float, k: int) -> float:
    """P(χ²_k > x) = Q(k/2, x/2): serie si x/2 < k/2+1, fracción continua (Lentz) si no. Sin scipy (no está en requirements)."""
    a, z = k / 2.0, x / 2.0
    if z <= 0:
        return 1.0
    log_pref = -z + a * math.log(z) - math.lgamma(a)
    if z < a + 1:
        term = s = 1.0 / a
        n = a
        for _ in range(10_000):
            n += 1
            term *= z / n
            s += term
            if abs(term) < abs(s) * 1e-15:
                break
        return max(0.0, 1.0 - s * math.exp(log_pref))
    tiny = 1e-300
    b = z + 1 - a
    c, d = 1 / tiny, 1 / b
    h = d
    for i in range(1, 10_000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return min(1.0, math.exp(log_pref) * h)
