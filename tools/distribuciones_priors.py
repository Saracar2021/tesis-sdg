"""Distribuciones para los priors: SOLO Bogotá urbano, con factor de expansión (chat 02).

Salida en outputs/distribuciones/ (CSV + distribuciones_priors.md + manifest). Toda cifra sale de código.
Ejecutar desde la raíz:  .venv\\Scripts\\python.exe tools\\distribuciones_priors.py

ENPH (hogar, FEX = FEX_C verificado como factor del hogar): estrato agrupado, quintil de ICGU (calculado dentro de
Bogotá), forma de pago principal NC2R_CC_P6, medio de pago por subcapítulo P438*.
GEIH (persona ocupada u hogar, FEX = FEX_C18 / n_meses): estrato agrupado (hogar), posición ocupacional,
componentes de formalidad, ingreso LABORAL INDIVIDUAL del ocupado (no es ingreso del hogar ni quintil de ingreso).
GEIH se calcula con 12 meses (principal) y con 11 (sin diciembre); se reporta toda diferencia > 1 p.p.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sdg import carga, codigos as cod  # noqa: E402
from sdg.medio_pago import ESTADOS, estado_p438  # noqa: E402
from sdg.pesos import cortes_ponderados, cruce, distribucion, fronteras, grupo_por_cortes  # noqa: E402

OUT = RAIZ / "outputs" / "distribuciones"
MIN_N_CELDA = 30          # solo para MARCAR celdas ralas; el umbral de soporte definitivo se declara en el Chat 05
UMBRAL_DIF_PP = 1.0       # sensibilidad de diciembre (CLAUDE.md)
SECCIONES: list[str] = []
INDICE: list[dict] = []


# ------------------------------------------------------------------------------------------------
# salida
# ------------------------------------------------------------------------------------------------
def es(x, d=2) -> str:
    """Número con separadores es-CO (miles «.», decimal «,»)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def md_tabla(df: pd.DataFrame, fmt: dict[str, int] | None = None) -> str:
    fmt = fmt or {}
    cab = "| " + " | ".join(df.columns) + " |\n|" + "|".join("---" for _ in df.columns) + "|\n"
    filas = []
    for _, r in df.iterrows():
        celdas = []
        for c in df.columns:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                celdas.append(es(float(v), fmt.get(c, 2)))
            elif isinstance(v, (int, np.integer)) and not isinstance(v, bool):
                celdas.append(es(float(v), 0))
            else:
                celdas.append(str(v))
        filas.append("| " + " | ".join(celdas) + " |")
    return cab + "\n".join(filas) + "\n"


def emitir(nombre: str, df: pd.DataFrame, *, titulo: str, meta: dict[str, str], nota: str = "", fmt: dict[str, int] | None = None,
           md_df: pd.DataFrame | None = None, en_md: bool = True) -> None:
    """Guarda el CSV (con metadatos en columnas) y añade la sección al informe."""
    OUT.mkdir(parents=True, exist_ok=True)
    csv = df.copy()
    for k in ("fuente", "dominio", "unidad", "peso"):
        csv[k] = meta[k]
    csv.to_csv(OUT / f"{nombre}.csv", index=False, encoding="utf-8")
    INDICE.append(dict(archivo=f"{nombre}.csv", titulo=titulo, filas=len(csv), **{k: meta[k] for k in ("fuente", "dominio", "unidad", "peso")}))
    txt = f"### {titulo}\n\n" + "".join(f"- **{k}:** {v}\n" for k, v in meta.items()) + "\n"
    if en_md:
        txt += md_tabla(df if md_df is None else md_df, fmt)
    else:
        txt += f"_(tabla de {len(df)} filas: solo en el CSV; el resumen está en la matriz siguiente)_\n"
    if nota:
        txt += f"\n{nota}\n"
    SECCIONES.append(txt + f"\nArchivo: `outputs/distribuciones/{nombre}.csv`\n")


def cols_dist(t: pd.DataFrame) -> pd.DataFrame:
    """Columnas legibles de ``distribucion``."""
    return t.rename(columns={"n": "n (sin ponderar)", "expandido": "expandido", "pct_con_respuesta": "% base con respuesta", "pct_total": "% del total"})[
        ["codigo", "categoria", "n (sin ponderar)", "expandido", "% base con respuesta", "% del total"]]


def estrato_col(serie: pd.Series) -> pd.Series:
    """Grupo (bajo/medio/alto) si el código es un estrato 1-6; si no, el código crudo (0, 9, vacío…) para reportarlo aparte."""
    g = carga.estrato_agrupado(serie)
    return g.astype(object).where(g.notna(), serie.astype(str))


def quintiles_icgu(h: pd.DataFrame) -> tuple[pd.Series, list[float]]:
    icgu = carga.a_numero(h["ICGU"])
    ok = icgu.notna()
    cortes = cortes_ponderados(icgu[ok], h.loc[ok, "FEX"], 5)
    return grupo_por_cortes(icgu, cortes), cortes


