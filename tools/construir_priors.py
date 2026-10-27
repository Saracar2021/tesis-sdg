"""Construye los priors bayesianos de WP3 y los escribe en outputs/priors/ (determinista, SEED = 42).

Ejecutar desde la raíz:  .venv\\Scripts\\python.exe tools\\construir_priors.py

Entradas: SOLO microdatos vía sdg.carga (nunca outputs/distribuciones/*.csv: esos son la referencia independiente de los tests).
Salidas (outputs/priors/):
  priors.json                       priors por celda + metadatos (entrada de muestrear_perfiles)
  soporte_celdas.csv                n, n_ef, κ̂ y marca «rala» por familia y celda (PD1)
  celdas_afectadas.csv              por celda: en cuántas familias/subcapítulos pesa más el padre que la celda (PD2)
  celdas_hogares.csv                masa, n, ICGU=0 y n urbano nacional por celda (cortes de Bogotá)
  perfil_kappa.csv                  log-verosimilitud marginal de κ por grupo de familias
  sensibilidad_priors.csv           cuánto cambian los priors con κ̂/2, 2κ̂, κ=30, deff=2 y padre sin Bogotá
  dependencia_ocupacion_quintil.csv ENPH personas: ¿la ocupación depende del quintil dado el estrato? (decisión 4)
  comparacion_geih_enph_ocupacion.csv  nivel de posición y formalidad: GEIH 2025 vs ENPH 2016-17
  cota_sesgo_bancarizacion.csv      cota superior del % de tarjeta entre bancarizados (L16)
  manifest_priors.json
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sdg import carga, priors as P  # noqa: E402
from sdg.encogimiento import chi2_sf, n_efectivo  # noqa: E402

OUT = RAIZ / "outputs" / "priors"
DEFF_CLUSTER = 2.0     # sensibilidad por conglomeración (UPM no disponible, L1): supuesto, no medición
KAPPA_FIJO = 30.0      # equivalente en κ de la marca histórica «n ≈ 30»


# ------------------------------------------------------------------------------------------------
# sensibilidad
# ------------------------------------------------------------------------------------------------
def _marginales(ins: P.Insumos, res: dict) -> dict:
    """Marginal de Bogotá implícita en cada prior (volviendo de las celdas con la masa de quienes respondieron)."""
    out = {}
    fam = ins.familias
    for nombre in [n for n in fam if n in ("nc2r", "formalidad", "tipo_contrato") or n.startswith("p438:")]:
        ult = fam[nombre].niveles[-1]
        w = np.array([ult[c].w for c in ult])
        out[nombre] = (w[:, None] * np.vstack([res["post"][nombre][c] for c in ult])).sum(axis=0) / w.sum()
    pos = np.zeros(len(P.POS_CATS))
    for e in P.ESTRATOS:
        for i, q in enumerate(P.QUINTILES):
            pos += ins.mezcla_geih[e] * ins.m_pers[e][i] * res["posicion"][(e, q)]
    out["posicion"] = pos
    return out


def _celda_final(res: dict) -> dict:
    """Todos los priors al nivel de celda, con el prior final de posición."""
    d = {n: v for n, v in res["post"].items() if n not in ("pos_enph", "pos_geih")}
    d["posicion"] = res["posicion"]
    return d


def _grupo(nombre: str) -> str:
    return "p438" if nombre.startswith("p438:") else nombre


def sensibilidad(ins: P.Insumos, base: dict) -> pd.DataFrame:
    esc = {
        "kappa_mitad": dict(kappas=base["kappas_detalle"], kappa_mult=0.5),
        "kappa_doble": dict(kappas=base["kappas_detalle"], kappa_mult=2.0),
        f"kappa_fijo_{int(KAPPA_FIJO)}": dict(kappas=base["kappas_detalle"], kappa_fijo=KAPPA_FIJO),
        f"deff_{DEFF_CLUSTER:g}_kappa_reestimado": dict(deff=DEFF_CLUSTER),
        "padre_sin_bogota_kappa_reestimado": dict(sin_bogota=True),
    }
    b_cel, b_mar = _celda_final(base), _marginales(ins, base)
    filas = []
    for nombre, kw in esc.items():
        alt = P.construir(ins, **kw)
        a_cel, a_mar = _celda_final(alt), _marginales(ins, alt)
        mejor: dict = {}
        for fam, tabla in b_cel.items():
            g = _grupo(fam)
            for c, v in tabla.items():
                d = 100 * np.abs(a_cel[fam][c] - v)
                j = int(d.argmax())
                m = mejor.setdefault(g, dict(dif_celda_max_pp=-1.0))
                if d[j] > m["dif_celda_max_pp"]:
                    m.update(dif_celda_max_pp=float(d[j]), donde_celda=f"{fam}|{c}|cat={j}")
        for fam, v in b_mar.items():
            d = 100 * np.abs(a_mar[fam] - v)
            j = int(d.argmax())
            m = mejor.setdefault(_grupo(fam), dict(dif_celda_max_pp=-1.0))
            if d[j] > m.get("dif_marginal_max_pp", -1.0):
                m.update(dif_marginal_max_pp=float(d[j]), donde_marginal=f"{fam}|cat={j}")
        for g, m in mejor.items():
            filas.append(dict(escenario=nombre, grupo=g, kappa_base=base["kappa"].get(g, np.nan) if g in base["kappa"] else np.nan,
                              kappa_escenario=alt["kappa"].get(g, np.nan) if g in alt["kappa"] else np.nan, **m))
    return pd.DataFrame(filas)


# ------------------------------------------------------------------------------------------------
# dependencia ocupación × quintil | estrato (decisión 4) — ENPH personas ocupadas de Bogotá
# ------------------------------------------------------------------------------------------------
def _chi2(g: pd.DataFrame, col: str, deff: float) -> dict | None:
    t = g.pivot_table(index="quintil", columns=col, values="FEX", aggfunc="sum", fill_value=0.0, observed=True)
    t = t.loc[t.sum(axis=1) > 0, t.sum(axis=0) > 0]
    if t.shape[0] < 2 or t.shape[1] < 2:
        return None
    neff = n_efectivo(g["FEX"].to_numpy()) / deff

    def valida(m: np.ndarray) -> bool:
        pr_ = m / m.sum()
        esp_ = neff * pr_.sum(axis=1, keepdims=True) * pr_.sum(axis=0, keepdims=True)  # esperados bajo independencia (unidades de n efectivo)
        return bool((esp_ >= 1).all() and (esp_ >= 5).mean() >= 0.8)  # regla clásica de validez asintótica de χ²

    tv = 0.5 * (t.div(t.sum(axis=1), axis=0) - t.sum(axis=0) / t.to_numpy().sum()).abs().sum(axis=1)  # sobre la tabla original
    a = t.to_numpy()
    fusionadas = 0
    while not valida(a) and a.shape[1] > 2:  # se fusionan las dos categorías más pequeñas hasta que el χ² sea válido
        i, j = np.argsort(a.sum(axis=0))[:2]
        a = np.column_stack([np.delete(a, [i, j], axis=1), a[:, i] + a[:, j]])
        fusionadas += 1
    pr = a / a.sum()
    r, c = pr.sum(axis=1, keepdims=True), pr.sum(axis=0, keepdims=True)
    x2 = neff * float(((pr - r * c) ** 2 / (r * c)).sum())
    gl = (a.shape[0] - 1) * (a.shape[1] - 1)
    return dict(n=len(g), n_ef=neff, gl=gl, X2=x2, p=chi2_sf(x2, gl), V=math.sqrt(x2 / neff / (min(a.shape) - 1)),
                tv_max_pp=100 * float(tv.max()), tv_Q1_pp=100 * float(tv.get(1.0, np.nan)), categorias_fusionadas=fusionadas, chi2_valido=valida(a))


def dependencia(ins: P.Insumos) -> pd.DataFrame:
    pe = ins.pers
    d = pe[pe["bogota"] & pe["pos_g"].notna() & pe["estrato_g"].notna() & pe["quintil"].notna()].copy()
    filas = []
    for deff in (1.0, DEFF_CLUSTER):
        for var in ("pos_g", "P6440", "P6920", "P6990"):
            dv = d if var == "pos_g" else d[d[var].isin(P.FORM_VALIDOS[var])]
            for e in P.ESTRATOS:
                r = _chi2(dv[dv["estrato_g"] == e], var, deff)
                if r:
                    if not r["chi2_valido"]:  # p sin valor inferencial: se deja la magnitud (V, TV) pero no el p-valor
                        r["p"] = np.nan
                    filas.append(dict(contraste=f"{'posicion' if var == 'pos_g' else var} ⟂ quintil | estrato", estrato_agrupado=e, deff=deff, **r))
        for var in ("P6440", "P6920", "P6990"):  # residual: ¿queda dependencia del quintil una vez dados estrato y posición?
            dv = d[d[var].isin(P.FORM_VALIDOS[var])]
            x2 = gl = ne = 0.0
            usadas = 0
            for (e, p), g in dv.groupby(["estrato_g", "pos_g"], observed=True):
                r = _chi2(g, var, deff)
                if r and r["chi2_valido"]:
                    x2, gl, ne, usadas = x2 + r["X2"], gl + r["gl"], ne + r["n_ef"], usadas + 1
            filas.append(dict(contraste=f"{var} ⟂ quintil | estrato, posición (suma de {usadas} tablas con χ² válido)", estrato_agrupado="todos", deff=deff,
                              n=np.nan, n_ef=ne, gl=gl, X2=x2, p=chi2_sf(x2, int(gl)) if gl else np.nan, V=np.nan, tv_max_pp=np.nan, tv_Q1_pp=np.nan,
                              chi2_valido=True))
    return pd.DataFrame(filas)


def comparacion_geih_enph(ins: P.Insumos) -> pd.DataFrame:
    g = ins.geih_oc[ins.geih_oc["estrato_g"].notna()]
    pe = ins.pers
    e_ = pe[pe["bogota"] & pe["pos_g"].notna() & pe["estrato_g"].notna()]
    filas = []
    for var, cats, col_g, col_e in [("posicion", P.POS_CATS, "pos_g", "pos_g"), *[(v, P.FORM_VALIDOS[v], v, v) for v in P.FORM_VARS]]:
        for e in P.ESTRATOS:
            a = g[(g["estrato_g"] == e) & g[col_g].isin(cats)]
            b = e_[(e_["estrato_g"] == e) & e_[col_e].isin(cats)]
            pa = a.groupby(col_g)["FEX"].sum().reindex(cats, fill_value=0) / a["FEX"].sum()
            pb = b.groupby(col_e)["FEX"].sum().reindex(cats, fill_value=0) / b["FEX"].sum()
            for c in cats:
                filas.append(dict(variable=var, estrato_agrupado=e, categoria=c, pct_geih_2025=100 * pa[c], pct_enph_2017=100 * pb[c],
                                  dif_pp_geih_menos_enph=100 * (pa[c] - pb[c]), n_geih=len(a), n_enph=len(b)))
    return pd.DataFrame(filas)


def cota_bancarizacion(ins: P.Insumos) -> pd.DataFrame:
    """L16: ENPH no tiene P5222. Si TODOS los hogares con tarjeta (débito o crédito) fueran bancarizados, el % de tarjeta entre
    bancarizados sería P / P(bancarizado|estrato) como máximo; si ninguno lo fuera, quedaría en P. Es una cota, no una estimación."""
    h = ins.hog[ins.hog["bogota"] & ins.hog["estrato_g"].notna() & ins.hog["NC2R_CC_P6"].isin(P.NC2R_CATS)]
    filas = []
    for e in P.ESTRATOS:
        g = h[h["estrato_g"] == e]
        pt = float(g.loc[g["NC2R_CC_P6"].isin(["1", "2"]), "FEX"].sum() / g["FEX"].sum())
        pb = ins.p_banc[e]
        filas.append(dict(estrato_agrupado=e, n=len(g), p_tarjeta_todos_pct=100 * pt, p_bancarizado=pb,
                          cota_inferior_pct=100 * pt, cota_superior_pct=100 * min(1.0, pt / pb), aumento_relativo_max_pct=100 * (min(1.0, pt / pb) / pt - 1)))
    return pd.DataFrame(filas)


# ------------------------------------------------------------------------------------------------
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ins = P.cargar_insumos()
    kap = P.estimar_kappas(ins)
    res = P.construir(ins, kappas=kap)
    celdas = P.tabla_celdas(ins)
    pj = P.construir_priors_json(ins, res, celdas)
    txt = P.serializar(pj)
    (OUT / "priors.json").write_text(txt, encoding="utf-8")

    # determinismo: segunda construcción desde los mismos insumos y muestreo con la misma semilla
    pj2 = P.construir_priors_json(ins, P.construir(ins, kappas=P.estimar_kappas(ins)), P.tabla_celdas(ins))
    assert P.serializar(pj2) == txt, "priors.json no es determinista"
    a, b = P.muestrear_perfiles(pj, 1000), P.muestrear_perfiles(pj, 1000)
    assert a.equals(b), "muestrear_perfiles no es determinista"
    assert P.muestrear_perfiles(pj, 100).equals(a.iloc[:100].reset_index(drop=True)), "los primeros n perfiles deben ser estables al crecer n"

    sop = P.tabla_soporte(ins, res["kappa"])
    sop.to_csv(OUT / "soporte_celdas.csv", index=False, encoding="utf-8")
    celdas.to_csv(OUT / "celdas_hogares.csv", index=False, encoding="utf-8")

    # celdas afectadas: por celda ENPH, cuántas familias/subcapítulos tienen n_ef < κ̂
    enph = sop[sop["quintil"] != ""].copy()
    filas = []
    for (e, q), g in enph.groupby(["estrato_agrupado", "quintil"]):
        p4 = g[g["familia"] == "p438"]
        f = dict(estrato_agrupado=e, quintil=q)
        for fam in ("nc2r", "pos_enph"):
            r = g[g["familia"] == fam].iloc[0]
            f[f"{fam}_n_ef"], f[f"{fam}_rala"] = r["n_ef"], bool(r["rala"])
        f.update(p438_subcapitulos_ralos=int(p4["rala"].sum()), p438_subcapitulos_total=len(p4), p438_pct_ralos=100 * float(p4["rala"].mean()),
                 p438_peso_padre_mediano=float(p4["peso_padre"].median()), p438_ralos=" ".join(sorted(p4.loc[p4["rala"], "variable"])))
        filas.append(f)
    pd.DataFrame(filas).to_csv(OUT / "celdas_afectadas.csv", index=False, encoding="utf-8")

    perfil = pd.DataFrame([dict(grupo=g, kappa=k, loglik=ll, es_optimo=(k == v["kappa"]), optimo_en_frontera=v["en_frontera"])
                           for g, v in kap.items() for k, ll in v["perfil"]])
    perfil.to_csv(OUT / "perfil_kappa.csv", index=False, encoding="utf-8")

    sens = sensibilidad(ins, res)
    sens.to_csv(OUT / "sensibilidad_priors.csv", index=False, encoding="utf-8")
    dep = dependencia(ins)
    dep.to_csv(OUT / "dependencia_ocupacion_quintil.csv", index=False, encoding="utf-8")
    comparacion_geih_enph(ins).to_csv(OUT / "comparacion_geih_enph_ocupacion.csv", index=False, encoding="utf-8")
    cota = cota_bancarizacion(ins)
    cota.to_csv(OUT / "cota_sesgo_bancarizacion.csv", index=False, encoding="utf-8")

    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip() or "no disponible"
    except OSError:
        commit = "no disponible"
    h = ins.hog
    man = {
        "script": "tools/construir_priors.py", "commit_base": commit, "pandas": pd.__version__, "numpy": np.__version__, "python": sys.version.split()[0],
        "semilla": P.SEED, "sha256_priors_json": P.sha256_texto(txt),
        "kappa": {g: {"kappa": v["kappa"], "en_frontera": v["en_frontera"]} for g, v in kap.items()},
        "conteos": {"hogares_enph_pais": len(h), "hogares_urbanos_nacional": int(h["urbano"].sum()), "hogares_bogota": int(h["bogota"].sum()),
                    "ocupados_enph_bogota": int((ins.pers["bogota"] & ins.pers["pos_g"].notna()).sum()), "ocupados_geih_bogota": len(ins.geih_oc),
                    "ocupados_geih_sin_estrato": int(ins.geih_oc["estrato_g"].isna().sum()), "hogares_geih_12_meses": ins.geih_hogares_n,
                    "hogares_bogota_icgu_cero": int((h["bogota"] & (h["icgu"] == 0)).sum()), "min_hogares_urbano_nacional_por_celda": int(celdas["n_urbano_nacional"].min())},
        "cortes_icgu_bogota": ins.cortes_icgu,
        "uniones": [{k: u[k] for k in ("nombre", "llave", "filas_izq", "pct_enlazado", "umbral")} for u in carga.UNIONES],
    }
    (OUT / "manifest_priors.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print("\n== κ̂ por grupo ==")
    for g, v in kap.items():
        print(f"  {g:14s} κ̂ = {v['kappa']:8.2f}  {'(EN FRONTERA)' if v['en_frontera'] else ''}")
    print(f"== priors.json sha256 {man['sha256_priors_json'][:16]}…  | commit {commit}")
    print(sens.groupby("escenario")[["dif_celda_max_pp", "dif_marginal_max_pp"]].max().round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
