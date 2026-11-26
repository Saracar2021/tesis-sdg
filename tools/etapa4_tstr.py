"""
Etapa 4 / WP8 — Clasificadores entrenados sobre SINTÉTICO, evaluados por TSTR.

Dos modos, decididos por una sola ruta (--test):
  * sin --test  -> SANITY CHECK (NO REPORTABLE): split 80/20 estratificado por
                   categoria_n1 dentro de cada sintético. Mide ajuste interno, no TSTR.
  * con --test  -> TSTR: entrena sobre TODO el sintético y evalúa sobre el real
                   anotado de WP4. Único número reportable.

Fuentes de entrenamiento (ablación reglas -> CTGAN, mismas plantillas de texto):
  reglas -> outputs/sintetico_reglas/sintetico_reglas_con_texto_v1.csv.gz   "protocolo (reglas)"
  ctgan  -> outputs/ctgan/sintetico_v1_con_texto.csv.gz                     "protocolo (CTGAN)"
  (ambas las produce tools/etapa3b_texto.py; reglas_original = texto original del generador, solo diagnóstico)

Brazos: 'logreg' (este archivo), 'beto' (tools/etapa4_beto.py), 'llm_groq' (tools/etapa4_llm.py).

Uso (desde la raíz del repo, entorno .venv):
  .venv/Scripts/python tools/etapa4_tstr.py                                  # sanity, reglas y ctgan
  .venv/Scripts/python tools/etapa4_tstr.py --test data/reales_anon/<real>.csv  # TSTR, reglas y ctgan

Contrato de columnas (train y test): descripcion, monto, signo, cuenta_tipo, categoria_n1.
Entrada ÚNICA de los tres brazos (misma cadena): "[CUENTA=<cuenta_tipo>] [SIGNO=<signo>] [MONTO=<bin_log>] <descripcion>",
con monto en bins log10 de media década (COP de promedio 2025; el test real se deflacta por IPC si trae 'fecha').
Test real de WP4 (pre-registro 05 v1.3): además, columnas de análisis (peso_muestreo, estrato_muestreo, voluntario_id,
unica_por_descripcion, doble_anotacion, subgrupo_reverso, ...), NUNCA features.
Métrica principal: F1-macro SIN ponderar con regla de soporte. IC principal (D-M7): bootstrap por fila estratificado por
estrato_muestreo; sensibilidad: bootstrap por grupo de extractos (voluntario_id). Secundaria (D-M6): exactitud ponderada
(Hájek) con peso_muestreo y su sensibilidad con pesos recortados al P95. Sensibilidades (a)-(d) del §4 en metricas.json.
Predicciones por ítem del real -> data/_privado/tstr/ (ignorado por git). --ic {ambos,fila,conglomerado}.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

RAIZ = Path(__file__).resolve().parents[1]
SEMILLA = 42
TAXONOMIA = Path("docs/taxonomia/taxonomia_gastos_colombia_v1.json")
VERSION_TAXONOMIA = "1.1.0"
FUENTES = {
    "reglas": Path("outputs/sintetico_reglas/sintetico_reglas_con_texto_v1.csv.gz"),
    "ctgan": Path("outputs/ctgan/sintetico_v1_con_texto.csv.gz"),
    "reglas_original": Path("outputs/sintetico_reglas/transacciones.csv.gz"),
}
FUENTES_DEFECTO = ["reglas", "ctgan"]
NOMBRE_FUENTE = {"reglas": "protocolo (reglas)", "ctgan": "protocolo (CTGAN)"}
SALIDA = Path("outputs/tstr")
TARGET = "categoria_n1"
SOPORTE_MIN = 10
CLASE_RESIDUAL = "otros"
FRAC_TEST_SANITY = 0.20
N_BOOTSTRAP = 1000
ETIQUETA_TEXTO = "texto"   # fuente_etiqueta de las filas cuya etiqueta se infiere del texto
COLUMNAS_REQUERIDAS = ["descripcion", "monto", "signo", "cuenta_tipo", TARGET]
COLUMNAS_CONGLOMERADO = ["voluntario_id", "perfil_id"]
# Esquema EXACTO de salida de WP4 (real anotado). En TSTR se verifica y lo que falte queda en metricas.json.
COLUMNAS_WP4 = ["descripcion", "monto", "fecha", "signo", "cuenta_tipo", TARGET, "fuente_etiqueta", "voluntario_id"]
N_COMPARABLE = 20_000      # tamaño de train de BETO; LogReg@N_COMPARABLE usa EXACTAMENTE las mismas filas
GZIP = {"method": "gzip", "mtime": 0}


# --------------------------------------------------------------------------- utilidades
def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def sha256_texto(df: pd.DataFrame) -> str:
    """Huella del contenido (descripcion, etiqueta) de una tabla, independiente del índice."""
    h = pd.util.hash_pandas_object(df[["descripcion", TARGET]].astype(str), index=False).to_numpy()
    return hashlib.sha256(h.tobytes()).hexdigest()


def submuestra(train: pd.DataFrame, n: int | None, semilla: int = SEMILLA) -> pd.DataFrame:
    """Submuestra estratificada por categoria_n1, determinista; la comparten LogReg@N y BETO (mismas filas).
    Con n None o n >= len(train) devuelve todo."""
    if n is None or n >= len(train):
        return train.reset_index(drop=True)
    sub, _ = train_test_split(train, train_size=n, stratify=train[TARGET], random_state=semilla)
    return sub.reset_index(drop=True)


def cargar_taxonomia() -> tuple[list[str], str]:
    ruta = RAIZ / TAXONOMIA
    tax = json.loads(ruta.read_text(encoding="utf-8"))
    version = tax["metadata"]["version"]
    if version != VERSION_TAXONOMIA:
        sys.exit(f"Taxonomía en versión {version}; WP8 exige la congelada {VERSION_TAXONOMIA}.")
    clases = [c["id"] for c in tax["categorias_nivel_1"]]
    assert len(clases) == 16 and CLASE_RESIDUAL in clases
    return clases, sha256(ruta)


def cargar_tabla(ruta_rel: Path, clases: list[str], rol: str) -> pd.DataFrame:
    """Carga train o test y valida el contrato. Si hay columna 'capa' (generador por
    reglas), conserva solo la capa 'emitida' (universo de extracto, D15)."""
    ruta = RAIZ / ruta_rel
    if not ruta.exists():
        sys.exit(f"[{rol}] no existe {ruta_rel}. Para las fuentes con texto corre antes tools/etapa3b_texto.py.")
    df = pd.read_csv(ruta, low_memory=False)
    if "capa" in df.columns:
        df = df[df["capa"] == "emitida"].copy()
    faltan = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltan:
        sys.exit(f"[{rol}] {ruta_rel} no cumple el contrato: faltan {faltan}.")
    fuera = sorted(set(df[TARGET].dropna()) - set(clases))
    if fuera:
        sys.exit(f"[{rol}] etiquetas fuera de la taxonomía {VERSION_TAXONOMIA}: {fuera}")
    n0 = len(df)
    df = df.dropna(subset=["descripcion", TARGET]).reset_index(drop=True)
    if len(df) < n0:
        print(f"[{rol}] descartadas {n0 - len(df)} filas sin descripcion/etiqueta")
    return df


# --------------------------------------------------------------------------- entrada única de los tres brazos
# Serialización canónica (misma cadena para TF-IDF, BETO y el prompt del LLM). Solo observables de extracto:
# cuenta_tipo, signo, monto y descripcion; nunca columnas de anotación.
FORMATO_ENTRADA = "[CUENTA=<cuenta_tipo>] [SIGNO=<signo>] [MONTO=<bin_log>] <descripcion>"
VERSION_ENTRADA = "serializacion_v1"
# Bins log10 de media década en COP de promedio 2025, fijados a priori (no se ajustan con train ni test).
BORDES_MONTO = [10 ** (k / 2) for k in range(6, 15)]            # 1e3, 3,16e3, 1e4, ..., 1e7
ETIQUETAS_MONTO = ["<1K", "1K-3K", "3K-10K", "10K-30K", "30K-100K", "100K-300K", "300K-1M", "1M-3M", "3M-10M", ">=10M"]
IPC = Path("outputs/ipc/ipc_total_nacional.csv")              # serie DANE (pública), índice total nacional
MES_BASE_IPC = "2025"                                        # el sintético está en pesos de promedio 2025


def bin_monto(monto) -> np.ndarray:
    m = np.abs(pd.to_numeric(pd.Series(monto), errors="coerce").to_numpy(dtype=float))
    idx = np.searchsorted(BORDES_MONTO, m, side="right")
    out = np.array(ETIQUETAS_MONTO, dtype=object)[np.clip(idx, 0, len(ETIQUETAS_MONTO) - 1)]
    out[np.isnan(m)] = "NA"
    return out


def serializar(df: pd.DataFrame) -> pd.Series:
    """'[CUENTA=banco] [SIGNO=-] [MONTO=10K-30K] COMPRA EN EXITO ...'. Entrada idéntica para los tres brazos."""
    cuenta = df["cuenta_tipo"].astype(str).to_numpy(dtype=object)
    signo = df["signo"].astype(str).to_numpy(dtype=object)
    bins = bin_monto(df["monto"])
    desc = df["descripcion"].astype(str).to_numpy(dtype=object)
    return pd.Series([f"[CUENTA={c}] [SIGNO={s}] [MONTO={b}] {d}" for c, s, b, d in zip(cuenta, signo, bins, desc)],
                     index=df.index)


def texto_entrada(df: pd.DataFrame) -> pd.Series:
    """Entrada de TODOS los brazos (alias histórico): la serialización canónica."""
    return serializar(df)


def deflactar_test_a_2025(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """El real de WP4 viene en pesos corrientes de su mes; el sintético, en pesos de promedio 2025. Se lleva el monto
    del test a precios de promedio 2025 con el IPC total nacional del mes de la transacción (dato público, no
    calibra nada con el test). Sin columna 'fecha' no se deflacta y se avisa."""
    if "fecha" not in df.columns:
        print("[test] AVISO: sin columna 'fecha'; el monto real NO se deflacta a pesos de promedio 2025")
        return df, {"deflactado": False, "motivo": "sin columna fecha"}
    ipc = pd.read_csv(RAIZ / IPC, dtype={"mes": str, "division": str})
    ipc = ipc[ipc["division"] == "00"].set_index("mes")["indice"]
    base_ipc = ipc[ipc.index.str.startswith(MES_BASE_IPC)].mean()
    mes = pd.to_datetime(df["fecha"], errors="coerce").dt.strftime("%Y-%m")
    factor = base_ipc / mes.map(ipc)
    if factor.isna().any():
        faltan = sorted(set(mes[factor.isna()].dropna()))
        sys.exit(f"[test] meses sin IPC en {IPC}: {faltan[:5]} (actualiza la serie o revisa 'fecha')")
    out = df.copy()
    out["monto"] = pd.to_numeric(out["monto"], errors="coerce") * factor.to_numpy()
    return out, {"deflactado": True, "base": f"promedio {MES_BASE_IPC}", "ipc": IPC.as_posix(),
                 "factor_min": float(factor.min()), "factor_max": float(factor.max())}


# --------------------------------------------------------------------------- diseño del test real (D-M6, D-M7)
# Columnas de análisis del archivo de WP4 (pre-registro 05 v1.3 §7). NINGUNA es feature: serializar() solo lee
# cuenta_tipo, signo, monto y descripcion.
COLUMNAS_ANALISIS_WP4 = ["item_id", "tx_id", "categoria_n2", "medio_pago", "formalidad_comercio", "canal_p2p",
                         "peso_muestreo", "estrato_muestreo", "doble_anotacion", "origen_etiqueta", "caso_convencion",
                         "subgrupo_reverso", "unica_por_descripcion"]
MODOS_IC = ("ambos", "fila", "conglomerado")
P_RECORTE_PESOS = 95                 # sensibilidad (c): pesos recortados al percentil 95 y renormalizados
UMBRAL_ALERTA_PESOS = 0.05           # alerta si la exactitud ponderada cambia > 5 puntos con el recorte
PRIVADO_TSTR = Path("data/_privado/tstr")   # predicciones por ítem del test REAL (data/ está ignorado por git)


@dataclass
class Diseno:
    """Información de diseño del test para el IC y las métricas ponderadas (nunca entra al clasificador)."""
    estratos: np.ndarray | None = None
    grupos: np.ndarray | None = None
    pesos: np.ndarray | None = None
    col_grupo: str | None = None

    def sub(self, m: np.ndarray) -> "Diseno":
        return Diseno(*(x[m] if x is not None else None for x in (self.estratos, self.grupos, self.pesos)),
                      self.col_grupo)


def diseno_desde(test: pd.DataFrame, modo: str) -> Diseno:
    if modo == "sanity":
        return Diseno()
    est = test["estrato_muestreo"].astype(str).to_numpy() if "estrato_muestreo" in test.columns else None
    col = next((c for c in COLUMNAS_CONGLOMERADO if c in test.columns), None)
    grp = test[col].astype(str).to_numpy() if col else None
    w = None
    if "peso_muestreo" in test.columns:
        w = pd.to_numeric(test["peso_muestreo"], errors="coerce").to_numpy(dtype=float)
        if np.isnan(w).any() or (w <= 0).any():
            sys.exit("[test] peso_muestreo vacío, no numérico o <= 0 en alguna fila")
    if est is None:
        print("[test] AVISO: sin 'estrato_muestreo'; el IC principal es bootstrap por fila SIN estratificar")
    return Diseno(est, grp, w, col)


# --------------------------------------------------------------------------- métricas
def aplicar_regla_soporte(y_true: np.ndarray, y_pred: np.ndarray, clases: list[str]):
    """Clases con soporte < SOPORTE_MIN en el TEST (filas de la muestra, sin ponderar) se recodifican a 'otros' en
    y_true y en y_pred antes de calcular el F1-macro. Devuelve (y_true', y_pred', etiquetas evaluadas, fusionadas)."""
    soporte = pd.Series(y_true).value_counts()
    fusionadas = sorted(
        c for c in clases if c != CLASE_RESIDUAL and soporte.get(c, 0) < SOPORTE_MIN
    )
    mapa = {c: CLASE_RESIDUAL for c in fusionadas}
    yt = np.array([mapa.get(v, v) for v in y_true])
    yp = np.array([mapa.get(v, v) for v in y_pred])
    etiquetas = [c for c in clases if c not in fusionadas and (yt == c).any()]
    return yt, yp, etiquetas, fusionadas


def f1_macro_regla(y_true, y_pred, clases) -> float:
    """Estimador puntual: la regla de soporte se decide sobre la muestra que se evalúa."""
    yt, yp, etiquetas, _ = aplicar_regla_soporte(y_true, y_pred, clases)
    return f1_score(yt, yp, labels=etiquetas, average="macro", zero_division=0)


def regla_fija(y_true, clases) -> tuple[dict, list[str]]:
    """Mapa de fusión y clases evaluadas decididos UNA vez sobre la muestra observada (corrección del 26-nov-2026).
    El bootstrap re-evalúa el MISMO estimando: no vuelve a decidir qué clases entran en cada réplica."""
    _, _, etiquetas, fusionadas = aplicar_regla_soporte(np.asarray(y_true), np.asarray(y_true), clases)
    return {c: CLASE_RESIDUAL for c in fusionadas}, etiquetas


def f1_macro_fijo(y_true, y_pred, mapa: dict, etiquetas: list[str]) -> float:
    """F1-macro con la regla de soporte FIJA. Una clase fija ausente de la réplica (rarísimo con soporte >= 10) no
    entra en el promedio de esa réplica."""
    yt = np.array([mapa.get(v, v) for v in y_true])
    yp = np.array([mapa.get(v, v) for v in y_pred])
    pres = [e for e in etiquetas if (yt == e).any()]
    return f1_score(yt, yp, labels=pres, average="macro", zero_division=0)


def exactitud_ponderada(y_true, y_pred, pesos) -> float:
    """Estimador de Hájek: Σ w·1[y = ŷ] / Σ w."""
    w = np.asarray(pesos, dtype=float)
    return float(np.sum(w * (np.asarray(y_true) == np.asarray(y_pred))) / np.sum(w))


def n_efectivo_kish(pesos) -> float:
    w = np.asarray(pesos, dtype=float)
    return float(w.sum() ** 2 / np.sum(w ** 2))


def _indices_bootstrap(n: int, grupos=None, n_rep: int = N_BOOTSTRAP, semilla: int = SEMILLA, estratos=None):
    """Réplicas de índices.
    * grupos  -> por conglomerado (grupo de extractos completo).
    * estratos -> por fila, estratificado: dentro de cada estrato se remuestrean n_h filas con reemplazo (D-M7).
    * ninguno -> por fila simple (sanity)."""
    rng = np.random.default_rng(semilla)
    if grupos is not None:
        grupos = np.asarray(grupos)
        unicos = np.unique(grupos)
        por_grupo = {g: np.flatnonzero(grupos == g) for g in unicos}
        for _ in range(n_rep):
            sel = rng.choice(unicos, size=len(unicos), replace=True)
            yield np.concatenate([por_grupo[g] for g in sel])
    elif estratos is not None:
        estratos = np.asarray(estratos)
        por_estrato = [np.flatnonzero(estratos == h) for h in np.unique(estratos)]
        for _ in range(n_rep):
            yield np.concatenate([idx[rng.integers(0, len(idx), len(idx))] for idx in por_estrato])
    else:
        for _ in range(n_rep):
            yield rng.integers(0, n, n)


def _ic_boot(estadistico, n: int, grupos=None, estratos=None, n_rep=N_BOOTSTRAP, semilla=SEMILLA) -> list[float]:
    vals = [estadistico(i) for i in _indices_bootstrap(n, grupos, n_rep, semilla, estratos)]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def bootstrap_ic(y_true, y_pred, clases, grupos=None, n=N_BOOTSTRAP, semilla=SEMILLA, estratos=None):
    """IC95 percentil del F1-macro con la regla de soporte fija en la muestra observada."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    mapa, etq = regla_fija(y_true, clases)
    lo, hi = _ic_boot(lambda i: f1_macro_fijo(y_true[i], y_pred[i], mapa, etq), len(y_true), grupos, estratos, n, semilla)
    return lo, hi


