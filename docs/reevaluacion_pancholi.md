# Reevaluación del pipeline de referencia (Pancholi et al.)

<!-- WP8:inicio -->

## 0. Resumen WP5 → WP8 (actualización del 23 nov 2026)

**Veredicto para WP8: comparación tipo (a).** La salida del pipeline de referencia **no es** mapeable a las 16 `categoria_n1` de la taxonomía v1.1.0: su generador alcanza 8 de 16 (6 sin las rutas marginales). Pancholi entra a WP8 solo como contexto: su F1 reportado se cita, no se compara. No se genera `outputs/pancholi/baseline_sintetico.csv.gz`.

### 0.1 Según diseño → según ejecución

«Diseño» = lo que dice su código (lectura). «Ejecución» = lo medido corriendo su código con el commit fijado (etapas 1–3: 10 semillas, criterios prerregistrados; §1–§3). Conjunto principal: réplica literal, etapa 3.

| Hipótesis | Según diseño | Según ejecución (etapas 1–3) | Etapa 4 (LLM) |
|---|---|---|---|
| H-P1 ingreso | Etapa 2: monto ∝ ingreso (elasticidad 1 por construcción). Etapa 3: el ingreso no es columna del CTGAN. Etapa 4: el ingreso entra al prompt como rango esperado | Etapa 2: 1,008 [1,007; 1,009]. Salida final (etapa 3): -0,003 [-0,008; 0,002]: **no conserva** la relación. Frente a Colombia: **no concluyente (sin referente colombiano en este entorno)** | elasticidad entre clientes 0,794 [0,598; 1,095], n = 25 clientes, una corrida: **sensible al ingreso**. Mecanismo: su prompt le da al LLM un «Expected spending range» proporcional al ingreso |
| H-P2 categorías | 7 etiquetas (etapa 2) y 39 subcategorías (etapa 4) en las mismas 6 familias de comercio de D.C. | Entretenimiento 13,0 % [13,0; 13,0] vs. alimentos 14,8 % [14,8; 14,9]: dominio de ocio **refutada** (**confirmada** si el hospedaje cuenta como ocio); 6 de 16 categorías con registros | 8 categoria_n1 (la cota del código). Entretenimiento 17,3 % [13,5; 22,0] vs. alimentos 24,0 % [19,5; 29,1]: **no concluyente**; con hospedaje 31,7 % [26,7; 37,1]: **no concluyente**. El LLM respeta la subcategoría pedida en el 99,7 % |
| H-P3 medio de pago | Etapas 1–3: sin campo. Etapa 4: `payment_type` en texto libre («Appropriate payment method»); un registro = una compra | Sin columna de medio de pago; 0 de 5.000.000 registros de retiro/P2P/movimiento propio/ingreso: **confirmada para las etapas 1–3** | `tarjeta_credito` 89,0 % [85,0; 92,1]; `tarjeta_debito` 11,0 % [7,9; 15,0] (6 grafías de 2 medios). Efectivo, billetera y transferencia: 0 de 300 (cota superior 1,3 %). Registros de extracto: 0. **Domina la tarjeta, pero no es 100 % `credit_card`** |

### 0.2 Etapa 4 (LLM): estado de la ejecución

- **Ejecutada** con `openai/gpt-oss-120b` — **desviación:** llama-3.3-70b-versatile no disponible para esta cuenta; sustituido por openai/gpt-oss-120b. 300 llamadas, 0 fallidas (0,0 %), 300 registros, 82,7 min, 85.658 tokens de entrada y 42.016 de salida. Parámetros y SHA-256 en `outputs/pancholi/etapa4/manifest_etapa4.json`; respuestas crudas en `llamadas.jsonl`.
- Semilla 42, pausa 10 s, temperatura 0,5, 25 clientes, pandas 2.2.3 (la versión que fija su repo). Las peticiones son idénticas entre corridas con la misma semilla; las respuestas del LLM no, y por eso el análisis parte de los registros guardados. El 11,7 % de los registros usa su comercio genérico de respaldo («DC … Service»). Costo: se reportan tokens; no se fijó precio por token.
- **Limitaciones de esta corrida:** un solo modelo, distinto del de su código; una sola corrida, sin IC entre corridas del LLM; 25 clientes. Verifica cómo se comporta la etapa 4, no estima su variabilidad.
- **La ejecución confirma la cota de diseño:** la etapa 4 emitió exactamente las categoria_n1 que su código puede sortear; el LLM no creó ninguna. El veredicto de §0.3 no cambia.