# ------------------------------------------------------------------------------------------------
# ENPH
# ------------------------------------------------------------------------------------------------
def tablas_enph() -> dict:
    h = carga.cargar_enph("viviendas_hogares", columnas=["P8520S1A1", "ICGU", "NC2R_CC_P6"])
    n_h, exp_h = len(h), float(h["FEX"].sum())
    base = {"fuente": "ENPH 2016-2017, hogares/viviendas_hogares.csv", "dominio": "Bogotá (DOMINIO = 'BOGOTÁ'), hogares",
            "unidad": "hogar", "peso": "FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)"}
    res = {"n_hogares": n_h, "hogares_expandidos": exp_h}

    # 1) estrato agrupado
    h["estrato_g"] = estrato_col(h["P8520S1A1"])
    t = distribucion(h, "estrato_g", etiquetas={g: g for g in carga.ESTRATO_GRUPOS}, motivos_sin_dato=cod.ESTRATO_ENPH_SIN_ESTRATO)
    emitir("enph_estrato_agrupado", cols_dist(t), titulo="ENPH · estrato agrupado (1-2 / 3-4 / 5-6)",
           meta={**base, "variable": "P8520S1A1 «Estrato para tarifa» (energía eléctrica)", "codigos": cod.ESTRATO_ENPH_FUENTE,
                 "denominador": "«% base con respuesta» = hogares con estrato 1-6; «% del total» = todos los hogares de Bogotá"},
           nota="Los códigos 0 y 9 NO son estratos y no se asignan a ningún grupo; el vacío se reporta como sin dato (no se imputa).")
    d = distribucion(h, "P8520S1A1", etiquetas={str(i): f"Estrato {i}" for i in range(1, 7)}, motivos_sin_dato=cod.ESTRATO_ENPH_SIN_ESTRATO)
    emitir("enph_estrato_detalle", cols_dist(d), titulo="ENPH · estrato para tarifa, sin agrupar", meta={**base, "variable": "P8520S1A1", "codigos": cod.ESTRATO_ENPH_FUENTE,
           "denominador": "igual que la tabla agrupada"})
    res["estrato"] = t

    # 2) quintiles de ICGU (dentro de Bogotá)
    h["quintil"], cortes = quintiles_icgu(h)
    icgu = carga.a_numero(h["ICGU"])
    filas = []
    for q in range(1, 6):
        m = h["quintil"] == q
        filas.append(dict(quintil=f"Q{q}", n=int(m.sum()), expandido=float(h.loc[m, "FEX"].sum()),
                          pct_hogares=100 * float(h.loc[m, "FEX"].sum()) / float(h.loc[h["quintil"].notna(), "FEX"].sum()),
                          icgu_min=float(icgu[m].min()), icgu_max=float(icgu[m].max()),
                          hogares_icgu_cero=int((icgu[m] == 0).sum())))
    tq = pd.DataFrame(filas)
    sin_icgu = int(icgu.isna().sum())
    emitir("enph_ingreso_quintil", tq, titulo="ENPH · quintiles de ICGU (ingreso corriente de la unidad de gasto), calculados dentro de Bogotá",
           meta={**base, "variable": "ICGU (ingreso del HOGAR / unidad de gasto; no es comparable con INGLABO de GEIH)",
                 "cortes": "menor ICGU con F ponderada ≥ j/5: " + ", ".join(es(c, 0) for c in cortes),
                 "denominador": f"hogares de Bogotá con ICGU (sin ICGU: {sin_icgu})"},
           nota="Los valores iguales a un corte quedan en el quintil inferior; por eso los % no son exactamente 20. Quintiles por ICGU del hogar, no per cápita.",
           fmt={"icgu_min": 0, "icgu_max": 0})
    res["quintil"], res["cortes_icgu"], res["sin_icgu"] = tq, cortes, sin_icgu
    res["fronteras_icgu"] = fronteras(icgu[icgu.notna()], h.loc[icgu.notna(), "FEX"], cortes)

    # 3) estrato agrupado × quintil (soporte de celdas)
    hh = h.assign(estrato_g=carga.estrato_agrupado(h["P8520S1A1"]), quintil_s=h["quintil"].map(lambda v: f"Q{int(v)}" if pd.notna(v) else np.nan))
    x = cruce(hh, "estrato_g", "quintil_s")
    x["pct_del_cruce"] = 100 * x["expandido"] / x["expandido"].sum()
    x["n_menor_30"] = x["n"] < MIN_N_CELDA
    x = x.rename(columns={"estrato_g": "estrato_agrupado", "quintil_s": "quintil"})
    x["estrato_agrupado"] = x["estrato_agrupado"].astype(str)
    completo = pd.MultiIndex.from_product([list(carga.ESTRATO_GRUPOS), [f"Q{i}" for i in range(1, 6)]], names=["estrato_agrupado", "quintil"])
    x = x.set_index(["estrato_agrupado", "quintil"]).reindex(completo).reset_index()
    x["n"] = x["n"].fillna(0).astype(int)
    x["n_menor_30"] = x["n"] < MIN_N_CELDA
    emitir("enph_estrato_x_quintil", x, titulo="ENPH · estrato agrupado × quintil de ICGU (soporte por celda)",
           meta={**base, "variable": "P8520S1A1 agrupado × quintil ICGU", "denominador": "hogares con estrato 1-6 e ICGU válido"},
           nota=f"`n_menor_30` marca celdas con menos de {MIN_N_CELDA} hogares (sin ponderar): informativo; el umbral de soporte y el encogimiento jerárquico se fijan en el Chat 05.")
    res["cruce"] = x

    # 4) forma de pago principal NC2R_CC_P6
    t4 = distribucion(h, "NC2R_CC_P6", etiquetas=cod.FORMA_PAGO_NC2R)
    emitir("enph_forma_pago_nc2r", cols_dist(t4), titulo="ENPH · forma de pago principal declarada por el hogar (NC2R_CC_P6)",
           meta={**base, "variable": "NC2R_CC_P6", "codigos": cod.FORMA_PAGO_NC2R_FUENTE,
                 "enunciado": "% de HOGARES cuya forma de pago principal declarada para los bienes del cuadernillo 2 urbano (gastos diarios, 14 días) es X",
                 "denominador": "«% base con respuesta» = hogares con respuesta; «% del total» = todos los hogares de Bogotá; el vacío se reporta, no se imputa"},
           nota="NO es una participación de transacciones ni de gasto: es una respuesta por hogar. El cuadernillo 2 urbano registra gastos diarios (compras frecuentes). "
                "Códigos según el cuadernillo 2 urbano (4 = Fiado, 5 = Bonos); NO usar el esquema de P438.")
    res["nc2r"] = t4

    # 5) P438* por subcapítulo
    mp = carga.cargar_enph("hogares/gastos_menos_frecuentes_medio_pago.csv")
    cols = [c for c in mp.columns if c.startswith("P438")]
    assert len(cols) == 29, cols
    assert mp["DIRECTORIO"].is_unique and len(mp) == n_h and set(mp["DIRECTORIO"]) == set(h["DIRECTORIO"])
    filas, cob = [], []
    exp_mp = float(mp["FEX"].sum())
    for c in cols:
        sub = c[4:]
        g = sub[0]
        d = distribucion(mp, c, etiquetas=cod.MEDIO_PAGO_P438)
        resp = d[d["tipo"] == "respuesta"]
        n_resp, exp_resp = int(resp["n"].sum()), float(resp["expandido"].sum())
        vac = d[d["codigo"] == ""]
        fuera = d[(d["tipo"] == "sin_dato") & (d["codigo"] != "")]
        cob.append(dict(columna=c, subcapitulo=sub, grupo=cod.GRUPOS_P438[g], detalle=cod.DETALLE_P438.get(sub, "(sin título de subbloque localizado)"),
                        n_con_respuesta=n_resp, n_vacio=int(vac["n"].sum()), n_codigo_fuera_de_lista=int(fuera["n"].sum()),
                        hogares_expandidos_con_respuesta=exp_resp, pct_hogares_bogota_con_respuesta=100 * exp_resp / exp_mp))
        for _, r in resp.iterrows():
            filas.append(dict(columna=c, subcapitulo=sub, grupo=cod.GRUPOS_P438[g], medio_codigo=r["codigo"], medio_pago=r["categoria"], n=int(r["n"]),
                              expandido=float(r["expandido"]), pct_de_hogares_con_respuesta=float(r["pct_con_respuesta"]), n_base_menor_30=n_resp < MIN_N_CELDA))
    largo, cobertura = pd.DataFrame(filas), pd.DataFrame(cob)
    meta5 = {**base, "fuente": "ENPH 2016-2017, hogares/gastos_menos_frecuentes_medio_pago.csv", "codigos": cod.MEDIO_PAGO_P438_FUENTE + " (NO es el esquema de NC2R_CC_P6)",
             "enunciado": "% de HOGARES (entre los que respondieron el subcapítulo) cuyo medio de pago principal en ese subcapítulo es X"}
    emitir("enph_p438_medio_pago_por_subcapitulo", largo, titulo="ENPH · medio de pago principal por subcapítulo de gasto (P438*), formato largo",
           meta={**meta5, "denominador": "hogares de Bogotá con código 1-6 en la columna del subcapítulo"},
           en_md=False)
    emitir("enph_p438_cobertura", cobertura, titulo="ENPH · cobertura de cada columna P438* (hogares con respuesta)",
           meta={**meta5, "denominador": "«pct_hogares_bogota_con_respuesta» = expandido con respuesta / total de hogares de Bogotá"},
           nota="Vacío = no respuesta O no aplica: se separan en la tabla `enph_p438_vacios` (cruce con los registros de artículos). " + cod.NOTA_P438_J +
                " Los subcapítulos son categoría × periodo de referencia "
                "(mes pasado / 3 meses / 12 meses) y cubren solo compras MENOS frecuentes.", fmt={"pct_hogares_bogota_con_respuesta": 2})
    matriz = largo.pivot_table(index=["subcapitulo", "grupo"], columns="medio_pago", values="pct_de_hogares_con_respuesta", aggfunc="first").reindex(
        columns=list(cod.MEDIO_PAGO_P438.values())).reset_index()
    matriz = matriz.merge(cobertura[["subcapitulo", "n_con_respuesta", "pct_hogares_bogota_con_respuesta"]], on="subcapitulo")
    emitir("enph_p438_matriz_categoria_x_medio", matriz.fillna(0.0), titulo="ENPH · matriz subcapítulo × medio de pago (% de hogares con respuesta)",
           meta={**meta5, "denominador": "hogares con código 1-6 en el subcapítulo (columna n_con_respuesta)"},
           nota="Esta es la tabla que usa el generador para condicionar `medio_pago` a la categoría de gasto (solo compras menos frecuentes). "
                "**Cobertura incompleta:** faltan los subcapítulos J14 y K11 (ver la sección «COBERTURA FALTANTE» más abajo, con el % de hogares afectados).",
           fmt={m: 2 for m in cod.MEDIO_PAGO_P438.values()} | {"pct_hogares_bogota_con_respuesta": 2})
    res["p438_cobertura"], res["p438_largo"] = cobertura, largo

    # 6) vacíos de P438*: no respuesta vs no aplica (cruce con los registros de artículos, por DIRECTORIO + CAP)
    art = carga.cargar_enph("hogares/gastos_menos_frecuentes_articulos.txt", columnas=["CAP", "FORMA"])
    art["compra"] = art["FORMA"] == "1"
    reg = art.groupby(["DIRECTORIO", "CAP"]).agg(n_registros=("CAP", "size"), n_compra=("compra", "sum")).reset_index()
    w = mp["FEX"]
    filas = []
    for c in cols:
        sub = c[4:]
        r = reg[reg["CAP"] == sub].set_index("DIRECTORIO")
        n_reg, n_comp = mp["DIRECTORIO"].map(r["n_registros"]).fillna(0), mp["DIRECTORIO"].map(r["n_compra"]).fillna(0)
        medio = mp[c].isin(list(cod.MEDIO_PAGO_P438))
        for nombre_base, base_ in (("cualquier registro en el subcapítulo", n_reg > 0), ("compra (FORMA=1, inferido)", n_comp > 0)):
            est = estado_p438(base_, medio)
            f = dict(subcapitulo=sub, base_de_compra=nombre_base)
            for e_ in ESTADOS:
                f[f"n_{e_}"], f[f"exp_{e_}"] = int((est == e_).sum()), float(w[est == e_].sum())
            f["n_hogares_con_base"] = f["n_responde"] + f["n_no_respuesta"]
            f["pct_no_respuesta_de_hogares_con_base"] = 100 * f["exp_no_respuesta"] / (f["exp_responde"] + f["exp_no_respuesta"])
            vac = f["exp_no_respuesta"] + f["exp_no_aplica"]
            f["pct_vacios_que_son_no_respuesta"] = 100 * f["exp_no_respuesta"] / vac
            f["pct_vacios_que_son_no_aplica"] = 100 * f["exp_no_aplica"] / vac
            f["pct_hogares_no_aplica"] = 100 * f["exp_no_aplica"] / float(w.sum())
            f["pct_medio_sin_base_de_hogares_sin_base"] = 100 * f["exp_medio_sin_base"] / (f["exp_no_aplica"] + f["exp_medio_sin_base"])
            filas.append(f)
    vac_t = pd.DataFrame(filas)
    md_cols = ["subcapitulo", "base_de_compra", "n_hogares_con_base", "n_no_respuesta", "pct_no_respuesta_de_hogares_con_base",
               "pct_vacios_que_son_no_respuesta", "pct_vacios_que_son_no_aplica", "n_medio_sin_base"]
    emitir("enph_p438_vacios", vac_t, titulo="ENPH · vacíos de P438*: no respuesta vs no aplica (cruce con registros de artículos)",
           meta={**meta5, "fuente": "ENPH 2016-2017, gastos_menos_frecuentes_medio_pago.csv × gastos_menos_frecuentes_articulos.txt (llave DIRECTORIO + CAP = subcapítulo)",
                 "definiciones": "responde = hay base de compra y medio 1-6 · **no respuesta** = hay base de compra y NO hay medio · **no aplica** = no hay base de compra y no hay medio · "
                                 "medio_sin_base = hay medio pero no hay registros/compras (inconsistencia entre tablas)",
                 "denominador": "pct_no_respuesta_de_hogares_con_base: hogares con base de compra; pct_vacios_*: hogares con columna vacía; pct_hogares_no_aplica: todos los hogares de Bogotá (todo ponderado con FEX_C)"},
           nota="«Base de compra» se reporta de dos formas porque FORMA (forma de adquisición) tiene códigos INFERIDOS (1 = compra; el cuadernillo lista las formas por letra, sin imprimir los números): "
                "(1) cualquier registro del hogar en el subcapítulo, que no depende de FORMA, y (2) registro con FORMA = 1. Si ambas coinciden en lo sustantivo, el supuesto sobre FORMA no pesa. "
                "Es un cruce entre dos tablas del mismo cuadernillo; no verifica que los registros de artículos estén completos.",
           md_df=vac_t[md_cols], fmt={c: 2 for c in md_cols if c.startswith("pct_")} | {"n_hogares_con_base": 0, "n_no_respuesta": 0, "n_medio_sin_base": 0})
    caps_sin_col = sorted(set(art["CAP"]) - {c[4:] for c in cols})
    gaps = []
    for cap in caps_sin_col:
        hh = reg[reg["CAP"] == cap]["DIRECTORIO"]
        gaps.append(dict(cap_en_articulos=cap, columna_p438="NO EXISTE", n_hogares_con_registros=int(hh.nunique()),
                         hogares_expandidos=float(mp.loc[mp["DIRECTORIO"].isin(hh), "FEX"].sum()),
                         pct_hogares_bogota=100 * float(mp.loc[mp["DIRECTORIO"].isin(hh), "FEX"].sum()) / float(w.sum())))
    gaps_t = pd.DataFrame(gaps)
    hh_union = reg[reg["CAP"].isin(caps_sin_col)]["DIRECTORIO"].unique()
    pct_union = 100 * float(mp.loc[mp["DIRECTORIO"].isin(hh_union), "FEX"].sum()) / float(w.sum())
    detalle = "; ".join(f"{r.cap_en_articulos}: {es(r.pct_hogares_bogota)} % ({es(r.n_hogares_con_registros, 0)} hogares en la muestra)" for r in gaps_t.itertuples())
    emitir("enph_p438_gaps", gaps_t, titulo="ENPH · COBERTURA FALTANTE de la matriz categoría × medio de pago: subcapítulos J14 y K11",
           meta={**meta5, "denominador": "% de hogares de Bogotá (expandido con FEX_C) con al menos un registro de artículos en el subcapítulo"},
           nota=(f"**Limitación del instrumento (declarar en la tesis).** La matriz categoría × medio de pago (`enph_p438_matriz_categoria_x_medio`) NO cubre los subcapítulos "
                 f"{', '.join(caps_sin_col)}: la base de artículos tiene registros en ellos, pero `gastos_menos_frecuentes_medio_pago` no trae columna P438 para ninguno "
                 f"(en el Cuadernillo 3 la pregunta (6) existe, pero el medio de pago no llegó a la base publicada). Hogares de Bogotá afectados (con registros en el subcapítulo): {detalle}; "
                 f"en conjunto, el {es(pct_union)} % de los hogares tiene al menos un registro en uno de los dos. Para esas categorías el generador no tiene medio de pago observado "
                 f"y no debe inventarse desde otro subcapítulo sin declararlo. " + cod.NOTA_P438_J))
    res["p438_vacios"], res["p438_gaps"] = vac_t, gaps_t
    return res