def bootstrap_delta(y_true, pred_a, pred_b, clases, grupos=None, n=N_BOOTSTRAP, semilla=SEMILLA, estratos=None):
    """Δ = F1(b) − F1(a) con bootstrap PAREADO (mismas réplicas del mismo test para ambos brazos) y la regla de
    soporte fija en el test observado."""
    y_true, pred_a, pred_b = map(np.asarray, (y_true, pred_a, pred_b))
    mapa, etq = regla_fija(y_true, clases)
    d = f1_macro_fijo(y_true, pred_b, mapa, etq) - f1_macro_fijo(y_true, pred_a, mapa, etq)
    lo, hi = _ic_boot(lambda i: f1_macro_fijo(y_true[i], pred_b[i], mapa, etq) - f1_macro_fijo(y_true[i], pred_a[i], mapa, etq),
                      len(y_true), grupos, estratos, n, semilla)
    return float(d), lo, hi


def ic_sensibilidad(estadistico, theta: float, n: int, estratos=None, n_rep=N_BOOTSTRAP, semilla=SEMILLA,
                    jackknife: bool = True) -> dict:
    """Sensibilidad del IC principal (mismas réplicas): percentil, básico (2θ − q) y BCa (sesgo z0 + aceleración por
    jackknife de filas; aproximación con remuestreo estratificado). También la media del bootstrap y su sesgo."""
    from statistics import NormalDist
    nd = NormalDist()
    vals = np.array([estadistico(i) for i in _indices_bootstrap(n, None, n_rep, semilla, estratos)])
    q_lo, q_hi = np.percentile(vals, [2.5, 97.5])
    out = {"percentil": [float(q_lo), float(q_hi)], "basico": [float(2 * theta - q_hi), float(2 * theta - q_lo)],
           "media_bootstrap": float(vals.mean()), "sesgo_bootstrap": float(vals.mean() - theta),
           "prop_replicas_bajo_el_punto": float((vals < theta).mean())}
    if jackknife:
        p0 = (vals < theta).mean() + 0.5 * (vals == theta).mean()
        p0 = min(max(p0, 1 / (2 * n_rep)), 1 - 1 / (2 * n_rep))
        z0 = nd.inv_cdf(p0)
        jk = np.array([estadistico(np.delete(np.arange(n), i)) for i in range(n)])
        dif = jk.mean() - jk
        den = 6 * (np.sum(dif ** 2) ** 1.5)
        a = float(np.sum(dif ** 3) / den) if den > 0 else 0.0
        alfas = [nd.cdf(z0 + (z0 + z) / (1 - a * (z0 + z))) for z in (nd.inv_cdf(0.025), nd.inv_cdf(0.975))]
        out["bca"] = [float(np.percentile(vals, 100 * alfas[0])), float(np.percentile(vals, 100 * alfas[1]))]
        out["bca_z0"], out["bca_aceleracion"] = float(z0), a
    return out


def evaluar(y_true, y_pred, clases, diseno: Diseno | None = None, ic: str = "ambos", sens_ic: bool = False) -> dict:
    """Métrica principal: F1-macro SIN ponderar con regla de soporte. IC principal: bootstrap por fila (estratificado
    por estrato_muestreo si existe); sensibilidad: bootstrap por grupo de extractos (D-M7). Si hay pesos: exactitud
    ponderada (Hájek) con su IC y la sensibilidad de pesos recortados al P95 (D-M6, pre-registro §4.2)."""
    d = diseno or Diseno()
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    n = len(y_true)
    yt, yp, etiquetas, fusionadas = aplicar_regla_soporte(y_true, y_pred, clases)
    p, r, f, s = precision_recall_fscore_support(yt, yp, labels=etiquetas, zero_division=0)
    por_clase = pd.DataFrame({"clase": etiquetas, "precision": p, "recall": r, "f1": f, "soporte": s})
    presentes = [c for c in clases if (y_true == c).any()]
    if len(etiquetas) < 2:
        print(f"  AVISO: solo {len(etiquetas)} clase(s) con soporte >= {SOPORTE_MIN}; el F1-macro no es interpretable")

    mapa, etq_fijas = regla_fija(y_true, clases)
    f1 = lambda i: f1_macro_fijo(y_true[i], y_pred[i], mapa, etq_fijas)  # noqa: E731
    usa_conglomerado_principal = ic == "conglomerado" and d.grupos is not None
    tipo_principal = ("conglomerado" if usa_conglomerado_principal
                      else "fila_estratificado" if d.estratos is not None else "fila")
    res = {
        "advertencia": (f"solo {len(etiquetas)} clase(s) evaluable(s): F1-macro no interpretable" if len(etiquetas) < 2 else None),
        "f1_macro_regla_soporte": float(f.mean()),
        "ic95_bootstrap": _ic_boot(f1, n, grupos=d.grupos if usa_conglomerado_principal else None,
                                   estratos=None if usa_conglomerado_principal else d.estratos),
        "ic_principal": tipo_principal,
        "ic95_conglomerado": (_ic_boot(f1, n, grupos=d.grupos) if ic == "ambos" and d.grupos is not None else None),
        "n_grupos": int(len(np.unique(d.grupos))) if d.grupos is not None else None,
        "f1_macro_sin_regla": float(f1_score(y_true, y_pred, labels=presentes, average="macro", zero_division=0)),
        "accuracy": float((y_true == y_pred).mean()),
        "n_test": int(n),
        "clases_evaluadas": len(etiquetas),
        "clases_fusionadas_a_otros": fusionadas,
        "_por_clase": por_clase,
        "regla_soporte_en_bootstrap": "fija en la muestra observada",
    }
    if sens_ic:
        est = None if usa_conglomerado_principal else d.estratos
        res["ic_sensibilidad"] = ic_sensibilidad(f1, res["f1_macro_regla_soporte"], n, estratos=est)
        res["ic95_regla_recalculada_por_replica"] = _ic_boot(
            lambda i: f1_macro_regla(y_true[i], y_pred[i], clases), n, estratos=est)   # IC de la 1.ª corrida oficial
    if d.pesos is not None:
        w = d.pesos
        p95 = float(np.percentile(w, P_RECORTE_PESOS))
        wr = np.minimum(w, p95)                      # recorte al P95; Hájek renormaliza al dividir por Σ w
        acc_w, acc_r = exactitud_ponderada(y_true, y_pred, w), exactitud_ponderada(y_true, y_pred, wr)
        est = None if usa_conglomerado_principal else d.estratos
        grp = d.grupos if usa_conglomerado_principal else None
        res["exactitud_ponderada"] = {
            "valor": acc_w,
            "ic95_bootstrap": _ic_boot(lambda i: exactitud_ponderada(y_true[i], y_pred[i], w[i]), n, grp, est),
            "n_efectivo_kish": n_efectivo_kish(w), "suma_pesos": float(w.sum()),
            "recorte_p95": {"p95": p95, "valor": acc_r,
                            "ic95_bootstrap": _ic_boot(lambda i: exactitud_ponderada(y_true[i], y_pred[i], wr[i]), n, grp, est),
                            "diferencia": acc_w - acc_r,
                            "alerta_depende_de_pocos_descriptores": bool(abs(acc_w - acc_r) > UMBRAL_ALERTA_PESOS)},
        }
    return res


