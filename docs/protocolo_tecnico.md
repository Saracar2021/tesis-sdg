# Protocolo técnico — generación de datos sintéticos de transacciones financieras para el contexto colombiano

**Autora:** Sara J. Cárdenas · Maestría en Inteligencia Artificial, Pontificia Universidad Javeriana
**Versión:** 0.1 (borrador para revisión) · **Fecha:** 20 de septiembre de 2026 · **Actividad 1 del cronograma** (diseño formal del protocolo)
**Basado en:** `CLAUDE.md` (v4), `docs/plan_maestro.md` (v2), `docs/fuentes_datos.md`, `outputs/distribuciones/distribuciones_priors.md` y sus CSV.

## Convenciones de este documento

- **VERIFICADO:** comprobado con los datos o con la fuente citada, con evidencia en `outputs/` o `docs/`.
- **INFERIDO / SUPUESTO:** no comprobado; se declara como tal.
- **PENDIENTE:** no está decidido o no se ha hecho. No se rellena con una propuesta propia; solo se enuncia qué falta y qué lo bloquea.
- **Cifras:** cada cifra lleva entre corchetes el archivo de `outputs/` del que sale (o, si no existe salida en `outputs/`, el documento de `docs/`). Toda cifra declara su dominio: **Bogotá urbano** salvo que se indique otra cosa. Ninguna es nacional. Las cifras de este documento **no se comparan** con las del informe de avance, que quedan retiradas (`docs/plan_maestro.md` §6).
- Este documento **no contiene código**. Los módulos que implementan cada etapa se documentan en la bitácora al construirse.

---

## 1. Objetivo y alcance

### 1.1 Objetivo

Diseñar y validar de forma preliminar un **protocolo reproducible** para generar datos sintéticos de transacciones financieras plausibles para Colombia, y medir si esos datos sirven para entrenar clasificadores de transacciones que funcionen sobre transacciones reales (evaluación TSTR: *train on synthetic, test on real*).

El protocolo se organiza en cuatro etapas encadenadas:

1. **Priors bayesianos** calibrados con microdatos del DANE.
2. **Generador por reglas** con nombres de comercio.
3. **CTGAN** entrenado sobre la salida del generador.
4. **Clasificadores + evaluación TSTR** contra transacciones reales etiquetadas.

### 1.2 Qué es colombiano y qué es de Bogotá

| Componente | Alcance |
|---|---|
| El **protocolo** (etapas, reglas de datos, evaluación) | Colombiano y reutilizable |
| La **calibración** (priors) y la **validación empírica** (TSTR) | **Solo Bogotá urbano**, como caso de estudio |
| Generalización a otras ciudades | Trabajo futuro; no se afirma |

**Razón (decisión cerrada, 20 sep 2026):** los 20 voluntarios del componente de datos reales son todos de Bogotá; calibrar contra otro dominio rompería la comparación sintético↔real del TSTR. Las cifras del documento no deben leerse como nacionales.

### 1.3 Fuera de alcance

- **ENPH rural** (6 archivos en `data/raw/ENPH_2017/rural/`): excluido con declaración explícita. Es un instrumento distinto (gasto semanal frente a diario) y los extractos bancarios son urbanos. No se mezcla con urbano.
- **Estimación poblacional** con los datos reales: los 20 voluntarios son una muestra por conveniencia; sirven como conjunto de validación, no como estimación (L8, §6).
- **Transacciones en efectivo no bancarizadas**: los extractos bancarios no las ven (L7, §6).

### 1.4 Motivación empírica y el pipeline de referencia

**El pipeline de Pancholi et al. se ejecutó de forma reproducible** (etapas 1–3; criterios prerregistrados; detalle en `docs/reevaluacion_pancholi.md`, resultados en `outputs/pancholi/`). Los veredictos por hipótesis (H-P1 no concluyente respecto a Colombia, con la salida final del CTGAN sin relación ingreso–monto; H-P2 refutada con la definición prerregistrada / confirmada si el hospedaje cuenta como ocio; H-P3 confirmada para las etapas 1–3, `payment_type` de la etapa 4 no concluyente) están en ese documento. Notas de contexto que siguen vigentes:

- **Sin respaldo, no se citan como resultado:** la diferencia de USD 12 entre perfiles de ingreso, los 5 perfiles y las 149 transacciones, el dominio de categorías de ocio (Athletic Exhibition, Special Events, Inn and Motel, Skating Rink) y el 100 % de `payment_type: credit_card`. Aparecen en el informe de avance (secciones I y III) y en la presentación (diapositivas 2 y 3) sin una ejecución que los sostenga.
- **Citables con referencia al paper**, porque describen su diseño y no sus salidas: demografía del American Community Survey 2015-2019 de Washington D.C. por código postal; nombres de comercio de Yelp y de D.C.; simulación por reglas con gasto calibrado por ingreso y características del hogar; refinamiento con CTGAN. La Tabla 5 del paper muestra 4 transacciones de ejemplo, todas con tarjeta de crédito: es un ejemplo, no una proporción.
- **Las tres limitaciones se contrastaron** (H-P1 ingreso, H-P2 categorías, H-P3 medio de pago) con un experimento reproducible; resultados en `docs/reevaluacion_pancholi.md`. **H-P1 no es «insensibilidad al ingreso»**: el paper declara que calibra el gasto por ingreso y características del hogar, con la distribución de Estados Unidos (ACS 2015-2019 de D.C.). La hipótesis es que la relación ingreso–gasto que produce no corresponde a la de los hogares colombianos, cuya distribución del ingreso y del gasto por quintil es distinta.
- **Qué sostiene la motivación mientras tanto:** la ausencia de conjuntos públicos de transacciones colombianas etiquetadas, y que el pipeline de referencia fue diseñado con fuentes de Estados Unidos (hecho documentado en el paper). Sobre esa base el protocolo es necesario; si además el pipeline falla en ingreso, categorías o medio de pago, lo dice la reevaluación del pipeline de referencia.
- La comparación del TSTR contra Pancholi (hipótesis de la tesis) **exige** ejecutarlo en cualquier caso.
---

## 2. Fuentes de datos y qué calibra cada una

### 2.1 Regla de división de fuentes

**ENPH aporta ingreso (`ICGU`) y gasto. GEIH aporta estructura demográfica y laboral (estrato, formalidad, posición ocupacional).** `INGLABO` **no** es insumo de calibración: solo se reporta de forma descriptiva (`CLAUDE.md`, decisión del 20 sep).

### 2.2 Tabla de fuentes

| Fuente | Periodo | Unidad de análisis (tabla usada) | Dominio | Peso | Qué calibra |
|---|---|---|---|---|---|
| **ENPH** `viviendas_hogares` | 2016-2017 | Hogar | `DOMINIO = 'BOGOTÁ'` (texto, sin código) | `FEX_C` | Estrato de tarifa (`P8520S1A1`); ingreso del hogar (`ICGU`) y sus quintiles; forma de pago principal en gastos frecuentes (`NC2R_CC_P6`) |
| **ENPH** `gastos_menos_frecuentes_medio_pago` | 2016-2017 | Hogar | Bogotá | `FEX_C` | Medio de pago principal **por subcapítulo de gasto** (`P438*`, 29 columnas) |
| **ENPH** `gastos_menos_frecuentes_articulos` (`.txt`) | 2016-2017 | Registro de gasto | Bogotá | agregar a hogar antes de ponderar | Solo para separar no respuesta de no aplica en `P438*` (cruce por `DIRECTORIO + CAP`) |
| **GEIH** `datos_hogar` | 2025, 12 meses | Hogar | `AREA = 11` (Bogotá urbano) | `FEX_C18 / n_meses` | Estrato del hogar (`P4030S1A1`) |
| **GEIH** `ocupados` | 2025, 12 meses | Persona ocupada | `AREA = 11` | `FEX_C18 / n_meses` | Posición ocupacional (`P6430`); componentes de formalidad (`P6440`, `P6450`, `P6920`, `P6990`) |

