# Resultados TSTR — WP8

> Archivo regenerado por `tools/etapa4_tstr.py`; no editar a mano.
> Última regeneración: 2026-11-26T17:59:58+00:00.
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
`docs/datos_reales/05_prerregistro_muestreo_anotacion.md` v1.4: diseño y métricas de la v1.3; la v1.4 solo registra
desviaciones de ejecución, §13). **Métrica principal:** F1-macro **sin ponderar**
sobre los ítems del test, con regla de soporte: clases con < 10 filas de la muestra se recodifican a
`otros` (en etiqueta real y predicha) antes del promedio. **IC95 principal (D-M7):** bootstrap por fila
(1000 réplicas, semilla 42) estratificado por `estrato_muestreo`. **Sensibilidad:** bootstrap por
grupo de extractos (`voluntario_id` = grupo, no titular). **Secundaria (D-M6):** exactitud ponderada con
`peso_muestreo` (estimador de Hájek), con IC por el mismo bootstrap; la exactitud sin ponderar describe la mezcla de
la muestra, no la de un extracto.

| Brazo | Fuente train | F1-macro (soporte ≥10) | IC95 principal (fila estrat.) | IC95 por grupo (sensibilidad) | Exactitud | Exactitud ponderada [IC95] | n train | n test | fusionadas a otros |
|---|---|---|---|---|---|---|---|---|---|
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (reglas) | 0.566 | [0.507, 0.619] | [0.471, 0.601] | 0.440 | 0.324 [0.222, 0.438] | 122,211 | 200 | 5 clases (lista en metricas.json) |
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (CTGAN) | 0.567 | [0.507, 0.619] | [0.447, 0.602] | 0.420 | 0.307 [0.210, 0.421] | 122,211 | 200 | 5 clases (lista en metricas.json) |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (reglas) | 0.458 | [0.397, 0.508] | [0.354, 0.544] | 0.350 | 0.230 [0.146, 0.350] | 20,000 | 200 | 5 clases (lista en metricas.json) |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (CTGAN) | 0.511 | [0.446, 0.568] | [0.366, 0.578] | 0.370 | 0.290 [0.194, 0.406] | 20,000 | 200 | 5 clases (lista en metricas.json) |
| BETO fine-tuning | protocolo (reglas) | 0.453 | [0.385, 0.520] | [0.335, 0.491] | 0.385 | 0.225 [0.164, 0.304] | 20,000 | 200 | 5 clases (lista en metricas.json) |
| BETO fine-tuning | protocolo (CTGAN) | 0.474 | [0.410, 0.528] | [0.357, 0.514] | 0.355 | 0.201 [0.143, 0.275] | 20,000 | 200 | 5 clases (lista en metricas.json) |
| LLM vía Groq, prompting few-shot (modelo y desviación en Costo) | protocolo (reglas) | no evaluado: brazo LLM no evaluado sobre el real por restricción de tratamiento de datos; humo sobre sintético en `outputs/tstr/sanity/reglas/llm_groq/` | | | | | | | |
| LLM vía Groq, prompting few-shot (modelo y desviación en Costo) | protocolo (CTGAN) | no evaluado: brazo LLM no evaluado sobre el real por restricción de tratamiento de datos; humo sobre sintético en `outputs/tstr/sanity/ctgan/llm_groq/` | | | | | | | |

### Sensibilidad del intervalo (misma réplica; corrección del 26-nov-2026)

**Corrección posterior a la primera corrida oficial (26-nov-2026).** Qué estaba mal: el bootstrap recalculaba la
regla de soporte (≥ 10) dentro de cada réplica. Con cinco clases en el umbral en el test (`educacion` y
`retiro_efectivo` con 10, `ingreso` y `salud` con 11, `entretenimiento` con 9), en ~95 % de las réplicas cambiaba el
conjunto de clases evaluadas: el IC no correspondía al estimador reportado y quedaba desplazado ~0,05 hacia abajo
(punto pegado al límite superior). Qué se cambió: la regla se fija una vez sobre el test observado y todas las
réplicas evalúan las mismas clases (IC principal, por grupo, sensibilidades y Δ de la ablación). Las cifras
**puntuales no cambiaron** (la corrida repetida las reproduce exactamente); solo cambian los IC. El IC anterior se
conserva en la última columna para trazabilidad. Como sensibilidad
se reportan el IC básico y el BCa (z0 por proporción de réplicas bajo el punto; aceleración por jackknife de filas,
aproximación con remuestreo estratificado).