# ------------------------------------------------------------------------------------------------
# GEIH
# ------------------------------------------------------------------------------------------------
def geih_tablas(meses) -> dict[str, pd.DataFrame]:
    """Todas las distribuciones GEIH para un conjunto de meses (se usa con 12 y con 11 meses)."""
    oc = carga.cargar_geih("ocupados", meses=meses, columnas=["P6430", "P6440", "P6450", "P6920", "P6990", "INGLABO"])
    dh = carga.cargar_geih("datos_hogar", meses=meses, columnas=["P4030S1A1"])
    out: dict[str, pd.DataFrame] = {"_oc": oc, "_dh": dh}

    dh["estrato_g"] = estrato_col(dh["P4030S1A1"])
    out["geih_estrato_agrupado"] = distribucion(dh, "estrato_g", etiquetas={g: g for g in carga.ESTRATO_GRUPOS}, motivos_sin_dato=cod.ESTRATO_GEIH_SIN_ESTRATO)
    out["geih_estrato_detalle"] = distribucion(dh, "P4030S1A1", etiquetas={str(i): f"Estrato {i}" for i in range(1, 7)}, motivos_sin_dato=cod.ESTRATO_GEIH_SIN_ESTRATO)
    out["geih_posicion_ocupacional"] = distribucion(oc, "P6430", etiquetas=cod.POSICION_OCUPACIONAL_P6430)
    comp = []
    for var, etq, motivos, validos in [("P6440", cod.TIENE_CONTRATO_P6440, {}, None),
                                       ("P6450", cod.TIPO_CONTRATO_P6450, {"9": "No sabe, no informa"}, ["1", "2"]),
                                       ("P6920", cod.COTIZA_PENSION_P6920, {}, None),
                                       ("P6990", cod.AFILIADO_ARL_P6990, {"9": "No sabe, no informa"}, ["1", "2"])]:
        d = distribucion(oc, var, etiquetas=etq, motivos_sin_dato=motivos, validos=validos)
        d.insert(0, "variable", var)
        comp.append(d)
    out["geih_formalidad_componentes"] = pd.concat(comp, ignore_index=True)

    # posición ocupacional × cotiza a pensión (% dentro de cada posición; solo P6920 válido)
    x = cruce(oc[oc["P6920"].isin(cod.COTIZA_PENSION_P6920)], "P6430", "P6920")
    x["pct_dentro_de_posicion"] = 100 * x["expandido"] / x.groupby("P6430")["expandido"].transform("sum")
    x["posicion"] = x["P6430"].map(cod.POSICION_OCUPACIONAL_P6430)
    x["cotiza_pension"] = x["P6920"].map(cod.COTIZA_PENSION_P6920)
    out["geih_posicion_x_pension"] = x[["P6430", "posicion", "P6920", "cotiza_pension", "n", "expandido", "pct_dentro_de_posicion"]]

    # ingreso laboral individual del ocupado: grupos del 20 % con FEX (NO son quintiles de ingreso del hogar)
    ing = carga.a_numero(oc["INGLABO"])
    ok = ing.notna()
    cortes = cortes_ponderados(ing[ok], oc.loc[ok, "FEX"], 5)
    oc["grupo_ing_lab"] = grupo_por_cortes(ing, cortes)
    filas = []
    for q in range(1, 6):
        m = oc["grupo_ing_lab"] == q
        sub = oc[m & oc["P6920"].isin(cod.COTIZA_PENSION_P6920)]
        cot = float(sub.loc[sub["P6920"] == "1", "FEX"].sum()) / float(sub["FEX"].sum()) * 100 if len(sub) else np.nan
        filas.append(dict(grupo=f"G{q}", n=int(m.sum()), expandido=float(oc.loc[m, "FEX"].sum()),
                          pct_ocupados_con_ingreso=100 * float(oc.loc[m, "FEX"].sum()) / float(oc.loc[ok, "FEX"].sum()),
                          inglabo_min=float(ing[m].min()), inglabo_max=float(ing[m].max()), pct_cotiza_pension=cot))
    out["geih_ingreso_laboral_individual"] = pd.DataFrame(filas)
    out["_cortes_inglabo"] = pd.DataFrame({"corte": [f"c{j}" for j in range(1, 5)], "valor": cortes})
    out["_fronteras_inglabo"] = fronteras(ing[ok], oc.loc[ok, "FEX"], cortes)
    out["_sin_inglabo"] = pd.DataFrame({"n": [int((~ok).sum())], "n_total": [len(oc)]})
    return out