Los 112 archivos (96 GEIH + 16 ENPH) tienen SHA-256 idéntico al del zip original del DANE [`outputs/normalizar_datos_log.json`; referencia en `docs/fuentes_datos.md` §2]. Los archivos ENPH `.txt` conservan su extensión y **no son CSV**.

### 2.3 Tamaño de muestra en Bogotá (sin ponderar)

| Fuente | Hogares | Otra unidad | Fuente de la cifra |
|---|---|---|---|
| ENPH 2016-2017 | 3.918 (2.555.731 expandidos) | 12.279 personas | `outputs/distribuciones/distribuciones_priors.md` (encabezado); `docs/fuentes_datos.md` §10.2 |
| GEIH 2025 (12 meses) | 9.733 (793–849 por mes) | 13.552 ocupados (1.083–1.196 por mes) | `docs/fuentes_datos.md` §10.2 |

**ENPH es la restricción activa**, y es la fuente del gasto, núcleo de la tesis.

### 2.4 Lo que **no** es comparable entre fuentes

- **`ICGU` (ENPH) vs. `INGLABO` (GEIH):** ingreso del hogar frente a ingreso laboral individual. No son comparables; cada tabla declara cuál usa [`outputs/distribuciones/distribuciones_priors.md`, encabezado].
- **Estrato ENPH vs. GEIH:** misma pregunta («estrato para tarifa»), esquemas de códigos documentados en fuentes distintas (ENPH: Manual ENPH, pregunta 4; GEIH: Diccionario 2025, fila 32). Cada esquema se mapea solo con su fuente.
- **`NC2R_CC_P6` vs. `P438*`:** los códigos difieren en 4 y 5 (ver §3.1). **Nunca mapear uno con el diccionario del otro.**
- **ENPH 2016-2017 vs. GEIH 2025:** ~9 años de diferencia. Composición por estrato agrupado, Bogotá, hogares con respuesta [`outputs/distribuciones/enph_estrato_agrupado.csv`, `geih_estrato_agrupado.csv`]:

| Estrato agrupado | ENPH 2016-2017 | GEIH 2025 | Diferencia GEIH − ENPH (calculada de las dos tablas) |
|---|---|---|---|
| Bajo (1-2) | 44,67 % | 47,26 % | +2,6 p.p. |
| Medio (3-4) | 49,47 % | 45,96 % | −3,5 p.p. |
| Alto (5-6) | 5,87 % | 6,78 % | +0,9 p.p. |

  La diferencia no distingue cambio real de la población de diferencias de instrumento o de calendario; no se interpreta.

### 2.5 Comparabilidad semántica de GEIH 2025 — SUPUESTO DECLARADO

- **Verificado:** los encabezados de las 96 tablas GEIH son idénticos entre meses (8 de 8 módulos, 12/12 meses) [`docs/fuentes_datos.md` §1, §3]. Esto sostiene el apilamiento *técnico*.
- **No verificado:** que las preguntas signifiquen lo mismo en 2025. El control de cambios cubre 2022–2024 (118, 9 y 2 cambios; tendencia decreciente) y el formulario del repositorio es de las etapas 2401–2412; **no hay entradas de 2025** [`docs/fuentes_datos.md` §7]. El diccionario también es de la etapa 2401.
- **Supuesto:** el formulario 2025 es el de 2024 (vigente al iniciar enero 2025, sin evidencia de cambio). **Es una inferencia, no una verificación.**
- **Evidencia corroborante (no prueba):** estabilidad mes a mes de las variables que alimentan los priors [`outputs/distribuciones/geih_estabilidad_mensual.csv`]. Mayores desviaciones: estrato medio (3-4) en julio, 38,00 % frente a 45,96 % de los 12 meses (−7,96 p.p., z binomial simple −4,54); cotiza pensión = «No» en marzo, +4,93 p.p.; afiliado a ARL = «Sí» en marzo, −5,72 p.p. El z binomial **no** incluye efecto de diseño (subestima el error real). No incluye `P6500` ni `P5222S*` (no se usan en este entregable).
- **Pendiente externo:** control de cambios de las etapas 2501–2512 (consulta al DANE; P9 del plan maestro).

---

## 3. Las cuatro etapas

### 3.1 Etapa 1 — Priors bayesianos desde el DANE

**Entradas.** Microdatos ENPH (Bogotá urbano) y GEIH (`AREA = 11`), cargados solo mediante `src/sdg/carga.py`, con las reglas de la §4.

**Salidas.**
- Distribuciones ponderadas de Bogotá urbano [`outputs/distribuciones/*.csv`, 16 tablas con informe y `manifest_distribuciones.json`] — **ya generadas**.
- Módulo de priors (WP3) que las convierte en priors condicionados por celda — **PENDIENTE, sin escribir**.

**Variables y cifras vigentes (Bogotá urbano).**

| Variable | Unidad | Fuente | Cifra clave | Archivo |
|---|---|---|---|---|
| Estrato agrupado (1-2 / 3-4 / 5-6) | Hogar | ENPH y GEIH | ver §2.4 | `enph_estrato_agrupado.csv`, `geih_estrato_agrupado.csv` |
| Quintil de `ICGU` (5) | Hogar | ENPH | Fronteras superiores: Q1 1.127.000 · Q2 1.810.250 · Q3 2.766.667 · Q4 4.506.283 (COP) | `enph_ingreso_quintil.csv` |
| Forma de pago principal, gastos frecuentes (`NC2R_CC_P6`) | Hogar (respuesta única por hogar) | ENPH | Efectivo 97,03 %; débito 1,97 %; crédito 0,48 % (base: 3.517 hogares con respuesta). Sin dato: 11,42 % del total, **no imputado** | `enph_forma_pago_nc2r.csv` |
| Medio de pago principal por subcapítulo (`P438*`) | Hogar (respuesta por subcapítulo) | ENPH | Ejemplos: G14 (electrodomésticos, muebles y enseres) crédito 28,01 % / efectivo 64,33 %; H12 (transporte y comunicaciones) crédito 22,39 % / efectivo 69,52 %; L11 (gastos varios) crédito 0,00 % / efectivo 98,68 % | `enph_p438_matriz_categoria_x_medio.csv` |
| Posición ocupacional (`P6430`) | Persona ocupada | GEIH | Empleado de empresa particular 58,87 %; cuenta propia 30,55 %; empleado del gobierno 4,33 %; patrón 2,77 %; empleado doméstico 2,68 % | `geih_posicion_ocupacional.csv` |
| Formalidad (componentes **separados**) | Persona ocupada | GEIH | Tiene contrato 73,30 %; contrato verbal 19,71 % (de quienes tienen contrato); cotiza pensión 64,08 %; afiliado a ARL 62,59 % | `geih_formalidad_componentes.csv` |

**Cómo se leen las cifras de medio de pago (VERIFICADO; es la advertencia central de la etapa).**
- `NC2R_CC_P6`: «% de **hogares** cuya forma de pago principal declarada es X», acotada al Cuadernillo 2 urbano, sección D2 (gastos diarios, registro de 14 días). No es participación de transacciones ni de gasto. Códigos (Cuadernillo 2 urbano): 1 débito, 2 crédito, 3 efectivo, **4 fiado** (el DDI dice «fiador»: error de rotulado), 5 bonos, 6 otra.
- `P438*`: 29 columnas, una por subcapítulo del Cuadernillo 3 (gastos **menos** frecuentes); cada subcapítulo es categoría × periodo de referencia. Códigos (Cuadernillo 3): 1 débito, 2 crédito, 3 efectivo, **4 bonos, 5 cheques**, 6 otro.
- La cifra «73,1 % de efectivo» del informe de avance está **descartada** (sin dominio y enunciada como % de transacciones); no se reutiliza.

