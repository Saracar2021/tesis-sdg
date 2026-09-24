"""WP5 — Análisis de H-P1, H-P2 y H-P3 sobre las salidas crudas del pipeline de referencia.

Lee outputs/pancholi/crudo/ (producido por tools/pancholi_ejecutar.py) y escribe en outputs/pancholi/:
  hp1_elasticidad.csv, hp1_monto_por_nivel.csv, hp1_participacion_por_nivel.csv, hp1_pendiente_alimentos.csv, hp1_disenoC_etapa1.csv,
  hp2_participacion_nivel1.csv, hp2_licencias_informe.csv, hp3_registros_extracto.csv, resumen_hipotesis.json
Los veredictos se calculan con las reglas de docs/prerregistro_wp5.md. Ninguna cifra se escribe a mano.
Uso: python tools/analisis_pancholi.py [--enph ruta.csv]   (referente colombiano opcional, ver comparar_enph)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CRUDO = RAIZ / "outputs" / "pancholi" / "crudo"
SALIDA = RAIZ / "outputs" / "pancholi"
MAPEO = RAIZ / "docs" / "taxonomia" / "mapeo_pancholi_taxonomia_v1.csv"
TAXO = RAIZ / "docs" / "taxonomia" / "taxonomia_v1_extracto.json"
DATOS = RAIZ / "external" / "pancholi" / "src" / "Data_Synthesizer" / "data"
Z = 1.959963984540054
B_BOOT = 10_000
RNG_BOOT = 20260923
EXTRACTO = ["retiro_efectivo", "transferencias_p2p", "movimiento_propio", "ingreso"]
LICENCIAS_INFORME = ["Athletic Exhibition", "Special Events", "Inn And Motel", "Skating Rink"]


# ---------------------------------------------------------------- utilidades
def wilson(x: int, n: int, z: float = Z) -> tuple[float, float, float]:
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def boot_semillas(valores: np.ndarray) -> dict:
    """Media entre semillas con IC percentil 95 % remuestreando semillas con reemplazo."""
    v = np.asarray(valores, float)
    rng = np.random.default_rng(RNG_BOOT)
    medias = rng.choice(v, size=(B_BOOT, len(v)), replace=True).mean(axis=1)
    return {"media": v.mean(), "ic95_inf": np.percentile(medias, 2.5), "ic95_sup": np.percentile(medias, 97.5),
            "min": v.min(), "max": v.max(), "n_semillas": len(v)}


def pendiente(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.polyfit(np.asarray(x, float), np.asarray(y, float), 1)[0])


def cargar_mapeo() -> dict[str, str]:
    m = pd.read_csv(MAPEO)
    return dict(zip(m.etiqueta_pancholi, m.nivel_1_v1))


def cargar_mapeo_n2() -> dict[str, str]:
    m = pd.read_csv(MAPEO).fillna({"nivel_2_v1": ""})
    return dict(zip(m.etiqueta_pancholi, m.nivel_2_v1))


def leer(nombre: str) -> pd.DataFrame:
    return pd.read_csv(CRUDO / f"{nombre}.csv.gz")


def semillas(diseno: str) -> list[int]:
    return sorted(int(re.search(r"_s(\d+)", p.name).group(1)) for p in CRUDO.glob(f"{diseno}_s*.hecho.json"))


def niveles() -> np.ndarray:
    """Misma regla que tools/pancholi_ejecutar.py; si existe el manifiesto, se exige que coincidan."""
    inc = pd.read_csv(DATOS / "synthetic_customer_gan.csv", usecols=["income"])["income"]
    lv = np.geomspace(inc.min(), inc.max(), 12)
    man = SALIDA / "manifest.json"
    if man.exists():
        assert np.allclose(lv, json.loads(man.read_text())["parametros"]["niveles_ingreso_usd_anual"])
    return lv


def nivel_de(cid: pd.Series) -> pd.Series:
    return cid.astype(str).str.extract(r"N(\d{2})C")[0].astype(float)


# ---------------------------------------------------------------- preparación por conjunto
def preparar(df: pd.DataFrame, ingreso_por_cliente: pd.Series | None, lv: np.ndarray | None) -> pd.DataFrame:
    mapa = cargar_mapeo()
    d = df.copy()
    if lv is not None:
        d["nivel"] = nivel_de(d.customer_id)
        d = d.dropna(subset=["nivel"])
        d["nivel"] = d.nivel.astype(int)
        d["income"] = lv[d.nivel.values]
    else:
        d["income"] = d.customer_id.map(ingreso_por_cliente)
        d = d.dropna(subset=["income"])
    d["n1"] = d.category.map(mapa)
    d["n1_merchant"] = d.mapped_category.map(mapa)
    d["amount"] = d.transaction_amount
    return d


def conjuntos() -> dict[str, list[tuple[int, pd.DataFrame]]]:
    """{nombre_conjunto: [(semilla, df preparado), ...]}"""
    lv = niveles()
    out: dict[str, list] = {"A_etapa2": [], "A_etapa3": [], "B_etapa2": [], "B_etapa3": [], "C_etapa3": []}
    for s in semillas("A"):
        out["A_etapa2"].append((s, preparar(leer(f"A_s{s}_etapa2_evaluacion"), None, lv)))
        out["A_etapa3"].append((s, preparar(leer(f"A_s{s}_etapa3_ctgan"), None, lv)))
    ing_b = pd.read_csv(DATOS / "synthetic_customers_deepseek.csv").set_index("customer_id")["income"]
    for s in semillas("B"):
        out["B_etapa2"].append((s, preparar(leer(f"B_s{s}_etapa2"), ing_b, None)))
        out["B_etapa3"].append((s, preparar(leer(f"B_s{s}_etapa3_ctgan"), ing_b, None)))
    if (CRUDO / "C_s42.hecho.json").exists():
        ing_c = leer("C_s42_etapa1_clientes155").set_index("customer_id")["income"]
        out["C_etapa3"].append((42, preparar(leer("C_s42_etapa3_ctgan"), ing_c, None)))
    return {k: v for k, v in out.items() if v}


# ---------------------------------------------------------------- H-P1
def grupos_ingreso(d: pd.DataFrame) -> pd.Series:
    """Diseño A: nivel de la rejilla. B y C: quintil del ingreso de los clientes (cortes sobre clientes únicos)."""
    if "nivel" in d:
        return d.nivel
    cli = d.drop_duplicates("customer_id").set_index("customer_id")["income"]
    q = pd.qcut(cli.rank(method="first"), 5, labels=False)
    return d.customer_id.map(q)


def elasticidad(d: pd.DataFrame) -> float:
    """β de log(monto medio) sobre log(ingreso). A: por nivel; B/C: por cliente."""
    clave = "nivel" if "nivel" in d else "customer_id"
    g = d.groupby(clave).agg(m=("amount", "mean"), inc=("income", "first"))
    g = g[g.m > 0]
    return pendiente(np.log(g.inc), np.log(g.m))


def pend_alimentos(d: pd.DataFrame) -> float:
    """Pendiente (pp por unidad de log ingreso) de la participación de alimentos_mercado en el monto."""
    d = d.assign(g=grupos_ingreso(d))
    tot = d.groupby("g").amount.sum()
    ali = d[d.n1 == "alimentos_mercado"].groupby("g").amount.sum().reindex(tot.index, fill_value=0)
    inc = d.groupby("g").income.median()
    return pendiente(np.log(inc), 100 * ali / tot)


def hp1(cj: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    filas_e, filas_a, filas_p = [], [], []
    for nombre, lista in cj.items():
        be = [elasticidad(d) for _, d in lista]
        ba = [pend_alimentos(d) for _, d in lista]
        filas_e.append({"conjunto": nombre, "metrica": "elasticidad_monto_ingreso", **boot_semillas(be)})
        filas_a.append({"conjunto": nombre, "metrica": "pendiente_part_alimentos_pp_por_log_ingreso", **boot_semillas(ba)})
        # participación por grupo de ingreso y categoría (conteo y monto), agregada sobre semillas
        todo = pd.concat([d.assign(g=grupos_ingreso(d), semilla=s) for s, d in lista])
        for (g, n1), sub in todo.groupby(["g", "n1"]):
            base = todo[todo.g == g]
            p, lo, hi = wilson(len(sub), len(base))
            filas_p.append({"conjunto": nombre, "grupo_ingreso": int(g), "ingreso_mediano": base.income.median(),
                            "nivel_1": n1, "n": len(sub), "n_grupo": len(base), "part_conteo": p, "wilson_inf": lo,
                            "wilson_sup": hi, "part_monto": sub.amount.sum() / base.amount.sum(),
                            "monto_medio": sub.amount.mean()})
    return pd.DataFrame(filas_e), pd.DataFrame(filas_a), pd.DataFrame(filas_p)


def monto_por_grupo(cj: dict) -> pd.DataFrame:
    """Monto medio por transacción en cada grupo de ingreso: media entre semillas e IC bootstrap entre semillas."""
    filas = []
    for nombre, lista in cj.items():
        por_sem = pd.concat([d.assign(g=grupos_ingreso(d)).groupby("g").agg(m=("amount", "mean"), inc=("income", "median"))
                             .assign(semilla=s) for s, d in lista]).reset_index()
        for g, sub in por_sem.groupby("g"):
            filas.append({"conjunto": nombre, "grupo_ingreso": int(g), "ingreso_mediano": sub.inc.median(),
                          **{f"monto_{k}": v for k, v in boot_semillas(sub.m.values).items()}})
    return pd.DataFrame(filas)


def disenoC_etapa1() -> pd.DataFrame:
    if not (CRUDO / "C_s42.hecho.json").exists():
        return pd.DataFrame()
    q = [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    a = leer("C_s42_etapa1_hogares").income.quantile(q)
    b = pd.read_csv(DATOS / "synthetic_customer_gan.csv").income.quantile(q)
    return pd.DataFrame({"cuantil": q, "ingreso_etapa1_reentrenada": a.values, "ingreso_etapa1_archivo_repo": b.values})


# ---------------------------------------------------------------- H-P2
def hp2(cj: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    n2 = cargar_mapeo_n2()
    taxo = list(json.loads(TAXO.read_text())["categorias_nivel_1"])
    filas = []
    for nombre, lista in cj.items():
        todo = pd.concat([d for _, d in lista])
        N = len(todo)
        for col, etiqueta in [("n1", "category"), ("n1_merchant", "mapped_category")]:
            cnt = todo[col].value_counts()
            for c in taxo:
                p, lo, hi = wilson(int(cnt.get(c, 0)), N)
                filas.append({"conjunto": nombre, "columna": etiqueta, "nivel_1": c, "n": int(cnt.get(c, 0)), "N": N,
                              "part_conteo": p, "wilson_inf": lo, "wilson_sup": hi,
                              "part_monto": todo.loc[todo[col] == c, "amount"].sum() / todo.amount.sum()})
        # servicios públicos (nivel 2): ninguna etiqueta de Pancholi mapea a él
        x = int(todo.category.map(n2).eq("servicios_publicos").sum())
        p, lo, hi = wilson(x, N)
        filas.append({"conjunto": nombre, "columna": "category", "nivel_1": "vivienda_servicios.servicios_publicos",
                      "n": x, "N": N, "part_conteo": p, "wilson_inf": lo, "wilson_sup": hi, "part_monto": np.nan})
    part = pd.DataFrame(filas)
    # licencias citadas en el informe, cruzando merchant_name con el archivo de comercios
    com = pd.read_csv(DATOS / "dc_businesses_cleaned.csv")
    lic = com.groupby("Name").Category.agg(lambda s: set(s))
    filas_l = []
    for nombre, lista in cj.items():
        todo = pd.concat([d for _, d in lista])
        cats = todo.merchant_name.map(lic)
        N = len(todo)
        for l in LICENCIAS_INFORME + ["__cualquiera_de_las_4__"]:
            obj = set(LICENCIAS_INFORME) if l.startswith("__") else {l}
            # laxo: el nombre aparece con alguna de las licencias; estricto: todas sus licencias están en el conjunto
            x_l = int(cats.map(lambda c: isinstance(c, set) and bool(c & obj)).sum())
            x_e = int(cats.map(lambda c: isinstance(c, set) and c <= obj).sum())
            p, lo, hi = wilson(x_e, N)
            filas_l.append({"conjunto": nombre, "licencia": l, "n_estricto": x_e, "n_laxo": x_l, "N": N,
                            "part": p, "wilson_inf": lo, "wilson_sup": hi, "part_laxo": x_l / N,
                            "part_nombres_sin_licencia": float(cats.isna().mean())})
    return part, pd.DataFrame(filas_l)


def zip_comercios(cj: dict) -> pd.DataFrame:
    """Diagnóstico: % de registros cuyo comercio está en el ZIP del cliente (20001) frente a la tasa base del archivo."""
    com = pd.read_csv(DATOS / "dc_businesses_cleaned.csv")
    zips = com.groupby("Name").Zipcode.agg(lambda s: set(s.astype(str)))
    base = float((com.Zipcode.astype(str) == "20001").mean())
    filas = []
    for nombre in [k for k in cj if k.startswith("A_etapa2")]:
        todo = pd.concat([d for _, d in cj[nombre]])
        en = todo.merchant_name.map(zips).map(lambda z: isinstance(z, set) and "20001" in z)
        filas.append({"conjunto": nombre, "part_registros_comercio_zip_20001": float(en.mean()),
                      "part_comercios_archivo_zip_20001": base,
                      "part_nombre_generico_DC": float(todo.merchant_name.str.startswith("DC ").mean())})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- H-P3
def hp3(cj: dict) -> pd.DataFrame:
    filas = []
    for nombre, lista in cj.items():
        todo = pd.concat([d for _, d in lista])
        crudo_cols = [c for c in lista[0][1].columns if c not in ("nivel", "income", "n1", "n1_merchant", "amount")]
        pago = [c for c in crudo_cols if re.search(r"pay|payment|method|medio|tarjeta|card|cash", c, re.I)]
        N = len(todo)
        for c in EXTRACTO + ["__cualquier_registro_de_extracto__"]:
            obj = set(EXTRACTO) if c.startswith("__") else {c}
            x = int(todo.n1.isin(obj).sum())
            p, lo, hi = wilson(x, N)
            filas.append({"conjunto": nombre, "tipo_registro": c, "n": x, "N": N, "part": p, "wilson_inf": lo,
                          "wilson_sup": hi, "columnas_salida": "|".join(crudo_cols),
                          "columnas_medio_pago": "|".join(pago) or "(ninguna)"})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- veredictos (reglas del prerregistro)
def veredictos(e: pd.DataFrame, part: pd.DataFrame, r3: pd.DataFrame, enph, hp2_ocio_hospedaje_df: pd.DataFrame) -> dict:
    v: dict = {"H-P1": {}, "H-P2": {}, "H-P3": {}}
    for _, r in e.iterrows():
        evaluable = r.n_semillas >= 2
        v["H-P1"][r.conjunto] = {"elasticidad": r.media, "ic95": [r.ic95_inf, r.ic95_sup] if evaluable else None,
                                 "n_semillas": int(r.n_semillas),
                                 "sensible_al_ingreso": bool(r.ic95_inf > 0 or r.ic95_sup < 0) if evaluable else None}
    v["H-P1"]["veredicto"] = "no concluyente (sin referente colombiano en este entorno)" if enph is None else enph
    principal = "B_etapa3" if "B_etapa3" in set(part.conjunto) else sorted(set(part.conjunto))[-1]
    for nombre in sorted(set(part.conjunto)):
        sub = part[(part.conjunto == nombre) & (part.columna == "category") & ~part.nivel_1.str.contains(r"\.")].set_index("nivel_1")
        ocio = sub.loc["entretenimiento"]
        otras = sub.drop(index="entretenimiento")
        otras = otras[otras.n > 0]
        if ocio.wilson_inf > otras.wilson_sup.max():
            ver = "confirmada"
        elif ocio.wilson_sup < sub.loc["alimentos_mercado"].wilson_inf:
            ver = "refutada"
        else:
            ver = "no concluyente"
        res = {"ocio=entretenimiento": {"part_ocio": ocio.part_conteo, "ic95": [ocio.wilson_inf, ocio.wilson_sup],
                                        "part_alimentos": sub.loc["alimentos_mercado"].part_conteo,
                                        "categoria_mayor_otra": otras.part_conteo.idxmax(),
                                        "part_mayor_otra": otras.part_conteo.max(), "veredicto": ver}}
        oh = hp2_ocio_hospedaje_df[hp2_ocio_hospedaje_df.conjunto == nombre].set_index("grupo")
        o2 = oh.loc["ocio_con_hospedaje"]; resto = oh.drop(index="ocio_con_hospedaje")
        ver2 = ("confirmada" if o2.wilson_inf > resto.wilson_sup.max() else
                "refutada" if o2.wilson_sup < oh.loc["alimentos_mercado"].wilson_inf else "no concluyente")
        res["ocio=entretenimiento+hospedaje (sensibilidad)"] = {"part_ocio": o2.part, "ic95": [o2.wilson_inf, o2.wilson_sup],
                                                                 "veredicto": ver2}
        res["categorias_v1_con_participacion"] = int((sub.n > 0).sum())
        res["categorias_v1_total"] = int(len(sub))
        v["H-P2"][nombre] = res
    v["H-P2"]["conjunto_principal"] = principal
    for nombre in sorted(set(r3.conjunto)):
        t = r3[(r3.conjunto == nombre) & (r3.tipo_registro == "__cualquier_registro_de_extracto__")].iloc[0]
        ok = t.columnas_medio_pago == "(ninguna)" and t.n == 0 and t.wilson_sup < 0.001
        v["H-P3"][nombre] = {"columnas_medio_pago": t.columnas_medio_pago, "registros_extracto": int(t.n), "N": int(t.N),
                             "wilson_sup": t.wilson_sup,
                             "veredicto_etapas_ejecutadas": "confirmada" if ok else "no confirmada"}
    v["H-P3"]["distribucion_payment_type_etapa4"] = "no concluyente: etapa 4 no ejecutable (API de Groq bloqueada)"
    return v


def hp2_ocio_hospedaje(cj: dict) -> pd.DataFrame:
    """Sensibilidad de H-P2(a): ocio = entretenimiento + hospedaje ('housing'), frente a cada otra categoría."""
    filas = []
    mapa = cargar_mapeo()
    for nombre, lista in cj.items():
        todo = pd.concat([d for _, d in lista])
        grupo = np.where(todo.category.isin(["entertainment", "housing"]), "ocio_con_hospedaje", todo.category.map(mapa))
        cnt = pd.Series(grupo).value_counts()
        N = len(todo)
        for g, x in cnt.items():
            p, lo, hi = wilson(int(x), N)
            filas.append({"conjunto": nombre, "grupo": g, "n": int(x), "N": N, "part": p, "wilson_inf": lo, "wilson_sup": hi})
    return pd.DataFrame(filas)


def comparar_enph(ruta: str, a: pd.DataFrame) -> dict:
    """Referente colombiano: CSV con columnas quintil, icgu_mediano, part_alimentos_pct, ic95_inf, ic95_sup de la
    PENDIENTE (una fila 'pendiente'). Lo produce la autora localmente (ENPH Bogotá, FEX_C, nivel hogar).
    Regla del prerregistro: confirmada si los IC de la pendiente no se solapan."""
    ref = pd.read_csv(ruta).set_index("quintil").loc["pendiente"]
    out = {}
    for _, r in a.iterrows():
        solapa = not (r.ic95_sup < ref.ic95_inf or r.ic95_inf > ref.ic95_sup)
        out[r.conjunto] = "refutada" if solapa else "confirmada"
    return out


def main() -> None:
    cj = conjuntos()
    e, a, p = hp1(cj)
    part, lic = hp2(cj)
    oh = hp2_ocio_hospedaje(cj)
    r3 = hp3(cj)
    enph = None
    if "--enph" in sys.argv:
        enph = comparar_enph(sys.argv[sys.argv.index("--enph") + 1], a)
    e.to_csv(SALIDA / "hp1_elasticidad.csv", index=False)
    a.to_csv(SALIDA / "hp1_pendiente_alimentos.csv", index=False)
    p.to_csv(SALIDA / "hp1_participacion_por_nivel.csv", index=False)
    monto_por_grupo(cj).to_csv(SALIDA / "hp1_monto_por_nivel.csv", index=False)
    disenoC_etapa1().to_csv(SALIDA / "hp1_disenoC_etapa1.csv", index=False)
    part.to_csv(SALIDA / "hp2_participacion_nivel1.csv", index=False)
    lic.to_csv(SALIDA / "hp2_licencias_informe.csv", index=False)
    oh.to_csv(SALIDA / "hp2_ocio_con_hospedaje.csv", index=False)
    r3.to_csv(SALIDA / "hp3_registros_extracto.csv", index=False)
    zip_comercios(cj).to_csv(SALIDA / "diag_zip_comercios.csv", index=False)
    v = veredictos(e, part, r3, enph, oh)
    (SALIDA / "resumen_hipotesis.json").write_text(json.dumps(v, indent=1, ensure_ascii=False, default=float))
    print(json.dumps(v, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main()