def prevalencias(y_true, pesos, clases) -> pd.DataFrame:
    """Prevalencia de cada clase real, sin ponderar y ponderada (D-M6); antes de la regla de soporte."""
    y = pd.Series(np.asarray(y_true))
    out = pd.DataFrame({"clase": clases, "n": [int((y == c).sum()) for c in clases]})
    out["pct_sin_ponderar"] = out["n"] / len(y)
    if pesos is not None:
        w = pd.Series(np.asarray(pesos, dtype=float))
        out["pct_ponderado"] = [float(w[y == c].sum() / w.sum()) for c in clases]
    return out


# --------------------------------------------------------------------------- brazos
@dataclass
class Brazo:
    """Un clasificador enchufable: ``ajustar_predecir(train, test) -> (y_pred, meta)``.
    Recibe las tablas completas (contrato de columnas); debe usar solo las columnas de entrada permitidas."""
    nombre: str                     # carpeta de salida y llave en la tabla (logreg, beto, groq_llama33_70b)
    descripcion: str
    ajustar_predecir: Callable[[pd.DataFrame, pd.DataFrame], tuple[np.ndarray, dict]]


def brazo_logreg() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), lowercase=True,
            strip_accents="unicode", sublinear_tf=True, min_df=2, dtype=np.float32,
        )),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=SEMILLA)),
    ])


def brazo_logreg_n(n: int | None = None) -> Brazo:
    """LogReg sobre todo el train (n None) o sobre la submuestra de n filas que usa BETO."""
    def ajustar_predecir(train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, dict]:
        sub = submuestra(train, n)
        modelo = brazo_logreg()
        modelo.fit(texto_entrada(sub), sub[TARGET].to_numpy())
        return modelo.predict(texto_entrada(test)), {
            "n_train_efectivo": len(sub), "n_vocabulario": int(len(modelo.named_steps["tfidf"].vocabulary_)),
            "submuestra": None if n is None else f"estratificada {TARGET}, n={n}, semilla {SEMILLA} (mismas filas que BETO)"}
    return Brazo("logreg" if n is None else f"logreg_n{n}", "logreg_tfidf_char_wb_3_5" + ("" if n is None else f"_n{n}"),
                 ajustar_predecir)


BRAZO_LOGREG = brazo_logreg_n(None)


def brazo_linea_base(tipo: str) -> Brazo:
    """Líneas base de contexto (no entran a la ablación): 'mayoritaria' = la clase más frecuente del sintético de
    entrenamiento; 'estratificada' = predicción aleatoria con la distribución de clases del sintético (semilla fija).
    No leen ninguna columna del test salvo su número de filas."""
    def ajustar_predecir(train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, dict]:
        frec = train[TARGET].value_counts(normalize=True).sort_index()
        if tipo == "mayoritaria":
            clase = frec.idxmax()
            return np.full(len(test), clase, dtype=object), {"clase_mayoritaria": clase, "n_train_efectivo": len(train)}
        rng = np.random.default_rng(SEMILLA)
        pred = rng.choice(frec.index.to_numpy(dtype=object), size=len(test), p=frec.to_numpy())
        return pred, {"distribucion": "frecuencias de categoria_n1 del sintético", "semilla": SEMILLA,
                      "n_train_efectivo": len(train)}
    return Brazo(f"base_{tipo}", f"linea_base_{tipo}", ajustar_predecir)


# --------------------------------------------------------------------------- una corrida
def ruta_predicciones(modo: str, fuente: str, brazo: str) -> Path:
    """Sanity (sintético): outputs/tstr/. TSTR (real): data/_privado/tstr/, ignorado por git; solo etiquetas, pesos,
    estratos y seudónimos de grupo, nunca texto."""
    base_dir = PRIVADO_TSTR if modo == "tstr" else SALIDA / modo
    return RAIZ / base_dir / fuente / brazo / "predicciones.csv.gz"


def _col(test: pd.DataFrame, c: str) -> np.ndarray | None:
    return test[c].astype(str).str.strip().str.lower().to_numpy() if c in test.columns else None


def sensibilidades(y_true, y_pred, test: pd.DataFrame, clases, d: Diseno, principal: dict) -> dict:
    """Sensibilidades pre-registradas (pre-registro 05 v1.3 §4). Cada F1 recalcula la regla de soporte en su subconjunto
    y lleva IC por el mismo bootstrap principal (fila estratificado)."""
    out = {}

    def f1_sub(m, nota):
        r = evaluar(y_true[m], y_pred[m], clases, d.sub(m), ic="fila")
        r.pop("_por_clase")
        return {"n": int(m.sum()), "f1_macro_regla_soporte": r["f1_macro_regla_soporte"], "ic95_bootstrap": r["ic95_bootstrap"],
                "clases_evaluadas": r["clases_evaluadas"], "clases_fusionadas_a_otros": r["clases_fusionadas_a_otros"],
                "fusiona_ademas_de_la_principal": sorted(set(r["clases_fusionadas_a_otros"])
                                                        - set(principal["clases_fusionadas_a_otros"])), "nota": nota}

    u = _col(test, "unica_por_descripcion")
    out["a_unica_por_descripcion"] = (f1_sub(u == "si", "una fila por descripción (§4.3)") if u is not None
                                      else {"aplica": False, "nota": "el test no trae unica_por_descripcion"})
    dob = _col(test, "doble_anotacion")
    if dob is None:
        out["b_solo_doble_anotacion"] = {"aplica": False, "nota": "el test no trae doble_anotacion"}
    elif (dob == "si").all():
        out["b_solo_doble_anotacion"] = {"aplica": False, "nota": "todos los ítems tienen doble anotación: igual a la principal"}
    else:
        out["b_solo_doble_anotacion"] = f1_sub(dob == "si", "solo ítems con doble anotación (§4.5)")
    ew = principal.get("exactitud_ponderada")
    out["c_exactitud_ponderada_recorte_p95"] = (
        {k: ew["recorte_p95"][k] for k in ("p95", "valor", "ic95_bootstrap", "diferencia",
                                           "alerta_depende_de_pocos_descriptores")} | {"sin_recorte": ew["valor"]}
        if ew else {"aplica": False, "nota": "el test no trae peso_muestreo"})
    rev = _col(test, "subgrupo_reverso")
    if rev is None:
        out["d_subgrupo_reverso"] = {"aplica": False, "nota": "el test no trae subgrupo_reverso"}
    else:
        m = rev == "si"
        pares = pd.Series([f"{t} -> {p}" for t, p in zip(y_true[m], y_pred[m])]).value_counts()
        out["d_subgrupo_reverso"] = {
            "n": int(m.sum()), "aciertos": int((y_true[m] == y_pred[m]).sum()),
            "exactitud": float((y_true[m] == y_pred[m]).mean()) if m.any() else None,
            "real_a_predicho": {k: int(v) for k, v in pares.items()},
            "nota": "reversos y devoluciones de tarjeta: incluidos en la métrica principal, reportados aparte (§4.6)"}
    out["e_kappa_sin_casos_convencion"] = {"aplica": False, "nota": "lo calcula tools/acuerdo_wp4.py, no WP8"}
    return out


