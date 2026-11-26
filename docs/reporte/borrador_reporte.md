# Diseño y validación de un protocolo de generación de datos sintéticos de transacciones financieras para el contexto colombiano

**Sara Juliana Cárdenas Bohórquez y Cecile <apellido>** (asesores: por completar) · Maestría en Inteligencia Artificial, Pontificia Universidad Javeriana · correo: <correo institucional>

> **Versión final — 26 nov 2026.** Espejo en markdown de `docs/reporte/main.tex` (plantilla IEEE Transactions on AI, clase `IEEEtai.cls`); el PDF de entrega se compila desde el `.tex`. Cifras del TSTR: `docs/resultados_tstr.md` (sección Trazabilidad); conjunto real: pre-registro `docs/datos_reales/05_prerregistro_muestreo_anotacion.md` v1.4 e inventario `data/reales_anon/_inventario_reales.md`. Por completar por la autora: `<correo institucional>`, `Cecile <apellido>` y los nombres de los asesores.

---

## Abstract

El acceso a datos transaccionales financieros en Colombia es prácticamente inexistente en el dominio público: su naturaleza privada y regulada (Ley 1266 de 2008, Habeas Data) impide entrenar y validar clasificadores de gastos para la población colombiana. Este trabajo diseña y valida un protocolo reproducible de generación de extractos bancarios sintéticos calibrado con microdatos abiertos del DANE —la GEIH 2025 y la ENPH 2016-2017— para Bogotá. El protocolo adapta el pipeline de Pancholi *et al.* con *priors* bayesianos jerárquicos por estrato y quintil de ingreso y con medios de pago condicionados a la categoría de gasto, en cuatro etapas: *priors*, generador por reglas, refinamiento con CTGAN y validación Train on Synthetic, Test on Real (TSTR). La reevaluación reproducible y prerregistrada del pipeline de referencia muestra que su salida no es mapeable a la taxonomía colombiana (8 de 16 categorías, techo de F1-macro de 0,50). En el TSTR sobre 200 transacciones reales anonimizadas y anotadas por dos anotadoras independientes (κ de Cohen de 0,934), una regresión logística entrenada solo con datos sintéticos alcanza un F1-macro de 0,57 [IC95: 0,51; 0,62], frente a 0,06 del azar estratificado. Con la misma capa de texto, el generador por reglas y el CTGAN rinden igual (Δ = +0,001 [−0,055; +0,053]). El error dominante es de etiquetado: el generador marca como ingreso parte de las transferencias recibidas de personas, mientras que el conjunto real, sin propósito declarado, las deja como transferencias entre personas; el sintético debe etiquetarse con la misma información que el real.

**Declaración de impacto —** En Colombia no existen datos públicos de transacciones bancarias, porque la ley los protege; sin ellos es difícil construir y auditar herramientas de finanzas personales para una población que usa mucho efectivo y transferencias entre personas. Este trabajo ofrece un procedimiento abierto y reproducible para fabricar extractos bancarios artificiales a partir de encuestas oficiales del DANE, sin usar datos de ningún cliente. Un clasificador de gastos entrenado solo con esos extractos artificiales acierta muy por encima del azar sobre transacciones reales de voluntarios de Bogotá. Esto sugiere que universidades, reguladores y empresas pequeñas podrían desarrollar y probar modelos sin acceder a datos sensibles. El trabajo deja además una lección práctica: los datos artificiales deben etiquetarse con la misma información que tendrá quien etiquete los datos reales; si no, el modelo aprende distinciones que en la práctica no se pueden hacer.

