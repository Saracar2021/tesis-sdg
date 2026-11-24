# Resultados TSTR — WP8

> **PROVISIONAL.** Archivo regenerado por `tools/etapa4_tstr.py`; no editar a mano.
> Última regeneración: 2026-11-24T02:54:39+00:00.
> Taxonomía 1.1.0, target `categoria_n1`, semilla 42.

**Taxonomía.** La v1.1.0 no cambió las 16 categorías ni las reglas R1–R7, solo documentación y metadatos
de anotación (T1–T6, §9 de `taxonomia_gastos_colombia_v1.md`); el CTGAN entrenado con el JSON v1.0.0 sigue
siendo válido para el TSTR y no se regenera.

**Texto (D14).** Ambas fuentes reciben la `descripcion` de la misma capa de texto (`src/sdg/texto.py`,
`tools/etapa3b_texto.py`): mismas plantillas, comercios y semilla, ninguna calibrada con el real de WP4.

**Swap a WP4.** El TSTR se activa con una sola ruta (`--test data/reales_anon/<real>.csv`). Esquema esperado:
`descripcion, monto, fecha, signo, cuenta_tipo, categoria_n1, fuente_etiqueta, voluntario_id`. Verificado de punta a punta con un real simulado de 30 filas
(`tests/fixtures/real_simulado_wp4.csv`, `tests/test_swap_wp4.py`).

## Tabla TSTR (único resultado reportable)

Entrenamiento sobre **todo** el sintético; evaluación sobre el conjunto **real anotado de WP4**.
F1-macro con regla de soporte: clases con < 10 ejemplos en el test real se recodifican a
`otros` (en etiqueta real y predicha) antes del promedio. IC95 por bootstrap (1000 réplicas),
por conglomerado (voluntario) cuando el test trae esa columna. «Solo etiqueta-por-texto» excluye las filas con
`fuente_etiqueta = declaracion_voluntario` (pagos a persona con propósito declarado, regla R2): su categoría no
está en el texto del extracto, así que acotan por diseño a cualquier clasificador de texto.

| Brazo | Fuente train | F1-macro (soporte ≥10) | IC95 | F1-macro solo etiqueta-por-texto | IC95 | n train | n test | fusionadas a otros |
|---|---|---|---|---|---|---|---|---|
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (reglas) | pendiente WP4 | | | | | | |
| Baseline: LogReg + TF-IDF char 3-5 (train completo) | protocolo (CTGAN) | pendiente WP4 | | | | | | |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (reglas) | pendiente WP4 | | | | | | |
| Baseline: LogReg @20k (mismas filas que BETO) | protocolo (CTGAN) | pendiente WP4 | | | | | | |
| BETO fine-tuning | protocolo (reglas) | pendiente WP4 | | | | | | |
| BETO fine-tuning | protocolo (CTGAN) | pendiente WP4 | | | | | | |
| LLM vía Groq, prompting few-shot (modelo y desviación en Costo) | protocolo (reglas) | pendiente WP4 | | | | | | |
| LLM vía Groq, prompting few-shot (modelo y desviación en Costo) | protocolo (CTGAN) | pendiente WP4 | | | | | | |

**Asimetría de tamaño (declarada).** BETO entrena sobre una submuestra estratificada de 20,000 filas por
costo de CPU. La comparación de igual a igual es LogReg @20k frente a BETO @20k
(mismas filas, misma semilla); LogReg con el train completo es la mejor cifra del baseline, no un rival de BETO en
igualdad de datos. El brazo LLM no entrena: el sintético solo entra por los ejemplos few-shot.

**Pipeline de Pancholi et al.: contexto, no fila de la tabla.** WP5 concluyó la rama (a), *no mapeable* (`outputs/pancholi/wp8_mapeabilidad.json`): su generador alcanza 8 de las 16 `categoria_n1` (6 sin las rutas marginales de peso 0,01), así que un clasificador entrenado con su salida tendría un techo de F1-macro de 0.500 (0.375 sin marginales) aun acertando todo lo que puede predecir. **Hallazgo de no transferibilidad:** solo emite compras; no produce `telecom_conectividad`, `salud`, `hogar_articulos`, `obligaciones_financieras`, `transferencias_p2p`, `retiro_efectivo`, `movimiento_propio`, `ingreso`, que suman el 42% de las filas del sintético del protocolo. Tampoco produce la entrada de WP8: no modela `cuenta_tipo`, su signo es constante y su monto está en USD de Washington D.C. Por eso no se entrena sobre su salida ni se pone en esta tabla. Como contexto, su F1 publicado (regresión logística: accuracy ≈ 71 %, F1-macro 0,57; BERT afinado: accuracy ≈ 71 %, F1-macro 0,62; LSTM: accuracy < 40 %; LLaMA-3 vía API: sin métricas estándar (revisión manual de 100 transacciones)) se mide sobre un hold-out de sus propios datos sintéticos de D.C., con otras categorías y en inglés: no es comparable con el TSTR del protocolo.

