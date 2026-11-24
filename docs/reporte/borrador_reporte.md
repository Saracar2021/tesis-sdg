# Diseño y validación preliminar de un protocolo de generación de datos sintéticos de transacciones financieras para el contexto colombiano

> **BORRADOR DE TRABAJO — 17 nov 2026.** Andamiaje para montar en la plantilla IEEE Transactions on AI. Porta la narrativa del informe de avance pero **toda cifra está reemplazada por la vigente** (`plan_maestro.md` §5, calculada sobre Bogotá con factores de expansión); las cifras retiradas del informe (§6) **no** se reutilizan. Las secciones de resultados experimentales (VII) van como **preliminares**. Texto asistido por IA — declararlo en la sección de uso de IA. La autora revisa y aprueba cada sección; ninguna cifra se escribe a mano: sale de `outputs/`.
>
> Marcadores: `[CIFRA→outputs/...]` número por verificar/citar del repo · `[PRELIMINAR]` pendiente de WP7/WP8 · `[DECISIÓN]` requiere confirmación de la autora.

---

## Abstract

El acceso a datos transaccionales financieros en Colombia es prácticamente inexistente en el dominio público: su naturaleza privada y sensible —amparada en la Ley 1266 de 2008 (Habeas Data) y la regulación de la Superintendencia Financiera— impide entrenar y validar modelos de clasificación de gastos para la población colombiana. Este trabajo diseña y valida de forma preliminar un protocolo reproducible de generación de datos sintéticos de transacciones (extractos bancarios) calibrado con fuentes abiertas del DANE —la Gran Encuesta Integrada de Hogares (GEIH) 2025 y la Encuesta Nacional de Presupuestos de los Hogares (ENPH) 2016-2017— para Bogotá como caso de estudio. El protocolo adapta el pipeline multi-agente de Pancholi et al. incorporando variables ausentes en el modelo de referencia: el estrato socioeconómico y el quintil de ingreso como priors bayesianos jerárquicos, y la distribución de medios de pago condicionada a la categoría de gasto. El protocolo consta de cuatro etapas —priors bayesianos, generador por reglas, refinamiento con CTGAN y validación Train on Synthetic, Test on Real (TSTR)—. Como contribución metodológica, el pipeline de referencia se **reevaluó mediante una ejecución reproducible con criterios prerregistrados**: su salida **no es mapeable** a la taxonomía colombiana (cubre 8 de 16 categorías, con un techo de F1-macro de 0,50 por construcción), lo que motiva un protocolo propio; de sus tres limitaciones reportadas, una se refuta, la de medios de pago se corrige y la de sensibilidad al ingreso resulta de su *prompt*, no del modelo generativo. Los resultados disponibles confirman la viabilidad del protocolo y cuantifican las diferencias estructurales con el modelo de referencia; la validación TSTR contra transacciones reales anotadas de voluntarios bogotanos se reporta como preliminar.

**Index Terms —** datos sintéticos, CTGAN, clasificación de transacciones, TSTR, priors bayesianos, informalidad financiera, Colombia.

---

## I. Introducción

El desarrollo de sistemas de inteligencia artificial para finanzas personales enfrenta en Colombia una barrera fundamental: la inexistencia de conjuntos de datos públicos de transacciones financieras. A diferencia de contextos como el estadounidense, donde existen bases abiertas derivadas de encuestas de consumidores y registros de pagos, en Colombia los datos transaccionales son estrictamente privados y están bajo el resguardo de entidades sujetas a la Ley 1266 de 2008 (Habeas Data) y a la Superintendencia Financiera. Esta restricción **no es técnica sino regulatoria y de privacidad**: no se resuelve con más cómputo ni mejores algoritmos.

La brecha impide entrenar, validar y replicar modelos de clasificación de gastos, detección de patrones de ahorro o asesoría financiera para la población colombiana. El problema se agrava por la estructura del país: según el Banco de la República, el efectivo es el instrumento más usado en los pagos habituales (77,8 % de las transacciones en su encuesta de 2024 [2]), y la tenencia de tarjeta de crédito es minoritaria (7,2 % de los hogares [11]). Estas características hacen inviable transferir directamente modelos entrenados con datos de economías formalizadas.