**Index Terms —** Datos sintéticos, CTGAN, clasificación de transacciones, TSTR, *priors* bayesianos, Colombia.

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
Un pipeline que incorpore el estrato socioeconómico y el quintil de ingreso como *priors* bayesianos, y la distribución de medios de pago condicionada a la categoría de gasto observada en Colombia, producirá datos sintéticos con utilidad de entrenamiento suficiente —medida por F1-macro en TSTR sobre transacciones reales bogotanas— para un clasificador de gastos funcional. La contextualización no es opcional: el pipeline de referencia no cubre, por construcción, el espacio de categorías colombiano (Sección V), de modo que la comparación pertinente es la ganancia que aporta la capa estructural propia (ablación generador por reglas frente a CTGAN), no un F1 cabeza a cabeza con un pipeline no mapeable. Bajo la arquitectura de dos capas (Sección \ref{sec:metodo}), la ENPH calibra la capa interna de gasto del hogar; la participación de billeteras y transferencias en la capa observable se introduce mediante una regla de migración parametrizada por escenarios (10/20/35 %), dado que la ENPH 2016-2017 no registra esos instrumentos; el TSTR de este informe usa el escenario base (20 %).

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
3. **Refinamiento con CTGAN** (SDV): aprende correlaciones de alto orden entre los campos estructurados del extracto, con pre-registro de columnas, métricas y reglas duras (ver VII.A).
4. **Validación TSTR:** entrenar clasificadores sobre sintético y evaluarlos sobre el conjunto real anotado de Bogotá.

### E. Taxonomía de categorías
Taxonomía v1.1.0 congelada (`docs/taxonomia/taxonomia_gastos_colombia_v1.json`): 16 categorías de primer nivel (`categoria_n1`), que incluyen transferencias entre personas (P2P) y movimientos propios, con las reglas de asignación R1–R7 y el medio de pago como dimensión aparte. La v1.1.0 no cambió las categorías ni las reglas de la v1.0, solo documentación y metadatos de anotación.

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
Corrida de referencia del generador: 1.000 perfiles × 3 meses (dic-2025, abr-2026, ago-2026), semilla 42 → 448.383 filas (122.211 emitidas; `outputs/sintetico_reglas/resumen_generacion.json`). El CTGAN (SDV) se entrena sobre los campos estructurados de la capa emitida y produce el dataset sintético v1 (122.211 filas). Parámetros prerregistrados: entradas, condicionamiento por `categoria_n1`, `epochs`, semilla y criterios de rechazo (hoja de pre-registro, `outputs/ctgan/manifest.json`).

### B. Conjunto real de evaluación
El conjunto real proviene de extractos de cuentas de ahorro y de tarjetas de crédito de voluntarios de Bogotá, recolectados con consentimiento informado y aval de ética. Es una muestra por conveniencia que sirve para evaluar, no para representar a la población, y por la separación entre datos reales y calibración solo evalúa: ni la muestra ni las etiquetas alimentan el generador ni las plantillas de texto.

**Extracción y conciliación.** Las transacciones se extraen de los PDF por código; cuando una página es una imagen escaneada sin capa de texto se aplica reconocimiento óptico de caracteres (OCR). Cada extracto que imprime totales del periodo (créditos y débitos) se concilia contra la suma de los movimientos extraídos; los de tarjeta no traen totales comparables.

**Anonimización.** Los nombres de personas naturales se reemplazan por el token `PERSONA`, el mismo que emite el generador, para no presentar en la evaluación un formato que el clasificador nunca vio al entrenar. El token enmascara también al propio titular, de modo que el texto no distingue una transferencia a un tercero de una a cuenta propia. Las llaves Bre-B (alias y correos) se reemplazan por `LLAVE`. Este documento no reproduce ninguna descripción real.

**Muestreo (pre-registrado).** El marco excluye los meses sin IPC incorporado al repositorio al congelarlo, porque el clasificador recibe los montos deflactados a pesos de 2025 con el IPC del mes. La muestra de n = 200 se estratifica por una preclasificación heurística por palabras clave —herramienta de muestreo, no etiqueta, que las anotadoras no ven—, con un mínimo de 10 ítems por estrato y un tope de 3 filas por descripción normalizada, en dos etapas con probabilidades de inclusión exactas; el peso de muestreo es 1/(π₁π₂). El sorteo usa claves SHA-256 y es idéntico en cualquier máquina.

