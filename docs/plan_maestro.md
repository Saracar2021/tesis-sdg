# Plan maestro y seguimiento — Trabajo de Grado

**Título:** Diseño y validación preliminar de un protocolo de generación de datos sintéticos de transacciones financieras para el contexto colombiano
**Autora:** Sara J. Cárdenas · Maestría en Inteligencia Artificial, Pontificia Universidad Javeriana
**Versión:** 2 · **Corte:** domingo 20 de septiembre de 2026 · reemplaza la v1 del 15 de septiembre
**Hitos:** avance a directora (previsto 18 sep, **no enviado**; se envía el lun 21 sep) · punto de control **vie 25 sep** · tesis final **jue 15 oct 2026** (25 días desde este corte)

> Documento vivo de seguimiento del proyecto (WP0). La fuente de verdad técnica es el repositorio `C:\tesis-sdg` (respaldo privado en GitHub). Este documento resume el estado; las cifras y su derivación viven en el repo.

---

## 0. Resumen ejecutivo

1. **La base empírica se reconstruyó desde cero.** Las cifras del análisis descriptivo del informe de avance estaban escritas a mano, sin factores de expansión y sobre un solo mes. Se re-descargaron los microdatos del DANE y se construyó una base verificable: 112 archivos con hash SHA-256 contra el original, cargador único con 29 pruebas automatizadas y distribuciones ponderadas para Bogotá.
2. **El dominio quedó definido: Bogotá urbano.** Los 20 voluntarios de la validación son de Bogotá; calibrar contra otro dominio rompería la comparación del TSTR.
3. **Hay resultados nuevos que refuerzan la tesis.** El efectivo domina en Bogotá (97 % de los hogares lo declara como forma de pago principal en gastos frecuentes), y el medio de pago **varía por categoría de gasto** (hasta 28 % de tarjeta de crédito en electrodomésticos y muebles). **El pipeline de Pancholi no se ha ejecutado**: las tres «fallas» que el informe de avance le atribuye (USD 12 entre perfiles, dominio de categorías de ocio, 100 % tarjeta de crédito) son **hipótesis sin respaldo** hasta WP5 (§6).
4. **Cuatro afirmaciones del análisis descriptivo quedan retiradas y las tres sobre Pancholi pasan a hipótesis** (§6) y **ocho limitaciones quedan declaradas** (§7).
5. **Lo que falta es casi todo el pipeline de generación y la validación empírica**, en 25 días. El punto de control del 25 de septiembre define si el alcance completo cabe.

---

## 1. Estado por actividad del cronograma

| # | Actividad (cronograma 2026-2) | Estado 15 sep | Estado 20 sep | Evidencia |
|---|---|---|---|---|
| — | Análisis descriptivo / validación de datos DANE | ⚠️ Con errores | ✅ **Reconstruido y cerrado** (WP1) | `docs/fuentes_datos.md`, `outputs/distribuciones/`, `src/sdg/carga.py`, `tests/` |
| 1 | Diseño formal del protocolo (documento técnico) | ❌ | 🟡 **Decisiones tomadas, documento sin redactar** | Decisiones en `CLAUDE.md` (v4) y en §4 de este plan |
| 2 | Módulo de priors bayesianos | ❌ | 🟡 **Insumos listos** (distribuciones Bogotá con FEX); módulo sin escribir | `outputs/distribuciones/distribuciones_priors.md` |
| 3 | CTGAN + dataset sintético v1 (≥ 5.000 tx) | ❌ | ❌ No empezado | — |
| 4 | Taxonomía colombiana | ⚠️ Generada con IA | 🟡 Correcciones factuales identificadas; congelamiento pendiente | `docs/taxonomia/pendientes_v1.1.md` |
| 5 | Recolección de transacciones reales | ❌ | 🟡 **20 voluntarios de Bogotá con acceso**; paquete v1.1 listo (consentimiento, anonimización, diseño de muestra: dic 2025, abr y ago 2026). **Bloqueado por la consulta de ética** | `docs/datos_reales/` |
| 6 | Etiquetado manual (2 anotadores) + Kappa | ❌ | 🟡 Guía v1.0 y muestra definida (600 movimientos, 30 por persona); guía por actualizar a la taxonomía v1.1; anotadores por confirmar | `docs/datos_reales/` |
| 7 | Entrenamiento de 3 clasificadores + TSTR | ❌ | ❌ No empezado | — |
| 01B | Reevaluación del pipeline de Pancholi | ❌ | 🔴 Notebook diseñado (WP5); **el pipeline nunca se ha ejecutado**. Sostiene la motivación empírica y la comparación de la hipótesis | WP5; `external/` vacío |
| — | Redacción de la tesis | ❌ | ❌ No empezada (el capítulo de datos ya tiene insumos) | — |