Pancholi et al. [1] propusieron un sistema integral de finanzas personales basado en IA que incluye un generador de datos sintéticos, un clasificador de gastos y un asesor de inversión. Aunque su contribución metodológica es relevante, el sistema fue diseñado y validado exclusivamente con datos demográficos del American Community Survey 2015-2019 de Washington D.C. y comercios de Yelp y de esa ciudad. Como parte de este trabajo, el pipeline se ejecutó y se **reevaluó de forma reproducible** (Sección V); sus tres limitaciones reportadas —insensibilidad al ingreso, sesgo de categorías hacia el ocio y asignación monolítica del medio de pago— se contrastan con criterios prerregistrados en lugar de darse por sentadas.

Ante esta situación, se propone un protocolo de generación de datos sintéticos de transacciones calibrado para el contexto colombiano, con **Bogotá urbana como caso de estudio** (el dominio donde se recolecta el conjunto real de validación, lo que exige calibrar y evaluar en el mismo dominio). El protocolo usa como insumos la GEIH 2025 y la ENPH 2016-2017 del DANE para construir priors bayesianos que reflejen la estructura demográfica y de gasto real, y su utilidad se valida mediante el paradigma Train on Synthetic, Test on Real (TSTR) [5]: entrenar un clasificador de gastos sobre los datos sintéticos y evaluarlo sobre un conjunto reducido de transacciones reales de usuarios bogotanos.

La contribución y la pregunta de investigación se precisan en la Sección III. El documento sigue con el estado del arte (II), el planteamiento y la hipótesis (III), los datos y la metodología (IV), la reevaluación del pipeline de referencia (V), el diseño experimental (VI), los resultados (VII), la discusión y limitaciones (VIII) y las conclusiones (IX).

---

## II. Trabajo relacionado

### A. Generación de datos sintéticos financieros
La generación de datos sintéticos para aplicaciones financieras ha ganado relevancia como alternativa a la escasez de datos reales. Lopez-Rojas et al. [6] desarrollaron PaySim, uno de los primeros simuladores de transacciones financieras móviles, basado en agentes y calibrado con datos reales anonimizados de un servicio de dinero móvil, orientado a la detección de fraude; no modela categorías de gasto ni perfiles demográficos diferenciados, y opera sobre transferencias y pagos sin considerar el efectivo. Xu et al. [7] propusieron el Conditional Tabular GAN (CTGAN), que extiende las GAN a datos tabulares con tipos mixtos, distribuciones no gaussianas y desbalance de clases, mediante normalización específica por modo y un generador condicional; es el componente del módulo de refinamiento de este trabajo. Altman et al. [8] aportaron un generador de transacciones sintéticas con ground truth completo para modelos de lavado de activos. Hounwanou et al. [9] compararon ARIMA-GARCH, VAE y TimeGAN sobre el S&P 500. Karst et al. [10] compararon CTGAN, DGAN, FinDiff y TVAE sobre datos bancarios, hallando en CTGAN el mejor equilibrio entre fidelidad distribucional y capacidad de síntesis.

### B. Clasificación automática de transacciones
La clasificación de transacciones es un problema de clasificación de texto con descripciones cortas, vocabulario de dominio y alto desbalance de clases. Pancholi et al. [1] evaluaron regresión logística con TF-IDF, LSTM, BERT fine-tuneado y LLaMA 3 en modo few-shot, con mejor desempeño de LLaMA 3, pero exclusivamente sobre transacciones en inglés de comercios de Washington D.C. En el contexto colombiano la investigación es escasa y sin datasets públicos: el trabajo más cercano es una tesis de maestría (Tecnológico de Antioquia, 2022) sobre clasificación de transacciones PSE con datos privados, no replicable. Esta brecha justifica la contribución de datos sintéticos públicos.