### 0.3 Criterio único para WP8: ¿es mapeable a las 16 `categoria_n1`?

**Regla:** mapeable ⇔ las 16 categoria_n1 alcanzables desde etiquetas con peso > 0 (etapas 2 y 4). Mapeos versionados: `docs/taxonomia/mapeo_pancholi_taxonomia_v1.csv` (etapa 2) y `docs/taxonomia/mapeo_pancholi_etapa4_taxonomia_v1.csv` (etapa 4), con prueba en `tests/`. Para no sesgar hacia (a), los mapeos son **generosos**: `driving_lessons` → `educacion` y `boarding_house` → `vivienda_servicios.arriendo` se aceptan aunque pesen 0,01 en su código. Cálculo: `tools/mapeabilidad_pancholi.py` → `outputs/pancholi/wp8_mapeabilidad.json`.

| categoria_n1 | ¿Alcanzable? | Etiquetas de Pancholi que llegan | Peso en su código (etapa 4) | Filas en el sintético del protocolo |
|---|---|---|---|---|
| alimentos_mercado | sí | etapa2:groceries; etapa4:groceries; etapa4:bakery; etapa4:packaged_foods; etapa4:seafood_market | 0,20 | 20,2 % |
| comidas_fuera | sí | etapa2:dining; etapa4:deli_prepared_foods; etapa4:vending_snacks; etapa4:ice_cream; etapa4:food_truck; etapa4:restaurant_dining; etapa4:catering_services | 0,18 | 14,5 % |
| transporte | sí | etapa2:transportation; etapa4:gas_station; etapa4:car_rental; etapa4:car_wash | 0,07 | 12,9 % |
| vivienda_servicios | sí | etapa4:boarding_house | 0,01 | 4,8 % |
| telecom_conectividad | **no** | — | 0,00 | 3,3 % |
| salud | **no** | — | 0,00 | 0,5 % |
| educacion | sí | etapa4:driving_lessons | 0,01 | 0,4 % |
| entretenimiento | sí | etapa2:entertainment; etapa4:movie_theater; etapa4:event_venue; etapa4:live_theater; etapa4:bowling; etapa4:pool_hall; etapa4:skating_rink; etapa4:sports_events; etapa4:special_events | 0,13 | 0,8 % |
| vestuario_cuidado_personal | sí | etapa2:personal_care; etapa4:beauty_services; etapa4:barber_services; etapa4:skin_care; etapa4:nail_salon; etapa4:spa_services; etapa4:massage_parlor | 0,10 | 4,1 % |
| hogar_articulos | **no** | — | 0,00 | 1,4 % |
| obligaciones_financieras | **no** | — | 0,00 | 0,8 % |
| transferencias_p2p | **no** | — | 0,00 | 6,3 % |
| retiro_efectivo | **no** | — | 0,00 | 15,6 % |
| movimiento_propio | **no** | — | 0,00 | 9,8 % |
| ingreso | **no** | — | 0,00 | 4,4 % |
| otros | sí | etapa2:housing; etapa2:other; etapa4:hotel_lodging; etapa4:motel_lodging; etapa4:bnb_lodging; etapa4:vacation_rental | 0,09 | 0,2 % |

- **Resultado:** 8 de 16 alcanzables → **NO mapeable**. No alcanzables: `telecom_conectividad`, `salud`, `hogar_articulos`, `obligaciones_financieras`, `transferencias_p2p`, `retiro_efectivo`, `movimiento_propio`, `ingreso`. La sensibilidad con las clases de soporte ≥ 10 da el mismo resultado (no mapeable).
- **Techo de F1-macro** de un clasificador entrenado con su salida y evaluado en las 16 clases: 0,500 (0,375 sin las rutas marginales), aun si acertara todo lo que puede predecir: una clase que nunca predice tiene F1 = 0.
- **Masa afectada:** en el sintético del protocolo (`outputs/ctgan/sintetico_v1.csv.gz`), el 42,1 % de las filas cae en clases que Pancholi no puede emitir (47,4 % sin las rutas marginales). Es una aproximación: la composición real del conjunto anotado (WP4) la reemplaza cuando exista.
- **Contexto colombiano** (descriptivo, no cambia la regla): de las 13 columnas del esquema de `sintetico_v1`, 3 salen directas de su salida, 3 son constantes (solo compras), 3 no existen (`cuenta_tipo`, `medio_pago` en las etapas 1–3, `formalidad_comercio`), 2 son parciales (`categoria_n1`, `categoria_n2`) y `monto` e `ingreso_mensual` exigirían inventar una conversión de USD de D.C. a COP de Bogotá.

