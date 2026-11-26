# Resultados TSTR — WP8

> **PROVISIONAL.** Archivo regenerado por `tools/etapa4_tstr.py`; no editar a mano.
> Última regeneración: 2026-11-26T15:46:51+00:00.
> Taxonomía 1.1.0, target `categoria_n1`, semilla 42.

**Taxonomía.** La v1.1.0 no cambió las 16 categorías ni las reglas R1–R7, solo documentación y metadatos
de anotación (T1–T6, §9 de `taxonomia_gastos_colombia_v1.md`); el CTGAN entrenado con el JSON v1.0.0 sigue
siendo válido para el TSTR y no se regenera.

**Texto (D14).** Ambas fuentes reciben la `descripcion` de la misma capa de texto (`src/sdg/texto.py`,
`tools/etapa3b_texto.py`): mismas plantillas, comercios y semilla, ninguna calibrada con el real de WP4.

**Swap a WP4.** El TSTR se activa con una sola ruta (`--test data/reales_anon/test_real_wp4_<AAAAMMDD>.csv`, escrito
por `tools/consolidar_test_wp4.py`). Esquema: `descripcion, monto, fecha, signo, cuenta_tipo, categoria_n1, fuente_etiqueta, voluntario_id` y columnas de análisis
`item_id, tx_id, categoria_n2, medio_pago, formalidad_comercio, canal_p2p, peso_muestreo, estrato_muestreo, doble_anotacion, origen_etiqueta, caso_convencion, subgrupo_reverso, unica_por_descripcion`, ninguna como entrada. Verificado de punta a punta con el real simulado
(`tests/fixtures/real_simulado_wp4.csv`) y con la salida del consolidador sobre datos simulados
(`tests/test_swap_wp4.py`). Las predicciones por ítem del real van a `data/_privado/tstr/` (ignorado por git).

## Tabla TSTR (único resultado reportable)

Entrenamiento sobre **todo** el sintético; evaluación sobre el conjunto **real anotado de WP4** (pre-registro
`docs/datos_reales/05_prerregistro_muestreo_anotacion.md` v1.3). **Métrica principal:** F1-macro **sin ponderar**
sobre los ítems del test, con regla de soporte: clases con < 10 filas de la muestra se recodifican a
`otros` (en etiqueta real y predicha) antes del promedio. **IC95 principal (D-M7):** bootstrap por fila
(1000 réplicas, semilla 42) estratificado por `estrato_muestreo`. **Sensibilidad:** bootstrap por
grupo de extractos (`voluntario_id` = grupo, no titular). **Secundaria (D-M6):** exactitud ponderada con
`peso_muestreo` (estimador de Hájek), con IC por el mismo bootstrap; la exactitud sin ponderar describe la mezcla de
la muestra, no la de un extracto.

| Brazo | Fuente train | F1-macro (soporte ≥10) | IC95 principal (fila estrat.) | IC95 por grupo (sensibilidad) | Exactitud | Exactitud ponderada [IC95] | n train | n test | fusionadas a otros |
|---|---|---|---|---|---|---|---|---|---|
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (reglas) | 0.566 | [0.440, 0.611] | [0.392, 0.598] | 0.440 | 0.324 [0.222, 0.438] | 122,211 | 200 | 5 clases (lista en metricas.json) |
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (CTGAN) | 0.567 | [0.452, 0.612] | [0.386, 0.642] | 0.420 | 0.307 [0.210, 0.421] | 122,211 | 200 | 5 clases (lista en metricas.json) |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (reglas) | 0.458 | [0.345, 0.503] | [0.297, 0.593] | 0.350 | 0.230 [0.146, 0.350] | 20,000 | 200 | 5 clases (lista en metricas.json) |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (CTGAN) | 0.511 | [0.391, 0.563] | [0.313, 0.607] | 0.370 | 0.290 [0.194, 0.406] | 20,000 | 200 | 5 clases (lista en metricas.json) |
| BETO fine-tuning | protocolo (reglas) | 0.453 | [0.351, 0.520] | [0.342, 0.520] | 0.385 | 0.225 [0.164, 0.304] | 20,000 | 200 | 5 clases (lista en metricas.json) |
| BETO fine-tuning | protocolo (CTGAN) | 0.474 | [0.354, 0.522] | [0.341, 0.507] | 0.355 | 0.201 [0.143, 0.275] | 20,000 | 200 | 5 clases (lista en metricas.json) |
| LLM vía Groq, prompting few-shot (modelo y desviación en Costo) | protocolo (reglas) | no evaluado: brazo LLM no evaluado sobre el real por restricción de tratamiento de datos; humo sobre sintético en `outputs/tstr/sanity/reglas/llm_groq/` | | | | | | | |
| LLM vía Groq, prompting few-shot (modelo y desviación en Costo) | protocolo (CTGAN) | no evaluado: brazo LLM no evaluado sobre el real por restricción de tratamiento de datos; humo sobre sintético en `outputs/tstr/sanity/ctgan/llm_groq/` | | | | | | | |

