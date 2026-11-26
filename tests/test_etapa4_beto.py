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


# --------------------------------------------------------------------------- modos entrenar / evaluar (sin torch)
import json  # noqa: E402

import pytest  # noqa: E402

import etapa4_beto as eb  # noqa: E402


def test_entrenamiento_rechaza_rutas_bajo_data():
    with pytest.raises(PermissionError):
        eb.rechazar_data(Path("data/reales_anon/test_real_wp4_20261127.csv"))
    eb.rechazar_data(Path("outputs/ctgan/sintetico_v1_con_texto.csv.gz"))      # sintético: permitido


def test_verificar_modelo_detecta_manipulacion(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "MODELOS", tmp_path / "modelos")
    d = tmp_path / "modelos" / "beto_reglas"
    d.mkdir(parents=True)
    (d / eb.PESOS_ARCHIVO).write_bytes(b"pesos")
    sint = tmp_path / "sintetico.csv"
    sint.write_text("x\n1\n")
    man = {"sha256_pesos": eb.base.sha256(d / eb.PESOS_ARCHIVO), "sintetico": {"ruta": str(sint), "sha256": eb.base.sha256(sint)},
           "revision_tokenizador": eb.REVISION_TOKENIZADOR, "revision_pesos": eb.REVISION_PESOS}
    (d / "manifiesto.json").write_text(json.dumps(man))
    assert eb.verificar_modelo("reglas") == []
    (d / eb.PESOS_ARCHIVO).write_bytes(b"otros pesos")
    assert any("pesos" in p for p in eb.verificar_modelo("reglas"))
    (d / eb.PESOS_ARCHIVO).write_bytes(b"pesos")
    sint.write_text("x\n2\n")
    assert any("cambió" in p for p in eb.verificar_modelo("reglas"))


def test_modelos_y_logs_ignorados_por_git():
    reglas = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8").split()
    assert {"outputs/tstr/_modelos/", "outputs/tstr/_ckpt/", "logs/", "data/"} <= set(reglas)
