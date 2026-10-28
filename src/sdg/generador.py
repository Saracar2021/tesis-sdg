"""Generador de transacciones sintéticas por reglas (WP6, Etapa 2; D15): capa interna → capa emitida.

Flujo, en dos capas
  CAPA INTERNA  Para cada perfil de ``sdg.priors.muestrear_perfiles`` se simula el gasto COMPLETO del hogar durante tres meses
                (categoría, monto, medio de pago). Cada (perfil, categoría) hereda los eventos de un hogar DONANTE de ENPH 2016-17
                (Bogotá), elegido de la celda estrato × quintil, del quintil o de Bogotá con la mezcla jerárquica calibrada en
                ``sdg.gasto_enph`` (P(celda) = n_ef/(n_ef+κ)). Los montos se actualizan a pesos de 2025 con el IPC (``sdg.ipc``;
                sin serie, factor 1,0 y la salida queda marcada «sin IPC»; con serie, deflactor único: IPC total nacional). El medio sale del medio principal del perfil (NC2R / P438).
  CAPA EMITIDA  Solo lo que vería un banco o una billetera: compras con tarjeta débito/crédito, PSE y transferencias, movimientos de
                billetera, ingresos, retiros en cajero/corresponsal, recargas de billetera y pagos de tarjeta de crédito. El efectivo
                no se emite: se acumula y sale como retiros periódicos. Sobre la capa interna se aplica una migración digital
                parametrizada (escenarios bajo/base/alto) porque ENPH 2016-17 no tiene billeteras ni transferencias.

Esquema de salida (una fila por movimiento; ver ``COLUMNAS``)
  capa ∈ {interna, emitida}; ``cuenta_tipo`` ∈ {banco, billetera, tarjeta_credito}; ``signo`` ∈ {+, -}.
  OBSERVABLES (lo que ve un modelo entrenado en filas emitidas): descripcion, monto, signo, fecha, cuenta_tipo.
  GOLD (etiqueta verdadera, para entrenar/evaluar clasificadores): categoria_n1, categoria_n2, medio_pago, formalidad_comercio, canal_p2p,
  fuente_etiqueta. AUXILIARES (NO son observables): id_interno, medio_enph, migrado_digital, origen, cuenta_id, perfil_id.

Supuestos y límites declarados (cada parámetro propio vive en ``docs/generador/parametros_propios.json`` con su fuente)
  * Unidad = HOGAR con un titular que concentra todo el gasto bancarizado; los extractos reales son de personas. Sobrestima el flujo por cuenta.
  * Donantes por categoría: dos categorías del mismo perfil pueden venir de hogares distintos (``donantes.modo = por_categoria``);
    un perfil puede gastar más que su ingreso (se reporta). ``por_hogar`` usa un solo donante para todo.
  * ENPH da el medio PRINCIPAL del hogar, no el de cada compra (``medios.p_uso_medio_principal``). Billeteras y transferencias salen solo
    de la migración digital y de las reglas de pagos recurrentes: la participación digital NO está anclada a una fuente primaria.
  * Calendario: tres meses fijos (``ventana.meses_referencia``); el día de cada evento es uniforme (ENPH no trae fecha); sin efectos de día
    de la semana ni quincena en el gasto. El saldo de las cuentas no se modela.
  * No se emiten GMF (4×1000), cuotas de manejo ni intereses; las compras a crédito se pagan completas el día de pago del mismo mes.
  * Las plantillas de descripción y la biblioteca de comercios son regla propia, no calibradas con los extractos reales (D14).
  * Determinista: ``SeedSequence(seed)`` repartida en flujos nombrados (``FLUJOS``); mismo pool, priors, parámetros, n y semilla → mismo resultado.
    Los valores dependen de la versión de numpy: el hash válido es el de la corrida con el ``.venv`` del repositorio.
"""
from __future__ import annotations

import calendar
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from sdg import carga
from sdg.comercios import CLASES_LINEA, Comercios, Plantillas
from sdg.priors import _categorica

RAIZ = carga.RAIZ
SEED = 42
DIR_PARAM = RAIZ / "docs" / "generador"
DIR_SALIDA = RAIZ / "outputs" / "generador"
DIR_POOL = DIR_SALIDA / "pool"
RUTA_PARAMETROS = DIR_PARAM / "parametros_propios.json"

FLUJOS = ("cuentas", "donantes", "replay", "medios", "overlay", "comercios", "retiros", "ingresos", "p2p", "descriptores")

CATEGORIAS_GASTO = ["alimentos_mercado", "comidas_fuera", "transporte", "vivienda_servicios", "telecom_conectividad", "salud",
                    "educacion", "entretenimiento", "vestuario_cuidado_personal", "hogar_articulos", "obligaciones_financieras", "otros"]

MEDIOS_NC2R = {"1": "tarjeta_debito", "2": "tarjeta_credito", "3": "efectivo", "4": "fiado_credito_tienda", "5": "bono_subsidio", "6": "otro_nd"}
MEDIOS_P438 = {"1": "tarjeta_debito", "2": "tarjeta_credito", "3": "efectivo", "4": "bono_subsidio", "5": "otro_nd", "6": "otro_nd"}
FUENTES_DIARIO = ("diario_hogar", "cf_hogar", "personal", "cf_personal")
MEDIOS_EFECTIVO = ("efectivo", "fiado_credito_tienda")   # salen de la cuenta como retiro (el fiado se salda en efectivo)
MEDIOS_NO_EMITIDOS = ("bono_subsidio", "otro_nd")        # ni emiten ni consumen efectivo
CUENTA_DE_MEDIO = {"tarjeta_debito": "banco", "transferencia_bancaria": "banco", "billetera_digital": "billetera", "tarjeta_credito": "tarjeta_credito"}
CLASES_P2P_TRANSFER = ("persona", "ambulante", "plaza", "feria", "tienda_barrio")   # contraparte con cara de persona si se paga por transferencia
CLASES_P2P_BILLETERA = ("persona", "ambulante")
N2_A_PERSONA = ("servicio_domestico", "informal_mototaxi")
CONCEPTOS_FIJOS = ("arriendo", "cuota_vivienda")          # mismo monto cada mes (sin jitter)

COLUMNAS = ["tx_id", "perfil_id", "mes_referencia", "fecha", "capa", "cuenta_id", "cuenta_tipo", "descripcion", "monto", "signo",
            "categoria_n1", "categoria_n2", "medio_pago", "formalidad_comercio", "canal_p2p", "fuente_etiqueta",
            "id_interno", "medio_enph", "migrado_digital", "origen"]
OBSERVABLES = ["descripcion", "monto", "signo", "fecha", "cuenta_tipo"]
GOLD = ["categoria_n1", "categoria_n2", "medio_pago", "formalidad_comercio", "canal_p2p", "fuente_etiqueta"]


# ================================================================================================
# parámetros
# ================================================================================================
def aplanar(p: dict) -> dict:
    """``{seccion.clave: valor}`` (y ``clave`` para los parámetros de nivel superior) desde parametros_propios.json."""
    plano = {}
    for k, v in p.items():
        if isinstance(v, dict) and "valor" in v:
            plano[k] = v["valor"]
        elif isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, dict) and "valor" in v2:
                    plano[f"{k}.{k2}"] = v2["valor"]
    return plano


def cargar_parametros(ruta: Path | str | None = None, overrides: dict | None = None) -> tuple[dict, dict]:
    """(``par`` plano con overrides aplicados, json original). Un override con clave inexistente es un error (evita typos silenciosos)."""
    crudo = json.loads(Path(ruta or RUTA_PARAMETROS).read_text(encoding="utf-8"))
    par = aplanar(crudo)
    for k, v in (overrides or {}).items():
        if k not in par:
            raise KeyError(f"override de parámetro inexistente: {k!r}")
        par[k] = v
    return par, crudo


