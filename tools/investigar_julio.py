"""Investigación de julio 2025 en GEIH: estrato (P4030S1A1) de datos_hogar se desvía en Bogotá (chat 02).

Preguntas (criterio de Sara, 20 sep 2026):
  1. Serie mensual completa de estrato (6 categorías + 0, 9, vacío) y tasa de sin dato: ¿se mueve «sin dato» (artefacto de codificación)
     o se mueve entre categorías vecinas (3 vs 4 / 1-2)?
  2. ¿Se repite a nivel nacional y en las 23 ciudades (AREA no vacío)? Si sí, no es un problema de la submuestra de Bogotá.
  3. ¿Otras variables del mismo módulo (datos_hogar) se mueven en julio? Se compara contra los otros 11 meses (z empírico con la
     desviación entre meses, que incorpora el efecto de diseño) y contra lo que implicaría el cambio de mezcla de estrato.
  4. Contraste: las mismas variables de ocupados (persona) en Bogotá.
Salida: outputs/julio/ (CSV + julio_estrato.md). Ejecutar:  .venv\\Scripts\\python.exe tools\\investigar_julio.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from sdg import carga  # noqa: E402

OUT = RAIZ / "outputs" / "julio"
MES_FOCO = 7
MIN_PCT = 2.0  # se ignoran códigos con media < 2 % (z inestable)
EXCLUIR = {"DIRECTORIO", "SECUENCIA_P", "HOGAR", "ORDEN", "MES", "PERIODO", "FEX_C18", "FEX", "AREA", "mes", "REGIS", "CLASE", "DPTO", "P4030S1A1"}


CONCLUSION = """
## 6. Lectura (sin cifras nuevas: todas están en las tablas de arriba)

- **No es «sin dato».** En Bogotá la tasa de sin dato/no estrato en julio no se mueve; lo que cambia es la mezcla entre categorías vecinas: en julio baja el estrato 3
  (y con él el grupo 3-4) y suben 1 y 2 (grupo 1-2); el estrato alto no se mueve (§1, §3).
- **No es solo la submuestra de Bogotá.** En las 23 ciudades julio es también el único mes con |z| > 2 en bajo y medio, con el mismo signo y más fuerte; a nivel nacional el mismo
  sentido aparece atenuado y ya no es exclusivo de julio (§3).
- **Otras variables del módulo:** julio no es el mes más extremo con frecuencia mayor que los demás meses en `datos_hogar`; en `ocupados` de Bogotá tampoco (§4, §5).
  La comprobación de mezcla (§4b) tiene poca potencia: las demás variables casi no dependen del estrato, así que no permite distinguir «cambió la composición de la muestra»
  de «cambió cómo se codificó el estrato».
- **Estado: SIN EXPLICAR.** No hay evidencia de un artefacto de codificación (sin dato) ni de un problema exclusivo de Bogotá, pero tampoco una explicación de composición.
  Se produjo la sensibilidad sin julio (`outputs/distribuciones/geih_sensibilidad_julio.csv`) y se registra como **evidencia a favor de pedir al DANE el control de cambios de
  las etapas 2501-2512** (es evidencia corroborante para consultar, no prueba de un cambio de instrumento).
