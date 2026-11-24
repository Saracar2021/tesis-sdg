import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from etapa4_tstr import aplicar_regla_soporte, f1_macro_regla  # noqa: E402

CLASES = ["a", "b", "c", "otros"]


def test_clase_con_menos_de_10_se_fusiona_a_otros():
    y_true = np.array(["a"] * 20 + ["b"] * 9 + ["otros"] * 10)
    y_pred = np.array(["a"] * 20 + ["b"] * 9 + ["otros"] * 10)
    yt, yp, etiquetas, fusionadas = aplicar_regla_soporte(y_true, y_pred, CLASES)
    assert fusionadas == ["b", "c"]
    assert "b" not in set(yt) and "b" not in set(yp)
    assert etiquetas == ["a", "otros"]


def test_prediccion_de_clase_fusionada_cuenta_como_otros():
    # 'b' tiene soporte 5 -> se fusiona; predecir 'b' sobre un 'otros' real es acierto.
    y_true = np.array(["a"] * 10 + ["otros"] * 5 + ["b"] * 5)
    y_pred = np.array(["a"] * 10 + ["b"] * 5 + ["otros"] * 5)
    assert f1_macro_regla(y_true, y_pred, CLASES) == 1.0


def test_clase_residual_nunca_se_fusiona():
    y_true = np.array(["a"] * 10 + ["otros"] * 2)
    _, _, etiquetas, fusionadas = aplicar_regla_soporte(y_true, y_true, CLASES)
    assert "otros" not in fusionadas and "otros" in etiquetas
