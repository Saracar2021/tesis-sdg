"""WP5 — Corrida acotada y reproducible de la etapa 4 (enriquecimiento con LLM) del pipeline de referencia.

Ejecuta SU generador `TransactionGenerator` (src/Data_Synthesizer/code/transaction_deepseek_synthesizer.py, commit
fijado) sin editar su código. Parches en memoria (tools/pancholi_parches/README.md):
  P3  su `from config import API_KEY_Groq` apunta a un archivo retirado del repo ("Removed API keys"): se inyecta un
      módulo `config` cuyo valor sale de GROQ_API_KEY en .env (python-dotenv). La llave nunca se imprime ni se guarda.
  P4  su modelo (`llama-3.3-70b-versatile`) se pidió en el código; si /models no lo ofrece a esta cuenta, se sustituye
      por --modelo-sustituto (desviación declarada). Para modelos de razonamiento (gpt-oss) se añade
      reasoning_effort="low" para que el razonamiento no agote su max_tokens=500.
Semillas: random.seed y np.random.seed (selección de subcategorías y comercios); su load_data ya usa random_state=42.
El LLM no es determinista: cada respuesta cruda se guarda en llamadas.jsonl, y el análisis parte de ese archivo,
así que es reproducible desde los registros aunque la API no lo sea.

Uso (desde la raíz del repo, en .venv-pancholi con pandas==2.2.3 numpy==2.2.3 requests==2.32.3 geopy==2.4.1
python-dotenv==1.0.1; pandas >= 3 rompe su caché de comercios y el script aborta):
  python tools/pancholi_etapa4.py --n 300            # ~1 h con su pausa de 10 s
  python tools/pancholi_etapa4.py --n 20 --pausa 1   # prueba de humo
Salida: outputs/pancholi/etapa4/{transacciones_etapa4.csv, llamadas.jsonl, manifest_etapa4.json}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CLON = RAIZ / "external" / "pancholi"
URL_REPO = "https://github.com/aman-jaglan/Capstone_Project.git"
COMMIT = "d0a61e783353f52123b1821bc1876824d608d2a1"
CODIGO = CLON / "src" / "Data_Synthesizer" / "code"
DATOS = CLON / "src" / "Data_Synthesizer" / "data"
SALIDA = RAIZ / "outputs" / "pancholi" / "etapa4"
MODELO_ORIGINAL = "llama-3.3-70b-versatile"
URL_GROQ = "https://api.groq.com/openai/v1"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def preparar_clon() -> None:
    if not CLON.exists():
        CLON.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "-q", URL_REPO, str(CLON))
    if git("-C", str(CLON), "rev-parse", "HEAD") != COMMIT:
        git("-C", str(CLON), "checkout", "-q", COMMIT)
    if git("-C", str(CLON), "rev-parse", "HEAD") != COMMIT:
        raise SystemExit("No se pudo fijar el commit del clon")
    if git("-C", str(CLON), "status", "--porcelain"):
        raise SystemExit("El clon tiene cambios locales: no se ejecuta sobre código modificado")


def cargar_llave() -> str:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    llave = os.environ.get("GROQ_API_KEY", "").strip()
    if not llave:
        raise SystemExit("Falta GROQ_API_KEY en .env")
    return llave


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="transacciones objetivo (su __main__ usa 1000)")
    ap.add_argument("--semilla", type=int, default=42)
    ap.add_argument("--pausa", type=float, default=10.0, help="segundos entre llamadas (su valor: 10)")
    ap.add_argument("--modelo-sustituto", default="openai/gpt-oss-120b",
                    help="si su modelo no está disponible (Groq lo retiró de free/developer el 16-ago-2026)")
    ap.add_argument("--max-fallos-iniciales", type=float, default=0.5,
                    help="aborta si falla más de esta fracción de las primeras 20 llamadas (control de costo)")
    a = ap.parse_args()

    import numpy as np
    import pandas as pd_v
    import requests

    # Su requirements fija pandas==2.2.3. Con pandas >= 3, groupby().apply() excluye las columnas de agrupación y su
    # merchant_cache pierde 'mapped_category' (KeyError antes de llamar a la API): se aborta antes de gastar llamadas.
    if not pd_v.__version__.startswith("2.2."):
        raise SystemExit(f"pandas {pd_v.__version__} no es compatible con su código (fija 2.2.3). Usa .venv-pancholi: "
                         "pip install pandas==2.2.3 numpy==2.2.3 requests==2.32.3 geopy==2.4.1 python-dotenv==1.0.1")

    preparar_clon()
    llave = cargar_llave()
    base = os.environ.get("PANCHOLI_GROQ_BASE_URL", URL_GROQ)   # solo para pruebas con servidor simulado
    SALIDA.mkdir(parents=True, exist_ok=True)

    # --- P4: elegir modelo según lo que la cuenta realmente ofrece
    r = requests.get(f"{base}/models", headers={"Authorization": f"Bearer {llave}"}, timeout=30)
    r.raise_for_status()
    disponibles = sorted(m["id"] for m in r.json().get("data", []))
    if MODELO_ORIGINAL in disponibles:
        modelo, desviacion = MODELO_ORIGINAL, None
    elif a.modelo_sustituto in disponibles:
        modelo, desviacion = a.modelo_sustituto, f"{MODELO_ORIGINAL} no disponible para esta cuenta; sustituido por {a.modelo_sustituto}"
    else:
        raise SystemExit(f"Ni {MODELO_ORIGINAL} ni {a.modelo_sustituto} están disponibles: {disponibles[:20]}")
    print(f"Modelo: {modelo}" + (f"  (DESVIACIÓN: {desviacion})" if desviacion else ""), flush=True)

    # --- P3: módulo config en memoria
    sys.modules["config"] = types.SimpleNamespace(API_KEY_Groq=llave)
    sys.path.insert(0, str(CODIGO))
    import transaction_deepseek_synthesizer as tds   # noqa: E402  (su módulo, sin editar)

    registro = (SALIDA / "llamadas.jsonl").open("w", encoding="utf-8")
    estado = {"llamadas": 0, "fallos": 0, "prompt_tokens": 0, "completion_tokens": 0}
    post_original = requests.post

    def post_registrado(url, headers=None, json=None, timeout=None, **kw):   # noqa: A002
        cuerpo = dict(json)
        cuerpo["model"] = modelo                                   # P4
        if modelo.startswith("openai/gpt-oss"):
            cuerpo["reasoning_effort"] = "low"                     # P4b
        url = url.replace(URL_GROQ, base)
        t0 = time.time()
        resp = post_original(url, headers=headers, json=cuerpo, timeout=timeout, **kw)
        estado["llamadas"] += 1
        try:
            datos = resp.json()
        except ValueError:
            datos = {"texto_no_json": resp.text[:2000]}
        uso = datos.get("usage", {}) if isinstance(datos, dict) else {}
        estado["prompt_tokens"] += int(uso.get("prompt_tokens", 0) or 0)
        estado["completion_tokens"] += int(uso.get("completion_tokens", 0) or 0)
        contenido = None
        try:
            contenido = datos["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            pass
        registro.write(json_mod.dumps({
            "i": estado["llamadas"], "http": resp.status_code, "segundos": round(time.time() - t0, 3),
            "modelo": modelo, "prompt": cuerpo["messages"][1]["content"], "contenido": contenido,
            "usage": uso, "error": None if resp.ok else datos}, ensure_ascii=False) + "\n")
        registro.flush()
        return resp

    json_mod = json
    tds.requests.post = post_registrado

    # control de costo: si las primeras llamadas fallan masivamente, abortar en lugar de gastar el lote completo
    gen_original = tds.TransactionGenerator._generate_transactions_api

    def gen_controlado(self, customer, merchant):
        try:
            return gen_original(self, customer, merchant)
        except Exception:
            estado["fallos"] += 1
            if estado["llamadas"] >= 20 and estado["fallos"] / estado["llamadas"] > a.max_fallos_iniciales and estado["llamadas"] <= 40:
                registro.close()
                raise SystemExit(f"Abortado: {estado['fallos']}/{estado['llamadas']} llamadas fallidas")
            raise

    tds.TransactionGenerator._generate_transactions_api = gen_controlado
    pausa_original = tds.time.sleep
    tds.time = types.SimpleNamespace(**{k: getattr(time, k) for k in dir(time) if not k.startswith("_")})
    tds.time.sleep = lambda s: pausa_original(a.pausa)

    random.seed(a.semilla)
    np.random.seed(a.semilla)
    t0 = time.time()
    g = tds.TransactionGenerator(api_key=llave)
    g.load_data(customers_path=str(DATOS / "synthetic_customer_gan.csv"),
                merchants_path=str(DATOS / "dc_businesses_cleaned.csv"))
    salida_csv = SALIDA / "transacciones_etapa4.csv"
    g.generate_transactions(str(salida_csv), target=a.n)
    registro.close()
    dur = time.time() - t0

    # subcategoría pedida en cada prompt (para comparar con la que devuelve el LLM)
    import pandas as pd
    out = pd.read_csv(salida_csv) if salida_csv.stat().st_size > 1 else pd.DataFrame()
    man = {
        "descripcion": "WP5 — etapa 4 del pipeline de referencia (enriquecimiento con LLM), corrida acotada",
        "repositorio": {"url": URL_REPO, "commit": COMMIT},
        "script": "src/Data_Synthesizer/code/transaction_deepseek_synthesizer.py (TransactionGenerator)",
        "parches": ["P3 config en memoria desde .env", "P4 sustitución de modelo si no está disponible",
                    "P4b reasoning_effort=low solo para gpt-oss"],
        "modelo_codigo": MODELO_ORIGINAL, "modelo_usado": modelo, "desviacion_modelo": desviacion,
        "modelos_disponibles_cuenta": disponibles,
        "parametros": {"n_objetivo": a.n, "semilla": a.semilla, "pausa_s": a.pausa, "temperatura": 0.5,
                       "max_tokens": 500, "clientes": 25, "random_state_clientes": 42,
                       "clientes_archivo": "synthetic_customer_gan.csv"},
        "resultado": {"llamadas": estado["llamadas"], "fallos": estado["fallos"], "filas_salida": len(out),
                      "prompt_tokens": estado["prompt_tokens"], "completion_tokens": estado["completion_tokens"],
                      "minutos": dur / 60},
        "sha256": {p.name: sha256(p) for p in [salida_csv, SALIDA / "llamadas.jsonl"] if p.exists()},
        "entorno": {"python": sys.version.split()[0], "plataforma": platform.platform(),
                    "pandas": pd.__version__, "numpy": np.__version__, "requests": requests.__version__},
        "simulado": base != URL_GROQ,
    }
    (SALIDA / "manifest_etapa4.json").write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(man["resultado"], indent=1), flush=True)


if __name__ == "__main__":
    main()