---

## 2. Cierre de los hallazgos H1–H8 del análisis anterior

Todos quedan resueltos por **reconstrucción**, no por parche: el análisis viejo se archivó en `docs/historico/` como referencia de solo lectura.

| # | Hallazgo (v1) | Cómo quedó |
|---|---|---|
| H1 | P438 nunca se ejecutaba; 97,6 % hardcodeado | P438* recalculado: son 29 columnas, una por subcapítulo de gasto; salida como matriz categoría × medio de pago |
| H2 | Cifras de gráficos escritas a mano | Toda cifra sale de código y queda en `outputs/` |
| H3 | Sin factores de expansión | `FEX_C18/12` en GEIH; `FEX_C` en ENPH, **verificado** contra la metodología (§2.2.4.1) y en los datos |
| H4 | Solo enero, reportado como «todos los meses» | Los 12 meses de 2025 apilados, con validación de filas por mes |
| H5 | Código truncado | Cargador único con 29 pruebas en verde |
| H6 | Mezcla ENPH 2016-17 / GEIH 2025 sin declarar | Regla explícita: ENPH aporta ingreso y gasto; GEIH, estructura demográfica y laboral |
| H7 | Quintiles sin ponderar | Quintiles de `ICGU` ponderados, calculados dentro de Bogotá |
| H8 | Ingreso laboral individual reportado como ingreso del hogar | `ICGU` (hogar) para calibración; `INGLABO` solo descriptivo |

---

## 3. Qué se construyó (inventario verificable)

| Componente | Qué hace | Dónde |
|---|---|---|
| Normalizador de datos | Extrae los 28 zips del DANE a una estructura canónica, bytes intactos, idempotente, excluye 2026 | `tools/normalizar_datos.py` |
| Referencia de integridad | 112 archivos: filas, columnas, SHA-256, encoding, separador, unidad de análisis y llave | `docs/fuentes_datos.md`, `outputs/fuentes_datos.json` |
| Cargador único | Carga GEIH y ENPH con reglas fijas, pondera, filtra Bogotá, bloquea rural, reporta % de filas enlazadas en cada unión | `src/sdg/carga.py`, `pesos.py`, `codigos.py`, `medio_pago.py` |
| Pruebas | 29 pruebas automatizadas | `tests/test_carga.py` |
| Distribuciones para priors | 16 tablas de Bogotá urbano con FEX, con informe y manifiesto | `outputs/distribuciones/` |
| Investigación de anomalías | Serie mensual de estrato, escaneo de julio y marzo, sensibilidades | `outputs/julio/`, `geih_sensibilidad_*.csv` |
| Contrato de trabajo | Reglas metodológicas permanentes del proyecto | `CLAUDE.md` (v4) |
| Bitácora | Registro fechado de lo hecho, por paquete de trabajo | `docs/bitacora.md` |
| Historial | Commits `081bf43` → `d221c5d` → `2aebb9e` en `main` | GitHub privado |

---

## 4. Decisiones metodológicas tomadas

