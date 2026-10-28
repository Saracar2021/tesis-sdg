"""Convierte el xlsx del IPC del DANE (hoja ``IndicesIPC``, serie de empalme) a formato largo para el generador (WP6).

Ejecutar desde la raíz:  .venv\\Scripts\\python.exe tools\\convertir_ipc.py [--xlsx RUTA] [--hoja IndicesIPC]

Lee:     data/raw/IPC/anex-IPC*.xlsx   (si hay exactamente uno; si no, pasar --xlsx). NO escribe en data/raw.
Escribe: outputs/ipc/ipc_total_nacional.csv   mes (AAAA-MM), division (00 = total), indice
         outputs/ipc/manifest_ipc.json        sha256 del xlsx y del CSV, hoja, rango de meses, texto «Actualizado el…», factores resultantes

Determinista (sin aleatoriedad). El deflactor es el índice TOTAL nacional, no por división (decisión de la autora, 27 oct 2026; ver
``sdg.ipc``). Las celdas vacías al final de la serie (meses aún no publicados) se omiten; un hueco en medio es un error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sdg import ipc  # noqa: E402

OUT = RAIZ / "outputs" / "ipc"


def localizar_xlsx(explicito: str | None) -> Path:
    if explicito:
        ruta = Path(explicito)
        if not ruta.is_file():
            raise SystemExit(f"no existe {ruta}")
        return ruta
    candidatos = sorted(ipc.DIR_CRUDO.glob("anex-IPC*.xlsx"))
    if len(candidatos) != 1:
        raise SystemExit(f"se esperaba exactamente un anex-IPC*.xlsx en {ipc.DIR_CRUDO}; hay {len(candidatos)}: pasar --xlsx")
    return candidatos[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xlsx", default=None)
    ap.add_argument("--hoja", default=ipc.HOJA_XLSX)
    a = ap.parse_args()
    ruta = localizar_xlsx(a.xlsx)
    serie, meta = ipc.leer_xlsx_empalme(ruta, a.hoja)
    OUT.mkdir(parents=True, exist_ok=True)
    serie.to_csv(ipc.RUTA_IPC, index=False, encoding="utf-8", lineterminator="\n")
    releida = ipc.cargar_serie(ipc.RUTA_IPC)
    if not releida.equals(serie):
        raise SystemExit("el CSV escrito no se lee igual que la serie convertida")
    base = float(ipc.indice_base(releida)[ipc.TOTAL])
    m17 = releida[releida["mes"].str.startswith(f"{ipc.ANIO_REF_ENPH}-")]["indice"]
    meta |= {"script": "tools/convertir_ipc.py", "csv": str(ipc.RUTA_IPC.relative_to(RAIZ)).replace("\\", "/"), "sha256_csv": ipc.sha256_archivo(ipc.RUTA_IPC),
             "division": ipc.TOTAL, "indice_base_2025_promedio": base, "indice_promedio_2017": float(m17.mean()), "meses_2017": int(len(m17)),
             "factor_promedio_2017_a_promedio_2025": float(base / m17.mean()),
             "nota": "solo el índice total nacional; el factor que usa el generador sale del mes de recolección de cada hogar (ver sdg.ipc)"}
    (OUT / "manifest_ipc.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{ruta.name} (hoja {meta['hoja']}): {meta['n_meses']} meses, {meta['primer_mes']} a {meta['ultimo_mes']}; {meta['actualizado']}")
    print(f"índice 2018-12 = {meta['indice_2018_12']} (base dic-2018 = 100: {meta['base_dic_2018_igual_100']}); promedio 2025 = {meta['indice_base_2025_promedio']:.4f}; "
          f"factor promedio 2017 → promedio 2025 = {meta['factor_promedio_2017_a_promedio_2025']:.4f} ({meta['meses_2017']} meses de 2017)")
    print(f"escrito {meta['csv']} (sha256 {meta['sha256_csv'][:16]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
