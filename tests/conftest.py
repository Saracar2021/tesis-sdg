"""Guarda de pruebas: ninguna prueba puede abrir, listar ni escribir rutas bajo data/.

Ahí viven los datos reales de WP4 (data/reales_anon, data/reales_crudos, data/_privado, data/consentimientos).
Se implementa con un audit hook de Python (PEP 578), que ve TODA apertura de archivo del proceso (open, io.open,
os.open, y por tanto pandas, openpyxl, gzip, zipfile…) y los listados (os.listdir, os.scandir → glob, rglob).

Única excepción: LECTURA en data/raw (microdatos públicos del DANE e IPC), que test_carga, test_generador,
test_priors y test_ipc leen a propósito y en solo lectura. Escribir en data/raw también está prohibido.

Si una prueba toca data/, la apertura falla en el acto con PermissionError (no se llega a leer nada) y la prueba
falla con un mensaje que dice qué ruta intentó abrir.
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_DATA = os.path.normcase(os.path.realpath(RAIZ / "data"))
_RAW = os.path.normcase(os.path.realpath(RAIZ / "data" / "raw"))
_ESCRITURA = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_EVENTOS_ESCRITURA = {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.truncate", "os.chmod", "shutil.rmtree"}
_EVENTOS_LISTADO = {"os.listdir", "os.scandir"}


def _bajo(ruta, base):
    return ruta == base or ruta.startswith(base + os.sep)


def _normalizar(p):
    if isinstance(p, int) or p is None:
        return None
    try:
        p = os.fsdecode(p)
    except TypeError:
        return None
    return os.path.normcase(os.path.realpath(p or "."))


def _es_lectura(evento, args):
    if evento in _EVENTOS_LISTADO:
        return True
    if evento != "open":
        return False
    modo, flags = (args[1] if len(args) > 1 else None), (args[2] if len(args) > 2 else 0)
    if isinstance(modo, str):
        return not any(c in modo for c in "wax+")
    return not (int(flags or 0) & _ESCRITURA)


def _guardia(evento, args):
    if evento != "open" and evento not in _EVENTOS_LISTADO and evento not in _EVENTOS_ESCRITURA:
        return
    rutas = args[:2] if evento == "os.rename" else args[:1]
    for p in rutas:
        r = _normalizar(p)
        if r is None or not _bajo(r, _DATA):
            continue
        if _bajo(r, _RAW) and _es_lectura(evento, args):
            continue
        raise PermissionError(f"[guarda de pruebas] {evento} bajo data/ prohibido en las pruebas: {p}")


sys.addaudithook(_guardia)
