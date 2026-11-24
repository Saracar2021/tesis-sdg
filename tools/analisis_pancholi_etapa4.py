"""WP5 — Análisis de la salida de la etapa 4 (LLM) del pipeline de referencia: H-P1, H-P2, H-P3 por ejecución.

Parte de los registros crudos (outputs/pancholi/etapa4/llamadas.jsonl y transacciones_etapa4.csv), no de la API,
así que es reproducible. Escribe outputs/pancholi/etapa4/analisis_etapa4.json y payment_type_distribucion.csv.
Uso: python tools/analisis_pancholi_etapa4.py [--precio-in USD_por_M --precio-out USD_por_M]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
from analisis_pancholi import wilson  # noqa: E402

E4 = RAIZ / "outputs" / "pancholi" / "etapa4"
MAP4 = RAIZ / "docs" / "taxonomia" / "mapeo_pancholi_etapa4_taxonomia_v1.csv"
CLIENTES = RAIZ / "external" / "pancholi" / "src" / "Data_Synthesizer" / "data" / "synthetic_customer_gan.csv"
RNG = 20261123
B = 10_000
# Normalización de payment_type (texto libre del LLM, en inglés) al enum medio_pago de la taxonomía v1.1.
# Orden: la primera regla que casa gana. Lo que no casa va a otro_nd y se lista aparte.
REGLAS_MEDIO = [
    (r"debit", "tarjeta_debito"),
    (r"credit|visa|mastercard|amex|american express|discover", "tarjeta_credito"),
    (r"cash", "efectivo"),
    (r"apple ?pay|google ?pay|samsung ?pay|paypal|venmo|zelle|cash ?app|wallet|mobile|contactless", "billetera_digital"),
    (r"bank transfer|ach|wire|transfer", "transferencia_bancaria"),
    (r"gift|voucher|coupon", "bono_subsidio"),
]


def medio(texto: str) -> str:
    t = str(texto).lower()
    for patron, destino in REGLAS_MEDIO:
        if re.search(patron, t):
            return destino
    return "otro_nd"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--precio-in", type=float, help="USD por millón de tokens de entrada (precio de lista vigente)")
    ap.add_argument("--precio-out", type=float, help="USD por millón de tokens de salida")
    a = ap.parse_args()

    man = json.loads((E4 / "manifest_etapa4.json").read_text(encoding="utf-8"))
    ll = pd.read_json(E4 / "llamadas.jsonl", lines=True)
    tx = pd.read_csv(E4 / "transacciones_etapa4.csv")
    m4 = pd.read_csv(MAP4).set_index("subcategoria_etapa4")

    # --- subcategoría pedida (prompt) y devuelta (LLM)
    ll["subcat_pedida"] = ll.prompt.str.extract(r"Spending Category: (\S+)")[0]
    tx["cat_llm"] = tx.merchant_details.map(lambda s: ast.literal_eval(s).get("category"))
    ok = ll[ll.contenido.notna()].copy()
    # las filas de tx salen en el orden de las llamadas válidas: emparejar por JSON parseable
    def parsea(c):
        try:
            j = json.loads(c.split("\n", 1)[1].rsplit("```", 1)[0] if str(c).startswith("```") else c)
            return all(k in j for k in ["amount", "timestamp", "merchant_details", "payment_type"])
        except Exception:
            return False
    ok = ok[ok.contenido.map(parsea)].reset_index(drop=True)
    if len(ok) != len(tx):
        raise SystemExit(f"No se pudo emparejar llamadas ({len(ok)}) y filas ({len(tx)})")
    tx["subcat_pedida"] = ok.subcat_pedida.values
    tx["n1"] = tx.subcat_pedida.map(m4.nivel_1_v1)
    N = len(tx)

    # --- H-P3: medio de pago
    tx["payment_norm"] = tx.payment_type.astype(str).str.strip().str.lower()
    tx["medio_pago_v1"] = tx.payment_type.map(medio)
    filas = []
    for col in ["payment_norm", "medio_pago_v1"]:
        for v, x in tx[col].value_counts().items():
            p, lo, hi = wilson(int(x), N)
            filas.append({"nivel": col, "valor": v, "n": int(x), "N": N, "part": p, "wilson_inf": lo, "wilson_sup": hi})
    dist = pd.DataFrame(filas)
    dist.to_csv(E4 / "payment_type_distribucion.csv", index=False)
    top = dist[dist.nivel == "medio_pago_v1"].iloc[0]

    # --- H-P1: elasticidad monto–ingreso entre clientes (bootstrap sobre clientes; una sola corrida)
    cli = pd.read_csv(CLIENTES).set_index("customer_id")["income"]
    g = tx.groupby("customer_id").amount.mean().to_frame("m").join(cli.rename("inc"), how="inner")
    g = g[g.m > 0]
    x, y = np.log(g.inc.values), np.log(g.m.values)
    beta = float(np.polyfit(x, y, 1)[0])
    rng = np.random.default_rng(RNG)
    bs = []
    for _ in range(B):
        i = rng.integers(0, len(g), len(g))
        if np.ptp(x[i]) > 0:
            bs.append(np.polyfit(x[i], y[i], 1)[0])

    # --- H-P2: categorías emitidas y regla prerregistrada (docs/prerregistro_wp5.md)
    cnt = tx.n1.value_counts()
    cats = {c: {"n": int(n), "part": n / N, "ic95": list(wilson(int(n), N)[1:])} for c, n in cnt.items()}

    def regla_ocio(grupos: pd.Series) -> dict:
        c = grupos.value_counts()
        w = {k: wilson(int(v), N) for k, v in c.items()}
        o = w["ocio"]
        resto = {k: v for k, v in w.items() if k != "ocio"}
        ali = w.get("alimentos_mercado", (0, 0, 0))
        ver = ("confirmada" if o[1] > max(v[2] for v in resto.values()) else
               "refutada" if o[2] < ali[1] else "no concluyente")
        return {"part_ocio": o[0], "ic95_ocio": [o[1], o[2]], "part_alimentos": ali[0],
                "ic95_alimentos": [ali[1], ali[2]], "veredicto": ver}

    fam = tx.subcat_pedida.map(m4.familia_pancholi)
    ocio = tx.n1.where(tx.n1 != "entretenimiento", "ocio")
    ocio_h = tx.n1.where(~((tx.n1 == "entretenimiento") | (fam == "Lodging")), "ocio")
    nombres = tx.merchant_details.map(lambda s: ast.literal_eval(s).get("name", ""))
    fallback = float(nombres.str.match(r"DC \S+ Service$").mean())

    uso = man["resultado"]
    costo = None
    if a.precio_in is not None and a.precio_out is not None:
        costo = uso["prompt_tokens"] / 1e6 * a.precio_in + uso["completion_tokens"] / 1e6 * a.precio_out
    res = {
        "simulado": man.get("simulado", False),
        "modelo_usado": man["modelo_usado"], "desviacion_modelo": man["desviacion_modelo"],
        "N_filas": N, "llamadas": uso["llamadas"], "fallos": uso["fallos"],
        "tasa_fallo": uso["fallos"] / max(uso["llamadas"], 1),
        "H-P3": {"valores_distintos_payment_type": int(tx.payment_norm.nunique()),
                 "medio_mas_frecuente": top.valor, "part_medio_mas_frecuente": top.part,
                 "ic95_medio_mas_frecuente": [top.wilson_inf, top.wilson_sup],
                 "monolitico_100pct": bool(top.n == N),
                 "medios_v1_distintos": sorted(tx.medio_pago_v1.unique()),
                 "ausentes_cota_sup_wilson": {m: wilson(int((tx.medio_pago_v1 == m).sum()), N)[2]
                                              for m in ["efectivo", "billetera_digital", "transferencia_bancaria"]},
                 "part_por_medio_v1": {m: {"part": float(v / N), "ic95": list(wilson(int(v), N)[1:])}
                                       for m, v in tx.medio_pago_v1.value_counts().items()},
                 "registros_extracto_retiro_p2p_propio_ingreso": int(tx.n1.isin(
                     ["retiro_efectivo", "transferencias_p2p", "movimiento_propio", "ingreso"]).sum())},
        "H-P2": {"categorias_n1_emitidas": cats, "n_categorias_n1": int(cnt.size),
                 "ocio_entretenimiento": regla_ocio(ocio), "ocio_con_hospedaje": regla_ocio(ocio_h),
                 "part_comercio_generico_fallback": fallback,
                 "fidelidad_categoria_llm": float((tx.cat_llm == tx.subcat_pedida).mean())},
        "H-P1": {"elasticidad_entre_clientes": beta,
                 "ic95_bootstrap_clientes": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                 "n_clientes": int(len(g)),
                 "sensible_al_ingreso": bool(np.percentile(bs, 2.5) > 0 or np.percentile(bs, 97.5) < 0),
                 "mecanismo": "el prompt incluye 'Expected spending range' = peso de la subcategoría x ingreso/12"},
        "monto_usd": {"media": float(tx.amount.mean()), "mediana": float(tx.amount.median()),
                      "p01": float(tx.amount.quantile(.01)), "p99": float(tx.amount.quantile(.99))},
        "costo": {"prompt_tokens": uso["prompt_tokens"], "completion_tokens": uso["completion_tokens"],
                  "minutos": uso["minutos"], "usd_estimado": costo,
                  "precio_usd_por_M": [a.precio_in, a.precio_out]},
    }
    (E4 / "analisis_etapa4.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