**Vacíos de `P438*`** [`outputs/distribuciones/enph_p438_vacios.csv`]. Se separan **no respuesta** (hay compra sin medio) de **no aplica** (sin compra). Con `FORMA = 1` como «compra», la no respuesta es 0 en los 29 subcapítulos; con «cualquier registro del hogar en el subcapítulo» aparece no respuesta (p. ej. L12: 29,12 % de los hogares con registro). **`FORMA = 1` = compra es INFERIDO** (el cuadernillo lista las formas por letra, sin imprimir los números); por eso se reportan ambas definiciones.

**Esquema de celdas de calibración (decisión cerrada).** Estrato agrupado en 3 × quintil de `ICGU` en 5 = **15 celdas**. El cruce estrato (6) × quintil (5) dejaba 12 de 30 celdas con menos de 30 hogares [`docs/fuentes_datos.md` §10.3 A]. Tras agrupar, quedan **4 de 15** celdas con menos de 30 hogares, todas de estrato alto (5-6) en Q1–Q4 (n = 9, 5, 13 y 21; Q5 tiene 168) [`outputs/distribuciones/enph_estrato_x_quintil.csv`, columna `n_menor_30`]. Las 11 celdas restantes tienen al menos 129 hogares.

**Respaldo jerárquico para celdas ralas.** Cuando una celda no tenga soporte suficiente en Bogotá, su prior se encoge hacia la distribución **urbana nacional** de ENPH en vez de inventar la celda. En el cruce urbano nacional ninguna de las 15 celdas tiene menos de 30 hogares (mínimo 71) [`docs/fuentes_datos.md` §10.3 C; no hay tabla equivalente en `outputs/`, PENDIENTE generarla]. Se documenta como ventaja del enfoque bayesiano, no como parche.

**Supuestos de la etapa.**
1. Los quintiles se calculan **dentro de Bogotá** con `ICGU` ponderado; los valores iguales a un corte quedan en el quintil inferior (por eso los % por quintil no son exactamente 20) [`enph_ingreso_quintil.csv`]. En `ICGU` ninguna frontera concentra más de 0,09 % del peso en un valor [`fronteras_amontonamiento.csv`].
2. Los priors de medio de pago describen **hogares**, y el generador los usará para emitir **transacciones** (ver riesgo en D9, §5).
3. `P438*` y `NC2R_CC_P6` cubren categorías distintas (menos frecuentes / frecuentes); ninguno cubre todo el gasto.

**PENDIENTE en esta etapa.**
- **Umbral de soporte.** El valor «30 hogares» de `n_menor_30` es solo una marca informativa (`min_n_celda_marca` en `manifest_distribuciones.json`), **no** el umbral. Se fija en WP3.
- **Método de encogimiento** (forma funcional, hiperparámetros del prior) y lista de celdas afectadas: WP3; irán a `outputs/`.
- **Priors por celda para el medio de pago.** Las tablas de `P438*` y `NC2R_CC_P6` en `outputs/` son **marginales de Bogotá**; ninguna está condicionada por estrato × quintil. Falta calcularlas por celda y su respaldo urbano nacional (mismos subcapítulos son ralos: p. ej. J13 tiene 201 hogares con respuesta en todo Bogotá [`enph_p438_matriz_categoria_x_medio.csv`]).
- **Papel de GEIH en la generación.** GEIH y ENPH no comparten unidades, así que no puede cruzarse `INGLABO`/formalidad con `ICGU`. Cómo entran concretamente estrato, posición ocupacional y formalidad de GEIH al generador (y si se usan para ajustar la composición ENPH 2016-2017 a 2025) no está decidido.
- **Distribución de montos y frecuencias de transacción.** No hay decisión ni salida en `outputs/`.
- **Correspondencia subcapítulos ENPH ↔ categorías de la taxonomía colombiana.** Depende de la taxonomía v1.1 (§3.2).

**Criterio de aceptación previsto (plan maestro, 23 sep):** pruebas de que los priors reproducen las marginales de §3.1. La tolerancia numérica es **PENDIENTE**.

---

### 3.2 Etapa 2 — Generador por reglas con nombres de comercio

**Entradas.** Priors de la Etapa 1; taxonomía colombiana; lista de nombres de comercio.

**Salidas.** Muestra sintética generada por reglas (hito del plan maestro: viernes 25 sep, punto de control con la directora).

**Lo que está decidido.**
- El generador **condiciona el medio de pago a la categoría de gasto** usando la matriz `P438*` [`enph_p438_matriz_categoria_x_medio.csv`]. Motivo: el medio de pago varía por categoría (crédito de 0,00 % en L11 a 28,01 % en G14).
- Para los gastos frecuentes, la única evidencia ENPH es `NC2R_CC_P6`, que es **una respuesta por hogar**, no por categoría.
- Para las categorías sin medio de pago observado **no se toma prestado de otro subcapítulo sin declararlo**: J14 (24,16 % de los hogares con registros) y K11 (13,80 %) no tienen columna `P438` [`enph_p438_gaps.csv`; 31,92 % de los hogares tiene al menos un registro en uno de los dos, `distribuciones_priors.md`].
- **D15 (22 sep 2026, cerrada): el generador emite extractos sintéticos.** Internamente simula el gasto completo del hogar, calibrado con ENPH (categoría, monto, medio de pago); solo **emite** lo que registraría un banco o billetera (compras con tarjeta, PSE, transferencias, billeteras, ingresos y retiros en cajero). Las compras en efectivo se acumulan en la capa interna y salen como retiros periódicos. Detalle, justificación y supuestos declarados en §5, D15.

**Taxonomía.** Existe la v1 (`docs/taxonomia/taxonomia_gastos_colombia_v1.md/.json`), generada con ayuda de IA y con correcciones factuales identificadas (`docs/taxonomia/pendientes_v1.1.md`). Se congela v1.1 solo cuando (1) esté cerrada la verificación de `P438*` y (2) se hayan revisado ≥ 50 descripciones reales de extractos. Ver §8 sobre el estado de esas correcciones.

**PENDIENTE en esta etapa.**
- **Esquema de la transacción** (campos, tipos, granularidad temporal). Los documentos fuente solo fijan que existen categoría, medio de pago y nombre de comercio.
- **Fuente de los nombres de comercio** y su mapeo a categorías.
- **Fuente para medios digitales** (billeteras, transferencias): ENPH 2016-2017 no los trae (L4). **Supuesto declarado (D15, §5):** se usará el Banco de la República (Banrep 2024) como fuente de participación de medios digitales. Las cifras concretas y su incorporación al generador quedan **PENDIENTES** (WP6).
- **Reglas de generación** (estructura, jerarquía de condicionamiento): las define WP6. Con D15 cerrada, deben implementar la capa interna de gasto del hogar (calibrada con ENPH) y la capa de emisión de extracto (bancarizada); ver §5, D15.

---

### 3.3 Etapa 3 — CTGAN

**Entradas.** Muestra generada por reglas (Etapa 2), según el orden del pipeline de `CLAUDE.md`. Los datos reales **no** se usan para entrenar: se reservan para la evaluación (§7).

**Salidas.** Dataset sintético v1 con ≥ 5.000 transacciones; `outputs/manifest.json` con versiones, semillas, commit, parámetros y entorno CPU/GPU.

**Reproducibilidad.** `SEED = 42` global (random, numpy, torch, CTGAN); rutas relativas; versiones fijas en `requirements.txt`. `torch`, `ctgan` y `jupyter` **aún no están fijados** en `requirements.txt` (se fijan al instalarse; `docs/bitacora.md`).

