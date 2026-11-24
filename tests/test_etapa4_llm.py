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
    assert llm.parsear("ingreso o transferencias_p2p", CLASES) == ("otros", "fuera_de_enum")
    assert llm.parsear("", CLASES) == ("otros", "vacia")
    assert llm.parsear(None, CLASES) == ("otros", "vacia")


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