- **Hallazgo colateral:** en `ocupados` de Bogotá el mes más extremo es MARZO (columna `mes03` de `escaneo_resumen.csv`), no julio. Se produjo también la sensibilidad sin marzo.
"""


def es(x, d=2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def md_tabla(df: pd.DataFrame, fmt: dict | None = None) -> str:
    fmt = fmt or {}
    cab = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "|".join("---" for _ in df.columns) + "|\n"
    filas = []
    for _, r in df.iterrows():
        cel = []
        for c in df.columns:
            v = r[c]
            cel.append(es(float(v), fmt.get(c, 2)) if isinstance(v, (float, np.floating)) else (es(float(v), 0) if isinstance(v, (int, np.integer)) and not isinstance(v, bool) else str(v)))
        filas.append("| " + " | ".join(cel) + " |")
    return cab + "\n".join(filas) + "\n"


def porcentajes_mensuales(df: pd.DataFrame, col: str, w: str = "FEX_C18") -> pd.DataFrame:
    t = df.pivot_table(index="mes", columns=col, values=w, aggfunc="sum").fillna(0.0)
    return 100 * t.div(t.sum(axis=1), axis=0)


def z_empirico(s: pd.Series) -> pd.Series:
    """z de cada mes frente a los otros 11: (x_m − media_otros) / sd_otros. Usa la variación entre meses, que incluye el efecto de diseño."""
    out = {}
    for m in s.index:
        o = s.drop(m)
        sd = o.std(ddof=1)
        out[m] = (s[m] - o.mean()) / sd if sd > 0 else 0.0
    return pd.Series(out)


def escaneo(df: pd.DataFrame, columnas: list[str], w: str = "FEX_C18") -> pd.DataFrame:
    filas = []
    for v in columnas:
        p = porcentajes_mensuales(df, v, w)
        for c in p.columns:
            s = p[c]
            if s.mean() < MIN_PCT:
                continue
            z = z_empirico(s)
            filas.append(dict(variable=v, codigo=str(c), media_pct=float(s.mean()), mes_mas_extremo=int(z.abs().idxmax()), z_abs_max=float(z.abs().max()),
                              z_julio=float(z[MES_FOCO]), rango_abs_julio=int(z.abs().rank(ascending=False)[MES_FOCO])))
    return pd.DataFrame(filas)


def resumen_escaneo(f: pd.DataFrame, nombre: str) -> dict:
    conteo = f["mes_mas_extremo"].value_counts().reindex(range(1, 13), fill_value=0)
    return dict(escaneo=nombre, variables_codigo=len(f), **{f"mes{m:02d}": int(conteo[m]) for m in range(1, 13)},
                julio_absz_gt3=int((f["z_julio"].abs() > 3).sum()), julio_absz_gt2=int((f["z_julio"].abs() > 2).sum()))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    d = carga.cargar_geih("datos_hogar", dominio="todo")
    d["mes"] = d["MES"].astype(int)
    d["estrato_g"] = carga.estrato_agrupado(d["P4030S1A1"]).astype(object)
    d["estrato_g"] = d["estrato_g"].where(d["estrato_g"].notna(), "sin dato / no estrato")
    d["P4030S1A1_c"] = d["P4030S1A1"].replace("", "vacío")
    dominios = {"Bogotá (AREA=11)": d[d["AREA"] == carga.AREA_BOGOTA_GEIH], "23 ciudades/A.M. (AREA no vacío)": d[d["AREA"] != ""], "Nacional (todo)": d}

    # 1-2) series de estrato por dominio
    largo, zs, sd_filas = [], [], []
    for nom, df in dominios.items():
        p = porcentajes_mensuales(df, "P4030S1A1_c")
        n = df.groupby("mes").size()
        for mes in p.index:
            for c in p.columns:
                largo.append(dict(dominio=nom, mes=int(mes), categoria=str(c), pct=float(p.loc[mes, c]), n_hogares_mes=int(n[mes])))
        sd = p[[c for c in p.columns if c in ("0", "9", "vacío")]].sum(axis=1)
        for mes in p.index:
            sd_filas.append(dict(dominio=nom, mes=int(mes), pct_sin_dato_o_no_estrato=float(sd[mes]), n_hogares_mes=int(n[mes])))
        pg = porcentajes_mensuales(df, "estrato_g")
        for c in pg.columns:
            s = pg[c]
            z = z_empirico(s)
            pr = s.mean() / 100
            se_bin = 100 * np.sqrt(pr * (1 - pr) / n.mean()) if 0 < pr < 1 else np.nan
            zs.append(dict(dominio=nom, categoria=c, media_pct=float(s.mean()), pct_julio=float(s[MES_FOCO]), sd_entre_meses=float(s.std(ddof=1)),
                           se_binomial=float(se_bin), deff_aprox=float((s.std(ddof=1) / se_bin) ** 2) if se_bin == se_bin else np.nan,
                           z_julio=float(z[MES_FOCO]), rango_abs_julio=int(z.abs().rank(ascending=False)[MES_FOCO]),
                           meses_con_absz_gt2=", ".join(str(int(m)) for m in z.index if abs(z[m]) > 2) or "ninguno"))
    serie = pd.DataFrame(largo)
    serie.to_csv(OUT / "estrato_serie_mensual.csv", index=False, encoding="utf-8")
    sin_dato = pd.DataFrame(sd_filas)
    sin_dato.to_csv(OUT / "estrato_sin_dato_mensual.csv", index=False, encoding="utf-8")
    z_est = pd.DataFrame(zs)
    z_est.to_csv(OUT / "estrato_z_julio.csv", index=False, encoding="utf-8")

    # 3) otras variables de datos_hogar
    cand = [c for c in d.columns if c not in EXCLUIR and c not in ("estrato_g", "P4030S1A1_c") and d[c].nunique() <= 20]
    res, escan = [], {}
    for nom, df in dominios.items():
        f = escaneo(df, cand)
        f.insert(0, "dominio", nom)
        escan[nom] = f
        res.append(resumen_escaneo(f, f"datos_hogar · {nom}"))
    pd.concat(escan.values()).to_csv(OUT / "datos_hogar_otras_variables_escaneo.csv", index=False, encoding="utf-8")

    # 3b) ¿lo que se mueve en julio es compatible con la MEZCLA de estrato? (Bogotá)
    b = dominios["Bogotá (AREA=11)"]
    bv = b[b["estrato_g"].isin(list(carga.ESTRATO_GRUPOS))]
    es_jul = bv["mes"] == MES_FOCO
    mezcla7 = bv[es_jul].groupby("estrato_g")["FEX_C18"].sum() / bv[es_jul]["FEX_C18"].sum()
    mezclao = bv[~es_jul].groupby("estrato_g")["FEX_C18"].sum() / bv[~es_jul]["FEX_C18"].sum()
    filas = []
    for v in cand:
        t = bv.pivot_table(index="estrato_g", columns=v, values="FEX_C18", aggfunc="sum", observed=True).fillna(0.0)
        cond = t.div(t.sum(axis=1), axis=0)  # P(código | estrato), todos los meses
        e7 = (cond.mul(mezcla7.reindex(cond.index), axis=0)).sum()
        eo = (cond.mul(mezclao.reindex(cond.index), axis=0)).sum()
        p7 = bv[es_jul].groupby(v)["FEX_C18"].sum() / bv[es_jul]["FEX_C18"].sum()
        po = bv[~es_jul].groupby(v)["FEX_C18"].sum() / bv[~es_jul]["FEX_C18"].sum()
        for c in cond.columns:
            filas.append(dict(variable=v, codigo=str(c), esperado_por_mezcla_pp=100 * float(e7[c] - eo[c]),
                              observado_pp=100 * float(p7.get(c, 0.0) - po.get(c, 0.0))))
    comp = pd.DataFrame(filas)
    comp["abs_esperado"] = comp["esperado_por_mezcla_pp"].abs()
    comp = comp.sort_values("abs_esperado", ascending=False).drop(columns="abs_esperado")
    comp.to_csv(OUT / "julio_mezcla_esperada_vs_observada.csv", index=False, encoding="utf-8")

    # 4) contraste con ocupados (Bogotá)
    oc = carga.cargar_geih("ocupados")
    oc["mes"] = oc["MES"].astype(int)
    cand_oc = [c for c in oc.columns if c not in EXCLUIR and c != "mes" and oc[c].nunique() <= 20]
    fo = escaneo(oc, cand_oc)
    fo.to_csv(OUT / "ocupados_bogota_escaneo.csv", index=False, encoding="utf-8")
    res.append(resumen_escaneo(fo, "ocupados · Bogotá (persona)"))
    resumen = pd.DataFrame(res)
    resumen.to_csv(OUT / "escaneo_resumen.csv", index=False, encoding="utf-8")

    # informe
    def sub(dom, cats=None):
        x = serie[serie["dominio"] == dom].pivot(index="mes", columns="categoria", values="pct")
        n = serie[serie["dominio"] == dom].groupby("mes")["n_hogares_mes"].first()
        x["n"] = n
        x = x.reset_index()
        x["mes"] = x["mes"].astype(int).astype(str)
        return x

    md = ["# Julio 2025 en GEIH: estrato de datos_hogar (P4030S1A1)\n",
          "> Generado por `tools/investigar_julio.py`. % ponderados con `FEX_C18` dentro de cada mes (no se divide por 12: es la composición del mes). "
          "`z empírico` = (valor de julio − media de los otros 11 meses) / desviación estándar entre esos 11 meses; usa la variación mes a mes real, "
          "que ya incluye el efecto de diseño (el binomial simple lo subestima). Con 12 puntos por serie, |z| ≈ 2-3 aparece por azar en algún mes "
          "de vez en cuando; lo relevante es si julio es *el* mes extremo y si se repite entre dominios y variables.\n",
          "## 1. Serie mensual de estrato (todos los hogares; columnas = código; `vacío` = sin dato)\n"]
    for nom in dominios:
        md += [f"### {nom}\n", md_tabla(sub(nom), {"n": 0})]
    md += ["## 2. Tasa de «sin dato / no estrato» (códigos 0, 9 y vacío) por mes\n",
           md_tabla(sin_dato.pivot(index="mes", columns="dominio", values="pct_sin_dato_o_no_estrato").reset_index().astype({"mes": int}).astype({"mes": str})),
           "\n## 3. Estrato agrupado: ¿julio es un mes extremo? (z empírico)\n", md_tabla(z_est, {"rango_abs_julio": 0}),
           "\n## 4. ¿Se mueven otras variables de `datos_hogar` en julio?\n",
           f"Se escanean {len(cand)} variables (≤ 20 categorías, media ≥ {MIN_PCT} %) por dominio. Si julio fuera un mes anómalo en general, sería el mes más extremo "
           "con frecuencia mayor que los demás. Conteo de (variable, código) por mes más extremo:\n\n",
           md_tabla(resumen, {c: 0 for c in resumen.columns if c not in ("escaneo",)}),
           "\n### 4b. ¿Es compatible el cambio de estrato de julio con un cambio de MEZCLA de la muestra? (Bogotá)\n",
           "Para cada variable se calcula cuánto debería moverse en julio SI solo cambiara la mezcla de estrato (usando P(código | estrato) de todos los meses) "
           "y se compara con lo observado (julio − otros meses). Mayores |esperado|:\n\n",
           md_tabla(comp.head(12), {"esperado_por_mezcla_pp": 2, "observado_pp": 2}),
           "\n## 5. Contraste: variables de `ocupados` (persona), Bogotá\n", md_tabla(fo[fo["mes_mas_extremo"] == MES_FOCO].sort_values("z_abs_max", ascending=False).head(8)) if (fo["mes_mas_extremo"] == MES_FOCO).any() else "Julio no es el mes más extremo de ninguna variable-código de ocupados.\n"]
    md.append(CONCLUSION)
    (OUT / "julio_estrato.md").write_text("\n".join(md), encoding="utf-8")
    print("OK: outputs/julio/")
    print(resumen.to_string(index=False))
    print(z_est.round(2).to_string(index=False))
    print(comp.head(10).round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