**PENDIENTE (no hay decisión ni dato).**
- **Arquitectura y parámetros del CTGAN** (dimensiones de las redes, épocas, tamaño de lote, tratamiento de variables condicionales y de texto como el nombre de comercio).
- **Qué variables entran al CTGAN** y cuáles se condicionan.
- **Métricas de fidelidad** (ver §7.2).
- **Criterios de rechazo** de muestras sintéticas (violaciones de las reglas de la Etapa 2).
- **Cómputo:** disponibilidad de GPU (R3 del plan maestro).

---

### 3.4 Etapa 4 — Clasificadores y evaluación TSTR

**Entradas.** Dataset sintético (Etapa 2 y/o 3: **PENDIENTE** cuál se usa para entrenar cada clasificador); transacciones reales de los voluntarios, **solo** anonimizadas (`data/reales_anon/`), etiquetadas por dos anotadores.

**Salidas.** Métricas TSTR por clasificador; comparación con el pipeline de referencia (Pancholi); Kappa entre anotadores.

**Clasificadores (plan maestro §10).** Tres: regresión logística con TF-IDF; BETO; LLaMA 3 con pocos ejemplos (*few-shot*). Este último no se entrena; su acceso (API de Groq) está **por confirmar** (R3).

**PENDIENTE.**
- **Etiqueta objetivo:** qué dimensión(es) de la taxonomía clasifican los modelos (categoría de gasto, medio de pago, otras). Se cierra con la taxonomía v1.1.
- **Hiperparámetros** de los clasificadores y su protocolo de ajuste. Ajustar sobre sintético no debe filtrar información del conjunto real.
- **Tamaño del conjunto real y de la muestra a anotar:** no está definido (anotar una muestra, no todo). Con 20 voluntarios, el volumen depende de los extractos que lleguen.
- **Partición y control de fuga:** no se detectaron hogares repetidos entre meses en GEIH, pero las viviendas vecinas pueden compartir características (hipótesis no verificada) [`docs/fuentes_datos.md` §11.5]. Cómo se particiona el conjunto real (por voluntario u otra unidad) queda por decidir.
- **Regla de soporte ≥ 10** para F1 macro por clase: a revisar cuando se conozca el tamaño real del corpus anotado (`pendientes_v1.1.md`).

---

## 4. Reglas de ponderación y de unión (no negociables)

### 4.1 Factores de expansión

| Fuente | Factor | Regla | Verificación |
|---|---|---|---|
| GEIH 2025 | `FEX_C18` | Al apilar meses: `FEX_C18 / n_meses` con el `n_meses` **realmente cargado** (12 normalmente; 11 en las corridas de sensibilidad). Nunca una constante | Suma mensual de `FEX_C18` casi constante entre meses [`docs/fuentes_datos.md` §11.5] |
| ENPH 2016-2017 | `FEX_C` | **Factor del hogar/vivienda.** Sirve para cifras por hogar y por persona | VERIFICADO: constante por `DIRECTORIO` e igual al de `viviendas_hogares` en 10 tablas (100 % de filas) [`outputs/fex_enph_verificacion.json`]. Metodología ENPH §2.2.4.1. **No cubre rural; no se contrastó contra un total poblacional externo** |

- En tablas de **registros de gasto**, cada fila lleva el factor de su hogar: hay que **agregar primero a hogar** y luego ponderar. Ponderar filas de gasto sueltas produce cifras mal calculadas.
- Todo cálculo sobre microdatos del DANE usa factores de expansión; **cero cifras hardcodeadas** (toda cifra sale de código y queda en `outputs/`).
- **No se reportan intervalos de confianza sobre cifras DANE:** los archivos públicos no traen segmento ni UPM (L1).

### 4.2 Llaves y uniones — GEIH y ENPH no comparten regla

| | GEIH | ENPH |
|---|---|---|
| Identificador de hogar | `DIRECTORIO + SECUENCIA_P + HOGAR` | **Solo `DIRECTORIO`** |
| Persona | + `ORDEN` | `DIRECTORIO + ORDEN` en `caracteristicas_generales_personas` |
| Registro de gasto | n/a | `DIRECTORIO + SECUENCIA_ENCUESTA + SECUENCIA_P` |
| Mismo módulo entre meses | Apilar | n/a |
| Módulos distintos | Unir por la llave de hogar (+ `ORDEN`) | Gasto → hogar por `DIRECTORIO` (uno-a-muchos) |

Aplicar la regla de GEIH a ENPH enlaza apenas 7–9 % de las filas urbanas de gasto (p. ej. 8,72 % en `gastos_diarios_hogar.txt`) **en silencio** [`docs/fuentes_datos.md` §4]. En ENPH `ORDEN` de las tablas de gasto **no** es la persona: el DDI no lo define.

**Regla operativa:** nunca «todo con todo». Tras cada unión se verifica y reporta el % de filas enlazadas; si no es ~100 %, se detiene el proceso. El cargador (`src/sdg/carga.py`) lo hace y bloquea rural; 29 pruebas automatizadas (`tests/`) [`docs/bitacora.md`].

### 4.3 Unidad de análisis

Cada tabla declara unidad y dominio. GEIH: 7 módulos son persona y `datos_hogar` es hogar. ENPH: solo `viviendas_hogares`, `gastos_menos_frecuentes_medio_pago` (hogar) y `caracteristicas_generales_personas` (persona) tienen una fila por unidad; **los otros 13 archivos son registros de gasto** (hasta 42,5 filas por hogar).

### 4.4 Dominio y códigos

- **Bogotá urbano en GEIH:** `AREA = 11` (Diccionario 2025, fila 169). **No `DPTO = 11`**: suma 237 hogares rurales con `AREA` vacía y rompe la comparabilidad con ENPH urbano [`docs/fuentes_datos.md` §10.1].
- **Bogotá en ENPH:** `DOMINIO = 'BOGOTÁ'` (texto sin código). **Respaldo documental débil**: ni el `.sav` ni el DDI traen etiquetas y los cuadernillos no mencionan Bogotá. Se declara así.
- **Estratos:** los códigos 0, 9 y vacío **no son estratos**; no se agrupan y se reportan como sin dato. ENPH `P8520S1A1`: 0 = conexión pirata, 9 = no establecible o planta eléctrica (Manual ENPH, pregunta 4). GEIH `P4030S1A1`: rango 0–6 ó 9, sin etiquetas para 0 ni 9 (Diccionario, fila 32).
- **Contrato GEIH:** `P6440` (1 sí, 2 no); `P6450` (1 verbal, 2 escrito, **9 no sabe**, no 3).
- **Etiquetas:** los CSV del DANE no traen etiquetas de valor; toda recodificación cita su fuente. El DDI de GEIH está desactualizado y no se usa como fuente de conteos ni etiquetas 2025.
- **Lectura de archivos:** GEIH `cp1252`; ENPH `.csv` `utf-8-sig`; ENPH `.txt` `utf-8` con tabulador.
- **Datos personales:** solo la versión anonimizada en `data/reales_anon/`; los datos crudos nunca se leen. `data/raw/` y `data/_descargas/` son de solo lectura.

---

## 5. Decisiones metodológicas y justificación