def sensibilidad(t12: dict, talt: dict) -> pd.DataFrame:
    """Compara todas las distribuciones GEIH de 12 meses (t12) contra un conjunto alterno de meses (talt): columnas v12, valt."""
    filas = []
    for nombre in [k for k in t12 if not k.startswith("_")]:
        a, b = t12[nombre], talt[nombre]
        if nombre == "geih_posicion_x_pension":
            m = a.merge(b, on=["P6430", "P6920"], suffixes=("_12", "_alt"))
            for _, r in m.iterrows():
                filas.append(dict(tabla=nombre, categoria=f"{r['posicion_12']} | {r['cotiza_pension_12']}", medida="pct_dentro_de_posicion",
                                  v12=r["pct_dentro_de_posicion_12"], valt=r["pct_dentro_de_posicion_alt"]))
        elif nombre == "geih_ingreso_laboral_individual":
            for col in ("pct_ocupados_con_ingreso", "pct_cotiza_pension"):
                for ra, rb in zip(a.itertuples(), b.itertuples()):
                    filas.append(dict(tabla=nombre, categoria=ra.grupo, medida=col, v12=getattr(ra, col), valt=getattr(rb, col)))
        else:
            llave = ["variable", "codigo"] if "variable" in a.columns else ["codigo"]
            m = a.merge(b, on=llave, suffixes=("_12", "_alt"), how="outer")
            for _, r in m.iterrows():
                cat = r.get("categoria_12") if pd.notna(r.get("categoria_12")) else r.get("categoria_alt")
                pref = f"{r['variable']}: " if "variable" in llave else ""
                for med in ("pct_con_respuesta", "pct_total"):
                    filas.append(dict(tabla=nombre, categoria=f"{pref}{cat}", medida=med, v12=r[f"{med}_12"], valt=r[f"{med}_alt"]))
    s = pd.DataFrame(filas).dropna(subset=["v12", "valt"], how="all")
    s["dif_pp_12_menos_alt"] = s["v12"] - s["valt"]
    s["supera_1pp"] = s["dif_pp_12_menos_alt"].abs() > UMBRAL_DIF_PP
    return s