**Implicación para WP8 y riesgos.**
1. **Comparación tipo (a).** El TSTR se reporta para el protocolo; Pancholi se cita con su F1 publicado como contexto, sin compararlo. La no transferibilidad es un hallazgo que justifica el protocolo, no un hueco.
2. **Inconsistencia con el borrador.** `docs/reporte/borrador_reporte.md` (método, «Comparación con el pipeline de referencia», y resultados, «F1-macro TSTR del protocolo adaptado vs. el pipeline de referencia») promete la comparación (b): entrenar sobre su salida y evaluar en Bogotá. Hay que reescribir ambos pasajes en términos de (a).
3. **Alternativa descartada:** un (b) restringido a las clases compartidas. Cambiaría la tarea (otro espacio de etiquetas y otra métrica) y ya no mediría lo mismo que el TSTR del protocolo. Se puede mencionar como trabajo futuro, no como resultado.
4. **El techo de F1 es una cota, no una medición.** El valor real sería menor, porque además las descripciones de texto de su salida son nombres de comercios de D.C. en inglés.

<!-- WP8:fin -->

> Documento generado por `tools/informe_pancholi.py` a partir de `outputs/pancholi/`. No editar las cifras a mano: se regeneran con `python tools/analisis_pancholi.py && python tools/informe_pancholi.py`.

## 1. Qué se corrió y cómo

- **Código:** https://github.com/aman-jaglan/Capstone_Project.git · commit `d0a61e783353f52123b1821bc1876824d608d2a1` · árbol del clon limpio: sí. El clon vive en `external/pancholi/` (ignorado por git); en el repositorio quedan solo la URL y el hash. **Licencia:** MIT (Copyright (c) 2025 Aman Jaglan): permite uso académico, modificación y redistribución conservando el aviso de copyright.
- **Entorno:** `.venv-pancholi`, Python 3.11.15, Linux-6.18.44-fc-v37-x86_64-with-glibc2.39, CPU (2 hilos de torch), CUDA: no. Versiones fijadas por el propio repo (`src/Data_Synthesizer/requirements.txt`); la lista completa está en `manifest.json`. Se ejecutó en un entorno aislado en la nube, **sin ningún dato del equipo de la autora**.
- **Etapas ejecutadas:** 1 (demografía), 2 (reglas) y 3 (CTGAN), llamando a sus clases desde `tools/pancholi_ejecutar.py` sin editar su código. **No ejecutadas:** 4 (enriquecimiento con LLM) y 5 (bucle híbrido): requieren la API de Groq, bloqueada desde el entorno de ejecución (HTTP 403 en el proxy); la etapa 5 además falla por código (§2).
- **Parche P1** (`tools/pancholi_parches/`): con `sdv==1.19.0`, que el propio repo fija, `src/component/transaction.py` no importa (`SingleTableMetadata` vive en `sdv.metadata.single_table`). Se reasigna el mismo objeto de clase en memoria antes de importar; no cambia ninguna lógica.
- **Criterios prerregistrados** en `docs/prerregistro_wp5.md` antes de la primera corrida (SHA-256 `82dae53ba89e381a…`, sello en `outputs/pancholi/prerregistro_sello.json`).

| Diseño | Qué es | Semillas | Parámetros |
|---|---|---|---|
| A | Rejilla de ingreso, etapas 2 y 3 | 10 (42–51) | 12 niveles log-espaciados de 5.000 a 310.975 USD/año (mínimo y máximo del ingreso de su etapa 1); 13 clientes/nivel para entrenar, 30 tx/cliente, CTGAN 100 épocas, 60.000 muestras; evaluación de la etapa 2 con 167 clientes/nivel; hogar de 2 personas, ZIP 20001 |
| B | Réplica literal de `transaction_synthesizer.py` | 10 | sus 155 clientes (`synthetic_customers_deepseek.csv`), 30 tx/cliente, 100 épocas, 500.000 muestras |
| C | Etapa 1 reentrenada (`AdvancedIncomeModel`) + etapas 2 y 3 sobre 155 de sus clientes | 1 (42) | 100 épocas en ambas CTGAN; 100.000 hogares como en `customer_synthesizer.py` |