| # | Decisión | Justificación | Evidencia / dónde queda registrada |
|---|---|---|---|
| D1 | **Dominio Bogotá urbano**; rural fuera | Los 20 voluntarios son de Bogotá; el TSTR exige el mismo dominio en sintético y real | `CLAUDE.md`; `docs/plan_maestro.md` §4 |
| D2 | **Protocolo colombiano, calibración sobre Bogotá** como caso de estudio | Evita presentar cifras bogotanas como nacionales | `CLAUDE.md` |
| D3 | **Llave de hogar ENPH = `DIRECTORIO`** | La llave de GEIH enlaza 7–9 % de filas urbanas de gasto en silencio | `docs/fuentes_datos.md` §4 |
| D4 | **ENPH aporta ingreso y gasto; GEIH, estructura demográfica y laboral; `INGLABO` solo descriptivo** | `INGLABO` es ingreso laboral individual, no del hogar; sus fronteras son inestables por amontonamiento en valores redondos (hasta 5,92 % del peso en un solo valor; `ICGU` máx. 0,09 %) | `outputs/distribuciones/fronteras_amontonamiento.csv` |
| D5 | **Estrato agrupado en 3 (1-2, 3-4, 5-6)** | 6 × 5 dejaba 12 de 30 celdas con < 30 hogares en ENPH Bogotá; estrato e ingreso están muy correlacionados, por lo que agrupar pierde poca información | `docs/fuentes_datos.md` §10.3 A y C; `enph_estrato_x_quintil.csv` |
| D6 | **Se conservan los 5 quintiles de `ICGU`** | La hipótesis de la tesis incorpora las proporciones de gasto por quintil de ingreso observadas en Colombia (informe de avance, §IV.B): calibrar por quintil con datos colombianos es parte central del protocolo. No se justifica con una falla atribuida a Pancholi (§1.4) | `CLAUDE.md` |
| D7 | **Celdas ralas → encogimiento hacia urbano nacional** | Bogotá reduce el n; el respaldo evita inventar celdas | `CLAUDE.md`; umbral y método **PENDIENTES** (WP3) |
| D8 | **12 meses de GEIH (incluye diciembre, marzo y julio)** con sensibilidades | Ver detalle abajo | `outputs/distribuciones/geih_sensibilidad_{diciembre,julio,marzo}.csv`; `docs/bitacora.md` |
| D9 | **Medio de pago por categoría, no un % global** | El medio varía por categoría; un porcentaje global de efectivo esconde esa estructura | `enph_p438_matriz_categoria_x_medio.csv` |
| D10 | **Formalidad: componentes por separado, sin indicador propio** | Un compuesto inventado no es defendible; si hace falta una sola variable se usa la definición oficial del DANE, citándola | `CLAUDE.md` (decisión del 20 sep) |
| D11 | **No respuesta declarada aparte, sin imputar** | Imputar la no respuesta como efectivo es un supuesto sin sustento | `enph_forma_pago_nc2r.csv` (11,42 % sin dato) |
| D12 | **Sin intervalos de confianza sobre cifras DANE** | No hay segmento ni UPM en los archivos públicos | L1 |
| D13 | **Reconstrucción desde cero de la base empírica** | El análisis anterior tenía cifras a mano, sin factores de expansión y con un solo mes; queda en `docs/historico/` como referencia de solo lectura | `docs/plan_maestro.md` §2 |
| D14 | **Los datos reales solo evalúan; nunca calibran el generador** | Si los mismos extractos calibran y evalúan, el TSTR queda contaminado; el generador se calibra solo con ENPH y GEIH | `docs/plan_maestro.md` §4; `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md` |
| D15 | **Universo del generador: extractos sintéticos con capa interna de gasto del hogar** (22 sep 2026, cerrada) | La pregunta de investigación es clasificar transacciones reales de usuarios, que son filas de extracto; un generador que emitiera el gasto total incluiría registros que no existen en ningún sistema real | `docs/plan_maestro.md` R10; detalle abajo |

**Detalle de D8 (12 meses).** Decisión del 20 sep 2026, cerrada.
- **Diciembre** tiene −2,5 % de personas y −1,0 % de hogares frente a la mediana de los otros meses, sin explicación documental; los `FEX_C18` compensan y los totales expandidos no caen [`docs/fuentes_datos.md` §8]. Sensibilidad sin diciembre: 86 comparaciones, 4 con diferencia > 1,0 p.p., todas en grupos de `INGLABO`; el corte c1 pasa de 1.300.000 a 1.200.000 (8,33 % relativo) [`geih_sensibilidad_diciembre.csv`].
- **Julio:** 86 comparaciones, 7 con diferencia > 1,0 p.p. [`geih_sensibilidad_julio.csv`]: 4 en `INGLABO` (mismo efecto de frontera) y 3 en la celda posición ocupacional × cotiza pensión (empleado doméstico y patrón), que son celdas pequeñas e inestables ya declaradas. **Estrato agrupado: máx. 0,73 p.p.; componentes de formalidad: máx. 0,29 p.p.** El estrato 3 de Bogotá cae a 26,04 % en julio [`outputs/julio/julio_estrato.md`]; la anomalía se repite, más fuerte, en las 23 ciudades y no es «sin dato»: es un desplazamiento 3 → 1-2.
- **Marzo:** 2 comparaciones > 1,0 p.p., ambas en posición × pensión de «patrón» (−2,64 y +3,05 p.p.) [`geih_sensibilidad_marzo.csv`]. Estrato agrupado: máx. 0,31 p.p. La cifra de formalidad sin marzo (0,52 p.p.) proviene de `docs/bitacora.md`, no se re-verificó al redactar este documento.
- **Por qué no se detiene el análisis:** lo único que supera 1 p.p. en los insumos de calibración es `INGLABO`, que no calibra nada (D4); las familias de ENPH (`ICGU`, forma de pago) no dependen de los meses de GEIH. Marzo y julio quedan como **anomalías declaradas**. No se investigan más las causas sin el control de cambios 2501–2512 del DANE. Las variables no son independientes: los hallazgos no se leen como 118 hallazgos.

**Detalle de D15 (universo del generador).** Decisión del 22 sep 2026, cerrada. Reemplaza la antigua decisión abierta DP1 (dos opciones sin elegir); resuelve R10 (`docs/plan_maestro.md`).

- **Arquitectura de dos capas.** (1) Una capa interna simula el gasto **completo** del hogar, calibrada con ENPH (categoría, monto, medio de pago; §2-§3.1). (2) Una capa de emisión filtra esa simulación y **solo saca lo que un banco o billetera registraría**: compras con tarjeta débito/crédito, PSE, transferencias, movimientos de billetera, ingresos y retiros en cajero. El gasto que la capa interna asignó a efectivo no desaparece: se acumula y sale como **retiros periódicos** en la capa de emisión.
- **Justificación.** La pregunta de investigación de la Etapa 4 es clasificar **transacciones reales de usuarios**, que son filas de un extracto bancario o de billetera. La opción alternativa (emitir el gasto total del hogar, incluido el efectivo como filas de compra) entrenaría los clasificadores con registros que **no existen en ningún sistema real** (nadie ve "compró pan por $3.000 en efectivo" como una fila de extracto): el TSTR mediría un desajuste de universo, no la calidad del sintético. La capa interna evita perder la calibración de ENPH; la capa de emisión evita ese desajuste.
- **Supuestos declarados (nuevos, sin resolver aún — WP6):**
  - **Cadencia y tamaño de los retiros** que representan el efectivo acumulado (cuántos retiros al mes, de qué monto): no hay fuente DANE para esto; se definirá como regla propia y se declarará como supuesto, no como cifra oficial.
  - **Participación de medios digitales** (billeteras, transferencias): ENPH 2016-2017 no las mide (L4). Se usará el Banco de la República (Banrep 2024) como fuente; cifras exactas y su incorporación al generador, **PENDIENTES** (WP6).
  - **Cuenta principal del voluntario:** se asume que cada hogar/voluntario opera desde una sola cuenta o billetera principal a efectos de generar el extracto (simplificación declarada; no hay evidencia de cuántas cuentas usa un hogar bogotano típico).
  - **Medio de pago no observable para categorías dentro de subcapítulos mezclados (L17):** para `telecom_conectividad` y las porciones de `transporte`, `educacion`, `obligaciones_financieras`, `entretenimiento` y `comidas_fuera` que caen en un subcapítulo P438 compartido con otra categoría (H11, H12, E11, I12, J11 confirmados; ver L17), la capa de emisión no puede tomar de ENPH un medio de pago específico de esa categoría — solo el del subcapítulo completo. Se necesitará un supuesto propio para esas categorías, no un dato de ENPH.