**Anotación doble a ciegas.** Dos anotadoras asignan `categoria_n1` de forma independiente viendo solo lo que ve el clasificador (tipo de cuenta, signo, monto y descripción). El acuerdo se mide con el κ de Cohen, con IC95 por *bootstrap* estratificado, y cada desacuerdo se adjudica registrando su causa. La primera anotadora (la autora) participó en la extracción, así que no es ciega a los datos, solo a las etiquetas de la otra; por eso la etiqueta adjudicada debe justificarse con lo que ve el clasificador.

**Desviaciones de ejecución** (pre-registro v1.4, §13), ninguna sobre el diseño muestral ni las métricas: (i) no hubo sesión de calibración previa, de modo que el κ mide acuerdo sin coordinación; (ii) las convenciones de cuatro casos que la taxonomía v1.1 no resuelve (reversos, pagos PSE sin facturador, transferencias a o desde billetera sin persona y pagos a `PERSONA`) se fijaron en la adjudicación, citando la taxonomía, viendo las dos anotaciones y antes de ver cualquier predicción, y se aplicaron a todos los ítems de cada caso; el κ usa las anotaciones originales; (iii) el patrón del cuarto caso se amplió después de anotar; y (iv) un error del consolidador marcó 7 ítems como de anotación simple, que se corrigió sin cambiar ninguna etiqueta.

### C. Protocolo TSTR y clasificadores
Los clasificadores se entrenan sobre cada sintético —generador por reglas y CTGAN, ambos con 122.211 filas— y se evalúan sobre los 200 ítems reales; el objetivo es `categoria_n1`. Ambas fuentes reciben la descripción de la misma capa de texto (mismas plantillas, comercios y semilla, ninguna calibrada con el real), de modo que la diferencia entre reglas y CTGAN aísla la capa estructural. La entrada es idéntica en todos los brazos: tipo de cuenta, signo y monto en rangos logarítmicos de media década (pesos de 2025; el real se deflacta con el IPC del mes), seguidos de la descripción. Clasificadores: (i) regresión logística con TF-IDF de n-gramas de caracteres 3–5, con todo el sintético y con una submuestra estratificada de 20.000 filas; (ii) BETO afinado sobre esa misma submuestra, por costo de cómputo en CPU, de modo que la comparación de igual a igual es regresión logística @20k frente a BETO @20k; y (iii) un LLM *few-shot* vía Groq, que no se evaluó sobre el real porque no se envían datos reales a la API.

**Métricas (pre-registradas).** Principal: F1-macro sin ponderar con regla de soporte: las clases con menos de 10 ítems en el test se fusionan con `otros`, en la etiqueta real y en la predicha, con la regla fijada una vez sobre el test observado. IC95 principal por *bootstrap* por fila estratificado por estrato de muestreo (1.000 réplicas, semilla 42); como sensibilidad, *bootstrap* por grupo de extractos. El alcance es la incertidumbre de muestreo dentro de estos extractos, no la generalización a nuevos titulares. Secundaria: exactitud ponderada con los pesos de muestreo (estimador de Hájek). La ablación mide Δ = F1_CTGAN−F1_reglas por *bootstrap* pareado sobre el mismo test; la comparación principal es la regresión logística con todo el sintético y las otras dos son secundarias, sin corrección por multiplicidad: una Δ secundaria cuyo IC toque o cruce cero no se interpreta como efecto. Líneas base: clase mayoritaria del sintético y predicción aleatoria con su distribución. El pipeline de referencia no entra como fila de la tabla TSTR (Sección VIII).

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

### B. Conjunto real y anotación
Los 53 extractos dan 2.471 transacciones anonimizadas. De ellos, 31 se concilian contra los totales impresos por el banco, sin ningún descuadre, y 22 no traen totales comparables. El marco muestral tiene 2.183 transacciones de diciembre de 2025 a septiembre de 2026 (corte en el último mes de la serie de IPC incorporada) en 6 grupos de extractos, que corresponden a lo sumo a 6 titulares. La muestra estratificada de 200 ítems cubre 153 descripciones distintas; sus pesos son insesgados (todas las filas del marco tienen probabilidad de inclusión positiva), pero el tope por descripción concentra el peso en pocos ítems y deja un tamaño efectivo de Kish de 48. La anotación doble independiente alcanza κ = 0,934 [0,896; 0,967] sobre `categoria_n1`, con 12 desacuerdos adjudicados; excluyendo los ítems de los casos de convención, el κ queda entre 0,925 y 0,935 según el patrón usado para identificarlos.

