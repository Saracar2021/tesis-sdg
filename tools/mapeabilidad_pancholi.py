"""WP5 → WP8 — ¿Es mapeable la salida del pipeline de referencia (Pancholi et al.) a las 16 categoria_n1?

Criterio único (fijado por la autora): el output de su pipeline es mapeable a las 16 categoria_n1 de la
taxonomía v1.1.0 y al contexto colombiano.
Operacionalización (docs/reevaluacion_pancholi.md §6):
  MAPEABLE  ⇔  las 16 categoria_n1 son alcanzables desde alguna etiqueta que su generador emite con peso > 0
              (etapa 2 `base_allocation` ∪ etapa 4 `spending_categories`), con los mapeos versionados en
              docs/taxonomia/. Sensibilidad (no cambia la regla): restringir a las clases con soporte ≥ 10
              en outputs/ctgan/sintetico_v1.csv.gz, aproximación del soporte real hasta que WP4 anote.
Evidencia complementaria: masa de filas del sintético del protocolo en clases alcanzables, techo de F1-macro
de un clasificador entrenado con su salida, y columnas del esquema WP8 derivables de su salida.

Lee el código del clon (external/pancholi, commit fijado) sin importarlo. Escribe
outputs/pancholi/wp8_mapeabilidad.json y outputs/pancholi/wp8_cobertura_categorias.csv.
Uso: python tools/mapeabilidad_pancholi.py
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CLON = RAIZ / "external" / "pancholi"
ETAPA2 = CLON / "src" / "component" / "transaction.py"
ETAPA4 = CLON / "src" / "Data_Synthesizer" / "code" / "transaction_deepseek_synthesizer.py"
TAXO = RAIZ / "docs" / "taxonomia" / "taxonomia_gastos_colombia_v1.json"
MAP2 = RAIZ / "docs" / "taxonomia" / "mapeo_pancholi_taxonomia_v1.csv"
MAP4 = RAIZ / "docs" / "taxonomia" / "mapeo_pancholi_etapa4_taxonomia_v1.csv"
SINT = RAIZ / "outputs" / "ctgan" / "sintetico_v1.csv.gz"
SALIDA = RAIZ / "outputs" / "pancholi"
SOPORTE_MIN = 10          # regla de reporte de la taxonomía (soporte >= 10)

# Columnas que la etapa 3 emite (verificado en ejecución, outputs/pancholi/hp3_registros_extracto.csv) y las
# que la etapa 4 emite (leídas de su dict de retorno en _generate_transactions_api).
COLS_ETAPA3 = ["customer_id", "zipcode", "category", "merchant_name", "mapped_category", "transaction_amount", "timestamp"]
COLS_ETAPA4 = ["customer_id", "amount", "timestamp", "merchant_details", "payment_type"]

# Derivabilidad de cada columna del esquema WP8 (outputs/ctgan/sintetico_v1.csv.gz) desde su salida.
# 'directa': existe; 'constante': solo emite compras, el valor es fijo; 'inventada': exigiría un supuesto
# externo (tipo de cambio, deflactor, regla de asignación) que su pipeline no contiene; 'ausente': no existe.
DERIVABILIDAD = {
    "fecha": ("directa", "timestamp"),
    "cuenta_tipo": ("ausente", "no modela cuentas"),
    "signo": ("constante", "todo registro es una compra: '-'"),
    "categoria_n1": ("parcial", "ver cobertura"),
    "categoria_n2": ("parcial", "ver mapeos"),
    "medio_pago": ("ausente", "etapas 1-3 sin campo; etapa 4: payment_type en texto libre en inglés"),
    "origen": ("constante", "solo 'compra'"),
    "formalidad_comercio": ("ausente", "no modela formalidad"),
    "canal_p2p": ("constante", "sin P2P: False"),
    "monto": ("inventada", "USD de D.C.; pasar a COP exige tipo de cambio y paridad de poder adquisitivo externos"),
    "ingreso_mensual": ("inventada", "ingreso anual en USD del ACS de D.C."),
    "dia_mes": ("directa", "de timestamp"),
    "mes": ("directa", "de timestamp"),
}


def dict_literal(ruta: Path, nombre: str) -> dict:
    """Primer dict literal asignado a `nombre` (variable o atributo self.nombre) en el archivo."""
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Assign):
            for t in nodo.targets:
                if getattr(t, "id", None) == nombre or getattr(t, "attr", None) == nombre:
                    # valores como `0.18 + (0.02 if ... else 0)`: se toma el término base (constante izquierda)
                    base = lambda v: ast.literal_eval(v.left if isinstance(v, ast.BinOp) else v)
                    return {ast.literal_eval(k): base(v) for k, v in zip(nodo.value.keys, nodo.value.values)}
    raise KeyError(f"{nombre} no está en {ruta}")


def etiquetas_emitidas() -> pd.DataFrame:
    """Etiquetas que cada etapa puede emitir, con su peso en el código."""
    filas = []
    for etapa, ruta, var in [("etapa2", ETAPA2, "base_allocation"), ("etapa4", ETAPA4, "spending_categories")]:
        for etiqueta, peso in dict_literal(ruta, var).items():
            filas.append({"etapa": etapa, "etiqueta": etiqueta, "peso_codigo": float(peso)})
    e = pd.DataFrame(filas)
    m2 = pd.read_csv(MAP2).fillna("")
    m4 = pd.read_csv(MAP4).fillna("")
    mapa = {("etapa2", r.etiqueta_pancholi): (r.nivel_1_v1, r.nivel_2_v1) for r in m2.itertuples()}
    mapa |= {("etapa4", r.subcategoria_etapa4): (r.nivel_1_v1, r.nivel_2_v1) for r in m4.itertuples()}
    faltan = [(r.etapa, r.etiqueta) for r in e.itertuples() if (r.etapa, r.etiqueta) not in mapa]
    if faltan:
        raise SystemExit(f"Etiquetas sin mapeo: {faltan}")
    e["nivel_1_v1"] = [mapa[(r.etapa, r.etiqueta)][0] for r in e.itertuples()]
    e["nivel_2_v1"] = [mapa[(r.etapa, r.etiqueta)][1] for r in e.itertuples()]
    return e


def main() -> None:
    taxo = json.loads(TAXO.read_text(encoding="utf-8"))
    clases = [c["id"] for c in taxo["categorias_nivel_1"]]
    e = etiquetas_emitidas()
    alcanzables = sorted(set(e.loc[e.peso_codigo > 0, "nivel_1_v1"]))

    s = pd.read_csv(SINT, usecols=["categoria_n1", "origen"])
    soporte = s.categoria_n1.value_counts()
    evaluadas = [c for c in clases if soporte.get(c, 0) >= SOPORTE_MIN]

    cob = pd.DataFrame({"categoria_n1": clases})
    cob["alcanzable_pancholi"] = cob.categoria_n1.isin(alcanzables)
    cob["etiquetas_pancholi"] = cob.categoria_n1.map(
        lambda c: "; ".join(f"{r.etapa}:{r.etiqueta}" for r in e[(e.nivel_1_v1 == c) & (e.peso_codigo > 0)].itertuples()))
    cob["peso_codigo_etapa4"] = cob.categoria_n1.map(
        lambda c: float(e[(e.etapa == "etapa4") & (e.nivel_1_v1 == c)].peso_codigo.sum()))
    cob["filas_sintetico_v1"] = cob.categoria_n1.map(lambda c: int(soporte.get(c, 0)))
    cob["part_sintetico_v1"] = cob.filas_sintetico_v1 / len(s)
    cob.to_csv(SALIDA / "wp8_cobertura_categorias.csv", index=False)

    alc_eval = [c for c in evaluadas if c in alcanzables]
    techo_16 = len([c for c in clases if c in alcanzables]) / len(clases)
    techo_eval = len(alc_eval) / len(evaluadas)
    masa = float(cob.loc[cob.alcanzable_pancholi, "part_sintetico_v1"].sum())
    p4 = e[e.etapa == "etapa4"]
    peso4 = p4.groupby("nivel_1_v1").peso_codigo.sum()
    # sensibilidad: sin las rutas marginales (clase alcanzable solo por subcategorías de la etapa 4 con peso <= 0,02 y
    # sin ruta en la etapa 2; p. ej. driving_lessons -> educacion, boarding_house -> vivienda_servicios)
    con_e2 = set(e.loc[(e.etapa == "etapa2") & (e.peso_codigo > 0), "nivel_1_v1"])
    marginales = [c for c in alcanzables if c not in con_e2 and peso4.get(c, 0) <= 0.02]
    alc_nm = [c for c in alcanzables if c not in marginales]
    mapeable = set(alcanzables) >= set(clases)
    mapeable_sens = set(alcanzables) >= set(evaluadas)
    res = {
        "criterio": "mapeable ⇔ las 16 categoria_n1 alcanzables desde etiquetas con peso > 0 (etapas 2 y 4)",
        "taxonomia_version": taxo["metadata"]["version"],
        "n_clases_taxonomia": len(clases),
        "etiquetas_etapa2": int((e.etapa == "etapa2").sum()),
        "etiquetas_etapa4": int((e.etapa == "etapa4").sum()),
        "etiquetas_etapa4_peso_cero": sorted(p4.loc[p4.peso_codigo == 0, "etiqueta"]),
        "clases_alcanzables": alcanzables,
        "n_clases_alcanzables": len(alcanzables),
        "clases_no_alcanzables": [c for c in clases if c not in alcanzables],
        "rutas_de_peso_minimo": {c: float(peso4.get(c, 0)) for c in alcanzables if 0 < peso4.get(c, 0) <= 0.02},
        "sensibilidad_soporte": {"soporte_min": SOPORTE_MIN, "fuente_soporte": str(SINT.relative_to(RAIZ)),
                                 "clases_evaluadas": evaluadas, "alcanzables_entre_evaluadas": alc_eval},
        "clases_por_ruta_marginal": marginales,
        "n_clases_alcanzables_sin_marginales": len(alc_nm),
        "techo_f1_macro_16_sin_marginales": len(alc_nm) / len(clases),
        "masa_sintetico_v1_sin_marginales": float(cob.loc[cob.categoria_n1.isin(alc_nm), "part_sintetico_v1"].sum()),
        "techo_f1_macro_16": techo_16,
        "techo_f1_macro_clases_evaluadas": techo_eval,
        "masa_sintetico_v1_en_clases_alcanzables": masa,
        "masa_sintetico_v1_por_origen_no_alcanzable": (
            s[~s.categoria_n1.isin(alcanzables)].origen.value_counts(normalize=True).to_dict()),
        "derivabilidad_esquema_wp8": {k: {"estado": v[0], "nota": v[1]} for k, v in DERIVABILIDAD.items()},
        "columnas_salida_etapa3": COLS_ETAPA3,
        "columnas_salida_etapa4": COLS_ETAPA4,
        "mapeable": mapeable,
        "mapeable_sensibilidad": mapeable_sens,
        "veredicto_wp8": "(b) baseline comparable" if mapeable else "(a) Pancholi solo como contexto",
    }
    (SALIDA / "wp8_mapeabilidad.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ["n_clases_alcanzables", "clases_no_alcanzables", "techo_f1_macro_16",
                                          "techo_f1_macro_clases_evaluadas", "masa_sintetico_v1_en_clases_alcanzables",
                                          "rutas_de_peso_minimo", "n_clases_alcanzables_sin_marginales",
                                          "techo_f1_macro_16_sin_marginales", "masa_sintetico_v1_sin_marginales", "mapeable", "mapeable_sensibilidad", "veredicto_wp8"]},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