**Reproducibilidad.** La semilla 42 del diseño A se corrió dos veces: contenido idéntico en 3 de 3 archivos (comparando sin `timestamp`, que su código toma de `datetime.now()`). SDV fija su propia semilla de muestreo (73251); la variación entre semillas viene de la simulación por reglas y del entrenamiento del CTGAN. **Tiempo total de cómputo:** 3,8 h; CTGAN ≈ 7,2 min por ajuste (mediana).

## 2. Lo que dice el código (inferido por lectura, no resultado de ejecución)

- **Etapa 2** (`src/component/transaction.py`, `generate_spending_pattern` y `simulate_transactions`): monto = ingreso/12 × fracción fija por categoría × U(0,05; 0,30); la categoría de cada transacción se sortea uniformemente (`random.choice`) entre 7. Las fracciones solo cambian con el ingreso en un escalón (+0,03 a `dining` si ingreso > 75.000) y con el hogar (+0,02 a `groceries` si > 2 personas).
- **Etapa 3** (`TransactionCTGAN.fit`): el CTGAN se entrena con `customer_id, zipcode, category, merchant_name, mapped_category, transaction_amount`; **el ingreso no es columna del entrenamiento**. El vínculo con el ingreso solo puede sobrevivir vía `customer_id`.
- **Etapa 1**: el paper la llama «Bayesian demographic modeling», pero el código es un CTGAN (`AdvancedIncomeModel`) o un muestreo por tramos (`ABMGlobalModel`); `arviz` se importa y no se usa. Las transacciones que el repo publica (`synthetic_transactions_ctgan.csv`) salen de 155 clientes generados por un LLM (`synthetic_customers_deepseek.csv`), no de la etapa 1.
- **Etapa 4** (`transaction_deepseek_synthesizer.py`): una llamada a Groq (`llama-3.3-70b-versatile`, temperatura 0,5) por transacción; el esquema de salida tiene un solo registro de compra con `payment_type` libre («Appropriate payment method»). **Etapa 5** (`hybridgenerator.py`): pasa a la etapa 4 un cliente sin `age`, `gender` ni `household_size` (KeyError en el prompt, capturado → salida vacía), fija el ingreso en 75.000 y su «fraud_score» de validación es `random.random()`.
- **Aplicación web** (`transaction_synthesizer_groq.py`, no es el pipeline del paper): descarta montos fuera de USD 10–200, no pasa el ingreso al LLM, pone `"payment_type": "credit_card"` como ejemplo literal del prompt (temperatura 0,1) y sortea casi uniformemente entre 39 subcategorías, en su mayoría de ocio. **Las cifras retiradas del informe de avance (5 perfiles, 149 tx, USD 12, categorías de ocio, 100 % `credit_card`) son compatibles con este programa y no con el pipeline del paper** (inferencia: no se pudo ejecutar, requiere Groq).
- **Verificado al ejecutar:** el emparejamiento de comercio por ZIP no actúa. El 11,9 % de los registros de la etapa 2 cae en comercios del ZIP del cliente, frente a una tasa base de 10,9 % en el archivo de comercios (`diag_zip_comercios.csv`). Causa probable (por lectura de código): el ZIP del cliente se convierte a texto como `20001.0` y el del comercio como `'20001'`, así que nunca coinciden.

## 3. Resultados por hipótesis

### H-P1 — relación ingreso–gasto

| Conjunto | Elasticidad monto–ingreso (media entre semillas) | IC 95 % bootstrap entre semillas | Rango entre semillas | ¿Sensible al ingreso? |
|---|---|---|---|---|
| A · etapa 2 (reglas) | 1,008 | [1,007; 1,009] | [1,005; 1,011] | sí (n = 10) |
| A · etapa 3 (CTGAN) | 0,000 | [-0,003; 0,004] | [-0,012; 0,009] | no (n = 10) |
| B · etapa 2 (reglas) | 1,029 | [1,019; 1,040] | [1,006; 1,058] | sí (n = 10) |
| B · etapa 3 (CTGAN) | -0,003 | [-0,008; 0,002] | [-0,017; 0,009] | no (n = 10) |
| C · etapas 1→2→3 (CTGAN final) | 0,014 | no calculable (1 semilla) | — | no evaluable (n = 1) |