| Brazo | Fuente train | F1-macro | IC95 percentil (principal) | IC95 básico | IC95 BCa | media bootstrap (sesgo) | IC95 con la regla recalculada por réplica (1.ª corrida) |
|---|---|---|---|---|---|---|---|
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (reglas) | 0.566 | [0.507, 0.619] | [0.513, 0.626] | [0.511, 0.623] | 0.565 (-0.002) | [0.440, 0.611] |
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (CTGAN) | 0.567 | [0.507, 0.619] | [0.516, 0.628] | [0.516, 0.633] | 0.563 (-0.004) | [0.452, 0.612] |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (reglas) | 0.458 | [0.397, 0.508] | [0.408, 0.519] | [0.404, 0.517] | 0.455 (-0.003) | [0.345, 0.503] |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (CTGAN) | 0.511 | [0.446, 0.568] | [0.455, 0.576] | [0.454, 0.575] | 0.508 (-0.003) | [0.391, 0.563] |
| BETO fine-tuning | protocolo (reglas) | 0.453 | [0.385, 0.520] | [0.387, 0.521] | [0.398, 0.529] | 0.450 (-0.003) | [0.351, 0.520] |
| BETO fine-tuning | protocolo (CTGAN) | 0.474 | [0.410, 0.528] | [0.421, 0.539] | [0.422, 0.533] | 0.469 (-0.005) | [0.354, 0.522] |

### Líneas base (contexto, mismo test y misma regla de soporte; no entran a la ablación)

| Línea base | Fuente train | F1-macro (soporte ≥10) | IC95 principal | Exactitud | Exactitud ponderada |
|---|---|---|---|---|---|
| Clase mayoritaria del sintético | protocolo (reglas) | 0.013 | [0.009, 0.017] | 0.075 | 0.105 |
| Clase mayoritaria del sintético | protocolo (CTGAN) | 0.013 | [0.009, 0.017] | 0.075 | 0.105 |
| Aleatorio estratificado (distribución del sintético, semilla 42) | protocolo (reglas) | 0.060 | [0.038, 0.085] | 0.055 | 0.057 |
| Aleatorio estratificado (distribución del sintético, semilla 42) | protocolo (CTGAN) | 0.059 | [0.037, 0.083] | 0.055 | 0.057 |

### Sensibilidades pre-registradas (§4)

Cada F1 recalcula la regla de soporte en su subconjunto («fusiona además» = clases que se pierden frente a la
principal). (c) recorta los pesos al percentil 95 y renormaliza; ⚠ si cambia la exactitud ponderada en más de 5
puntos. (d) los reversos y devoluciones de tarjeta están dentro de la métrica principal y se muestran aparte.
(e) el κ sin los casos de convención lo calcula `tools/acuerdo_wp4.py`, no WP8.

| Brazo | Fuente train | (a) F1 una fila por descripción [IC95] | (b) F1 solo doble anotación [IC95] | (c) Exactitud ponderada P95 (Δ = sin recorte − P95) | (d) Reversos: aciertos/n |
|---|---|---|---|---|---|
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (reglas) | 0.531 [0.460, 0.593] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.348 (Δ -0.024) | 1/6 |
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (CTGAN) | 0.556 [0.481, 0.626] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.327 (Δ -0.020) | 1/6 |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (reglas) | 0.404 [0.328, 0.467] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.233 (Δ -0.003) | 0/6 |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (CTGAN) | 0.498 [0.417, 0.571] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.306 (Δ -0.016) | 0/6 |
| BETO fine-tuning | protocolo (reglas) | 0.447 [0.366, 0.525] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.275 (Δ -0.0498: **en el umbral** de ±0.05; sin alerta formal) | 0/6 |
| BETO fine-tuning | protocolo (CTGAN) | 0.433 [0.357, 0.502] (n=153); fusiona además: educacion, ingreso, retiro_efectivo | no aplica | 0.245 (Δ -0.044) | 0/6 |

