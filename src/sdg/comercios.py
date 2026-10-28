"""Nombres de comercio y descriptores de extracto para el generador por reglas (WP6, capa emitida de D15).

Qué hace: dado el tipo de evento (compra, retiro, recarga, nómina...) produce la ``descripcion`` que vería un banco o una billetera.
  * ``Comercios.asignar``: elige el nombre del comercio de ``docs/generador/comercios_curados.csv`` según categoría, subtipo, clase
    de lugar de compra (ENPH) y canal (presencial / en línea). Los nombres con ``{X}`` son genéricos (TIENDA LA ESQUINA, FRUVER DON JOSE).
  * ``Plantillas.descripciones``: aplica la plantilla de ``docs/generador/plantillas_descriptor.csv`` (COMPRA {C}, PAGO PSE {C},
    RETIRO ATM {B}...). El resultado imita el formato ANONIMIZADO de ``docs/datos_reales/02_protocolo_anonimizacion_v1.1.md`` (§3):
    personas → ``PERSONA``, secuencias largas de dígitos → ``#``, comercios intactos.

Límites declarados
  * Las plantillas y la biblioteca de comercios son regla propia (ejemplos de la guía de anotación y de la taxonomía v1, convenciones
    públicas de bancos y billeteras). NO se calibraron con los extractos reales (D14): la sintética es MÁS limpia y MÁS regular que un
    extracto real, y el TSTR sobre ella es una cota optimista de la capacidad de generalizar al texto real.
  * El comercio se elige condicionado a la categoría generativa. Solo las cadenas multicategoría (Éxito, Alkosto, Falabella, Mercado Libre)
    aparecen bajo más de una categoría; un anotador humano etiquetaría esas por el comercio, aquí la etiqueta gold es la categoría generativa.
  * Determinista: mismo ``rng`` y mismas entradas → mismas salidas (los grupos se recorren en orden fijo).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from sdg import carga

DIR_PARAM = carga.RAIZ / "docs" / "generador"
CLASES_LINEA = ("internet", "catalogo")


def _leer(nombre: str, dir_param: Path) -> pd.DataFrame:
    return pd.read_csv(dir_param / nombre, dtype=str, keep_default_na=False)


def _pesos(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return x / x.sum()


class Comercios:
    """Biblioteca de comercios curados + pools de palabras y sucursales."""

    def __init__(self, dir_param: Path = DIR_PARAM, p_sucursal: float = 0.5):
        cat = _leer("comercios_curados.csv", dir_param)
        cat["peso"] = cat["peso"].astype(float)
        cat["clases_set"] = cat["clases"].map(lambda s: frozenset(x for x in s.split("|") if x))
        cat["generico"] = cat["nombre"].str.contains("{X}", regex=False) | cat["nombre"].str.contains("{L}", regex=False)
        self.catalogo = cat
        pal = _leer("palabras_nombres.csv", dir_param)
        self.palabras = pal.loc[pal["tipo"] == "comercio", "palabra"].to_list()
        self.lugares = pal.loc[pal["tipo"] == "lugar", "palabra"].to_list()
        self.sucursales = _leer("sucursales_bogota.csv", dir_param)["sucursal"].to_list()
        self.empleadores = _leer("empleadores_ficticios.csv", dir_param)["empleador"].to_list()
        self.p_sucursal = float(p_sucursal)

    # ---- candidatos ------------------------------------------------------------------------------------
    def _candidatos(self, cat: str, n2: str, clase: str, linea: bool, concepto: str) -> pd.DataFrame:
        """Cascada de relajación: se exigen (categoría, subtipo, clase, canal, concepto) y se van soltando en orden fijo."""
        c = self.catalogo
        base = c[c["categoria_n1"] == cat]
        canal = "linea" if linea else "presencial"

        def f(df, n2_ok=True, clase_ok=True, canal_ok=True, concepto_ok=True):
            m = pd.Series(True, index=df.index)
            if n2_ok:
                m &= (df["categoria_n2"] == n2) | (df["categoria_n2"] == "")
            if clase_ok:
                m &= df["clases_set"].map(lambda s: clase in s)
            if canal_ok:
                m &= df["canal"].isin(["ambos", canal])
            m &= (df["concepto"] == concepto) if concepto_ok and concepto else (df["concepto"] == "")
            return df[m]

        for kw in (dict(), dict(clase_ok=False), dict(clase_ok=False, canal_ok=False)):
            r = f(base, **kw)
            if len(r):
                return r
        # un evento sin concepto (p. ej. servicio público registrado como artículo) puede usar los nombres con concepto del mismo subtipo
        r = base[(base["categoria_n2"] == n2) & (base["categoria_n2"] != "")]
        if len(r):
            return r
        r = base[base["concepto"] == ""]
        if len(r):
            return r
        return self.catalogo[self.catalogo["nombre"] == "ALMACEN {X}"].head(1)

    # ---- asignación -------------------------------------------------------------------------------------
    def asignar(self, rng: np.random.Generator, ev: pd.DataFrame) -> pd.DataFrame:
        """``ev``: columnas categoria_n1, categoria_n2, clase_comercio, linea (bool), concepto, sucursal_ok (bool). Devuelve ``comercio`` y ``es_marca``.

        Los grupos (categoría, subtipo, clase, canal, concepto) se recorren en orden lexicográfico; dentro de cada grupo se sortea con
        los pesos del catálogo. Para un grupo, la consulta al catálogo se hace una sola vez."""
        n = len(ev)
        nombre = np.empty(n, dtype=object)
        marca = np.zeros(n, dtype=bool)
        ev = ev.reset_index(drop=True)
        llaves = ev[["categoria_n1", "categoria_n2", "clase_comercio", "linea", "concepto"]]
        grupos = llaves.groupby(list(llaves.columns), sort=True).indices
        for k in sorted(grupos):
            idx = grupos[k]
            cat, n2, clase, linea, concepto = k
            cand = self._candidatos(cat, n2, clase, bool(linea), concepto)
            sel = rng.choice(len(cand), size=len(idx), p=_pesos(cand["peso"].to_numpy()))
            nom = cand["nombre"].to_numpy()[sel].astype(object)
            gen = cand["generico"].to_numpy()[sel]
            # nombres genéricos: {X} → palabra de comercio, {L} → toponimia (colegios, administraciones, inmobiliarias)
            if gen.any():
                pal = rng.integers(0, len(self.palabras), size=int(gen.sum()))
                top = rng.integers(0, len(self.lugares), size=int(gen.sum()))
                nom[gen] = [s.replace("{X}", self.palabras[j]).replace("{L}", self.lugares[t]) for s, j, t in zip(nom[gen], pal, top)]
            # marcas presenciales pagadas en el punto de venta: sucursal con probabilidad p_sucursal (no en facturas ni PSE)
            pres = (~gen) & (not bool(linea)) & ev["sucursal_ok"].to_numpy()[idx]
            if pres.any():
                u = rng.random(int(pres.sum()))
                suc = rng.integers(0, len(self.sucursales), size=int(pres.sum()))
                add = u < self.p_sucursal
                v = nom[pres]
                v[add] = [f"{s} {self.sucursales[j]}" for s, j in zip(v[add], suc[add])]
                nom[pres] = v
            nombre[idx] = nom
            marca[idx] = ~gen
        return pd.DataFrame({"comercio": nombre, "es_marca": marca}, index=ev.index)

    def empleador(self, rng: np.random.Generator, n: int) -> np.ndarray:
        return np.array(self.empleadores, dtype=object)[rng.integers(0, len(self.empleadores), size=n)]


class Plantillas:
    """Plantillas de descriptor por tipo de evento."""

    def __init__(self, dir_param: Path = DIR_PARAM):
        t = _leer("plantillas_descriptor.csv", dir_param)
        t["peso"] = t["peso"].astype(float)
        self.tabla = t
        self._por_tipo = {k: g.reset_index(drop=True) for k, g in t.groupby("tipo_evento")}

    def tipos(self) -> list[str]:
        return sorted(self._por_tipo)

    def descripciones(self, rng: np.random.Generator, tipo: np.ndarray, comercio: np.ndarray, banco: np.ndarray,
                      billetera: np.ndarray, empleador: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Una descripción por fila y el subtipo p2p que implica la plantilla (vacío si no aplica).

        Marcadores: {C} comercio, {B} banco, {W} billetera en mayúsculas, {Wt} billetera en título, {E} empleador."""
        n = len(tipo)
        out = np.empty(n, dtype=object)
        n2 = np.full(n, "", dtype=object)
        emp = empleador if empleador is not None else np.full(n, "", dtype=object)
        for t in sorted(set(tipo)):
            if t not in self._por_tipo:
                raise KeyError(f"tipo de evento sin plantilla: {t!r}")
            idx = np.flatnonzero(tipo == t)
            g = self._por_tipo[t]
            j = rng.choice(len(g), size=len(idx), p=_pesos(g["peso"].to_numpy()))
            pl = g["plantilla"].to_numpy()[j]
            n2[idx] = g["n2"].to_numpy()[j]
            out[idx] = [p.replace("{C}", c).replace("{B}", b).replace("{Wt}", w.title()).replace("{W}", w).replace("{E}", e)
                        for p, c, b, w, e in zip(pl, comercio[idx], banco[idx], billetera[idx], emp[idx])]
        out = np.array([" ".join(s.split()) for s in out], dtype=object)
        return out, n2