def correr(fuente: str, ruta_train: Path, ruta_test: Path | None, clases: list[str], sha_tax: str,
           brazo: Brazo = BRAZO_LOGREG, recorte_test: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
           ic: str = "ambos") -> dict:
    """``recorte_test`` (opcional, brazo LLM): submuestra declarada del test por costo de API; se registra n_test.
    ``ic`` (TSTR): 'ambos' = principal por fila estratificado + sensibilidad por grupo (D-M7, por defecto);
    'fila' = solo el principal; 'conglomerado' = el grupo como principal (arnés anterior)."""
    if ic not in MODOS_IC:
        raise ValueError(f"ic debe ser uno de {MODOS_IC}")
    train = cargar_tabla(ruta_train, clases, f"train:{fuente}")
    deflactor = {"deflactado": False, "motivo": "sanity: test sintético, ya en pesos de promedio 2025"}
    faltan_wp4 = None
    if ruta_test is None:
        modo = "sanity"
        train, test = train_test_split(train, test_size=FRAC_TEST_SANITY, stratify=train[TARGET],
                                       random_state=SEMILLA)
        print(f"[{fuente}] MODO SANITY CHECK — NO REPORTABLE (holdout del propio sintético)")
    else:
        modo = "tstr"
        test = cargar_tabla(ruta_test, clases, "test")
        faltan_wp4 = [c for c in COLUMNAS_WP4 if c not in test.columns]
        if faltan_wp4:
            print(f"[test] AVISO: el test no trae {faltan_wp4} del esquema WP4 (se omite lo que dependa de ellas)")
        test, deflactor = deflactar_test_a_2025(test)
        print(f"[{fuente}] MODO TSTR — train: todo {ruta_train} | test real: {ruta_test}")

    n_test_completo = len(test)
    if recorte_test is not None:
        test = recorte_test(test).reset_index(drop=True)
        print(f"[{fuente}] test recortado a {len(test):,} de {n_test_completo:,} filas (costo de API, declarado)")
    test = test.reset_index(drop=True)
    d = diseno_desde(test, modo)
    fe = test["fuente_etiqueta"].astype(str).to_numpy() if "fuente_etiqueta" in test.columns else None

    t0 = datetime.now(timezone.utc)
    y_pred, meta = brazo.ajustar_predecir(train, test)
    y_pred = np.asarray(y_pred, dtype=object)
    segundos = (datetime.now(timezone.utc) - t0).total_seconds()
    y_true = test[TARGET].to_numpy(dtype=object)

    res = evaluar(y_true, y_pred, clases, d, ic=ic if modo == "tstr" else "fila", sens_ic=modo == "tstr")
    por_clase = res.pop("_por_clase")
    if fe is not None:
        m = fe == ETIQUETA_TEXTO
        if m.all():
            res["solo_etiqueta_por_texto"] = {"aplica": False, "nota": (
                "todas las filas son etiqueta-por-texto (R2: ningún propósito declarado); el corte no aporta")}
        else:
            sub = evaluar(y_true[m], y_pred[m], clases, d.sub(m), ic="fila")
            sub.pop("_por_clase")
            res["solo_etiqueta_por_texto"] = {k: sub[k] for k in (
                "f1_macro_regla_soporte", "ic95_bootstrap", "n_test", "clases_evaluadas", "clases_fusionadas_a_otros")}
        res["frac_test_etiqueta_por_declaracion"] = float((~m).mean())
    if modo == "tstr":
        res["sensibilidades"] = sensibilidades(y_true, y_pred, test, clases, d, res)

    destino = RAIZ / SALIDA / modo / fuente / brazo.nombre
    destino.mkdir(parents=True, exist_ok=True)
    por_clase.to_csv(destino / "por_clase.csv", index=False)
    extra = sorted(set(y_pred) - set(clases))           # p. ej. __fuera_de_enum__ del LLM: columna propia, no se pierde
    pd.DataFrame(confusion_matrix(y_true, y_pred, labels=clases + extra)[:len(clases)], index=clases,
                 columns=clases + extra).rename_axis("real\\pred").to_csv(destino / "matriz_confusion.csv")
    if modo == "tstr":
        prevalencias(y_true, d.pesos, clases).to_csv(destino / "prevalencias.csv", index=False)
    vacio = np.full(len(test), "", dtype=object)
    pred = pd.DataFrame({
        "y_true": y_true, "y_pred": y_pred,
        "grupo": d.grupos if d.grupos is not None else vacio,
        "estrato": d.estratos if d.estratos is not None else vacio,
        "peso": d.pesos if d.pesos is not None else np.nan,
        "fuente_etiqueta": fe if fe is not None else vacio,
        **{c: (_col(test, c) if c in test.columns else vacio)
           for c in ("unica_por_descripcion", "doble_anotacion", "subgrupo_reverso")},
    })
    rp = ruta_predicciones(modo, fuente, brazo.nombre)
    rp.parent.mkdir(parents=True, exist_ok=True)
    pred.to_csv(rp, index=False, compression=GZIP)

    metricas = {
        "modo": modo, "reportable": modo == "tstr", "fuente": fuente, "brazo": brazo.descripcion,
        **res,
        "bootstrap": {"n": N_BOOTSTRAP, "principal": res["ic_principal"],
                      "sensibilidad": ("conglomerado:" + d.col_grupo) if res.get("ic95_conglomerado") else None,
                      "estratos": int(len(np.unique(d.estratos))) if d.estratos is not None else None,
                      "alcance": ("incertidumbre de muestreo dentro de estos extractos, no generalización a nuevos "
                                  "titulares (D-M7)") if modo == "tstr" else "holdout sintético"},
        "segundos_entrenamiento_y_prediccion": round(segundos, 1),
        "n_train": int(meta.pop("n_train_efectivo", len(train))),
        "n_train_disponible": int(len(train)),
        "n_test_completo": int(n_test_completo),
        "contrato_wp4_faltan": faltan_wp4,
        "predicciones": (rp.relative_to(RAIZ).as_posix() if rp.is_relative_to(RAIZ) else str(rp)),
        "brazo_meta": meta,
        "entrada": {"version": VERSION_ENTRADA, "formato": FORMATO_ENTRADA, "bordes_monto_cop_2025": BORDES_MONTO,
                    "etiquetas_monto": ETIQUETAS_MONTO, "deflactor_test": deflactor},
        "semilla": SEMILLA, "soporte_min": SOPORTE_MIN,
        "train": {"ruta": ruta_train.as_posix(), "sha256": sha256(RAIZ / ruta_train)},
        "test": ({"ruta": ruta_test.as_posix(), "sha256": sha256(RAIZ / ruta_test)} if ruta_test
                 else {"split": f"estratificado {TARGET} {FRAC_TEST_SANITY}"}),
        "taxonomia": {"ruta": TAXONOMIA.as_posix(), "version": VERSION_TAXONOMIA, "sha256": sha_tax},
        "versiones": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                      "pandas": pd.__version__, "numpy": np.__version__},
        "plataforma": platform.platform(),
        "fecha_utc": t0.isoformat(timespec="seconds"),
    }
    (destino / "metricas.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")
    resumen = {k: metricas.get(k) for k in ("modo", "f1_macro_regla_soporte", "ic95_bootstrap", "ic95_conglomerado",
                                            "accuracy", "n_train", "n_test", "segundos_entrenamiento_y_prediccion")}
    if "exactitud_ponderada" in metricas:
        resumen["exactitud_ponderada"] = metricas["exactitud_ponderada"]["valor"]
    print(json.dumps(resumen, ensure_ascii=False))
    print(f"-> {destino.relative_to(RAIZ).as_posix() if destino.is_relative_to(RAIZ) else destino}")
    return metricas


# --------------------------------------------------------------------------- post hoc (no pre-registrado)
CLASE_FUSION_EXPL = "transferencias_p2p+ingreso"


# Todas las salidas del reporte se derivan de SALIDA EN TIEMPO DE LLAMADA: una prueba que redirige SALIDA a tmp_path
# redirige también estas (antes eran rutas fijas y una prueba sobrescribió outputs/tstr/tablas_informe.tex).
def ruta_exploratorio() -> Path:
    return RAIZ / SALIDA / "tstr" / "exploratorio_p2p_ingreso.json"


def ruta_hallazgo() -> Path:
    return RAIZ / SALIDA / "hallazgo_cruce_p2p_ingreso.json"


def ruta_tablas_tex() -> Path:
    return RAIZ / SALIDA / "tablas_informe.tex"


def _rel(p: Path) -> str:
    """Ruta para mostrar en el reporte: relativa a la raíz del repo si cae dentro."""
    try:
        return Path(p).resolve().relative_to(RAIZ.resolve()).as_posix()
    except ValueError:
        return Path(p).as_posix()
FAMILIAS_TEXTO = {"p2p_recibida_banco": "P2P recibida", "p2p_recibida_billetera": "P2P recibida",
                  "p2p_enviada_banco": "P2P enviada", "p2p_enviada_billetera": "P2P enviada",
                  "recarga_origen": "recarga: sale del banco", "recarga_destino": "recarga: entra a la billetera"}