def _cdf_en(t: dict, valor: float) -> tuple[float, float]:
    """(F ponderada de INGLABO ≤ valor, peso ponderado exactamente en valor), entre ocupados con INGLABO."""
    oc = t["_oc"]
    x = carga.a_numero(oc["INGLABO"])
    ok = x.notna()
    w = oc.loc[ok, "FEX"]
    return float(w[x[ok] <= valor].sum() / w.sum()), float(w[x[ok] == valor].sum() / w.sum())


def nota_artefacto_corte(t12: dict, talt: dict, cortes: pd.DataFrame, sup: pd.DataFrame, alt: str) -> str:
    """Explica (con cifras calculadas) si las diferencias > 1 p.p. vienen del desplazamiento de un corte de INGLABO."""
    if not len(sup):
        return ""
    solo_ing = sup["tabla"].eq("geih_ingreso_laboral_individual").all()
    movidos = cortes[cortes["inglabo_12"] != cortes["inglabo_alt"]]
    txt = "**Lectura.** "
    if solo_ing and len(movidos):
        v = float(movidos.iloc[0]["inglabo_alt"])
        f12, pe12 = _cdf_en(t12, v)
        fa, pea = _cdf_en(talt, v)
        txt += (f"Todas las diferencias > {es(UMBRAL_DIF_PP, 1)} p.p. están en los grupos de INGLABO y coinciden con un corte que se mueve entre 12 meses y {alt}. "
                f"En INGLABO = {es(v, 0)}: F ponderada = {es(100 * f12)} % con 12 meses y {es(100 * fa)} % {alt}, y ese valor concentra "
                f"{es(100 * pe12)} % / {es(100 * pea)} % del peso (ingreso redondeado). Es un efecto de frontera sobre un ingreso amontonado en valores redondos, "
                "no un cambio de composición (ver «Fronteras y amontonamiento»); las demás distribuciones no se mueven más de 1 p.p.\n")
    else:
        txt += "Hay diferencias > 1 p.p. fuera de los grupos de INGLABO o sin un corte desplazado: revisar antes de fijar priors.\n"
    return txt


