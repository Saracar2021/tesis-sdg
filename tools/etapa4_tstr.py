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
Opcionales en el test: fuente_etiqueta (F1 con y sin filas etiquetadas por declaración del
voluntario) y voluntario_id (bootstrap por conglomerado). Las columnas de anotación
(categoria_n2, medio_pago, origen, formalidad_comercio, canal_p2p, ...) NUNCA son features.
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


# --------------------------------------------------------------------------- métricas
def aplicar_regla_soporte(y_true: np.ndarray, y_pred: np.ndarray, clases: list[str]):
    """Clases con soporte < SOPORTE_MIN en el TEST se recodifican a 'otros' en y_true
    y en y_pred antes de calcular el F1-macro. Devuelve (y_true', y_pred', etiquetas
    evaluadas, clases fusionadas)."""
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
    yt, yp, etiquetas, _ = aplicar_regla_soporte(y_true, y_pred, clases)
    return f1_score(yt, yp, labels=etiquetas, average="macro", zero_division=0)


def _indices_bootstrap(n: int, grupos, n_rep: int, semilla: int):
    """Réplicas de índices; por conglomerado si hay grupos (filas de una persona no son independientes)."""
    rng = np.random.default_rng(semilla)
    if grupos is None:
        for _ in range(n_rep):
            yield rng.integers(0, n, n)
        return
    grupos = np.asarray(grupos)
    unicos = np.unique(grupos)
    por_grupo = {g: np.flatnonzero(grupos == g) for g in unicos}
    for _ in range(n_rep):
        sel = rng.choice(unicos, size=len(unicos), replace=True)
        yield np.concatenate([por_grupo[g] for g in sel])