### Ablación reglas → CTGAN (Δ = CTGAN − reglas, bootstrap pareado sobre el mismo test)

| Brazo | Δ F1-macro | IC95 | Δ solo etiqueta-por-texto | IC95 |
|---|---|---|---|---|
| — | pendiente WP4 | | | |

**Entrada (idéntica en los tres brazos).** `[CUENTA=<cuenta_tipo>] [SIGNO=<signo>] [MONTO=<bin_log>] <descripcion>`; `monto` en bins log10 de media década, en
pesos de promedio 2025 (el sintético ya lo está; el real de WP4 se deflacta con el IPC total nacional del mes si trae
`fecha`). Son observables del extracto, no anotaciones. Indicio del sanity (no reportable): frente a solo
`descripcion`, el F1-macro del baseline sube poco y la ganancia está en `transferencias_p2p` e `ingreso` (el signo, la
cuenta y el monto separan P2P recibida de ingreso y P2P sin propósito de pagos con propósito); `retiro_efectivo` y
`movimiento_propio` ya estaban en el techo solo con texto. Las ambigüedades de categoría por texto no se resuelven, y
en las filas etiquetadas por declaración el monto mueve errores hacia clases raras (en el sanity, `educacion` cae).
El techo por diseño de esas filas sigue intacto; el efecto real se mide solo sobre el test de WP4.

**Brazo LLM.** El sintético entra solo por los ejemplos few-shot (3 por clase difícil): su Δ CTGAN − reglas mide el
efecto de la fuente de esos ejemplos, no de un entrenamiento, y se espera cerca de cero. Groq retiró
`llama-3.3-70b-versatile` de las cuentas free/developer el 16-ago-2026: el modelo usado y la desviación quedan en la
tabla de costo y en `metricas.json`.

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
| sanity | ctgan | logreg | 97,768 | 50 |  |
| sanity | ctgan | logreg_n20000 | 20,000 | 12 |  |
| sanity | reglas | beto | 2,000 | 2,830 | BETO CPU 4 hilos: 2,000 filas x 3 épocas = 375 pasos, 2.02 s/paso, 0.21 h de entrenamiento |
| sanity | reglas | logreg | 97,768 | 34 |  |
| sanity | reglas | logreg_n20000 | 20,000 | 11 |  |

---

## Sanity check — NO REPORTABLE

Holdout 80/20 estratificado por `categoria_n1` **dentro de cada sintético**. Mide ajuste interno del
clasificador al generador, no transferencia a datos reales. No es TSTR, no va al informe como resultado y
no admite Δ pareado (cada fuente tiene su propio holdout). `reglas_original` = texto original del generador
por reglas (diagnóstico de la capa de texto factorizada).

| Brazo | Fuente train | F1-macro (soporte ≥10) | IC95 | F1-macro solo etiqueta-por-texto | IC95 | n train | n test | fusionadas a otros |
|---|---|---|---|---|---|---|---|---|
| beto | ctgan | 0.566 | [0.560, 0.572] | 0.593 | [0.586, 0.600] | 2,000 | 24,443 | — |
| logreg | ctgan | 0.866 | [0.859, 0.873] | 0.909 | [0.902, 0.916] | 97,768 | 24,443 | — |
| logreg_n20000 | ctgan | 0.864 | [0.857, 0.871] | 0.907 | [0.899, 0.914] | 20,000 | 24,443 | — |
| beto | reglas | 0.616 | [0.607, 0.624] | 0.647 | [0.638, 0.656] | 2,000 | 24,443 | — |
| logreg | reglas | 0.889 | [0.878, 0.898] | 0.941 | [0.931, 0.948] | 97,768 | 24,443 | — |
| logreg_n20000 | reglas | 0.860 | [0.850, 0.869] | 0.936 | [0.927, 0.945] | 20,000 | 24,443 | — |