**Declaraciones (D-M6, D-M7, pre-registro §3–§4).**
- **Alcance del IC:** incertidumbre de muestreo **dentro de estos extractos**; no es generalización a nuevos titulares.
  El IC por fila supone filas independientes y subestima la variación entre personas.
- **Sensibilidad por grupo:** 6 grupos de extractos; solo admiten unas pocas réplicas distintas y las clases están
  concentradas por grupo, así que ese IC es inestable. Se reporta al lado, no como principal.
- **Exactitud ponderada:** n efectivo de Kish = 48 (cota inferior: los ítems pesados son copias de la misma
  descripción). Su IC sale ancho por diseño. Los PSE sin facturador (≈ 4,4 % del marco, 95 filas) no tienen ningún ítem
  en el test: la exactitud ponderada no dice nada de ellos.
- **Etiqueta-por-texto vs. declaración:** todas las filas son etiqueta-por-texto (R2: ningún propósito declarado); el corte no aporta.
- **Representatividad:** 7 grupos en el conjunto extraído; 6 grupos (≤6 titulares) en el marco y el test, por
  conveniencia; los pesos corrigen el diseño muestral, no la representatividad poblacional.

**Asimetría de tamaño (declarada).** BETO entrena sobre una submuestra estratificada de 20,000 filas por
costo de CPU. La comparación de igual a igual es LogReg @20k frente a BETO @20k
(mismas filas, misma semilla); LogReg con el train completo es la mejor cifra del baseline, no un rival de BETO en
igualdad de datos. El brazo LLM no entrena: el sintético solo entra por los ejemplos few-shot.

**Pipeline de Pancholi et al.: contexto, no fila de la tabla.** WP5 concluyó la rama (a), *no mapeable* (`outputs/pancholi/wp8_mapeabilidad.json`): su generador alcanza 8 de las 16 `categoria_n1` (6 sin las rutas marginales de peso 0,01), así que un clasificador entrenado con su salida tendría un techo de F1-macro de 0.500 (0.375 sin marginales) aun acertando todo lo que puede predecir. **Hallazgo de no transferibilidad:** solo emite compras; no produce `telecom_conectividad`, `salud`, `hogar_articulos`, `obligaciones_financieras`, `transferencias_p2p`, `retiro_efectivo`, `movimiento_propio`, `ingreso`, que suman el 42% de las filas del sintético del protocolo. Tampoco produce la entrada de WP8: no modela `cuenta_tipo`, su signo es constante y su monto está en USD de Washington D.C. Por eso no se entrena sobre su salida ni se pone en esta tabla. Como contexto, su F1 publicado (regresión logística: accuracy ≈ 71 %, F1-macro 0,57; BERT afinado: accuracy ≈ 71 %, F1-macro 0,62; LSTM: accuracy < 40 %; LLaMA-3 vía API: sin métricas estándar (revisión manual de 100 transacciones)) se mide sobre un hold-out de sus propios datos sintéticos de D.C., con otras categorías y en inglés: no es comparable con el TSTR del protocolo.

### Ablación reglas → CTGAN (Δ = CTGAN − reglas, bootstrap pareado sobre el mismo test)

| Brazo | Δ F1-macro | IC95 principal (fila estrat.) | IC95 por grupo (sensibilidad) |
|---|---|---|---|
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | +0.001 | [-0.055, +0.053] | [-0.061, +0.034] |
| Baseline: LogReg @20k (mismas filas que BETO) | +0.053 | [+0.012, +0.096] | [-0.010, +0.081] |
| BETO fine-tuning | +0.021 | [-0.030, +0.073] | [-0.017, +0.062] |

**Jerarquía.** La comparación principal es LogReg con el train completo; LogReg @20k y BETO @20k son secundarias. Son tres comparaciones sin corrección por comparaciones múltiples: una Δ secundaria no se interpreta como efecto si su IC95 (por fila o por grupo) toca o cruza cero.

- Baseline: LogReg + TF-IDF char 3-5 (train completo) (principal): Δ +0.001; el IC contiene cero: **sin diferencia detectable** entre fuentes.
- Baseline: LogReg @20k (mismas filas que BETO) (secundaria): Δ +0.053; algún IC toca o cruza cero → **no se interpreta como efecto**.
- BETO fine-tuning (secundaria): Δ +0.021; algún IC toca o cruza cero → **no se interpreta como efecto**.

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

