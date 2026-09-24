"""WP5 — Ejecución reproducible del pipeline de referencia (Pancholi et al., etapas 1-3).

No edita el clon: verifica commit y árbol limpio, aplica el parche P1 en memoria e importa sus clases.
Diseños (ver docs/prerregistro_wp5.md):
  A  rejilla de ingreso, etapas 2+3, semillas 42-51
  R  repetición de A con semilla 42 (verificación de reproducibilidad)
  B  réplica literal de src/Data_Synthesizer/code/transaction_synthesizer.py, semillas 42-51
  C  etapa 1 reentrenada (AdvancedIncomeModel) + etapas 2+3 sobre 155 clientes suyos, semilla 42
Cada corrida escribe crudo/<id>.hecho.json; si existe, se salta (reanudable).
Uso:  python tools/pancholi_ejecutar.py [A R B C manifiesto]
"""
from __future__ import annotations

import hashlib
import io
import json
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CLON = RAIZ / "external" / "pancholi"
URL = "https://github.com/aman-jaglan/Capstone_Project.git"
COMMIT = "d0a61e783353f52123b1821bc1876824d608d2a1"
DATOS = CLON / "src" / "Data_Synthesizer" / "data"
SALIDA = RAIZ / "outputs" / "pancholi"
CRUDO = SALIDA / "crudo"
PARCHES = RAIZ / "tools" / "pancholi_parches"
PRERREGISTRO = RAIZ / "docs" / "prerregistro_wp5.md"

SEMILLAS = list(range(42, 52))
N_NIVELES = 12
CLIENTES_ENTRENA_POR_NIVEL = 13      # 12 x 13 = 156 (el repo usa 155)
CLIENTES_EVAL_POR_NIVEL = 167        # 167 x 30 = 5.010 tx por nivel
TX_POR_CLIENTE = 30                  # valor de transaction_synthesizer.py
EPOCAS = 100                         # valor de transaction_synthesizer.py
MUESTRAS_A = 60_000                  # ~5.000 por nivel
MUESTRAS_B = 500_000                 # valor de transaction_synthesizer.py
HOGAR = 2                            # mediana de household_size en su etapa 1
ZIP = 20001.0                        # ZIP del ejemplo del paper; float como en sus archivos


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_sin_timestamp(df: pd.DataFrame) -> str:
    """Hash del contenido sin la columna timestamp (depende de datetime.now() en su código)."""
    buf = io.StringIO()
    df.drop(columns=["timestamp"], errors="ignore").to_csv(buf, index=False)
    return hashlib.sha256(buf.getvalue().encode()).hexdigest()


