"""Cargador único de GEIH 2025 y ENPH 2016-2017 (CLAUDE.md v3).

Reglas que impone este módulo (no se pueden saltar sin pedirlo explícitamente):
- Lectura: GEIH .csv cp1252 «;» · ENPH .csv utf-8-sig «;» · ENPH .txt utf-8 tab. Todo entra como texto
  (los códigos sin etiqueta no se interpretan) y las celdas se recortan (` ` → ``).
- GEIH: el peso es ``FEX = FEX_C18 / len(meses)`` con los meses REALMENTE cargados. ``FEX_C18`` original
  se conserva sin dividir. Dominio Bogotá = ``AREA == '11'`` (nunca ``DPTO``).
- ENPH: el hogar es solo ``DIRECTORIO``. Dominio Bogotá = ``DOMINIO == 'BOGOTÁ'`` en viviendas_hogares; las demás
  tablas se restringen por los ``DIRECTORIO`` de esos hogares. Rural bloqueado salvo ``permitir_rural=True``.
  El peso es ``FEX = FEX_C`` (verificado como factor del hogar/vivienda: outputs/fex_enph_verificacion.json).
- Filas por archivo se validan contra ``outputs/fuentes_datos.json`` (misma salida que docs/fuentes_datos.md,
  generada por tools/generar_fuentes_datos.py) ANTES de filtrar. Si no cuadran → ``IntegridadError``.
- Toda unión (``unir``) reporta el % de filas enlazadas y falla por debajo del umbral (piso, no objetivo).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
GEIH_DIR = RAIZ / "data" / "raw" / "GEIH_2025"
ENPH_DIR = RAIZ / "data" / "raw" / "ENPH_2017"
FUENTES_JSON = RAIZ / "outputs" / "fuentes_datos.json"

MESES_GEIH = {1: "01_enero", 2: "02_febrero", 3: "03_marzo", 4: "04_abril", 5: "05_mayo", 6: "06_junio",
              7: "07_julio", 8: "08_agosto", 9: "09_septiembre", 10: "10_octubre", 11: "11_noviembre", 12: "12_diciembre"}
MODULOS_GEIH = ("caracteristicas_generales", "datos_hogar", "fuerza_trabajo", "migracion", "no_ocupados",
                "ocupados", "otras_formas_trabajo", "otros_ingresos")
UNIDAD_GEIH = {m: ("hogar" if m == "datos_hogar" else "persona") for m in MODULOS_GEIH}

LLAVE_GEIH_HOGAR = ["DIRECTORIO", "SECUENCIA_P", "HOGAR"]
LLAVE_GEIH_PERSONA = LLAVE_GEIH_HOGAR + ["ORDEN"]
LLAVE_ENPH_HOGAR = ["DIRECTORIO"]
LLAVE_ENPH_GASTO = ["DIRECTORIO", "SECUENCIA_ENCUESTA", "SECUENCIA_P"]

AREA_BOGOTA_GEIH = "11"          # Diccionario GEIH 2025, fila 169
DOMINIO_BOGOTA_ENPH = "BOGOTÁ"   # texto; viviendas_hogares.DOMINIO
UMBRAL_UNION = 99.0              # piso, no objetivo: se reporta siempre el % real
UMBRAL_UNION_ENPH = 100.0        # ENPH por DIRECTORIO: verificado 100 % (docs/fuentes_datos.md §4)

ENPH_CARPETAS = ("hogares", "personas", "urbano", "rural")
ENPH_UNIDAD = {"viviendas_hogares": "hogar", "gastos_menos_frecuentes_medio_pago": "hogar",
               "caracteristicas_generales_personas": "persona"}
ESTRATO_GRUPOS = ("bajo (1-2)", "medio (3-4)", "alto (5-6)")

UNIONES: list[dict] = []  # registro de todas las uniones hechas en la sesión


class IntegridadError(ValueError):
    """Filas o estructura no cuadran con docs/fuentes_datos.md."""


class UnionError(ValueError):
    """Una unión enlazó menos del umbral."""


class DominioError(PermissionError):
    """Dominio no permitido (p. ej. rural sin pedirlo)."""


# ------------------------------------------------------------------------------------------------
# utilidades
# ------------------------------------------------------------------------------------------------
def a_numero(serie: pd.Series) -> pd.Series:
    """Texto → float; acepta coma o punto decimal (ENPH usa coma; GEIH, punto). Vacío/ilegible → NaN."""
    return pd.to_numeric(serie.astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")


@lru_cache(maxsize=1)
def _fuentes() -> dict:
    if not FUENTES_JSON.exists():
        raise IntegridadError(f"No existe {FUENTES_JSON.relative_to(RAIZ)}; ejecutar tools/generar_fuentes_datos.py")
    return json.loads(FUENTES_JSON.read_text(encoding="utf-8"))


def _filas_esperadas_geih(num_mes: int, modulo: str) -> int:
    for r in _fuentes()["geih"]:
        if r["num_mes"] == num_mes and r["modulo"] == modulo:
            return int(r["filas"])
    raise IntegridadError(f"GEIH mes {num_mes} módulo {modulo}: no está en fuentes_datos.json")


def _filas_esperadas_enph(ruta: str) -> int:
    for r in _fuentes()["enph"]:
        if r["ruta"] == ruta:
            return int(r["filas"])
    raise IntegridadError(f"ENPH {ruta}: no está en fuentes_datos.json")


def _leer(ruta: Path, *, sep: str, encoding: str, columnas: Iterable[str] | None) -> pd.DataFrame:
    """Lee todo como texto; recorta espacios. ``columnas`` debe existir (error explícito si no)."""
    encabezado = pd.read_csv(ruta, sep=sep, encoding=encoding, nrows=0, dtype=str).columns
    if columnas is None:
        usar = list(encabezado)
    else:
        pedidas = list(dict.fromkeys(columnas))
        faltan = [c for c in pedidas if c not in set(encabezado)]
        if faltan:
            raise IntegridadError(f"{ruta.name}: columnas inexistentes {faltan}")
        usar = pedidas
    df = pd.read_csv(ruta, sep=sep, encoding=encoding, usecols=usar, dtype=str, keep_default_na=False)
    for c in df.columns:
        df[c] = df[c].str.strip()
    return df


def _como_lista(x) -> list:
    return [x] if isinstance(x, str) else list(x)


# ------------------------------------------------------------------------------------------------
# GEIH
# ------------------------------------------------------------------------------------------------
def cargar_geih(modulos, meses=range(1, 13), dominio: str = "bogota", columnas: Iterable[str] | None = None):
    """Apila los ``meses`` de cada módulo GEIH 2025.

    ``modulos``: un nombre (devuelve DataFrame) o lista (devuelve dict módulo → DataFrame).
    ``dominio``: ``"bogota"`` (``AREA == '11'``) o ``"todo"`` (sin filtro: incluye lo rural/otras ciudades).
    ``columnas``: subconjunto a cargar; siempre se añaden MES, AREA, FEX_C18 y las llaves del módulo.
    Añade ``FEX = FEX_C18 / len(meses)``. Las filas se validan por mes contra fuentes_datos.json.
    """
    if dominio not in ("bogota", "todo"):
        raise ValueError(f"dominio GEIH inválido: {dominio!r} (use 'bogota' o 'todo')")
    meses = list(meses)
    if not meses or len(set(meses)) != len(meses) or any(m not in MESES_GEIH for m in meses):
        raise ValueError(f"meses inválidos: {meses}")
    n_meses = len(meses)
    solo_uno = isinstance(modulos, str)
    salida: dict[str, pd.DataFrame] = {}
    for modulo in _como_lista(modulos):
        if modulo not in MODULOS_GEIH:
            raise ValueError(f"módulo GEIH desconocido: {modulo!r}")
        llaves = LLAVE_GEIH_HOGAR if UNIDAD_GEIH[modulo] == "hogar" else LLAVE_GEIH_PERSONA
        usar = None if columnas is None else [*columnas, *llaves, "MES", "AREA", "FEX_C18"]
        partes, filas_mes = [], {}
        for m in meses:
            ruta = GEIH_DIR / MESES_GEIH[m] / f"{modulo}.csv"
            df = _leer(ruta, sep=";", encoding="cp1252", columnas=usar)
            esperado = _filas_esperadas_geih(m, modulo)
            if len(df) != esperado:
                raise IntegridadError(f"GEIH {MESES_GEIH[m]}/{modulo}: {len(df)} filas leídas ≠ {esperado} en fuentes_datos.json")
            if not (df["MES"].astype(int) == m).all():
                raise IntegridadError(f"GEIH {MESES_GEIH[m]}/{modulo}: la columna MES no coincide con la carpeta")
            filas_mes[m] = len(df)
            partes.append(df)
        df = pd.concat(partes, ignore_index=True)
        n_total = len(df)
        if dominio == "bogota":
            df = df[df["AREA"] == AREA_BOGOTA_GEIH].reset_index(drop=True)
            if df.empty:
                raise IntegridadError(f"GEIH {modulo}: AREA == '{AREA_BOGOTA_GEIH}' no dejó filas")
        df["FEX_C18"] = a_numero(df["FEX_C18"])
        if df["FEX_C18"].isna().any() or (df["FEX_C18"] <= 0).any():
            raise IntegridadError(f"GEIH {modulo}: FEX_C18 vacío o no positivo")
        df["FEX"] = df["FEX_C18"] / n_meses
        df.attrs.update(fuente="GEIH 2025", modulo=modulo, unidad=UNIDAD_GEIH[modulo], dominio=dominio, meses=meses,
                        n_meses=n_meses, filas_nacional_validadas=n_total, filas_por_mes=filas_mes,
                        peso="FEX = FEX_C18 / n_meses")
        salida[modulo] = df
    return salida[modulos] if solo_uno else salida


# ------------------------------------------------------------------------------------------------
# ENPH
# ------------------------------------------------------------------------------------------------
def _resolver_enph(nombre: str, permitir_rural: bool) -> Path:
    """Acepta ``carpeta/archivo.ext`` o un nombre suelto (con o sin extensión) único entre las carpetas permitidas."""
    if "/" in nombre:
        ruta = ENPH_DIR / nombre
        if not ruta.is_file():
            raise FileNotFoundError(f"ENPH: no existe {nombre}")
        candidatos = [ruta]
    else:
        candidatos = [p for c in ENPH_CARPETAS for p in (ENPH_DIR / c).glob("*")
                      if p.is_file() and nombre in (p.name, p.stem)]
        if not candidatos:
            raise FileNotFoundError(f"ENPH: no existe ningún archivo llamado {nombre!r}")
    permitidos = [p for p in candidatos if p.parent.name != "rural" or permitir_rural]
    if not permitidos:
        raise DominioError(f"ENPH rural está fuera de alcance (CLAUDE.md): {nombre!r}. Use permitir_rural=True solo si se pide explícito.")
    if len(permitidos) > 1:
        raise ValueError(f"nombre ambiguo {nombre!r}: use carpeta/archivo ({[p.parent.name + '/' + p.name for p in permitidos]})")
    return permitidos[0]


def _leer_enph(ruta: Path, columnas: Iterable[str] | None) -> pd.DataFrame:
    if ruta.suffix == ".txt":
        return _leer(ruta, sep="\t", encoding="utf-8", columnas=columnas)
    return _leer(ruta, sep=";", encoding="utf-8-sig", columnas=columnas)


@lru_cache(maxsize=1)
def _hogares_enph() -> tuple[frozenset, frozenset]:
    """(todos los DIRECTORIO, DIRECTORIO de Bogotá) de viviendas_hogares."""
    h = _leer_enph(ENPH_DIR / "hogares" / "viviendas_hogares.csv", ["DIRECTORIO", "DOMINIO"])
    if not h["DIRECTORIO"].is_unique:
        raise IntegridadError("viviendas_hogares: DIRECTORIO no es único (rompe la llave de hogar)")
    return frozenset(h["DIRECTORIO"]), frozenset(h.loc[h["DOMINIO"] == DOMINIO_BOGOTA_ENPH, "DIRECTORIO"])


def _registrar_union(**kw) -> dict:
    UNIONES.append(kw)
    print(f"[unión] {kw['nombre']}: {kw['pct_enlazado']:.4f} % de {kw['filas_izq']:,} filas enlazadas por {kw['llave']} (piso {kw['umbral']} %)")
    return kw


def cargar_enph(archivos, dominio: str = "bogota", permitir_rural: bool = False, columnas: Iterable[str] | None = None):
    """Carga archivos ENPH 2016-2017.

    ``archivos``: un nombre (DataFrame) o lista (dict). ``dominio``: ``"bogota"`` o ``"todo"``.
    Bogotá: ``DOMINIO == 'BOGOTÁ'`` en viviendas_hogares; el resto de tablas por ``DIRECTORIO`` (se reporta y exige
    100 % de enlace con viviendas_hogares). Añade ``FEX = FEX_C`` como float. Con ``columnas`` se añaden las llaves,
    ``FEX_C`` y ``DOMINIO`` cuando existe.
    """
    if dominio not in ("bogota", "todo"):
        raise ValueError(f"dominio ENPH inválido: {dominio!r} (use 'bogota' o 'todo')")
    solo_uno = isinstance(archivos, str)
    salida: dict[str, pd.DataFrame] = {}
    for nombre in _como_lista(archivos):
        ruta = _resolver_enph(nombre, permitir_rural)
        rel = ruta.relative_to(ENPH_DIR).as_posix()
        es_hogares = ruta.name == "viviendas_hogares.csv"
        usar = None if columnas is None else [*columnas, "DIRECTORIO", "FEX_C", *(["DOMINIO"] if es_hogares else [])]
        df = _leer_enph(ruta, usar)
        esperado = _filas_esperadas_enph(f"ENPH_2017/{rel}")
        if len(df) != esperado:
            raise IntegridadError(f"ENPH {rel}: {len(df)} filas leídas ≠ {esperado} en fuentes_datos.json")
        n_total = len(df)
        if dominio == "bogota":
            todos, bogota = _hogares_enph()
            if es_hogares:
                df = df[df["DOMINIO"] == DOMINIO_BOGOTA_ENPH]
            else:
                pct = 100 * df["DIRECTORIO"].isin(todos).mean()
                _registrar_union(nombre=f"{rel} -> viviendas_hogares", llave="DIRECTORIO", filas_izq=n_total,
                                 pct_enlazado=float(pct), umbral=UMBRAL_UNION_ENPH)
                if pct < UMBRAL_UNION_ENPH:
                    raise UnionError(f"ENPH {rel}: solo {pct:.4f} % de filas enlaza con viviendas_hogares por DIRECTORIO")
                df = df[df["DIRECTORIO"].isin(bogota)]
            df = df.reset_index(drop=True)
            if df.empty:
                raise IntegridadError(f"ENPH {rel}: el dominio Bogotá no dejó filas")
        df["FEX_C"] = a_numero(df["FEX_C"])
        if df["FEX_C"].isna().any() or (df["FEX_C"] <= 0).any():
            raise IntegridadError(f"ENPH {rel}: FEX_C vacío o no positivo")
        df["FEX"] = df["FEX_C"]
        unidad = ENPH_UNIDAD.get(ruta.stem, "registro de gasto")
        df.attrs.update(fuente="ENPH 2016-2017", archivo=rel, unidad=unidad, dominio=dominio,
                        filas_nacional_validadas=n_total, peso="FEX = FEX_C (factor del hogar, verificado)")
        salida[nombre] = df
    return salida[archivos] if solo_uno else salida


# ------------------------------------------------------------------------------------------------
# uniones
# ------------------------------------------------------------------------------------------------
def unir(izq: pd.DataFrame, der: pd.DataFrame, llave: list[str], *, nombre: str = "", umbral: float = UMBRAL_UNION,
         columnas_der: Iterable[str] | None = None) -> pd.DataFrame:
    """Unión izquierda muchos-a-uno que REPORTA el % de filas de ``izq`` enlazadas y falla bajo ``umbral``.

    ``der`` debe ser único por ``llave`` (si no, la unión duplicaría filas de ``izq``). El umbral es un piso:
    el % real queda en ``UNIONES`` y en ``attrs['union']``. No se admiten columnas repetidas fuera de la llave.
    """
    llave = list(llave)
    nombre = nombre or f"{izq.attrs.get('modulo', izq.attrs.get('archivo', 'izq'))} -> {der.attrs.get('modulo', der.attrs.get('archivo', 'der'))}"
    if columnas_der is not None:
        der = der[[*llave, *[c for c in columnas_der if c not in llave]]]
    if der.duplicated(llave).any():
        raise UnionError(f"{nombre}: el lado derecho no es único por {llave} (la unión duplicaría filas)")
    repetidas = (set(izq.columns) & set(der.columns)) - set(llave)
    if repetidas:
        raise UnionError(f"{nombre}: columnas en ambos lados fuera de la llave: {sorted(repetidas)}")
    salida = izq.merge(der, on=llave, how="left", indicator="_enlace", validate="m:1")
    pct = 100 * float((salida["_enlace"] == "both").mean()) if len(salida) else 0.0
    claves_der = der[llave].drop_duplicates()
    usadas = izq[llave].drop_duplicates().merge(claves_der, on=llave, how="inner")
    reg = _registrar_union(nombre=nombre, llave="+".join(llave), filas_izq=len(izq), filas_der=len(der),
                           pct_enlazado=pct, pct_der_usado=100 * len(usadas) / max(len(claves_der), 1), umbral=umbral)
    if len(salida) != len(izq):
        raise UnionError(f"{nombre}: la unión cambió el número de filas ({len(izq)} -> {len(salida)})")
    if pct < umbral:
        raise UnionError(f"{nombre}: solo {pct:.4f} % de filas enlazadas (< {umbral} %)")
    salida = salida.drop(columns="_enlace")
    salida.attrs.update(izq.attrs)
    salida.attrs["union"] = reg
    return salida


def unir_geih(izq: pd.DataFrame, der: pd.DataFrame, nivel: str = "persona", **kw) -> pd.DataFrame:
    """Unión GEIH entre módulos: ``DIRECTORIO+SECUENCIA_P+HOGAR`` (+ ``ORDEN`` si nivel='persona')."""
    llave = LLAVE_GEIH_PERSONA if nivel == "persona" else LLAVE_GEIH_HOGAR
    if "MES" in izq.columns and "MES" in der.columns:  # prudencia: uniones dentro del mismo mes (fuentes_datos.md §11)
        llave = llave + ["MES"]
    return unir(izq, der.drop(columns=[c for c in ("AREA", "FEX_C18", "FEX") if c in der.columns]), llave, **kw)


def unir_enph_hogar(izq: pd.DataFrame, hogares: pd.DataFrame, **kw) -> pd.DataFrame:
    """Gasto/persona → hogar por ``DIRECTORIO`` (exige 100 %). Uno-a-muchos del lado del gasto."""
    kw.setdefault("umbral", UMBRAL_UNION_ENPH)
    return unir(izq, hogares.drop(columns=[c for c in ("FEX_C", "FEX") if c in hogares.columns]), LLAVE_ENPH_HOGAR, **kw)


# ------------------------------------------------------------------------------------------------
# estrato
# ------------------------------------------------------------------------------------------------
def estrato_agrupado(estrato: pd.Series) -> pd.Series:
    """Estrato 1-6 → ``bajo (1-2)`` / ``medio (3-4)`` / ``alto (5-6)``. Cualquier otro valor (0, 9, vacío, 2.5…) → NaN.

    NO asigna a un grupo los códigos 0 ni 9: no son estratos (ver sdg.codigos). Devuelve Categorical ordenada.
    """
    n = a_numero(estrato)
    entero = n.where(n.notna() & (n == np.floor(n)))
    grupo = pd.Series(np.select([entero.isin([1, 2]), entero.isin([3, 4]), entero.isin([5, 6])], list(ESTRATO_GRUPOS), default=""),
                      index=estrato.index).replace("", np.nan)
    return pd.Series(pd.Categorical(grupo, categories=list(ESTRATO_GRUPOS), ordered=True), index=estrato.index, name="estrato_agrupado")
