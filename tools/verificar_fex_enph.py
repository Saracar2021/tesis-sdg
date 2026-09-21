"""Verificación empírica de FEX_C en ENPH (solo lectura de data/raw; escribe outputs/).

Pregunta: ¿FEX_C es un factor de la vivienda/hogar, el mismo en todas las tablas?
Metodología ENPH (Metodologia_ENPH.pdf, §2.2.4.1): la calibración se hace a nivel de
vivienda y «a la vivienda corresponde un único factor de expansión». Aquí se contrasta:
  (1) FEX_C constante dentro de DIRECTORIO en cada tabla;
  (2) FEX_C de cada tabla == FEX_C de viviendas_hogares para el mismo DIRECTORIO.
Solo urbano + hogares + personas (rural fuera de alcance).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ENPH = RAIZ / "data" / "raw" / "ENPH_2017"
ARCHIVOS = [
    ("hogares", "viviendas_hogares.csv"),
    ("hogares", "gastos_menos_frecuentes_medio_pago.csv"),
    ("hogares", "gastos_menos_frecuentes_articulos.txt"),
    ("personas", "caracteristicas_generales_personas.csv"),
    ("urbano", "gastos_diarios_hogar_comidas_fuera.csv"),
    ("urbano", "gastos_diarios_personales.csv"),
    ("urbano", "gastos_diarios_capitulo_c.txt"),
    ("urbano", "gastos_diarios_mercados.csv"),
    ("urbano", "gastos_diarios_hogar.txt"),
    ("urbano", "gastos_personales_comidas_fuera.csv"),
]


def leer(carpeta, nombre):
    ruta = ENPH / carpeta / nombre
    if nombre.endswith(".txt"):
        kw = dict(sep="\t", encoding="utf-8")
    else:
        kw = dict(sep=";", encoding="utf-8-sig")
    return pd.read_csv(ruta, usecols=["DIRECTORIO", "FEX_C"], dtype=str, **kw)


def num(s):
    return pd.to_numeric(s.str.strip().str.replace(",", ".", regex=False), errors="coerce")


ref = leer("hogares", "viviendas_hogares.csv")
ref["FEX_C"] = num(ref["FEX_C"])
ref = ref.set_index("DIRECTORIO")["FEX_C"]
res = {}
for carpeta, nombre in ARCHIVOS:
    d = leer(carpeta, nombre)
    d["FEX_C"] = num(d["FEX_C"])
    g = d.groupby("DIRECTORIO")["FEX_C"]
    rango = (g.max() - g.min()).fillna(0)
    ref_dir = d["DIRECTORIO"].map(ref)
    ok = np.isclose(d["FEX_C"], ref_dir, rtol=1e-9, atol=0)
    res[f"{carpeta}/{nombre}"] = dict(
        filas=int(len(d)),
        directorios=int(d["DIRECTORIO"].nunique()),
        fex_nulos=int(d["FEX_C"].isna().sum()),
        directorios_con_fex_no_constante=int((rango > 1e-9).sum()),
        filas_con_directorio_en_hogares=int(ref_dir.notna().sum()),
        filas_fex_igual_a_hogares=int(ok.sum()),
        pct_filas_fex_igual_a_hogares=round(100 * ok.mean(), 4),
    )
    print(carpeta, nombre, res[f"{carpeta}/{nombre}"])
(RAIZ / "outputs").mkdir(exist_ok=True)
(RAIZ / "outputs" / "fex_enph_verificacion.json").write_text(
    json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