def verificar_clon() -> None:
    head = subprocess.run(["git", "-C", str(CLON), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    sucio = subprocess.run(["git", "-C", str(CLON), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if head != COMMIT:
        raise SystemExit(f"Commit del clon {head} != fijado {COMMIT}")
    if sucio:
        raise SystemExit(f"El clon tiene cambios locales:\n{sucio}")


def importar_pipeline():
    verificar_clon()
    import sdv.metadata.single_table as _m
    import sdv.single_table
    sdv.single_table.SingleTableMetadata = _m.SingleTableMetadata   # parche P1 (ver tools/pancholi_parches)
    sys.path.insert(0, str(CLON))
    from src.component import transaction, customer
    return transaction, customer


def fijar_semilla(s: int) -> None:
    import torch
    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)


def niveles_ingreso() -> np.ndarray:
    inc = pd.read_csv(DATOS / "synthetic_customer_gan.csv", usecols=["income"])["income"]
    return np.geomspace(inc.min(), inc.max(), N_NIVELES)


def clientes_rejilla(por_nivel: int, prefijo: str) -> pd.DataFrame:
    filas = [{"customer_id": f"{prefijo}N{i:02d}C{j:03d}", "nivel": i, "zipcode": ZIP,
              "income": float(x), "household_size": HOGAR}
             for i, x in enumerate(niveles_ingreso()) for j in range(por_nivel)]
    return pd.DataFrame(filas)


def guardar(df: pd.DataFrame, nombre: str) -> dict:
    p = CRUDO / f"{nombre}.csv.gz"
    df.to_csv(p, index=False, compression={"method": "gzip", "mtime": 0})
    return {"archivo": str(p.relative_to(RAIZ)), "filas": len(df), "sha256": sha256(p),
            "sha256_sin_timestamp": sha_sin_timestamp(df)}


def ya_hecho(idc: str) -> bool:
    return (CRUDO / f"{idc}.hecho.json").exists()


def marcar(idc: str, info: dict) -> None:
    info["terminado_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (CRUDO / f"{idc}.hecho.json").write_text(json.dumps(info, indent=1, ensure_ascii=False))
    estado = sorted(p.stem.replace(".hecho", "") for p in CRUDO.glob("*.hecho.json"))
    (SALIDA / "ESTADO.md").write_text("# Estado WP5\n\nCorridas terminadas:\n" + "\n".join(f"- {e}" for e in estado) + "\n")


def comercios() -> pd.DataFrame:
    return pd.read_csv(DATOS / "dc_businesses_cleaned.csv")


LOTE_MUESTREO = 50_000               # P2: solo para n_muestras > LOTE_MUESTREO (diseño B)


def muestrear(tr_mod, modelo, n: int) -> pd.DataFrame:
    """Igual que TransactionCTGAN.generate, pero con batch_size de SDV cuando n es grande (parche P2, memoria)."""
    if n <= LOTE_MUESTREO:
        return modelo.generate(num_samples=n)
    sint = modelo.synthesizer.sample(num_rows=n, batch_size=LOTE_MUESTREO)
    sint["timestamp"] = [tr_mod.random_timestamp_within_30_days() for _ in range(len(sint))]
    return sint


def etapas_2_3(tr_mod, clientes: pd.DataFrame, n_muestras: int, idc: str) -> dict:
    t0 = time.time()
    s2 = tr_mod.TransactionSimulator(customers=clientes, merchants=comercios()).simulate_transactions(num_per_customer=TX_POR_CLIENTE)
    t1 = time.time()
    modelo = tr_mod.TransactionCTGAN(epochs=EPOCAS)
    modelo.fit(s2)
    t2 = time.time()
    s3 = muestrear(tr_mod, modelo, n_muestras)
    t3 = time.time()
    return {"s2": s2, "s3": s3, "tiempos_s": {"etapa2": t1 - t0, "ctgan_fit": t2 - t1, "ctgan_muestreo": t3 - t2}}


def correr_A(tr_mod, s: int, idc: str) -> None:
    fijar_semilla(s)
    r = etapas_2_3(tr_mod, clientes_rejilla(CLIENTES_ENTRENA_POR_NIVEL, "T"), MUESTRAS_A, idc)
    t = time.time()
    ev = clientes_rejilla(CLIENTES_EVAL_POR_NIVEL, "E")
    s2e = tr_mod.TransactionSimulator(customers=ev, merchants=comercios()).simulate_transactions(num_per_customer=TX_POR_CLIENTE)
    r["tiempos_s"]["etapa2_evaluacion"] = time.time() - t
    info = {"diseno": idc[0], "semilla": s, "tiempos_s": r["tiempos_s"], "archivos": [
        guardar(r["s2"], f"{idc}_etapa2_entrenamiento"),
        guardar(r["s3"], f"{idc}_etapa3_ctgan"),
        guardar(s2e, f"{idc}_etapa2_evaluacion")]}
    marcar(idc, info)


def correr_B(tr_mod, s: int, idc: str) -> None:
    fijar_semilla(s)
    cl = pd.read_csv(DATOS / "synthetic_customers_deepseek.csv")
    r = etapas_2_3(tr_mod, cl, MUESTRAS_B, idc)
    marcar(idc, {"diseno": "B", "semilla": s, "tiempos_s": r["tiempos_s"], "archivos": [
        guardar(r["s2"], f"{idc}_etapa2"), guardar(r["s3"], f"{idc}_etapa3_ctgan")]})


def correr_C(tr_mod, cu_mod, s: int, idc: str) -> None:
    fijar_semilla(s)
    t0 = time.time()
    m1 = cu_mod.AdvancedIncomeModel(epochs=EPOCAS)
    m1.fit(pd.read_csv(DATOS / "cleaned_income_data.csv"))
    t1 = time.time()
    hogares = m1.generate(100_000)               # como customer_synthesizer.py
    t2 = time.time()
    muestra = hogares.sample(n=155, random_state=s).reset_index(drop=True)
    muestra.insert(0, "customer_id", [f"C1_{i:03d}" for i in range(len(muestra))])  # su add_customer_ids usa uuid4 sin semilla
    r = etapas_2_3(tr_mod, muestra, MUESTRAS_A, idc)
    r["tiempos_s"].update({"etapa1_fit": t1 - t0, "etapa1_muestreo": t2 - t1})
    marcar(idc, {"diseno": "C", "semilla": s, "tiempos_s": r["tiempos_s"], "archivos": [
        guardar(hogares, f"{idc}_etapa1_hogares"), guardar(muestra, f"{idc}_etapa1_clientes155"),
        guardar(r["s2"], f"{idc}_etapa2"), guardar(r["s3"], f"{idc}_etapa3_ctgan")]})


def manifiesto() -> None:
    import torch
    corridas = [json.loads(p.read_text()) | {"id": p.stem.replace(".hecho", "")} for p in sorted(CRUDO.glob("*.hecho.json"))]
    rep = None
    a42 = CRUDO / "A_s42.hecho.json"; r42 = CRUDO / "R_s42.hecho.json"
    if a42.exists() and r42.exists():
        ha = {Path(f["archivo"]).name.split("_", 2)[-1]: f["sha256_sin_timestamp"] for f in json.loads(a42.read_text())["archivos"]}
        hr = {Path(f["archivo"]).name.split("_", 2)[-1]: f["sha256_sin_timestamp"] for f in json.loads(r42.read_text())["archivos"]}
        rep = {k: ha[k] == hr.get(k) for k in ha}
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout.split()
    m = {
        "descripcion": "WP5 — ejecución del pipeline de referencia (Pancholi et al.), etapas 1-3",
        "repositorio": {"url": URL, "commit": COMMIT, "arbol_limpio": subprocess.run(
            ["git", "-C", str(CLON), "status", "--porcelain"], capture_output=True, text=True).stdout.strip() == ""},
        "licencia": "MIT (Copyright (c) 2025 Aman Jaglan)",
        "parches": {p.name: sha256(p) for p in sorted(PARCHES.glob("*")) if p.is_file()},
        "prerregistro": {"archivo": str(PRERREGISTRO.relative_to(RAIZ)), "sha256": sha256(PRERREGISTRO)},
        "semillas": SEMILLAS,
        "semilla_muestreo_sdv": "SDV 1.19 fija FIXED_RNG_SEED=73251 al muestrear (comportamiento por defecto, no se altera)",
        "parametros": {"n_niveles": N_NIVELES, "niveles_ingreso_usd_anual": niveles_ingreso().tolist(),
                        "clientes_entrena_por_nivel": CLIENTES_ENTRENA_POR_NIVEL, "clientes_eval_por_nivel": CLIENTES_EVAL_POR_NIVEL,
                        "tx_por_cliente": TX_POR_CLIENTE, "epocas_ctgan": EPOCAS, "muestras_A": MUESTRAS_A,
                        "muestras_B": MUESTRAS_B, "lote_muestreo_B": LOTE_MUESTREO, "household_size": HOGAR, "zipcode": ZIP},
        "reproducibilidad_semilla_42": rep,
        "entorno": {"python": sys.version, "plataforma": platform.platform(), "procesador": platform.processor(),
                    "cpu_hilos_torch": torch.get_num_threads(), "cuda": torch.cuda.is_available(),
                    "venv": ".venv-pancholi", "paquetes": freeze},
        "corridas": corridas,
        "tiempo_total_s": sum(sum(c["tiempos_s"].values()) for c in corridas),
    }
    (SALIDA / "manifest.json").write_text(json.dumps(m, indent=1, ensure_ascii=False))


def main(pasos: list[str]) -> None:
    CRUDO.mkdir(parents=True, exist_ok=True)
    tr_mod, cu_mod = importar_pipeline()
    for paso in pasos:
        if paso == "A":
            for s in SEMILLAS:
                if not ya_hecho(f"A_s{s}"):
                    correr_A(tr_mod, s, f"A_s{s}")
        elif paso == "R" and not ya_hecho("R_s42"):
            correr_A(tr_mod, 42, "R_s42")
        elif paso == "B":
            for s in SEMILLAS:
                if not ya_hecho(f"B_s{s}"):
                    correr_B(tr_mod, s, f"B_s{s}")
        elif paso == "C" and not ya_hecho("C_s42"):
            correr_C(tr_mod, cu_mod, 42, "C_s42")
        elif paso == "manifiesto":
            manifiesto()
        print(f"[{time.strftime('%H:%M:%S')}] paso {paso} listo", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["A", "R", "B", "C", "manifiesto"])