### Sensibilidades pre-registradas (§4)

Cada F1 recalcula la regla de soporte en su subconjunto («fusiona además» = clases que se pierden frente a la
principal). (c) recorta los pesos al percentil 95 y renormaliza; ⚠ si cambia la exactitud ponderada en más de 5
puntos. (d) los reversos y devoluciones de tarjeta están dentro de la métrica principal y se muestran aparte.
(e) el κ sin los casos de convención lo calcula `tools/acuerdo_wp4.py`, no WP8.

| Brazo | Fuente train | (a) F1 una fila por descripción [IC95] | (b) F1 solo doble anotación [IC95] | (c) Exactitud ponderada P95 (Δ vs. sin recorte) | (d) Reversos: aciertos/n |
|---|---|---|---|---|---|
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (reglas) | 0.531 [0.452, 0.622] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.348 (Δ -0.024) | 1/6 |
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (CTGAN) | 0.556 [0.464, 0.655] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.327 (Δ -0.020) | 1/6 |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (reglas) | 0.404 [0.335, 0.492] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.233 (Δ -0.003) | 0/6 |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (CTGAN) | 0.498 [0.408, 0.587] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.306 (Δ -0.016) | 0/6 |
| BETO fine-tuning | protocolo (reglas) | 0.447 [0.362, 0.525] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.275 (Δ -0.050) | 0/6 |
| BETO fine-tuning | protocolo (CTGAN) | 0.433 [0.350, 0.518] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.245 (Δ -0.044) | 0/6 |

**Declaraciones (D-M6, D-M7, pre-registro §3–§4).**
- **Alcance del IC:** incertidumbre de muestreo **dentro de estos extractos**; no es generalización a nuevos titulares.
  El IC por fila supone filas independientes y subestima la variación entre personas.
- **Sensibilidad por grupo:** 6 grupos de extractos; solo admiten unas pocas réplicas distintas y las clases están
  concentradas por grupo, así que ese IC es inestable. Se reporta al lado, no como principal.
- **Exactitud ponderada:** n efectivo de Kish = 48 (cota inferior: los ítems pesados son copias de la misma
  descripción). Su IC sale ancho por diseño. Los PSE sin facturador (≈ 4,4 % del marco, 95 filas) no tienen ningún ítem
  en el test: la exactitud ponderada no dice nada de ellos.
- **Etiqueta-por-texto vs. declaración:** todas las filas son etiqueta-por-texto (R2: ningún propósito declarado); el corte no aporta.
- **Representatividad:** 6 grupos de ≤ 7 titulares por conveniencia; los pesos corrigen el diseño muestral, no la
  representatividad poblacional.

**Asimetría de tamaño (declarada).** BETO entrena sobre una submuestra estratificada de 20,000 filas por
costo de CPU. La comparación de igual a igual es LogReg @20k frente a BETO @20k
(mismas filas, misma semilla); LogReg con el train completo es la mejor cifra del baseline, no un rival de BETO en
igualdad de datos. El brazo LLM no entrena: el sintético solo entra por los ejemplos few-shot.

