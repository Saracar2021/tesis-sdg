"""Pruebas de las utilidades de la Etapa 3 (reglas duras, cuotas, elasticidad). No requieren torch/sdv."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from sdg import etapa3 as E  # noqa: E402

ANIO = {12: 2025, 4: 2026, 8: 2026}
PARES = {("alimentos_mercado", "tienda_barrio"), ("transferencias_p2p", "enviada_persona"), ("otros", E.SIN_N2)}


def fila(**k):
    base = dict(cuenta_tipo="banco", signo="-", categoria_n1="alimentos_mercado", categoria_n2="tienda_barrio", medio_pago="tarjeta_debito",
                origen="compra", formalidad_comercio="formal", canal_p2p=False, monto=1000, ingreso_mensual=1e6, dia_mes=15, mes=4)
    base.update(k)
    return base


def viola(**k):
    v = E.violaciones(pd.DataFrame([fila(**k)]), PARES, ANIO).iloc[0]
    return set(v.index[v])


def test_fila_valida_no_viola():
    assert viola() == set()


@pytest.mark.parametrize("cambio, regla", [
    (dict(monto=0), "monto_no_positivo"),
    (dict(medio_pago="billetera_digital"), "medio_imposible_para_cuenta"),
    (dict(cuenta_tipo="tarjeta_credito", medio_pago="tarjeta_debito"), "medio_imposible_para_cuenta"),
    (dict(categoria_n2="enviada_persona"), "par_n1_n2_inexistente"),
    (dict(categoria_n2=E.SIN_N2), "par_n1_n2_inexistente"),
    (dict(dia_mes=31, mes=4), "fecha_imposible"),
    (dict(dia_mes=0), "fecha_imposible"),
    (dict(mes=2), "fecha_imposible"),
])
def test_cada_regla(cambio, regla):
    assert viola(**cambio) == {regla}


def test_canal_p2p_sigue_la_regla_r2():
    # pago a persona con propósito declarado: categoría del propósito, por transferencia → válido
    assert viola(canal_p2p=True, medio_pago="transferencia_bancaria") == set()
    # con tarjeta no puede ser canal P2P
    assert viola(canal_p2p=True) == {"canal_p2p_incoherente"}
    # P2P sin propósito lleva canal_p2p=False; con True es incoherente
    assert viola(canal_p2p=True, medio_pago="transferencia_bancaria", origen="p2p_sin_proposito",
                 categoria_n1="transferencias_p2p", categoria_n2="enviada_persona") == {"canal_p2p_incoherente"}


def test_dia_31_valido_en_agosto_y_diciembre():
    assert viola(dia_mes=31, mes=8) == set() and viola(dia_mes=31, mes=12) == set()


def test_cuotas_suman_n_y_son_deterministas():
    m = pd.Series({"a": 5, "b": 3, "c": 1, "d": 1})
    q = E.cuotas(m, 7)
    assert int(q.sum()) == 7 and q.equals(E.cuotas(m, 7))
    assert E.cuotas(m, 10).to_dict() == {"a": 5, "b": 3, "c": 1, "d": 1}


def test_elasticidad_recupera_pendiente_y_el_piso_la_destruye():
    rng = np.random.default_rng(0)
    ing = np.exp(rng.normal(14, 0.8, 4000))
    d = pd.DataFrame([fila()] * 4000)
    d["ingreso_mensual"] = ing
    d["monto"] = np.exp(0.5 * np.log(ing) + rng.normal(0, 0.3, 4000))
    d["perfil_id"] = np.arange(4000) // 4
    assert abs(E.elasticidad(d) - 0.5) < 0.02
    lo, hi = E.ic_elasticidad(d, seed=42, b=300, conglomerado="perfil_id")
    assert lo < 0.5 < hi
    lo, hi = E.ic_elasticidad(d, seed=42, b=300)
    assert lo < 0.5 < hi
    assert abs(E.elasticidad(E.piso_marginales(d, 4000, seed=42))) < 0.05


def test_particion_por_perfil_no_comparte_perfiles():
    d = pd.DataFrame({"perfil_id": [f"S{i % 50:03d}" for i in range(1000)], "x": range(1000)})
    tr, ho = E.partir_por_perfil(d, 0.2, 42)
    assert not set(tr.perfil_id) & set(ho.perfil_id) and ho.perfil_id.nunique() == 10
    assert E.partir_por_perfil(d, 0.2, 42)[1].equals(ho)


@pytest.mark.parametrize("punto, ic, esperado", [
    (0.33, (0.31, 0.35), "CONSERVA"), (0.50, (0.48, 0.52), "CONSERVA"), (0.231, (0.22, 0.24), "CONSERVA"),
    (0.20, (0.19, 0.21), "ATENÚA"), (0.10, (0.09, 0.11), "ATENÚA"),
    (0.03, (0.02, 0.04), "NO CONSERVA"), (0.004, (-0.002, 0.010), "NO CONSERVA"), (-0.05, (-0.07, -0.03), "NO CONSERVA"),
    (0.25, (-0.01, 0.51), "NO CONSERVA"),
])
def test_veredicto_elasticidad(punto, ic, esperado):
    v, r = E.veredicto_elasticidad(punto, ic, 0.33)
    assert v == esperado and abs(r - punto / 0.33) < 1e-12


@pytest.mark.parametrize("cambio, viola_signo", [
    (dict(signo="+"), True),
    (dict(origen="nomina", signo="-"), True),
    (dict(origen="pago_tarjeta", cuenta_tipo="tarjeta_credito", medio_pago="transferencia_bancaria", signo="+"), False),
    (dict(origen="pago_tarjeta", cuenta_tipo="tarjeta_credito", medio_pago="transferencia_bancaria", signo="-"), True),
    (dict(origen="recarga_billetera", cuenta_tipo="billetera", medio_pago="transferencia_bancaria", signo="-"), True),
    (dict(origen="p2p_sin_proposito", categoria_n2="recibida_persona", signo="-"), True),
    (dict(origen="p2p_sin_proposito", categoria_n2="indeterminada", signo="+"), False),
    (dict(origen="p2p_sin_proposito", categoria_n2="indeterminada", signo="-"), False),
])
def test_regla_signo(cambio, viola_signo):
    assert ("signo_incompatible_con_origen" in viola(**cambio)) == viola_signo