### C. Paradigma Train on Synthetic, Test on Real (TSTR)
TSTR fue formalizado por Esteban et al. [5] para series de tiempo médicas con GAN recurrentes: se entrena sobre datos sintéticos y se evalúa sobre datos reales no vistos, midiendo la utilidad práctica más allá de la fidelidad distribucional. En dominios tabulares sensibles se ha consolidado como métrica de utilidad estándar, complementada con fidelidad (p. ej. MMD, distancia de Wasserstein) y privacidad. La aplicación de TSTR a finanzas personales colombianas, donde los datos reales son escasos **por diseño**, es una de las contribuciones metodológicas de este trabajo.

---

## III. Planteamiento del problema e hipótesis

### A. El problema
El desarrollo de clasificadores de gastos para usuarios colombianos enfrenta una contradicción estructural: entrenar un modelo requiere transacciones etiquetadas, pero esos datos son privados por diseño y no existen en el dominio público. La restricción es regulatoria, no técnica.

Usar datos sintéticos de pipelines calibrados en otros países no es viable sin adaptación. La reevaluación reproducible del pipeline de referencia (Sección V) examina las tres limitaciones que el informe de avance le atribuía —insensibilidad al ingreso, sesgo hacia categorías de ocio y asignación monolítica del medio de pago como tarjeta—; el análisis muestra que no todas se sostienen tal como se enunciaron, pero sí confirma que el modelo de referencia **no reproduce la relación ingreso–gasto ni la estructura de medios de pago colombiana**, lo que motiva la adaptación.

### B. Pregunta de investigación
¿Puede un protocolo de generación de datos sintéticos calibrado con fuentes colombianas (GEIH 2025 y ENPH 2016-2017 del DANE) producir transacciones suficientemente realistas para entrenar un clasificador de gastos que funcione sobre transacciones reales de usuarios bogotanos, validado mediante el paradigma TSTR?

### C. Hipótesis
Un pipeline que incorpore el estrato socioeconómico y el quintil de ingreso como priors bayesianos, y la distribución de medios de pago condicionada a la categoría de gasto observada en Colombia, producirá datos con mayor utilidad de entrenamiento —medida por F1-score macro en TSTR— que el pipeline de referencia aplicado sin adaptación.

> **[DECISIÓN — P16]** Precisar, con la directora, que bajo la arquitectura de dos capas (D15) la ENPH calibra la **capa interna** de gasto del hogar; la mezcla de medios observable en el extracto (billetera/transferencia) se introduce con una regla de migración parametrizada por escenarios, no directamente desde la ENPH (que no registra esos instrumentos). La redacción de la hipótesis debe reflejarlo.

---

## IV. Datos y metodología

### A. Fuentes de datos y dominio
Se usan dos fuentes abiertas del DANE, con una regla de calibración explícita: **la ENPH aporta ingreso (`ICGU`) y gasto; la GEIH aporta la estructura demográfica y laboral.** El ingreso laboral individual (`INGLABO`) es solo descriptivo por su amontonamiento en valores redondos.

- **GEIH 2025** (12 meses apilados): estrato, posición ocupacional, formalidad y tenencia de productos financieros (`P5222S*`). Muestra de Bogotá: 9.733 hogares y 13.552 ocupados (sin ponderar; verificado en `outputs/distribuciones/`).
- **ENPH 2016-2017**: ingreso del hogar (`ICGU`), gasto por categoría y forma de pago (`NC2R`, `P438`). Muestra de Bogotá: 3.918 hogares y 12.279 personas. Los valores monetarios se deflactan a pesos de 2025 con el índice total del IPC nacional del DANE (factor por mes de recolección del hogar, entre 1,56 y 1,62).

El dominio es **Bogotá urbana** (`AREA = 11` en GEIH, no `DPTO = 11`); la llave de hogar en ENPH es `DIRECTORIO`. Todo cálculo usa factores de expansión (`FEX_C18/FEX_C12` en GEIH; `FEX_C` en ENPH), verificados. Los 112 archivos del DANE se validan por SHA-256 y se cargan con un único módulo con pruebas automatizadas; ninguna cifra se escribe a mano.