**Pipeline de Pancholi et al.: contexto, no fila de la tabla.** WP5 concluyó la rama (a), *no mapeable* (`outputs/pancholi/wp8_mapeabilidad.json`): su generador alcanza 8 de las 16 `categoria_n1` (6 sin las rutas marginales de peso 0,01), así que un clasificador entrenado con su salida tendría un techo de F1-macro de 0.500 (0.375 sin marginales) aun acertando todo lo que puede predecir. **Hallazgo de no transferibilidad:** solo emite compras; no produce `telecom_conectividad`, `salud`, `hogar_articulos`, `obligaciones_financieras`, `transferencias_p2p`, `retiro_efectivo`, `movimiento_propio`, `ingreso`, que suman el 42% de las filas del sintético del protocolo. Tampoco produce la entrada de WP8: no modela `cuenta_tipo`, su signo es constante y su monto está en USD de Washington D.C. Por eso no se entrena sobre su salida ni se pone en esta tabla. Como contexto, su F1 publicado (regresión logística: accuracy ≈ 71 %, F1-macro 0,57; BERT afinado: accuracy ≈ 71 %, F1-macro 0,62; LSTM: accuracy < 40 %; LLaMA-3 vía API: sin métricas estándar (revisión manual de 100 transacciones)) se mide sobre un hold-out de sus propios datos sintéticos de D.C., con otras categorías y en inglés: no es comparable con el TSTR del protocolo.

### Ablación reglas → CTGAN (Δ = CTGAN − reglas, bootstrap pareado sobre el mismo test)

| Brazo | Δ F1-macro | IC95 principal (fila estrat.) | IC95 por grupo (sensibilidad) |
|---|---|---|---|
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | +0.001 | [-0.055, +0.059] | [-0.051, +0.076] |
| Baseline: LogReg @20k (mismas filas que BETO) | +0.053 | [+0.001, +0.105] | [-0.025, +0.095] |
| BETO fine-tuning | +0.021 | [-0.065, +0.059] | [-0.052, +0.049] |

**Entrada (idéntica en los tres brazos).** `[CUENTA=<cuenta_tipo>] [SIGNO=<signo>] [MONTO=<bin_log>] <descripcion>`; `monto` en bins log10 de media década, en
pesos de promedio 2025 (el sintético ya lo está; el real de WP4 se deflacta con el IPC total nacional del mes si trae
`fecha`). Son observables del extracto, no anotaciones. Indicio del sanity (no reportable): frente a solo
`descripcion`, el F1-macro del baseline sube poco y la ganancia está en `transferencias_p2p` e `ingreso` (el signo, la
cuenta y el monto separan P2P recibida de ingreso y P2P sin propósito de pagos con propósito); `retiro_efectivo` y
`movimiento_propio` ya estaban en el techo solo con texto. Las ambigüedades de categoría por texto no se resuelven, y
en las filas etiquetadas por declaración el monto mueve errores hacia clases raras (en el sanity, `educacion` cae).
El techo por diseño de esas filas sigue intacto; el efecto real se mide solo sobre el test de WP4.

**Brazo LLM.** brazo LLM no evaluado sobre el real por restricción de tratamiento de datos; humo sobre sintético en `outputs/tstr/sanity/{reglas,ctgan}/llm_groq/` (decisión final del 26-nov-2026: no se envían datos
reales a Groq). El humo usa `openai/gpt-oss-120b` porque Groq retiró `llama-3.3-70b-versatile` de las cuentas
free/developer el 16-ago-2026 (desviación en `metricas.json`); las respuestas vacías o fuera del enum se cuentan como
error (etiqueta centinela `__fuera_de_enum__`), no se descartan. Con 40 filas su F1-macro no es interpretable.

**Cómo leer estos números.** El TSTR absoluto mide *plantillas + estructura*: está acotado por el realismo
de las plantillas de texto (regla propia, más limpias y regulares que un extracto real), así que es una cota
del protocolo completo, no de la Etapa 3 sola. La diferencia reglas → CTGAN, con plantillas idénticas,
aísla la capa estructural: es el número que atribuye una mejora (o un deterioro) al generador CTGAN y no al
texto. Las filas que el CTGAN emite con combinaciones que el generador por reglas nunca produce (1.8%,
`outputs/texto/manifest.json`) no se reparan: su error es de la Etapa 3 y el TSTR lo cobra.

---

## Costo de cómputo (declarado)

