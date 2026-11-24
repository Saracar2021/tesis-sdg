import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from sdg import texto  # noqa: E402
from sdg.comercios import Plantillas  # noqa: E402

POOL = RAIZ / "outputs" / "generador" / "pool"
requiere_pool = pytest.mark.skipif(not (POOL / "eventos.csv.gz").exists(), reason="pool del generador no construido")


def _filas():
    return pd.DataFrame([
        # cuenta, signo, n1, n2, medio, origen, canal_p2p
        ("banco", "-", "alimentos_mercado", "supermercado_cadena", "tarjeta_debito", "compra", False),
        ("billetera", "-", "comidas_fuera", None, "billetera_digital", "compra", False),
        ("banco", "-", "alimentos_mercado", "tienda_barrio", "transferencia_bancaria", "compra", True),
        ("billetera", "+", "transferencias_p2p", "recibida_persona", "billetera_digital", "p2p_sin_proposito", False),
        ("banco", "-", "retiro_efectivo", "corresponsal", "tarjeta_debito", "retiro", False),
        ("banco", "-", "alimentos_mercado", "supermercado_cadena", "tarjeta_debito", "retiro", False),
    ], columns=texto.COLUMNAS_ESTRUCTURA)


def test_tipo_evento_tabla_de_decision():
    t = texto.tipo_evento(_filas())
    assert list(t) == ["compra_debito", "compra_billetera", "p2p_enviada_banco", "p2p_recibida_billetera",
                       "retiro_corresponsal_banco", "retiro_atm_banco"]


def test_incoherencia_se_marca_no_se_repara():
    inc = texto.incoherencias(_filas())
    assert list(inc[:5]) == [""] * 5 and inc[5] == "origen_vs_categoria_n1"


def test_plantilla_p2p_respeta_n2_objetivo():
    pl = Plantillas(texto.DIR_PARAM)
    n = 300
    tipo = np.full(n, "p2p_recibida_billetera", dtype=object)
    vacio = np.full(n, "", dtype=object)
    _, n2 = pl.descripciones(np.random.default_rng(0), tipo, vacio, vacio, np.full(n, "NEQUI", dtype=object), vacio,
                             n2_objetivo=np.full(n, "recibida_persona", dtype=object))
    assert set(n2) == {"recibida_persona"}


def test_d14_rechaza_rutas_bajo_data():
    with pytest.raises(PermissionError):
        texto._rechazar_reales(texto.carga.RAIZ / "data" / "reales_anon")


@requiere_pool
def test_determinista_y_conserva_etiquetas():
    df = _filas()
    a, _ = texto.agregar_texto(df, seed=42)
    b, _ = texto.agregar_texto(df, seed=42)
    assert (a["descripcion"] == b["descripcion"]).all()
    assert (a["categoria_n1"] == df["categoria_n1"]).all()
    assert list(a["fuente_etiqueta"]) == ["texto", "texto", "declaracion_voluntario", "texto", "texto", "texto"]