**Tabla — TSTR: entrenamiento en sintético, evaluación en el conjunto real anotado (n = 200). F1-macro con regla de soporte ≥ 10**

| Clasificador | n train | Fuente | F1-macro | IC95 fila^a | IC95 grupo^b | Exactitud | Exact. ponderada [IC95] |
|---|---|---|---|---|---|---|---|
| Reg. logística (TF-IDF 3–5) | 122.211 | reglas | 0,566 | [0,507; 0,619] | [0,471; 0,601] | 0,440 | 0,324 [0,222; 0,438] |
|  | 122.211 | CTGAN | 0,567 | [0,507; 0,619] | [0,447; 0,602] | 0,420 | 0,307 [0,210; 0,421] |
| Reg. logística @20k | 20.000 | reglas | 0,458 | [0,397; 0,508] | [0,354; 0,544] | 0,350 | 0,230 [0,146; 0,350] |
|  | 20.000 | CTGAN | 0,511 | [0,446; 0,568] | [0,366; 0,578] | 0,370 | 0,290 [0,194; 0,406] |
| BETO afinado @20k | 20.000 | reglas | 0,453 | [0,385; 0,520] | [0,335; 0,491] | 0,385 | 0,225 [0,164; 0,304] |
|  | 20.000 | CTGAN | 0,474 | [0,410; 0,528] | [0,357; 0,514] | 0,355 | 0,201 [0,143; 0,275] |
| LLM *few-shot* (Groq) | – | ambas | no evaluado sobre el real (restricción de tratamiento de datos) |  |  |  |  |
| *Líneas base* |  |  |  |  |  |  |  |
| Clase mayoritaria | 122.211 | reglas / CTGAN | 0,013 | [0,009; 0,017] | – | 0,075 | 0,105 |
| Aleatorio estratificado | 122.211 | reglas | 0,060 | [0,038; 0,085] | – | 0,055 | 0,057 |
|  | 122.211 | CTGAN | 0,059 | [0,037; 0,083] | – | 0,055 | 0,057 |

*^a*Bootstrap* por fila estratificado por estrato de muestreo (1.000 réplicas, semilla 42), principal. ^b*Bootstrap* por grupo de extractos (6 grupos), sensibilidad. Cinco clases con soporte <10 se fusionan con `otros`; se evalúan 11 clases.*

### C. Utilidad TSTR
La Tabla TSTR resume el TSTR. Con todo el sintético, la regresión logística alcanza un F1-macro de 0,566 [0,507; 0,619] entrenada con el generador por reglas y de 0,567 [0,507; 0,619] con el CTGAN; con el IC por grupo de extractos, [0,471; 0,601] y [0,447; 0,602]. Con 20.000 filas, la regresión logística obtiene 0,458 (reglas) y 0,511 (CTGAN), y BETO, 0,453 y 0,474. Las líneas base quedan en 0,013 (clase mayoritaria) y 0,060 y 0,059 (aleatorio estratificado, reglas y CTGAN).

**Tabla — Ablación: Δ F1-macro = CTGAN − reglas, con la misma capa de texto (*bootstrap* pareado)**

| Clasificador (rol) | Δ | IC95 fila | IC95 grupo |
|---|---|---|---|
| Reg. log. completo (princ.) | +0,001 | [−0,055; 0,053] | [−0,061; 0,034] |
| Reg. log. @20k (sec.) | +0,053 | [0,012; 0,096] | [−0,010; 0,081] |
| BETO @20k (sec.) | +0,021 | [−0,030; 0,073] | [−0,017; 0,062] |

*Tres comparaciones sin corrección por multiplicidad; una Δ secundaria cuyo IC (fila o grupo) toca o cruza cero no se interpreta como efecto.*

