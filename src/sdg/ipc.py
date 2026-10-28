"""Actualización de pesos de 2016-17 a pesos de 2025 con el IPC (WP6, PD5).

Qué hace: para cada registro de gasto de ENPH multiplica el valor por ``índice_base(división) / índice(mes de recolección,
división)``. «Deflactar a 2025» es en rigor ACTUALIZAR a pesos de 2025 (llevar hacia adelante): el factor es > 1.

Decisiones de la autora (27 oct 2026): IPC de Bogotá por división COICOP (conserva los pesos relativos entre categorías), base =
promedio de 2025; si el mapeo por división se complica, factor único con el índice total (``modo="total"``).

Entrada: ``data/raw/IPC/ipc_bogota_division.csv`` (formato largo, UTF-8, coma): ``mes`` (``AAAA-MM``), ``division`` (``00`` = total,
``01``…``12`` = divisiones COICOP), ``indice`` (número). Lo produce la conversión del archivo oficial de DANE (serie de empalme
del IPC), que NO se descarga desde este código. Sin el archivo, ``cargar_serie`` devuelve ``None`` y el generador marca la salida
como «sin IPC» (factor 1,0, pesos de 2016-17): nunca se inventa un factor.

Limitaciones declaradas: el IPC mide precios, no corrige crecimiento real del ingreso ni cambios de patrón de consumo desde 2017;
la división ENPH de un artículo es el prefijo de 2 dígitos de su código COICOP.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sdg import carga

RUTA_IPC = carga.RAIZ / "data" / "raw" / "IPC" / "ipc_bogota_division.csv"
ANIO_BASE = 2025
TOTAL = "00"
DIVISIONES = [f"{i:02d}" for i in range(1, 13)]


class IPCError(ValueError):
    """La serie de IPC no cumple el formato o no cubre los meses que se necesitan."""


def cargar_serie(ruta: Path | str | None = None) -> pd.DataFrame | None:
    """Lee la serie en formato largo y la valida. ``None`` si el archivo no existe (NO es un error: el llamador lo declara)."""
    ruta = Path(ruta) if ruta else RUTA_IPC
    if not ruta.is_file():
        return None
    s = pd.read_csv(ruta, dtype={"mes": str, "division": str})
    faltan = {"mes", "division", "indice"} - set(s.columns)
    if faltan:
        raise IPCError(f"{ruta.name}: faltan columnas {sorted(faltan)}")
    s["division"] = s["division"].str.strip().str.zfill(2)
    s["mes"] = s["mes"].str.strip()
    s["indice"] = pd.to_numeric(s["indice"], errors="coerce")
    if s["indice"].isna().any() or (s["indice"] <= 0).any():
        raise IPCError(f"{ruta.name}: índices vacíos o no positivos")
    if not s["mes"].str.fullmatch(r"\d{4}-\d{2}").all():
        raise IPCError(f"{ruta.name}: la columna mes debe ser AAAA-MM")
    if not s["division"].isin([TOTAL, *DIVISIONES]).all():
        raise IPCError(f"{ruta.name}: división fuera de 00-12")
    if s.duplicated(["mes", "division"]).any():
        raise IPCError(f"{ruta.name}: pares (mes, división) repetidos")
    return s.sort_values(["division", "mes"]).reset_index(drop=True)


def indice_base(serie: pd.DataFrame, anio: int = ANIO_BASE) -> pd.Series:
    """Promedio simple de los 12 índices mensuales del año, por división. Exige los 12 meses."""
    s = serie[serie["mes"].str.startswith(f"{anio}-")]
    n = s.groupby("division").size()
    if (n != 12).any():
        raise IPCError(f"el año base {anio} no tiene los 12 meses en las divisiones {sorted(n[n != 12].index)}")
    return s.groupby("division")["indice"].mean()


def factores(serie: pd.DataFrame | None, periodo: pd.Series, division: pd.Series, modo: str = "division") -> tuple[pd.Series, dict]:
    """Factor de actualización por fila. ``periodo``: ``AAAAMM`` de recolección ENPH. ``division``: 2 dígitos COICOP (otro → total).

    ``modo="division"`` usa la división de cada artículo (si la serie no la trae, cae al total y lo cuenta); ``modo="total"`` usa
    siempre el índice total. Sin serie (``None``) → factor 1,0 y ``diag['aplicado'] = False``.
    """
    if modo not in ("division", "total"):
        raise ValueError(f"modo IPC inválido: {modo!r}")
    if serie is None:
        return pd.Series(1.0, index=periodo.index), {"aplicado": False, "motivo": "no hay serie de IPC en data/raw/IPC/", "modo": modo,
                                                     "pesos": "2016-17 (sin actualizar)"}
    base = indice_base(serie)
    ancho = serie.pivot(index="mes", columns="division", values="indice")
    mes = periodo.str[:4] + "-" + periodo.str[4:6]
    div = pd.Series(TOTAL, index=periodo.index) if modo == "total" else division.where(division.isin(ancho.columns), TOTAL)
    faltan = sorted(set(mes) - set(ancho.index))
    if faltan:
        raise IPCError(f"la serie no cubre los meses de recolección {faltan}")
    idx = pd.Series(ancho.to_numpy()[ancho.index.get_indexer(mes), ancho.columns.get_indexer(div)], index=periodo.index)
    if idx.isna().any():
        raise IPCError("hay (mes, división) sin índice en la serie")
    f = base.reindex(div.to_numpy()).to_numpy() / idx.to_numpy()
    n_caida = int((~division.isin(ancho.columns)).sum()) if modo == "division" else 0
    diag = {"aplicado": True, "modo": modo, "anio_base": ANIO_BASE, "base": "promedio simple de los 12 meses de 2025",
            "filas": int(len(f)), "filas_con_caida_al_total": n_caida, "factor_min": float(np.min(f)), "factor_max": float(np.max(f)),
            "indice_base": {k: float(v) for k, v in base.items()}}
    return pd.Series(f, index=periodo.index), diag
