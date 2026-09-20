#!/usr/bin/env python
"""Normaliza los .zip del DANE (data/_descargas/) a la estructura canónica de data/raw/.

Uso (desde la raíz del repo):
    .venv\\Scripts\\python.exe tools\\normalizar_datos.py --dry-run   # solo planifica y compara
    .venv\\Scripts\\python.exe tools\\normalizar_datos.py             # extrae

Reglas (ver CLAUDE.md):
- Extracción TAL CUAL: bytes intactos, sin re-encodear ni renombrar la extensión (.txt sigue .txt).
- Mapeo módulo -> nombre canónico por tokens (sin mayúsculas, tildes, \\xa0 ni espacios múltiples).
  Si un zip o un CSV no encaja exactamente en una regla, FALLA antes de escribir nada.
- Se selecciona por carpeta CSV/ + extensión, nunca por posición dentro del zip.
- GEIH: solo los 8 CSV de cada uno de los 12 meses de 2025. No se extraen .SAV ni .DTA.
- Todo lo de 2026 se excluye (por nombre de zip/miembro y por MES/PERIODO dentro del CSV).
- No toca GEIH_2025/_metadatos/, GEIH_2025/_etiquetas/ ni ENPH_2017/_metadatos/.
- Idempotente: si el destino existe y su SHA-256 coincide con el del zip, no hace nada;
  si existe y difiere, FALLA sin sobrescribir. Escritura atómica (.part -> os.replace).
- Determinista: orden fijo, sin aleatoriedad (SEED no aplica), log sin marcas de tiempo.
- Solo librería estándar. Rutas relativas a la raíz del repo vía pathlib.

Regla fija de lectura (documentada también en outputs/normalizar_datos_log.json):
    GEIH .csv -> encoding cp1252,     sep ';'
    ENPH .csv -> encoding utf-8-sig,  sep ';'
    ENPH .txt -> encoding utf-8,      sep tab
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
DESCARGAS = ROOT / "data" / "_descargas"
RAW = ROOT / "data" / "raw"
LOG = ROOT / "outputs" / "normalizar_datos_log.json"

CHUNK = 1 << 20
ANIO_GEIH = "2025"
ANIO_EXCLUIDO = "2026"
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")
CARPETAS_PROTEGIDAS = {"_metadatos", "_etiquetas"}

LECTURA = {
    "GEIH_csv": {"encoding": "cp1252", "sep": ";"},
    "ENPH_csv": {"encoding": "utf-8-sig", "sep": ";"},
    "ENPH_txt": {"encoding": "utf-8", "sep": "\t"},
}


class NormalizacionError(Exception):
    """Error de mapeo o de integridad. Se reporta y el script termina con código 1."""


@dataclass(frozen=True)
class Regla:
    destino: str                       # GEIH: nombre de archivo; ENPH: ruta relativa a data/raw
    requeridos: frozenset              # tokens que deben estar todos
    prohibidos: frozenset = frozenset()  # tokens que no pueden aparecer

    def encaja(self, toks: set[str]) -> bool:
        return self.requeridos <= toks and not (self.prohibidos & toks)


@dataclass(frozen=True)
class Tarea:
    zip_path: Path
    miembro: str
    destino: Path
    lectura: str                       # clave de LECTURA


def _r(destino: str, req: str, prohib: str = "") -> Regla:
    return Regla(destino, frozenset(req.split()), frozenset(prohib.split()))


MODULOS_GEIH = (
    _r("caracteristicas_generales.csv", "caracteristicas generales"),
    _r("datos_hogar.csv", "datos hogar"),
    _r("fuerza_trabajo.csv", "fuerza trabajo"),
    _r("migracion.csv", "migracion"),
    _r("no_ocupados.csv", "no ocupados"),
    _r("ocupados.csv", "ocupados", "no"),
    _r("otras_formas_trabajo.csv", "otras formas trabajo"),
    _r("otros_ingresos.csv", "otros ingresos"),
)

# 16 zips de ENPH -> subcarpeta/nombre canónico. La extensión del destino debe coincidir con la del
# archivo dentro del zip (los tres .txt conservan .txt). Los tokens distinguen urbano/urbanos, etc.
ENPH_REGLAS = (
    _r("ENPH_2017/hogares/viviendas_hogares.csv", "viviendas hogares"),
    _r("ENPH_2017/hogares/gastos_menos_frecuentes_medio_pago.csv", "menos frecuentes medio pago"),
    _r("ENPH_2017/hogares/gastos_menos_frecuentes_articulos.txt", "menos frecuentes articulos"),
    _r("ENPH_2017/personas/caracteristicas_generales_personas.csv", "caracteristicas generales personas"),
    _r("ENPH_2017/urbano/gastos_diarios_hogar_comidas_fuera.csv", "diarios hogar urbano comidas"),
    _r("ENPH_2017/urbano/gastos_diarios_personales.csv", "diarios personales urbano", "comidas"),
    _r("ENPH_2017/urbano/gastos_diarios_capitulo_c.txt", "diarios urbano capitulo"),
    _r("ENPH_2017/urbano/gastos_diarios_mercados.csv", "diarios urbanos mercados"),
    _r("ENPH_2017/urbano/gastos_diarios_hogar.txt", "diarios urbanos", "mercados capitulo comidas personales"),
    _r("ENPH_2017/urbano/gastos_personales_comidas_fuera.csv", "personales urbano comidas", "diarios"),
    _r("ENPH_2017/rural/gastos_personales_comidas_fuera.csv", "personales rural comidas"),
    _r("ENPH_2017/rural/gastos_personales.csv", "personales rural", "comidas"),
    _r("ENPH_2017/rural/gastos_semanales_capitulo_c.csv", "semanales rural capitulo"),
    _r("ENPH_2017/rural/gastos_semanales_comidas_fuera.csv", "semanales rural comidas"),
    _r("ENPH_2017/rural/gastos_semanales_mercados.csv", "semanales rurales mercados"),
    _r("ENPH_2017/rural/gastos_semanales.csv", "semanales rurales", "mercados"),
)


def tokens(texto: str) -> list[str]:
    """Minúsculas, sin tildes; \\xa0, espacios múltiples y puntuación separan tokens."""
    s = unicodedata.normalize("NFKD", texto)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", s.casefold())


def elegir_regla(reglas, texto: str, contexto: str) -> Regla:
    toks = set(tokens(texto))
    candidatas = [r for r in reglas if r.encaja(toks)]
    if len(candidatas) != 1:
        raise NormalizacionError(
            f"{contexto}: '{texto}' (tokens: {sorted(toks)}) encaja con {len(candidatas)} reglas "
            f"({[r.destino for r in candidatas]}); se esperaba exactamente 1. No adivino: "
            f"corrige el mapeo en ENPH_REGLAS / MODULOS_GEIH."
        )
    return candidatas[0]


def _miembros(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    return [i for i in zf.infolist() if not i.is_dir()]


def _es_2026(texto: str) -> bool:
    return ANIO_EXCLUIDO in tokens(texto)


def verificar_periodo(zf: zipfile.ZipFile, info: zipfile.ZipInfo, mes_num: int, ident: str) -> None:
    """Humo: la primera fila de datos debe traer MES == mes del zip y PERIODO de 2025."""
    with zf.open(info) as f:
        lineas = f.read(256 * 1024).decode("cp1252", errors="replace").splitlines()[:2]
    if len(lineas) < 2:
        raise NormalizacionError(f"{ident}: CSV sin fila de datos.")
    filas = list(csv.reader(lineas, delimiter=";"))
    cab = [c.strip() for c in filas[0]]
    for col in ("MES", "PERIODO"):
        if col not in cab:
            raise NormalizacionError(f"{ident}: falta la columna {col} para validar el mes/año.")
    mes = filas[1][cab.index("MES")].strip()
    periodo = filas[1][cab.index("PERIODO")].strip()
    if not mes.isdigit() or int(mes) != mes_num or not periodo.startswith(ANIO_GEIH):
        raise NormalizacionError(
            f"{ident}: MES={mes!r}, PERIODO={periodo!r} no corresponden a {ANIO_GEIH}-{mes_num:02d}."
        )


def _planificar_geih(zpath: Path, num: int, mes: str, raw: Path, excluidos: list[str]) -> list[Tarea]:
    carpeta = raw / "GEIH_2025" / f"{num:02d}_{mes}"
    try:
        zf_ctx = zipfile.ZipFile(zpath)
    except zipfile.BadZipFile as e:
        raise NormalizacionError(f"{zpath.name}: zip ilegible ({e}).") from e
    with zf_ctx as zf:
        elegidos: dict[str, zipfile.ZipInfo] = {}
        for info in _miembros(zf):
            partes = PurePosixPath(info.filename.replace("\\", "/")).parts
            if _es_2026(info.filename):
                excluidos.append(f"{zpath.name}::{info.filename}")
                continue
            if not (len(partes) == 2 and tokens(partes[0]) == ["csv"]
                    and partes[1].lower().endswith(".csv")):
                continue  # SAV / DTA / DAT u otros: no se extraen
            regla = elegir_regla(MODULOS_GEIH, PurePosixPath(partes[1]).stem, f"{zpath.name}/CSV")
            if regla.destino in elegidos:
                raise NormalizacionError(f"{zpath.name}: dos CSV mapean a {regla.destino}.")
            elegidos[regla.destino] = info
        esperados = {r.destino for r in MODULOS_GEIH}
        if set(elegidos) != esperados:
            raise NormalizacionError(
                f"{zpath.name}: módulos GEIH faltantes {sorted(esperados - set(elegidos))}; "
                f"se esperaban los 8 CSV en la carpeta CSV/."
            )
        tareas = []
        for destino, info in sorted(elegidos.items()):
            verificar_periodo(zf, info, num, f"{zpath.name}/{info.filename}")
            tareas.append(Tarea(zpath, info.filename, carpeta / destino, "GEIH_csv"))
    return tareas


def _planificar_enph(zpath: Path, regla: Regla, raw: Path, excluidos: list[str]) -> Tarea:
    destino = raw / regla.destino
    ext = destino.suffix.lower()
    with zipfile.ZipFile(zpath) as zf:
        validos = []
        for info in _miembros(zf):
            if _es_2026(info.filename):
                excluidos.append(f"{zpath.name}::{info.filename}")
            elif info.filename.lower().endswith(ext):
                validos.append(info)
    if len(validos) != 1:
        raise NormalizacionError(
            f"{zpath.name}: se esperaba exactamente 1 archivo '{ext}' (por la regla "
            f"{regla.destino}) y hay {len(validos)}."
        )
    return Tarea(zpath, validos[0].filename, destino, f"ENPH_{ext[1:]}")


def planificar(descargas: Path = DESCARGAS, raw: Path = RAW):
    """Valida TODO el mapeo antes de escribir nada. Devuelve (tareas, zips_excluidos, miembros_excluidos)."""
    if not descargas.is_dir():
        raise NormalizacionError(f"No existe {descargas}.")
    geih: dict[str, Path] = {}
    enph: dict[str, Path] = {}
    zips_excluidos: list[str] = []
    for z in sorted(descargas.glob("*.zip"), key=lambda p: p.name):
        toks = tokens(z.stem)
        if ANIO_EXCLUIDO in toks:
            zips_excluidos.append(z.name)
            continue
        meses = [t for t in toks if t in MESES]
        if meses:
            if toks != [meses[0], ANIO_GEIH]:
                raise NormalizacionError(
                    f"{z.name}: parece un mes de GEIH pero no es '<mes> {ANIO_GEIH}'. GEIH: solo 2025."
                )
            if meses[0] in geih:
                raise NormalizacionError(f"{z.name}: mes duplicado ({geih[meses[0]].name}).")
            geih[meses[0]] = z
        else:
            regla = elegir_regla(ENPH_REGLAS, z.stem, z.name)
            if regla.destino in enph:
                raise NormalizacionError(f"{z.name} y {enph[regla.destino].name} mapean a {regla.destino}.")
            enph[regla.destino] = z

    n_meses = len(geih)
    if n_meses != 12:
        raise NormalizacionError(
            f"GEIH: n_meses={n_meses}, se esperaban 12. Faltan: {[m for m in MESES if m not in geih]}."
        )
    faltan = [r.destino for r in ENPH_REGLAS if r.destino not in enph]
    if faltan:
        raise NormalizacionError(f"ENPH: no hay zip para {faltan}.")

    excluidos_miembros: list[str] = []
    tareas: list[Tarea] = []
    for num, mes in enumerate(MESES, start=1):
        tareas += _planificar_geih(geih[mes], num, mes, raw, excluidos_miembros)
    for regla in ENPH_REGLAS:
        tareas.append(_planificar_enph(enph[regla.destino], regla, raw, excluidos_miembros))

    destinos = [t.destino for t in tareas]
    if len(set(destinos)) != len(destinos):
        raise NormalizacionError("Destinos duplicados en el plan.")
    for d in destinos:
        if CARPETAS_PROTEGIDAS & set(d.relative_to(raw).parts):
            raise NormalizacionError(f"El plan intenta escribir en una carpeta protegida: {d}.")
    return tareas, zips_excluidos, excluidos_miembros


def _consumir(origen, h, salida=None) -> None:
    while chunk := origen.read(CHUNK):
        h.update(chunk)
        if salida is not None:
            salida.write(chunk)


def _sha256_archivo(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        _consumir(f, h)
    return h.hexdigest()


def _procesar(zf: zipfile.ZipFile, t: Tarea, dry_run: bool) -> dict:
    info = zf.getinfo(t.miembro)
    dest = t.destino
    parcial = dest.with_name(f".{dest.name}.part")
    if parcial.exists() and not dry_run:
        parcial.unlink()  # residuo de una corrida interrumpida

    if dest.exists():
        h = hashlib.sha256()
        with zf.open(info) as f:  # zipfile verifica el CRC al llegar al final
            _consumir(f, h)
        if dest.stat().st_size != info.file_size or _sha256_archivo(dest) != h.hexdigest():
            raise NormalizacionError(
                f"{dest} ya existe pero difiere del zip {t.zip_path.name}::{t.miembro}. "
                f"No se sobrescribe; revísalo y bórralo manualmente si es un residuo."
            )
        return {"estado": "ya_existia", "bytes": info.file_size, "sha256": h.hexdigest()}

    if dry_run:
        return {"estado": "faltante", "bytes": info.file_size, "sha256": None}

    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    try:
        with zf.open(info) as f, open(parcial, "wb") as out:
            _consumir(f, h, out)
        if parcial.stat().st_size != info.file_size:
            raise NormalizacionError(f"{dest.name}: tamaño extraído != tamaño en el zip.")
        os.replace(parcial, dest)
    finally:
        if parcial.exists():
            parcial.unlink()
    return {"estado": "extraido", "bytes": info.file_size, "sha256": h.hexdigest()}


def ejecutar(tareas: list[Tarea], raw: Path = RAW, dry_run: bool = False) -> list[dict]:
    por_zip: dict[Path, list[Tarea]] = defaultdict(list)
    for t in tareas:
        por_zip[t.zip_path].append(t)
    registros = []
    for zpath in sorted(por_zip, key=lambda p: p.name):
        with zipfile.ZipFile(zpath) as zf:
            for t in por_zip[zpath]:
                r = _procesar(zf, t, dry_run)
                r.update(destino=t.destino.relative_to(raw).as_posix(), zip=zpath.name,
                         miembro=t.miembro, lectura=t.lectura)
                registros.append(r)
                print(f"  [{r['estado']:<10}] {r['destino']}  ({r['bytes']:,} B)", flush=True)
    return sorted(registros, key=lambda r: r["destino"])


def inesperados(tareas: list[Tarea]) -> list[Path]:
    """Archivos presentes en las carpetas canónicas que este script no produce (solo aviso)."""
    esperado: dict[Path, set[str]] = defaultdict(set)
    for t in tareas:
        esperado[t.destino.parent].add(t.destino.name)
    return sorted(p for carpeta, nombres in esperado.items() if carpeta.is_dir()
                  for p in carpeta.iterdir() if p.name not in nombres)


def escribir_log(registros: list[dict], log: Path = LOG) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    contenido = {
        "lectura": LECTURA,
        "archivos": [{k: r[k] for k in ("destino", "zip", "miembro", "bytes", "sha256", "lectura")}
                     for r in registros],
    }
    log.write_text(json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="planifica y compara; no escribe nada")
    args = ap.parse_args(argv)
    try:
        tareas, zips_excl, miembros_excl = planificar()
        print(f"Plan validado: {len(tareas)} archivos "
              f"(GEIH {sum(t.lectura == 'GEIH_csv' for t in tareas)}, "
              f"ENPH {sum(t.lectura != 'GEIH_csv' for t in tareas)}).")
        for z in zips_excl:
            print(f"  EXCLUIDO (2026, zip): {z}")
        for m in miembros_excl:
            print(f"  EXCLUIDO (2026, miembro): {m}")
        registros = ejecutar(tareas, RAW, args.dry_run)
        for p in inesperados(tareas):
            print(f"  AVISO: archivo no esperado en carpeta canónica (no se toca): {p.relative_to(RAW)}")
        conteo = defaultdict(int)
        for r in registros:
            conteo[r["estado"]] += 1
        print("Resumen:", dict(conteo))
        if not args.dry_run:
            escribir_log(registros)
            print(f"Log: {LOG.relative_to(ROOT).as_posix()}")
    except NormalizacionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
