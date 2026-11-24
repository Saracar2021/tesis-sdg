"""
Etapa 4 / WP8 — Brazo 2: BETO (dccuchile/bert-base-spanish-wwm-cased), fine-tuning en CPU.

Mismo contrato, métricas, salidas y modos que tools/etapa4_tstr.py (lo importa):
  * sin --test -> SANITY CHECK (NO REPORTABLE), mismo holdout 80/20 y semilla que el baseline.
  * con --test -> TSTR: entrena sobre el sintético, evalúa sobre el real de WP4.
Fuentes por defecto: reglas y ctgan (ablación con las mismas plantillas de texto).

Entrada del modelo: la serialización canónica de etapa4_tstr.serializar (la MISMA de los tres brazos):
"[CUENTA=..] [SIGNO=..] [MONTO=<bin>] <descripcion>". Nunca columnas de anotación.

Hiperparámetros fijados ANTES de ver el test (no hay validación ni early stopping, no se ajusta nada):
  lr 2e-5, batch 16, 3 épocas, max_len 64, AdamW (weight_decay 0.01), warmup lineal 10 %,
  pérdida con pesos de clase 'balanced' (como el baseline), semilla 42.

COSTO EN CPU. El train completo (122.211 filas x 3 épocas = ~23.000 pasos) no cabe en el plazo: se
entrena sobre una SUBMUESTRA estratificada por categoria_n1 (--n-train, por defecto 20.000), con la misma
semilla y el mismo tamaño para las dos fuentes, de modo que la ablación sigue siendo pareja. El número de
filas, los pasos, los segundos por paso y el total quedan en metricas.json y en docs/resultados_tstr.md.
Con --medir N se cronometran N pasos y se proyecta el costo sin escribir resultados.

Modelo: revisiones fijas REVISION_TOKENIZADOR (main) y REVISION_PESOS (refs/pr/3, safetensors); ver abajo.
Uso (desde la raíz del repo, entorno .venv-ctgan; la primera vez descarga ~440 MB de Hugging Face):
  .venv-ctgan/Scripts/python tools/etapa4_beto.py --medir 30          # cronometrar y proyectar
  .venv-ctgan/Scripts/python tools/etapa4_beto.py                     # sanity, reglas y ctgan
  .venv-ctgan/Scripts/python tools/etapa4_beto.py --test data/reales_anon/<real>.csv   # TSTR
Reanudable: al final de cada época guarda un punto de control en outputs/tstr/_ckpt/ (ignorado por git);
si la corrida se corta, relanzar el mismo comando continúa desde la última época completa.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
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


class BrazoBETO:
    def __init__(self, clases: list[str], n_train: int, epocas: int, hilos: int,
                 medir: int | None = None, modelo: str = MODELO,
                 revision_tokenizador: str = REVISION_TOKENIZADOR, revision_pesos: str = REVISION_PESOS):
        self.clases, self.n_train, self.epocas, self.hilos = clases, n_train, epocas, hilos
        self.medir, self.modelo = medir, modelo
        self.rev_tok, self.rev_pesos = revision_tokenizador, revision_pesos
        self.revision = f"tok={revision_tokenizador[:12]},pesos={revision_pesos[:12]}"
        self.etiqueta_ckpt = "sin_ckpt"

    # --------------------------------------------------------------------- carga
    def _cargar(self):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        k = len(self.clases)
        tok = AutoTokenizer.from_pretrained(self.modelo, revision=self.rev_tok)
        mod = AutoModelForSequenceClassification.from_pretrained(
            self.modelo, revision=self.rev_pesos, use_safetensors=True, num_labels=k,
            id2label=dict(enumerate(self.clases)), label2id={c: i for i, c in enumerate(self.clases)})
        return tok, mod

    def _lotes(self, tok, textos: list[str], y: np.ndarray | None, orden: np.ndarray):
        import torch
        for i in range(0, len(orden), BATCH if y is not None else BATCH_PRED):
            j = orden[i:i + (BATCH if y is not None else BATCH_PRED)]
            enc = tok([textos[t] for t in j], padding=True, truncation=True, max_length=MAX_LEN, return_tensors="pt")
            if y is not None:
                enc["labels"] = torch.as_tensor(y[j], dtype=torch.long)
            yield enc

    # --------------------------------------------------------------------- brazo
    def __call__(self, train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, dict]:
        import torch
        import transformers
        from transformers import get_linear_schedule_with_warmup

        fijar_semillas(base.SEMILLA, self.hilos)
        sub = submuestra(train, self.n_train, base.SEMILLA)
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
                print(f"  reanudando desde el final de la época {epoca0}")

        mod.train()
        t0, paso, seg_paso = time.perf_counter(), 0, None
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
                    seg_paso = (time.perf_counter() - t0) / paso
                    raise MedicionLista(seg_paso, total, len(sub), self.epocas)
                if paso % 100 == 0:
                    s = (time.perf_counter() - t0) / paso
                    faltan = (total - epoca0 * pasos_epoca - paso) * s
                    print(f"  época {ep + 1}/{self.epocas} paso {paso:,} | {s:.2f} s/paso | pérdida {loss.item():.3f} "
                          f"| faltan ~{faltan / 3600:.1f} h", flush=True)
            ckpt.parent.mkdir(parents=True, exist_ok=True)
            torch.save({"firma": self._firma(sub), "epoca": ep + 1, "modelo": mod.state_dict(), "opt": opt.state_dict(),
                        "sch": sch.state_dict(), "rng": torch.get_rng_state()}, ckpt)
        seg_ent = time.perf_counter() - t0
        seg_paso = seg_ent / max(paso, 1)

        mod.eval()
        tt = base.texto_entrada(test).tolist()
        preds = []
        with torch.no_grad():
            for enc in self._lotes(tok, tt, None, np.arange(len(tt))):
                preds.append(mod(**enc).logits.argmax(-1).numpy())
        y_pred = np.array(self.clases, dtype=object)[np.concatenate(preds)]
        ckpt.unlink(missing_ok=True)       # corrida completa: el punto de control ya no hace falta

        return y_pred, {
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

    def _firma(self, sub: pd.DataFrame) -> str:
        return f"{len(sub)}|{self.epocas}|{self.hilos}|{self.revision}|{base.sha256_texto(sub)}"


class MedicionLista(Exception):
    def __init__(self, seg_paso, total, n, epocas):
        self.seg_paso, self.total, self.n, self.epocas = seg_paso, total, n, epocas


def main() -> None:
    ap = argparse.ArgumentParser(description="BETO fine-tuning (TSTR / sanity)")
    ap.add_argument("--fuentes", nargs="+", default=base.FUENTES_DEFECTO)
    ap.add_argument("--test", type=Path, default=None)
    ap.add_argument("--n-train", type=int, default=N_TRAIN_DEFECTO,
                    help="Filas de la submuestra estratificada (mismo valor para todas las fuentes).")
    ap.add_argument("--epocas", type=int, default=EPOCAS, choices=[3, 4])
    ap.add_argument("--hilos", type=int, default=HILOS_DEFECTO)
    ap.add_argument("--medir", type=int, default=None, help="Cronometra N pasos y proyecta el costo; no escribe.")
    args = ap.parse_args()

    clases, sha_tax = base.cargar_taxonomia()
    for f in args.fuentes:
        ruta = base.FUENTES.get(f, Path(f))
        nombre = f if f in base.FUENTES else ruta.name.split(".")[0]
        brazo = BrazoBETO(clases, args.n_train, args.epocas, args.hilos, args.medir)
        brazo.etiqueta_ckpt = f"beto_{'tstr' if args.test else 'sanity'}_{nombre}"
        try:
            base.correr(nombre, ruta, args.test, clases, sha_tax, base.Brazo("beto", f"beto_{MODELO}", brazo))
        except MedicionLista as m:
            print(f"[{nombre}] {m.seg_paso:.2f} s/paso con {args.hilos} hilos -> {m.n:,} filas x {m.epocas} épocas = "
                  f"{m.total:,} pasos ≈ {m.seg_paso * m.total / 3600:.1f} h por fuente "
                  f"(x{len(args.fuentes)} fuentes ≈ {m.seg_paso * m.total * len(args.fuentes) / 3600:.1f} h)")
            return
    base.escribir_resultados_md(clases)


if __name__ == "__main__":
    main()