def estabilidad_mensual() -> pd.DataFrame:
    """Distribución mes a mes (FEX_C18 dentro de cada mes) de las variables que alimentan los priors; evidencia corroborante, no prueba."""
    oc = carga.cargar_geih("ocupados", columnas=["P6430", "P6440", "P6450", "P6920", "P6990"])
    dh = carga.cargar_geih("datos_hogar", columnas=["P4030S1A1"])
    dh["P4030S1A1"] = estrato_col(dh["P4030S1A1"])
    filas = []
    for df, var, validos in [(oc, "P6430", list(cod.POSICION_OCUPACIONAL_P6430)), (oc, "P6440", ["1", "2"]), (oc, "P6450", ["1", "2"]),
                             (oc, "P6920", ["1", "2", "3"]), (oc, "P6990", ["1", "2"]), (dh, "P4030S1A1", list(carga.ESTRATO_GRUPOS))]:
        d = df[df[var].isin(validos)]
        acum = d.groupby(var)["FEX_C18"].sum() / d["FEX_C18"].sum() * 100
        for mes, dm in d.groupby(d["MES"].astype(int)):
            pm = dm.groupby(var)["FEX_C18"].sum() / dm["FEX_C18"].sum() * 100
            for cod_ in validos:
                filas.append(dict(variable=var, codigo=cod_, mes=int(mes), n_mes=int((dm[var] == cod_).sum()), n_base_mes=len(dm),
                                  pct_mes=float(pm.get(cod_, 0.0)), pct_12_meses=float(acum.get(cod_, 0.0))))
    e = pd.DataFrame(filas)
    e["desv_pp"] = e["pct_mes"] - e["pct_12_meses"]
    pr = (e["pct_12_meses"] / 100).clip(1e-9, 1 - 1e-9)
    e["z_binomial"] = e["desv_pp"] / (100 * np.sqrt(pr * (1 - pr) / e["n_base_mes"]))  # sin efecto de diseño: SUBESTIMA el error
    return e


