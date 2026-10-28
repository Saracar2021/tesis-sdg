"""Genera la muestra sintética por reglas (WP6, Etapa 2; hito del plan maestro) a partir del pool de donantes (determinista, SEED = 42).

Ejecutar desde la raíz (después de tools/construir_generador.py):
  .venv\\Scripts\\python.exe tools\\generar_sintetico_reglas.py [--n 1000] [--semilla 42] [--escenario bajo|base|alto]
                                                            [--modo-donantes por_categoria|por_hogar] [--modo-cuentas multiple|una] [--sin-sensibilidad]

Lee: outputs/generador/ (pool y mezcla; NO lee microdatos), outputs/priors/priors.json, docs/generador/ (tablas y parámetros propios).
Escribe (outputs/sintetico_reglas/):
  transacciones.csv.gz            ambas capas (interna y emitida); NO se versiona (.gitignore). CTGAN entrena con capa == emitida.
  perfiles_generados.csv          un perfil por fila: celda, posición, cuentas, banco, billetera, ingreso mensual
  muestra_20_perfiles.csv         las filas de los 20 primeros perfiles (revisión a ojo; sí se versiona)
  resumen_generacion.json         diagnósticos de la muestra
  sensibilidad.csv                escenarios digitales, modo de donantes, modo de cuentas, medio principal, pagos recurrentes digitales
  manifest.json                   versiones, semilla, sha256 (del contenido, no del gzip), estado del IPC y parámetros
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sdg import generador as G, priors as PR  # noqa: E402

OUT = RAIZ / "outputs" / "sintetico_reglas"
N_DEFECTO = 1000
N_SENSIBILIDAD = 1000
N_MUESTRA_PERFILES = 20

SENSIBILIDAD = {
    "base": {},
    "digital_bajo": {"digital.escenario": "bajo"},
    "digital_alto": {"digital.escenario": "alto"},
    "donantes_por_hogar": {"donantes.modo": "por_hogar"},
    "una_cuenta": {"cuentas.modo": "una"},
    "medio_principal_0.6": {"medios.p_uso_medio_principal": 0.6},
    "medio_principal_1.0": {"medios.p_uso_medio_principal": 1.0},
    "recurrentes_digitales_bajo": {"recurrentes_digital.servicios": 0.3, "recurrentes_digital.arriendo": 0.3},
    "recurrentes_digitales_alto": {"recurrentes_digital.servicios": 0.9, "recurrentes_digital.arriendo": 0.9},
}


def csv_bytes(df: pd.DataFrame, **kw) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False, lineterminator="\n", **kw)
    return buf.getvalue().encode("utf-8")


def escribir_gz(ruta: Path, contenido: bytes) -> None:
    with open(ruta, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0, filename="") as g:
        g.write(contenido)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_archivo(ruta: Path) -> str:
    return sha(Path(ruta).read_bytes())


def fila_sensibilidad(nombre: str, T: pd.DataFrame, P: pd.DataFrame, info: dict) -> dict:
    em, it = T[T["capa"] == "emitida"], T[T["capa"] == "interna"]
    v = it.groupby("medio_pago")["monto"].sum()
    v = v / v.sum()
    n_p = len(P)
    return dict(
        escenario=nombre, n_perfiles=n_p, filas_emitidas_por_perfil_mes=len(em) / (n_p * len(info["meses"])),
        pct_filas_billetera=100 * float((em["cuenta_tipo"] == "billetera").mean()), pct_filas_tc=100 * float((em["cuenta_tipo"] == "tarjeta_credito").mean()),
        pct_valor_interno_efectivo=100 * float(v.get("efectivo", 0.0) + v.get("fiado_credito_tienda", 0.0)),
        pct_valor_interno_digital=100 * float(v.get("billetera_digital", 0.0) + v.get("transferencia_bancaria", 0.0)),
        pct_valor_interno_tarjeta=100 * float(v.get("tarjeta_debito", 0.0) + v.get("tarjeta_credito", 0.0)),
        pct_filas_emitidas_p2p_con_proposito=100 * float(em["canal_p2p"].mean()),
        pct_filas_emitidas_transferencias_p2p=100 * float((em["categoria_n1"] == "transferencias_p2p").mean()),
        pct_filas_emitidas_retiro=100 * float((em["categoria_n1"] == "retiro_efectivo").mean()),
        mediana_monto_emitido=float(em["monto"].median()),
        gasto_sobre_ingreso_mediana=info["gasto_sobre_ingreso_por_perfil"]["mediana"], gasto_sobre_ingreso_p90=info["gasto_sobre_ingreso_por_perfil"]["p90"],
        migracion_lograda=info["medios"]["migracion"]["fraccion_lograda"]).copy()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=N_DEFECTO)
    ap.add_argument("--semilla", type=int, default=G.SEED)
    ap.add_argument("--escenario", choices=["bajo", "base", "alto"], default=None)
    ap.add_argument("--modo-donantes", choices=["por_categoria", "por_hogar"], default=None)
    ap.add_argument("--modo-cuentas", choices=["multiple", "una"], default=None)
    ap.add_argument("--sin-sensibilidad", action="store_true")
    a = ap.parse_args()
    ov = {}
    if a.escenario:
        ov["digital.escenario"] = a.escenario
    if a.modo_donantes:
        ov["donantes.modo"] = a.modo_donantes
    if a.modo_cuentas:
        ov["cuentas.modo"] = a.modo_cuentas

    pool = G.cargar_pool()
    priors = PR.cargar_priors()
    OUT.mkdir(parents=True, exist_ok=True)

    T, P, info = G.generar_muestra(pool, priors, a.n, a.semilla, overrides=ov)
    b_tx = csv_bytes(T)
    b_pf = csv_bytes(P, float_format="%.2f")
    escribir_gz(OUT / "transacciones.csv.gz", b_tx)
    (OUT / "perfiles_generados.csv").write_bytes(b_pf)
    primeros = P["perfil_id"].iloc[:N_MUESTRA_PERFILES]
    (OUT / "muestra_20_perfiles.csv").write_bytes(csv_bytes(T[T["perfil_id"].isin(primeros)]))
    (OUT / "resumen_generacion.json").write_text(json.dumps(info, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")

    sens = None
    if not a.sin_sensibilidad:
        filas = []
        for nombre, extra in SENSIBILIDAD.items():
            if nombre == "base":
                T2, P2, i2 = T, P, info
            else:
                T2, P2, i2 = G.generar_muestra(pool, priors, N_SENSIBILIDAD, a.semilla, overrides=ov | extra)
            filas.append(fila_sensibilidad(nombre, T2, P2, i2))
        sens = pd.DataFrame(filas).round(4)
        sens.to_csv(OUT / "sensibilidad.csv", index=False, encoding="utf-8", lineterminator="\n")

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip() or "no disponible"
    except OSError:
        commit = "no disponible"
    gen = RAIZ / "outputs" / "generador"
    par, crudo = G.cargar_parametros(overrides=ov)
    man = {
        "script": "tools/generar_sintetico_reglas.py", "commit_base": commit, "pandas": pd.__version__, "numpy": np.__version__, "python": sys.version.split()[0],
        "semilla": a.semilla, "n_perfiles": a.n, "overrides": ov, "parametros_propios_version": crudo.get("version"),
        "escenario_digital": par["digital.escenario"], "modo_donantes": par["donantes.modo"], "modo_cuentas": par["cuentas.modo"],
        "ipc_aplicado": bool(pool.meta.get("ipc_aplicado", False)),
        "aviso": None if pool.meta.get("ipc_aplicado") else "SIN IPC: montos en pesos de 2016-17 (factor 1,0); no comparar niveles con 2025",
        "filas": info["filas"], "meses": info["meses"],
        "columnas": G.COLUMNAS, "observables": G.OBSERVABLES, "gold": G.GOLD,
        "sha256_transacciones_csv": sha(b_tx), "sha256_perfiles_csv": sha(b_pf),
        "sha256_priors_json": sha_archivo(PR.RUTA_PRIORS),
        "sha256_entradas": {"parametros_propios.json": sha_archivo(G.RUTA_PARAMETROS),
                            **{n: sha_archivo(G.DIR_PARAM / n) for n in ("comercios_curados.csv", "plantillas_descriptor.csv", "permisos_medios_digitales.csv",
                                                                         "palabras_nombres.csv", "sucursales_bogota.csv", "empleadores_ficticios.csv", "lugares_compra.csv")},
                            "mezcla_donantes.json": sha_archivo(gen / "mezcla_donantes.json"), "estructura_cuentas.csv": sha_archivo(gen / "estructura_cuentas.csv")},
        "sha256_pool_descomprimido": json.loads((gen / "manifest_generador.json").read_text(encoding="utf-8")).get("sha256_pool_descomprimido")
        if (gen / "manifest_generador.json").is_file() else None,
        "sensibilidad": "sensibilidad.csv" if sens is not None else None,
    }
    (OUT / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"{info['filas']['total']} filas ({info['filas']['emitida']} emitidas) para {a.n} perfiles; sha256 transacciones {man['sha256_transacciones_csv'][:16]}…")
    if man["aviso"]:
        print("AVISO:", man["aviso"])
    if sens is not None:
        print(sens.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
