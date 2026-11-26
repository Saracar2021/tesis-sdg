"""
Etapa 4 / WP8 — Brazo 2: BETO (dccuchile/bert-base-spanish-wwm-cased), fine-tuning en CPU.

Modos
  --solo-entrenar        Entrena sobre el SINTÉTICO COMPLETO de cada fuente, submuestra estratificada de --n-train filas
                         (20.000, las mismas filas que LogReg@20k en TSTR), y guarda el modelo en
                         outputs/tstr/_modelos/beto_<fuente>/ (ignorado por git) con manifiesto.json: SHA-256 de los
                         pesos, revisiones del modelo base, semilla, n_train, SHA-256 del sintético y de la submuestra,
                         hiperparámetros y versiones. NO lee ni toca data/ (guardia explícita). Fuentes en serie; si una
                         falla, sigue con la otra y lo registra en outputs/tstr/_modelos/estado_entrenamiento.json.
                         Reanudable por época (outputs/tstr/_ckpt/).
  --evaluar --test X     Carga cada modelo, verifica su manifiesto contra los archivos actuales (pesos, sintético,
                         submuestra, revisiones, clases) y solo predice y evalúa con etapa4_tstr.correr (mismas
                         métricas, IC y salidas que el baseline). Minutos.
  --verificar            Revisa estado_entrenamiento.json y los manifiestos sin cargar el modelo. Código de salida 0
                         si todo está bien.
  --medir N              Cronometra N pasos y proyecta el costo; no escribe nada.
  (sin modo)             SANITY CHECK (NO REPORTABLE): entrena sobre el 80 % sintético y evalúa en el 20 % holdout.

Entrada: la serialización canónica de etapa4_tstr.serializar (la MISMA de los tres brazos). Nunca columnas de anotación.
Hiperparámetros fijados ANTES de ver el test (sin validación ni early stopping): lr 2e-5, batch 16, 3 épocas,
max_len 64, AdamW (weight_decay 0.01), warmup lineal 10 %, pesos de clase 'balanced', semilla 42, 4 hilos.
Modelo base: revisiones fijas REVISION_TOKENIZADOR (main) y REVISION_PESOS (refs/pr/3, safetensors).
BETO no publica pesos del pooler: el pooler y el clasificador se inicializan al azar y se entrenan (declarado).

Uso (raíz del repo, entorno .venv-ctgan):
  .venv-ctgan/Scripts/python tools/etapa4_beto.py --solo-entrenar
  .venv-ctgan/Scripts/python tools/etapa4_beto.py --verificar
  .venv-ctgan/Scripts/python tools/etapa4_beto.py --evaluar --test data/reales_anon/test_real_wp4_<AAAAMMDD>.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import etapa4_tstr as base  # noqa: E402

MODELO = "dccuchile/bert-base-spanish-wwm-cased"
# Revisiones FIJAS (reproducibilidad). `main` no trae model.safetensors, solo pytorch_model.bin; transformers tomaba los
# pesos de la conversión automática refs/pr/3. Se fija exactamente lo que corrió el 23-nov-2026: configuración y
# tokenizador de main, pesos safetensors de refs/pr/3 (configuración equivalente a la de main).
REVISION_TOKENIZADOR = "c4d86612f51b4f46759c8390d1798c2febe71b93"     # refs/heads/main
REVISION_PESOS = "35695e6a39cb1254b606e9d72d89dd53fb1e384d"           # refs/pr/3 (model.safetensors)
LR, BATCH, EPOCAS, MAX_LEN = 2e-5, 16, 3, 64
WEIGHT_DECAY, WARMUP = 0.01, 0.10
N_TRAIN_DEFECTO = base.N_COMPARABLE     # 20.000: el mismo N que la fila LogReg@20k
HILOS_DEFECTO = 4
BATCH_PRED = 64
CKPT = Path("outputs/tstr/_ckpt")
MODELOS = Path("outputs/tstr/_modelos")       # ignorado por git
ESTADO = MODELOS / "estado_entrenamiento.json"
PESOS_ARCHIVO = "model.safetensors"


# --------------------------------------------------------------------------- utilidades
def fijar_semillas(semilla: int, hilos: int):
    import torch
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(semilla)
    np.random.seed(semilla)
    torch.manual_seed(semilla)
    torch.set_num_threads(hilos)          # el nº de hilos cambia el orden de las sumas: se fija y se declara
    torch.use_deterministic_algorithms(True)


def submuestra(train: pd.DataFrame, n: int, semilla: int) -> pd.DataFrame:
    """La misma submuestra que LogReg@N (etapa4_tstr.submuestra): mismas filas para la comparación de igual a igual."""
    return base.submuestra(train, n, semilla)


def pesos_balanced(y_idx: np.ndarray, k: int) -> np.ndarray:
    """w_c = n / (k * n_c), igual que class_weight='balanced' de sklearn (clases ausentes: peso 0)."""
    cuenta = np.bincount(y_idx, minlength=k).astype(float)
    w = np.zeros(k)
    w[cuenta > 0] = len(y_idx) / (np.count_nonzero(cuenta) * cuenta[cuenta > 0])
    return w


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rechazar_data(ruta: Path) -> None:
    """D14 / pedido de WP8: el entrenamiento nunca lee ni escribe bajo data/ (ahí vive el real de WP4)."""
    datos = (base.RAIZ / "data").resolve()
    r = (base.RAIZ / ruta).resolve()
    if r == datos or datos in r.parents:
        raise PermissionError(f"El entrenamiento de BETO no puede usar {ruta} (bajo data/)")


def dir_modelo(fuente: str) -> Path:
    return base.RAIZ / MODELOS / f"beto_{fuente}"


def leer_estado() -> dict:
    ruta = base.RAIZ / ESTADO
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def escribir_estado(estado: dict) -> None:
    ruta = base.RAIZ / ESTADO
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- entrenamiento y predicción
class MedicionLista(Exception):
    def __init__(self, seg_paso, total, n, epocas):
        self.seg_paso, self.total, self.n, self.epocas = seg_paso, total, n, epocas


class BrazoBETO:
    def __init__(self, clases: list[str], n_train: int = N_TRAIN_DEFECTO, epocas: int = EPOCAS,
                 hilos: int = HILOS_DEFECTO, medir: int | None = None, modelo: str = MODELO,
                 revision_tokenizador: str = REVISION_TOKENIZADOR, revision_pesos: str = REVISION_PESOS):
        self.clases, self.n_train, self.epocas, self.hilos = clases, n_train, epocas, hilos
        self.medir, self.modelo = medir, modelo
        self.rev_tok, self.rev_pesos = revision_tokenizador, revision_pesos
        self.revision = f"tok={revision_tokenizador[:12]},pesos={revision_pesos[:12]}"
        self.etiqueta_ckpt = "sin_ckpt"

    def _cargar(self):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        k = len(self.clases)
        tok = AutoTokenizer.from_pretrained(self.modelo, revision=self.rev_tok)
        mod = AutoModelForSequenceClassification.from_pretrained(
            self.modelo, revision=self.rev_pesos, use_safetensors=True, num_labels=k,
            id2label=dict(enumerate(self.clases)), label2id={c: i for i, c in enumerate(self.clases)})
        return tok, mod

    @staticmethod
    def _lotes(tok, textos: list[str], y: np.ndarray | None, orden: np.ndarray):
        import torch
        tam = BATCH if y is not None else BATCH_PRED
        for i in range(0, len(orden), tam):
            j = orden[i:i + tam]
            enc = tok([textos[t] for t in j], padding=True, truncation=True, max_length=MAX_LEN, return_tensors="pt")
            if y is not None:
                enc["labels"] = torch.as_tensor(y[j], dtype=torch.long)
            yield enc

    def _firma(self, sub: pd.DataFrame) -> str:
        return f"{len(sub)}|{self.epocas}|{self.hilos}|{self.revision}|{base.sha256_texto(sub)}"

    def entrenar(self, sub: pd.DataFrame):
        """Fine-tuning determinista sobre `sub` (ya submuestreado). Devuelve (tokenizador, modelo, meta)."""
        import torch
        import transformers
        from transformers import get_linear_schedule_with_warmup

        fijar_semillas(base.SEMILLA, self.hilos)
        idx_clase = {c: i for i, c in enumerate(self.clases)}
        y = sub[base.TARGET].map(idx_clase).to_numpy()
        textos = base.texto_entrada(sub).tolist()
        tok, mod = self._cargar()
        n_trunc = int(sum(len(e) > MAX_LEN for e in tok(textos, truncation=False)["input_ids"]))

        pasos_epoca = int(np.ceil(len(sub) / BATCH))
        total = pasos_epoca * self.epocas
        opt = torch.optim.AdamW(mod.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
        sch = get_linear_schedule_with_warmup(opt, int(WARMUP * total), total)
        perdida = torch.nn.CrossEntropyLoss(weight=torch.as_tensor(pesos_balanced(y, len(self.clases)), dtype=torch.float32))

        ckpt = base.RAIZ / CKPT / f"{self.etiqueta_ckpt}.pt"
        epoca0 = 0
        if self.medir is None and ckpt.exists():
            est = torch.load(ckpt, weights_only=False)
            if est["firma"] == self._firma(sub):
                mod.load_state_dict(est["modelo"]); opt.load_state_dict(est["opt"]); sch.load_state_dict(est["sch"])
                torch.set_rng_state(est["rng"]); epoca0 = est["epoca"]
                print(f"  reanudando desde el final de la época {epoca0}", flush=True)

        mod.train()
        t0, paso = time.perf_counter(), 0
        for ep in range(epoca0, self.epocas):
            orden = np.random.default_rng(base.SEMILLA + ep).permutation(len(sub))   # barajado por época, sin estado
            for enc in self._lotes(tok, textos, y, orden):
                labels = enc.pop("labels")
                loss = perdida(mod(**enc).logits, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(mod.parameters(), 1.0)
                opt.step(); sch.step(); opt.zero_grad()
                paso += 1
                if self.medir is not None and paso >= self.medir:
                    raise MedicionLista((time.perf_counter() - t0) / paso, total, len(sub), self.epocas)
                if paso % 100 == 0:
                    s = (time.perf_counter() - t0) / paso
                    faltan = (total - epoca0 * pasos_epoca - paso) * s
                    print(f"  {ahora()} época {ep + 1}/{self.epocas} paso {paso:,} | {s:.2f} s/paso | "
                          f"pérdida {loss.item():.3f} | faltan ~{faltan / 3600:.1f} h", flush=True)
            ckpt.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"firma": self._firma(sub), "epoca": ep + 1, "modelo": mod.state_dict(), "opt": opt.state_dict(),
                        "sch": sch.state_dict(), "rng": torch.get_rng_state()}, ckpt)
            print(f"  {ahora()} época {ep + 1}/{self.epocas} completa (punto de control guardado)", flush=True)
        seg_ent = time.perf_counter() - t0
        seg_paso = seg_ent / max(paso, 1)
        meta = {
            "n_train_efectivo": len(sub), "modelo": self.modelo,
            "revision_tokenizador": self.rev_tok, "revision_pesos": self.rev_pesos,
            "commit_modelo": {"tokenizador": self.rev_tok, "pesos_safetensors": self.rev_pesos},
            "lr": LR, "batch": BATCH, "epocas": self.epocas, "max_len": MAX_LEN, "weight_decay": WEIGHT_DECAY,
            "warmup": WARMUP, "pesos_clase": "balanced", "hilos_cpu": self.hilos, "pasos": total,
            "pasos_ejecutados_esta_corrida": paso, "segundos_por_paso": round(seg_paso, 3),
            "segundos_entrenamiento": round(seg_ent, 1), "filas_truncadas_max_len": n_trunc,
            "torch": torch.__version__, "transformers": transformers.__version__,
            "costo": (f"BETO CPU {self.hilos} hilos: {len(sub):,} filas x {self.epocas} épocas = {total:,} pasos, "
                      f"{seg_paso:.2f} s/paso, {seg_ent / 3600:.2f} h de entrenamiento"),
        }
        return tok, mod, meta, ckpt

    def predecir(self, tok, mod, test: pd.DataFrame) -> np.ndarray:
        import torch
        mod.eval()
        tt = base.texto_entrada(test).tolist()
        preds = []
        with torch.no_grad():
            for enc in self._lotes(tok, tt, None, np.arange(len(tt))):
                preds.append(mod(**enc).logits.argmax(-1).numpy())
        return np.array(self.clases, dtype=object)[np.concatenate(preds)]

    # modo combinado (sanity): entrena y predice en la misma corrida
    def __call__(self, train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, dict]:
        sub = submuestra(train, self.n_train, base.SEMILLA)
        tok, mod, meta, ckpt = self.entrenar(sub)
        y_pred = self.predecir(tok, mod, test)
        ckpt.unlink(missing_ok=True)
        return y_pred, meta


# --------------------------------------------------------------------------- --solo-entrenar
def manifiesto_esperado(fuente: str, ruta_train: Path, sub: pd.DataFrame, brazo: BrazoBETO, clases: list[str]) -> dict:
    return {
        "fuente": fuente, "modelo_base": MODELO,
        "revision_tokenizador": brazo.rev_tok, "revision_pesos": brazo.rev_pesos,
        "semilla": base.SEMILLA, "n_train": len(sub), "epocas": brazo.epocas, "hilos_cpu": brazo.hilos,
        "lr": LR, "batch": BATCH, "max_len": MAX_LEN, "weight_decay": WEIGHT_DECAY, "warmup": WARMUP,
        "sintetico": {"ruta": ruta_train.as_posix(), "sha256": base.sha256(base.RAIZ / ruta_train)},
        "sha256_submuestra": base.sha256_texto(sub),
        "entrada": {"version": base.VERSION_ENTRADA, "formato": base.FORMATO_ENTRADA},
        "clases": clases, "taxonomia_version": base.VERSION_TAXONOMIA,
    }


def entrenar_fuente(fuente: str, ruta_train: Path, clases: list[str], args) -> dict:
    rechazar_data(ruta_train)
    train = base.cargar_tabla(ruta_train, clases, f"train:{fuente}")
    sub = submuestra(train, args.n_train, base.SEMILLA)
    brazo = BrazoBETO(clases, args.n_train, args.epocas, args.hilos)
    brazo.etiqueta_ckpt = f"beto_entrenar_{fuente}"
    esperado = manifiesto_esperado(fuente, ruta_train, sub, brazo, clases)
    destino = dir_modelo(fuente)
    if (destino / "manifiesto.json").exists() and not args.forzar:
        problemas = verificar_modelo(fuente, esperado)
        if not problemas:
            print(f"[{fuente}] ya existe un modelo válido en {destino.relative_to(base.RAIZ).as_posix()}; "
                  f"no se reentrena (usa --forzar para reentrenar)", flush=True)
            return {"estado": "ok", "reutilizado": True, "verificado_utc": ahora(),
                    "nota": "modelo existente verificado, no reentrenado"}
    print(f"[{fuente}] {ahora()} entrenando BETO sobre {len(sub):,} filas de {ruta_train} "
          f"({args.epocas} épocas, {args.hilos} hilos)", flush=True)
    tok, mod, meta, ckpt = brazo.entrenar(sub)
    destino.mkdir(parents=True, exist_ok=True)
    mod.save_pretrained(destino, safe_serialization=True)
    tok.save_pretrained(destino)
    man = esperado | {
        "sha256_pesos": base.sha256(destino / PESOS_ARCHIVO),
        "entrenamiento": {k: meta[k] for k in ("pasos", "segundos_por_paso", "segundos_entrenamiento",
                                               "filas_truncadas_max_len", "costo", "torch", "transformers")},
        "versiones": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "plataforma": platform.platform(), "fecha_utc": ahora(),
    }
    (destino / "manifiesto.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    ckpt.unlink(missing_ok=True)
    print(f"[{fuente}] {ahora()} listo: {destino.relative_to(base.RAIZ).as_posix()} · {meta['costo']}", flush=True)
    return {"estado": "ok", "costo": meta["costo"], "sha256_pesos": man["sha256_pesos"]}


def solo_entrenar(args, clases: list[str]) -> int:
    estado = leer_estado()
    fallos = 0
    for f in args.fuentes:
        ruta = base.FUENTES.get(f, Path(f))
        nombre = f if f in base.FUENTES else ruta.name.split(".")[0]
        previo = dict(estado.get(nombre, {}))
        estado[nombre] = {"estado": "en_curso", "inicio_utc": ahora(), "pid": os.getpid()}
        escribir_estado(estado)
        try:
            r = entrenar_fuente(nombre, ruta, clases, args)
            estado[nombre] = (previo | r) if r.get("reutilizado") and previo.get("estado") == "ok" \
                else estado[nombre] | r | {"fin_utc": ahora()}
        except Exception as e:                                   # sigue con la siguiente fuente
            fallos += 1
            estado[nombre] |= {"estado": "error", "fin_utc": ahora(), "error": f"{type(e).__name__}: {e}"}
            print(f"[{nombre}] ERROR\n{traceback.format_exc()}", file=sys.stderr, flush=True)
        escribir_estado(estado)
    print(f"{ahora()} FIN del entrenamiento: {json.dumps({k: v['estado'] for k, v in estado.items()}, ensure_ascii=False)}",
          flush=True)
    return 1 if fallos else 0


# --------------------------------------------------------------------------- verificación y --evaluar
CAMPOS_VERIFICADOS = ("modelo_base", "revision_tokenizador", "revision_pesos", "semilla", "n_train", "epocas",
                      "sintetico", "sha256_submuestra", "entrada", "clases", "taxonomia_version")


def verificar_modelo(fuente: str, esperado: dict | None = None) -> list[str]:
    """Lista de problemas (vacía = válido). Sin `esperado`, solo revisa integridad de archivos y del sintético."""
    d = dir_modelo(fuente)
    if not (d / "manifiesto.json").exists():
        return [f"falta {d.relative_to(base.RAIZ).as_posix()}/manifiesto.json"]
    man = json.loads((d / "manifiesto.json").read_text(encoding="utf-8"))
    prob = []
    if not (d / PESOS_ARCHIVO).exists():
        prob.append(f"faltan los pesos {PESOS_ARCHIVO}")
    elif base.sha256(d / PESOS_ARCHIVO) != man.get("sha256_pesos"):
        prob.append("el SHA-256 de los pesos no coincide con el manifiesto")
    ruta_sint = Path(man["sintetico"]["ruta"])
    if not (base.RAIZ / ruta_sint).exists():
        prob.append(f"no existe el sintético {ruta_sint}")
    elif base.sha256(base.RAIZ / ruta_sint) != man["sintetico"]["sha256"]:
        prob.append(f"el sintético {ruta_sint} cambió desde el entrenamiento")
    if man.get("revision_tokenizador") != REVISION_TOKENIZADOR or man.get("revision_pesos") != REVISION_PESOS:
        prob.append("revisiones del modelo base distintas de las fijadas en el código")
    if esperado:
        prob += [f"manifiesto: '{k}' no coincide" for k in CAMPOS_VERIFICADOS if man.get(k) != esperado.get(k)]
    return prob


def verificar(args) -> int:
    estado = leer_estado()
    ok = True
    for f in args.fuentes:
        e = estado.get(f, {})
        prob = verificar_modelo(f)
        man_ruta = dir_modelo(f) / "manifiesto.json"
        man = json.loads(man_ruta.read_text(encoding="utf-8")) if man_ruta.exists() else {}
        linea = (f"[{f}] estado={e.get('estado', 'sin registro')} inicio={e.get('inicio_utc', '-')} "
                 f"fin={e.get('fin_utc', '-')} n_train={man.get('n_train', '-')} "
                 f"{man.get('entrenamiento', {}).get('costo', '')}")
        print(linea)
        if e.get("estado") == "error":
            print(f"   error: {e.get('error')}")
        for p in prob:
            print(f"   PROBLEMA: {p}")
        ok &= e.get("estado") == "ok" and not prob
    print("TODO BIEN: los dos modelos están entrenados y verificados." if ok else "HAY PROBLEMAS (ver arriba).")
    return 0 if ok else 1


class BrazoBETOGuardado:
    """Brazo de evaluación: carga el modelo entrenado y solo predice. Verifica que la submuestra que reconstruye del
    sintético actual sea la del manifiesto (mismas filas que LogReg@20k)."""

    def __init__(self, fuente: str, clases: list[str]):
        self.fuente, self.clases = fuente, clases

    def __call__(self, train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, dict]:
        import torch
        import transformers
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        d = dir_modelo(self.fuente)
        man = json.loads((d / "manifiesto.json").read_text(encoding="utf-8"))
        sub = submuestra(train, man["n_train"], man["semilla"])
        if base.sha256_texto(sub) != man["sha256_submuestra"]:
            raise RuntimeError(f"[{self.fuente}] la submuestra reconstruida no coincide con la del manifiesto")
        fijar_semillas(base.SEMILLA, man["hilos_cpu"])
        tok = AutoTokenizer.from_pretrained(d)
        mod = AutoModelForSequenceClassification.from_pretrained(d, use_safetensors=True)
        if [mod.config.id2label[i] for i in range(len(self.clases))] != self.clases:
            raise RuntimeError(f"[{self.fuente}] las clases del modelo no coinciden con la taxonomía")
        t0 = time.perf_counter()
        y_pred = BrazoBETO(self.clases).predecir(tok, mod, test)
        return y_pred, {
            "n_train_efectivo": man["n_train"], "modelo": MODELO, "modelo_entrenado": d.relative_to(base.RAIZ).as_posix(),
            "sha256_pesos": man["sha256_pesos"], "revision_tokenizador": man["revision_tokenizador"],
            "revision_pesos": man["revision_pesos"], "epocas": man["epocas"], "hilos_cpu": man["hilos_cpu"],
            "entrenamiento": man["entrenamiento"], "segundos_prediccion": round(time.perf_counter() - t0, 1),
            "torch": torch.__version__, "transformers": transformers.__version__,
            "costo": man["entrenamiento"]["costo"] + " (entrenado aparte con --solo-entrenar)",
        }


def evaluar(args, clases: list[str], sha_tax: str) -> int:
    if args.test is None:
        sys.exit("--evaluar necesita --test (el modelo vio todo el sintético: no hay holdout sintético limpio)")
    for f in args.fuentes:
        prob = verificar_modelo(f)
        if prob:
            sys.exit(f"[{f}] el modelo no pasa la verificación: {'; '.join(prob)}. Corre --verificar.")
    for f in args.fuentes:
        base.correr(f, base.FUENTES[f], args.test, clases, sha_tax,
                    base.Brazo("beto", f"beto_{MODELO}", BrazoBETOGuardado(f, clases)), ic=args.ic)
    base.escribir_resultados_md(clases)
    return 0


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="BETO fine-tuning (entrenar / evaluar / sanity)")
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--solo-entrenar", action="store_true")
    modo.add_argument("--evaluar", action="store_true")
    modo.add_argument("--verificar", action="store_true")
    modo.add_argument("--medir", type=int, default=None, help="Cronometra N pasos y proyecta el costo; no escribe.")
    ap.add_argument("--fuentes", nargs="+", default=base.FUENTES_DEFECTO)
    ap.add_argument("--test", type=Path, default=None)
    ap.add_argument("--n-train", type=int, default=N_TRAIN_DEFECTO,
                    help="Filas de la submuestra estratificada (mismo valor para todas las fuentes).")
    ap.add_argument("--epocas", type=int, default=EPOCAS, choices=[3, 4])
    ap.add_argument("--hilos", type=int, default=HILOS_DEFECTO)
    ap.add_argument("--forzar", action="store_true", help="--solo-entrenar: reentrena aunque haya un modelo válido.")
    ap.add_argument("--ic", choices=base.MODOS_IC, default="ambos")
    args = ap.parse_args()

    if args.verificar:
        sys.exit(verificar(args))
    clases, sha_tax = base.cargar_taxonomia()
    if args.solo_entrenar:
        if args.test is not None:
            sys.exit("--solo-entrenar no acepta --test: el entrenamiento no lee el real")
        sys.exit(solo_entrenar(args, clases))
    if args.evaluar:
        sys.exit(evaluar(args, clases, sha_tax))

    # sanity combinado o --medir
    if args.test is not None:
        sys.exit("Para el TSTR usa --solo-entrenar y luego --evaluar --test.")
    for f in args.fuentes:
        ruta = base.FUENTES.get(f, Path(f))
        nombre = f if f in base.FUENTES else ruta.name.split(".")[0]
        brazo = BrazoBETO(clases, args.n_train, args.epocas, args.hilos, args.medir)
        brazo.etiqueta_ckpt = f"beto_sanity_{nombre}"
        try:
            base.correr(nombre, ruta, None, clases, sha_tax, base.Brazo("beto", f"beto_{MODELO}", brazo))
        except MedicionLista as m:
            print(f"[{nombre}] {m.seg_paso:.2f} s/paso con {args.hilos} hilos -> {m.n:,} filas x {m.epocas} épocas = "
                  f"{m.total:,} pasos ≈ {m.seg_paso * m.total / 3600:.1f} h por fuente "
                  f"(x{len(args.fuentes)} fuentes ≈ {m.seg_paso * m.total * len(args.fuentes) / 3600:.1f} h)")
            return
    base.escribir_resultados_md(clases)


if __name__ == "__main__":
    main()
