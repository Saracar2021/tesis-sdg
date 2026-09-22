#!/usr/bin/env python
"""Cálculos de diseño muestral para la anotación TSTR (WP4).

Tres cálculos, cada uno con sus supuestos declarados en el CSV de salida (columna `nota`):
  (a) participación mínima por categoría para soporte >= 10 con N en {360, 450, 600};
  (b) cruce de (a) con la participación de cada categoría de la taxonomía v1 en ENPH Bogotá
      (proxy declarado: prevalencia de hogares con al menos una compra en P438, gastos menos
      frecuentes; no es participación de transacciones ni de gasto, y no hay supuesto de
      conversión entre una y otra: se declara la diferencia y se usa la prevalencia tal cual);
  (c) ancho del IC 95 % del kappa de Cohen para n en {100, 150, 200, 300}, con acuerdo esperado
      calculado a partir de las participaciones de (b).

Uso (desde la raíz del repo):
    .venv\\Scripts\\python.exe tools\\calculos_diseno_muestral.py

No escribe nada en data/raw/. Toda cifra sale de este código y queda en outputs/diseno_muestral/.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DISTRIB = RAIZ / "outputs" / "distribuciones"
OUT = RAIZ / "outputs" / "diseno_muestral"

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

N_VALUES = [360, 450, 600]          # tamaños de muestra a anotar considerados (04_diseno_muestra)
N_ANOTADO_VALUES = [100, 150, 200, 300]  # tamaños de solapamiento doble-anotado considerados
SOPORTE_MINIMO = 10                 # regla de soporte de protocolo_tecnico.md (PENDIENTE de origen)
Z_95 = 1.959963984540054            # z crítico exacto de la normal estándar al 97.5 % (constante
                                     # matemática, no cifra de datos; equivale a scipy.stats.norm.ppf(0.975))

# --- Mapeo ENPH P438 (grupo, gastos MENOS frecuentes) -> categoría de taxonomia_gastos_colombia_v1 ---
# INFERIDO / SUPUESTO, no verificado en ningún documento del proyecto:
# - P438 (Cuadernillo 3) NO cubre gastos frecuentes (alimentos_mercado, comidas_fuera) ni las
#   4 categorías operativas del extracto (transferencias_p2p, retiro_efectivo, movimiento_propio,
#   ingreso), porque esas no tienen fuente ENPH en absoluto (ver D15, protocolo_tecnico.md §5).
# - "obligaciones_financieras" tampoco tiene subcapítulo P438 propio: se deja sin dato.
# - H ("transporte y comunicaciones") se asigna solo a `transporte`; `telecom_conectividad` queda
#   sin dato porque ENPH no separa comunicaciones de transporte en ese subcapítulo.
# - A y G se combinan en `hogar_articulos`; B y D se combinan en `vestuario_cuidado_personal`;
#   H e I se combinan en `transporte`. Son simplificaciones declaradas, no verificadas.
MAPEO_GRUPO_A_CATEGORIA = {
    "A": "hogar_articulos", "G": "hogar_articulos",
    "B": "vestuario_cuidado_personal", "D": "vestuario_cuidado_personal",
    "C": "vivienda_servicios",
    "E": "educacion",
    "F": "salud",
    "H": "transporte", "I": "transporte",
    "J": "entretenimiento",
    "L": "otros",
}
CATEGORIAS_SIN_DATO_ENPH = [
    "alimentos_mercado", "comidas_fuera", "telecom_conectividad",
    "obligaciones_financieras", "transferencias_p2p", "retiro_efectivo",
    "movimiento_propio", "ingreso",
]
NOTA_PROXY = ("Proxy declarado: %% de hogares de Bogotá con al menos una compra en el subcapítulo "
              "P438 (gastos menos frecuentes, ponderado con FEX_C). NO es participación de "
              "transacciones ni de gasto (son cosas distintas: un hogar puede comprar poco pero "
              "muchas veces, o mucho pero una sola vez). No se aplica ningún supuesto de conversión "
              "entre prevalencia de hogares y participación de transacciones: se declara la "
              "diferencia y se usa la prevalencia tal cual, como cota aproximada.")


def soporte_minimo_por_n(n_values: list[int], soporte: int = SOPORTE_MINIMO) -> pd.DataFrame:
    """(a) Participación mínima por categoría para que el soporte esperado sea >= `soporte`."""
    return pd.DataFrame({
        "N": n_values,
        "soporte_minimo": soporte,
        "participacion_minima_pct": [100 * soporte / n for n in n_values],
        "nota": f"soporte >= {soporte} requiere participación >= soporte/N (regla F1 macro, protocolo_tecnico.md §3.4)",
    })


def participacion_enph_por_categoria() -> pd.DataFrame:
    """(b, insumo) Prevalencia ENPH por categoría de la taxonomía, agregada desde P438."""
    cob = pd.read_csv(DISTRIB / "enph_p438_cobertura.csv")
    cob["letra"] = cob["subcapitulo"].str[0]
    cob["categoria"] = cob["letra"].map(MAPEO_GRUPO_A_CATEGORIA)
    con_dato = cob.dropna(subset=["categoria"])
    prevalencia = (con_dato.groupby("categoria")["pct_hogares_bogota_con_respuesta"]
                   .mean().rename("prevalencia_hogares_pct"))
    n_subcapitulos = con_dato.groupby("categoria").size().rename("n_subcapitulos_p438")
    tabla = pd.concat([prevalencia, n_subcapitulos], axis=1).reset_index()
    tabla["participacion_relativa_pct"] = 100 * tabla["prevalencia_hogares_pct"] / tabla["prevalencia_hogares_pct"].sum()
    tabla["fuente"] = "ENPH 2016-2017, gastos_menos_frecuentes_medio_pago.csv (P438), Bogotá, FEX_C"
    tabla["nota"] = NOTA_PROXY
    tabla["con_dato_enph"] = True

    sin_dato = pd.DataFrame({
        "categoria": CATEGORIAS_SIN_DATO_ENPH,
        "prevalencia_hogares_pct": np.nan,
        "n_subcapitulos_p438": 0,
        "participacion_relativa_pct": np.nan,
        "fuente": "sin fuente ENPH (gasto frecuente no cubierto por P438, o categoría operativa de extracto)",
        "nota": "No evaluable: ENPH no tiene esta categoría en P438. No se inventa una cifra.",
        "con_dato_enph": False,
    })
    return pd.concat([tabla, sin_dato], ignore_index=True)


def soporte_insuficiente_por_categoria(part_a: pd.DataFrame, part_b: pd.DataFrame) -> pd.DataFrame:
    """(b) Cruce: para cada N, qué categorías con dato ENPH quedarían con soporte esperado < 10."""
    con_dato = part_b[part_b["con_dato_enph"]].copy()
    filas = []
    for _, r in part_a.iterrows():
        for _, c in con_dato.iterrows():
            soporte_esperado = r["N"] * c["participacion_relativa_pct"] / 100
            filas.append({
                "N": int(r["N"]),
                "categoria": c["categoria"],
                "participacion_relativa_pct": c["participacion_relativa_pct"],
                "soporte_esperado": soporte_esperado,
                "soporte_insuficiente": bool(soporte_esperado < SOPORTE_MINIMO),
            })
    return pd.DataFrame(filas)


def kappa_ic95_ancho(part_b: pd.DataFrame, po_values: list[float], n_values: list[int]) -> pd.DataFrame:
    """(c) Ancho del IC 95% de kappa de Cohen. Supuestos declarados en `nota`.

    pe (acuerdo esperado por azar) se calcula como sum(p_i^2) sobre las K categorías CON dato ENPH
    de (b), renormalizadas a sumar 1, asumiendo marginales iguales para los dos anotadores.
    NO se calcula un pe para las 16 categorías de la taxonomía completa: 8 de ellas no tienen
    participación ENPH (ver CATEGORIAS_SIN_DATO_ENPH) y no hay una base para inventarles una cifra;
    ese escenario queda PENDIENTE, no calculado.

    SE(kappa) se aproxima con SE(kappa) ~= sqrt(po*(1-po) / (n*(1-pe)^2)), una simplificación de
    tipo Fleiss (1981) / Sim & Wright (2005) para planeación de tamaño de muestra que asume un
    patrón de desacuerdo simétrico entre categorías (no la fórmula exacta de Fleiss-Cohen-Everitt
    1969, que requiere la matriz de confusión completa). NO VERIFICADA contra la fuente primaria
    línea por línea: se declara como aproximación, no como fórmula confirmada.
    """
    con_dato = part_b[part_b["con_dato_enph"]].copy()
    p = con_dato["participacion_relativa_pct"].to_numpy() / 100.0
    p = p / p.sum()
    k_categorias = len(p)
    pe = float(np.sum(p ** 2))

    filas = []
    for po in po_values:
        for n in n_values:
            se = np.sqrt(po * (1 - po) / (n * (1 - pe) ** 2))
            ancho = 2 * Z_95 * se
            filas.append({
                "n_doble_anotado": n,
                "acuerdo_observado_po": po,
                "k_categorias_con_dato_enph": k_categorias,
                "acuerdo_esperado_pe": pe,
                "se_kappa_aprox": se,
                "ic95_ancho_aprox": ancho,
                "nota": ("Aproximación de tipo Fleiss/Sim-Wright, no la fórmula exacta de "
                         "Fleiss-Cohen-Everitt (1969); pe calculado solo sobre las categorías con "
                         "dato ENPH, no sobre las 16 de la taxonomía completa."),
            })
    return pd.DataFrame(filas)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    a = soporte_minimo_por_n(N_VALUES)
    a.to_csv(OUT / "a_soporte_minimo_por_n.csv", index=False, encoding="utf-8")

    b = participacion_enph_por_categoria()
    b.to_csv(OUT / "b_participacion_enph_por_categoria.csv", index=False, encoding="utf-8")

    b_cruce = soporte_insuficiente_por_categoria(a, b)
    b_cruce.to_csv(OUT / "b_soporte_insuficiente_por_categoria_y_n.csv", index=False, encoding="utf-8")

    c = kappa_ic95_ancho(b, po_values=[0.80, 0.90], n_values=N_ANOTADO_VALUES)
    c.to_csv(OUT / "c_kappa_ic95_ancho.csv", index=False, encoding="utf-8")

    manifest = {
        "seed": SEED,
        "z_95": Z_95,
        "n_values_a": N_VALUES,
        "n_anotado_values_c": N_ANOTADO_VALUES,
        "soporte_minimo": SOPORTE_MINIMO,
        "k_categorias_con_dato_enph": int(b["con_dato_enph"].sum()),
        "categorias_sin_dato_enph": CATEGORIAS_SIN_DATO_ENPH,
        "fuentes": [str((DISTRIB / "enph_p438_cobertura.csv").relative_to(RAIZ))],
        "advertencia": "pandas/numpy determinan el orden de agregación; sin aleatoriedad real en estos cálculos (SEED fijado por convención del proyecto, no porque el cálculo lo requiera).",
    }
    (OUT / "manifest_diseno_muestral.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("OK: outputs/diseno_muestral/")
    print(a.to_string(index=False))
    print(b[["categoria", "prevalencia_hogares_pct", "participacion_relativa_pct", "con_dato_enph"]].to_string(index=False))
    print(c.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
