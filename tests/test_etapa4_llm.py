import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import etapa4_llm as llm  # noqa: E402
import etapa4_tstr as base  # noqa: E402

CLASES, _ = base.cargar_taxonomia()


def test_parseo():
    assert llm.parsear("comidas_fuera", CLASES) == ("comidas_fuera", "exacta")
    assert llm.parsear("Categoría: ingreso.", CLASES) == ("ingreso", "contenida")
    assert llm.parsear("ingreso o transferencias_p2p", CLASES) == (llm.FUERA_DE_ENUM, "fuera_de_enum")
    assert llm.parsear("", CLASES) == (llm.FUERA_DE_ENUM, "vacia")
    assert llm.parsear(None, CLASES) == (llm.FUERA_DE_ENUM, "vacia")


def test_fuera_de_enum_cuenta_como_error_aunque_la_real_sea_otros():
    import numpy as np
    y_true = np.array(["otros"] * 10 + ["ingreso"] * 10)
    y_pred = np.array([llm.FUERA_DE_ENUM] * 10 + ["ingreso"] * 10, dtype=object)
    r = base.evaluar(y_true, y_pred, CLASES)
    assert r["accuracy"] == 0.5 and r["f1_macro_regla_soporte"] < 1.0


def test_llm_rechaza_test_real(monkeypatch):
    import pytest
    monkeypatch.setattr(sys, "argv", ["etapa4_llm.py", "--test", "tests/fixtures/real_simulado_wp4.csv"])
    with pytest.raises(SystemExit) as e:
        llm.main()
    assert "no se envían datos reales" in str(e.value)


def test_prompt_sistema_tiene_16_clases_y_r1():
    s = llm.prompt_sistema(CLASES)
    assert all(f"- {c}:" in s for c in CLASES) and "Regla R1" in s and "SOLO" in s


def test_few_shot_determinista_y_sin_filas_declaradas():
    t = pd.DataFrame({
        "descripcion": [f"PAGO {i}" for i in range(40)] + ["PAGO A PERSONA"] * 5,
        "monto": 20000, "signo": "-", "cuenta_tipo": "banco",
        "categoria_n1": ["educacion"] * 20 + ["otros"] * 20 + ["educacion"] * 5,
        "fuente_etiqueta": ["texto"] * 40 + ["declaracion_voluntario"] * 5,
    })
    a, b = llm.ejemplos_few_shot(t), llm.ejemplos_few_shot(t)
    assert a == b and len(a) == 6
    assert not any("PAGO A PERSONA" in x for x, _ in a)


def test_serializacion_canonica():
    t = pd.DataFrame({"cuenta_tipo": ["banco"], "signo": ["-"], "monto": [25000], "descripcion": ["COMPRA EXITO"]})
    assert base.serializar(t).iloc[0] == "[CUENTA=banco] [SIGNO=-] [MONTO=10K-30K] COMPRA EXITO"