- **Formulación de la hipótesis H-P3 sobre Pancholi con D15.** *(Corregido el 22 sep: una versión anterior afirmaba que el paper «lista como limitación que su generador no genera efectivo» y que el pipeline «asume que todo el gasto pasa por tarjeta de crédito»; ninguna de las dos está en el paper ni sale de una ejecución.)* Con D15, la hipótesis se formula en términos de registros de extracto: en Bogotá el gasto dominante en efectivo (L7; 97,03 % de hogares lo declara como forma de pago principal en gastos frecuentes, `enph_forma_pago_nc2r.csv`) **sí aparece** en los extractos reales, pero como retiros en cajero, transferencias a personas y movimientos de billetera — no como filas de compra. Es una hipótesis sobre Pancholi (H-P3, `docs/plan_maestro.md` §6) que la reevaluación del pipeline de referencia contrasta en esos mismos términos: no basta con que el pipeline de referencia no tenga una categoría "efectivo"; hay que ver si su salida refleja la estructura real de retiros y transferencias. Lo único documentado es que la Tabla 5 del paper muestra 4 transacciones de ejemplo con tarjeta de crédito. **Límite adicional (L17):** para las categorías cuyo subcapítulo ENPH mezcla con otra (arriba), la comparación de H-P3 en términos de medio de pago no tiene con qué contrastarse desde ENPH; se sostiene solo para las categorías cuyo subcapítulo no mezcla.
- **Consecuencia para los priors (WP3, población bancarizada).** El generador ya no calibra sobre "todos los hogares de Bogotá" sino sobre **hogares bancarizados**: solo esos producen extractos. Se calculó la tenencia de productos financieros con la batería `P5222S*` de GEIH `datos_hogar` (Bogotá, 12 meses, `FEX_C18/12`; códigos verificados contra el Diccionario GEIH 2025, filas 93-104): **93,47 % de los hogares de Bogotá tiene al menos un producto financiero; 6,53 % declara «Ninguno» (P5222S9)** [`geih_bancarizacion_total.csv`]. Por estrato agrupado, el % **sin** ningún producto es 9,37 % (bajo 1-2), 4,54 % (medio 3-4) y 0,27 % (alto 5-6) [`geih_bancarizacion_x_estrato.csv`]: la bancarización sube con el estrato, como es esperable. El perfil estrato × quintil de ENPH (`enph_estrato_x_quintil.csv`) se reponderó por `P(bancarizado | estrato agrupado)` de GEIH, la única variable común entre las dos fuentes, dando `enph_estrato_x_quintil_bancarizado.csv`. **Supuesto de independencia condicional (declarado, no verificable con estas fuentes):** dentro de cada estrato agrupado, el quintil de `ICGU` es independiente de la tenencia de productos financieros — ENPH no tiene `P5222S*` y GEIH no tiene `ICGU`, así que el cruce real no se puede calcular directamente.
- **Riesgo residual** (`docs/plan_maestro.md` R10): la validez de los supuestos de retiros y de medios digitales queda sin verificar hasta que WP6 los implemente y, si llegan extractos reales, se puedan contrastar contra ellos.

**Riesgo asociado a D9 (declarado de frente).** El prior de medio de pago es una respuesta **por hogar** («¿cuál fue el medio principal en este subcapítulo?»), y el generador emite **transacciones**. La equivalencia entre «medio principal del hogar» y «participación del medio entre transacciones» **no está demostrada** y no se asume; el generador usará la matriz como condicionante, no como frecuencia de transacciones. Cómo se traduce formalmente es PENDIENTE (WP3/WP6).

---

## 6. Limitaciones

| # | Limitación | Consecuencia | Dónde se soporta |
|---|---|---|---|
| L1 | Los archivos públicos de GEIH y ENPH **no traen segmento ni UPM** | No hay errores estándar de diseño; no se reportan intervalos sobre cifras DANE. Los errores ingenuos subestiman la incertidumbre (muestreo por conglomerados de ~10 viviendas) | `docs/fuentes_datos.md` §11.5 |
| L2 | **Marzo y julio de 2025** con anomalías sin explicación documental | Se usan los 12 meses; efecto < 1 p.p. en los insumos de calibración; quedan declaradas | §5, D8 |
| L3 | **Comparabilidad semántica GEIH 2025 sin verificar** | Supuesto declarado; consulta al DANE por las etapas 2501–2512 | §2.5 |
| L4 | **ENPH es de 2016-2017**: ~9 años frente a GEIH 2025, y sin billeteras digitales ni transferencias entre sus medios de pago | Se declara qué calibra cada fuente; los medios digitales necesitan fuente complementaria (**PENDIENTE**) | §2.4; `docs/plan_maestro.md` §7 |
| L5 | **Cobertura faltante de medio de pago:** J14 y K11 existen en artículos pero no tienen columna `P438` (24,16 % y 13,80 % de los hogares de Bogotá con registros). Además, la correspondencia de `P438J13` con un bloque del cuadernillo **no está verificada** | La matriz tiene dos huecos; no se rellenan desde otro subcapítulo sin declararlo | `enph_p438_gaps.csv` |
| L6 | **Amontonamiento** de `INGLABO` en valores redondos | Fronteras de grupo inestables; no calibra nada; no se cambió a cortes fijos | `fronteras_amontonamiento.csv` |
| L7 | **Los extractos bancarios no ven el efectivo** (un retiro es una fila, no quince compras) | El TSTR se evalúa sobre el universo bancarizado, sin extrapolar al gasto total; `medio_pago = efectivo` queda subrepresentado en el real frente a ENPH | `pendientes_v1.1.md` |
| L8 | **20 voluntarios por conveniencia** | Diversidad, no representatividad; conjunto de validación, no estimación poblacional | `docs/plan_maestro.md` §7 |
| L9 | **Los priors de medio de pago son de hogares, no de transacciones**, y `NC2R_CC_P6` cubre solo el cuadernillo 2 | No se interpretan como participación de transacciones ni de gasto | §3.1, §5 |
| L10 | **No respuesta de ítem no corregida** por la expansión: 11,42 % de los hogares sin dato en `NC2R_CC_P6`; se reportan porcentajes sobre la base con respuesta y sobre el total | Los % sobre respuesta suponen que quien no responde no difiere; no verificado | `enph_forma_pago_nc2r.csv` |
| L11 | **`FORMA = 1` = compra es inferido** | Se reporta con dos definiciones de base de compra | `enph_p438_vacios.csv` |
| L12 | **Tamaño de muestra de Bogotá en ENPH** (3.918 hogares) | Categorías con pocos hogares dan % expandidos poco fiables (p. ej. `NC2R_CC_P6` código 5 «bonos»: 1 hogar; 4 «fiado»: 4 hogares) | `enph_forma_pago_nc2r.csv` |
| L13 | **Rotación de la muestra GEIH: PENDIENTE (parcial).** Verificado: ningún hogar aparece en más de un mes (9.733 hogares únicos = filas apiladas en Bogotá) y la prueba por composición no muestra exceso de coincidencias. No verificado: que el diseño no revisite hogares dentro del año; `DIRECTORIO` parece un contador por mes | No se detectó nada que contradiga apilar los 12 meses; la varianza puede subestimarse | `docs/fuentes_datos.md` §11 |
| L14 | **Diciembre con menos filas, sin explicación** | Sensibilidad realizada (D8) | `docs/fuentes_datos.md` §8 |
| L15 | **Respaldo documental débil del dominio ENPH** | `DOMINIO = 'BOGOTÁ'` sin código numérico | §4.4 |
| L16 | **Repeso a hogares bancarizados (D15) asume independencia condicional** entre quintil de `ICGU` y tenencia de productos financieros, dentro de cada estrato agrupado | No verificable con estas fuentes: ENPH no tiene `P5222S*` y GEIH no tiene `ICGU` | §5, D15; `enph_estrato_x_quintil_bancarizado.csv` |
| L17 | **El medio de pago de `P438` se pregunta por subcapítulo, no por artículo; en los subcapítulos que mezclan categorías de la taxonomía, el medio de pago de cada categoría por separado no es observable** | Afecta la calibración de medios de pago de la capa de emisión (D15) y la comparación contra Pancholi en esos mismos términos (H-P3). Detalle abajo | Cuadernillo 3 (pregunta 6, impresa en cada subcapítulo); `tools/calculos_diseno_muestral.py` |