## Hallazgo del protocolo: cruce de convenciones P2P / ingreso (cuantificado solo en el sintético)

La regla R2 manda a `transferencias_p2p` toda transferencia con persona sin propósito declarado, y en el test real de
WP4 ninguna etiqueta proviene de declaración del voluntario (`frac_test_etiqueta_por_declaracion` = 0 en
`metricas.json`): todo P2P real queda en `transferencias_p2p`. El generador, en cambio, etiqueta como `ingreso` una parte de las
transferencias **recibidas** de persona: el ingreso de los no asalariados llega con plantilla de P2P recibida con
probabilidad 0,6 (`src/sdg/generador.py:607-632 (no asalariados: con prob. ingreso.p_p2p_otros = 0,6 el depósito usa plantilla p2p_recibida_* y queda categoria_n1 = ingreso; consignación a billetera -> p2p_recibida_billetera)`; capa de texto del CTGAN: `src/sdg/texto.py:95 (ingreso_no_asalariado + canal_p2p -> p2p_recibida_*; ingreso + billetera -> p2p_recibida_billetera)`).
La taxonomía v1.1 lo anticipa: «Este cruce P2P/ingreso es un hallazgo esperable y debe cuantificarse en la tesis»
(caso límite de `ingreso`). No se cambió el generador, ni las etiquetas del test, ni los modelos.

| Fuente | Familia de texto | ingreso | transferencias_p2p | movimiento_propio | otras (propósito declarado) | total |
|---|---|---|---|---|---|---|
| protocolo (reglas) | P2P enviada | 0 | 4,577 | 0 | 6,472 | 11,049 |
| protocolo (reglas) | P2P recibida | 2,157 | 3,076 | 0 | 0 | 5,233 |
| protocolo (reglas) | recarga: entra a la billetera | 0 | 0 | 6,143 | 0 | 6,143 |
| protocolo (reglas) | recarga: sale del banco | 0 | 0 | 6,143 | 0 | 6,143 |
| protocolo (CTGAN) | P2P enviada | 2 | 4,171 | 49 | 12,069 | 16,291 |
| protocolo (CTGAN) | P2P recibida | 2,461 | 3,264 | 100 | 15 | 5,840 |
| protocolo (CTGAN) | recarga: entra a la billetera | 17 | 8 | 7,702 | 15 | 7,742 |
| protocolo (CTGAN) | recarga: sale del banco | 0 | 39 | 3,676 | 251 | 3,966 |

Segundo canal del mismo choque: las P2P **enviadas** con propósito declarado se etiquetan con la categoría del
propósito (R2 con `canal_p2p` = true; columna «otras»), así que en el entrenamiento el texto «… A PERSONA» aparece
también bajo categorías de bienes, mientras en el test ese texto es siempre `transferencias_p2p`.

P2P recibida etiquetada `ingreso`: protocolo (reglas) 41.2%, protocolo (CTGAN) 42.1%.
**Errores hacia `movimiento_propio`:** en el sintético, las salidas desde banco que nombran NEQUI/DAVIPLATA son casi
siempre recargas propias (protocolo (reglas): 6,143 de 6,143 son `movimiento_propio` (100.0%); protocolo (CTGAN): 3,666 de 3,956 son `movimiento_propio` (92.7%)), porque la única plantilla que
produce ese texto es la de recarga (`TRANSFERENCIA A {W}`, `RECARGA {W}`); los envíos P2P desde banco usan
«TRANSFERENCIA A PERSONA». Un envío real desde un banco a la billetera de un tercero se parece así a una recarga.
Menor: el anonimizador de WP4 deja el token `LLAVE` (pagos Bre-B) y en el sintético «LLAVE» solo aparece dentro de
«TULLAVE» (transporte) (protocolo (reglas): 8,097 filas, protocolo (CTGAN): 7,728 filas).
Fuente: `outputs/tstr/hallazgo_cruce_p2p_ingreso.json`.

---

## Exploratorio (post hoc, no pre-registrado)