# ------------------------------------------------------------------------------------------------
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    e = tablas_enph()

    t12 = geih_tablas(range(1, 13))
    t11 = geih_tablas(range(1, 12))
    t_sj = geih_tablas([m for m in range(1, 13) if m != 7])
    t_sm = geih_tablas([m for m in range(1, 13) if m != 3])
    oc, dh = t12["_oc"], t12["_dh"]
    base_oc = {"fuente": "GEIH 2025, ocupados.csv", "dominio": "Bogotá urbano (AREA = 11), 12 meses apilados", "unidad": "persona ocupada",
               "peso": "FEX = FEX_C18 / 12"}
    base_dh = {"fuente": "GEIH 2025, datos_hogar.csv", "dominio": "Bogotá urbano (AREA = 11), 12 meses apilados", "unidad": "hogar (promedio anual)",
               "peso": "FEX = FEX_C18 / 12"}
    emitir("geih_estrato_agrupado", cols_dist(t12["geih_estrato_agrupado"]), titulo="GEIH · estrato agrupado del hogar (1-2 / 3-4 / 5-6)",
           meta={**base_dh, "variable": "P4030S1A1 «Estrato para tarifa»", "codigos": cod.ESTRATO_GEIH_FUENTE,
                 "denominador": "«% base con respuesta» = hogares con estrato 1-6; «% del total» = todos los hogares de Bogotá"},
           nota="Los códigos 0 y 9 no se asignan a ningún grupo (el diccionario GEIH no los etiqueta).")
    emitir("geih_estrato_detalle", cols_dist(t12["geih_estrato_detalle"]), titulo="GEIH · estrato para tarifa, sin agrupar",
           meta={**base_dh, "variable": "P4030S1A1", "codigos": cod.ESTRATO_GEIH_FUENTE})
    emitir("geih_posicion_ocupacional", cols_dist(t12["geih_posicion_ocupacional"]), titulo="GEIH · posición ocupacional de los ocupados (P6430)",
           meta={**base_oc, "variable": "P6430 «En este trabajo … es»", "codigos": "Diccionario GEIH 2025, filas 708-715",
                 "denominador": "ocupados de Bogotá con P6430"},
           nota="El diccionario menciona «P6430 = 9» en la regla de P6430S1 (fila 716) pero no lista el código 9 entre las categorías; aquí cualquier código fuera de 1-8 se reporta como «código fuera de lista».")
    f = t12["geih_formalidad_componentes"]
    f2 = f.rename(columns={"n": "n (sin ponderar)", "pct_con_respuesta": "% base con respuesta", "pct_total": "% del total"})[
        ["variable", "codigo", "categoria", "n (sin ponderar)", "expandido", "% base con respuesta", "% del total"]]
    contrato_ok = int(((oc["P6450"] == "") == (oc["P6440"] == "2")).sum())
    emitir("geih_formalidad_componentes", f, titulo="GEIH · componentes de formalidad laboral (contrato, pensión, ARL)",
           meta={**base_oc, "variable": "P6440 (tiene contrato), P6450 (verbal/escrito), P6920 (cotiza a pensión), P6990 (afiliado a ARL)",
                 "codigos": "Diccionario GEIH 2025, filas 680-684 (P6440/P6450), 983-985 (P6920), 995-997 (P6990); P6450: 1 Verbal, 2 Escrito, 9 No sabe (NO 3)",
                 "denominador": "P6450: «% base con respuesta» = con contrato y P6450 en {1,2}; P6990 y P6920: ocupados con respuesta válida"},
           nota="No se define aquí una variable «formal/informal» compuesta: es decisión metodológica pendiente (cada componente se reporta por separado). "
                f"P6450 vacío ⇔ P6440 = 2 (sin contrato, no aplica) en {es(contrato_ok, 0)} de {es(len(oc), 0)} ocupados-mes.",
           md_df=f2)
    x = t12["geih_posicion_x_pension"]
    emitir("geih_posicion_x_pension", x, titulo="GEIH · posición ocupacional × cotiza a pensión (% dentro de cada posición)",
           meta={**base_oc, "variable": "P6430 × P6920", "denominador": "ocupados con P6920 válido, dentro de cada posición"})
    ig = t12["geih_ingreso_laboral_individual"]
    cz, sin = t12["_cortes_inglabo"], t12["_sin_inglabo"].iloc[0]
    emitir("geih_ingreso_laboral_individual", ig, titulo="GEIH · ingreso laboral individual del ocupado (INGLABO), grupos del 20 % de los ocupados con ingreso",
           meta={**base_oc, "variable": "INGLABO: ingreso laboral de la PERSONA (no es ingreso del hogar; no comparable con ICGU; estos grupos NO son quintiles de ingreso)",
                 "cortes": "menor INGLABO con F ponderada ≥ j/5: " + ", ".join(es(v, 0) for v in cz["valor"]),
                 "denominador": f"ocupados con INGLABO informado (sin INGLABO: {es(sin['n'], 0)} de {es(sin['n_total'], 0)} ocupados-mes)"},
           fmt={"inglabo_min": 0, "inglabo_max": 0})

    # sensibilidad: sin diciembre (regla CLAUDE.md), sin julio (pendiente de explicar) y sin marzo (hallazgo del escaneo de ocupados)
    alternos = {"diciembre": ("sin diciembre (ene-nov, FEX_C18/11)", t11), "julio": ("sin julio (11 meses, FEX_C18/11)", t_sj), "marzo": ("sin marzo (11 meses, FEX_C18/11)", t_sm)}
    resumen_sens = {}
    for clave, (etq, talt) in alternos.items():
        s = sensibilidad(t12, talt)
        s.to_csv(OUT / f"geih_sensibilidad_{clave}.csv", index=False, encoding="utf-8")
        sup = s[s["supera_1pp"]]
        resumen_sens[clave] = (s, sup)
        cortes_dif = pd.DataFrame({"corte": cz["corte"], "inglabo_12": t12["_cortes_inglabo"]["valor"], "inglabo_alt": talt["_cortes_inglabo"]["valor"]})
        cortes_dif["dif_relativa_%"] = 100 * (cortes_dif["inglabo_12"] - cortes_dif["inglabo_alt"]) / cortes_dif["inglabo_alt"]
        sec = (f"### GEIH · sensibilidad a {clave} (12 meses vs. {etq})\n\n"
               f"- **Regla (CLAUDE.md):** cada distribución GEIH se calcula con los 12 meses y con el conjunto alterno; se reporta toda diferencia > {es(UMBRAL_DIF_PP, 1)} p.p.\n"
               f"- **Comparaciones:** {es(len(s), 0)} (tabla × categoría × medida) · **con |diferencia| > {es(UMBRAL_DIF_PP, 1)} p.p.: {es(len(sup), 0)}** · máx. |dif| = {es(s['dif_pp_12_menos_alt'].abs().max())} p.p.\n"
               f"- **Ocupados Bogotá:** 12 meses = {es(len(oc), 0)} filas; alterno = {es(len(talt['_oc']), 0)} filas.\n\n")
        sec += (md_tabla(sup[["tabla", "categoria", "medida", "v12", "valt", "dif_pp_12_menos_alt"]]) if len(sup) else "Ninguna diferencia supera el umbral.\n")
        sec += "\nCortes de INGLABO (relativos, %; no son p.p.):\n\n" + md_tabla(cortes_dif, {"inglabo_12": 0, "inglabo_alt": 0})
        sec += "\n" + nota_artefacto_corte(t12, talt, cortes_dif, sup, etq)
        sec += f"\nArchivo: `outputs/distribuciones/geih_sensibilidad_{clave}.csv`\n"
        SECCIONES.append(sec)
    s, sup = resumen_sens["diciembre"]

    # fronteras y amontonamiento (limitación declarada; los cortes NO se cambian a fijos)
    fr = [t12["_fronteras_inglabo"].assign(variable="INGLABO (GEIH, ocupados, Bogotá)", escenario="12 meses"),
          t11["_fronteras_inglabo"].assign(variable="INGLABO (GEIH, ocupados, Bogotá)", escenario="sin diciembre"),
          t_sj["_fronteras_inglabo"].assign(variable="INGLABO (GEIH, ocupados, Bogotá)", escenario="sin julio"),
          t_sm["_fronteras_inglabo"].assign(variable="INGLABO (GEIH, ocupados, Bogotá)", escenario="sin marzo"),
          e["fronteras_icgu"].assign(variable="ICGU (ENPH, hogares, Bogotá)", escenario="todos los hogares")]
    fr = pd.concat(fr, ignore_index=True)[["variable", "escenario", "corte", "valor", "objetivo_pct", "masa_bajo_el_valor_pct", "masa_en_el_valor_pct",
                                          "cdf_hasta_el_valor_pct", "sobrepaso_pp", "n_en_el_valor", "fraccion_del_monton_bajo_objetivo"]]
    fr.to_csv(OUT / "fronteras_amontonamiento.csv", index=False, encoding="utf-8")
    maxmasa = fr.groupby("variable")["masa_en_el_valor_pct"].max()
    SECCIONES.append("### Fronteras de grupo y amontonamiento en valores redondos (LIMITACIÓN)\n\n"
                     "- **Qué se mide:** para cada frontera de los grupos del 20 % (4 por variable), el % del peso que cae EXACTAMENTE en el valor de la frontera "
                     "(`masa_en_el_valor_pct`) y en qué punto de ese montón cae el percentil objetivo (`fraccion_del_monton_bajo_objetivo`: 0 = al inicio, 1 = al final).\n"
                     f"- **Máximo % de masa en un solo valor:** " + "; ".join(f"{k}: {es(v)} %" for k, v in maxmasa.items()) + ".\n"
                     "- **Limitación declarada (aplica a INGLABO, NO a ICGU: en ICGU ninguna frontera concentra más del 0,1 % del peso):** el ingreso laboral individual se reporta en valores redondos, por lo que la frontera de un grupo del 20 % cae DENTRO de un montón: "
                     "el percentil objetivo se alcanza en medio de un valor que reúne varios puntos porcentuales de la población, y quién queda en el grupo inferior o superior "
                     "depende de la regla de desempate (aquí: los iguales al corte van al grupo inferior). Con cualquier perturbación de la muestra o de los pesos, "
                     "la frontera puede saltar de un valor redondo al siguiente. Los % por grupo no son exactamente 20 y las fronteras no son estables ante cambios de meses. "
                     "**No se cambió a cortes fijos** (decisión de Sara, 20 sep 2026); se declara como limitación de la calibración por quintil de ingreso.\n\n"
                     + md_tabla(fr, {"valor": 0, "n_en_el_valor": 0, "fraccion_del_monton_bajo_objetivo": 2})
                     + "\nArchivo: `outputs/distribuciones/fronteras_amontonamiento.csv`\n")

    m = estabilidad_mensual()
    m.to_csv(OUT / "geih_estabilidad_mensual.csv", index=False, encoding="utf-8")
    peor = m.loc[m.groupby("variable")["desv_pp"].apply(lambda s_: s_.abs().idxmax())][["variable", "codigo", "mes", "n_mes", "n_base_mes", "pct_mes", "pct_12_meses", "desv_pp", "z_binomial"]]
    SECCIONES.append("### GEIH · estabilidad mes a mes de las variables que alimentan los priors\n\n"
                     "- **Qué es:** distribución por mes (FEX_C18 dentro del mes) frente a la de los 12 meses, Bogotá (AREA = 11). Contraste empírico exigido por CLAUDE.md "
                     "(comparabilidad semántica GEIH 2025).\n- **Alcance:** detecta saltos grandes; con ~1.000 ocupados por mes hay ruido muestral de varios p.p. "
                     "`z_binomial` = desviación / error binomial simple SIN efecto de diseño (subestima el error real: el diseño es por conglomerados). "
                     "Es evidencia corroborante, NO prueba de que el formulario 2025 sea el de 2024. No incluye P6500 ni P5222S*/medio de pago de GEIH (no se usan en este entregable).\n"
                     "- **Mayor desviación por variable:**\n\n" + md_tabla(peor, {"n_mes": 0, "n_base_mes": 0}) +
                     "\nArchivo: `outputs/distribuciones/geih_estabilidad_mensual.csv` (todas las categorías × meses).\n")

    # informe
    cab = ("# Distribuciones para los priors — Bogotá urbano\n\n"
           "> Generado por `tools/distribuciones_priors.py`. Toda cifra sale de código. **Dominio: Bogotá urbano (caso de estudio), no nacional.** "
           "Cifras expandidas con factor de expansión; no se calcularon errores estándar (los archivos no traen identificador de segmento). "
           "Las cifras ENPH son 2016-2017 (una fila por hogar); las de GEIH son 2025 (12 meses apilados, ver sensibilidad a diciembre).\n\n"
           "**Fuentes de códigos (cada esquema se mapea solo con la suya):** estrato ENPH → Manual ENPH (Pregunta 4); estrato GEIH → Diccionario GEIH 2025 fila 32; "
           "P438* → Cuadernillo 3 (1 débito, 2 crédito, 3 efectivo, **4 bonos, 5 cheques**, 6 otro); NC2R_CC_P6 → Cuadernillo 2 urbano "
           "(1 débito, 2 crédito, 3 efectivo, **4 fiado, 5 bonos**, 6 otra).\n\n"
           "**No comparables entre fuentes:** ICGU (ENPH, ingreso del hogar) e INGLABO (GEIH, ingreso laboral individual).\n\n"
           f"Hogares ENPH Bogotá: {es(e['n_hogares'], 0)} (sin ponderar), {es(e['hogares_expandidos'], 0)} expandidos.\n\n---\n\n")
    (OUT / "distribuciones_priors.md").write_text(cab + "\n\n".join(SECCIONES), encoding="utf-8")

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = "desconocido"
    (OUT / "manifest_distribuciones.json").write_text(json.dumps({
        "script": "tools/distribuciones_priors.py", "commit_base": commit, "pandas": pd.__version__, "numpy": np.__version__, "python": sys.version.split()[0],
        "semilla": "no aplica (sin aleatoriedad)", "min_n_celda_marca": MIN_N_CELDA, "umbral_sensibilidad_pp": UMBRAL_DIF_PP,
        "salidas": INDICE, "uniones": carga.UNIONES}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"OK: {len(INDICE)} tablas en outputs/distribuciones/ ; > {es(UMBRAL_DIF_PP, 1)} pp: " + ", ".join(f"{k}: {len(v[1])}/{len(v[0])}" for k, v in resumen_sens.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
