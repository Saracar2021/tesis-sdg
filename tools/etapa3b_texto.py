"""Capa de texto (WP6, 2.ª capa) sobre las DOS fuentes estructuradas de la ablación reglas → CTGAN.

Salidas (mismas plantillas, misma semilla, misma función ``sdg.texto.agregar_texto``):
  outputs/ctgan/sintetico_v1_con_texto.csv.gz            CTGAN (Etapa 3) + texto
  outputs/sintetico_reglas/sintetico_reglas_con_texto_v1.csv.gz   generador por reglas (capa emitida) + texto,
                                                          SIN su descripción original (se reemplaza)
  outputs/texto/manifest.json                             hashes, versiones, diagnósticos, validación

Uso (desde la raíz del repo, entorno .venv):
  .venv/Scripts/python tools/etapa3b_texto.py

D14: no lee nada bajo data/ (ni el real anotado de WP4).
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from sdg import texto  # noqa: E402

SEED = texto.SEED
ENTRADA_CTGAN = Path("outputs/ctgan/sintetico_v1.csv.gz")
ENTRADA_REGLAS = Path("outputs/sintetico_reglas/transacciones.csv.gz")
SALIDA_CTGAN = Path("outputs/ctgan/sintetico_v1_con_texto.csv.gz")
SALIDA_REGLAS = Path("outputs/sintetico_reglas/sintetico_reglas_con_texto_v1.csv.gz")
MANIFEST = Path("outputs/texto/manifest.json")
# columnas que comparten ambas fuentes (las del CTGAN); de reglas se conserva además perfil_id
COLUMNAS_CTGAN = ["fecha", "cuenta_tipo", "signo", "categoria_n1", "categoria_n2", "medio_pago", "origen",
                  "formalidad_comercio", "canal_p2p", "monto"]
GZIP = {"method": "gzip", "mtime": 0}


def sha(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_contenido(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def main() -> None:
    for r in (ENTRADA_CTGAN, ENTRADA_REGLAS):
        if not (RAIZ / r).exists():
            sys.exit(f"falta {r}")

    reglas = pd.read_csv(RAIZ / ENTRADA_REGLAS, low_memory=False)
    reglas = reglas[reglas["capa"] == "emitida"].reset_index(drop=True)
    validacion = texto.validar_contra_reglas(reglas)
    print(f"validación tipo_evento vs. descripciones originales del generador: {validacion['coinciden']:,}/"
          f"{validacion['filas']:,} ({validacion['frac']:.4%})")
    if validacion["frac"] < 1.0:
        print("  AVISO: la tabla de decisión no reproduce todas las filas:", validacion["ejemplos_no_coinciden"][:3])

    ctgan = pd.read_csv(RAIZ / ENTRADA_CTGAN)
    fuentes = {
        "ctgan": (ctgan, ENTRADA_CTGAN, SALIDA_CTGAN),
        "reglas": (reglas[["perfil_id"] + COLUMNAS_CTGAN], ENTRADA_REGLAS, SALIDA_REGLAS),
    }
    man = {
        "script": "tools/etapa3b_texto.py", "modulo": "src/sdg/texto.py", "semilla": SEED,
        "declaracion": ("Capa de texto del protocolo (2.ª capa del generador, WP6), aplicada con la misma función, "
                        "plantillas y semilla a la capa emitida del generador por reglas y al CTGAN. Plantillas y "
                        "comercios: docs/generador (regla propia, listados públicos). Latentes del comercio: pool ENPH "
                        "2016-17 (FEX × frecuencia). No usa el real anotado de WP4 (D14)."),
        "validacion_tipo_evento_vs_reglas": validacion,
        "parametros": {f"docs/generador/{p}": sha(RAIZ / "docs/generador" / p)
                       for p in ("plantillas_descriptor.csv", "comercios_curados.csv", "parametros_propios.json",
                                 "lugares_compra.csv", "palabras_nombres.csv", "sucursales_bogota.csv",
                                 "empleadores_ficticios.csv")},
        "pool": {p: sha(RAIZ / "outputs/generador/pool" / p) for p in ("eventos.csv.gz", "recurrentes.csv.gz")},
        "versiones": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "plataforma": platform.platform(),
        "fuentes": {},
    }
    for nombre, (df, ent, sal) in fuentes.items():
        out, diag = texto.agregar_texto(df, seed=SEED)
        (RAIZ / sal).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(RAIZ / sal, index=False, compression=GZIP)
        man["fuentes"][nombre] = {"entrada": ent.as_posix(), "sha256_entrada": sha(RAIZ / ent),
                                  "salida": sal.as_posix(), "sha256_contenido_salida": sha_contenido(out), **diag}
        print(f"[{nombre}] {len(out):,} filas -> {sal.as_posix()} | incoherentes {diag['frac_incoherente']:.2%} "
              f"| descripciones únicas {diag['descripciones_unicas']:,}")
    (RAIZ / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (RAIZ / MANIFEST).write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {MANIFEST.as_posix()}")


if __name__ == "__main__":
    main()