### B. Hallazgos descriptivos que calibran el protocolo (Bogotá, con FEX)
- **Estrato agrupado (% de hogares):** ENPH bajo 44,7 / medio 49,5 / alto 5,9; GEIH 2025 bajo 47,3 / medio 46,0 / alto 6,8.
- **Forma de pago principal en gastos frecuentes** (`NC2R`, n = 3.517): efectivo 97,0 %, débito 2,0 %, crédito 0,5 %, otras 0,5 % (no respuesta 11,4 %, declarada aparte).
- **Medio de pago por categoría** (`P438`): el efectivo supera el 85 % en 22 de 29 subcapítulos, pero la tarjeta de crédito sube donde el gasto es grande (electrodomésticos y muebles 28,0 %; transporte y comunicaciones 22,4 %). Esta matriz condiciona el medio de pago a la categoría.
- **Mercado laboral (ocupados):** empleado particular 58,9 %, cuenta propia 30,5 %, gobierno 4,3 %, patrón 2,8 %, doméstico 2,7 %; con contrato 73,3 % (de ellos verbal 19,7 %); cotiza a pensión 64,1 %.
- **Quintiles de ingreso del hogar (`ICGU`, dentro de Bogotá):** fronteras superiores Q1 $1.127.000 · Q2 $1.810.250 · Q3 $2.766.667 · Q4 $4.506.283.
- **Bancarización:** 93,47 % de hogares con al menos un producto financiero (sin ninguno: 9,37 % estrato bajo, 4,54 % medio, 0,27 % alto).

### C. Decisiones metodológicas (D1–D15)
Las decisiones de diseño se documentan con su justificación (`docs/protocolo_tecnico.md`, `CLAUDE.md`). Las centrales: dominio Bogotá; ENPH calibra, GEIH estructura; estrato agrupado en 3 × quintil en 5 = 15 celdas; encogimiento jerárquico para las 4 celdas ralas; **D15 — el generador emite extractos bancarios** (capa interna de gasto del hogar calibrada con ENPH; capa emitida = lo que ve un banco; el efectivo sale como retiros periódicos; población = hogares bancarizados); **los datos reales solo evalúan, nunca calibran (D14)**.

### D. Las cuatro etapas del protocolo
1. **Priors bayesianos.** Para cada una de las 15 celdas (estrato × quintil) se estima la distribución categórica de gasto, forma y medio de pago y ocupación como media posterior de un Dirichlet jerárquico: `π_post = (n·p̂ + κ·π_padre)/(n + κ)`, con `n` el tamaño efectivo de Kish, `π_padre` el nivel urbano nacional recalibrado al nivel de Bogotá, y `κ` estimado por verosimilitud marginal (no elegido a mano). Una celda se encoge cuando `n_ef < κ̂`.
2. **Generador por reglas.** Muestrea perfiles de hogares bancarizados y emite el extracto: compras (medio condicionado a la categoría), retiros, nómina, transferencias P2P, recargas y pagos recurrentes. El texto de la descripción se construye con una biblioteca curada de comercios y plantillas de descriptor que imitan el formato anonimizado real.
3. **Refinamiento con CTGAN** (SDV): aprende correlaciones de alto orden entre los campos estructurados del extracto. `[DECISIÓN]` parámetros y métricas prerregistrados (ver VI).
4. **Validación TSTR:** entrenar clasificadores sobre sintético y evaluarlos sobre el conjunto real anotado de Bogotá.

### E. Taxonomía de categorías
`[PRELIMINAR — WP2]` Taxonomía v1 adaptada a Colombia (incluye P2P y comercio informal), con la variable de medio de pago como dimensión. Congelamiento a v1.1 pendiente tras revisar ≥ 50 descripciones reales (`docs/taxonomia/`).

---

## V. Reevaluación del pipeline de referencia (Pancholi et al.)

