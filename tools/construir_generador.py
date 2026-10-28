"""Calibra el gasto del hogar para el generador por reglas (WP6, Etapa 2, PD5) y escribe el pool de donantes (determinista).

Ejecutar desde la raíz:  .venv\\Scripts\\python.exe tools\\construir_generador.py [--ipc RUTA] [--modo-ipc total|division] [--referencia-ipc mes_recoleccion|promedio_campo|anio_2017]

Entradas: SOLO microdatos vía sdg.carga (dentro de sdg.gasto_enph) y las tablas versionadas de docs/generador/. Sin aleatoriedad.
Salidas (outputs/generador/):
  pool/eventos.csv.gz, recurrentes.csv.gz, hogares.csv.gz   microdatos derivados por hogar (NO se versionan: .gitignore)
  mezcla_donantes.json              P(celda), P(quintil), P(Bogotá) del donante por celda (κ_donantes) y marca «rala»
  estructura_cuentas.csv            P(banco, billetera, tarjeta de crédito | estrato) desde GEIH 2025 (P5222)
  calibracion_meta.json             IPC aplicado o no, κ
  diagnostico_calibracion.json      conteos por fuente, filas descartadas, reconciliación con GCMUG, IPC
  categoria_valor_mensual.csv       gasto mensual medio del hogar por categoría de la taxonomía (FEX; pesos 2016-17 y con IPC)
  cobertura_mapeo.csv               valor mensual por prefijo COICOP → categoría (para revisar el mapeo provisional)
  recurrentes_resumen.csv           arriendo, cuota de vivienda, servicios públicos y de conectividad
  manifest_generador.json

IPC: el deflactor es el índice TOTAL nacional (``outputs/ipc/ipc_total_nacional.csv``, de ``tools/convertir_ipc.py``); referencia = mes de recolección
de cada hogar y base = promedio 2025 (ver ``sdg.ipc``). Sin el CSV los montos quedan en pesos de 2016-17 y la salida se marca «sin IPC» (factor 1,0).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sdg import carga, generador as G, gasto_enph as GE, ipc as ipc_mod  # noqa: E402

OUT = RAIZ / "outputs" / "generador"
REDONDEO = 6


def _sha(ruta: Path) -> str:
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def _manifest_conversion() -> dict | None:
    """Datos del xlsx de origen que dejó ``tools/convertir_ipc.py`` (sha256 del xlsx, texto «Actualizado el…»); ``None`` si no se corrió."""
    ruta = RAIZ / "outputs" / "ipc" / "manifest_ipc.json"
    if not ruta.is_file():
        return None
    m = json.loads(ruta.read_text(encoding="utf-8"))
    return {k: m.get(k) for k in ("archivo", "hoja", "sha256_xlsx", "actualizado", "primer_mes", "ultimo_mes", "indice_2018_12")}


def _promedio(x: pd.Series, w: pd.Series) -> float:
    return float(np.average(x.fillna(0.0), weights=w))


def categoria_valor_mensual(R: dict) -> pd.DataFrame:
    h = R["hogares"].set_index("DIRECTORIO")
    w = h["FEX"]
    ev, rec = R["eventos"], R["recurrentes"]
    filas = []
    for fuente, df, vcol in (("eventos", ev, "valor"), ("recurrentes", rec, "valor")):
        d = df.assign(m=df[vcol] * df["factor"], m_ipc=df[vcol] * df["factor"] * df["factor_ipc"])
        g = d.groupby(["DIRECTORIO", "categoria_n1"])[["m", "m_ipc"]].sum().reset_index()
        g["fuente"] = fuente
        filas.append(g)
    g = pd.concat(filas, ignore_index=True)
    out = []
    for cat in GE.CATEGORIAS_GASTO:
        x = g[g["categoria_n1"] == cat].groupby("DIRECTORIO")[["m", "m_ipc"]].sum().reindex(h.index).fillna(0.0)
        out.append(dict(categoria_n1=cat, media_mensual_hogar_2016_17=_promedio(x["m"], w), media_mensual_hogar_con_ipc=_promedio(x["m_ipc"], w),
                        pct_hogares_con_gasto=float(100 * (w * (x["m"] > 0)).sum() / w.sum()),
                        mediana_ponderada_entre_con_gasto=_mediana_ponderada(x["m"][x["m"] > 0], w[x["m"] > 0])))
    t = pd.DataFrame(out)
    t["participacion_valor_pct"] = 100 * t["media_mensual_hogar_2016_17"] / t["media_mensual_hogar_2016_17"].sum()
    return t.round(REDONDEO)


def _mediana_ponderada(x: pd.Series, w: pd.Series) -> float:
    if not len(x):
        return float("nan")
    o = np.argsort(x.to_numpy())
    c = np.cumsum(w.to_numpy()[o])
    return float(x.to_numpy()[o][np.searchsorted(c, 0.5 * c[-1])])


def recurrentes_resumen(R: dict) -> pd.DataFrame:
    rec, h = R["recurrentes"], R["hogares"].set_index("DIRECTORIO")
    n_h, masa = len(h), h["FEX"].sum()
    filas = []
    for c, g in rec.groupby("concepto"):
        filas.append(dict(concepto=c, categoria_n1=g["categoria_n1"].iloc[0], categoria_n2=g["categoria_n2"].iloc[0], hogares_con_valor=int(len(g)),
                          pct_hogares_expandido=float(100 * g["FEX"].sum() / masa),
                          valor_medio_ponderado=float(np.average(g["valor"], weights=g["FEX"])),
                          frecuencia_mensual_media=float(np.average(g["factor"], weights=g["FEX"]))))
    return pd.DataFrame(filas).round(REDONDEO)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ipc", default=None, help="ruta del CSV de IPC en formato largo (mes, division, indice)")
    ap.add_argument("--modo-ipc", choices=["division", "total"], default=None)
    ap.add_argument("--referencia-ipc", choices=list(ipc_mod.REFERENCIAS), default=None)
    a = ap.parse_args()
    par_prop = json.loads((GE.DIR_PARAM / "parametros_propios.json").read_text(encoding="utf-8"))
    modo_ipc = a.modo_ipc or par_prop["calibracion"]["modo_ipc"]["valor"]
    referencia_ipc = a.referencia_ipc or par_prop["calibracion"]["referencia_ipc"]["valor"]

    print(f"calibrando (IPC: modo {modo_ipc}, referencia {referencia_ipc}; archivo {a.ipc or ipc_mod.RUTA_IPC.relative_to(RAIZ)})…")
    R = GE.construir(modo_ipc, a.ipc, referencia_ipc)
    pool = G.pool_desde_calibracion(R)
    OUT.mkdir(parents=True, exist_ok=True)
    G.guardar_pool(pool, OUT / "pool", OUT)

    diag = {k: v for k, v in R["diag"].items() if k != "cobertura_mapeo"}
    diag["cuentas"] = R["diag_cuentas"]
    diag["kappa_donantes"] = {k: R["kappa"][k] for k in ("kappa", "en_frontera", "categorias_usadas", "categorias_omitidas", "n_bins") if k in R["kappa"]}
    (OUT / "diagnostico_calibracion.json").write_text(json.dumps(diag, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    R["diag"]["cobertura_mapeo"].round(REDONDEO).to_csv(OUT / "cobertura_mapeo.csv", index=False, encoding="utf-8", lineterminator="\n")
    tabla = categoria_valor_mensual(R)
    tabla.to_csv(OUT / "categoria_valor_mensual.csv", index=False, encoding="utf-8", lineterminator="\n")
    recurrentes_resumen(R).to_csv(OUT / "recurrentes_resumen.csv", index=False, encoding="utf-8", lineterminator="\n")

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip() or "no disponible"
    except OSError:
        commit = "no disponible"
    ruta_ipc = Path(a.ipc) if a.ipc else ipc_mod.RUTA_IPC
    rutas_tablas = [GE.DIR_PARAM / n for n in ("mensualizacion_enph.csv", "periodo_referencia_caps.csv", "lugares_compra.csv",
                                                "mapeo_coicop_taxonomia_provisional.csv", "parametros_propios.json")]
    rutas_salida = [OUT / n for n in ("mezcla_donantes.json", "estructura_cuentas.csv", "diagnostico_calibracion.json", "categoria_valor_mensual.csv",
                                      "cobertura_mapeo.csv", "recurrentes_resumen.csv")]
    man = {
        "script": "tools/construir_generador.py", "commit_base": commit, "pandas": pd.__version__, "numpy": np.__version__, "python": sys.version.split()[0],
        "semilla": GE.SEED, "nota_semilla": "la calibración no usa aleatoriedad; SEED se declara por convención",
        "ipc": R["diag"]["ipc"] | {"modo_solicitado": modo_ipc, "referencia_solicitada": referencia_ipc,
                                   "archivo": str(ipc_mod.RUTA_IPC.relative_to(RAIZ)).replace("\\", "/") if a.ipc is None else a.ipc,
                                   "sha256_serie": _sha(ruta_ipc) if ruta_ipc.is_file() else None, "manifest_conversion": _manifest_conversion()},
        "kappa_donantes": R["kappa"]["kappa"], "kappa_en_frontera": bool(R["kappa"]["en_frontera"]),
        "conteos": {"hogares_bogota": R["diag"]["hogares"]["n_bogota"], "hogares_con_celda": R["diag"]["hogares"]["n_con_celda"],
                    "eventos": int(len(R["eventos"])), "recurrentes": int(len(R["recurrentes"])), "celdas_ralas_donantes": int(sum(m["rala"] for m in R["mezcla"].values()))},
        "reconciliacion_gcmug": R["diag"]["reconciliacion_gcmug"],
        "sha256_tablas_entrada": {p.name: _sha(p) for p in rutas_tablas},
        "sha256_salidas": {p.name: _sha(p) for p in rutas_salida},
        "sha256_pool_descomprimido": {n: _sha_gz(OUT / "pool" / f"{n}.csv.gz") for n in ("eventos", "recurrentes", "hogares")},
        "uniones": [{k: u[k] for k in ("nombre", "llave", "filas_izq", "pct_enlazado", "umbral")} for u in carga.UNIONES],
    }
    (OUT / "manifest_generador.json").write_text(json.dumps(man, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")

    r = R["diag"]["reconciliacion_gcmug"]
    print(f"κ donantes = {R['kappa']['kappa']:.2f} | hogares {man['conteos']['hogares_con_celda']} | eventos {man['conteos']['eventos']} | recurrentes {man['conteos']['recurrentes']}")
    print(f"reconciliación con GCMUG: eventos {r['agregado_eventos_sobre_gcmug']:.3f}; eventos + recurrentes {r['agregado_eventos_mas_recurrentes_sobre_gcmug']:.3f}")
    di = R["diag"]["ipc"]
    if di.get("aplicado"):
        print(f"IPC aplicado: {di['indice']}, base {di['base']}, referencia {di['referencia']}; factor entre {di['factor_min']:.4f} y {di['factor_max']:.4f}")
    else:
        print(f"IPC aplicado: False ({di.get('motivo')})")
    print(tabla[["categoria_n1", "media_mensual_hogar_2016_17", "pct_hogares_con_gasto", "participacion_valor_pct"]].to_string(index=False))
    return 0


def _sha_gz(ruta: Path) -> str:
    import gzip
    h = hashlib.sha256()
    with gzip.open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