**Detalle de L17 (medio de pago por subcapítulo, no por artículo).** Verificado el 22 sep 2026
contra el texto impreso del Cuadernillo 3 (`data/raw/ENPH_2017/_metadatos/CUADERNILLOS/Cuadernillo 3.pdf`).

La pregunta que genera `P438` está impresa igual, una vez por subcapítulo, en las ~29 páginas del
cuadernillo:

> **(6) El medio de pago usado principalmente para comprar los artículos y servicios enunciados en
> este subcapítulo fue: [...]**

No es una pregunta por artículo: es **una sola respuesta que cubre todos los artículos listados en
el subcapítulo**. Consecuencias:

a. **Todo prior de medio de pago derivado de ENPH está a nivel de subcapítulo** y describe el
   medio **principal declarado** para ese subcapítulo, no la distribución de transacciones por
   medio de pago (esto ya estaba declarado para `P438` y `NC2R_CC_P6` en general, §3.1; L17 lo
   hace más específico).
b. **Cuando un subcapítulo mezcla artículos de categorías distintas de la taxonomía, el medio de
   pago de cada categoría por separado no es observable en ENPH**, con ningún nivel de
   agregación: el problema es del cuestionario (una sola respuesta para el subcapítulo completo),
   no de cómo se procesan los datos después.
c. **Afecta a D15** en la calibración de medios de pago de la capa de emisión (el generador no
   puede tomar de ENPH un medio de pago específico de `telecom_conectividad` ni de las porciones
   mezcladas de `transporte`, `educacion`, `obligaciones_financieras`, `entretenimiento` y
   `comidas_fuera` listadas abajo) y **a H-P3** (la comparación contra Pancholi en términos de
   medio de pago por categoría solo puede sostenerse con las categorías cuyo subcapítulo ENPH no
   mezcla; para las mezcladas, la hipótesis no tiene con qué contrastarse desde ENPH).

**Subcapítulos con mezcla confirmada contra el texto impreso** (no es una lista completa: ver
`outputs/diseno_muestral/e_mezcla_categorias_p438_preliminar.csv` para los candidatos detectados
por código pero sin confirmar, PD19):

| Subcapítulo | Título impreso | Categorías que mezcla | Ejemplos de artículos |
|---|---|---|---|
| H11 | Servicio telefónico, internet y pasajes | `transporte` + `telecom_conectividad` | Parqueadero, peajes, pasaje en bus/tren/avión (transporte); recargas de celular, internet fijo, llamadas de larga distancia, suscripciones web (telecom) |
| H12 | Teléfonos y otros artículos relacionados con las comunicaciones y transporte | `telecom_conectividad` + `transporte` | Teléfonos (telecom); artículos de transporte del mismo subcapítulo |
| E11 | Pensiones, transporte y artículos escolares | `educacion` + `transporte` | Pensiones, artículos escolares (educación); transporte escolar (transporte) |
| I12 | Gastos relacionados con servicios para vehículo, seguros e impuestos | `transporte` + `obligaciones_financieras` | Mantenimiento y servicios para el vehículo (transporte); seguros e impuestos del vehículo (obligaciones financieras) |
| J11 | Bebidas alcohólicas, entradas a cine, teatro, museos, bibliotecas y otros, alojamiento, libros y CD | `entretenimiento` + `comidas_fuera` | Cine, teatro, museos, libros, CD (entretenimiento); alojamiento (mismo grupo COICOP que hoteles y restaurantes, 11, que es la fuente de `comidas_fuera`) |

**Cómo se hizo esta verificación:** lectura del texto impreso de cada subcapítulo (`pdftotext`)
contra su título y lista de artículos; no se infirió de los códigos. Un intento de detectar
automáticamente el resto de los subcapítulos mezclados, por prefijo COICOP de `P10270`
(`tools/calculos_diseno_muestral.py`, función `mezcla_categorias_p438`), **no es confiable para
todos los casos**: el subcapítulo E12 (título 100 % educación) clasifica por código como 43 %
"entretenimiento" / 28 % "vestuario" / 22 % "educación", lo que prueba que el mapeo de 2 dígitos
de COICOP no basta para las divisiones 02, 09 y 12. Esa detección queda en
`outputs/diseno_muestral/e_mezcla_categorias_p438_preliminar.csv`, marcada como preliminar, y no
se usa aquí como hallazgo.

---

## 7. Plan de evaluación

### 7.1 Por etapa

| Etapa | Qué se evalúa | Criterio | Estado |
|---|---|---|---|
| **1 Priors** | Que el módulo reproduce las marginales de las distribuciones de Bogotá (§3.1) | Comparación contra `outputs/distribuciones/*.csv`; pruebas automatizadas | Tolerancia **PENDIENTE**; previsto 23 sep |
| **1 Priors** | Encogimiento en celdas ralas | Lista de celdas afectadas y umbral declarados en `outputs/` | **PENDIENTE** (WP3) |
| **2 Reglas** | Consistencia interna: respeta el medio de pago por categoría y la taxonomía | Muestra sintética funcionando; punto de control con la directora | Previsto 25 sep; métricas **PENDIENTES** |
| **3 CTGAN** | Fidelidad del dataset sintético v1 (≥ 5.000 transacciones) frente a su fuente (Etapa 2) | **Métricas de fidelidad PENDIENTES**: no hay decisión de cuáles ni con qué umbral | **PENDIENTE** |
| **4 TSTR** | Desempeño de los 3 clasificadores entrenados en sintético y evaluados en real anotado | F1 macro (con regla de soporte ≥ 10, a revisar); otras métricas **PENDIENTES** | **PENDIENTE** (semana del 5 oct) |

### 7.2 Métricas de fidelidad — PENDIENTE

No hay métricas de fidelidad decididas. Los documentos fuente no las fijan. Se decidirá cuáles se usan (marginales, dependencias entre variables, utilidad) y con qué umbrales antes de correr la Etapa 3, **no después de ver los resultados**.

### 7.3 Evaluación TSTR

- **Entrenamiento:** solo datos sintéticos.
- **Prueba:** transacciones reales de los voluntarios, anonimizadas y anotadas por **dos anotadores** con la guía de anotación; acuerdo medido con **Kappa**.
- **Universo:** bancarizado (L7). No se extrapola a gasto total.
- **Comparación:** contra el pipeline de referencia (Pancholi), ya ejecutado (etapas 1–3; `docs/reevaluacion_pancholi.md`). El cierre de H-P1 requiere el referente ENPH (participación de alimentos por quintil de `ICGU`; P19).
- **Precisión con muestra pequeña:** con 20 voluntarios y una muestra anotada de tamaño aún desconocido, la incertidumbre de las métricas puede ser grande. El método para cuantificarla (p. ej. remuestreo) es **PENDIENTE**; el conjunto real no permite generalizar más allá de Bogotá (L8).

### 7.4 Condiciones previas de la evaluación con datos reales — PENDIENTES

- **Aval del comité de ética:** no está confirmado si el programa lo exige (P2 del plan maestro). Bloquea toda la recolección.
- **Paquete de consentimiento y anonimización** (WP4) por ajustar al alcance actual.
- **Confirmación de los 2 anotadores** (P4).
- **Congelar la taxonomía v1.1** tras revisar ≥ 50 descripciones reales.
- **Si se recogerá el estrato y el ingreso de los voluntarios**, para poder contrastar la calibración por celda contra lo real: no está decidido.