### D. Ablación: generador por reglas frente a CTGAN
En la comparación principal (Tabla de ablación), Δ = +0,001 [−0,055; +0,053] (por grupo, [−0,061; +0,034]): no hay diferencia detectable entre fuentes, y el intervalo hace improbable una diferencia mayor que unos 0,05 puntos de F1 en cualquier dirección. Las dos comparaciones secundarias no se interpretan como efecto: con la regresión logística @20k, Δ = +0,053 [+0,012; +0,096], pero su IC por grupo cruza cero ([−0,010; +0,081]); con BETO, Δ = +0,021 [−0,030; +0,073]. Las tres comparaciones no se corrigen por multiplicidad.

### E. Volumen de entrenamiento y arquitectura
Pasar de 20.000 a 122.211 filas sube el F1-macro de la regresión logística entre 0,06 (CTGAN) y 0,11 (reglas). Con el mismo número de filas, BETO no supera a la regresión logística (0,453 frente a 0,458 con reglas; 0,474 frente a 0,511 con CTGAN).

**Tabla — F1 por clase, regresión logística con todo el sintético, sobre el conjunto real**

| Clase | Soporte | Reglas | CTGAN |
|---|---|---|---|
| `retiro_efectivo` | 10 | 1,000 | 1,000 |
| `salud` | 11 | 0,957 | 0,957 |
| `educacion` | 10 | 0,762 | 0,625 |
| `transporte` | 13 | 0,667 | 0,545 |
| `comidas_fuera` | 25 | 0,652 | 0,650 |
| `ingreso` | 11 | 0,485 | 0,625 |
| `otros`^† | 44 | 0,485 | 0,441 |
| `obligaciones_financieras` | 17 | 0,432 | 0,552 |
| `alimentos_mercado` | 15 | 0,333 | 0,240 |
| `hogar_articulos` | 16 | 0,270 | 0,313 |
| `transferencias_p2p` | 28 | 0,188 | 0,294 |

*^†Incluye las clases con soporte <10 fusionadas: `entretenimiento` (9), `telecom_conectividad` (5), `vestuario_cuidado_personal` (5), `vivienda_servicios` (1) y `movimiento_propio` (1).*

### F. Desempeño por clase
La Tabla por clase desagrega el F1 de la comparación principal. Las mejores clases son `retiro_efectivo` (1,00) y `salud` (0,96); las peores, `transferencias_p2p` (0,19 con reglas y 0,29 con CTGAN), `hogar_articulos` y `alimentos_mercado`. La exactitud es de 0,44 (reglas) y 0,42 (CTGAN), y la exactitud ponderada, de 0,32 y 0,31. La caída al ponderar se explica por el peso de `transferencias_p2p`, la clase peor clasificada: es el 14 % de la muestra, pero su peso estimado en el marco es del 33,7 %.

**Tabla — Sensibilidades pre-registradas**

| Clasificador | Fuente | (a) F1, una fila | (c) Exact. pond. | (d) Re- |
|---|---|---|---|---|
|  |  | por descripción | P95 (Δ) | versos |
| Reg. log. | reglas | 0,531 [0,460; 0,593] | 0,348 (−0,024) | 1/6 |
| (completo) | CTGAN | 0,556 [0,481; 0,626] | 0,327 (−0,020) | 1/6 |
| Reg. log. | reglas | 0,404 [0,328; 0,467] | 0,233 (−0,003) | 0/6 |
| @20k | CTGAN | 0,498 [0,417; 0,571] | 0,306 (−0,016) | 0/6 |
| BETO | reglas | 0,447 [0,366; 0,525] | 0,275 (−0,0498)^c | 0/6 |
| @20k | CTGAN | 0,433 [0,357; 0,502] | 0,245 (−0,044) | 0/6 |

*(a) n = 153; la regla de soporte fusiona además `educacion`, `ingreso` y `retiro_efectivo`. (b) No aplica: todos los ítems tienen doble anotación. (c) Pesos recortados al percentil 95 y renormalizados; Δ = sin recorte − con recorte; alerta si \|Δ\|>0,05. ^cEn el umbral, sin alerta formal; se reporta sin redondear. (d) Aciertos sobre los reversos y devoluciones de tarjeta.*

