"""Estado de cada (hogar, subcapítulo) frente a la pregunta de medio de pago P438* (Cuadernillo 3).

El cuadernillo pregunta el medio de pago «luego de preguntar por todos los artículos del subcapítulo». Cruzando con los
registros de artículos (hogares/gastos_menos_frecuentes_articulos.txt, columna CAP = subcapítulo) se distingue:
  responde        : hay base de compra y hay medio válido
  no_respuesta    : hay base de compra y NO hay medio válido
  no_aplica       : no hay base de compra y no hay medio
  medio_sin_base  : no hay base de compra pero sí hay medio (inconsistencia entre las dos tablas)
«Base de compra» puede ser «cualquier registro en el subcapítulo» o «registro con FORMA = 1» (ver sdg.codigos.FORMA_ADQUISICION).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ESTADOS = ("responde", "no_respuesta", "no_aplica", "medio_sin_base")


def estado_p438(tiene_base: pd.Series, medio_valido: pd.Series) -> pd.Series:
    tb, mv = tiene_base.astype(bool), medio_valido.astype(bool)
    return pd.Series(np.select([tb & mv, tb & ~mv, ~tb & ~mv, ~tb & mv], list(ESTADOS), default=""), index=tb.index)