| Decisión | Razón | Registro |
|---|---|---|
| **Dominio: Bogotá urbano** | Los 20 voluntarios son de Bogotá; el TSTR exige el mismo dominio en sintético y real | `CLAUDE.md` |
| Encuadre: protocolo colombiano, **calibración y validación sobre Bogotá** como caso de estudio | Evita presentar cifras bogotanas como nacionales; la generalización es trabajo futuro | `CLAUDE.md` |
| Rural fuera de alcance | Los extractos bancarios son urbanos; el instrumento rural es distinto (gasto semanal) | `CLAUDE.md` |
| Bogotá en GEIH = `AREA = 11` (no `DPTO = 11`) | `DPTO` suma 237 hogares rurales; `AREA` es comparable con ENPH urbano | `docs/fuentes_datos.md` §10 |
| Llave de hogar en ENPH = `DIRECTORIO` | La llave de GEIH enlaza solo el 8,72 % de los registros de gasto urbano | `docs/fuentes_datos.md` §4 |
| **ENPH aporta ingreso (`ICGU`) y gasto; GEIH aporta estructura demográfica y laboral** | `INGLABO` es ingreso laboral individual y sus fronteras son inestables por amontonamiento | `CLAUDE.md` |
| Estrato agrupado en 3 (1-2, 3-4, 5-6), **quintiles de ingreso completos** | 6 × 5 dejaba 12 de 30 celdas con < 30 hogares; la hipótesis de la tesis incorpora las proporciones de gasto por quintil observadas en Colombia, así que la calibración por quintil es central | `CLAUDE.md` |
| Celdas ralas → encogimiento jerárquico hacia urbano nacional | Quedan 4 de 15 celdas ralas en Bogotá (estrato 5-6 en Q1–Q4); urbano nacional no tiene ninguna | `CLAUDE.md`; umbral a fijar en WP3 |
| **Se usan los 12 meses de GEIH 2025** | Sin marzo o sin julio, estrato y formalidad se mueven < 1 p.p.; lo que supera 1 p.p. es un efecto de frontera de `INGLABO` | `docs/bitacora.md` |
| Formalidad: componentes separados, sin índice propio | Un indicador compuesto inventado no es defendible; si hace falta uno, se usa la definición oficial del DANE | `CLAUDE.md` |
| **D15 — el generador emite extractos sintéticos, con capa interna de gasto del hogar** (22 sep) | La pregunta de investigación es clasificar transacciones reales de usuarios, que son filas de extracto. La capa interna simula el gasto completo calibrado con ENPH; se emiten solo los registros que vería un banco o billetera, y el efectivo sale como retiros periódicos. Implica: (1) población = hogares bancarizados, reponderando priors con `P5222S*` de GEIH por estrato; (2) la hipótesis H-P3 sobre Pancholi se formula en términos de registros de extracto, y se verifica al ejecutarlo; (2b) tenencia de productos financieros calculada: 93,47 % de hogares de Bogotá con al menos uno (9,37 % sin ninguno en estrato bajo, 4,54 % medio, 0,27 % alto), `outputs/distribuciones/geih_bancarizacion_x_estrato.csv`. Tener un producto no implica usarlo para gastar: un hogar con cuenta de ahorros sin movimientos produce un extracto casi vacío (supuesto a declarar); (3) supuestos declarados de cadencia de retiros y participación de medios digitales (Banrep 2024) | `docs/protocolo_tecnico.md` §5 |
| **Los datos reales solo evalúan; nunca calibran el generador** | Si los mismos extractos calibran y evalúan, el TSTR queda contaminado. El generador se calibra solo con ENPH y GEIH | `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md` |
| Proporciones descriptivas sobre quienes responden; no respuesta declarada aparte, sin imputar | Evita el error del 73,1 % (§6) | `CLAUDE.md` |
| No se reportan intervalos de confianza sobre cifras DANE | Los archivos públicos no traen segmento ni UPM | `CLAUDE.md` |

---

## 5. Cifras vigentes (Bogotá urbano, con factores de expansión)

Todas salen de `outputs/distribuciones/`. Son las únicas cifras que se citan; ninguna se compara contra el informe anterior.

**Tamaño de muestra (sin ponderar).** ENPH: 3.918 hogares y 12.279 personas. GEIH 2025: 9.733 hogares y 13.552 ocupados en los 12 meses.

**Estrato agrupado (% de hogares con respuesta).**