Las tres limitaciones que se atribuían al pipeline de referencia se reevaluaron **ejecutando su propio código** (clon con commit fijo, con sus dependencias) en **tres diseños** (A: rejilla de ingreso; B: réplica literal con sus 155 clientes; C: su etapa 1 reentrenada + etapas 2–3), con **10 semillas**, hasta **5.000.000 de registros**, intervalos bootstrap y criterios **fijados por escrito antes de correr**; la **etapa 4** (enriquecimiento con LLM) se corrió después con un modelo sustituto (`gpt-oss-120b`, porque Groq retiró el modelo original el 16-ago-2026) en una corrida, como evidencia indicativa. Una aclaración de honestidad: las cifras del informe inicial (5 perfiles, 149 tx, «USD 12», 100 % tarjeta) venían de su *app web*, no del pipeline del paper, y **quedan retiradas**. Resultado:

| Hipótesis | Enunciado del informe | Veredicto tras la ejecución |
|---|---|---|
| **H-P1** (insensibilidad al ingreso) | ≈ USD 12 entre perfiles | La etapa de reglas conserva la relación monto–ingreso (elasticidad **1,008** [1,007; 1,009]) y la etapa 4 responde al ingreso (elasticidad **0,79**), pero solo porque su *prompt* inyecta al LLM un rango de gasto derivado del ingreso; **la salida CTGAN no conserva la señal: −0,003** [−0,008; 0,002]. Contraste a favor del protocolo: su propio CTGAN **sí** la conserva (r≈1,37). |
| **H-P2** (dominio de categorías de ocio) | Domina el ocio | **Refutada** con la definición prerregistrada (ocio = entretenimiento, 13,0 % vs. alimentos 14,8 %); se confirma solo si el hospedaje cuenta como ocio. Solo 6 de 16 categorías tienen registros. |
| **H-P3** (100 % tarjeta de crédito) | Todo es `credit_card` | El pipeline no emite retiros, transferencias ni billetera (0 de 5.000.000). La etapa 4 **sí se ejecutó**: domina la tarjeta (**89 % crédito**) pero **no es 100 %**; efectivo/billetera/transferencia: 0 de 300. La afirmación de «100 % `credit_card`» del informe queda corregida. |

Prerregistrar los criterios es lo que da credibilidad a la reevaluación: no se ajustó la definición para obtener un resultado. La conclusión que sostiene el protocolo es que el pipeline de referencia **no reproduce ni la relación ingreso–gasto ni la estructura de medios de pago colombiana**; adaptarlo no es opcional. Más aún, su salida **no es mapeable** a la taxonomía colombiana: solo emite compras y alcanza **8 de las 16 categorías** (`outputs/pancholi/wp8_mapeabilidad.json`), de modo que cualquier clasificador entrenado con ella tiene un **techo de F1-macro de 0,50** por construcción —faltan ingreso, retiro, movimiento propio, P2P y otras, el 42 % de las transacciones observables—. Esta **no-transferibilidad** es, en sí misma, el resultado que motiva un protocolo propio. (Detalle y figura de elasticidad por etapa: `docs/reevaluacion_pancholi.md`, `outputs/pancholi/`.)

---

## VI. Diseño experimental

### A. Dataset sintético
`[PRELIMINAR — WP6/WP7]` Corrida de referencia del generador: 1.000 perfiles × 3 meses (dic-2025, abr-2026, ago-2026), semilla 42 → 448.383 filas (122.211 emitidas; `outputs/sintetico_reglas/resumen_generacion.json`). El CTGAN (SDV) se entrena sobre los campos estructurados de la capa emitida para producir el dataset sintético v1 (≥ 5.000 transacciones). Parámetros prerregistrados: entradas, condicionamiento por `categoria_n1`, `epochs`, semilla y criterios de rechazo (hoja de pre-registro, `outputs/ctgan/manifest.json`).