### 7.5 Reproducibilidad (criterio transversal)

- Semilla global `SEED = 42`; otras semillas, si las hay, se documentan.
- `outputs/manifest.json` en cada corrida de modelo (versiones, semillas, commit, parámetros, entorno).
- Notebooks que corran de punta a punta con «Restart & Run All».
- Las distribuciones de Bogotá se regeneran con `tools/distribuciones_priors.py`; sin aleatoriedad [`outputs/distribuciones/manifest_distribuciones.json`].
- Una recomendación del plan maestro §12: recalcular desde cero, en un entorno limpio y sin leer `outputs/`, tres cifras clave antes de usarlas en la tesis.

### 7.6 Calendario (plan maestro §10)

| Fecha | Hito |
|---|---|
| 21 sep | Este documento; correo a la directora |
| 22–23 sep | Módulo de priors y sus pruebas |
| 24–25 sep | Generador por reglas; **punto de control con la directora el 25** |
| 28 sep – 4 oct | CTGAN y dataset sintético v1; congelar taxonomía; doble anotación |
| 5–11 oct | Clasificadores y TSTR |
| 12–15 oct | Resultados y cierre; **entrega el 15 de octubre de 2026** |

Criterio del punto de control: si el 25 no hay muestra sintética por reglas funcionando, se revisa el alcance con la directora en vez de comprimir el trabajo.

---

## 8. Registro de pendientes y discrepancias

### 8.1 Pendientes de decisión o de trabajo

| # | Pendiente | Etapa | Bloquea |
|---|---|---|---|
| PD1 | Umbral de soporte de las celdas | 1 | Encogimiento |
| PD2 | Método de encogimiento y lista de celdas afectadas | 1 | Priors por celda |
| PD3 | Priors de medio de pago por celda (estrato × quintil) y su respaldo urbano nacional | 1 | Generador |
| PD4 | Cómo entra GEIH al generador (estrato, posición, formalidad) | 1–2 | Generador |
| PD5 | Montos y frecuencias de transacción | 1–2 | Generador |
| PD6 | Esquema de la transacción | 2 | Generador |
| PD7 | Fuente de nombres de comercio y de medios digitales | 2 | Generador |
| PD8 | Cadencia y tamaño de los retiros que representan el efectivo acumulado en la capa de emisión (D15, §5) | 2 | WP6 |
| PD9 | Traducción de prior de hogar a probabilidad de transacción | 1–2 | Generador |
| PD10 | Arquitectura y parámetros del CTGAN; variables de entrada | 3 | CTGAN |
| PD11 | **Métricas de fidelidad y umbrales** | 3 | Evaluación de Etapa 3 |
| PD12 | Etiqueta objetivo, hiperparámetros y partición de los clasificadores | 4 | TSTR |
| PD13 | ✅ Reevaluación ejecutada (etapas 1–3; `docs/reevaluacion_pancholi.md`). Pendiente: referente ENPH para H-P1 (P19) y decisión justificada de la categoría de hospedaje para H-P2 | 4 | Cierre de H-P1 y H-P2 |
| PD14 | Taxonomía v1.1 congelada | 2, 4 | Anotación |
| PD15 | Control de cambios del DANE 2501–2512 | Fuentes | L3, L2 |
| PD16 | Verificar bloque de `P438J13` en el Cuadernillo 3; ubicar `P438J14` y `P438K11` | 1 | Cobertura de la matriz |
| PD17 | Definición oficial DANE de formalidad, solo si hace falta una sola variable | 1 | — |
| PD18 | Aval de ética, anotadores y paquete de datos reales | 4 | Toda la recolección |
| PD19 | Confirmar o descartar, contra el texto impreso del Cuadernillo 3, los subcapítulos que `outputs/diseno_muestral/e_mezcla_categorias_p438_preliminar.csv` detecta como posible mezcla de categorías por código pero sin confirmar (L17) | 1 | Alcance real de L17 sobre la calibración de medio de pago |
| PD20 | ~~Ejecutar `rareza_subcapitulo_k_financiero()` para saber la prevalencia real de `obligaciones_financieras`~~ ✅ **Resuelto 22 sep:** K11 no es ralo (13,80 % de hogares expandidos en Bogotá, 8,39 % a nivel nacional); K12 da 0 en ambos dominios por una razón estructural de la pregunta, no de prevalencia — ver `docs/justificacion_parametros.md` y `outputs/diseno_muestral/f_rareza_obligaciones_financieras.csv` | 1 | — |

### 8.2 Discrepancias entre documentos fuente (detectadas al redactar la v0.1) y su estado

| # | Discrepancia | Estado (20 sep 2026) |
|---|---|---|
| 1 | `docs/fuentes_datos.md` §10.3 daba el estrato ENPH como «supuesto no verificado» | **Corregida.** El texto se regenera con `tools/generar_fuentes_datos.py` y cita el Manual ENPH, pregunta 4 |
| 2 | Cortes de quintil y conteos de celda distintos entre `docs/fuentes_datos.md` (1.128.000 / 1.815.000 / 2.775.333 / 4.518.575; celda 1-2 × Q1 = 654) y `outputs/distribuciones/` (1.127.000 / 1.810.250 / 2.766.667 / 4.506.283; 653) | **Corregida.** Ambos scripts usan ahora la misma función (`sdg.pesos.cortes_ponderados`). La diferencia venía de la **población** sobre la que se calculaban los cortes: `fuentes_datos.md` los calculaba solo sobre hogares con estrato válido (3.899); `outputs/` los calcula sobre todos los hogares de Bogotá con `ICGU` (3.918). Es correcta la de `outputs/`: el quintil describe la distribución del ingreso de la población de Bogotá y no debe depender de que el hogar tenga estrato válido. Los cruces GEIH (§10.3 B) también se recalcularon con esta regla |
| 3 | `docs/taxonomia/pendientes_v1.1.md` T2–T4 seguían «Por verificar» / «Bloqueado por T2» | **Corregida.** T2 y T4 verificados; T3 desbloqueado y pendiente de aplicar al regenerar la taxonomía v1.1 |
| 4 | `docs/fuentes_datos.md` §10.4 y §10.6 rotulaban el código 4 de `NC2R_CC_P6` como «Fiador» | **Corregida (22 sep 2026).** El Cuadernillo 2 urbano es la fuente autoritativa del instrumento (`sdg.codigos.FORMA_PAGO_NC2R_FUENTE`): dice «Fiado». `tools/generar_fuentes_datos.py` ahora muestra «Fiado (DDI: «Fiador»)» en §10.4 y en la tabla de §10.6, citando el rótulo del DDI en vez de repetirlo como si fuera correcto |
| 5 | Afirmaciones sobre las salidas del pipeline de Pancholi (USD 12, 5 perfiles, 149 tx, categorías de ocio, 100 % `credit_card`) presentadas como resultados | **Resuelta (24 sep).** El pipeline se ejecutó (etapas 1–3): las afirmaciones se reevaluaron (H-P1/H-P2/H-P3, §1.4 y `docs/reevaluacion_pancholi.md`); las cifras del informe son compatibles con la aplicación web, no con el pipeline del paper (inferido). Siguen sin corregir en el informe de avance y la presentación, documentos de la autora fuera del repo |
| 6 | «Efectivo supera el 85 % en 22 de 29 subcapítulos» sin salida de código | **Corregida.** Sale de `outputs/distribuciones/enph_p438_resumen_efectivo.csv` (29 filas, columna `supera_umbral`; comparación estricta sobre el valor sin redondear). Los 7 subcapítulos que no lo superan: G14 64,33 %, H12 69,52 %, J13 72,79 %, G13 75,22 %, F13 80,55 %, I12 84,36 %, D12 84,39 % |