# ================================================================================================
# pool (salida de la calibración; NO son microdatos)
# ================================================================================================
@dataclass
class Pool:
    eventos: pd.DataFrame
    recurrentes: pd.DataFrame
    hogares: pd.DataFrame
    mezcla: dict
    cuentas: pd.DataFrame
    meta: dict = field(default_factory=dict)


COLS_EVENTOS = ["DIRECTORIO", "FEX", "fuente", "tipo", "cap", "lugar", "clase_comercio", "categoria_n1", "categoria_n2", "valor", "factor", "factor_ipc", "domicilio"]
COLS_REC = ["DIRECTORIO", "FEX", "concepto", "categoria_n1", "categoria_n2", "valor", "factor", "factor_ipc"]
COLS_HOG = ["DIRECTORIO", "FEX", "estrato_agrupado", "quintil", "celda", "con_celda", "icmdug", "factor_ipc_total"]


def pool_desde_calibracion(R: dict) -> Pool:
    """Pool a partir del resultado de ``gasto_enph.construir()``."""
    meta = dict(modo_ipc=R["modo_ipc"], referencia_ipc=R.get("referencia_ipc"), ipc_aplicado=bool(R["diag"]["ipc"].get("aplicado", False)),
                ipc=R["diag"]["ipc"], kappa=float(R["kappa"]["kappa"]))
    return Pool(R["eventos"][COLS_EVENTOS].copy(), R["recurrentes"][COLS_REC].copy(), R["hogares"][COLS_HOG].copy(), R["mezcla"],
                R["cuentas"].copy(), meta)