| Fuente | Bajo (1-2) | Medio (3-4) | Alto (5-6) |
|---|---|---|---|
| ENPH 2016-2017 | 44,7 % | 49,5 % | 5,9 % |
| GEIH 2025 (12 meses) | 47,3 % | 46,0 % | 6,8 % |

**Quintiles de ingreso del hogar (`ICGU`, ENPH, calculados dentro de Bogotá).** Fronteras superiores: Q1 $1.127.000 · Q2 $1.810.250 · Q3 $2.766.667 · Q4 $4.506.283. Ninguna frontera tiene más del 0,1 % del peso amontonado en un valor.

**Forma de pago principal en gastos frecuentes** (`NC2R_CC_P6`, cuadernillo 2, % de hogares que responden, n = 3.517): efectivo 97,0 % · tarjeta débito 2,0 % · tarjeta de crédito 0,5 % · otras 0,5 %. No respuesta: 11,4 % de los hogares, declarada aparte.

**Medio de pago por categoría de gasto** (`P438*`, cuadernillo 3, gastos menos frecuentes, 29 subcapítulos). El efectivo supera el 85 % en 22 de los 29 subcapítulos, pero la tarjeta de crédito sube donde el gasto es grande:

| Subcapítulo | Categoría | Tarjeta de crédito | Efectivo |
|---|---|---|---|
| G14 | Electrodomésticos, muebles y enseres | 28,0 % | 64,3 % |
| H12 | Transporte y comunicaciones | 22,4 % | 69,5 % |
| G13 | Electrodomésticos, muebles y enseres | 17,7 % | 75,2 % |
| J13 | Recreación, cultura y viajes | 15,1 % | 72,8 % |
| L11 | Gastos varios | 0,0 % | 98,7 % |

Esta matriz es el insumo con el que el generador condiciona el medio de pago a la categoría.

**Mercado laboral (GEIH, ocupados).** Posición ocupacional: empleado de empresa particular 58,9 % · cuenta propia 30,5 % · empleado del gobierno 4,3 % · patrón 2,8 % · empleado doméstico 2,7 %. Tiene algún contrato: 73,3 % (de ellos, verbal 19,7 %). Cotiza a pensión: 64,1 %. Afiliado a ARL: 62,6 %.

---

## 6. Afirmaciones del informe de avance que se retiran

| Afirmación retirada | Por qué |
|---|---|
| «El efectivo representa el 73,1 % de las transacciones» | Es % de **hogares** según su forma de pago principal, no de transacciones; y el cálculo incluía la no respuesta en el denominador (73,1 / 74,5 ≈ 98 %) |
| «Consistente con el 77,8 % del Banco de la República» | La coincidencia era un artefacto del error de denominador. Además miden cosas distintas |
| «El 25,5 % sin dato es probablemente efectivo no declarado» | Supuesto sin sustento; la no respuesta no se imputa |
| «Análisis de todos los meses de la GEIH» | Cubría solo enero |

**Afirmaciones sobre el pipeline de Pancholi: sin respaldo de ejecución (pasan a hipótesis de WP5)**

| Afirmación del informe | Estado |
|---|---|
| Entre perfiles de USD 15.000 y USD 85.000 anuales el monto promedio varía apenas USD 12 (5 perfiles), es decir, «insensibilidad al ingreso» | **Retirada y reformulada como H-P1.** El paper sí calibra el gasto por ingreso, con la distribución de EE.UU. (ACS 2015-2019 de D.C.). La hipótesis es que esa calibración no reproduce la relación ingreso–gasto de los hogares colombianos |
| Dominio de categorías de ocio (Athletic Exhibition, Special Events, Inn and Motel, Skating Rink) | **Hipótesis H-P2** |
| El 100 % de las transacciones tiene `payment_type: credit_card` | **Hipótesis H-P3.** La Tabla 5 del paper trae 4 ejemplos con tarjeta de crédito; es un ejemplo, no una proporción |

Sí se puede citar, con referencia al paper, su diseño: demografía del ACS 2015-2019 de Washington D.C., comercios de Yelp y de D.C., reglas calibradas por ingreso, CTGAN. Estas afirmaciones también están en la presentación (diapositivas 2 y 3) y en la introducción del informe.

