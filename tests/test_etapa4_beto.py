import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.utils.class_weight import compute_class_weight

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from etapa4_beto import pesos_balanced, submuestra  # noqa: E402


def _tabla(n=2000):
    rng = np.random.default_rng(0)
    y = rng.choice(["a", "b", "c"], size=n, p=[0.7, 0.2, 0.1])
    return pd.DataFrame({"descripcion": [f"d{i}" for i in range(n)], "categoria_n1": y})


def test_pesos_iguales_a_class_weight_balanced():
    y = np.array([0, 0, 0, 1, 2, 2])
    esperado = compute_class_weight("balanced", classes=np.array([0, 1, 2]), y=y)
    assert np.allclose(pesos_balanced(y, 4)[:3], esperado) and pesos_balanced(y, 4)[3] == 0


def test_submuestra_determinista_y_estratificada():
    t = _tabla()
    a, b = submuestra(t, 500, 42), submuestra(t, 500, 42)
    assert a.equals(b) and len(a) == 500
    frac = a["categoria_n1"].value_counts(normalize=True)
    assert abs(frac["a"] - 0.7) < 0.03 and abs(frac["c"] - 0.1) < 0.03


def test_submuestra_mayor_que_train_usa_todo():
    t = _tabla(100)
    assert len(submuestra(t, 10_000, 42)) == 100