En la rejilla (A), el monto medio por transacción pasa de 10,44 a 664,09 USD entre el nivel más bajo y el más alto en la **etapa 2**, y de 173,70 a 174,63 USD en la **etapa 3** (entre niveles, el monto medio de la etapa 3 oscila entre 170,32 y 175,95 USD; detalle con IC en `hp1_monto_por_nivel.csv`).

| Conjunto | Pendiente de la participación de alimentos_mercado en el monto (pp por unidad de log ingreso) | IC 95 % |
|---|---|---|
| A · etapa 2 (reglas) | -0,25 | [-0,34; -0,16] |
| A · etapa 3 (CTGAN) | -0,16 | [-0,35; 0,01] |
| B · etapa 2 (reglas) | -0,47 | [-1,35; 0,76] |
| B · etapa 3 (CTGAN) | -0,25 | [-0,91; 0,31] |
| C · etapas 1→2→3 (CTGAN final) | 1,50 | no calculable (1 semilla) |

**Lectura.** La etapa 2 hace lo que su código dice: el monto escala con el ingreso (elasticidad ≈ 1) y las participaciones por categoría casi no se mueven con él. La etapa 3, que es la salida final del pipeline, **no conserva la relación**: el CTGAN aprende la distribución marginal del monto y la reparte entre clientes sin importar su ingreso. Esto no es lo mismo que la afirmación retirada del informe: el mecanismo es el entrenamiento del CTGAN sin la columna de ingreso, no las reglas, y la cifra sale de 10 semillas con IC.

Diseño C, etapa 1 reentrenada: mediana del ingreso generado 108.624 USD frente a 106.914 en el archivo del repo (`hp1_disenoC_etapa1.csv`).

**Veredicto H-P1: NO CONCLUYENTE (SIN REFERENTE COLOMBIANO EN ESTE ENTORNO).** La hipótesis compara con los hogares colombianos, y el referente (participación de alimentos por quintil de `ICGU`, ENPH Bogotá, `FEX_C`, a nivel hogar) no se calculó aquí porque este entorno no recibe microdatos. Queda lista la comparación: `python tools/analisis_pancholi.py --enph <csv>` aplica la regla prerregistrada. **Hallazgo que sí queda firme:** la salida final del pipeline no varía con el ingreso del cliente.

### H-P2 — categorías

Mapeo a la taxonomía v1: `docs/taxonomia/mapeo_pancholi_taxonomia_v1.csv`, con su prueba en `tests/test_mapeo_pancholi.py`. Decisión declarada: `housing` son hoteles, moteles y alquiler vacacional (hospedaje, COICOP 11.2), no vivienda; v1 no tiene categoría de hospedaje y se asigna a `otros`.

| Categoría v1 (por `category`) | A · etapa 2 (reglas) | A · etapa 3 (CTGAN) | B · etapa 2 (reglas) | B · etapa 3 (CTGAN) | C · etapas 1→2→3 (CTGAN final) |
|---|---|---|---|---|---|
| alimentos_mercado | 14,3 % [14,2 %; 14,4 %] | 17,7 % [17,6 %; 17,8 %] | 14,4 % [14,1 %; 14,7 %] | 14,8 % [14,8 %; 14,9 %] | 11,0 % [10,7 %; 11,2 %] |
| comidas_fuera | 14,3 % [14,3 %; 14,4 %] | 14,5 % [14,4 %; 14,6 %] | 14,2 % [13,9 %; 14,5 %] | 14,9 % [14,9 %; 15,0 %] | 21,3 % [21,0 %; 21,6 %] |
| transporte | 14,3 % [14,2 %; 14,4 %] | 11,3 % [11,3 %; 11,4 %] | 14,1 % [13,8 %; 14,4 %] | 13,8 % [13,8 %; 13,9 %] | 12,6 % [12,3 %; 12,9 %] |
| entretenimiento | 14,3 % [14,2 %; 14,4 %] | 14,6 % [14,6 %; 14,7 %] | 14,5 % [14,2 %; 14,9 %] | 13,0 % [13,0 %; 13,0 %] | 17,9 % [17,6 %; 18,2 %] |
| vestuario_cuidado_personal | 14,3 % [14,2 %; 14,4 %] | 15,9 % [15,8 %; 16,0 %] | 14,4 % [14,0 %; 14,7 %] | 17,1 % [17,1 %; 17,1 %] | 11,4 % [11,1 %; 11,6 %] |
| otros | 28,5 % [28,3 %; 28,6 %] | 25,9 % [25,8 %; 26,0 %] | 28,4 % [28,0 %; 28,8 %] | 26,3 % [26,3 %; 26,3 %] | 25,8 % [25,5 %; 26,2 %] |
| vivienda_servicios.servicios_publicos | 0,0 % [0,0 %; 0,0 %] | 0,0 % [0,0 %; 0,0 %] | 0,0 % [0,0 %; 0,0 %] | 0,0 % [0,0 %; 0,0 %] | 0,0 % [0,0 %; 0,0 %] |