Además, **todas** las cifras numéricas de la sección de análisis descriptivo del informe (estrato, ingresos por quintil y por estrato, brecha de 4,7 veces, formalidad, posición ocupacional) quedan sin validez y se reemplazan por las de §5, calculadas en otro dominio y con otra metodología.

---

## 7. Limitaciones declaradas (irán en la tesis)

| # | Limitación | Consecuencia |
|---|---|---|
| L1 | Los archivos públicos de GEIH y ENPH **no traen identificador de segmento ni de UPM** | No es posible calcular errores estándar de diseño; no se reportan intervalos sobre cifras DANE |
| L2 | **Marzo y julio de 2025** presentan anomalías sin explicación documental (julio: el estrato 3 cae de ~35 % a 26 % en Bogotá, también en las 23 ciudades) | Se usan los 12 meses; las sensibilidades muestran efecto < 1 p.p. en los insumos de calibración |
| L3 | **Comparabilidad semántica 2025 sin verificar**: el control de cambios del formulario y el diccionario disponibles son de 2024 | Supuesto declarado; consulta al DANE por las etapas 2501–2512 |
| L4 | **ENPH es de 2016-2017**: ~9 años frente a GEIH 2025, y sin billeteras digitales ni transferencias entre sus medios de pago | Se declara qué calibra cada fuente; los medios digitales requieren fuente complementaria |
| L5 | **Cobertura faltante de medio de pago**: los subcapítulos J14 y K11 existen en artículos pero no tienen columna `P438` (24,2 % y 13,8 % de los hogares de Bogotá con registros) | La matriz categoría × medio de pago tiene dos huecos |
| L6 | **Amontonamiento** en valores redondos de `INGLABO` | Fronteras de grupo inestables; por eso `INGLABO` no calibra nada |
| L7 | **Los extractos bancarios no ven el efectivo** (un retiro en cajero es una fila, no quince compras) | El TSTR se evalúa sobre el universo bancarizado, sin extrapolar al gasto total |
| L8 | 20 voluntarios por conveniencia | Diversidad, no representatividad; conjunto de validación, no estimación poblacional |

---

## 8. Pendientes abiertos