| Modo | Fuente | Brazo | n train efectivo | segundos | detalle |
|---|---|---|---|---|---|
| sanity | ctgan | beto | 2,000 | 2,602 | BETO CPU 4 hilos: 2,000 filas x 3 épocas = 375 pasos, 2.71 s/paso, 0.28 h de entrenamiento |
| sanity | ctgan | llm_groq | 18 | 0 | openai/gpt-oss-120b: 38 entradas únicas (0 llamadas nuevas, 38 del registro), 62,027 tokens; DESVIACIÓN: llama-3.3-70b-versatile no disponible para esta cuenta (retirado por Groq 16-ago-2026); sustituido por openai/gpt-oss-120b |
| sanity | ctgan | logreg | 97,768 | 50 |  |
| sanity | ctgan | logreg_n20000 | 20,000 | 12 |  |
| sanity | reglas | beto | 2,000 | 2,830 | BETO CPU 4 hilos: 2,000 filas x 3 épocas = 375 pasos, 2.02 s/paso, 0.21 h de entrenamiento |
| sanity | reglas | llm_groq | 18 | 0 | openai/gpt-oss-120b: 38 entradas únicas (0 llamadas nuevas, 38 del registro), 62,384 tokens; DESVIACIÓN: llama-3.3-70b-versatile no disponible para esta cuenta (retirado por Groq 16-ago-2026); sustituido por openai/gpt-oss-120b |
| sanity | reglas | logreg | 97,768 | 34 |  |
| sanity | reglas | logreg_n20000 | 20,000 | 11 |  |
| tstr | ctgan | beto | 20,000 | 10 | BETO CPU 4 hilos: 20,000 filas x 3 épocas = 3,750 pasos, 1.27 s/paso, 1.33 h de entrenamiento (entrenado aparte con --solo-entrenar) |
| tstr | ctgan | logreg | 122,211 | 28 |  |
| tstr | ctgan | logreg_n20000 | 20,000 | 4 |  |
| tstr | reglas | beto | 20,000 | 20 | BETO CPU 4 hilos: 20,000 filas x 3 épocas = 3,750 pasos, 1.47 s/paso, 1.53 h de entrenamiento (entrenado aparte con --solo-entrenar) |
| tstr | reglas | logreg | 122,211 | 32 |  |
| tstr | reglas | logreg_n20000 | 20,000 | 4 |  |

---

## Sanity check — NO REPORTABLE

Holdout 80/20 estratificado por `categoria_n1` **dentro de cada sintético**. Mide ajuste interno del
clasificador al generador, no transferencia a datos reales. No es TSTR, no va al informe como resultado y
no admite Δ pareado (cada fuente tiene su propio holdout). `reglas_original` = texto original del generador
por reglas (diagnóstico de la capa de texto factorizada).

| Brazo | Fuente train | F1-macro (soporte ≥10) | IC95 | F1-macro solo etiqueta-por-texto | IC95 | n train | n test | fusionadas a otros |
|---|---|---|---|---|---|---|---|---|
| beto | ctgan | 0.566 | [0.560, 0.572] | 0.593 | [0.586, 0.600] | 2,000 | 24,443 | — |
| llm_groq | ctgan | 0.987 ⚠ no interpretable (1 clase evaluable) | [0.702, 1.000] | 0.986 | [0.770, 1.000] | 18 | 40 | 15 clases (lista en metricas.json) |
| logreg | ctgan | 0.866 | [0.859, 0.873] | 0.909 | [0.902, 0.916] | 97,768 | 24,443 | — |
| logreg_n20000 | ctgan | 0.864 | [0.857, 0.871] | 0.907 | [0.899, 0.914] | 20,000 | 24,443 | — |
| beto | reglas | 0.616 | [0.607, 0.624] | 0.647 | [0.638, 0.656] | 2,000 | 24,443 | — |
| llm_groq | reglas | 0.974 ⚠ no interpretable (1 clase evaluable) | [0.715, 1.000] | 1.000 | [0.925, 1.000] | 18 | 40 | 15 clases (lista en metricas.json) |
| logreg | reglas | 0.889 | [0.878, 0.898] | 0.941 | [0.931, 0.948] | 97,768 | 24,443 | — |
| logreg_n20000 | reglas | 0.860 | [0.850, 0.869] | 0.936 | [0.927, 0.945] | 20,000 | 24,443 | — |