Participación por número de registros, con IC de Wilson al 95 % sobre todas las semillas. Participación por monto y la variante con `mapped_category` en `hp2_participacion_nivel1.csv`.

- **A · etapa 2 (reglas):** 6 de 16 categorías nivel 1 de v1 tienen algún registro. Ocio = entretenimiento: 14,3 % frente a 14,3 % de alimentos → **no concluyente**. Ocio con hospedaje (sensibilidad): 28,5 % → **confirmada**.
- **A · etapa 3 (CTGAN):** 6 de 16 categorías nivel 1 de v1 tienen algún registro. Ocio = entretenimiento: 14,6 % frente a 17,7 % de alimentos → **refutada**. Ocio con hospedaje (sensibilidad): 29,0 % → **confirmada**.
- **B · etapa 2 (reglas):** 6 de 16 categorías nivel 1 de v1 tienen algún registro. Ocio = entretenimiento: 14,5 % frente a 14,4 % de alimentos → **no concluyente**. Ocio con hospedaje (sensibilidad): 28,8 % → **confirmada**.
- **B · etapa 3 (CTGAN):** 6 de 16 categorías nivel 1 de v1 tienen algún registro. Ocio = entretenimiento: 13,0 % frente a 14,8 % de alimentos → **refutada**. Ocio con hospedaje (sensibilidad): 25,5 % → **confirmada**.
- **C · etapas 1→2→3 (CTGAN final):** 6 de 16 categorías nivel 1 de v1 tienen algún registro. Ocio = entretenimiento: 17,9 % frente a 11,0 % de alimentos → **no concluyente**. Ocio con hospedaje (sensibilidad): 28,4 % → **confirmada**.

Licencias que cita el informe (Athletic Exhibition, Special Events, Inn And Motel, Skating Rink), cruzando `merchant_name` con el archivo de comercios. *Estricto*: todas las licencias con ese nombre están entre las cuatro. *Laxo*: alguna lo está; nombres como «Unknown» se repiten entre licencias e inflan esta cifra.

| Conjunto | Estricto | Laxo |
|---|---|---|
| A · etapa 2 (reglas) | 2,51 % [2,47 %; 2,55 %] | 4,53 % |
| A · etapa 3 (CTGAN) | 2,05 % [2,02 %; 2,09 %] | 3,57 % |
| B · etapa 2 (reglas) | 2,61 % [2,47 %; 2,76 %] | 4,57 % |
| B · etapa 3 (CTGAN) | 1,82 % [1,81 %; 1,83 %] | 3,31 % |
| C · etapas 1→2→3 (CTGAN final) | 1,88 % [1,77 %; 1,99 %] | 3,69 % |

3 de las cuatro licencias no están en el `CATEGORY_MAPPING` de la etapa 2, así que esa etapa no puede asignarlas; por licencia en `hp2_licencias_informe.csv`.

**Veredicto H-P2 (conjunto principal B · etapa 3 (CTGAN)): dominio de ocio REFUTADA con la definición prerregistrada; CONFIRMADA si el hospedaje se cuenta como ocio.** El veredicto depende de cómo se clasifiquen los hoteles; se declaran ambos. El prerregistro no fijó qué conjunto es el principal: se fijó en el código de análisis (la réplica literal, B · etapa 3) antes de que corriera el diseño B, y el veredicto coincide con el de A · etapa 3. Lo que no depende de esa decisión es la **cobertura**: servicios públicos, arriendo, transporte público, salud, educación, telecomunicaciones, obligaciones financieras y todas las categorías operativas de extracto tienen participación cero por construcción.