| # | Pendiente | Bloquea | Responsable | Cuándo |
|---|---|---|---|---|
| P1 | **Enviar el correo a la directora** (avance + consulta de ética + punto de control 25 sep) | Relación con la directora; ética | Autora | Lun 21 sep |
| P2 | **Confirmar si el programa exige aval de comité de ética** | Toda la recolección | Autora / directora | Esta semana |
| P3 | ~~Ajustar el paquete de WP4~~ ✅ v1.1 en `docs/datos_reales/` (20 sep). Falta: contactos, canal seguro de envío, script de anonimización | Pedir el primer extracto | Autora | Mar 22 – mié 23 |
| P4 | Confirmar los **2 anotadores** | Kappa | Autora | Esta semana |
| P5 | **Documento técnico del protocolo** (WP0) | Actividad 1 del cronograma | Autora | Esta semana |
| P6 | **Módulo de priors** (WP3): umbral de soporte y método de encogimiento | Generador | Autora | Mar 22 – mié 23 |
| P7 | **Generador por reglas** (WP6) | CTGAN | Autora | Jue 24 – vie 25 |
| P8 | **Ejecutar por primera vez el pipeline de Pancholi** (WP5): conseguir el código, clonarlo en `external/`, ejecutar y contrastar H-P1 a H-P3 | **Motivación empírica y comparación de la hipótesis** | Autora | **Adelantado: esta semana, antes del 25** |
| P9 | Consulta al DANE: control de cambios 2501–2512 | L3 | Autora | Esta semana (bajo costo) |
| P12 | **D15 — medios observables:** marcar en la taxonomía v1.1 qué valores de `medio_pago` aparecen en extractos (efectivo y fiado solo existen en la capa interna) | Taxonomía, generador | WP2 | Antes del 28 sep |
| P13 | **D15 — categorías operativas a emitir, con fuente o supuesto:** `ingreso` (monto desde `ICGU`; cadencia por supuesto), `transferencias_p2p` (prevalencia de dinero recibido de otros hogares: familia `P7510*` de ENPH, por verificar), `movimiento_propio` (sin fuente: supuesto), `retiro_efectivo` (desde el gasto en efectivo de la capa interna; PD8) | WP6 | Autora | Jue 24 |
| P14 | **D15 — qué entrena el CTGAN:** los registros emitidos (extracto), no la capa interna. Registrar en el protocolo | WP7 | Autora | Con WP6 |
| P15 | **D15 — cuenta principal vs. consentimiento:** el consentimiento admite dos cuentas (banco + billetera) y el generador supone una. Decidir si el generador emite ambas o si el TSTR se evalúa por cuenta | WP6 y TSTR | Autora | Antes del 24 |
| P16 | **D15 — redacción de la hipótesis:** dice «la distribución real de medios de pago según la ENPH». Con D15, ENPH actúa en la capa interna y la mezcla observable en extractos requiere Banrep 2024. Ajustar la redacción con la directora | Tesis | Autora + directora | Punto de control del 25 |
| P10 | Congelar taxonomía v1.1 tras ver ≥ 50 descripciones reales | Anotación | WP2 | Cuando lleguen extractos |
| P11 | Pasar los entregables de WP4 y WP5 al repo (`docs/`) | Trazabilidad | Autora | Lun 21 |
| P19 | **Calcular en `outputs/distribuciones/` la participación ENPH de 6 categorías de la taxonomía que existen en ENPH pero no se han calculado:** `alimentos_mercado` (Cuadernillo 2, Capítulo C: `gastos_diarios_capitulo_c.txt`, `gastos_diarios_mercados.csv`); `comidas_fuera` (Cuadernillo 2, D1: `gastos_diarios_hogar_comidas_fuera.csv`); `telecom_conectividad` (Cuadernillo 3, H11/H12, separable de transporte a nivel de artículo por prefijo COICOP "083" en `gastos_menos_frecuentes_articulos.txt`, columna `P10270`); `obligaciones_financieras` (Cuadernillo 3, grupo K, `CAP`=K11/K12 en `gastos_menos_frecuentes_articulos.txt`; probablemente muy ralo); `transferencias_p2p` e `ingreso` (familia `P7510`/`P7513` de `caracteristicas_generales_personas.csv`, incidencia anual, requiere transformar a participación de transacciones) | Cruce de soporte de `tools/calculos_diseno_muestral.py`; `docs/justificacion_parametros.md` | WP1/WP3 | Antes de fijar el módulo de priors |
| P20 | Confirmar si `retiro_efectivo` y `movimiento_propio` (sin fuente ENPH, son mecánica bancaria) necesitan una fuente externa distinta para su participación esperada, o si basta con el supuesto de cadencia de retiros ya declarado (PD8) | Anotación, F1 macro por categoría | WP6 | Con WP6 |

---

## 9. Riesgos actualizados

| Riesgo | Estado | Mitigación |
|---|---|---|
| R1 — Datos reales (ruta crítica humana) | **Baja parcialmente**: hay 20 voluntarios. Sube el riesgo legal y de volumen | Paquete de WP4 ajustado antes de recibir el primer extracto; anotar una muestra, no todo |
| R2 — Base de datos inválida | ✅ **Cerrado** | Reconstrucción verificada |
| R3 — Cómputo (GPU para BETO, API de Groq) | Sin cambios | Colab para BETO con `requirements.txt` y semillas; API de Groq por confirmar |
| R4 — Sobrepromesa a la directora | **Activo**: el avance del 18 no se envió | Correo del lunes con evidencia y punto de control del 25 |
| R5 — Reproducibilidad | ✅ **Controlado** | Repo, pruebas, SHA-256, cero cifras hardcodeadas |
| R6 — TSTR bloqueado | Activo | Recolección desde esta semana; TSTR en la semana del 5 oct |
| **R7 — Calendario (nuevo)** | **Alto**: 25 días para priors, generador, CTGAN, clasificadores, TSTR y redacción | Punto de control 25 sep; redacción del capítulo de datos desde ya |
| **R8 — Comité de ética (nuevo)** | Desconocido | Preguntar el lunes; si aplica, iniciar el trámite de inmediato |
| **R9 — Instrumento DANE 2025 (nuevo)** | Declarado | L2 y L3 |
| **R12 — Motivación empírica sin respaldo (nuevo)** | **Alto** | Las tres fallas de Pancholi nunca se midieron. Si al ejecutarlo no aparecen, la motivación descansa en la ausencia de datos colombianos y en el diseño estadounidense del paper, y la hipótesis de la tesis se reformula. **Primer riesgo: que el código no esté disponible o no corra** |
| **R10 — Universo del generador vs. universo del real** | ✅ **Resuelto (D15, 22 sep)** | Extracto sintético con capa interna de gasto del hogar. Queda como riesgo residual la validez de los supuestos de retiros y medios digitales |
| **R11 — Unidad de los priors de medio de pago (nuevo)** | Declarado | ENPH da forma de pago principal **por hogar**; el generador emite transacciones. Usarla como probabilidad por transacción es un supuesto a declarar |

