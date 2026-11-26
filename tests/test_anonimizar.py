# -*- coding: utf-8 -*-
"""Pruebas del anonimizador de extractos (tools/anonimizar_extractos.py).

Cubre: (1) el bug de v1.0 (sobre-enmascarado de terminos financieros), (2) que los nombres
reales de persona si se enmascaran, (3) el parseo multi-formato de montos (colombiano y anglo,
signo al inicio o al final) y (4) los formatos de fecha (ISO, DD/MM/AAAA y DD MM sin anio).
"""
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "anonimizar_extractos", RAIZ / "tools" / "anonimizar_extractos.py"
)
anon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anon)


def _dep(s):
    c = {"titular": 0, "persona_R_A": 0, "digitos_R_B": 0}
    return anon.depurar(s, [], c)


def test_no_enmascara_terminos_financieros():
    assert _dep("CENTRAL DE C PAGO DE INTERESES") == "CENTRAL DE C PAGO DE INTERESES"
    assert _dep("PAGO DE INTERES GENERADO") == "PAGO DE INTERES GENERADO"
    assert _dep("RETENCION EN LA FUENTE") == "RETENCION EN LA FUENTE"


def test_enmascara_nombres_reales():
    assert _dep("TRANSFERENCIA A JUAN PEREZ") == "TRANSFERENCIA A PERSONA"
    assert _dep("PAGO A MARIA GOMEZ LOPEZ") == "PAGO A PERSONA"
    assert _dep("NEQUI A CARLOS RAMIREZ") == "NEQUI A PERSONA"


def test_enmascara_digitos_largos():
    assert _dep("Rec.Inter TFR FR-13520323") == "Rec.Inter TFR FR-#"


def test_titular_se_enmascara():
    c = {"titular": 0, "persona_R_A": 0, "digitos_R_B": 0}
    out = anon.depurar("COMPRA EN TIENDA DE SARA CARDENAS", ["SARA CARDENAS"], c)
    assert "SARA CARDENAS" not in out
    assert "PERSONA" in out


def test_monto_colombiano():
    assert anon.valor_monto("3.000.000,00")[:2] == (3000000, False)
    assert anon.valor_monto("-35.000,00")[:2] == (35000, True)
    assert anon.valor_monto("35.000")[:2] == (35000, False)   # miles sin decimales


def test_monto_anglo():
    assert anon.valor_monto("200,000.00-")[:2] == (200000, True)   # signo al final
    assert anon.valor_monto("$129,860.00-")[:2] == (129860, True)
    assert anon.valor_monto("1,234,567.89")[:2] == (1234567, False)


def test_fechas():
    assert anon.leer_fecha("2026-03-15 PAGO", formato_fecha="auto")[0].isoformat() == "2026-03-15"
    assert anon.leer_fecha("15/03/2026 PAGO", formato_fecha="auto")[0].isoformat() == "2026-03-15"
    # DD MM sin anio (Davivienda): el anio viene del parametro
    assert anon.leer_fecha("   03   01   $200", 2026, "dm")[0].isoformat() == "2026-01-03"
    # en modo auto, 'DD MM' no debe matchear (evita falsos positivos)
    assert anon.leer_fecha("03 01 $200", formato_fecha="auto")[0] is None


def test_posible_nombre():
    assert anon.es_posible_nombre("LUIS ALEJANDRO RAMIREZ")
    assert anon.es_posible_nombre("BLANCA YANIT PLAZAS")
    assert not anon.es_posible_nombre("OXXO CONNECTA")          # no empieza por nombre de pila
    assert not anon.es_posible_nombre("MERCADO PAGO SAMSUNG")   # MERCADO no es nombre de pila


def test_fecha_cc():
    assert anon.leer_fecha("Virtual 2026-04-20 DLO*DIDI", formato_fecha="cc")[0].isoformat() == "2026-04-20"
    assert anon.leer_fecha("2026-04-20 sin etiqueta", formato_fecha="cc")[0] is None