### B. Conjunto real de validación
`[PRELIMINAR — WP4]` 20 voluntarios de Bogotá (muestra por conveniencia; conjunto de validación, no representativo). Extractos de Nequi, Daviplata o bancarios de 3 meses de referencia, anonimizados según protocolo (`docs/datos_reales/02_protocolo_anonimizacion_v1.1.md`). Etiquetado por 2 anotadores con la taxonomía v1.1 y concordancia inter-anotador (Cohen's Kappa). **Estado:** aval de ética resuelto; ingesta/anonimización en curso; anotación pendiente.

### C. Protocolo TSTR y clasificadores
Tres clasificadores entrenados sobre sintético: (i) regresión logística con TF-IDF (baseline), (ii) BETO fine-tuneado, (iii) LLaMA 3 few-shot. Métricas: F1-macro (con regla de soporte ≥ 10 por clase), Cohen's Kappa y AUC. **Brazo de control (solo campos estructurados):** como la descripción de texto se genera por plantillas condicionadas a la categoría, un clasificador de texto mediría las plantillas y no el aporte del CTGAN; por eso se incluye un brazo entrenado únicamente con los campos estructurados (monto, medio de pago, cuenta, etc.), que aísla la contribución del refinamiento generativo. **Comparación con el pipeline de referencia:** su salida no es mapeable a la taxonomía colombiana (solo emite compras, 8 de 16 categorías; Sección V), así que **no admite un entrenamiento TSTR comparable**: un clasificador entrenado con ella queda acotado a un techo de F1-macro de 0,50 por construcción. La comparación es, por tanto, **estructural** —la no-transferibilidad del pipeline de referencia frente a la cobertura completa del protocolo propio—, no un F1 medido cabeza a cabeza. El desempeño que los autores reportan (datos en inglés, otra ciudad, otras categorías) se cita solo como contexto.

---

## VII. Resultados

### A. Fidelidad del dataset sintético
Corrida oficial (300 épocas, CPU, semilla 42; SDV 2.2.0 / ctgan 0.13.0). **Reproducibilidad bit a bit confirmada:** dos entrenamientos independientes dan el mismo SHA-256 de la muestra. Train = 96.386 filas (80 % de los perfiles); holdout = 25.825.

**Calidad (SDV QualityReport)**, con piso = muestreo de marginales independientes y techo = train vs. holdout:

| Métrica | Piso | CTGAN v1 | Techo | Brecha al techo |
|---|---|---|---|---|
| Overall | 0,830 | 0,931 | 0,974 | 0,043 |
| Column Shapes | 0,980 | 0,935 | 0,980 | 0,046 |
| Column Pair Trends | 0,680 | 0,927 | 0,968 | 0,041 |

En **dependencias** (Column Pair Trends) el CTGAN recupera el **85,7 %** de la distancia piso→techo (0,927 frente a piso 0,680 y techo 0,968): ahí está su aporte sobre un muestreo trivial. En **marginales** (Column Shapes) el CTGAN (0,935) queda por debajo del piso (0,980), que clava las marginales por construcción; la desviación en la marginal de `categoria_n1` es ≈ 0,13.

**Elasticidad monto–ingreso** (veredicto prerregistrado): train ê = 0,331 [0,267; 0,388]; **CTGAN v1 ê = 0,452 [0,441; 0,463], r = 1,37 → CONSERVA** (de hecho amplifica, r > 1); piso ≈ 0 (−0,005). Nuestro CTGAN conserva —e intensifica— la relación ingreso–monto, en contraste con el del pipeline de referencia que la colapsa (−0,003). La amplificación por encima del train (ICs que no se solapan) se discute como posible sobre-ajuste de la correlación.

**Reglas duras / rechazo:** tasa total **14,78 %**, que **supera el tope declarado del 10 %** → resultado de fidelidad **negativo**, reportado. El grueso es `par_n1_n2_inexistente` (10,78 %): el CTGAN plano genera pares categoría–subcategoría fuera de la taxonomía, señal de que **no captura bien la jerarquía categórica**. El resto: signo incompatible 2,66 %, medio imposible para la cuenta 1,67 %, `canal_p2p` 0,25 %, fecha 0,11 %. El dataset v1 (122.211 filas) es el resultado tras filtrar las violaciones.

### B. Validación TSTR
`[PRELIMINAR — WP8]` F1-macro por clasificador, matriz de confusión por categoría, Kappa. Pendiente de la anotación del conjunto real.

### C. Comparación con el pipeline de referencia
`[PRELIMINAR — WP8]` El pipeline de referencia **no es mapeable** a la taxonomía colombiana (Sección V): su salida cubre 8 de 16 categorías, con un techo de F1-macro de 0,50 por construcción, así que **no entra como fila comparable** en la tabla TSTR. La comparación es estructural (no-transferibilidad) y se reporta como contexto; la tabla TSTR contrasta las dos variantes propias —generador por reglas vs. generador con CTGAN (ablación de la Etapa 3)— sobre el mismo conjunto real.

---

## VIII. Discusión y limitaciones

El aporte disponible a la fecha es doble: (1) una base empírica reconstruida y verificable de Bogotá, y un protocolo de generación con priors jerárquicos y medios de pago condicionados a la categoría; (2) una reevaluación reproducible y prerregistrada del pipeline de referencia. La validación TSTR es preliminar; su resultado acota —no cierra— la hipótesis, porque el conjunto real todavía se está anotando.

Limitaciones declaradas (`docs/protocolo_tecnico.md`, L1–L17), las principales:
- **L1** — Los archivos públicos no traen segmento ni UPM: no se reportan intervalos de confianza de diseño sobre cifras DANE.
- **L4** — La ENPH es de 2016-2017 y no registra billeteras ni transferencias; los medios digitales se introducen por una regla de migración por escenarios (10/20/35 %), sin ancla verificada.
- **L7** — Los extractos no ven el efectivo (un retiro es una fila, no quince compras): el TSTR se evalúa sobre el universo bancarizado.
- **L8** — 20 voluntarios por conveniencia: diversidad, no representatividad.
- **L16** — El repeso a bancarizados (D15) asume independencia condicional entre quintil de `ICGU` y tenencia de productos, dentro del estrato.
- **Realismo del texto sintético** — Las descripciones provienen de una biblioteca curada de comercios y plantillas (regla propia, no calibrada con los extractos reales): son más limpias y regulares que un extracto real, por lo que el TSTR es un **techo optimista** que se estrecha al incorporar los datos reales anotados. Como el texto se genera por plantillas condicionadas a la categoría, un clasificador de texto mide en parte el sistema de plantillas, no el refinamiento del CTGAN (de ahí el brazo de control solo-estructurado, §VI.C).
- **Fidelidad del CTGAN a las reglas, no a Colombia** — El CTGAN se entrena sobre la capa emitida, que ya es sintética (salida del generador por reglas); por tanto sus métricas de fidelidad miden cercanía a la salida de las reglas, no a la realidad colombiana. La prueba frente a la realidad es el TSTR contra datos reales.
- **Jerarquía categórica en el CTGAN** — El CTGAN plano genera un 10,78 % de pares categoría–subcategoría inexistentes en la taxonomía (rechazo total 14,78 %, por encima del tope prerregistrado del 10 %). Modelar explícitamente la jerarquía o restringir el muestreo condicional es trabajo futuro. La amplificación de la elasticidad por el CTGAN (0,45 vs. 0,33 del train) también debe vigilarse como posible sobre-ajuste de la correlación ingreso–monto.

---

## IX. Conclusiones y trabajo futuro

El trabajo entrega un protocolo reproducible para generar extractos bancarios sintéticos calibrado con microdatos del DANE para Bogotá, con priors bayesianos jerárquicos por estrato y quintil, medios de pago condicionados a la categoría, y una reevaluación prerregistrada del pipeline de referencia. Contribuciones esperadas: (i) un protocolo replicable para economías de alta informalidad; (ii) el primer dataset sintético público de transacciones financieras colombianas; (iii) una taxonomía con categoría P2P y descripciones en español; (iv) evidencia empírica —vía TSTR— del valor de la contextualización.

Trabajo futuro: cerrar la validación TSTR con el conjunto real anotado; extender a otras ciudades; anclar la participación de medios digitales con una fuente primaria; reemplazar la biblioteca curada de comercios por una capa empírica (p. ej. OpenStreetMap); y la etapa 5 del pipeline de referencia (asesoría de inversión), fuera de alcance de este trabajo.

---

## Declaración de uso de herramientas de IA
`[DECISIÓN — obligatoria]` Describir el uso de asistentes de IA (Claude / Fable) en la reconstrucción de la base de datos, la implementación de los módulos, la reevaluación del pipeline de referencia y la redacción asistida de este documento, conforme a la política de integridad académica de la Universidad.

## Declaración de ética y consentimiento
Consentimiento informado de los voluntarios y anonimización de los extractos (`docs/datos_reales/`); aval de comité de ética según el programa.

## Referencias

> DOIs/arXiv verificados vía web el 17 nov 2026. Pendientes marcados `[verificar]`.

[1] S. Pancholi, A. Jaglan, H. Makadia, P. Doshi, and M. Jafari, "An end-to-end multi-agent AI system for personal finance: synthetic data generation, budget optimization, and investment advisory," *Neural Computing and Applications*, vol. 38, 2026, doi: 10.1007/s00521-025-11749-7.

[2] Banco de la República de Colombia, "Resultados de la encuesta de percepción sobre el uso de los instrumentos para los pagos habituales en Colombia 2024," Dept. de Seguimiento a la Infraestructura Financiera, Bogotá, Colombia, 2024. [Online]. Available: https://www.banrep.gov.co/es/publicaciones-investigaciones/encuesta-percepcion-uso-instrumentos-pagos/2024

[3] Departamento Administrativo Nacional de Estadística (DANE), "Gran Encuesta Integrada de Hogares — GEIH 2025," Bogotá, Colombia, 2025. [Online]. Available: https://microdatos.dane.gov.co/index.php/catalog/853

[4] Departamento Administrativo Nacional de Estadística (DANE), "Encuesta Nacional de Presupuestos de los Hogares — ENPH 2016-2017," Bogotá, Colombia, 2017. [Online]. Available: https://microdatos.dane.gov.co/index.php/catalog/566

[5] C. Esteban, S. L. Hyland, and G. Rätsch, "Real-valued (medical) time series generation with recurrent conditional GANs," *arXiv:1706.02633*, 2017.

[6] E. A. Lopez-Rojas, A. Elmir, and S. Axelsson, "PaySim: A financial mobile money simulator for fraud detection," in *Proc. 28th European Modeling and Simulation Symp. (EMSS)*, Larnaca, Cyprus, 2016.

[7] L. Xu, M. Skoularidou, A. Cuesta-Infante, and K. Veeramachaneni, "Modeling tabular data using conditional GAN," in *Advances in Neural Information Processing Systems (NeurIPS)*, vol. 32, 2019.

[8] E. Altman et al., "Realistic synthetic financial transactions for anti-money laundering models," in *Advances in Neural Information Processing Systems (NeurIPS) Datasets and Benchmarks Track*, 2023, *arXiv:2306.16424*.

[9] C. D. Hounwanou, P. Ntakirutimana, and Y. U. Gaba, "Evaluating generative models for synthetic financial data," *arXiv:2512.21791*, 2025. `[verificar: el mismo arXiv aparece con el título "Synthetic Financial Data Generation for Enhanced Financial Modelling"; confirmar título y autores exactos]`

[10] N. Karst et al., "Generative AI for banks: Benchmarks and algorithms for synthetic financial transaction data," *arXiv:2412.14730*, 2024.

[11] Banca de las Oportunidades y Superintendencia Financiera de Colombia, "Reporte de Inclusión Financiera 2024," Bogotá, Colombia, 2024. [Online]. Available: https://bancadelasoportunidades.gov.co/es/reportes-e-indicadores

> **Notas de verificación:** DOI de [1] y arXiv de [5]–[10] confirmados. [10]: se añadió "Transaction" al título (versión correcta). [9]: título por confirmar (ver arriba). Páginas de [6] y [7] y listas completas de autores de [8] y [10] por completar contra la fuente. [2]–[4] y [11] son reportes/datasets oficiales sin DOI.

## Figuras candidatas
Pirámide de estrato (ENPH vs GEIH); matriz medio de pago × categoría; elasticidad de Pancholi por etapa; composición de las filas emitidas por tipo; matriz de confusión TSTR `[PRELIMINAR]`.