---

## 10. Plan ajustado 21 sep → 15 oct

**Principio:** dos tracks en paralelo. El Track A (software) se ejecuta sobre el repo; el Track B (datos reales) depende de personas y no se puede acelerar.

### Semana 1 — lun 21 a dom 27 sep · *pipeline sintético hasta reglas*

| Día | Track A (software) | Track B (datos reales) |
|---|---|---|
| Lun 21 | Documento técnico del protocolo (WP0) | **Enviar correo a la directora.** Ajustar paquete WP4. Consulta al DANE |
| Mar 22 | Módulo de priors (WP3) | Consentimiento final; contactar a los 20 voluntarios |
| Mié 23 | Priors: pruebas de que reproducen las marginales | Primeros extractos; anonimización |
| Jue 24 | Generador por reglas (WP6) | Recolección |
| **Vie 25** | Muestra sintética por reglas · **punto de control con la directora** | Recolección |
| Sáb 26 – dom 27 | Pancholi (WP5), si no se alcanzó antes | Revisar ~50 descripciones reales para la taxonomía |

**Criterio del punto de control:** si el 25 no hay muestra sintética por reglas funcionando, se revisa el alcance con la directora en vez de comprimir el trabajo.

### Semana 2 — lun 28 sep a dom 4 oct · *CTGAN y datos reales*
- **A:** CTGAN (WP7) → dataset sintético v1 ≥ 5.000 transacciones → métricas de fidelidad.
- **B:** congelar taxonomía v1.1 (WP2) → cerrar recolección → muestra a anotar → **doble anotación** → Kappa.
- **Redacción:** capítulo de datos y metodología, con §4, §5 y §7 de este plan como base.

### Semana 3 — lun 5 a dom 11 oct · *clasificadores y TSTR*
- Tres clasificadores entrenados sobre sintético (logístico TF-IDF, BETO, LLaMA 3 few-shot).
- Evaluación TSTR sobre el conjunto real anotado; comparación contra Pancholi.

### Semana 4 — lun 12 a jue 15 oct · *cierre*
- Resultados, discusión, conclusiones; revisión de la directora; **entrega el jueves 15**.

---

## 11. Qué se puede avanzar esta noche para enriquecer el correo

| Opción | Esfuerzo | Valor para la directora | Requisito |
|---|---|---|---|
| **A. Documento técnico del protocolo** (WP0), borrador | 1–2 h | Alto: es la actividad 1 del cronograma y el mejor anexo del correo | Ninguno: todas las decisiones están en `CLAUDE.md` |
| **B. Ajustar el paquete de WP4** | 1 h | Alto: demuestra que la recolección está lista para arrancar | Recuperar los 4 documentos de WP4 y responder formato y periodo de los extractos |
| C. Módulo de priors (WP3) | 2–3 h | Medio-alto | Fijar umbral de soporte |

**Recomendación:** A y B en paralelo esta noche. C al día siguiente.

---

## 12. Cómo verificar y reproducir lo hecho

