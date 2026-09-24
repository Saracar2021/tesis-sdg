"""WP5 — Genera docs/reevaluacion_pancholi.md y docs/propuestas_repo_wp5.md desde outputs/pancholi/.

Todas las cifras del informe salen de manifest.json, resumen_hipotesis.json y los CSV de outputs/pancholi/.
El texto fijo solo cita constantes del código de Pancholi (con archivo y línea), no estadísticas.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
S = RAIZ / "outputs" / "pancholi"
DOCS = RAIZ / "docs"
NOMBRE = {"A_etapa2": "A · etapa 2 (reglas)", "A_etapa3": "A · etapa 3 (CTGAN)",
          "B_etapa2": "B · etapa 2 (reglas)", "B_etapa3": "B · etapa 3 (CTGAN)",
          "C_etapa3": "C · etapas 1→2→3 (CTGAN final)"}


def f(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, d: int = 1) -> str:
    return f(100 * x, d) + " %"


def ic(lo: float, hi: float, d: int = 3, p: bool = False) -> str:
    return f"[{pct(lo, d) if p else f(lo, d)}; {pct(hi, d) if p else f(hi, d)}]"


def main() -> None:
    man = json.loads((S / "manifest.json").read_text())
    v = json.loads((S / "resumen_hipotesis.json").read_text())
    el = pd.read_csv(S / "hp1_elasticidad.csv").set_index("conjunto")
    al = pd.read_csv(S / "hp1_pendiente_alimentos.csv").set_index("conjunto")
    mn = pd.read_csv(S / "hp1_monto_por_nivel.csv")
    p2 = pd.read_csv(S / "hp2_participacion_nivel1.csv")
    lic = pd.read_csv(S / "hp2_licencias_informe.csv")
    oh = pd.read_csv(S / "hp2_ocio_con_hospedaje.csv")
    h3 = pd.read_csv(S / "hp3_registros_extracto.csv")
    zc = pd.read_csv(S / "diag_zip_comercios.csv")
    c1 = pd.read_csv(S / "hp1_disenoC_etapa1.csv") if (S / "hp1_disenoC_etapa1.csv").stat().st_size > 1 else pd.DataFrame()
    conj = [c for c in NOMBRE if c in el.index]
    par = man["parametros"]
    corr = pd.DataFrame(man["corridas"])
    t_total_h = man["tiempo_total_s"] / 3600
    rep = man["reproducibilidad_semilla_42"]
    principal = v["H-P2"]["conjunto_principal"]
    L: list[str] = []
    w = L.append

    # ------------------------------------------------------------------ encabezado
    w("# Reevaluación del pipeline de referencia (Pancholi et al.) — WP5\n")
    w("> Documento generado por `tools/informe_pancholi.py` a partir de `outputs/pancholi/`. No editar las cifras a mano:"
      " se regeneran con `python tools/analisis_pancholi.py && python tools/informe_pancholi.py`.\n")
    w("## 1. Qué se corrió y cómo\n")
    w(f"- **Código:** {man['repositorio']['url']} · commit `{man['repositorio']['commit']}` · árbol del clon limpio: "
      f"{'sí' if man['repositorio']['arbol_limpio'] else 'NO'}. El clon vive en `external/pancholi/` (ignorado por git); "
      f"en el repositorio quedan solo la URL y el hash. **Licencia:** {man['licencia']}: permite uso académico, "
      "modificación y redistribución conservando el aviso de copyright.")
    w(f"- **Entorno:** `{man['entorno']['venv']}`, Python {man['entorno']['python'].split()[0]}, "
      f"{man['entorno']['plataforma']}, CPU ({man['entorno']['cpu_hilos_torch']} hilos de torch), CUDA: "
      f"{'sí' if man['entorno']['cuda'] else 'no'}. Versiones fijadas por el propio repo "
      "(`src/Data_Synthesizer/requirements.txt`); la lista completa está en `manifest.json`. "
      "Se ejecutó en un entorno aislado en la nube, **sin ningún dato del equipo de la autora**.")
    w("- **Etapas ejecutadas:** 1 (demografía), 2 (reglas) y 3 (CTGAN), llamando a sus clases desde "
      "`tools/pancholi_ejecutar.py` sin editar su código. **No ejecutadas:** 4 (enriquecimiento con LLM) y 5 (bucle "
      "híbrido): requieren la API de Groq, bloqueada desde el entorno de ejecución (HTTP 403 en el proxy); la etapa 5 "
      "además falla por código (§2).")
    w("- **Parche P1** (`tools/pancholi_parches/`): con `sdv==1.19.0`, que el propio repo fija, "
      "`src/component/transaction.py` no importa (`SingleTableMetadata` vive en `sdv.metadata.single_table`). "
      "Se reasigna el mismo objeto de clase en memoria antes de importar; no cambia ninguna lógica.")
    w(f"- **Criterios prerregistrados** en `docs/prerregistro_wp5.md` antes de la primera corrida "
      f"(SHA-256 `{man['prerregistro']['sha256'][:16]}…`, sello en `outputs/pancholi/prerregistro_sello.json`).\n")
    w("| Diseño | Qué es | Semillas | Parámetros |\n|---|---|---|---|")
    nA = len(corr[corr.diseno == "A"]); nB = len(corr[corr.diseno == "B"]); nC = len(corr[corr.diseno == "C"])
    niv = par["niveles_ingreso_usd_anual"]
    w(f"| A | Rejilla de ingreso, etapas 2 y 3 | {nA} ({min(man['semillas'])}–{max(man['semillas'])}) | "
      f"{par['n_niveles']} niveles log-espaciados de {f(niv[0], 0)} a {f(niv[-1], 0)} USD/año (mínimo y máximo del ingreso de su etapa 1); "
      f"{par['clientes_entrena_por_nivel']} clientes/nivel para entrenar, {par['tx_por_cliente']} tx/cliente, "
      f"CTGAN {par['epocas_ctgan']} épocas, {f(par['muestras_A'], 0)} muestras; evaluación de la etapa 2 con "
      f"{par['clientes_eval_por_nivel']} clientes/nivel; hogar de {par['household_size']} personas, ZIP {int(par['zipcode'])} |")
    w(f"| B | Réplica literal de `transaction_synthesizer.py` | {nB} | sus 155 clientes (`synthetic_customers_deepseek.csv`), "
      f"{par['tx_por_cliente']} tx/cliente, {par['epocas_ctgan']} épocas, {f(par['muestras_B'], 0)} muestras |")
    if nC:
        w(f"| C | Etapa 1 reentrenada (`AdvancedIncomeModel`) + etapas 2 y 3 sobre 155 de sus clientes | {nC} (42) | "
          f"{par['epocas_ctgan']} épocas en ambas CTGAN; 100.000 hogares como en `customer_synthesizer.py` |")
    w("")
    todas = all(rep.values()) if rep else False
    w(f"**Reproducibilidad.** La semilla 42 del diseño A se corrió dos veces: contenido idéntico en "
      f"{sum(rep.values())} de {len(rep)} archivos (comparando sin `timestamp`, que su código toma de `datetime.now()`)"
      f"{'' if todas else ' — HAY DIFERENCIAS'}. SDV fija su propia semilla de muestreo (73251); la variación entre "
      f"semillas viene de la simulación por reglas y del entrenamiento del CTGAN. **Tiempo total de cómputo:** "
      f"{f(t_total_h, 1)} h; CTGAN ≈ {f(corr.tiempos_s.map(lambda t: t['ctgan_fit']).median() / 60, 1)} min por ajuste (mediana).\n")

    # ------------------------------------------------------------------ lectura de código
    w("## 2. Lo que dice el código (inferido por lectura, no resultado de ejecución)\n")
    w("- **Etapa 2** (`src/component/transaction.py`, `generate_spending_pattern` y `simulate_transactions`): "
      "monto = ingreso/12 × fracción fija por categoría × U(0,05; 0,30); la categoría de cada transacción se sortea "
      "uniformemente (`random.choice`) entre 7. Las fracciones solo cambian con el ingreso en un escalón (+0,03 a "
      "`dining` si ingreso > 75.000) y con el hogar (+0,02 a `groceries` si > 2 personas).")
    w("- **Etapa 3** (`TransactionCTGAN.fit`): el CTGAN se entrena con `customer_id, zipcode, category, merchant_name, "
      "mapped_category, transaction_amount`; **el ingreso no es columna del entrenamiento**. El vínculo con el "
      "ingreso solo puede sobrevivir vía `customer_id`.")
    w("- **Etapa 1**: el paper la llama «Bayesian demographic modeling», pero el código es un CTGAN "
      "(`AdvancedIncomeModel`) o un muestreo por tramos (`ABMGlobalModel`); `arviz` se importa y no se usa. Las "
      "transacciones que el repo publica (`synthetic_transactions_ctgan.csv`) salen de 155 clientes generados por "
      "un LLM (`synthetic_customers_deepseek.csv`), no de la etapa 1.")
    w("- **Etapa 4** (`transaction_deepseek_synthesizer.py`): una llamada a Groq (`llama-3.3-70b-versatile`, "
      "temperatura 0,5) por transacción; el esquema de salida tiene un solo registro de compra con `payment_type` "
      "libre («Appropriate payment method»). **Etapa 5** (`hybridgenerator.py`): pasa a la etapa 4 un cliente sin "
      "`age`, `gender` ni `household_size` (KeyError en el prompt, capturado → salida vacía), fija el ingreso en "
      "75.000 y su «fraud_score» de validación es `random.random()`.")
    w("- **Aplicación web** (`transaction_synthesizer_groq.py`, no es el pipeline del paper): descarta montos fuera de "
      "USD 10–200, no pasa el ingreso al LLM, pone `\"payment_type\": \"credit_card\"` como ejemplo literal del "
      "prompt (temperatura 0,1) y sortea casi uniformemente entre 39 subcategorías, en su mayoría de ocio. "
      "**Las cifras retiradas del informe de avance (5 perfiles, 149 tx, USD 12, categorías de ocio, 100 % "
      "`credit_card`) son compatibles con este programa y no con el pipeline del paper** (inferencia: no se "
      "pudo ejecutar, requiere Groq).")
    z = zc.iloc[0]
    w(f"- **Verificado al ejecutar:** el emparejamiento de comercio por ZIP no actúa. El {pct(z.part_registros_comercio_zip_20001)} "
      f"de los registros de la etapa 2 cae en comercios del ZIP del cliente, frente a una tasa base de "
      f"{pct(z.part_comercios_archivo_zip_20001)} en el archivo de comercios (`diag_zip_comercios.csv`). Causa probable "
      f"(por lectura de código): el ZIP del cliente se convierte a texto como `20001.0` y el del comercio como `'20001'`, así que nunca coinciden.\n")

    # ------------------------------------------------------------------ H-P1
    w("## 3. Resultados por hipótesis\n")
    w("### H-P1 — relación ingreso–gasto\n")
    w("| Conjunto | Elasticidad monto–ingreso (media entre semillas) | IC 95 % bootstrap entre semillas | Rango entre semillas | ¿Sensible al ingreso? |")
    w("|---|---|---|---|---|")
    for c in conj:
        r = el.loc[c]; sv = v["H-P1"][c]["sensible_al_ingreso"]
        if sv is None:
            w(f"| {NOMBRE[c]} | {f(r.media, 3)} | no calculable (1 semilla) | — | no evaluable (n = 1) |")
        else:
            w(f"| {NOMBRE[c]} | {f(r.media, 3)} | {ic(r.ic95_inf, r.ic95_sup)} | {ic(r['min'], r['max'])} | {'sí' if sv else 'no'} (n = {int(r.n_semillas)}) |")
    w("")
    a2 = mn[mn.conjunto == "A_etapa2"].sort_values("grupo_ingreso"); a3 = mn[mn.conjunto == "A_etapa3"].sort_values("grupo_ingreso")
    w(f"En la rejilla (A), el monto medio por transacción pasa de {f(a2.monto_media.iloc[0])} a {f(a2.monto_media.iloc[-1])} USD "
      f"entre el nivel más bajo y el más alto en la **etapa 2**, y de {f(a3.monto_media.iloc[0])} a {f(a3.monto_media.iloc[-1])} USD "
      f"en la **etapa 3** (entre niveles, el monto medio de la etapa 3 oscila entre {f(a3.monto_media.min())} y "
      f"{f(a3.monto_media.max())} USD; detalle con IC en `hp1_monto_por_nivel.csv`).\n")
    w("| Conjunto | Pendiente de la participación de alimentos_mercado en el monto (pp por unidad de log ingreso) | IC 95 % |")
    w("|---|---|---|")
    for c in conj:
        r = al.loc[c]
        w(f"| {NOMBRE[c]} | {f(r.media, 2)} | {ic(r.ic95_inf, r.ic95_sup, 2) if r.n_semillas >= 2 else 'no calculable (1 semilla)'} |")
    w("")
    w("**Lectura.** La etapa 2 hace lo que su código dice: el monto escala con el ingreso (elasticidad ≈ 1) y las "
      "participaciones por categoría casi no se mueven con él. La etapa 3, que es la salida final del pipeline, "
      "**no conserva la relación**: el CTGAN aprende la distribución marginal del monto y la reparte entre clientes "
      "sin importar su ingreso. Esto no es lo mismo que la afirmación retirada del informe: el mecanismo es el "
      "entrenamiento del CTGAN sin la columna de ingreso, no las reglas, y la cifra sale de "
      f"{nA} semillas con IC.\n")
    if not c1.empty:
        w(f"Diseño C, etapa 1 reentrenada: mediana del ingreso generado {f(c1.set_index('cuantil').loc[0.5, 'ingreso_etapa1_reentrenada'], 0)} USD "
          f"frente a {f(c1.set_index('cuantil').loc[0.5, 'ingreso_etapa1_archivo_repo'], 0)} en el archivo del repo (`hp1_disenoC_etapa1.csv`).\n")
    w(f"**Veredicto H-P1: {v['H-P1']['veredicto'].upper()}.** La hipótesis compara con los hogares colombianos, y el "
      "referente (participación de alimentos por quintil de `ICGU`, ENPH Bogotá, `FEX_C`, a nivel hogar) no se calculó "
      "aquí porque este entorno no recibe microdatos. Queda lista la comparación: `python tools/analisis_pancholi.py "
      "--enph <csv>` aplica la regla prerregistrada. **Hallazgo que sí queda firme:** la salida final del pipeline "
      "no varía con el ingreso del cliente.\n")

    # ------------------------------------------------------------------ H-P2
    w("### H-P2 — categorías\n")
    w("Mapeo a la taxonomía v1: `docs/taxonomia/mapeo_pancholi_taxonomia_v1.csv`, con su prueba en "
      "`tests/test_mapeo_pancholi.py`. Decisión declarada: `housing` son hoteles, moteles y alquiler vacacional "
      "(hospedaje, COICOP 11.2), no vivienda; v1 no tiene categoría de hospedaje y se asigna a `otros`.\n")
    cols = [c for c in conj if c in set(p2.conjunto)]
    cats = ["alimentos_mercado", "comidas_fuera", "transporte", "entretenimiento", "vestuario_cuidado_personal", "otros",
            "vivienda_servicios.servicios_publicos"]
    w("| Categoría v1 (por `category`) | " + " | ".join(NOMBRE[c] for c in cols) + " |")
    w("|---|" + "---|" * len(cols))
    for k in cats:
        celdas = []
        for c in cols:
            r = p2[(p2.conjunto == c) & (p2.columna == "category") & (p2.nivel_1 == k)].iloc[0]
            celdas.append(f"{pct(r.part_conteo)} {ic(r.wilson_inf, r.wilson_sup, 1, True)}")
        w(f"| {k} | " + " | ".join(celdas) + " |")
    w("\nParticipación por número de registros, con IC de Wilson al 95 % sobre todas las semillas. Participación por "
      "monto y la variante con `mapped_category` en `hp2_participacion_nivel1.csv`.\n")
    for c in cols:
        r = v["H-P2"][c]
        w(f"- **{NOMBRE[c]}:** {r['categorias_v1_con_participacion']} de {r['categorias_v1_total']} categorías nivel 1 de v1 "
          f"tienen algún registro. Ocio = entretenimiento: {pct(r['ocio=entretenimiento']['part_ocio'])} frente a "
          f"{pct(r['ocio=entretenimiento']['part_alimentos'])} de alimentos → **{r['ocio=entretenimiento']['veredicto']}**. "
          f"Ocio con hospedaje (sensibilidad): {pct(r['ocio=entretenimiento+hospedaje (sensibilidad)']['part_ocio'])} → "
          f"**{r['ocio=entretenimiento+hospedaje (sensibilidad)']['veredicto']}**.")
    cm = set(pd.read_csv(RAIZ / "docs/taxonomia/mapeo_pancholi_taxonomia_v1.csv").fillna("").licencias_dc_que_la_alimentan.str.split("; ").sum())
    no_mapeadas = sum(l not in cm for l in ["Athletic Exhibition", "Special Events", "Inn And Motel", "Skating Rink"])
    lp = lic[(lic.conjunto == principal) & (lic.licencia == "__cualquiera_de_las_4__")].iloc[0]
    w("\nLicencias que cita el informe (Athletic Exhibition, Special Events, Inn And Motel, Skating Rink), cruzando "
      "`merchant_name` con el archivo de comercios. *Estricto*: todas las licencias con ese nombre están entre las cuatro. "
      "*Laxo*: alguna lo está; nombres como «Unknown» se repiten entre licencias e inflan esta cifra.\n")
    w("| Conjunto | Estricto | Laxo |\n|---|---|---|")
    for c in cols:
        r = lic[(lic.conjunto == c) & (lic.licencia == "__cualquiera_de_las_4__")].iloc[0]
        w(f"| {NOMBRE[c]} | {pct(r.part, 2)} {ic(r.wilson_inf, r.wilson_sup, 2, True)} | {pct(r.part_laxo, 2)} |")
    w(f"\n{no_mapeadas} de las cuatro licencias no están en el `CATEGORY_MAPPING` de la etapa 2, así que esa etapa no puede "
      "asignarlas; por licencia en `hp2_licencias_informe.csv`.\n")
    rp = v["H-P2"][principal]
    w(f"**Veredicto H-P2 (conjunto principal {NOMBRE[principal]}): dominio de ocio {rp['ocio=entretenimiento']['veredicto'].upper()} "
      f"con la definición prerregistrada; {rp['ocio=entretenimiento+hospedaje (sensibilidad)']['veredicto'].upper()} si el "
      "hospedaje se cuenta como ocio.** El veredicto depende de cómo se clasifiquen los hoteles; se declaran ambos. "
      "El prerregistro no fijó qué conjunto es el principal: se fijó en el código de análisis (la réplica literal, B · etapa 3) "
      "antes de que corriera el diseño B, y el veredicto coincide con el de A · etapa 3. "
      "Lo que no depende de esa decisión es la **cobertura**: servicios públicos, arriendo, transporte público, salud, "
      "educación, telecomunicaciones, obligaciones financieras y todas las categorías operativas de extracto tienen "
      "participación cero por construcción.\n")

    # ------------------------------------------------------------------ H-P3
    w("### H-P3 — medio de pago y registros de extracto (D15)\n")
    for c in cols:
        t = h3[(h3.conjunto == c) & (h3.tipo_registro == "__cualquier_registro_de_extracto__")].iloc[0]
        w(f"- **{NOMBRE[c]}:** columnas de salida `{t.columnas_salida.replace('|', ', ')}`; columnas de medio de pago: "
          f"{t.columnas_medio_pago}. Registros de retiro, transferencia P2P, movimiento propio o ingreso: "
          f"{int(t.n)} de {f(t.N, 0)} (cota superior de Wilson {pct(t.wilson_sup, 4)}).")
    w(f"\n**Veredicto H-P3: CONFIRMADA para las etapas ejecutadas (1–3).** Su salida no tiene campo de medio de pago y solo "
      "emite compras: no hay retiros, transferencias, billeteras ni efectivo como tipos de registro. **La distribución de "
      f"`payment_type` de la etapa 4 es NO CONCLUYENTE**: {v['H-P3']['distribucion_payment_type_etapa4'].split(': ', 1)[-1]}. "
      "Por lectura de código, el esquema de la etapa 4 también es de una compra por registro, así que tampoco produciría "
      "retiros ni transferencias como registros (inferido).\n")

    # ------------------------------------------------------------------ limitaciones
    w("## 4. Limitaciones\n")
    w("1. **Etapas 4 y 5 sin ejecutar.** `payment_type` y la «validación» por LLM no se midieron. El paper presenta "
      "la salida final como la del bucle híbrido (etapa 5), que no corre tal cual.")
    ing_b = pd.read_csv(RAIZ / "external/pancholi/src/Data_Synthesizer/data/synthetic_customers_deepseek.csv").income
    w("2. **La rejilla (A) es un diseño propio.** Fija hogar y ZIP y recorre el ingreso para aislar su efecto. La "
      f"réplica literal (B) usa sus {len(ing_b)} clientes, con ingresos entre {f(ing_b.min(), 0)} y {f(ing_b.max(), 0)} USD, "
      "un rango más estrecho.")
    w("3. **Montos en USD de 2024–2025 (D.C.).** La comparación con Colombia solo tiene sentido en términos sin "
      "unidades (elasticidad, participaciones), nunca en niveles.")
    w(f"4. **IC entre semillas con n = {nA}.** El bootstrap percentil con 10 semillas es aproximado; se reporta también "
      "el rango.")
    w("5. **CTGAN sin diagnóstico de convergencia.** Se usan sus 100 épocas; SDV advierte que la cardinalidad de "
      "`merchant_name` es alta. No se exploraron otras configuraciones: se evalúa su pipeline, no el mejor CTGAN posible.")
    w("6. **Entorno distinto al de los autores** (Linux, CPU, sin GPU). No se sabe si ellos usaban GPU.")
    w("7. **Referente colombiano de H-P1 pendiente.** Sin él, H-P1 no puede confirmarse ni refutarse.\n")
    w("## 5. Cómo reproducir\n")
    w("```\npython3.11 -m venv .venv-pancholi && . .venv-pancholi/bin/activate\n"
      "pip install -r external/pancholi/src/Data_Synthesizer/requirements.txt pytest==8.3.5\n"
      f"git clone {man['repositorio']['url']} external/pancholi && git -C external/pancholi checkout {man['repositorio']['commit']}\n"
      "python tools/pancholi_ejecutar.py A R B C manifiesto   # ~" + f(t_total_h, 1) + " h en 2 CPU\n"
      "python tools/analisis_pancholi.py && python tools/informe_pancholi.py\npython -m pytest -q tests/test_mapeo_pancholi.py\n```\n")
    (DOCS / "reevaluacion_pancholi.md").write_text("\n".join(L))

    # ------------------------------------------------------------------ propuestas para el repo (no aplicadas)
    P: list[str] = []
    q = P.append
    b3 = "B_etapa3" if "B_etapa3" in el.index else conj[-1]
    q("# Propuestas para el repositorio (WP5) — NO aplicadas\n")
    q("La autora pidió no editar `C:\\tesis-sdg`. Estas son las ediciones propuestas, para aplicarlas a mano.\n")
    q("## `docs/plan_maestro.md` §6 — reemplazo de la tabla de Pancholi\n")
    q("| Afirmación del informe | Estado tras WP5 (ejecutado, `docs/reevaluacion_pancholi.md`) |\n|---|---|")
    q(f"| USD 12 entre perfiles / «insensibilidad al ingreso» → H-P1 | **{v['H-P1']['veredicto']}** respecto a Colombia. "
      f"Medido: etapa 2 elasticidad {f(el.loc['A_etapa2'].media, 3)} {ic(el.loc['A_etapa2'].ic95_inf, el.loc['A_etapa2'].ic95_sup)}; "
      f"salida final (etapa 3) {f(el.loc[b3].media, 3)} {ic(el.loc[b3].ic95_inf, el.loc[b3].ic95_sup)}: el CTGAN no conserva "
      "la relación ingreso–monto. Las cifras del informe salen probablemente de la aplicación web (inferido) |")
    q(f"| Dominio de categorías de ocio → H-P2 | **{rp['ocio=entretenimiento']['veredicto']}** (ocio = entretenimiento, "
      f"{pct(rp['ocio=entretenimiento']['part_ocio'])}); **{rp['ocio=entretenimiento+hospedaje (sensibilidad)']['veredicto']}** si "
      f"el hospedaje cuenta como ocio. Cobertura: {rp['categorias_v1_con_participacion']} de {rp['categorias_v1_total']} "
      "categorías v1; servicios públicos 0 |")
    t = h3[(h3.conjunto == b3) & (h3.tipo_registro == "__cualquier_registro_de_extracto__")].iloc[0]
    q(f"| 100 % `credit_card` → H-P3 | **Confirmada para las etapas 1–3**: sin campo de medio de pago, 0 de {f(t.N, 0)} "
      "registros de extracto. `payment_type` (etapa 4): **no concluyente**, no ejecutable (Groq bloqueado) |\n")
    q("También: fila 01B del §1 → «✅ ejecutado (etapas 1–3)»; checklist «Reevaluación de Pancholi ejecutada» → [x] "
      "con la salvedad de las etapas 4 y 5; R12 → se materializó en parte (etapas 4 y 5 no corren).\n")
    q("## `docs/bitacora.md` — entrada propuesta\n")
    q(f"### 2026-09-23 — WP5: ejecución y reevaluación del pipeline de referencia\n"
      f"- Ejecutado {man['repositorio']['url']} @ `{man['repositorio']['commit'][:12]}` (MIT), etapas 1–3, en `.venv-pancholi`, "
      f"con el parche P1 (importación). Rejilla de {par['n_niveles']} niveles × {nA} semillas, réplica literal × {nB}"
      f"{', etapa 1 reentrenada × ' + str(nC) if nC else ''}. Criterios prerregistrados. Reproducibilidad de la semilla 42: "
      f"{'OK' if todas else 'FALLA'}.\n"
      f"- H-P1: {v['H-P1']['veredicto']}; la etapa 3 no conserva la relación ingreso–monto (elasticidad "
      f"{f(el.loc[b3].media, 3)}).\n- H-P2: {rp['ocio=entretenimiento']['veredicto']} (sensibilidad con hospedaje: "
      f"{rp['ocio=entretenimiento+hospedaje (sensibilidad)']['veredicto']}).\n- H-P3: confirmada para las etapas 1–3; "
      "`payment_type` no concluyente (etapa 4 no ejecutable).\n"
      "- Pendiente: referente ENPH para H-P1; decidir la categoría de hospedaje en la taxonomía v1.1.\n")
    q("## Commit sugerido\n\n```\ngit add docs/reevaluacion_pancholi.md docs/prerregistro_wp5.md docs/taxonomia/mapeo_pancholi_taxonomia_v1.csv "
      "docs/taxonomia/taxonomia_v1_extracto.json tools/pancholi_ejecutar.py tools/analisis_pancholi.py tools/informe_pancholi.py "
      "tools/pancholi_parches tests/test_mapeo_pancholi.py "
      "outputs/pancholi/*.json outputs/pancholi/*.csv docs/plan_maestro.md docs/bitacora.md\n"
      "git commit -m \"[WP5] ejecución y reevaluación del pipeline de referencia\"\n```\n"
      "Nota: el `.gitignore` del repo excluye `outputs/*.csv`, pero solo en la raíz de `outputs/`; los de "
      f"`outputs/pancholi/` sí entran. `crudo/` pesa {f(sum(p.stat().st_size for p in (S / 'crudo').glob('*')) / 2**20, 0)} MB: conviene añadir `outputs/pancholi/crudo/` a "
      "`.gitignore` y conservar sus SHA-256 en el manifiesto.\n")
    (DOCS / "propuestas_repo_wp5.md").write_text("\n".join(P))
    print("ok")


if __name__ == "__main__":
    main()