### G. Sensibilidades pre-registradas
La Tabla de sensibilidades reporta las sensibilidades fijadas antes de anotar. (a) Con una sola fila por descripción, el F1-macro de la comparación principal baja a 0,531 (reglas) y 0,556 (CTGAN): las descripciones repetidas sostienen parte del resultado, pero no lo explican. (b) No aplica, porque todos los ítems tienen doble anotación. (c) Recortar los pesos al percentil 95 no dispara la alerta en ningún brazo; la diferencia mayor, la de BETO con reglas (−0,0498), queda en el umbral. (d) De los 6 reversos y devoluciones de tarjeta, la regresión logística con todo el sintético acierta 1 y los demás brazos ninguno; es un tipo de transacción que probablemente no existe en el sintético.

## VIII. Discusión y limitaciones
### A. Discusión
**Utilidad.** Un clasificador entrenado solo con datos sintéticos alcanza un F1-macro de 0,57 sobre transacciones reales, frente a 0,06 del azar estratificado: el sintético transfiere al dato real con una utilidad moderada. El alcance es el de estos extractos; con 6 grupos de extractos no se afirma generalización a nuevos titulares.

**Reglas frente a CTGAN.** Con la misma capa de texto, el generador por reglas y el CTGAN rinden igual, aunque el CTGAN no conserve bien la jerarquía categórica (Sección VII). La lectura más consistente es que la utilidad la aporta sobre todo la capa de texto y no la estructura tabular que distingue a las dos fuentes; la ablación no mide por separado el aporte del texto, de modo que esta lectura es una interpretación, no un resultado.

**Choque de convenciones P2P/ingreso.** La clase peor clasificada se explica por una diferencia de etiquetado, confirmada en el código del generador. El generador etiqueta con el propósito declarado por el hogar simulado: el ingreso de los no asalariados llega con plantilla de transferencia recibida de persona, de modo que el 41–42 % de las transferencias P2P recibidas del sintético quedan como `ingreso`. La recolección real no tuvo declaraciones del voluntario (0 % del test), así que, por la regla R2 de la taxonomía, toda transferencia con persona queda en `transferencias_p2p`. En el test, de las 28 transferencias P2P, 9 (reglas) y 6 (CTGAN) se predicen como `ingreso`, y 7 y 10 como `movimiento_propio`: en el sintético, la única plantilla de una salida bancaria que nombra una billetera es la de recarga propia, y un envío real del banco a una billetera se le parece. La lección para el protocolo es que el espacio de etiquetas depende de la información disponible al etiquetar: el sintético debe etiquetarse en las mismas condiciones de información que el real. La taxonomía v1.1 ya anticipaba este cruce como un hallazgo esperable. Como análisis exploratorio, *post hoc* y no pre-registrado, fusionar `transferencias_p2p` e `ingreso` sube el F1-macro de 0,566 a 0,617 [0,559; 0,670] (reglas) y de 0,567 a 0,596 [0,537; 0,650] (CTGAN); esto solo dimensiona el choque, y el orden entre reglas y CTGAN no se interpreta.

**Pipeline de referencia.** El pipeline de Pancholi *et al.* queda como contexto, no como fila comparable: solo emite compras, alcanza 8 de las 16 categorías y un clasificador entrenado con su salida tendría un techo de F1-macro de 0,50 por construcción (Sección V). Su desempeño publicado se mide sobre sus propios datos sintéticos, en inglés y con otras categorías, y no es comparable con este TSTR.

