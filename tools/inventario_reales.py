"""Inventario de data/reales_crudos/ — reporta SOLO estructura, nunca datos personales.

Seguro para privacidad: imprime nombres de archivo, tipo, tamaño, nº de hojas/filas/páginas
y, para tablas, los ENCABEZADOS de columna. NO imprime valores de celdas ni texto de los PDF.

Uso (en tu terminal, con el .venv activado):
    python tools/inventario_reales.py
"""
from __future__ import annotations
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CRUDOS = RAIZ / "data" / "reales_crudos"


def inventario_tabla(p: Path) -> list[str]:
    out = []
    try:
        if p.suffix.lower() in (".xlsx", ".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
            for ws in wb.worksheets:
                filas = ws.max_row
                # encabezados = primera fila no vacía (nombres de columna, no datos)
                headers = []
                for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
                    headers = [str(c) for c in row if c is not None]
                    break
                out.append(f"    hoja '{ws.title}': {filas} filas · encabezados: {headers}")
            wb.close()
        elif p.suffix.lower() in (".csv", ".tsv"):
            import csv
            sep = "\t" if p.suffix.lower() == ".tsv" else ","
            with open(p, encoding="utf-8-sig", errors="replace", newline="") as f:
                r = csv.reader(f, delimiter=sep)
                headers = next(r, [])
                n = sum(1 for _ in r)
            out.append(f"    {n} filas · encabezados: {headers}")
    except Exception as e:
        out.append(f"    [no se pudo leer la estructura: {type(e).__name__}: {e}]")
    return out


def inventario_pdf(p: Path) -> list[str]:
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader
        r = PdfReader(str(p))
        n = len(r.pages)
        # ¿texto extraíble? medimos SOLO la longitud del texto de la pág 1, no su contenido
        txt = (r.pages[0].extract_text() or "") if n else ""
        tipo = "texto extraíble" if len(txt.strip()) > 50 else "posiblemente escaneado (poco/zero texto)"
        return [f"    {n} páginas · {tipo} (pág 1: {len(txt.strip())} caracteres)"]
    except Exception as e:
        return [f"    [no se pudo abrir el PDF: {type(e).__name__}: {e} — ¿falta 'pip install pypdf'?]"]


def main() -> None:
    if not CRUDOS.exists():
        print(f"No existe {CRUDOS}. Crea la carpeta y pon ahí los extractos.")
        return
    archivos = sorted(x for x in CRUDOS.rglob("*") if x.is_file() and x.name != "LEEME.md")
    if not archivos:
        print(f"{CRUDOS} está vacía. Pon ahí los extractos (PDF/Excel) y vuelve a correr.")
        return
    print(f"== Inventario de {CRUDOS} ({len(archivos)} archivos) ==\n")
    resumen: dict[str, int] = {}
    for p in archivos:
        rel = p.relative_to(CRUDOS)
        kb = p.stat().st_size // 1024
        ext = p.suffix.lower()
        resumen[ext] = resumen.get(ext, 0) + 1
        print(f"• {rel}  ({kb} KB)")
        if ext in (".xlsx", ".xls", ".csv", ".tsv"):
            for ln in inventario_tabla(p):
                print(ln)
        elif ext == ".pdf":
            for ln in inventario_pdf(p):
                print(ln)
        print()
    print("== Resumen por tipo ==")
    for ext, n in sorted(resumen.items()):
        print(f"  {ext or '(sin extensión)'}: {n}")
    print("\nNota: este inventario NO imprimió ningún valor de celda ni texto de los PDF.")


if __name__ == "__main__":
    main()
