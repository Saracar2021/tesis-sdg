"""
Etapa 4 / WP8 — Brazo 3: LLM vía Groq, clasificación por prompting few-shot.

Mismo contrato, entrada, métricas, salidas y modos que tools/etapa4_tstr.py (lo importa):
  * sin --test -> SANITY CHECK (NO REPORTABLE) sobre una muestra estratificada del holdout (--max-test, 400).
  * con --test -> TSTR sobre el real anotado de WP4 (todas las filas).

Qué ve el modelo
  system : las 16 categoria_n1 (id + definición de una línea, de la taxonomía v1.1.0), la regla R1, el formato de la
           entrada y "responde solo la etiqueta".
  few-shot: 3 ejemplos por clase difícil, tomados del SINTÉTICO de entrenamiento (única vía por la que el sintético
           entra a este brazo) y solo de filas con fuente_etiqueta = texto (una fila etiquetada por declaración
           enseñaría que "PAGO A PERSONA" es educación). Clases difíciles fijadas a priori: las seis de menor F1 del
           baseline en el sanity (unión reglas ∪ CTGAN), antes de ver el real.
  user   : la MISMA serialización canónica de los tres brazos (etapa4_tstr.serializar).
Parámetros: temperature 0, seed 42; modelos de razonamiento (gpt-oss): reasoning_effort "low", razonamiento oculto.
Parseo: etiqueta exacta del enum; si no, la única etiqueta del enum contenida en la respuesta; si no, 'otros'
(se cuentan fuera_de_enum y vacías).

Modelo. Se pide llama-3.3-70b-versatile; Groq lo retiró de las cuentas free/developer el 16-ago-2026. Si /models no lo
ofrece a esta cuenta se usa --modelo-sustituto (por defecto openai/gpt-oss-120b, el mismo sustituto de WP5) y la
DESVIACIÓN queda en metricas.json y en docs/resultados_tstr.md.

Reproducibilidad. La API no es determinista aunque temperature=0: cada respuesta cruda se guarda en
outputs/tstr/llm_cache/<modelo>.jsonl con la huella de (modelo, system, few-shot, entrada, parámetros), y una corrida
repetida sale de ese registro sin llamar a la API. Entradas idénticas se consultan una sola vez.

Llave: GROQ_API_KEY en .env (python-dotenv). Nunca se imprime ni se guarda.

DATOS REALES. En TSTR las descripciones de los voluntarios salen a un tercero (Groq, EE. UU.): exige
--autorizo-envio-real (consentimiento informado y Ley 1581 de 2012) y el registro se guarda en data/_privado/llm_cache/
(data/ está ignorado por git), nunca en outputs/. Las predicciones de outputs/tstr/ solo llevan etiquetas.

Uso (desde la raíz del repo, entorno .venv):
  .venv/Scripts/python tools/etapa4_llm.py --max-test 40            # prueba de humo (sanity, 2 fuentes)
  .venv/Scripts/python tools/etapa4_llm.py                          # sanity (400 filas por fuente)
  .venv/Scripts/python tools/etapa4_llm.py --test data/reales_anon/<real>.csv --autorizo-envio-real   # TSTR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import etapa4_tstr as base  # noqa: E402

MODELO_PEDIDO = "llama-3.3-70b-versatile"
SUSTITUTO_DEFECTO = "openai/gpt-oss-120b"
URL_GROQ = "https://api.groq.com/openai/v1"
CLASES_DIFICILES = ["otros", "hogar_articulos", "educacion", "transferencias_p2p", "ingreso", "vivienda_servicios"]
N_EJEMPLOS_POR_CLASE = 3
MAX_TEST_SANITY = 400
PAUSA_DEFECTO = 2.1          # ≈ 28 solicitudes/min, bajo el límite típico de 30 RPM del plan gratuito
MAX_TOKENS = {"razonamiento": 512, "normal": 16}
REINTENTOS = 6
CACHE = Path("outputs/tstr/llm_cache")            # sanity: entradas sintéticas, se versiona
CACHE_PRIVADO = Path("data/_privado/llm_cache")   # TSTR: entradas REALES de WP4; data/ está ignorado por git


# --------------------------------------------------------------------------- prompt
def _una_linea(txt: str, max_c: int = 160) -> str:
    t = " ".join(str(txt).split())
    t = t.split(". ")[0].rstrip(".")
    return t if len(t) <= max_c else t[: max_c - 1].rstrip() + "…"


def prompt_sistema(clases: list[str]) -> str:
    tax = json.loads((base.RAIZ / base.TAXONOMIA).read_text(encoding="utf-8"))
    por_id = {c["id"]: c for c in tax["categorias_nivel_1"]}
    r1 = next(r["regla"] for r in tax["reglas_de_decision"] if r["id"] == "R1")
    lineas = "\n".join(f"- {c}: {_una_linea(por_id[c]['definicion'])}" for c in clases)
    return (
        "Clasificas movimientos de extractos bancarios y de billeteras digitales de hogares colombianos en UNA de "
        "estas 16 categorías (taxonomía v1.1.0):\n"
        f"{lineas}\n\n"
        f"Regla R1: {r1}\n\n"
        "Formato de la entrada: [CUENTA=banco|billetera|tarjeta_credito] [SIGNO=- salida de dinero | + entrada] "
        "[MONTO=rango en pesos colombianos de 2025, K=miles, M=millones] seguido de la descripción del movimiento.\n\n"
        "Responde SOLO con el identificador exacto de la categoría (por ejemplo: comidas_fuera), sin explicación."
    )


def ejemplos_few_shot(train: pd.DataFrame, semilla: int = base.SEMILLA) -> list[tuple[str, str]]:
    """3 ejemplos por clase difícil, del sintético, solo etiqueta-por-texto, entradas distintas, deterministas."""
    t = train
    if "fuente_etiqueta" in t.columns:
        t = t[t["fuente_etiqueta"].astype(str) == base.ETIQUETA_TEXTO]
    t = t.assign(_entrada=base.serializar(t))
    rng = np.random.default_rng(semilla)
    out = []
    for c in CLASES_DIFICILES:
        cand = np.array(sorted(set(t.loc[t[base.TARGET] == c, "_entrada"])), dtype=object)
        if len(cand) == 0:
            continue
        sel = rng.choice(len(cand), size=min(N_EJEMPLOS_POR_CLASE, len(cand)), replace=False)
        out += [(cand[i], c) for i in sorted(sel)]
    return out


def mensajes(sistema: str, shots: list[tuple[str, str]], entrada: str) -> list[dict]:
    m = [{"role": "system", "content": sistema}]
    for x, y in shots:
        m += [{"role": "user", "content": x}, {"role": "assistant", "content": y}]
    return m + [{"role": "user", "content": entrada}]


# --------------------------------------------------------------------------- parseo
def parsear(contenido: str | None, clases: list[str]) -> tuple[str, str]:
    """(etiqueta, estado) con estado en exacta | contenida | fuera_de_enum | vacia."""
    if not contenido or not str(contenido).strip():
        return base.CLASE_RESIDUAL, "vacia"
    t = str(contenido).strip().strip("`'\".:;, \n").lower()
    if t in clases:
        return t, "exacta"
    hallados = {c for c in clases if re.search(rf"(?<![a-z_]){re.escape(c)}(?![a-z_])", t)}
    if len(hallados) == 1:
        return hallados.pop(), "contenida"
    return base.CLASE_RESIDUAL, "fuera_de_enum"


# --------------------------------------------------------------------------- API
class ClienteGroq:
    def __init__(self, llave: str, url: str, pausa: float):
        self.llave, self.url, self.pausa = llave, url.rstrip("/"), pausa
        self._ultimo = 0.0

    def _pedir(self, ruta: str, cuerpo: dict | None = None) -> tuple[int, dict, float]:
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        req = urllib.request.Request(f"{self.url}{ruta}", data=datos, method="POST" if datos else "GET", headers={
            "Authorization": f"Bearer {self.llave}", "Content-Type": "application/json",
            "User-Agent": "tesis-sdg-wp8/1.0"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read().decode("utf-8")), time.time() - t0
        except urllib.error.HTTPError as e:
            try:
                cuerpo_err = json.loads(e.read().decode("utf-8"))
            except ValueError:
                cuerpo_err = {}
            cuerpo_err["_retry_after"] = e.headers.get("retry-after")
            return e.code, cuerpo_err, time.time() - t0

    def modelos(self) -> list[str]:
        st, d, _ = self._pedir("/models")
        if st != 200:
            sys.exit(f"Groq /models respondió {st}: {str(d.get('error', d))[:200]}")
        return sorted(m["id"] for m in d.get("data", []))

    def completar(self, cuerpo: dict) -> tuple[int, dict, float]:
        for intento in range(REINTENTOS):
            espera = self.pausa - (time.time() - self._ultimo)
            if espera > 0:
                time.sleep(espera)
            st, d, seg = self._pedir("/chat/completions", cuerpo)
            self._ultimo = time.time()
            if st == 200 or st not in (408, 409, 429, 500, 502, 503, 504):
                return st, d, seg
            ra = d.get("_retry_after")
            time.sleep(float(ra) if ra and str(ra).replace(".", "", 1).isdigit() else min(60, 2 ** (intento + 1)))
        return st, d, seg


# --------------------------------------------------------------------------- brazo
class BrazoLLM:
    def __init__(self, clases, cliente: ClienteGroq, modelo: str, desviacion: str | None, privado: bool = False):
        self.clases, self.cliente, self.modelo, self.desviacion = clases, cliente, modelo, desviacion
        self.dir_cache = CACHE_PRIVADO if privado else CACHE
        self.razonamiento = modelo.startswith("openai/gpt-oss")

    def _parametros(self) -> dict:
        p = {"temperature": 0, "seed": base.SEMILLA,
             "max_completion_tokens": MAX_TOKENS["razonamiento" if self.razonamiento else "normal"]}
        if self.razonamiento:
            p.update({"reasoning_effort": "low", "include_reasoning": False})
        return p

    def __call__(self, train: pd.DataFrame, test: pd.DataFrame) -> tuple[np.ndarray, dict]:
        sistema = prompt_sistema(self.clases)
        shots = ejemplos_few_shot(train)
        params = self._parametros()
        entradas = base.serializar(test).to_numpy(dtype=object)
        unicas = sorted(set(entradas))

        ruta_cache = base.RAIZ / self.dir_cache / f"{re.sub(r'[^A-Za-z0-9._-]+', '_', self.modelo)}.jsonl"
        ruta_cache.parent.mkdir(parents=True, exist_ok=True)
        cache = {}
        if ruta_cache.exists():
            for linea in ruta_cache.read_text(encoding="utf-8").splitlines():
                r = json.loads(linea)
                cache[r["clave"]] = r

        def clave(x: str) -> str:
            return hashlib.sha256(json.dumps({"modelo": self.modelo, "sistema": sistema, "shots": shots, "entrada": x,
                                              "params": params}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

        resp, nuevas, fallos, tokens = {}, 0, 0, {"prompt": 0, "completion": 0}
        with ruta_cache.open("a", encoding="utf-8") as reg:
            for i, x in enumerate(unicas):
                k = clave(x)
                if k in cache:
                    resp[x] = cache[k]["contenido"]
                    continue
                st, d, seg = self.cliente.completar({"model": self.modelo, "messages": mensajes(sistema, shots, x), **params})
                nuevas += 1
                if st != 200:
                    fallos += 1
                    resp[x] = None
                    if nuevas == 20 and fallos > 4:
                        sys.exit(f"Abortado: {fallos}/20 llamadas fallaron (último HTTP {st}: {str(d.get('error', d))[:200]})")
                    continue
                cont = (d.get("choices") or [{}])[0].get("message", {}).get("content")
                uso = d.get("usage", {}) or {}
                tokens["prompt"] += int(uso.get("prompt_tokens", 0) or 0)
                tokens["completion"] += int(uso.get("completion_tokens", 0) or 0)
                fila = {"clave": k, "modelo": self.modelo, "modelo_respuesta": d.get("model"), "entrada": x,
                        "contenido": cont, "usage": uso, "segundos": round(seg, 3),
                        "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                reg.write(json.dumps(fila, ensure_ascii=False) + "\n")
                reg.flush()
                resp[x] = cont
                if nuevas % 50 == 0:
                    print(f"  {i + 1:,}/{len(unicas):,} entradas únicas | {nuevas:,} llamadas nuevas | {fallos} fallos",
                          flush=True)

        parse = {x: parsear(resp[x], self.clases) for x in unicas}
        y_pred = np.array([parse[x][0] for x in entradas], dtype=object)
        estados = pd.Series([parse[x][1] for x in entradas]).value_counts().to_dict()
        return y_pred, {
            "n_train_efectivo": len(shots), "modelo_pedido": MODELO_PEDIDO, "modelo": self.modelo,
            "desviacion": self.desviacion, "parametros": params, "clases_dificiles": CLASES_DIFICILES,
            "n_ejemplos_few_shot": len(shots), "few_shot": [{"entrada": x, "etiqueta": y} for x, y in shots],
            "sha256_system": hashlib.sha256(sistema.encode()).hexdigest(), "regla_incluida": "R1",
            "entradas_unicas": len(unicas), "llamadas_nuevas": nuevas, "respuestas_de_registro": len(unicas) - nuevas,
            "llamadas_fallidas": fallos, "estado_parseo_filas": {k: int(v) for k, v in estados.items()},
            "tokens_llamadas_nuevas": tokens, "registro": (self.dir_cache / ruta_cache.name).as_posix(),
            "costo": (f"{self.modelo}: {len(unicas):,} entradas únicas, {nuevas:,} llamadas nuevas, "
                      f"{tokens['prompt'] + tokens['completion']:,} tokens"
                      + (f"; DESVIACIÓN: {self.desviacion}" if self.desviacion else "")),
        }


def muestra_estratificada(test: pd.DataFrame, n: int) -> pd.DataFrame:
    if n >= len(test):
        return test
    from sklearn.model_selection import train_test_split
    sub, _ = train_test_split(test, train_size=n, stratify=test[base.TARGET], random_state=base.SEMILLA)
    return sub.sort_index()


def cargar_llave() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv(base.RAIZ / ".env")
    except ImportError:
        pass
    llave = os.environ.get("GROQ_API_KEY", "").strip()
    if not llave:
        sys.exit("Falta GROQ_API_KEY en .env (no la pegues en el chat ni la subas a git).")
    return llave


def main() -> None:
    ap = argparse.ArgumentParser(description="LLM vía Groq, prompting few-shot (TSTR / sanity)")
    ap.add_argument("--fuentes", nargs="+", default=base.FUENTES_DEFECTO)
    ap.add_argument("--test", type=Path, default=None)
    ap.add_argument("--max-test", type=int, default=None,
                    help=f"Filas de test (muestra estratificada). Sanity: {MAX_TEST_SANITY} por defecto; TSTR: todas.")
    ap.add_argument("--modelo-sustituto", default=SUSTITUTO_DEFECTO)
    ap.add_argument("--pausa", type=float, default=PAUSA_DEFECTO, help="segundos mínimos entre llamadas")
    ap.add_argument("--autorizo-envio-real", action="store_true",
                    help="Obligatorio con --test: confirma que el consentimiento de los voluntarios y la política de "
                         "datos cubren enviar sus descripciones (anonimizadas) a una API externa (Groq, EE. UU.).")
    args = ap.parse_args()
    if args.test is not None and not args.autorizo_envio_real:
        sys.exit("TSTR con LLM envía las descripciones REALES de WP4 a Groq (tercero, fuera de Colombia). Verifica que "
                 "el consentimiento informado y la Ley 1581 de 2012 lo cubran y relanza con --autorizo-envio-real. "
                 f"Las respuestas se guardan en {CACHE_PRIVADO.as_posix()} (ignorado por git), no en outputs/.")

    cliente = ClienteGroq(cargar_llave(), os.environ.get("GROQ_BASE_URL", URL_GROQ), args.pausa)
    disponibles = cliente.modelos()
    if MODELO_PEDIDO in disponibles:
        modelo, desviacion = MODELO_PEDIDO, None
    elif args.modelo_sustituto in disponibles:
        modelo = args.modelo_sustituto
        desviacion = f"{MODELO_PEDIDO} no disponible para esta cuenta (retirado por Groq 16-ago-2026); sustituido por {modelo}"
    else:
        sys.exit(f"Ni {MODELO_PEDIDO} ni {args.modelo_sustituto} están disponibles: {disponibles[:20]}")
    print(f"Modelo: {modelo}" + (f"  (DESVIACIÓN: {desviacion})" if desviacion else ""), flush=True)

    max_test = args.max_test if args.max_test is not None else (None if args.test else MAX_TEST_SANITY)
    clases, sha_tax = base.cargar_taxonomia()
    brazo_obj = BrazoLLM(clases, cliente, modelo, desviacion, privado=args.test is not None)

    for f in args.fuentes:
        ruta = base.FUENTES.get(f, Path(f))
        nombre = f if f in base.FUENTES else ruta.name.split(".")[0]
        base.correr(nombre, ruta, args.test, clases, sha_tax,
                    base.Brazo("llm_groq", f"llm_groq_{modelo}", brazo_obj),
                    recorte_test=(lambda t: muestra_estratificada(t, max_test)) if max_test else None)
    base.escribir_resultados_md(clases)


if __name__ == "__main__":
    main()