### H-P3 — medio de pago y registros de extracto (D15)

- **A · etapa 2 (reglas):** columnas de salida `customer_id, zipcode, category, merchant_name, mapped_category, transaction_amount, timestamp`; columnas de medio de pago: (ninguna). Registros de retiro, transferencia P2P, movimiento propio o ingreso: 0 de 601.200 (cota superior de Wilson 0,0006 %).
- **A · etapa 3 (CTGAN):** columnas de salida `customer_id, zipcode, category, merchant_name, mapped_category, transaction_amount, timestamp`; columnas de medio de pago: (ninguna). Registros de retiro, transferencia P2P, movimiento propio o ingreso: 0 de 600.000 (cota superior de Wilson 0,0006 %).
- **B · etapa 2 (reglas):** columnas de salida `customer_id, zipcode, category, merchant_name, mapped_category, transaction_amount, timestamp`; columnas de medio de pago: (ninguna). Registros de retiro, transferencia P2P, movimiento propio o ingreso: 0 de 46.500 (cota superior de Wilson 0,0083 %).
- **B · etapa 3 (CTGAN):** columnas de salida `customer_id, zipcode, category, merchant_name, mapped_category, transaction_amount, timestamp`; columnas de medio de pago: (ninguna). Registros de retiro, transferencia P2P, movimiento propio o ingreso: 0 de 5.000.000 (cota superior de Wilson 0,0001 %).
- **C · etapas 1→2→3 (CTGAN final):** columnas de salida `customer_id, zipcode, category, merchant_name, mapped_category, transaction_amount, timestamp`; columnas de medio de pago: (ninguna). Registros de retiro, transferencia P2P, movimiento propio o ingreso: 0 de 60.000 (cota superior de Wilson 0,0064 %).

**Veredicto H-P3: CONFIRMADA para las etapas ejecutadas (1–3).** Su salida no tiene campo de medio de pago y solo emite compras: no hay retiros, transferencias, billeteras ni efectivo como tipos de registro. **La distribución de `payment_type` de la etapa 4 es NO CONCLUYENTE**: etapa 4 no ejecutable (API de Groq bloqueada). Por lectura de código, el esquema de la etapa 4 también es de una compra por registro, así que tampoco produciría retiros ni transferencias como registros (inferido).

## 4. Limitaciones

1. **Etapas 4 y 5 sin ejecutar.** `payment_type` y la «validación» por LLM no se midieron. El paper presenta la salida final como la del bucle híbrido (etapa 5), que no corre tal cual.
2. **La rejilla (A) es un diseño propio.** Fija hogar y ZIP y recorre el ingreso para aislar su efecto. La réplica literal (B) usa sus 155 clientes, con ingresos entre 25.000 y 180.000 USD, un rango más estrecho.
3. **Montos en USD de 2024–2025 (D.C.).** La comparación con Colombia solo tiene sentido en términos sin unidades (elasticidad, participaciones), nunca en niveles.
4. **IC entre semillas con n = 10.** El bootstrap percentil con 10 semillas es aproximado; se reporta también el rango.
5. **CTGAN sin diagnóstico de convergencia.** Se usan sus 100 épocas; SDV advierte que la cardinalidad de `merchant_name` es alta. No se exploraron otras configuraciones: se evalúa su pipeline, no el mejor CTGAN posible.
6. **Entorno distinto al de los autores** (Linux, CPU, sin GPU). No se sabe si ellos usaban GPU.
7. **Referente colombiano de H-P1 pendiente.** Sin él, H-P1 no puede confirmarse ni refutarse.

## 5. Cómo reproducir

```
python3.11 -m venv .venv-pancholi && . .venv-pancholi/bin/activate
pip install -r external/pancholi/src/Data_Synthesizer/requirements.txt pytest==8.3.5
git clone https://github.com/aman-jaglan/Capstone_Project.git external/pancholi && git -C external/pancholi checkout d0a61e783353f52123b1821bc1876824d608d2a1
python tools/pancholi_ejecutar.py A R B C manifiesto   # ~3,8 h en 2 CPU
python tools/analisis_pancholi.py && python tools/informe_pancholi.py
python -m pytest -q tests/test_mapeo_pancholi.py
```