POST HOC, NO PRE-REGISTRADO: solo dimensiona el choque de convenciones P2P/ingreso; no reemplaza la métrica principal ni entra a la tabla principal. `transferencias_p2p` e `ingreso` se fusionan en una sola clase en la etiqueta real y en la predicha; la
regla de soporte se fija sobre el test con la clase fusionada. Fuente: `outputs/tstr/tstr/exploratorio_p2p_ingreso.json`.

| Brazo | Fuente train | F1-macro principal | F1-macro con P2P+ingreso fusionadas | IC95 fila estrat. | IC95 por grupo | clases evaluadas |
|---|---|---|---|---|---|---|
| LogReg completo | protocolo (reglas) | 0.566 | 0.617 | [0.559, 0.670] | [0.556, 0.650] | 10 |
| LogReg completo | protocolo (CTGAN) | 0.567 | 0.596 | [0.537, 0.650] | [0.497, 0.639] | 10 |

---

## Trazabilidad: qué archivo respalda cada número

| Número | Archivo (agregado, en `outputs/`) | Campo |
|---|---|---|
| F1-macro, IC95 fila y grupo, exactitud, exactitud ponderada, n | `outputs/tstr/tstr/<fuente>/<brazo>/metricas.json` | `f1_macro_regla_soporte`, `ic95_bootstrap`, `ic95_conglomerado`, `accuracy`, `exactitud_ponderada` |
| IC básico, BCa, media/sesgo; IC anterior | ídem | `ic_sensibilidad`, `ic95_regla_recalculada_por_replica` |
| Sensibilidades (a)–(e) | ídem | `sensibilidades` |
| Clases fusionadas a `otros` | ídem | `clases_fusionadas_a_otros` |
| F1/precisión/recall por clase y soporte | `outputs/tstr/tstr/<fuente>/<brazo>/por_clase.csv` | — |
| Errores entre clases (agregados) | `outputs/tstr/tstr/<fuente>/<brazo>/matriz_confusion.csv` | — |
| Soporte original de las clases fusionadas; pesos por clase | `outputs/tstr/tstr/<fuente>/<brazo>/prevalencias.csv` | `n`, `pct_ponderado` |
| Δ de la ablación y sus IC | `outputs/tstr/tstr/ablacion.json` | `delta_f1_macro`, `ic95_fila_estratificado`, `ic95_grupo` |
| Líneas base | `outputs/tstr/tstr/<fuente>/base_mayoritaria|base_estratificada/metricas.json` | ídem |
| Cruce P2P/ingreso en el sintético | `outputs/tstr/hallazgo_cruce_p2p_ingreso.json` | `fuentes.<fuente>.por_familia` |
| Exploratorio P2P+ingreso fusionadas | `outputs/tstr/tstr/exploratorio_p2p_ingreso.json` | `resultados` |
| Tablas LaTeX | `outputs/tstr/tablas_informe.tex` | — |

`<brazo>` ∈ {`logreg`, `logreg_n20000`, `beto`}; `<fuente>` ∈ {`reglas`, `ctgan`}.

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
| tstr | ctgan | base_estratificada | 122,211 | 0 |  |
| tstr | ctgan | base_mayoritaria | 122,211 | 0 |  |
| tstr | ctgan | beto | 20,000 | 5 | BETO CPU 4 hilos: 20,000 filas x 3 épocas = 3,750 pasos, 1.27 s/paso, 1.33 h de entrenamiento (entrenado aparte con --solo-entrenar) |
| tstr | ctgan | logreg | 122,211 | 17 |  |
| tstr | ctgan | logreg_n20000 | 20,000 | 2 |  |
| tstr | reglas | base_estratificada | 122,211 | 0 |  |
| tstr | reglas | base_mayoritaria | 122,211 | 0 |  |
| tstr | reglas | beto | 20,000 | 8 | BETO CPU 4 hilos: 20,000 filas x 3 épocas = 3,750 pasos, 1.47 s/paso, 1.53 h de entrenamiento (entrenado aparte con --solo-entrenar) |
| tstr | reglas | logreg | 122,211 | 17 |  |
| tstr | reglas | logreg_n20000 | 20,000 | 2 |  |

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