def test_monto_signo_mas_davivienda():
    # Davivienda: "fecha | $ 90,000.00+ | Doc | Clase | Oficina". El '+' final marca el abono;
    # el Doc (entero suelto) no debe tomarse como monto.
    lineas = ["  03   02   $ 90,000.00+   2565   Transferencia De Otra Entidad A Llave   Redeban BreB"]
    mov = anon.parsear_extracto(lineas, "2026-02", None, "dm", filtrar_mes=False)["movimientos"][0]
    assert mov["monto"] == 90000 and not mov["negativo"]
    assert "2565" not in mov["desc_cruda"] and "Transferencia" in mov["desc_cruda"]


def test_monto_menor_a_un_peso():
    # Bancolombia imprime los intereses < $1 como ".51": no debe tomarse el saldo ni leerse como 51.
    assert anon.valor_monto(".51")[0] == 0
    r = anon.parsear_extracto(["5/02 ABONO INTERESES AHORROS .51 1,212,881.96"], "2026-02", "primera", "dm", filtrar_mes=False)
    assert r["movimientos"][0]["monto"] == 0


def test_gmf_sin_fecha():
    lineas = ["30/04/2026 CENTRAL DE C PAGO DE INTERESES 12,61 160.019,23",
              "IMP/TRANS FINANC/ACUM MES -1.200,00 158.832,60"]
    movs = anon.parsear_extracto(lineas, "2026-04", "primera", "auto", filtrar_mes=False)["movimientos"]
    assert len(movs) == 2 and movs[1]["monto"] == 1200 and movs[1]["negativo"]
    assert movs[1]["fecha"] == movs[0]["fecha"]


def test_personas_v1_2():
    c = {"titular": 0, "persona_R_A": 0, "digitos_R_B": 0}
    casos = {
        "TRANSF A Sara Juliana": "TRANSF A PERSONA",            # minúsculas
        "TRANSF DE LUZ MELIDA O": "TRANSF DE PERSONA",          # truncado por el banco
        "TRANSF QR NEQUI FABIAN ROA": "TRANSF QR NEQUI PERSONA",
        "PAGO QR Gloria Yaneth": "PAGO QR PERSONA",             # condicional: nombre de pila
        "PAGO QR SALSAMENTARIA": "PAGO QR SALSAMENTARIA",       # condicional: comercio intacto
        "COMPRA EN JUAN VALDEZ": "COMPRA EN JUAN VALDEZ",       # marca con nombre de pila
        "PAGO DE NOMI REPREMUNDO S A": "PAGO DE NOMI REPREMUNDO S A",  # concepto tras el prefijo
        "PAGO DE INTERESES": "PAGO DE INTERESES",
    }
    for entrada, esperado in casos.items():
        assert anon.depurar(entrada, [], c) == esperado, entrada


def test_llaves_breb():
    c = {"titular": 0, "persona_R_A": 0, "digitos_R_B": 0}
    assert anon.depurar("CENTRAL DE C BREB @sarac6353", [], c) == "CENTRAL DE C BREB LLAVE"
    assert anon.depurar("CENTRAL DE C BREB diegocan@live.com.ar", [], c) == "CENTRAL DE C BREB LLAVE"
    assert anon.depurar("CRUZ VERDE ACU@A UNICE", [], c) == "CRUZ VERDE ACU@A UNICE"   # Ñ mal codificada: no es llave


def test_tarjeta_comercio_partido_y_pagos():
    lineas = ["SR WOK CONNECTA",
              "Virtual 2026-08-24 $24.900,00 $24.900,00 1 de 1 $0,00 0,0000% 0,00%",
              "BOGOTA",
              "- 2026-08-30 PAGOS POR PSE $-3.365.000,00 N/A N/A N/A 0% 0,00%",
              "Virtual 2026-08-30 R59 CREPESYWAFFLES NUE $56.725,00 $56.725,00 1 de 1 $0,00 0,0000% 0,00%"]
    movs = anon.parsear_extracto(lineas, "2026-08", "primera", "cc", filtrar_mes=False)["movimientos"]
    assert [m["desc_cruda"].strip() for m in movs] == ["SR WOK CONNECTA BOGOTA", "PAGOS POR PSE", "R59 CREPESYWAFFLES NUE"]
    assert [m["monto"] for m in movs] == [24900, 3365000, 56725]
    assert [anon.signo_de(m, "tarjeta") for m in movs] == ["egreso", "ingreso", "egreso"]