def exploratorio_p2p_ingreso(clases: list[str]) -> list[dict]:
    """POST HOC, NO PRE-REGISTRADO: F1-macro de LogReg completo con transferencias_p2p e ingreso fusionadas en una sola
    clase, para dimensionar el choque de convenciones P2P/ingreso. Lee las predicciones por ítem SOLO en la máquina
    local (data/_privado/tstr/) y escribe agregados. La regla de soporte se fija sobre el test con la clase fusionada."""
    fusion = ("transferencias_p2p", "ingreso")
    c2 = [c for c in clases if c not in fusion] + [CLASE_FUSION_EXPL]
    mp = lambda a: np.array([CLASE_FUSION_EXPL if v in fusion else v for v in a], dtype=object)  # noqa: E731
    out = []
    for f in FUENTES_DEFECTO:
        rp = ruta_predicciones("tstr", f, "logreg")
        if not rp.exists():
            continue
        p = pd.read_csv(rp, keep_default_na=False)
        yt, yp = p["y_true"].to_numpy(dtype=object), p["y_pred"].to_numpy(dtype=object)
        est = p["estrato"].astype(str).to_numpy() if (p["estrato"].astype(str) != "").any() else None
        grp = p["grupo"].astype(str).to_numpy() if (p["grupo"].astype(str) != "").any() else None
        yt2, yp2 = mp(yt), mp(yp)
        mapa, etq = regla_fija(yt2, c2)
        f1f = lambda i: f1_macro_fijo(yt2[i], yp2[i], mapa, etq)  # noqa: E731
        out.append({"fuente": f, "brazo": "logreg", "f1_macro_original": f1_macro_regla(yt, yp, clases),
                    "f1_macro_fusionado": f1_macro_regla(yt2, yp2, c2),
                    "ic95_fila_estratificado": _ic_boot(f1f, len(yt2), estratos=est),
                    "ic95_grupo": _ic_boot(f1f, len(yt2), grupos=grp) if grp is not None else None,
                    "clases_evaluadas": len(etq), "clases_fusionadas_a_otros": sorted(mapa), "n_test": int(len(yt))})
    if out:
        ruta_exploratorio().write_text(json.dumps({
            "aviso": "POST HOC, NO PRE-REGISTRADO: solo dimensiona el choque de convenciones P2P/ingreso; no reemplaza la "
                     "métrica principal ni entra a la tabla principal.",
            "fusion": list(fusion), "bootstrap": {"n": N_BOOTSTRAP, "semilla": SEMILLA, "regla_soporte": "fija"},
            "resultados": out}, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def cuantificar_cruce_p2p() -> dict:
    """Hallazgo del protocolo, SOLO desde el sintético (ningún dato real): cómo se reparten las etiquetas dentro de las
    familias de texto de transferencia y recarga, y qué textos de billetera existen en salidas desde banco."""
    res = {"fuente_codigo": {
        "ingreso_p2p": "src/sdg/generador.py:607-632 (no asalariados: con prob. ingreso.p_p2p_otros = 0,6 el depósito usa "
                       "plantilla p2p_recibida_* y queda categoria_n1 = ingreso; consignación a billetera -> p2p_recibida_billetera)",
        "p2p_sin_proposito": "src/sdg/generador.py:634-655 (P2P recibida/enviada sin propósito -> transferencias_p2p)",
        "recargas": "src/sdg/generador.py:691-707 (recarga banco->billetera -> movimiento_propio; plantillas 'RECARGA {W}', "
                    "'TRANSFERENCIA A {W}', 'RECARGA DESDE {B}')",
        "capa_texto_ctgan": "src/sdg/texto.py:95 (ingreso_no_asalariado + canal_p2p -> p2p_recibida_*; ingreso + billetera -> "
                            "p2p_recibida_billetera)"}, "fuentes": {}}
    for f in FUENTES_DEFECTO:
        d = pd.read_csv(RAIZ / FUENTES[f], usecols=["tipo_evento", TARGET, "signo", "cuenta_tipo", "descripcion"])
        d["familia"] = d["tipo_evento"].map(FAMILIAS_TEXTO)
        t = pd.crosstab(d["familia"], d[TARGET])
        claves = ["ingreso", "transferencias_p2p", "movimiento_propio"]
        tabla = {fam: {**{k: int(t.loc[fam].get(k, 0)) for k in claves},
                       "otras_proposito_declarado": int(t.loc[fam].drop(labels=[k for k in claves if k in t.columns]).sum()),
                       "total": int(t.loc[fam].sum())} for fam in t.index}
        rec = d[d["familia"] == "P2P recibida"]
        up = d["descripcion"].astype(str).str.upper()
        banco_billetera = (d["signo"] == "-") & (d["cuenta_tipo"] == "banco") & up.str.contains(r"\bNEQUI\b|\bDAVIPLATA\b")
        res["fuentes"][f] = {
            "por_familia": tabla,
            "p2p_recibida_etiquetada_ingreso": float((rec[TARGET] == "ingreso").mean()),
            "salidas_banco_con_billetera_en_texto": {k: int(v) for k, v in d.loc[banco_billetera, TARGET].value_counts().items()},
            "token_LLAVE_aislado": int(up.str.contains(r"\bLLAVE\b").sum()),
            "token_LLAVE_dentro_de_TULLAVE": int(up.str.contains("TULLAVE").sum()),
        }
    ruta_hallazgo().write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--fuentes", nargs="+", default=FUENTES_DEFECTO,
                    help=f"Alias ({', '.join(FUENTES)}) o rutas relativas a la raíz.")
    ap.add_argument("--test", type=Path, default=None,
                    help="Real anotado de WP4. Si se omite: sanity check NO reportable.")
    ap.add_argument("--n-train", type=int, nargs="*", default=[0],
                    help=f"0 = train completo; N = submuestra de N filas (las mismas que BETO). "
                         f"Por defecto solo completo; '--n-train 0 {N_COMPARABLE}' corre ambas.")
    ap.add_argument("--ic", choices=MODOS_IC, default="ambos",
                    help="TSTR: 'ambos' (D-M7) = principal por fila estratificado + sensibilidad por grupo.")
    ap.add_argument("--lineas-base", action="store_true",
                    help="Agrega las líneas base de contexto (clase mayoritaria y aleatorio estratificado del sintético).")
    ap.add_argument("--exploratorio-p2p-ingreso", action="store_true",
                    help="POST HOC: F1 con P2P e ingreso fusionadas (lee data/_privado/ localmente) y cuantificación del "
                         "cruce en el sintético. No entrena; regenera el .md y las tablas LaTeX.")
    ap.add_argument("--solo-reporte", action="store_true",
                    help="No entrena ni lee el test: regenera docs/resultados_tstr.md y outputs/tstr/tablas_informe.tex "
                         "desde los metricas.json/ablacion.json existentes (el Δ pareado se recalcula si hay "
                         "predicciones privadas locales; misma semilla, mismos valores).")
    args = ap.parse_args()
    clases, sha_tax = cargar_taxonomia()
    if args.solo_reporte:
        escribir_resultados_md(clases)
        print(f"regenerados: {RESULTADOS_MD.as_posix()} y {_rel(ruta_tablas_tex())}")
        return
    if args.exploratorio_p2p_ingreso:
        cuantificar_cruce_p2p()
        r = exploratorio_p2p_ingreso(clases)
        print(json.dumps([{k: x[k] for k in ("fuente", "f1_macro_original", "f1_macro_fusionado",
                                             "ic95_fila_estratificado", "ic95_grupo")} for x in r], ensure_ascii=False))
        escribir_resultados_md(clases)
        return
    for f in args.fuentes:
        ruta = FUENTES.get(f, Path(f))
        nombre = f if f in FUENTES else ruta.name.split(".")[0]
        for n in args.n_train:
            correr(nombre, ruta, args.test, clases, sha_tax, brazo_logreg_n(n or None), ic=args.ic)
        if args.lineas_base:
            for tipo in ("mayoritaria", "estratificada"):
                correr(nombre, ruta, args.test, clases, sha_tax, brazo_linea_base(tipo), ic=args.ic)
    escribir_resultados_md(clases)


# --------------------------------------------------------------------------- reporte
RESULTADOS_MD = Path("docs/resultados_tstr.md")
LLM_SIN_REAL = ("brazo LLM no evaluado sobre el real por restricción de tratamiento de datos; humo sobre sintético en "
                "`outputs/tstr/sanity/<fuente>/llm_groq/`")
BRAZOS_TABLA = [
    ("logreg", "Baseline: LogReg + TF-IDF char 3-5 (train completo)"),
    (f"logreg_n{N_COMPARABLE}", f"Baseline: LogReg @{N_COMPARABLE // 1000}k (mismas filas que BETO)"),
    ("beto", "BETO fine-tuning"),
    ("llm_groq", "LLM vía Groq, prompting few-shot (modelo y desviación en Costo)"),
]
CAB = ("| Brazo | Fuente train | F1-macro (soporte ≥10) | IC95 | F1-macro solo etiqueta-por-texto | IC95 | "
       "n train | n test | fusionadas a otros |\n|---|---|---|---|---|---|---|---|---|")
CAB_TSTR = ("| Brazo | Fuente train | F1-macro (soporte ≥10) | IC95 principal (fila estrat.) | IC95 por grupo "
            "(sensibilidad) | Exactitud | Exactitud ponderada [IC95] | n train | n test | fusionadas a otros |\n"
            "|---|---|---|---|---|---|---|---|---|---|")
LINEAS_BASE = [("base_mayoritaria", "Clase mayoritaria del sintético"),
               ("base_estratificada", "Aleatorio estratificado (distribución del sintético, semilla 42)")]
CAB_IC = ("| Brazo | Fuente train | F1-macro | IC95 percentil (principal) | IC95 básico | IC95 BCa | media bootstrap "
          "(sesgo) | IC95 con la regla recalculada por réplica (1.ª corrida) |\n|---|---|---|---|---|---|---|---|")
CAB_BASE = ("| Línea base | Fuente train | F1-macro (soporte ≥10) | IC95 principal | Exactitud | Exactitud ponderada |\n"
            "|---|---|---|---|---|---|")
CAB_SENS = ("| Brazo | Fuente train | (a) F1 una fila por descripción [IC95] | (b) F1 solo doble anotación [IC95] | "
            "(c) Exactitud ponderada P95 (Δ = sin recorte − P95) | (d) Reversos: aciertos/n |\n|---|---|---|---|---|---|")


def _ic(v) -> str:
    return f"[{v[0]:.3f}, {v[1]:.3f}]" if v else "—"


def _fila_tstr(nombre: str, fuente: str, m: dict) -> str:
    ew = m.get("exactitud_ponderada")
    ew_txt = f"{ew['valor']:.3f} {_ic(ew['ic95_bootstrap'])}" if ew else "—"
    return (f"| {nombre} | {fuente} | {m['f1_macro_regla_soporte']:.3f} | {_ic(m['ic95_bootstrap'])} | "
            f"{_ic(m.get('ic95_conglomerado'))} | {m['accuracy']:.3f} | {ew_txt} | {m['n_train']:,} | {m['n_test']:,} | "
            f"{_fusionadas(m['clases_fusionadas_a_otros'])} |")


def _fila_ic(nombre: str, fuente: str, m: dict) -> str:
    s = m.get("ic_sensibilidad")
    if not s:
        return f"| {nombre} | {fuente} | {m['f1_macro_regla_soporte']:.3f} | {_ic(m['ic95_bootstrap'])} | — | — | — | — |"
    return (f"| {nombre} | {fuente} | {m['f1_macro_regla_soporte']:.3f} | {_ic(s['percentil'])} | {_ic(s['basico'])} | "
            f"{_ic(s.get('bca'))} | {s['media_bootstrap']:.3f} ({s['sesgo_bootstrap']:+.3f}) | "
            f"{_ic(m.get('ic95_regla_recalculada_por_replica'))} |")


def _fila_base(nombre: str, fuente: str, m: dict) -> str:
    ew = m.get("exactitud_ponderada")
    return (f"| {nombre} | {fuente} | {m['f1_macro_regla_soporte']:.3f} | {_ic(m['ic95_bootstrap'])} | "
            f"{m['accuracy']:.3f} | {ew['valor']:.3f} |" if ew else
            f"| {nombre} | {fuente} | {m['f1_macro_regla_soporte']:.3f} | {_ic(m['ic95_bootstrap'])} | {m['accuracy']:.3f} | — |")


def _fila_sens(nombre: str, fuente: str, m: dict) -> str:
    s = m.get("sensibilidades", {})

    def f1(k):
        x = s.get(k, {})
        if x.get("aplica") is False:
            return "no aplica"
        extra = x.get("fusiona_ademas_de_la_principal")
        return (f"{x['f1_macro_regla_soporte']:.3f} {_ic(x['ic95_bootstrap'])} (n={x['n']})"
                + (f"; fusiona además: {', '.join(extra)}" if extra else ""))
    c = s.get("c_exactitud_ponderada_recorte_p95", {})
    if c.get("aplica") is False:
        c_txt = "no aplica"
    elif abs(abs(c["diferencia"]) - UMBRAL_ALERTA_PESOS) < 0.0005:
        c_txt = (f"{c['valor']:.3f} (Δ {c['diferencia']:+.4f}: **en el umbral** de ±{UMBRAL_ALERTA_PESOS:.2f}; "
                 f"{'alerta' if c['alerta_depende_de_pocos_descriptores'] else 'sin alerta formal'})")
    else:
        c_txt = (f"{c['valor']:.3f} (Δ {c['diferencia']:+.3f}"
                 f"{'; ⚠ > 5 pts: depende de pocos descriptores' if c['alerta_depende_de_pocos_descriptores'] else ''})")
    dd = s.get("d_subgrupo_reverso", {})
    d_txt = "no aplica" if dd.get("aplica") is False else f"{dd['aciertos']}/{dd['n']}"
    return f"| {nombre} | {fuente} | {f1('a_unica_por_descripcion')} | {f1('b_solo_doble_anotacion')} | {c_txt} | {d_txt} |"


def _fila(nombre: str, fuente: str, m: dict) -> str:
    st = m.get("solo_etiqueta_por_texto")
    st_txt = (f"{st['f1_macro_regla_soporte']:.3f} | {_ic(st['ic95_bootstrap'])}" if st and st.get("aplica") is not False
              else "— | —")
    f1_txt = (f"{m['f1_macro_regla_soporte']:.3f} ⚠ no interpretable ({m['clases_evaluadas']} clase evaluable)"
              if m.get("advertencia") else f"{m['f1_macro_regla_soporte']:.3f}")
    return (f"| {nombre} | {fuente} | {f1_txt} | {_ic(m['ic95_bootstrap'])} | {st_txt} | "
            f"{m['n_train']:,} | {m['n_test']:,} | {_fusionadas(m['clases_fusionadas_a_otros'])} |")


def _fusionadas(lista: list[str]) -> str:
    if not lista:
        return "—"
    return ", ".join(lista) if len(lista) <= 4 else f"{len(lista)} clases (lista en metricas.json)"


def _ablacion(modo: str, corridas: dict, clases: list[str]) -> list[str]:
    """Δ CTGAN − reglas por brazo, bootstrap PAREADO sobre las predicciones guardadas (mismo test, mismas réplicas):
    principal por fila estratificado y sensibilidad por grupo de extractos (D-M7)."""
    filas, registro = [], []
    if modo != "tstr":
        return filas                 # en sanity cada fuente tiene su propio holdout: no hay Δ pareado
    for brazo, nombre in BRAZOS_TABLA:
        a, b = corridas.get((modo, "reglas", brazo)), corridas.get((modo, "ctgan", brazo))
        if not (a and b) or a["test"] != b["test"]:
            continue
        ra, rb = ruta_predicciones(modo, "reglas", brazo), ruta_predicciones(modo, "ctgan", brazo)
        if not (ra.exists() and rb.exists()):
            continue
        pa = pd.read_csv(ra, keep_default_na=False)
        pb = pd.read_csv(rb, keep_default_na=False)
        if len(pa) != len(pb) or not (pa["y_true"].to_numpy() == pb["y_true"].to_numpy()).all():
            continue
        yt, ya, yb = pa["y_true"].to_numpy(), pa["y_pred"].to_numpy(), pb["y_pred"].to_numpy()
        est = pa["estrato"].astype(str).to_numpy() if (pa["estrato"].astype(str) != "").any() else None
        grp = pa["grupo"].astype(str).to_numpy() if (pa["grupo"].astype(str) != "").any() else None
        d, lo, hi = bootstrap_delta(yt, ya, yb, clases, estratos=est)
        txt = f"| {nombre} | {d:+.3f} | [{lo:+.3f}, {hi:+.3f}] |"
        if grp is not None:
            _, lo2, hi2 = bootstrap_delta(yt, ya, yb, clases, grupos=grp)
            txt += f" [{lo2:+.3f}, {hi2:+.3f}] |"
        else:
            txt += " — |"
        filas.append(txt)
        registro.append({"brazo": brazo, "delta_f1_macro": d, "ic95_fila_estratificado": [lo, hi],
                         "ic95_grupo": [lo2, hi2] if grp is not None else None, "n_test": int(len(yt)),
                         "test": a["test"], "bootstrap": {"n": N_BOOTSTRAP, "semilla": SEMILLA}})
    ruta_abl = RAIZ / SALIDA / modo / "ablacion.json"
    if registro:
        ruta_abl.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    elif ruta_abl.exists():          # sin predicciones privadas en esta máquina: se lee el agregado ya calculado
        nombres = dict(BRAZOS_TABLA)
        for r in json.loads(ruta_abl.read_text(encoding="utf-8")):
            g = r.get("ic95_grupo")
            filas.append(f"| {nombres.get(r['brazo'], r['brazo'])} | {r['delta_f1_macro']:+.3f} | "
                         f"[{r['ic95_fila_estratificado'][0]:+.3f}, {r['ic95_fila_estratificado'][1]:+.3f}] | "
                         + (f"[{g[0]:+.3f}, {g[1]:+.3f}] |" if g else "— |"))
    return filas


# F1 publicado por Pancholi et al. (Neural Computing and Applications 2026, 38:5, §4.2 y Tabla 7): hold-out de sus
# propias transacciones de Washington D.C., categorías propias en inglés; NO es TSTR sobre datos reales.
PANCHOLI_PUBLICADO = ("regresión logística: accuracy ≈ 71 %, F1-macro 0,57; BERT afinado: accuracy ≈ 71 %, F1-macro "
                      "0,62; LSTM: accuracy < 40 %; LLaMA-3 vía API: sin métricas estándar (revisión manual de 100 "
                      "transacciones)")


def _contexto_pancholi() -> str:
    ruta = RAIZ / "outputs/pancholi/wp8_mapeabilidad.json"
    if not ruta.exists():
        return "pendiente: falta outputs/pancholi/wp8_mapeabilidad.json (WP5)."
    m = json.loads(ruta.read_text(encoding="utf-8"))
    falta = m["clases_no_alcanzables"]
    masa = 1 - m["masa_sintetico_v1_en_clases_alcanzables"]
    return (
        f"WP5 concluyó la rama (a), *no mapeable* (`outputs/pancholi/wp8_mapeabilidad.json`): su generador alcanza "
        f"{m['n_clases_alcanzables']} de las {m['n_clases_taxonomia']} `categoria_n1` "
        f"({m['n_clases_alcanzables_sin_marginales']} sin las rutas marginales de peso 0,01), así que un clasificador "
        f"entrenado con su salida tendría un techo de F1-macro de {m['techo_f1_macro_16']:.3f} "
        f"({m['techo_f1_macro_16_sin_marginales']:.3f} sin marginales) aun acertando todo lo que puede predecir. "
        f"**Hallazgo de no transferibilidad:** solo emite compras; no produce {', '.join(f'`{c}`' for c in falta)}, "
        f"que suman el {masa:.0%} de las filas del sintético del protocolo. Tampoco produce la entrada de WP8: no "
        f"modela `cuenta_tipo`, su signo es constante y su monto está en USD de Washington D.C. Por eso no se entrena "
        f"sobre su salida ni se pone en esta tabla. Como contexto, su F1 publicado ({PANCHOLI_PUBLICADO}) se mide "
        f"sobre un hold-out de sus propios datos sintéticos de D.C., con otras categorías y en inglés: no es "
        f"comparable con el TSTR del protocolo."
    )


def _jerarquia_ablacion() -> str:
    """Jerarquía de la ablación y lectura de las secundarias, desde ablacion.json."""
    ruta = RAIZ / SALIDA / "tstr" / "ablacion.json"
    base_txt = ("**Jerarquía.** La comparación principal es LogReg con el train completo; LogReg @20k y BETO @20k son "
                "secundarias. Son tres comparaciones sin corrección por comparaciones múltiples: una Δ secundaria no se "
                "interpreta como efecto si su IC95 (por fila o por grupo) toca o cruza cero.")
    if not ruta.exists():
        return base_txt
    lineas = []
    nombres = dict(BRAZOS_TABLA)
    for r in json.loads(ruta.read_text(encoding="utf-8")):
        ics = [r["ic95_fila_estratificado"]] + ([r["ic95_grupo"]] if r.get("ic95_grupo") else [])
        toca = any(lo <= 0 <= hi for lo, hi in ics)
        rol = "principal" if r["brazo"] == "logreg" else "secundaria"
        if rol == "principal":
            lectura = ("el IC contiene cero: **sin diferencia detectable** entre fuentes." if toca
                       else "ningún IC toca cero.")
        else:
            lectura = ("algún IC toca o cruza cero → **no se interpreta como efecto**." if toca
                       else "ningún IC toca cero (secundaria, sin corrección por multiplicidad).")
        lineas.append(f"- {nombres.get(r['brazo'], r['brazo'])} ({rol}): Δ {r['delta_f1_macro']:+.3f}; {lectura}")
    return base_txt + "\n\n" + "\n".join(lineas)


def _seccion_post_hoc() -> str:
    """Hallazgo del cruce P2P/ingreso (solo sintético) y exploratorio post hoc, si existen sus JSON."""
    partes = []
    h = ruta_hallazgo()
    if h.exists():
        H = json.loads(h.read_text(encoding="utf-8"))
        filas = []
        for f, v in H["fuentes"].items():
            for fam, t in v["por_familia"].items():
                filas.append(f"| {NOMBRE_FUENTE.get(f, f)} | {fam} | {t['ingreso']:,} | {t['transferencias_p2p']:,} | "
                             f"{t['movimiento_propio']:,} | {t['otras_proposito_declarado']:,} | {t['total']:,} |")
        sb = {}
        for f, v in H["fuentes"].items():
            x = v["salidas_banco_con_billetera_en_texto"]
            tot = sum(x.values())
            sb[f] = f"{x.get('movimiento_propio', 0):,} de {tot:,} son `movimiento_propio` ({x.get('movimiento_propio', 0) / max(tot, 1):.1%})"
        partes.append(f"""## Hallazgo del protocolo: cruce de convenciones P2P / ingreso (cuantificado solo en el sintético)

La regla R2 manda a `transferencias_p2p` toda transferencia con persona sin propósito declarado, y en el test real de
WP4 ninguna etiqueta proviene de declaración del voluntario (`frac_test_etiqueta_por_declaracion` = 0 en
`metricas.json`): todo P2P real queda en `transferencias_p2p`. El generador, en cambio, etiqueta como `ingreso` una parte de las
transferencias **recibidas** de persona: el ingreso de los no asalariados llega con plantilla de P2P recibida con
probabilidad 0,6 (`{H['fuente_codigo']['ingreso_p2p']}`; capa de texto del CTGAN: `{H['fuente_codigo']['capa_texto_ctgan']}`).
La taxonomía v1.1 lo anticipa: «Este cruce P2P/ingreso es un hallazgo esperable y debe cuantificarse en la tesis»
(caso límite de `ingreso`). No se cambió el generador, ni las etiquetas del test, ni los modelos.

| Fuente | Familia de texto | ingreso | transferencias_p2p | movimiento_propio | otras (propósito declarado) | total |
|---|---|---|---|---|---|---|
{chr(10).join(filas)}

Segundo canal del mismo choque: las P2P **enviadas** con propósito declarado se etiquetan con la categoría del
propósito (R2 con `canal_p2p` = true; columna «otras»), así que en el entrenamiento el texto «… A PERSONA» aparece
también bajo categorías de bienes, mientras en el test ese texto es siempre `transferencias_p2p`.

P2P recibida etiquetada `ingreso`: {', '.join(f"{NOMBRE_FUENTE.get(f, f)} {v['p2p_recibida_etiquetada_ingreso']:.1%}" for f, v in H['fuentes'].items())}.
**Errores hacia `movimiento_propio`:** en el sintético, las salidas desde banco que nombran NEQUI/DAVIPLATA son casi
siempre recargas propias ({'; '.join(f"{NOMBRE_FUENTE.get(f, f)}: {x}" for f, x in sb.items())}), porque la única plantilla que
produce ese texto es la de recarga (`TRANSFERENCIA A {{W}}`, `RECARGA {{W}}`); los envíos P2P desde banco usan
«TRANSFERENCIA A PERSONA». Un envío real desde un banco a la billetera de un tercero se parece así a una recarga.
Menor: el anonimizador de WP4 deja el token `LLAVE` (pagos Bre-B) y en el sintético «LLAVE» solo aparece dentro de
«TULLAVE» (transporte) ({', '.join(f"{NOMBRE_FUENTE.get(f, f)}: {v['token_LLAVE_dentro_de_TULLAVE']:,} filas" for f, v in H['fuentes'].items())}).
Fuente: `{_rel(h)}`.""")
    e = ruta_exploratorio()
    if e.exists():
        E = json.loads(e.read_text(encoding="utf-8"))
        filas = [f"| LogReg completo | {NOMBRE_FUENTE.get(r['fuente'], r['fuente'])} | {r['f1_macro_original']:.3f} | "
                 f"{r['f1_macro_fusionado']:.3f} | {_ic(r['ic95_fila_estratificado'])} | {_ic(r.get('ic95_grupo'))} | "
                 f"{r['clases_evaluadas']} |" for r in E["resultados"]]
        partes.append(f"""## Exploratorio (post hoc, no pre-registrado)

{E['aviso']} `transferencias_p2p` e `ingreso` se fusionan en una sola clase en la etiqueta real y en la predicha; la
regla de soporte se fija sobre el test con la clase fusionada. Fuente: `{_rel(e)}`.

| Brazo | Fuente train | F1-macro principal | F1-macro con P2P+ingreso fusionadas | IC95 fila estrat. | IC95 por grupo | clases evaluadas |
|---|---|---|---|---|---|---|
{chr(10).join(filas)}""")
    return "\n\n---\n\n".join(partes)


# --------------------------------------------------------------------------- insumos LaTeX para el informe


def _n(x: float, d: int = 3) -> str:
    """Número con coma decimal para LaTeX en español."""
    return f"{x:.{d}f}".replace("-", "$-$").replace(".", "{,}")


def _ns(x: float, d: int = 3) -> str:
    """Como _n, con signo explícito (para Δ)."""
    return ("$+$" if x >= 0 else "") + _n(x, d)


def _ic_tex(v, par: str = "[]") -> str:
    return f"{par[0]}{_n(v[0])}; {_n(v[1])}{par[1]}" if v else "---"


def escribir_tablas_latex(corridas: dict, clases: list[str]) -> Path:
    """Tablas booktabs para el informe, generadas desde los mismos JSON/CSV agregados que el .md."""
    T = [f"% Generado por tools/etapa4_tstr.py desde {_rel(RAIZ / SALIDA / 'tstr')}/; no editar a mano.",
         "% Requiere \\usepackage{booktabs}. Coma decimal; IC95 bootstrap con la regla de soporte fija.", ""]
    # 1. tabla principal
    fil = []
    for brazo, nombre in BRAZOS_TABLA:
        corto = nombre.split(" (")[0].replace("Baseline: ", "").replace("+ TF-IDF char 3-5", "(TF-IDF char 3--5)")
        corto = corto.replace("@", "@")
        for f in FUENTES_DEFECTO:
            m = corridas.get(("tstr", f, brazo))
            if brazo == "llm_groq":
                fil.append(f"{corto} & {NOMBRE_FUENTE[f]} & \\multicolumn{{4}}{{l}}{{no evaluado sobre el real$^{{b}}$}} \\\\")
            elif m:
                ew = m.get("exactitud_ponderada") or {}
                fil.append(f"{corto} & {NOMBRE_FUENTE[f]} & {_n(m['f1_macro_regla_soporte'])} & {_ic_tex(m['ic95_bootstrap'])} "
                           f"{_ic_tex(m.get('ic95_conglomerado'), '()')} & {_n(m['accuracy'])} & "
                           f"{_n(ew['valor']) if ew else '---'} \\\\")
        fil.append("\\addlinespace")
    for brazo, nombre in LINEAS_BASE:
        for f in FUENTES_DEFECTO:
            m = corridas.get(("tstr", f, brazo))
            if m:
                ew = m.get("exactitud_ponderada") or {}
                fil.append(f"{nombre.split(' (')[0]} & {NOMBRE_FUENTE[f]} & {_n(m['f1_macro_regla_soporte'])} & "
                           f"{_ic_tex(m['ic95_bootstrap'])} & {_n(m['accuracy'])} & {_n(ew['valor']) if ew else '---'} \\\\")
    T += ["\\begin{table}[ht]\\centering\\small",
          "\\caption{TSTR: entrenado en sintético, evaluado en el real anotado de WP4 ($n=200$). F1-macro con soporte $\\geq 10$.}",
          "\\label{tab:tstr}", "\\begin{tabular}{llcccc}", "\\toprule",
          "Brazo & Fuente de entrenamiento & F1-macro & IC95$^{a}$ & Exactitud & Exactitud ponderada \\\\", "\\midrule",
          *fil, "\\bottomrule", "\\end{tabular}",
          "\\par\\footnotesize $^{a}$ Corchetes: bootstrap por fila estratificado por estrato de muestreo (1000 réplicas, "
          "semilla 42), principal; paréntesis: bootstrap por grupo de extractos (6 grupos), sensibilidad. "
          "$^{b}$ Restricción de tratamiento de datos: no se envían datos reales a la API; humo sobre sintético aparte.",
          "\\end{table}", ""]
    # 2. ablación
    ab = RAIZ / SALIDA / "tstr" / "ablacion.json"
    if ab.exists():
        nombres = {b: n.split(" (")[0].replace("Baseline: ", "").replace("+ TF-IDF char 3-5", "(TF-IDF char 3--5)")
                   for b, n in BRAZOS_TABLA}
        fa = [f"{nombres.get(r['brazo'], r['brazo'])} & {'principal' if r['brazo'] == 'logreg' else 'secundaria'} & "
              f"{_ns(r['delta_f1_macro'])} & {_ic_tex(r['ic95_fila_estratificado'])} & {_ic_tex(r.get('ic95_grupo'))} \\\\"
              for r in json.loads(ab.read_text(encoding="utf-8"))]
        T += ["\\begin{table}[ht]\\centering\\small",
              "\\caption{Ablación: $\\Delta$ F1-macro = CTGAN $-$ reglas, con plantillas de texto idénticas (bootstrap pareado).}",
              "\\label{tab:ablacion}", "\\begin{tabular}{llccc}", "\\toprule",
              "Brazo & Rol & $\\Delta$ & IC95 fila estrat. & IC95 por grupo \\\\", "\\midrule", *fa, "\\bottomrule",
              "\\end{tabular}",
              "\\par\\footnotesize Tres comparaciones sin corrección por multiplicidad; una $\\Delta$ secundaria cuyo IC "
              "(fila o grupo) toca o cruza cero no se interpreta como efecto.", "\\end{table}", ""]
    # 3. F1 por clase, LogReg completo
    pc = {f: pd.read_csv(RAIZ / SALIDA / "tstr" / f / "logreg" / "por_clase.csv").set_index("clase") for f in FUENTES_DEFECTO
          if (RAIZ / SALIDA / "tstr" / f / "logreg" / "por_clase.csv").exists()}
    m0 = corridas.get(("tstr", FUENTES_DEFECTO[0], "logreg"))
    if len(pc) == len(FUENTES_DEFECTO) and m0:
        prev = pd.read_csv(RAIZ / SALIDA / "tstr" / FUENTES_DEFECTO[0] / "logreg" / "prevalencias.csv").set_index("clase")
        fus = m0["clases_fusionadas_a_otros"]
        base = pc[FUENTES_DEFECTO[0]].sort_values("soporte", ascending=False)
        dag, tt = "$^{\\dagger}$", lambda c: "\\texttt{" + c.replace("_", "\\_") + "}"  # noqa: E731
        fc = [f"{tt(c)}{dag if c == CLASE_RESIDUAL else ''} & "
              f"{int(base.loc[c, 'soporte'])} & " + " & ".join(_n(pc[f].loc[c, 'f1']) if c in pc[f].index else "---"
                                                            for f in FUENTES_DEFECTO) + " \\\\" for c in base.index]
        nota = ", ".join(f"{tt(c)} ({int(prev.loc[c, 'n']) if c in prev.index else '?'})"
                         for c in fus)
        T += ["\\begin{table}[ht]\\centering\\small",
              "\\caption{F1 por clase, LogReg (TF-IDF char 3--5) con el train completo, sobre el real de WP4.}",
              "\\label{tab:por_clase}", "\\begin{tabular}{lccc}", "\\toprule",
              "Clase & Soporte & " + " & ".join(NOMBRE_FUENTE[f] for f in FUENTES_DEFECTO) + " \\\\", "\\midrule",
              *fc, "\\bottomrule", "\\end{tabular}",
              f"\\par\\footnotesize $^{{\\dagger}}$ Incluye las clases con soporte $<10$ fusionadas: {nota}.",
              "\\end{table}", ""]
    # 4. sensibilidades
    fs = []
    for brazo, nombre in BRAZOS_TABLA:
        for f in FUENTES_DEFECTO:
            m = corridas.get(("tstr", f, brazo))
            if not m or brazo == "llm_groq":
                continue
            s_ = m["sensibilidades"]
            a, c, d = s_["a_unica_por_descripcion"], s_["c_exactitud_ponderada_recorte_p95"], s_["d_subgrupo_reverso"]
            corto = nombre.split(" (")[0].replace("Baseline: ", "").replace("+ TF-IDF char 3-5", "(TF-IDF char 3--5)")
            umbral = c.get("aplica") is not False and abs(abs(c["diferencia"]) - UMBRAL_ALERTA_PESOS) < 0.0005
            c_txt = ("---" if c.get("aplica") is False else
                     f"{_n(c['valor'])} {_ic_tex(c['ic95_bootstrap'])} & {_n(c['diferencia'], 4)}"
                     + ("$^{c}$" if umbral else ""))
            fs.append(f"{corto} & {NOMBRE_FUENTE[f]} & "
                      + ("---" if a.get("aplica") is False else f"{_n(a['f1_macro_regla_soporte'])} {_ic_tex(a['ic95_bootstrap'])}")
                      + f" & {c_txt} & {'---' if d.get('aplica') is False else str(d['aciertos']) + '/' + str(d['n'])} \\\\")
    if fs:
        a0 = m0["sensibilidades"]["a_unica_por_descripcion"] if m0 else {}
        extra = ", ".join("\\texttt{" + c.replace("_", "\\_") + "}" for c in a0.get("fusiona_ademas_de_la_principal") or [])
        nota_a = (f"(a) $n={a0['n']}$" + (f"; la regla de soporte fusiona además {extra}" if extra else "") + ". ") if a0.get("n") else ""
        T += ["\\begin{table}[ht]\\centering\\small",
              "\\caption{Sensibilidades pre-registradas (IC95 por fila estratificado, regla de soporte fija).}",
              "\\label{tab:sensibilidades}", "\\begin{tabular}{llcccc}", "\\toprule",
              "Brazo & Fuente & (a) F1, una fila por descripción & (c) Exact. pond. P95 & $\\Delta$ vs.\\ sin recorte & (d) Reversos \\\\",
              "\\midrule", *fs, "\\bottomrule", "\\end{tabular}",
              "\\par\\footnotesize " + nota_a + "(c) $\\Delta$ = sin recorte $-$ con recorte al P95. "
              "(b) no aplica: todas las filas tienen doble anotación. (e) $\\kappa$: lo reporta WP4 "
              "(\\texttt{acuerdo\\_wp4.py}). $^{c}$ En el umbral de $\\pm 0{,}05$ (sin alerta formal); se reporta sin redondear.",
              "\\end{table}", ""]
    ruta = ruta_tablas_tex()
    ruta.write_text("\n".join(T), encoding="utf-8")
    return ruta


def _trazabilidad() -> str:
    return f"""## Trazabilidad: qué archivo respalda cada número

| Número | Archivo (agregado, en `outputs/`) | Campo |
|---|---|---|
| F1-macro, IC95 fila y grupo, exactitud, exactitud ponderada, n | `{SALIDA.as_posix()}/tstr/<fuente>/<brazo>/metricas.json` | `f1_macro_regla_soporte`, `ic95_bootstrap`, `ic95_conglomerado`, `accuracy`, `exactitud_ponderada` |
| IC básico, BCa, media/sesgo; IC anterior | ídem | `ic_sensibilidad`, `ic95_regla_recalculada_por_replica` |
| Sensibilidades (a)–(e) | ídem | `sensibilidades` |
| Clases fusionadas a `otros` | ídem | `clases_fusionadas_a_otros` |
| F1/precisión/recall por clase y soporte | `{SALIDA.as_posix()}/tstr/<fuente>/<brazo>/por_clase.csv` | — |
| Errores entre clases (agregados) | `{SALIDA.as_posix()}/tstr/<fuente>/<brazo>/matriz_confusion.csv` | — |
| Soporte original de las clases fusionadas; pesos por clase | `{SALIDA.as_posix()}/tstr/<fuente>/<brazo>/prevalencias.csv` | `n`, `pct_ponderado` |
| Δ de la ablación y sus IC | `{SALIDA.as_posix()}/tstr/ablacion.json` | `delta_f1_macro`, `ic95_fila_estratificado`, `ic95_grupo` |
| Líneas base | `{SALIDA.as_posix()}/tstr/<fuente>/base_mayoritaria|base_estratificada/metricas.json` | ídem |
| Cruce P2P/ingreso en el sintético | `{_rel(ruta_hallazgo())}` | `fuentes.<fuente>.por_familia` |
| Exploratorio P2P+ingreso fusionadas | `{_rel(ruta_exploratorio())}` | `resultados` |
| Tablas LaTeX | `{_rel(ruta_tablas_tex())}` | — |

`<brazo>` ∈ {{`logreg`, `logreg_n{N_COMPARABLE}`, `beto`}}; `<fuente>` ∈ {{`reglas`, `ctgan`}}."""


def _declaraciones_tstr(corridas: dict) -> str:
    """Declaraciones del pre-registro que acompañan a la tabla TSTR, con las cifras del propio test cuando existe."""
    m = next((v for k, v in sorted(corridas.items()) if k[0] == "tstr"), None)
    ew = (m or {}).get("exactitud_ponderada")
    kish = f"{ew['n_efectivo_kish']:.0f}" if ew else "48 según el pre-registro §3"
    ng = (m or {}).get("n_grupos")
    ste = (m or {}).get("solo_etiqueta_por_texto", {})
    return f"""**Declaraciones (D-M6, D-M7, pre-registro §3–§4).**
- **Alcance del IC:** incertidumbre de muestreo **dentro de estos extractos**; no es generalización a nuevos titulares.
  El IC por fila supone filas independientes y subestima la variación entre personas.
- **Sensibilidad por grupo:** {ng if ng else 6} grupos de extractos; solo admiten unas pocas réplicas distintas y las clases están
  concentradas por grupo, así que ese IC es inestable. Se reporta al lado, no como principal.
- **Exactitud ponderada:** n efectivo de Kish = {kish} (cota inferior: los ítems pesados son copias de la misma
  descripción). Su IC sale ancho por diseño. Los PSE sin facturador (≈ 4,4 % del marco, 95 filas) no tienen ningún ítem
  en el test: la exactitud ponderada no dice nada de ellos.
- **Etiqueta-por-texto vs. declaración:** {ste.get('nota', 'ver metricas.json') if ste.get('aplica') is False else 'ver metricas.json'}.
- **Representatividad:** 7 grupos en el conjunto extraído; 6 grupos (≤6 titulares) en el marco y el test, por
  conveniencia; los pesos corrigen el diseño muestral, no la representatividad poblacional."""


def escribir_resultados_md(clases: list[str]) -> None:
    """Regenera docs/resultados_tstr.md a partir de outputs/tstr/**/metricas.json."""
    corridas = {}
    for ruta in sorted((RAIZ / SALIDA).glob("*/*/*/metricas.json")):
        modo, fuente, brazo = ruta.relative_to(RAIZ / SALIDA).parts[:3]
        corridas[(modo, fuente, brazo)] = json.loads(ruta.read_text(encoding="utf-8"))

    filas = []
    for brazo, nombre in BRAZOS_TABLA:
        for fuente in FUENTES_DEFECTO:
            m = corridas.get(("tstr", fuente, brazo))
            if brazo == "llm_groq":
                filas.append(f"| {nombre} | {NOMBRE_FUENTE[fuente]} | no evaluado: {LLM_SIN_REAL.replace('<fuente>', fuente)} "
                             f"| | | | | | | |")
            else:
                filas.append(_fila_tstr(nombre, NOMBRE_FUENTE[fuente], m) if m
                             else f"| {nombre} | {NOMBRE_FUENTE[fuente]} | pendiente WP4 | | | | | | | |")
    sens = [_fila_sens(nombre, NOMBRE_FUENTE[f], corridas[("tstr", f, b)])
            for b, nombre in BRAZOS_TABLA for f in FUENTES_DEFECTO if ("tstr", f, b) in corridas] \
        or ["| — | pendiente WP4 | | | | |"]
    abl = _ablacion("tstr", corridas, clases) or ["| — | pendiente WP4 | | |"]
    filas_ic = [_fila_ic(nombre, NOMBRE_FUENTE[f], corridas[("tstr", f, b)])
                for b, nombre in BRAZOS_TABLA for f in FUENTES_DEFECTO if ("tstr", f, b) in corridas and b != "llm_groq"] \
        or ["| — | pendiente WP4 | | | | | | |"]
    filas_base = [_fila_base(nombre, NOMBRE_FUENTE[f], corridas[("tstr", f, b)])
                  for b, nombre in LINEAS_BASE for f in FUENTES_DEFECTO if ("tstr", f, b) in corridas] \
        or ["| — | sin correr (`--lineas-base`) | | | | |"]
    decl = _declaraciones_tstr(corridas)

    sanity = sorted((k, m) for k, m in corridas.items() if k[0] == "sanity")
    filas_s = [_fila(k[2] + ("" if m.get("entrada", {}).get("version") == VERSION_ENTRADA
                             else " ⚠ entrada vieja (solo descripción): volver a correr"), k[1], m)
               for k, m in sanity] or ["| — | | | | | | | | |"]
    costo = [f"| {k[0]} | {k[1]} | {k[2]} | {m['n_train']:,} | {m['segundos_entrenamiento_y_prediccion']:,.0f} | "
             f"{m.get('brazo_meta', {}).get('costo', '')} |" for k, m in sorted(corridas.items())] or ["| — | | | | | |"]

    man = RAIZ / "outputs/texto/manifest.json"
    frac_inc = (f"{json.loads(man.read_text(encoding='utf-8'))['fuentes']['ctgan']['frac_incoherente']:.1%}"
                if man.exists() else "ver")
    md = f"""# Resultados TSTR — WP8

> Archivo regenerado por `tools/etapa4_tstr.py`; no editar a mano.
> Última regeneración: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.
> Taxonomía {VERSION_TAXONOMIA}, target `{TARGET}`, semilla {SEMILLA}.

**Taxonomía.** La v1.1.0 no cambió las 16 categorías ni las reglas R1–R7, solo documentación y metadatos
de anotación (T1–T6, §9 de `taxonomia_gastos_colombia_v1.md`); el CTGAN entrenado con el JSON v1.0.0 sigue
siendo válido para el TSTR y no se regenera.

**Texto (D14).** Ambas fuentes reciben la `descripcion` de la misma capa de texto (`src/sdg/texto.py`,
`tools/etapa3b_texto.py`): mismas plantillas, comercios y semilla, ninguna calibrada con el real de WP4.

**Swap a WP4.** El TSTR se activa con una sola ruta (`--test data/reales_anon/test_real_wp4_<AAAAMMDD>.csv`, escrito
por `tools/consolidar_test_wp4.py`). Esquema: `{', '.join(COLUMNAS_WP4)}` y columnas de análisis
`{', '.join(COLUMNAS_ANALISIS_WP4)}`, ninguna como entrada. Verificado de punta a punta con el real simulado
(`tests/fixtures/real_simulado_wp4.csv`) y con la salida del consolidador sobre datos simulados
(`tests/test_swap_wp4.py`). Las predicciones por ítem del real van a `data/_privado/tstr/` (ignorado por git).

## Tabla TSTR (único resultado reportable)

Entrenamiento sobre **todo** el sintético; evaluación sobre el conjunto **real anotado de WP4** (pre-registro
`docs/datos_reales/05_prerregistro_muestreo_anotacion.md` v1.4: diseño y métricas de la v1.3; la v1.4 solo registra
desviaciones de ejecución, §13). **Métrica principal:** F1-macro **sin ponderar**
sobre los ítems del test, con regla de soporte: clases con < {SOPORTE_MIN} filas de la muestra se recodifican a
`{CLASE_RESIDUAL}` (en etiqueta real y predicha) antes del promedio. **IC95 principal (D-M7):** bootstrap por fila
({N_BOOTSTRAP} réplicas, semilla {SEMILLA}) estratificado por `estrato_muestreo`. **Sensibilidad:** bootstrap por
grupo de extractos (`voluntario_id` = grupo, no titular). **Secundaria (D-M6):** exactitud ponderada con
`peso_muestreo` (estimador de Hájek), con IC por el mismo bootstrap; la exactitud sin ponderar describe la mezcla de
la muestra, no la de un extracto.

{CAB_TSTR}
{chr(10).join(filas)}

### Sensibilidad del intervalo (misma réplica; corrección del 26-nov-2026)

**Corrección posterior a la primera corrida oficial (26-nov-2026).** Qué estaba mal: el bootstrap recalculaba la
regla de soporte (≥ 10) dentro de cada réplica. Con cinco clases en el umbral en el test (`educacion` y
`retiro_efectivo` con 10, `ingreso` y `salud` con 11, `entretenimiento` con 9), en ~95 % de las réplicas cambiaba el
conjunto de clases evaluadas: el IC no correspondía al estimador reportado y quedaba desplazado ~0,05 hacia abajo
(punto pegado al límite superior). Qué se cambió: la regla se fija una vez sobre el test observado y todas las
réplicas evalúan las mismas clases (IC principal, por grupo, sensibilidades y Δ de la ablación). Las cifras
**puntuales no cambiaron** (la corrida repetida las reproduce exactamente); solo cambian los IC. El IC anterior se
conserva en la última columna para trazabilidad. Como sensibilidad
se reportan el IC básico y el BCa (z0 por proporción de réplicas bajo el punto; aceleración por jackknife de filas,
aproximación con remuestreo estratificado).

{CAB_IC}
{chr(10).join(filas_ic)}

### Líneas base (contexto, mismo test y misma regla de soporte; no entran a la ablación)

{CAB_BASE}
{chr(10).join(filas_base)}

### Sensibilidades pre-registradas (§4)

Cada F1 recalcula la regla de soporte en su subconjunto («fusiona además» = clases que se pierden frente a la
principal). (c) recorta los pesos al percentil 95 y renormaliza; ⚠ si cambia la exactitud ponderada en más de 5
puntos. (d) los reversos y devoluciones de tarjeta están dentro de la métrica principal y se muestran aparte.
(e) el κ sin los casos de convención lo calcula `tools/acuerdo_wp4.py`, no WP8.

{CAB_SENS}
{chr(10).join(sens)}

{decl}

**Asimetría de tamaño (declarada).** BETO entrena sobre una submuestra estratificada de {N_COMPARABLE:,} filas por
costo de CPU. La comparación de igual a igual es LogReg @{N_COMPARABLE // 1000}k frente a BETO @{N_COMPARABLE // 1000}k
(mismas filas, misma semilla); LogReg con el train completo es la mejor cifra del baseline, no un rival de BETO en
igualdad de datos. El brazo LLM no entrena: el sintético solo entra por los ejemplos few-shot.

**Pipeline de Pancholi et al.: contexto, no fila de la tabla.** {_contexto_pancholi()}

### Ablación reglas → CTGAN (Δ = CTGAN − reglas, bootstrap pareado sobre el mismo test)

| Brazo | Δ F1-macro | IC95 principal (fila estrat.) | IC95 por grupo (sensibilidad) |
|---|---|---|---|
{chr(10).join(abl)}

{_jerarquia_ablacion()}

**Entrada (idéntica en los tres brazos).** `{FORMATO_ENTRADA}`; `monto` en bins log10 de media década, en
pesos de promedio 2025 (el sintético ya lo está; el real de WP4 se deflacta con el IPC total nacional del mes si trae
`fecha`). Son observables del extracto, no anotaciones. Indicio del sanity (no reportable): frente a solo
`descripcion`, el F1-macro del baseline sube poco y la ganancia está en `transferencias_p2p` e `ingreso` (el signo, la
cuenta y el monto separan P2P recibida de ingreso y P2P sin propósito de pagos con propósito); `retiro_efectivo` y
`movimiento_propio` ya estaban en el techo solo con texto. Las ambigüedades de categoría por texto no se resuelven, y
en las filas etiquetadas por declaración el monto mueve errores hacia clases raras (en el sanity, `educacion` cae).
El techo por diseño de esas filas sigue intacto; el efecto real se mide solo sobre el test de WP4.

**Brazo LLM.** {LLM_SIN_REAL.replace('<fuente>', '{reglas,ctgan}')} (decisión final del 26-nov-2026: no se envían datos
reales a Groq). El humo usa `openai/gpt-oss-120b` porque Groq retiró `llama-3.3-70b-versatile` de las cuentas
free/developer el 16-ago-2026 (desviación en `metricas.json`); las respuestas vacías o fuera del enum se cuentan como
error (etiqueta centinela `__fuera_de_enum__`), no se descartan. Con 40 filas su F1-macro no es interpretable.

**Cómo leer estos números.** El TSTR absoluto mide *plantillas + estructura*: está acotado por el realismo
de las plantillas de texto (regla propia, más limpias y regulares que un extracto real), así que es una cota
del protocolo completo, no de la Etapa 3 sola. La diferencia reglas → CTGAN, con plantillas idénticas,
aísla la capa estructural: es el número que atribuye una mejora (o un deterioro) al generador CTGAN y no al
texto. Las filas que el CTGAN emite con combinaciones que el generador por reglas nunca produce ({frac_inc},
`outputs/texto/manifest.json`) no se reparan: su error es de la Etapa 3 y el TSTR lo cobra.

{_seccion_post_hoc()}

---

{_trazabilidad()}

---

## Costo de cómputo (declarado)

| Modo | Fuente | Brazo | n train efectivo | segundos | detalle |
|---|---|---|---|---|---|
{chr(10).join(costo)}

---

## Sanity check — NO REPORTABLE

Holdout 80/20 estratificado por `{TARGET}` **dentro de cada sintético**. Mide ajuste interno del
clasificador al generador, no transferencia a datos reales. No es TSTR, no va al informe como resultado y
no admite Δ pareado (cada fuente tiene su propio holdout). `reglas_original` = texto original del generador
por reglas (diagnóstico de la capa de texto factorizada).

{CAB}
{chr(10).join(filas_s)}
"""
    (RAIZ / RESULTADOS_MD).write_text(md, encoding="utf-8")
    escribir_tablas_latex(corridas, clases)


if __name__ == "__main__":
    main()