Todo se corre desde Git Bash en `C:\tesis-sdg`, con el entorno activado (`source .venv/Scripts/activate`).

| Qué verificar | Comando | Resultado esperado |
|---|---|---|
| Que el código funciona | `python -m unittest discover -s tests` | 29 pruebas, `OK` |
| Que los datos no cambiaron | `python tools/normalizar_datos.py --dry-run` | Los 112 archivos como ya existentes, sin avisos |
| Referencia de integridad | `python tools/generar_fuentes_datos.py` | Regenera `docs/fuentes_datos.md`; `git diff` no debería mostrar cambios de cifras (si los muestra, algo en datos o código se movió) |
| Factor de expansión de ENPH | `python tools/verificar_fex_enph.py` | 100 % de filas con FEX igual al del hogar en las tablas verificadas |
| Distribuciones de §5 | `python tools/distribuciones_priors.py` | Regenera `outputs/distribuciones/`; las cifras de §5 deben salir iguales |
| Historial | `git log --oneline` | Commits hasta `2aebb9e` |

**Cómo leer los resultados sin correr nada:** `outputs/distribuciones/distribuciones_priors.md` (todas las tablas de §5, con fuente, dominio, unidad y peso en cada una) y `docs/fuentes_datos.md` §1 (tabla de riesgos y pendientes de los datos).

**Verificación independiente (recomendada antes de entregar cifras a la tesis):** recalcular desde cero, en un entorno limpio y sin leer `tools/` ni `outputs/`, tres cifras de §5 (por ejemplo, el 97,0 % de efectivo, la frontera de Q1 y el % de estrato bajo en GEIH). Si coinciden, la cifra está verificada por un camino independiente.

---

## 13. Checklist maestro

- [x] Microdatos DANE re-descargados y normalizados (112 archivos, SHA-256)
- [x] Referencia de integridad `docs/fuentes_datos.md`
- [x] Cargador único + 29 pruebas
- [x] Distribuciones Bogotá urbano con FEX
- [x] Hallazgos H1–H8 cerrados por reconstrucción
- [x] Dominio y reglas metodológicas definidas (`CLAUDE.md` v4)
- [ ] Correo a la directora enviado
- [ ] Consulta de comité de ética resuelta
- [ ] Documento técnico del protocolo
- [x] Paquete de WP4 ajustado (consentimiento, anonimización, muestra) — v1.1
- [ ] Guía de anotación actualizada a la taxonomía v1.1
- [ ] Taxonomía v1.1 congelada
- [ ] Módulo de priors (Etapa 1)
- [ ] Generador por reglas + nombres de comercio (Etapa 2)
- [ ] CTGAN + dataset sintético v1 ≥ 5.000 tx + métricas (Etapa 3)
- [ ] Reevaluación de Pancholi ejecutada
- [ ] Extractos recolectados y anonimizados
- [ ] Muestra anotada por 2 anotadores + Kappa
- [ ] 3 clasificadores + TSTR (Etapa 4)
- [ ] Tesis redactada y revisada · entrega 15 oct

---

## Anexo — Estado por paquete de trabajo (WP)

El trabajo se organiza en paquetes WP0–WP8 (entorno y datos, perfilado DANE, taxonomía, priors,
datos reales, pipeline de referencia, generador, CTGAN, evaluación TSTR). El repositorio de
código y documentos se respalda en GitHub privado; los datos no se suben.

| WP | Estado |
|---|---|
| WP0 — Entorno y seguimiento | Este documento (v2) |
| WP1 — Perfilado DANE | ✅ Cerrado (`2aebb9e`) |
| WP2 — Taxonomía | Pendientes en `docs/taxonomia/pendientes_v1.1.md` |
| WP3 — Priors | Insumos listos; módulo sin escribir |
| WP4 — Datos reales | Paquete redactado el 15 sep; por ajustar |
| WP5 — Pipeline de referencia (Pancholi) | Notebook diseñado, sin ejecutar |
| WP6 — Generador · WP7 — CTGAN · WP8 — Evaluación TSTR | Por hacer |

La equivalencia completa entre los chats de trabajo originales y estos WP queda en `docs/bitacora.md`.