def guardar_pool(pool: Pool, dir_pool: Path = DIR_POOL, dir_resumen: Path = DIR_SALIDA) -> dict:
    """Escribe el pool (gzip con mtime 0: contenido reproducible byte a byte) y las tablas pequeñas versionables. Devuelve los nombres."""
    dir_pool.mkdir(parents=True, exist_ok=True)
    dir_resumen.mkdir(parents=True, exist_ok=True)
    gz = {"method": "gzip", "mtime": 0}
    for nombre, df in (("eventos", pool.eventos), ("recurrentes", pool.recurrentes), ("hogares", pool.hogares)):
        df.to_csv(dir_pool / f"{nombre}.csv.gz", index=False, compression=gz, lineterminator="\n")
    (dir_resumen / "mezcla_donantes.json").write_text(json.dumps(pool.mezcla, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pool.cuentas.to_csv(dir_resumen / "estructura_cuentas.csv", index=False, lineterminator="\n")
    (dir_resumen / "calibracion_meta.json").write_text(json.dumps(pool.meta, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return {"pool": str(dir_pool), "resumen": str(dir_resumen)}


def cargar_pool(dir_pool: Path = DIR_POOL, dir_resumen: Path = DIR_SALIDA) -> Pool:
    """Lee el pool. Si falta, el mensaje dice cómo regenerarlo (``tools/construir_generador.py``)."""
    faltan = [n for n in ("eventos", "recurrentes", "hogares") if not (dir_pool / f"{n}.csv.gz").is_file()]
    if faltan or not (dir_resumen / "mezcla_donantes.json").is_file():
        raise FileNotFoundError("falta el pool del generador; corra primero tools/construir_generador.py "
                                f"(no encontrado: {faltan or 'mezcla_donantes.json'})")
    ev = pd.read_csv(dir_pool / "eventos.csv.gz", dtype={"DIRECTORIO": str, "lugar": str, "cap": str}, keep_default_na=False,
                     na_values=[])
    rec = pd.read_csv(dir_pool / "recurrentes.csv.gz", dtype={"DIRECTORIO": str}, keep_default_na=False, na_values=[])
    hog = pd.read_csv(dir_pool / "hogares.csv.gz", dtype={"DIRECTORIO": str, "celda": str, "estrato_agrupado": str}, keep_default_na=False,
                      na_values=[])
    hog["con_celda"] = hog["con_celda"].astype(str).str.lower().eq("true")
    for c in ("icmdug", "FEX", "factor_ipc_total"):
        hog[c] = pd.to_numeric(hog[c], errors="coerce")
    mezcla = json.loads((dir_resumen / "mezcla_donantes.json").read_text(encoding="utf-8"))
    cuentas = pd.read_csv(dir_resumen / "estructura_cuentas.csv", dtype={"estrato_agrupado": str})
    meta = json.loads((dir_resumen / "calibracion_meta.json").read_text(encoding="utf-8")) if (dir_resumen / "calibracion_meta.json").is_file() else {}
    return Pool(ev, rec, hog, mezcla, cuentas, meta)


def cargar_lugares(dir_param: Path = DIR_PARAM) -> pd.DataFrame:
    """Por clase de comercio: acepta_tarjeta (mínimo) y formalidad (modal). Tabla de parámetros, no microdatos."""
    t = pd.read_csv(dir_param / "lugares_compra.csv", dtype=str, keep_default_na=False)
    t["acepta_tarjeta"] = t["acepta_tarjeta"].astype(int)
    return t.groupby("clase_comercio").agg(acepta_tarjeta=("acepta_tarjeta", "min"), formalidad_comercio=("formalidad_comercio", "first"))


# ================================================================================================
# utilidades
# ================================================================================================
def redondear(x: np.ndarray, paso: int) -> np.ndarray:
    return np.maximum(paso, np.round(np.asarray(x, dtype=float) / paso) * paso).astype(np.int64)


def _sorteo(rng: np.random.Generator, pesos: np.ndarray, n: int) -> np.ndarray:
    p = np.asarray(pesos, dtype=float)
    return rng.choice(len(p), size=n, p=p / p.sum())


def plan_reposicion(dias: np.ndarray, montos: np.ndarray, umbral: int, horizonte: int, multiplo: int, minimo: int, maximo: int) -> list[tuple[int, int]]:
    """Reposiciones (retiros de efectivo, recargas de billetera) que sostienen unas salidas dadas.

    ``dias`` (ordenados) y ``montos``: salidas de efectivo (o de billetera) de un mes. Regla: el día d de una salida, si el saldo no cubre las
    salidas de los próximos ``umbral`` días, se repone lo que falta para cubrir ``horizonte`` días, redondeado hacia arriba a ``multiplo``,
    con mínimo ``minimo`` y partido en tramos de a lo sumo ``maximo``. El saldo inicial del mes es 0 (declarado: no hay arrastre entre meses)."""
    n = len(dias)
    if n == 0:
        return []
    cs = np.concatenate([[0.0], np.cumsum(montos, dtype=float)])
    out: list[tuple[int, int]] = []
    saldo, i = 0.0, 0
    while i < n:
        d = dias[i]
        j = int(np.searchsorted(dias, d, side="right"))
        hoy = cs[j] - cs[i]
        ku = int(np.searchsorted(dias, d + umbral, side="left"))
        if saldo < cs[ku] - cs[i]:
            kh = int(np.searchsorted(dias, d + horizonte, side="left"))
            falta = (cs[kh] - cs[i]) - saldo
            rep = int(max(minimo, np.ceil(falta / multiplo) * multiplo))
            while rep > 0:
                w = min(rep, maximo)
                out.append((int(d), int(w)))
                saldo += w
                rep -= w
        saldo -= hoy
        i = j
    return out


# ================================================================================================
# cuentas por perfil
# ================================================================================================
def asignar_cuentas(rng: np.random.Generator, perfiles: pd.DataFrame, tabla: pd.DataFrame, par: dict) -> pd.DataFrame:
    """banco / billetera / tarjeta de crédito por perfil, desde la estructura GEIH 2025 por estrato (``estructura_cuentas``).

    ``cuentas.modo = una`` reduce a una sola cuenta (banco si lo hay, si no billetera) y descarta tarjeta de crédito (modo de contingencia).
    Un banco, una billetera y una tarjeta como máximo por perfil (supuesto declarado); la tarjeta es del mismo banco."""
    n = len(perfiles)
    banco, bill, tc = np.zeros(n, int), np.zeros(n, int), np.zeros(n, int)
    u = rng.random(n)
    est = perfiles["estrato_agrupado"].to_numpy()
    for e in sorted(set(est)):
        m = est == e
        t = tabla[tabla["estrato_agrupado"] == e].sort_values(["banco", "billetera", "tc"]).reset_index(drop=True)
        if t.empty:
            raise ValueError(f"estructura de cuentas sin filas para el estrato {e!r}")
        cdf = np.cumsum(t["p"].to_numpy() / t["p"].sum())
        cdf[-1] = 1.0
        j = np.searchsorted(cdf, u[m], side="right")
        banco[m], bill[m], tc[m] = t["banco"].to_numpy()[j], t["billetera"].to_numpy()[j], t["tc"].to_numpy()[j]
    if par["cuentas.modo"] == "una":
        bill = np.where(banco == 1, 0, bill)
        tc[:] = 0
    elif par["cuentas.modo"] != "multiple":
        raise ValueError(f"cuentas.modo inválido: {par['cuentas.modo']!r}")
    bancos = par["cuentas.bancos"]
    nombres = np.array(sorted(bancos), dtype=object)
    banco_nombre = nombres[_sorteo(rng, np.array([bancos[k] for k in nombres]), n)]
    marca = np.where(rng.random(n) < par["cuentas.p_nequi_entre_billeteras"], "NEQUI", "DAVIPLATA").astype(object)
    return pd.DataFrame({"banco": banco, "billetera": bill, "tc": tc, "banco_nombre": banco_nombre, "billetera_marca": marca}, index=perfiles.index)


# ================================================================================================
# donantes
# ================================================================================================
class Donantes:
    """Sorteo jerárquico de hogares donantes: celda → quintil → Bogotá, con la mezcla de ``mezcla_donantes.json``. Pesos = FEX."""

    def __init__(self, hogares: pd.DataFrame, mezcla: dict, exigir_ingreso: bool = False):
        h = hogares[hogares["con_celda"]]
        if exigir_ingreso:
            h = h[h["icmdug"] > 0]
        self.mezcla = mezcla
        self.niv: dict = {}
        self._indexar(h)

    def _arr(self, g: pd.DataFrame):
        g = g.sort_values("DIRECTORIO", kind="mergesort")
        return g["DIRECTORIO"].to_numpy(dtype=object), np.cumsum(g["FEX"].to_numpy(dtype=float))

    def _indexar(self, h: pd.DataFrame) -> None:
        q = h["celda"].str.extract(r"\|Q(\d)")[0].astype(int)
        for c, g in h.groupby("celda"):
            self.niv[("c", c)] = self._arr(g)
        for k, g in h.groupby(q):
            self.niv[("q", int(k))] = self._arr(g)
        self.niv[("b", 0)] = self._arr(h)

    def muestrear(self, rng: np.random.Generator, celdas: np.ndarray) -> np.ndarray:
        n = len(celdas)
        u1, u2 = rng.random(n), rng.random(n)
        out = np.empty(n, dtype=object)
        for c in sorted(set(celdas)):
            if c not in self.mezcla:
                raise KeyError(f"la celda {c!r} no está en la mezcla de donantes")
            m = np.flatnonzero(celdas == c)
            mz = self.mezcla[c]
            q = int(c.split("|Q")[1])
            nivel = np.where(u1[m] < mz["celda"], 0, np.where(u1[m] < mz["celda"] + mz["quintil"], 1, 2))
            # si un nivel quedó vacío (p. ej. celda sin hogares con ingreso) se sube al siguiente
            llave = [("c", c), ("q", q), ("b", 0)]
            for l in (0, 1):
                if llave[l] not in self.niv:
                    nivel[nivel == l] = l + 1
            for l in (0, 1, 2):
                s = m[nivel == l]
                if not len(s):
                    continue
                ids, cum = self.niv[llave[l]]
                k = np.minimum(np.searchsorted(cum, u2[s] * cum[-1], side="right"), len(ids) - 1)
                out[s] = ids[k]
        return out


# ================================================================================================
# capa interna
# ================================================================================================
def _indices(df: pd.DataFrame, col_cat: str = "categoria_n1") -> dict:
    return df.groupby(["DIRECTORIO", col_cat]).indices


def _juntar(idx_map: dict, donantes: np.ndarray, cat: str) -> tuple[np.ndarray, np.ndarray]:
    perf, pos = [], []
    for p, d in enumerate(donantes):
        a = idx_map.get((d, cat))
        if a is not None:
            perf.append(np.full(len(a), p, dtype=np.int64))
            pos.append(a)
    if not perf:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    return np.concatenate(perf), np.concatenate(pos)


def candidatos(pool: Pool, donantes: dict, rng: np.random.Generator, par: dict) -> pd.DataFrame:
    """Eventos y pagos recurrentes de los donantes de cada (perfil, categoría), con su frecuencia mensual esperada (``factor``)."""
    ev, rec = pool.eventos, pool.recurrentes
    ie, ir = _indices(ev), _indices(rec)
    partes = []
    p_inm = par["arriendo.p_inmobiliaria"]
    for cat in CATEGORIAS_GASTO:
        d = donantes[cat]
        pe, xe = _juntar(ie, d, cat)
        e = ev.iloc[xe]
        partes.append(pd.DataFrame({
            "perfil": pe, "valor": e["valor"].to_numpy(), "factor": e["factor"].to_numpy(), "factor_ipc": e["factor_ipc"].to_numpy(),
            "categoria_n1": cat, "categoria_n2": e["categoria_n2"].to_numpy(), "clase_comercio": e["clase_comercio"].to_numpy(),
            "lugar": e["lugar"].to_numpy(), "domicilio": e["domicilio"].to_numpy(), "fuente": e["fuente"].to_numpy(), "cap": e["cap"].to_numpy(),
            "concepto": "", "recurrente": False}))
        pr, xr = _juntar(ir, d, cat)
        r = rec.iloc[xr]
        conc = r["concepto"].to_numpy()
        clase = np.where((conc == "arriendo") & (rng.random(len(r)) >= p_inm), "persona", "especializado")
        partes.append(pd.DataFrame({
            "perfil": pr, "valor": r["valor"].to_numpy(), "factor": r["factor"].to_numpy(), "factor_ipc": r["factor_ipc"].to_numpy(),
            "categoria_n1": cat, "categoria_n2": r["categoria_n2"].to_numpy(), "clase_comercio": clase, "lugar": "", "domicilio": 0,
            "fuente": "recurrente", "cap": "", "concepto": conc, "recurrente": True}))
    C = pd.concat(partes, ignore_index=True)
    return C.sort_values(["perfil", "recurrente", "categoria_n1"], kind="mergesort").reset_index(drop=True)


def expandir(C: pd.DataFrame, rng: np.random.Generator, par: dict, meses: list[tuple[int, int]]) -> pd.DataFrame:
    """Repite cada evento según su frecuencia mensual (redondeo estocástico), fija día y monto (IPC y jitter lognormal)."""
    base = np.floor(C["factor"].to_numpy())
    frac = C["factor"].to_numpy() - base
    partes = []
    for m in range(len(meses)):
        k = (base + (rng.random(len(C)) < frac)).astype(np.int64)
        d = C.iloc[np.repeat(np.arange(len(C)), k)].copy()
        d["mes"] = m
        partes.append(d)
    E = pd.concat(partes, ignore_index=True)
    dim = np.array([calendar.monthrange(a, b)[1] for a, b in meses])[E["mes"].to_numpy()]
    lo, hi = np.ones(len(E), dtype=int), dim.copy()
    arr = (E["concepto"] == "arriendo").to_numpy()
    srv = (E["recurrente"] & ~arr).to_numpy()
    lo[arr], hi[arr] = par["arriendo.dia_inicio"], par["arriendo.dia_fin"]
    lo[srv], hi[srv] = par["servicios.dia_inicio"], par["servicios.dia_fin"]
    hi = np.minimum(hi, dim)
    E["dia"] = (lo + np.floor(rng.random(len(E)) * (hi - lo + 1))).astype(int)
    sigma = par["donantes.jitter_sigma_log"]
    fijo = E["concepto"].isin(CONCEPTOS_FIJOS).to_numpy()
    z = np.where(fijo, 0.0, rng.standard_normal(len(E)) * sigma)
    E["monto"] = redondear(E["valor"].to_numpy() * E["factor_ipc"].to_numpy() * np.exp(z), par["donantes.redondeo_cop"])
    return E.drop(columns=["valor", "factor", "factor_ipc"]).reset_index(drop=True)


# ================================================================================================
# medios de pago
# ================================================================================================
def asignar_medio_enph(E: pd.DataFrame, perfiles: pd.DataFrame, priors: dict, rng: np.random.Generator, p_principal: float) -> tuple[np.ndarray, dict]:
    """Medio de cada compra: con prob. ``p_principal`` el principal del perfil (NC2R para el diario, P438 del subcapítulo para los menos
    frecuentes); con la restante, un sorteo de la distribución de la celda. Los pagos recurrentes no pasan por aquí."""
    orden = priors["orden_celdas"]
    icelda = {k: i for i, k in enumerate(orden)}
    cod_nc, cod_p4 = priors["categorias"]["nc2r"]["codigos"], priors["categorias"]["p438"]["codigos"]
    caps = sorted(c for c, t in priors["p438"].items() if t is not None)
    prob = np.stack([np.array([priors["nc2r"][k] for k in orden], dtype=float)] +
                    [np.array([priors["p438"][c][k] for k in orden], dtype=float) for c in caps])      # (S+1, celdas, 6)
    mapa = np.array([[MEDIOS_NC2R[c] for c in cod_nc]] + [[MEDIOS_P438[c] for c in cod_p4]] * len(caps), dtype=object)
    principal_nc = np.array([cod_nc.index(c) for c in perfiles["nc2r_forma_pago"]])
    principal_p4 = np.stack([np.array([cod_p4.index(c) for c in perfiles[f"p438_{cap}"]]) for cap in caps], axis=1) if caps else np.zeros((len(perfiles), 0), int)
    n = len(E)
    s = pd.Series(E["cap"]).map({c: i + 1 for i, c in enumerate(caps)}).fillna(0).astype(int).to_numpy()
    s = np.where(E["fuente"].isin(FUENTES_DIARIO).to_numpy() | E["recurrente"].to_numpy(), 0, s)
    p = E["perfil"].to_numpy()
    main = np.where(s == 0, principal_nc[p], principal_p4[p, np.maximum(s - 1, 0)] if len(caps) else 0)
    ic = perfiles["celda"].map(icelda).to_numpy()[p]
    alt = _categorica(rng.random(n), prob[s, ic])
    usa = rng.random(n) < p_principal
    code = np.where(usa, main, alt)
    medio = mapa[s, code]
    diag = dict(eventos_con_esquema_p438=int((s > 0).sum()), eventos_con_esquema_nc2r=int(((s == 0) & ~E["recurrente"].to_numpy()).sum()),
                caps_p438_disponibles=caps)
    return medio, diag


def aplicar_restricciones(E: pd.DataFrame, medio: np.ndarray, cuentas: pd.DataFrame, lugares: pd.DataFrame, par: dict) -> tuple[np.ndarray, dict]:
    """Reglas de factibilidad, en este orden: (a) crédito sin tarjeta → débito; (b) débito sin banco → billetera, si no efectivo;
    (c) tarjeta en un lugar que no la acepta → efectivo; (d) compra por internet en efectivo → débito/billetera si hay cuenta."""
    m = medio.copy()
    p = E["perfil"].to_numpy()
    tb, tw, tt = cuentas["banco"].to_numpy()[p] == 1, cuentas["billetera"].to_numpy()[p] == 1, cuentas["tc"].to_numpy()[p] == 1
    rec = E["recurrente"].to_numpy()
    cont = {}
    a = (m == "tarjeta_credito") & ~tt & ~rec
    cont["credito_sin_tarjeta"] = int(a.sum())
    m[a] = "tarjeta_debito"
    b = (m == "tarjeta_debito") & ~tb & ~rec
    cont["debito_sin_banco_a_billetera"] = int((b & tw).sum())
    cont["debito_sin_banco_a_efectivo"] = int((b & ~tw).sum())
    m[b & tw] = "billetera_digital"
    m[b & ~tw] = "efectivo"
    acepta = E["clase_comercio"].map(lugares["acepta_tarjeta"]).fillna(1).astype(int).to_numpy() == 1
    c = np.isin(m, ["tarjeta_debito", "tarjeta_credito"]) & ~acepta & ~rec
    cont["tarjeta_en_lugar_sin_datafono_a_efectivo"] = int(c.sum())
    m[c] = "efectivo"
    if par["medios.internet_sin_efectivo"]:
        d = (m == "efectivo") & (E["clase_comercio"] == "internet").to_numpy() & ~rec     # el catálogo/televentas se paga contra entrega
        cont["internet_efectivo_a_debito"] = int((d & tb).sum())
        cont["internet_efectivo_a_billetera"] = int((d & ~tb & tw).sum())
        m[d & tb] = "tarjeta_debito"
        m[d & ~tb & tw] = "billetera_digital"
    return m, cont


def migracion_digital(E: pd.DataFrame, medio: np.ndarray, cuentas: pd.DataFrame, rng: np.random.Generator, par: dict,
                      permisos: pd.DataFrame) -> tuple[np.ndarray, dict]:
    """Migración digital (PD7): una fracción ``f`` (escenario) de los eventos en efectivo o débito pasa a billetera o transferencia.

    La fracción es del TOTAL de eventos elegibles; ``digital.prop_billetera`` reparte entre billetera y transferencia. Dentro de cada canal
    la probabilidad es ∝ peso estructural de la categoría (``permisos_medios_digitales.csv``), con la constante fijada para que se cumpla el
    total (un solo margen: es el caso unidimensional del IPF, no hay margen de fila que respetar). Solo migran los perfiles que tienen la cuenta."""
    esc = par["digital.escenario"]
    f = float(par["digital.escenarios"][esc])
    pb = float(par["digital.prop_billetera"])
    p = E["perfil"].to_numpy()
    tb, tw = cuentas["banco"].to_numpy()[p] == 1, cuentas["billetera"].to_numpy()[p] == 1
    elegible = np.isin(medio, ["efectivo", "tarjeta_debito"]) & ~E["recurrente"].to_numpy()
    wb = E["categoria_n1"].map(permisos.set_index("categoria_n1")["peso_billetera"]).fillna(0.0).to_numpy()
    wt = E["categoria_n1"].map(permisos.set_index("categoria_n1")["peso_transferencia"]).fillna(0.0).to_numpy()
    n_el = int(elegible.sum())
    pw, pt = np.zeros(len(E)), np.zeros(len(E))
    if n_el:
        sb, st = (wb * (elegible & tw)).sum(), (wt * (elegible & tb)).sum()
        if sb > 0:
            pw = np.minimum(1.0, f * pb * n_el / sb * wb) * (elegible & tw)
        if st > 0:
            pt = np.minimum(1.0, f * (1 - pb) * n_el / st * wt) * (elegible & tb)
        exceso = pw + pt > 1.0
        if exceso.any():
            tot = (pw + pt)[exceso]
            pw[exceso], pt[exceso] = pw[exceso] / tot, pt[exceso] / tot
    u = rng.random(len(E))
    a_w = u < pw
    a_t = (~a_w) & (u < pw + pt)
    out = medio.copy()
    out[a_w], out[a_t] = "billetera_digital", "transferencia_bancaria"
    diag = dict(escenario=esc, fraccion_objetivo=f, prop_billetera=pb, eventos_elegibles=n_el, a_billetera=int(a_w.sum()), a_transferencia=int(a_t.sum()),
                fraccion_lograda=float((a_w.sum() + a_t.sum()) / n_el) if n_el else 0.0)
    return out, diag | dict(_mascara=(a_w | a_t))


def medio_recurrentes(E: pd.DataFrame, medio: np.ndarray, cuentas: pd.DataFrame, rng: np.random.Generator, par: dict) -> np.ndarray:
    """Pagos recurrentes: digitales con la prob. de ``recurrentes_digital`` si hay cuenta (banco → transferencia; solo billetera → billetera); si no, efectivo."""
    out = medio.copy()
    r = E["recurrente"].to_numpy()
    p = E["perfil"].to_numpy()
    conc = E["concepto"].to_numpy()
    prob = np.where(conc == "arriendo", par["recurrentes_digital.arriendo"], np.where(conc == "cuota_vivienda", par["recurrentes_digital.cuota_vivienda"],
                                                                                         par["recurrentes_digital.servicios"]))
    dig = rng.random(len(E)) < prob
    tb, tw = cuentas["banco"].to_numpy()[p] == 1, cuentas["billetera"].to_numpy()[p] == 1
    out[r] = "efectivo"
    digital_banco = np.where(conc == "cuota_vivienda", par["tipo_medio_hipoteca"], "transferencia_bancaria").astype(object)
    out[r & dig & tb] = digital_banco[r & dig & tb]
    out[r & dig & ~tb & tw] = "billetera_digital"
    return out


def contraparte(E: pd.DataFrame, medio: np.ndarray) -> np.ndarray:
    """``persona`` si el pago por transferencia/billetera va a una persona natural (tienda de barrio, vendedor, servicio doméstico, arriendo informal)."""
    clase, n2 = E["clase_comercio"].to_numpy(), E["categoria_n2"].to_numpy()
    pers = ((medio == "transferencia_bancaria") & np.isin(clase, CLASES_P2P_TRANSFER)) | ((medio == "billetera_digital") & np.isin(clase, CLASES_P2P_BILLETERA))
    pers |= np.isin(n2, N2_A_PERSONA) & np.isin(medio, ["transferencia_bancaria", "billetera_digital"])
    pers |= (E["concepto"].to_numpy() == "arriendo") & (clase == "persona") & np.isin(medio, ["transferencia_bancaria", "billetera_digital"])
    return np.where(pers, "persona", "comercio").astype(object)


# ================================================================================================
# generación
# ================================================================================================
def perfil_id(i) -> np.ndarray:
    return np.char.add("S", np.char.zfill(np.asarray(i).astype(str), 5))


def _flujos(seed: int) -> dict:
    return {k: np.random.default_rng(s) for k, s in zip(FLUJOS, np.random.SeedSequence(seed).spawn(len(FLUJOS)))}


def generar(pool: Pool, priors: dict, perfiles: pd.DataFrame, par: dict, seed: int = SEED, dir_param: Path = DIR_PARAM
            ) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Genera la muestra. ``perfiles``: salida de ``sdg.priors.muestrear_perfiles``. Devuelve (transacciones, perfiles_generados, info)."""
    rng = _flujos(seed)
    n = len(perfiles)
    perfiles = perfiles.reset_index(drop=True).copy()
    perfiles["celda"] = perfiles["estrato_agrupado"] + "|" + perfiles["quintil"]
    meses_txt = list(par["ventana.meses_referencia"])
    meses = [tuple(int(x) for x in s.split("-")) for s in meses_txt]
    dim = [calendar.monthrange(a, b)[1] for a, b in meses]
    lugares = cargar_lugares(dir_param)
    permisos = pd.read_csv(dir_param / "permisos_medios_digitales.csv", dtype={"categoria_n1": str})
    info: dict = {"n_perfiles": n, "semilla": seed, "meses": meses_txt, "escenario_digital": par["digital.escenario"], "modo_donantes": par["donantes.modo"],
                  "modo_cuentas": par["cuentas.modo"], "ipc_aplicado": bool(pool.meta.get("ipc_aplicado", False)),
                  "ipc": {k: v for k, v in (pool.meta.get("ipc") or {}).items() if k != "indice_base"}, "avisos": []}
    if not info["ipc_aplicado"]:
        info["avisos"].append("SIN IPC: montos en pesos de 2016-17 sin actualizar (factor 1,0). No usar para comparar niveles con 2025.")

    # --- cuentas e ingreso -------------------------------------------------------------------------------
    cu = asignar_cuentas(rng["cuentas"], perfiles, pool.cuentas, par)
    perfiles = pd.concat([perfiles, cu], axis=1)
    celdas = perfiles["celda"].to_numpy()
    modo = par["donantes.modo"]
    if modo == "por_hogar":
        d_todo = Donantes(pool.hogares, pool.mezcla, exigir_ingreso=True).muestrear(rng["donantes"], celdas)
        donantes = {c: d_todo for c in CATEGORIAS_GASTO}
        d_ing = d_todo
    elif modo == "por_categoria":
        dn = Donantes(pool.hogares, pool.mezcla)
        donantes = {c: dn.muestrear(rng["donantes"], celdas) for c in CATEGORIAS_GASTO}
        d_ing = Donantes(pool.hogares, pool.mezcla, exigir_ingreso=True).muestrear(rng["donantes"], celdas)
    else:
        raise ValueError(f"donantes.modo inválido: {modo!r}")
    h = pool.hogares.set_index("DIRECTORIO")
    perfiles["ingreso_mensual"] = (h["icmdug"].reindex(d_ing).to_numpy() * h["factor_ipc_total"].reindex(d_ing).to_numpy()).astype(float)
    asal = perfiles["posicion_ocupacional"].isin(par["ingreso.posiciones_asalariadas"]).to_numpy().copy()
    if par["ingreso.requiere_cotizacion_pension"]:
        asal &= (perfiles["P6920"] == "1").to_numpy()
    perfiles["asalariado"] = asal

    # --- capa interna ---------------------------------------------------------------------------------
    C = candidatos(pool, donantes, rng["replay"], par)
    E = expandir(C, rng["replay"], par, meses)
    medio_enph, d_medio = asignar_medio_enph(E, perfiles, priors, rng["medios"], par["medios.p_uso_medio_principal"])
    medio_enph = np.where(E["recurrente"].to_numpy(), "efectivo", medio_enph)       # los recurrentes no tienen medio ENPH
    medio, rest = aplicar_restricciones(E, medio_enph, cu, lugares, par)
    medio, d_mig = migracion_digital(E, medio, cu, rng["overlay"], par, permisos)
    migrado = d_mig.pop("_mascara")
    medio = medio_recurrentes(E, medio, cu, rng["overlay"], par)
    cont = contraparte(E, medio)
    E["medio_enph"], E["medio"], E["migrado"], E["contraparte"] = medio_enph, medio, migrado, cont
    E["ord"] = np.arange(len(E))
    info["medios"] = d_medio | dict(restricciones=rest, migracion=d_mig)

    # --- capa emitida -----------------------------------------------------------------------------------
    com, pl = Comercios(dir_param, par["descriptores.p_sucursal"]), Plantillas(dir_param)
    Z = []                                   # filas emitidas, sin descripción
    cid = lambda p, t: np.char.add(perfil_id(p), np.where(t == "banco", "-B", np.where(t == "billetera", "-W", "-T")))
    # compras y pagos recurrentes por canal digital
    emit = E["medio"].isin(list(CUENTA_DE_MEDIO)).to_numpy()
    X = E[emit].copy()
    X["cuenta_tipo"] = X["medio"].map(CUENTA_DE_MEDIO)
    X["linea"] = X["clase_comercio"].isin(CLASES_LINEA) | (X["domicilio"] == 1)
    X["sucursal_ok"] = X["medio"].isin(["tarjeta_debito", "tarjeta_credito", "billetera_digital"]) & ~X["recurrente"]
    nombres = com.asignar(rng["comercios"], X)
    X["comercio"], X["es_marca"] = nombres["comercio"].to_numpy(), nombres["es_marca"].to_numpy()
    cr = (X["categoria_n2"] == "credito_formal").to_numpy()
    X.loc[cr, "comercio"] = ["CUOTA CREDITO " + b for b in cu["banco_nombre"].to_numpy()[X.loc[cr, "perfil"].to_numpy()]]
    X.loc[cr, "es_marca"] = True
    t_ev = np.select([X["medio"] == "tarjeta_debito", X["medio"] == "tarjeta_credito",
                      (X["medio"] == "billetera_digital") & (X["contraparte"] == "persona"), X["medio"] == "billetera_digital",
                      (X["medio"] == "transferencia_bancaria") & (X["contraparte"] == "persona")],
                     ["compra_debito", "compra_credito", "p2p_enviada_billetera", "compra_billetera", "p2p_enviada_banco"], default="pago_pse")
    form_lugar = X["clase_comercio"].map(lugares["formalidad_comercio"]).fillna("pequeno_comercio_indeterminado")
    form = np.where(X["es_marca"], "formal", form_lugar)
    form = np.where(X["contraparte"] == "persona", np.where(np.isin(X["clase_comercio"], list(lugares.index)), form_lugar, "informal"), form)
    form = np.where(X["recurrente"] & (X["concepto"] != "arriendo"), "formal", form)
    es_p2p = (X["contraparte"] == "persona").to_numpy()
    Z.append(pd.DataFrame({
        "perfil": X["perfil"].to_numpy(), "mes": X["mes"].to_numpy(), "dia": X["dia"].to_numpy(), "ord": X["ord"].to_numpy(),
        "cuenta_tipo": X["cuenta_tipo"].to_numpy(), "tipo_evento": t_ev, "comercio": np.where(es_p2p, "", X["comercio"]),
        "monto": X["monto"].to_numpy(), "signo": "-", "categoria_n1": X["categoria_n1"].to_numpy(), "categoria_n2": X["categoria_n2"].to_numpy(),
        "medio_pago": X["medio"].to_numpy(), "formalidad_comercio": form, "canal_p2p": es_p2p,
        "fuente_etiqueta": np.where(es_p2p, "declaracion_voluntario", "texto"), "id_interno_ord": X["ord"].to_numpy(),
        "medio_enph": X["medio_enph"].to_numpy(), "migrado_digital": X["migrado"].to_numpy(),
        "origen": np.where(X["recurrente"], "pago_recurrente", "compra")}))

    # ingresos --------------------------------------------------------------------------------------------
    Y = perfiles["ingreso_mensual"].to_numpy()
    tb, tw, tt = cu["banco"].to_numpy() == 1, cu["billetera"].to_numpy() == 1, cu["tc"].to_numpy() == 1
    cta_ing = np.where(tb, "banco", "billetera").astype(object)
    r_in = rng["ingresos"]
    emp = com.empleador(r_in, n)
    ing = []
    for m in range(len(meses)):
        q = r_in.random(n) < par["ingreso.p_quincenal_asalariado"]
        # asalariados: nómina fin de mes (o quincenal 15 y fin de mes)
        base = Y * par["ingreso.fraccion_en_cuenta_asalariado"]
        for k, (dia, frac) in enumerate(((15, 0.5), (min(30, dim[m]), 0.5))):
            sel = asal & q
            ing.append(pd.DataFrame({"perfil": np.flatnonzero(sel), "mes": m, "dia": dia, "monto": np.round(base[sel] * frac).astype(np.int64), "tipo": "nomina"}))
        sel = asal & ~q
        ing.append(pd.DataFrame({"perfil": np.flatnonzero(sel), "mes": m, "dia": min(30, dim[m]), "monto": np.round(base[sel]).astype(np.int64), "tipo": "nomina"}))
        # no asalariados: k depósitos irregulares
        no = np.flatnonzero(~asal)
        tot = Y[no] * par["ingreso.fraccion_en_cuenta_otros"] * np.exp(0.05 * r_in.standard_normal(len(no)))
        kdep = np.maximum(1, r_in.poisson(par["ingreso.lambda_depositos_otros"], size=len(no)))
        pp = np.repeat(no, kdep)
        w = r_in.exponential(1.0, size=len(pp))
        s = np.bincount(np.repeat(np.arange(len(no)), kdep), weights=w, minlength=len(no))
        monto = redondear(np.repeat(tot, kdep) * w / np.repeat(s, kdep), 1000)
        p2p_like = r_in.random(len(pp)) < par["ingreso.p_p2p_otros"]
        ing.append(pd.DataFrame({"perfil": pp, "mes": m, "dia": 1 + np.floor(r_in.random(len(pp)) * dim[m]).astype(int), "monto": monto,
                                 "tipo": np.where(p2p_like, "ingreso_p2p", "consignacion")}))
    I = pd.concat(ing, ignore_index=True)
    I = I[(I["monto"] > 0) & np.isfinite(I["monto"])]
    c_ing = cta_ing[I["perfil"].to_numpy()]
    nom = (I["tipo"] == "nomina").to_numpy()
    p2pi = (I["tipo"] == "ingreso_p2p").to_numpy()
    tev = np.select([nom, p2pi & (c_ing == "banco"), p2pi, I["tipo"] == "consignacion"],
                    ["nomina", "p2p_recibida_banco", "p2p_recibida_billetera", "ingreso_consignacion"], default="ingreso_consignacion")
    # una consignación en efectivo exige banco; sin banco se trata como recibida por billetera
    tev = np.where((tev == "ingreso_consignacion") & (c_ing == "billetera"), "p2p_recibida_billetera", tev)
    p2pi = np.isin(tev, ["p2p_recibida_banco", "p2p_recibida_billetera"]) & ~nom
    Z.append(pd.DataFrame({
        "perfil": I["perfil"].to_numpy(), "mes": I["mes"].to_numpy(), "dia": I["dia"].to_numpy(), "ord": -1, "cuenta_tipo": c_ing, "tipo_evento": tev,
        "comercio": "", "monto": I["monto"].to_numpy(), "signo": "+", "categoria_n1": "ingreso",
        "categoria_n2": np.where(nom, "salario_nomina", "honorarios_ventas"), "medio_pago": "transferencia_bancaria",
        "formalidad_comercio": "no_aplica", "canal_p2p": p2pi, "fuente_etiqueta": np.where(p2pi, "declaracion_voluntario", "texto"),
        "id_interno_ord": -1, "medio_enph": "", "migrado_digital": False, "origen": np.where(nom, "nomina", "ingreso_no_asalariado")}))

    # P2P sin propósito ------------------------------------------------------------------------------------
    r_p = rng["p2p"]
    filas = []
    for m in range(len(meses)):
        for sentido, lam in (("env", par["p2p.lambda_enviadas_mes"]), ("rec", par["p2p.lambda_recibidas_mes"])):
            k = r_p.poisson(lam, size=n)
            pp = np.repeat(np.arange(n), k)
            usa_w = np.where(tb & tw, r_p.random(n) < par["p2p.p_billetera_si_ambas"], ~tb)[pp]
            monto = redondear(np.exp(np.log(np.maximum(Y[pp], 1.0) * par["p2p.mediana_fraccion_ingreso"]) + par["p2p.sigma_log"] * r_p.standard_normal(len(pp))), 1000)
            monto = np.maximum(monto, par["p2p.piso_cop"])
            cta = np.where(usa_w, "billetera", "banco").astype(object)
            filas.append(pd.DataFrame({"perfil": pp, "mes": m, "dia": 1 + np.floor(r_p.random(len(pp)) * dim[m]).astype(int), "monto": monto,
                                       "cuenta_tipo": cta, "sentido": sentido}))
    P = pd.concat(filas, ignore_index=True)
    env = (P["sentido"] == "env").to_numpy()
    wlt = (P["cuenta_tipo"] == "billetera").to_numpy()
    tev = np.where(env, np.where(wlt, "p2p_enviada_billetera", "p2p_enviada_banco"), np.where(wlt, "p2p_recibida_billetera", "p2p_recibida_banco"))
    Z.append(pd.DataFrame({
        "perfil": P["perfil"].to_numpy(), "mes": P["mes"].to_numpy(), "dia": P["dia"].to_numpy(), "ord": -1, "cuenta_tipo": P["cuenta_tipo"].to_numpy(),
        "tipo_evento": tev, "comercio": "", "monto": P["monto"].to_numpy(), "signo": np.where(env, "-", "+"), "categoria_n1": "transferencias_p2p",
        "categoria_n2": "", "medio_pago": np.where(wlt, "billetera_digital", "transferencia_bancaria"), "formalidad_comercio": "no_aplica",
        "canal_p2p": False, "fuente_etiqueta": "texto", "id_interno_ord": -1, "medio_enph": "", "migrado_digital": False, "origen": "p2p_sin_proposito"}))

    # retiros de efectivo ----------------------------------------------------------------------------------
    r_r = rng["retiros"]
    ef = E[E["medio"].isin(MEDIOS_EFECTIVO)].sort_values(["perfil", "mes", "dia", "ord"], kind="mergesort")
    ret = []
    pr = {k: par[f"retiros.{k}"] for k in ("umbral_dias", "horizonte_dias", "multiplo_cop", "minimo_cop", "maximo_cop")}
    for (p, m), g in ef.groupby(["perfil", "mes"], sort=True):
        for dia, monto in plan_reposicion(g["dia"].to_numpy(), g["monto"].to_numpy(), pr["umbral_dias"], pr["horizonte_dias"], pr["multiplo_cop"],
                                          pr["minimo_cop"], pr["maximo_cop"]):
            ret.append((p, m, dia, monto))
    R_ = pd.DataFrame(ret, columns=["perfil", "mes", "dia", "monto"]).astype("int64")
    if len(R_):
        corr = r_r.random(len(R_)) < par["retiros.p_corresponsal"]
        wlt = ~tb[R_["perfil"].to_numpy()]
        tev = np.where(wlt, np.where(corr, "retiro_corresponsal_billetera", "retiro_atm_billetera"), np.where(corr, "retiro_corresponsal_banco", "retiro_atm_banco"))
        Z.append(pd.DataFrame({
            "perfil": R_["perfil"].to_numpy(), "mes": R_["mes"].to_numpy(), "dia": R_["dia"].to_numpy(), "ord": -1,
            "cuenta_tipo": np.where(wlt, "billetera", "banco"), "tipo_evento": tev, "comercio": "", "monto": R_["monto"].to_numpy(), "signo": "-",
            "categoria_n1": "retiro_efectivo", "categoria_n2": np.where(corr, "corresponsal", "cajero_atm"),
            "medio_pago": np.where(wlt, "billetera_digital", "tarjeta_debito"), "formalidad_comercio": "no_aplica", "canal_p2p": False,
            "fuente_etiqueta": "texto", "id_interno_ord": -1, "medio_enph": "", "migrado_digital": False, "origen": "retiro"}))

    # pago de tarjeta de crédito ------------------------------------------------------------------------------
    tcX = X[(X["medio"] == "tarjeta_credito") & (X["dia"] <= par["tarjeta_credito.dia_pago"])]
    pagos = tcX.groupby(["perfil", "mes"], sort=True)["monto"].sum().reset_index()
    pagos["monto"] = np.round(pagos["monto"] * par["tarjeta_credito.fraccion_pago"]).astype(np.int64)
    pagos = pagos[pagos["monto"] > 0]
    for lado, cta, sg, cat, n2, mp in (("origen", "banco", "-", "obligaciones_financieras", "pago_tarjeta_credito", "transferencia_bancaria"),
                                       ("destino", "tarjeta_credito", "+", "obligaciones_financieras", "pago_tarjeta_credito", "transferencia_bancaria")):
        Z.append(pd.DataFrame({
            "perfil": pagos["perfil"].to_numpy(), "mes": pagos["mes"].to_numpy(), "dia": par["tarjeta_credito.dia_pago"], "ord": -1, "cuenta_tipo": cta,
            "tipo_evento": f"pago_tc_{lado}", "comercio": "", "monto": pagos["monto"].to_numpy(), "signo": sg, "categoria_n1": cat, "categoria_n2": n2,
            "medio_pago": mp, "formalidad_comercio": "no_aplica", "canal_p2p": False, "fuente_etiqueta": "texto", "id_interno_ord": -1, "medio_enph": "",
            "migrado_digital": False, "origen": "pago_tarjeta"}))

    # recargas de billetera (solo si hay banco y billetera) --------------------------------------------------------
    Zc = pd.concat(Z, ignore_index=True)
    sal_w = Zc[(Zc["cuenta_tipo"] == "billetera") & (Zc["signo"] == "-") & tb[Zc["perfil"].to_numpy()]].sort_values(["perfil", "mes", "dia"], kind="mergesort")
    rec = []
    for (p, m), g in sal_w.groupby(["perfil", "mes"], sort=True):
        for dia, monto in plan_reposicion(g["dia"].to_numpy(), g["monto"].to_numpy(), par["billetera.umbral_dias"], par["billetera.horizonte_dias"],
                                          par["billetera.multiplo_recarga_cop"], par["billetera.minimo_cop"], par["billetera.maximo_cop"]):
            rec.append((p, m, dia, monto))
    Rw = pd.DataFrame(rec, columns=["perfil", "mes", "dia", "monto"]).astype("int64")
    extra = []
    for lado, cta, sg in (("origen", "banco", "-"), ("destino", "billetera", "+")):
        extra.append(pd.DataFrame({
            "perfil": Rw["perfil"].to_numpy(), "mes": Rw["mes"].to_numpy(), "dia": Rw["dia"].to_numpy(), "ord": -1, "cuenta_tipo": cta,
            "tipo_evento": f"recarga_{lado}", "comercio": "", "monto": Rw["monto"].to_numpy(), "signo": sg, "categoria_n1": "movimiento_propio",
            "categoria_n2": "recarga_billetera", "medio_pago": "transferencia_bancaria", "formalidad_comercio": "no_aplica", "canal_p2p": False,
            "fuente_etiqueta": "texto", "id_interno_ord": -1, "medio_enph": "", "migrado_digital": False, "origen": "recarga_billetera"}))
    Zc = pd.concat([Zc, *extra], ignore_index=True)
    Zc[["perfil", "mes", "dia", "monto"]] = Zc[["perfil", "mes", "dia", "monto"]].astype("int64")

    # descripciones ---------------------------------------------------------------------------------------------
    pf = Zc["perfil"].to_numpy()
    desc, n2p = pl.descripciones(rng["descriptores"], Zc["tipo_evento"].to_numpy(), Zc["comercio"].to_numpy(dtype=object),
                                 cu["banco_nombre"].to_numpy()[pf], cu["billetera_marca"].to_numpy()[pf], emp[pf])
    Zc["descripcion"] = desc
    # el subtipo p2p lo fija la plantilla solo en transferencias SIN propósito
    sin_prop = (Zc["origen"] == "p2p_sin_proposito").to_numpy()
    Zc.loc[sin_prop, "categoria_n2"] = n2p[sin_prop]
    Zc["capa"] = "emitida"
    Zc["cuenta_id"] = cid(pf, Zc["cuenta_tipo"].to_numpy())

    # orden, identificadores y fechas -------------------------------------------------------------------------------
    Zc["_o"] = np.arange(len(Zc))
    Zc = Zc.sort_values(["perfil", "mes", "dia", "_o"], kind="mergesort").reset_index(drop=True)
    ym = np.array([f"{a % 100:02d}{b:02d}" for a, b in meses])
    Zc["mes_referencia"] = np.array(meses_txt)[Zc["mes"].to_numpy()]
    Zc["fecha"] = Zc["mes_referencia"] + "-" + Zc["dia"].astype(str).str.zfill(2)
    Zc["perfil_id"] = perfil_id(Zc["perfil"].to_numpy())
    Zc["tx_id"] = Zc["perfil_id"] + "-" + ym[Zc["mes"].to_numpy()] + "-" + (Zc.groupby(["perfil", "mes"]).cumcount() + 1).astype(str).str.zfill(3)

    # capa interna ------------------------------------------------------------------------------------------------------
    E = E.sort_values(["perfil", "mes", "dia", "ord"], kind="mergesort").reset_index(drop=True)
    E["tx_id"] = perfil_id(E["perfil"].to_numpy()) + "-" + ym[E["mes"].to_numpy()] + "-I" + (E.groupby(["perfil", "mes"]).cumcount() + 1).astype(str).str.zfill(4)
    mapa_id = dict(zip(E["ord"].to_numpy(), E["tx_id"].to_numpy()))
    Zc["id_interno"] = pd.Series(Zc["id_interno_ord"].to_numpy()).map(mapa_id).fillna("").to_numpy()
    lugar_form = E["clase_comercio"].map(lugares["formalidad_comercio"]).fillna("pequeno_comercio_indeterminado").to_numpy()
    cta_pago = pd.Series(E["medio"]).map(CUENTA_DE_MEDIO).fillna("").to_numpy()
    In = pd.DataFrame({
        "tx_id": E["tx_id"].to_numpy(), "perfil_id": perfil_id(E["perfil"].to_numpy()), "mes_referencia": np.array(meses_txt)[E["mes"].to_numpy()],
        "fecha": np.array(meses_txt)[E["mes"].to_numpy()] + "-" + E["dia"].astype(str).str.zfill(2), "capa": "interna",
        "cuenta_id": np.where(cta_pago != "", cid(E["perfil"].to_numpy(), cta_pago), ""), "cuenta_tipo": cta_pago, "descripcion": "",
        "monto": E["monto"].to_numpy(), "signo": "-", "categoria_n1": E["categoria_n1"].to_numpy(), "categoria_n2": E["categoria_n2"].to_numpy(),
        "medio_pago": E["medio"].to_numpy(), "formalidad_comercio": np.where(E["recurrente"] & (E["concepto"] != "arriendo"), "formal", lugar_form),
        "canal_p2p": (E["contraparte"] == "persona").to_numpy(), "fuente_etiqueta": "", "id_interno": "", "medio_enph": E["medio_enph"].to_numpy(),
        "migrado_digital": E["migrado"].to_numpy(), "origen": np.where(E["recurrente"], "pago_recurrente", "compra")})
    T = pd.concat([Zc[COLUMNAS], In[COLUMNAS]], ignore_index=True)
    T["_k"] = np.where(T["capa"] == "interna", 1, 0)
    T = T.sort_values(["perfil_id", "mes_referencia", "_k", "tx_id"], kind="mergesort").drop(columns="_k").reset_index(drop=True)
    T["canal_p2p"] = T["canal_p2p"].astype(bool)
    T["migrado_digital"] = T["migrado_digital"].astype(bool)

    perfiles_out = perfiles.assign(perfil_id=perfil_id(np.arange(n)))
    perfiles_out["tiene_banco"], perfiles_out["tiene_billetera"], perfiles_out["tiene_tarjeta_credito"] = cu["banco"], cu["billetera"], cu["tc"]
    info.update(_resumen(T, perfiles_out, E, par))
    return T, perfiles_out, info


def _resumen(T: pd.DataFrame, perfiles: pd.DataFrame, E: pd.DataFrame, par: dict) -> dict:
    """Diagnósticos de la muestra (todo JSON-serializable)."""
    em, it = T[T["capa"] == "emitida"], T[T["capa"] == "interna"]
    out: dict = {}
    out["filas"] = {"total": int(len(T)), "interna": int(len(it)), "emitida": int(len(em))}
    out["filas_emitidas_por_cuenta"] = {k: int(v) for k, v in em["cuenta_tipo"].value_counts().sort_index().items()}
    out["filas_emitidas_por_origen"] = {k: int(v) for k, v in em["origen"].value_counts().sort_index().items()}
    out["cuentas_perfiles"] = {c: float(perfiles[c].mean()) for c in ("tiene_banco", "tiene_billetera", "tiene_tarjeta_credito")}
    v = it.groupby("medio_pago")["monto"].sum()
    out["capa_interna_valor_por_medio_pago"] = {k: float(x / v.sum()) for k, x in v.items()}
    out["capa_interna_eventos_por_medio_pago"] = {k: float(x) for k, x in (it["medio_pago"].value_counts(normalize=True)).items()}
    out["valor_interno_pagado_desde_cuenta"] = float(it.loc[it["cuenta_tipo"].ne(""), "monto"].sum() / it["monto"].sum())
    gasto_pm = it.groupby("perfil_id")["monto"].sum() / len(par["ventana.meses_referencia"])
    ratio = (gasto_pm / perfiles.set_index("perfil_id")["ingreso_mensual"]).replace([np.inf], np.nan).dropna()
    out["gasto_sobre_ingreso_por_perfil"] = {"mediana": float(ratio.median()), "p90": float(ratio.quantile(0.9)), "frac_mayor_1": float((ratio > 1).mean())}
    cash = it.loc[it["medio_pago"].isin(MEDIOS_EFECTIVO), "monto"].sum()
    ret = em.loc[em["categoria_n1"] == "retiro_efectivo", "monto"].sum()
    out["efectivo"] = {"gasto_en_efectivo": float(cash), "retiros": float(ret), "retiros_sobre_gasto_efectivo": float(ret / cash) if cash else None}
    out["tarjeta_credito"] = {"compras": float(em.loc[(em["cuenta_tipo"] == "tarjeta_credito") & (em["signo"] == "-"), "monto"].sum()),
                              "pagos": float(em.loc[(em["origen"] == "pago_tarjeta") & (em["cuenta_tipo"] == "banco"), "monto"].sum())}
    out["p2p_proposito_declarado"] = {"filas": int(em["canal_p2p"].sum()), "fraccion_filas_emitidas": float(em["canal_p2p"].mean())}
    out["monto"] = {"mediana_emitida": float(em["monto"].median()), "p99_emitida": float(em["monto"].quantile(0.99))}
    return out


# ================================================================================================
# punto de entrada
# ================================================================================================
def generar_muestra(pool: Pool, priors: dict, n_perfiles: int, seed: int = SEED, overrides: dict | None = None, dir_param: Path = DIR_PARAM,
                    ruta_parametros: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Muestrea perfiles de ``priors`` (``sdg.priors.muestrear_perfiles``) y genera su sintético. Determinista dado (pool, priors, parámetros, n, seed)."""
    from sdg.priors import muestrear_perfiles
    par, crudo = cargar_parametros(ruta_parametros or (dir_param / "parametros_propios.json"), overrides)
    perfiles = muestrear_perfiles(priors, n_perfiles, seed)
    T, P, info = generar(pool, priors, perfiles, par, seed, dir_param)
    info["parametros_version"] = crudo.get("version")
    info["overrides"] = overrides or {}
    return T, P, info