### B. Limitaciones
**Del protocolo.** Los archivos públicos no traen segmento ni UPM, por lo que no se reportan intervalos de confianza de diseño sobre cifras del DANE; la ENPH es de 2016-2017 y no registra billeteras ni transferencias, que se introducen por una regla de migración por escenarios sin ancla verificada; los extractos no ven el efectivo (un retiro es una fila, no quince compras), por lo que el TSTR se evalúa sobre el universo bancarizado. La reevaluación del pipeline de referencia ejecutó sus etapas 1–4 (la etapa 4 con un modelo sustituto en una sola corrida, como evidencia indicativa; la etapa 5 de asesoría de inversión queda fuera de alcance). Dos límites propios del CTGAN: genera un 10,78 % de pares categoría–subcategoría inexistentes (no modela bien la jerarquía categórica), y amplifica la elasticidad por encima del *train* (posible sobre-ajuste de la correlación ingreso–monto). El texto sintético se genera por plantillas, más limpias que un extracto real; y el CTGAN se entrena sobre la capa emitida, que ya es sintética, de modo que su fidelidad es a la salida de las reglas, no a la realidad colombiana —la prueba frente a la realidad es el TSTR—.

**De la validación.**
- El brazo LLM no se evaluó sobre el real por la restricción de tratamiento de datos.
- Los pagos PSE sin facturador (4,4 % del marco) no tienen ningún ítem en el test, así que la exactitud ponderada no dice nada de ellos.
- Con n = 200 y 6 grupos de extractos recolectados por conveniencia, la inferencia se limita a estos extractos y el IC por grupo es inestable.
- El marco termina en septiembre de 2026, último mes con IPC incorporado.
- La anotación se hizo sin calibración previa, y las convenciones de los casos no resueltos se fijaron en la adjudicación, antes de ver predicciones.
- El *bootstrap* se corrigió tras la primera corrida oficial (la regla de soporte se recalculaba en cada réplica); las cifras puntuales no cambiaron y el IC anterior se conserva para trazabilidad.
- Las tres comparaciones de la ablación no se corrigen por multiplicidad.
- El token `LLAVE` que deja el anonimizador no existe en el sintético.

## IX. Conclusiones y trabajo futuro
El trabajo entrega un protocolo reproducible para generar extractos bancarios sintéticos calibrado con microdatos del DANE para Bogotá, con *priors* bayesianos jerárquicos por estrato y quintil, medios de pago condicionados a la categoría, y una reevaluación prerregistrada del pipeline de referencia cuya principal diferencia —la conservación de la relación ingreso–monto— se verifica en el refinamiento propio. La validación TSTR responde la pregunta de investigación para estos extractos: un clasificador entrenado solo con sintético alcanza un F1-macro de 0,57 sobre transacciones reales anotadas, frente a 0,06 del azar, una utilidad moderada que no se generaliza a nuevos titulares. Con la misma capa de texto, el generador por reglas y el CTGAN rinden igual, y el principal error proviene de una diferencia de convenciones de etiquetado entre el sintético y el real (transferencias entre personas frente a ingreso) que la taxonomía ya anticipaba.

Trabajo futuro: etiquetar el sintético en las mismas condiciones de información que el real; distinguir `PERSONA` de `TITULAR` en la anonimización; ampliar el número de titulares; evaluar el LLM con autorización explícita para el tratamiento de los datos; y, en el protocolo, extender a otras ciudades, anclar la participación de medios digitales con una fuente primaria, modelar explícitamente la jerarquía categórica en el CTGAN y reemplazar la biblioteca curada de comercios por una capa empírica.

---

## Declaración de uso de herramientas de IA
Este trabajo se apoyó en asistentes de IA para programación, depuración y redacción asistida, bajo la dirección de la autora, quien definió la metodología, tomó las decisiones de diseño, ejecutó el pipeline sobre los microdatos y verificó los resultados. El detalle por fase está en `docs/reporte/declaracion_uso_ia.md`. La reproducibilidad del repositorio (pruebas automatizadas, SHA-256, semillas fijas, cifras generadas por código) permite auditar cada resultado de forma independiente.

## Declaración de ética y consentimiento
Consentimiento informado de los voluntarios y anonimización de los extractos (`docs/datos_reales/`); aval del comité de ética. (En el `.tex` va dentro de VI.B.)

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
Pirámide de estrato (ENPH vs GEIH); matriz medio de pago × categoría; elasticidad de Pancholi por etapa; composición de las filas emitidas por tipo (las cuatro van en el `.tex`). Opcional: matriz de confusión TSTR (`outputs/tstr/tstr/<fuente>/logreg/matriz_confusion.csv`).