def bootstrap_ic(y_true, y_pred, clases, grupos=None, n=N_BOOTSTRAP, semilla=SEMILLA):
    """IC95 percentil del F1-macro con regla de soporte."""
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    vals = [f1_macro_regla(y_true[i], y_pred[i], clases)
            for i in _indices_bootstrap(len(y_true), grupos, n, semilla)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def bootstrap_delta(y_true, pred_a, pred_b, clases, grupos=None, n=N_BOOTSTRAP, semilla=SEMILLA):
    """Δ = F1(b) − F1(a) con bootstrap PAREADO (mismas réplicas del mismo test para ambos brazos)."""
    y_true, pred_a, pred_b = map(np.asarray, (y_true, pred_a, pred_b))
    d = f1_macro_regla(y_true, pred_b, clases) - f1_macro_regla(y_true, pred_a, clases)
    vals = [f1_macro_regla(y_true[i], pred_b[i], clases) - f1_macro_regla(y_true[i], pred_a[i], clases)
            for i in _indices_bootstrap(len(y_true), grupos, n, semilla)]
    return float(d), float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def evaluar(y_true, y_pred, clases, grupos=None) -> dict:
    yt, yp, etiquetas, fusionadas = aplicar_regla_soporte(y_true, y_pred, clases)
    p, r, f, s = precision_recall_fscore_support(yt, yp, labels=etiquetas, zero_division=0)
    por_clase = pd.DataFrame({"clase": etiquetas, "precision": p, "recall": r, "f1": f, "soporte": s})
    presentes = [c for c in clases if (np.asarray(y_true) == c).any()]
    if len(etiquetas) < 2:
        print(f"  AVISO: solo {len(etiquetas)} clase(s) con soporte >= {SOPORTE_MIN}; el F1-macro no es interpretable")
    return {
        "advertencia": (f"solo {len(etiquetas)} clase(s) evaluable(s): F1-macro no interpretable" if len(etiquetas) < 2 else None),
        "f1_macro_regla_soporte": float(f.mean()),
        "ic95_bootstrap": list(bootstrap_ic(y_true, y_pred, clases, grupos)),
        "f1_macro_sin_regla": float(
            f1_score(y_true, y_pred, labels=presentes, average="macro", zero_division=0)),
        "accuracy": float((np.asarray(y_true) == np.asarray(y_pred)).mean()),
        "n_test": int(len(y_true)),
        "clases_evaluadas": len(etiquetas),
        "clases_fusionadas_a_otros": fusionadas,
        "_por_clase": por_clase,
    }


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


# --------------------------------------------------------------------------- una corrida
def correr(fuente: str, ruta_train: Path, ruta_test: Path | None, clases: list[str], sha_tax: str,
           brazo: Brazo = BRAZO_LOGREG, recorte_test: Callable[[pd.DataFrame], pd.DataFrame] | None = None) -> dict:
    """``recorte_test`` (opcional, brazo LLM): submuestra declarada del test por costo de API; se registra n_test."""
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
    col_grupo = None if modo == "sanity" else next((c for c in COLUMNAS_CONGLOMERADO if c in test.columns), None)
    grupos = test[col_grupo].to_numpy() if col_grupo else None
    fe = test["fuente_etiqueta"].astype(str).to_numpy() if "fuente_etiqueta" in test.columns else None

    t0 = datetime.now(timezone.utc)
    y_pred, meta = brazo.ajustar_predecir(train, test)
    y_pred = np.asarray(y_pred, dtype=object)
    segundos = (datetime.now(timezone.utc) - t0).total_seconds()
    y_true = test[TARGET].to_numpy()

    res = evaluar(y_true, y_pred, clases, grupos)
    por_clase = res.pop("_por_clase")
    if fe is not None:
        m = fe == ETIQUETA_TEXTO
        sub = evaluar(y_true[m], y_pred[m], clases, grupos[m] if grupos is not None else None)
        sub.pop("_por_clase")
        res["solo_etiqueta_por_texto"] = {k: sub[k] for k in (
            "f1_macro_regla_soporte", "ic95_bootstrap", "n_test", "clases_evaluadas", "clases_fusionadas_a_otros")}
        res["frac_test_etiqueta_por_declaracion"] = float((~m).mean())

    destino = RAIZ / SALIDA / modo / fuente / brazo.nombre
    destino.mkdir(parents=True, exist_ok=True)
    por_clase.to_csv(destino / "por_clase.csv", index=False)
    pd.DataFrame(confusion_matrix(y_true, y_pred, labels=clases), index=clases, columns=clases
                 ).rename_axis("real\\pred").to_csv(destino / "matriz_confusion.csv")
    pd.DataFrame({"y_true": y_true, "y_pred": y_pred,
                  "grupo": grupos if grupos is not None else "",
                  "fuente_etiqueta": fe if fe is not None else ""}
                 ).to_csv(destino / "predicciones.csv.gz", index=False, compression=GZIP)

    metricas = {
        "modo": modo, "reportable": modo == "tstr", "fuente": fuente, "brazo": brazo.descripcion,
        **res,
        "bootstrap": {"n": N_BOOTSTRAP, "unidad": col_grupo or "fila"},
        "segundos_entrenamiento_y_prediccion": round(segundos, 1),
        "n_train": int(meta.pop("n_train_efectivo", len(train))),
        "n_train_disponible": int(len(train)),
        "n_test_completo": int(n_test_completo),
        "contrato_wp4_faltan": faltan_wp4,
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
    resumen = {k: metricas.get(k) for k in ("modo", "f1_macro_regla_soporte", "ic95_bootstrap", "accuracy",
                                            "n_train", "n_test", "clases_fusionadas_a_otros",
                                            "segundos_entrenamiento_y_prediccion")}
    if "solo_etiqueta_por_texto" in metricas:
        resumen["f1_solo_etiqueta_por_texto"] = metricas["solo_etiqueta_por_texto"]["f1_macro_regla_soporte"]
    print(json.dumps(resumen, ensure_ascii=False))
    print(f"-> {destino.relative_to(RAIZ).as_posix() if destino.is_relative_to(RAIZ) else destino}")
    return metricas


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--fuentes", nargs="+", default=FUENTES_DEFECTO,
                    help=f"Alias ({', '.join(FUENTES)}) o rutas relativas a la raíz.")
    ap.add_argument("--test", type=Path, default=None,
                    help="Real anotado de WP4. Si se omite: sanity check NO reportable.")
    ap.add_argument("--n-train", type=int, nargs="*", default=[0],
                    help=f"0 = train completo; N = submuestra de N filas (las mismas que BETO). "
                         f"Por defecto solo completo; '--n-train 0 {N_COMPARABLE}' corre ambas.")
    args = ap.parse_args()
    clases, sha_tax = cargar_taxonomia()
    for f in args.fuentes:
        ruta = FUENTES.get(f, Path(f))
        nombre = f if f in FUENTES else ruta.name.split(".")[0]
        for n in args.n_train:
            correr(nombre, ruta, args.test, clases, sha_tax, brazo_logreg_n(n or None))
    escribir_resultados_md(clases)


# --------------------------------------------------------------------------- reporte
RESULTADOS_MD = Path("docs/resultados_tstr.md")
BRAZOS_TABLA = [
    ("logreg", "Baseline: LogReg + TF-IDF char 3-5 (train completo)"),
    (f"logreg_n{N_COMPARABLE}", f"Baseline: LogReg @{N_COMPARABLE // 1000}k (mismas filas que BETO)"),
    ("beto", "BETO fine-tuning"),
    ("llm_groq", "LLM vía Groq, prompting few-shot (modelo y desviación en Costo)"),
]
CAB = ("| Brazo | Fuente train | F1-macro (soporte ≥10) | IC95 | F1-macro solo etiqueta-por-texto | IC95 | "
       "n train | n test | fusionadas a otros |\n|---|---|---|---|---|---|---|---|---|")


def _ic(v) -> str:
    return f"[{v[0]:.3f}, {v[1]:.3f}]"


def _fila(nombre: str, fuente: str, m: dict) -> str:
    st = m.get("solo_etiqueta_por_texto")
    st_txt = (f"{st['f1_macro_regla_soporte']:.3f} | {_ic(st['ic95_bootstrap'])}" if st else "— | —")
    return (f"| {nombre} | {fuente} | {m['f1_macro_regla_soporte']:.3f} | {_ic(m['ic95_bootstrap'])} | {st_txt} | "
            f"{m['n_train']:,} | {m['n_test']:,} | {_fusionadas(m['clases_fusionadas_a_otros'])} |")


def _fusionadas(lista: list[str]) -> str:
    if not lista:
        return "—"
    return ", ".join(lista) if len(lista) <= 4 else f"{len(lista)} clases (lista en metricas.json)"


def _ablacion(modo: str, corridas: dict, clases: list[str]) -> list[str]:
    """Δ CTGAN − reglas por brazo, bootstrap pareado sobre las predicciones guardadas (mismo test)."""
    filas = []
    for brazo, nombre in BRAZOS_TABLA:
        a, b = corridas.get((modo, "reglas", brazo)), corridas.get((modo, "ctgan", brazo))
        if not (a and b) or a["test"] != b["test"] and modo == "tstr":
            continue
        pa = pd.read_csv(RAIZ / SALIDA / modo / "reglas" / brazo / "predicciones.csv.gz", keep_default_na=False)
        pb = pd.read_csv(RAIZ / SALIDA / modo / "ctgan" / brazo / "predicciones.csv.gz", keep_default_na=False)
        if modo == "sanity" or len(pa) != len(pb) or not (pa["y_true"].to_numpy() == pb["y_true"].to_numpy()).all():
            continue          # en sanity cada fuente tiene su propio holdout: no hay Δ pareado
        g = pa["grupo"].to_numpy() if (pa["grupo"] != "").any() else None
        d, lo, hi = bootstrap_delta(pa["y_true"].to_numpy(), pa["y_pred"].to_numpy(), pb["y_pred"].to_numpy(), clases, g)
        txt = f"| {nombre} | {d:+.3f} | [{lo:+.3f}, {hi:+.3f}] |"
        m = (pa["fuente_etiqueta"] == ETIQUETA_TEXTO).to_numpy()
        if (pa["fuente_etiqueta"] != "").any():
            d2, lo2, hi2 = bootstrap_delta(pa["y_true"].to_numpy()[m], pa["y_pred"].to_numpy()[m],
                                           pb["y_pred"].to_numpy()[m], clases, g[m] if g is not None else None)
            txt += f" {d2:+.3f} | [{lo2:+.3f}, {hi2:+.3f}] |"
        else:
            txt += " — | — |"
        filas.append(txt)
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
            filas.append(_fila(nombre, NOMBRE_FUENTE[fuente], m) if m
                         else f"| {nombre} | {NOMBRE_FUENTE[fuente]} | pendiente WP4 | | | | | | |")
    abl = _ablacion("tstr", corridas, clases) or ["| — | pendiente WP4 | | | |"]

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

> **PROVISIONAL.** Archivo regenerado por `tools/etapa4_tstr.py`; no editar a mano.
> Última regeneración: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.
> Taxonomía {VERSION_TAXONOMIA}, target `{TARGET}`, semilla {SEMILLA}.

**Taxonomía.** La v1.1.0 no cambió las 16 categorías ni las reglas R1–R7, solo documentación y metadatos
de anotación (T1–T6, §9 de `taxonomia_gastos_colombia_v1.md`); el CTGAN entrenado con el JSON v1.0.0 sigue
siendo válido para el TSTR y no se regenera.

**Texto (D14).** Ambas fuentes reciben la `descripcion` de la misma capa de texto (`src/sdg/texto.py`,
`tools/etapa3b_texto.py`): mismas plantillas, comercios y semilla, ninguna calibrada con el real de WP4.

**Swap a WP4.** El TSTR se activa con una sola ruta (`--test data/reales_anon/<real>.csv`). Esquema esperado:
`{', '.join(COLUMNAS_WP4)}`. Verificado de punta a punta con un real simulado de 30 filas
(`tests/fixtures/real_simulado_wp4.csv`, `tests/test_swap_wp4.py`).

## Tabla TSTR (único resultado reportable)

Entrenamiento sobre **todo** el sintético; evaluación sobre el conjunto **real anotado de WP4**.
F1-macro con regla de soporte: clases con < {SOPORTE_MIN} ejemplos en el test real se recodifican a
`{CLASE_RESIDUAL}` (en etiqueta real y predicha) antes del promedio. IC95 por bootstrap ({N_BOOTSTRAP} réplicas),
por conglomerado (voluntario) cuando el test trae esa columna. «Solo etiqueta-por-texto» excluye las filas con
`fuente_etiqueta = declaracion_voluntario` (pagos a persona con propósito declarado, regla R2): su categoría no
está en el texto del extracto, así que acotan por diseño a cualquier clasificador de texto.

{CAB}
{chr(10).join(filas)}

**Asimetría de tamaño (declarada).** BETO entrena sobre una submuestra estratificada de {N_COMPARABLE:,} filas por
costo de CPU. La comparación de igual a igual es LogReg @{N_COMPARABLE // 1000}k frente a BETO @{N_COMPARABLE // 1000}k
(mismas filas, misma semilla); LogReg con el train completo es la mejor cifra del baseline, no un rival de BETO en
igualdad de datos. El brazo LLM no entrena: el sintético solo entra por los ejemplos few-shot.

**Pipeline de Pancholi et al.: contexto, no fila de la tabla.** {_contexto_pancholi()}

### Ablación reglas → CTGAN (Δ = CTGAN − reglas, bootstrap pareado sobre el mismo test)

| Brazo | Δ F1-macro | IC95 | Δ solo etiqueta-por-texto | IC95 |
|---|---|---|---|---|
{chr(10).join(abl)}

**Entrada (idéntica en los tres brazos).** `{FORMATO_ENTRADA}`; `monto` en bins log10 de media década, en
pesos de promedio 2025 (el sintético ya lo está; el real de WP4 se deflacta con el IPC total nacional del mes si trae
`fecha`). Son observables del extracto, no anotaciones. Indicio del sanity (no reportable): frente a solo
`descripcion`, el F1-macro del baseline sube poco y la ganancia está en `transferencias_p2p` e `ingreso` (el signo, la
cuenta y el monto separan P2P recibida de ingreso y P2P sin propósito de pagos con propósito); `retiro_efectivo` y
`movimiento_propio` ya estaban en el techo solo con texto. Las ambigüedades de categoría por texto no se resuelven, y
en las filas etiquetadas por declaración el monto mueve errores hacia clases raras (en el sanity, `educacion` cae).
El techo por diseño de esas filas sigue intacto; el efecto real se mide solo sobre el test de WP4.

**Brazo LLM.** El sintético entra solo por los ejemplos few-shot (3 por clase difícil): su Δ CTGAN − reglas mide el
efecto de la fuente de esos ejemplos, no de un entrenamiento, y se espera cerca de cero. Groq retiró
`llama-3.3-70b-versatile` de las cuentas free/developer el 16-ago-2026: el modelo usado y la desviación quedan en la
tabla de costo y en `metricas.json`.

**Cómo leer estos números.** El TSTR absoluto mide *plantillas + estructura*: está acotado por el realismo
de las plantillas de texto (regla propia, más limpias y regulares que un extracto real), así que es una cota
del protocolo completo, no de la Etapa 3 sola. La diferencia reglas → CTGAN, con plantillas idénticas,
aísla la capa estructural: es el número que atribuye una mejora (o un deterioro) al generador CTGAN y no al
texto. Las filas que el CTGAN emite con combinaciones que el generador por reglas nunca produce ({frac_inc},
`outputs/texto/manifest.json`) no se reparan: su error es de la Etapa 3 y el TSTR lo cobra.

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


if __name__ == "__main__":
    main()
