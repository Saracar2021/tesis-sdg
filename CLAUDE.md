# CLAUDE.md — Tesis SDG Colombia (Sara Cárdenas, Maestría en IA, U. Javeriana)

> v4 — 20 sep 2026. Incorpora los hallazgos de `docs/fuentes_datos.md` (llave ENPH,
> unidad de análisis, diciembre, comparabilidad semántica), la decisión de dominio y las
> verificaciones del Chat 01 (`FEX_C` ENPH, códigos de `P438*`/`NC2R_CC_P6`/estrato/`P6450`, julio).

## Proyecto
Diseño y validación preliminar de un protocolo de generación de datos sintéticos de
transacciones financieras para el contexto colombiano.
Pipeline: (1) priors bayesianos desde DANE → (2) generador por reglas + nombres de
comercio → (3) CTGAN → (4) clasificadores + evaluación TSTR contra datos reales etiquetados.
Plan y estado: `docs/plan_maestro.md`. Bitácora: `docs/bitacora.md`. Entrega final: 15 oct 2026.

## Idioma y entregables
- Responder y documentar en **español**. Sé concisa; señala riesgos metodológicos de frente.
- Entregables en **.md** o **notebooks reproducibles**. Nunca Word salvo pedido explícito.

## Dominio de análisis (decisión cerrada, 20 sep 2026)
- **Dominio de calibración y validación: BOGOTÁ, urbano.** Los 20 voluntarios del componente
  de datos reales son todos de Bogotá; calibrar contra otro dominio rompería la comparación
  sintético↔real del TSTR.
- **Encuadre para la tesis:** el *protocolo* es colombiano y reutilizable; la *calibración y
  validación empírica* se hace sobre Bogotá como caso de estudio. Declararlo así, no como si
  las cifras fueran nacionales. La generalización a otras ciudades es trabajo futuro.
- Los 6 archivos `ENPH_2017/rural/` **quedan fuera de alcance**, con la exclusión declarada.
  No se mezclan con urbano: son instrumentos distintos (gasto semanal vs. diario).
- **Respaldo para celdas ralas (jerárquico).** Bogotá reduce el n. Cuando una celda
  (estrato × ingreso × categoría) no tenga soporte suficiente en Bogotá, el prior se encoge
  hacia la distribución **urbana nacional** en vez de inventar la celda. Umbral de soporte,
  método de encogimiento y lista de celdas afectadas se declaran en el Chat 05 y quedan en
  `outputs/`. Esto es una ventaja del enfoque bayesiano, no un parche: se documenta como tal.
- Toda cifra declara su dominio explícitamente. Nunca presentar una cifra de Bogotá como
  nacional, una urbana como nacional, ni una rural como urbana.
- **Variable de dominio (verificado 20 sep):** GEIH → `AREA = 11` (Bogotá urbano; fuente:
  diccionario 2025, hoja «Plantilla Diccionario de Datos», fila 169). **No usar `DPTO = 11`**,
  que suma 237 hogares rurales con `AREA` vacía y rompe la comparabilidad con ENPH urbano.
  ENPH → `DOMINIO = 'BOGOTÁ'` en `viviendas_hogares` (texto, sin código numérico; `REGION`
  selecciona los mismos hogares). El respaldo documental de ENPH es débil: ni el `.sav` ni el
  DDI traen etiquetas y los cuadernillos no mencionan Bogotá. Declararlo como tal.
- **Tamaño de muestra en Bogotá (sin ponderar):** ENPH 3.918 hogares (4,5 %) y 12.279 personas;
  GEIH 9.733 hogares y 13.552 ocupados en los 12 meses (793–849 hogares/mes).
  **ENPH es la restricción activa**, y es donde vive el gasto, que es el núcleo de la tesis.
- **Cortes de calibración — DECISIÓN:** el cruce estrato (6) × quintil (5) deja 12 de 30 celdas
  con menos de 30 observaciones en ENPH Bogotá, concentradas en estratos 4–6.
  Se agrupa **estrato en 3 (1–2 bajo, 3–4 medio, 5–6 alto)** y se **conservan los 5 quintiles
  de ingreso**: la sensibilidad al ingreso es la contribución central de la tesis (la hipótesis es que
  el pipeline de referencia no la tiene; sin verificar, ver regla de Pancholi), así que esa
  dimensión no se sacrifica. Estrato e ingreso están muy
  correlacionados en Colombia, de modo que agrupar estrato pierde poca información.
  Revalidar el conteo de celdas tras agrupar; lo que siga ralo va a encogimiento jerárquico
  hacia urbano nacional, con el umbral declarado.
- **Ingreso — no confundir fuentes:** ENPH usa ingreso del hogar (`ICGU`, ingreso corriente de
  la unidad de gasto) y GEIH `INGLABO` es ingreso **laboral individual**. No son comparables.
  Declarar en cada tabla cuál se usa y qué calibra. Los quintiles se calculan **dentro de
  Bogotá**, no sobre el total nacional.


## Pipeline de referencia (Pancholi et al.) — regla de evidencia (Sara, 22 sep)
- **El pipeline de Pancholi no se ha ejecutado.** Ninguna salida suya es un resultado hasta que el
  Chat 01B lo ejecute de forma reproducible. **No se citan** como hallazgos: la diferencia de
  USD 12 entre perfiles, los 5 perfiles, las 149 transacciones, el dominio de categorías de ocio
  (Athletic Exhibition, Skating Rink, etc.) ni el 100 % de `credit_card`. Aparecen en el informe
  de avance y en la presentación sin respaldo de ejecución.
- **Sí se puede citar, con referencia al paper, lo que el paper documenta de su diseño:**
  demografía del ACS 2015-2019 de Washington D.C. por código postal (ZIP 20001), nombres de
  comercio de Yelp y de D.C., simulación por reglas con gasto calibrado por ingreso y hogar,
  refinamiento con CTGAN. Su Tabla 5 muestra 4 transacciones de ejemplo, todas con tarjeta de
  crédito: es un ejemplo, no una proporción.
- Las «tres limitaciones» (ingreso, categorías, medio de pago) son **hipótesis a verificar**.
  Nota: el paper afirma calibrar el gasto por ingreso, así que la insensibilidad al ingreso
  contradice lo que el paper declara y solo una ejecución puede establecerla.

## Estructura de datos (canónica — no improvisar otra)
```
data/_descargas/            zips originales del DANE, intactos (solo lectura)
data/raw/
  GEIH_2025/<NN>_<mes>/     01_enero ... 12_diciembre; 8 archivos por mes con nombres fijos:
                            caracteristicas_generales.csv, datos_hogar.csv, fuerza_trabajo.csv,
                            migracion.csv, no_ocupados.csv, ocupados.csv,
                            otras_formas_trabajo.csv, otros_ingresos.csv
  GEIH_2025/_etiquetas/     SAV de enero (etiquetas de valor)
  GEIH_2025/_metadatos/     diccionario xlsx, DDI xml, ficha metodológica, formulario

  ENPH_2017/hogares/        viviendas_hogares.csv, gastos_menos_frecuentes_medio_pago.csv,
                            gastos_menos_frecuentes_articulos.txt
  ENPH_2017/personas/       caracteristicas_generales_personas.csv
  ENPH_2017/urbano|rural/   archivos de gastos (13 .csv y 3 .txt separados por tabulador)

data/interim/  data/processed/  data/reales_anon/   outputs/   docs/   src/sdg/   tools/
```
- `data/raw/` y `data/_descargas/` son **solo lectura**. Nunca escribir, mover ni renombrar ahí.
  Todo derivado va a `data/interim/` o `data/processed/`.
- La regeneración de `data/raw/` es tarea exclusiva de `tools/normalizar_datos.py`.
- `docs/fuentes_datos.md` (filas, columnas, SHA-256, encoding, separador, unidad de análisis
  y llave por archivo) es la **referencia de integridad**. Si un conteo no cuadra contra ese
  archivo, **detente y avisa**. Lo regenera `tools/generar_fuentes_datos.py`.

## Reglas de datos (no negociables)

### Factores de expansión
- **Todo cálculo sobre microdatos DANE usa factores de expansión.**
- GEIH 2025: `FEX_C18`. Al apilar meses, `FEX_C18 / n_meses` con el `n_meses` **realmente
  cargado** (12 normalmente, 11 en la corrida sin diciembre). Nunca dividir por una constante.
- ENPH 2016-2017: **`FEX_C` VERIFICADO (20 sep 2026) como factor del hogar/vivienda.** Fuente:
  `Metodologia_ENPH.pdf` §2.2.4.1 («a la vivienda corresponde un único factor de expansión»);
  contraste empírico (`tools/verificar_fex_enph.py`, `outputs/fex_enph_verificacion.json`,
  `docs/fuentes_datos.md` §4): constante por `DIRECTORIO` e igual al de `viviendas_hogares` en
  10 tablas (hogares, personas y urbano). **No cubre rural** (fuera de alcance) ni se contrastó
  contra un total poblacional externo. Consecuencia: `FEX_C` sirve para cifras **por hogar** y por
  persona; en tablas de registros de gasto cada fila lleva el factor de su hogar, así que hay que
  **agregar primero a hogar**: ponderar filas de gasto sueltas produce cifras mal calculadas.
- Cargador único: `src/sdg/carga.py` (`cargar_geih`, `cargar_enph`, `unir`, `estrato_agrupado`);
  añade `FEX` (GEIH: `FEX_C18 / n_meses`; ENPH: `FEX_C`). No leer los CSV por fuera de él.

### Llaves y uniones — GEIH y ENPH NO comparten regla
- **GEIH:** mismo módulo entre meses → apilar. Módulos distintos → unir por
  `DIRECTORIO + SECUENCIA_P + HOGAR` (+ `ORDEN` a nivel persona).
- **ENPH:** el hogar se identifica **solo por `DIRECTORIO`** (verificado). ENPH no tiene
  columna `HOGAR`; `SECUENCIA_P` y `SECUENCIA_ENCUESTA` valen 1 en `viviendas_hogares` pero
  son contadores de registro en las tablas de gasto. Aplicar la regla de GEIH a ENPH enlaza
  apenas el 7–9 % de las filas urbanas **en silencio**.
  - Llave única de un registro de gasto: `DIRECTORIO + SECUENCIA_ENCUESTA + SECUENCIA_P`.
  - Unir gasto con hogar por `DIRECTORIO`, con conciencia de que es uno-a-muchos.
  - `ORDEN` en tablas de gasto **no** es la persona: el DDI no lo define. No asumirlo.
- Nunca "todo con todo". Tras cada unión, verificar y reportar el % de filas enlazadas;
  si no es ~100 %, detenerse.

### Unidad de análisis
- Declarar siempre la unidad (persona / hogar / registro de gasto) y el dominio en cada tabla.
- GEIH: 7 módulos son persona, `datos_hogar` es hogar.
- ENPH: solo `viviendas_hogares`, `gastos_menos_frecuentes_medio_pago` (hogar) y
  `caracteristicas_generales_personas` (persona) tienen una fila por unidad.
  **Los otros 13 son registros de gasto** (hasta 42,5 filas por hogar). Agregar a nivel hogar
  antes de promediar o ponderar; nunca tratar una fila de gasto como un hogar.

### Etiquetas y cifras
- Los CSV del DANE **no traen etiquetas de valor**: toda recodificación debe citar su fuente
  (diccionario, cuadernillo o el `.SAV` de `_etiquetas/`). No inferir el significado de un código.
  El DDI de GEIH está desactualizado («aplica para el 2023», `caseQnty` = 0): no usarlo como
  fuente de conteos ni de etiquetas 2025.
- Cifras ponderadas (FEX) son las oficiales. **Cero cifras hardcodeadas**: toda cifra sale de
  código y queda escrita en `outputs/`.
- Los archivos se extraen con bytes intactos (SHA-256 trazable al zip original).
  Regla fija de lectura: GEIH → `cp1252`; ENPH `.csv` → `utf-8-sig`; ENPH `.txt` → `utf-8`
  con separador tab. Los `.txt` conservan su extensión: **no son CSV**.

### Datos personales
- Datos reales de voluntarios: solo la versión anonimizada, en `data/reales_anon/`.
  Nunca leer `data/reales_crudos/`.

## Decisiones abiertas y supuestos declarados
Todo lo de esta sección va **declarado en la tesis**, no escondido.

- **Diciembre 2025 — SE INCLUYE, con prueba de sensibilidad.** Tiene −2,5 % de personas y
  −1,0 % de hogares frente a la mediana, sin explicación documental. Los `FEX_C18` compensan,
  así que los totales expandidos no caen. El cargador acepta `meses` como parámetro; antes de
  fijar priors se recalculan las cifras clave con 12 meses y con 11, y se reporta toda
  diferencia > 1 p.p. en `outputs/`. Si algo se mueve, se declara.
- **Comparabilidad semántica GEIH 2025 — SUPUESTO DECLARADO.** El control de cambios cubre
  2022–2024 (118 → 9 → 2 cambios: tendencia decreciente) y el formulario del repo es de las
  etapas 2401–2412. Se asume que el formulario de 2025 es el de 2024, porque es el vigente al
  iniciar enero 2025 y no hay evidencia de cambio. **Es una inferencia, no una verificación:**
  el documento simplemente es anterior a 2025.
  Contraste empírico obligatorio antes de fijar priors: estabilidad mes a mes de la
  distribución de las variables que alimentan los priors (`P6450`, `P6500`, `P5222S*` y las de
  medio de pago). Una discontinuidad entre meses es señal de cambio de instrumento.
  El chequeo detecta saltos grandes, no reformulaciones sutiles: es evidencia corroborante,
  no prueba. Pendiente: control de cambios de las etapas 2501–2512 (consulta al DANE).
- **Dominio:** cerrado en Bogotá urbano (ver arriba). El respaldo jerárquico hacia urbano
  nacional para celdas ralas es un supuesto declarado, con su umbral documentado.
- **`NC2R_CC_P6` — RESUELTO (20 sep).** El prefijo `NC2R_` NO implica rural: la variable vive
  en `hogares/viviendas_hogares.csv`, está diligenciada en hogares urbanos (3.517 de 3.918 en
  Bogotá) y su redacción coincide con el **Cuadernillo 2 urbano, sección D2 (gastos diarios del
  hogar, registro de 14 días)**, pregunta 2 (el rural dice «comprar o adquirir»). Su unidad es la
  forma de pago **principal declarada por hogar**, acotada a ese cuadernillo (compras frecuentes),
  no una participación de transacciones ni de gasto: se enuncia siempre como «% de HOGARES cuya
  forma de pago principal declarada es X».
  **Códigos (según el cuadernillo, no el DDI):** 1 débito, 2 crédito, 3 efectivo, **4 «Fiado»**
  (el DDI dice «fiador»: es un error de rotulado), 5 bonos, 6 otra. Sin dato: fila explícita,
  % sobre base con respuesta y sobre el total, sin imputar (decisión de Sara).
  **Cifra retirada:** «73,1 %» (efectivo) — cifra del informe de avance, sin dominio declarado,
  **DESCARTADA**. Se retiró por no declarar dominio y por enunciarse como % de transacciones cuando
  es una respuesta por hogar acotada a un cuadernillo. Se conserva aquí solo como registro; no reusarla.
- **`P438*` (`gastos_menos_frecuentes_medio_pago.csv`, hogar) — VERIFICADO (20 sep).** Son **29
  columnas, una por subcapítulo** del Cuadernillo 3 (gastos MENOS frecuentes); cada subcapítulo es
  **categoría × periodo de referencia** (mes pasado / 3 meses / 12 meses). Es el medio de pago
  principal **por categoría**, no un % global de efectivo: la salida es la matriz subcapítulo ×
  medio de pago. **Códigos (Cuadernillo 3): 1 débito, 2 crédito, 3 efectivo, 4 bonos, 5 cheques,
  6 otro.** ⚠️ Difieren de `NC2R_CC_P6` en 4 y 5: **nunca mapear uno con el diccionario del otro.**
  Vacíos: se cruzan con `gastos_menos_frecuentes_articulos.txt` por `DIRECTORIO + CAP` y se
  separan **no respuesta** (hay compra sin medio) de **no aplica** (sin compra) en
  `outputs/distribuciones/enph_p438_vacios.csv`. `FORMA = 1` = compra es **inferido** (el cuadernillo
  lista las formas por letra); por eso se reporta también con «cualquier registro».
  **Gaps abiertos:** no existen `P438J14` ni `P438K11` (los artículos sí traen esos `CAP`), y la
  correspondencia de `P438J13` con un bloque del cuadernillo no está verificada.
- **Estratos (verificado 20 sep).** ENPH `P8520S1A1`: Manual ENPH, Pregunta 4: **1-6 estrato,
  0 = conexión pirata, 9 = no establecible / planta eléctrica** (el Cuadernillo 1 y el DDI no traen
  códigos). GEIH `P4030S1A1`: Diccionario GEIH 2025 fila 32, «Rango entre 0 y 6 ó 9», **sin
  etiquetas para 0 ni 9**. Los códigos 0, 9 y vacío **no son estratos**: no se agrupan, se reportan
  como sin dato.
- **Contrato GEIH:** `P6440` (¿tiene contrato?: 1 sí, 2 no) y `P6450` (1 Verbal, 2 Escrito,
  **9 No sabe, no informa — NO 3**), Diccionario GEIH filas 680-684.
- **Formalidad laboral — SIN variable compuesta (decisión de Sara, 20 sep).** Los componentes
  (contrato, pensión `P6920`, ARL `P6990`) se reportan por separado. No se construye un indicador
  propio formal/informal; si hace falta una sola variable se usa la **definición oficial del DANE,
  citándola**.
- **Fronteras de grupos de ingreso amontonadas — LIMITACIÓN DECLARADA (20 sep).** `INGLABO` se
  reporta en valores redondos: la frontera de un grupo del 20 % cae dentro de un montón de valores
  iguales y salta ante cualquier perturbación de la muestra (`outputs/distribuciones/fronteras_amontonamiento.csv`).
  En `ICGU` (ENPH) las fronteras no están amontonadas. No se cambió a cortes fijos; se declara.
- **JULIO 2025 EN GEIH — PENDIENTE DE EXPLICAR.** En `datos_hogar` el estrato se desvía en julio
  (baja el estrato 3, suben 1 y 2; no es «sin dato»; se repite, más fuerte, en las 23 ciudades y
  atenuado a nivel nacional; otras variables del módulo no se mueven). Ver
  `outputs/julio/julio_estrato.md`. Se produjo la sensibilidad sin julio y queda registrado como
  **evidencia a favor de pedir al DANE el control de cambios 2501-2512** (evidencia para consultar,
  no prueba de cambio de instrumento). También: en `ocupados` de Bogotá el mes más extremo es
  **marzo** (sensibilidad sin marzo producida); las variables no son independientes, no leerlo como
  118 hallazgos.
  **DECISIÓN (Sara, 20 sep 2026, CERRADA): se usan los 12 meses.** Razón: (a) estrato agrupado
  (máx. 0,73 p.p. sin julio; 0,31 sin marzo) y formalidad (0,29 y 0,52 p.p.) quedan bajo el umbral
  de 1 p.p. en ambas versiones; (b) las familias de ENPH (quintil de `ICGU`, forma de pago) no dependen
  de los meses de GEIH; (c) lo único que supera 1 p.p. es `INGLABO`, con causa identificada: el
  corte pasa de 1.300.000 a 1.200.000 por el amontonamiento ya declarado (efecto de frontera, no
  cambio de composición). Marzo y julio quedan como **anomalías declaradas en la tesis**, con sus
  sensibilidades en `outputs/distribuciones/` como respaldo. No se investigan más las causas: sin
  el control de cambios del DANE (2501-2512) no hay forma de cerrarlas.
- **División de fuentes (regla).** ENPH aporta ingreso (`ICGU`) y gasto. GEIH aporta estructura
  demográfica y laboral (estrato, formalidad, posición ocupacional). `INGLABO` NO se usa como insumo
  de calibración: se reporta solo de forma descriptiva, y sus grupos tienen fronteras inestables por
  amontonamiento.
- **Celdas de posición ocupacional × cotiza pensión (GEIH):** pequeñas e inestables; se declaran
  así en `outputs/distribuciones/distribuciones_priors.md`. No requieren acción.
- **Rotación de hogares en GEIH — PENDIENTE CRÍTICO.** GEIH tiene panel rotativo. Si los hogares
  se repiten entre meses, apilar 12 meses NO da 12 muestras independientes: los errores estándar
  saldrían subestimados y los 9.733 hogares de Bogotá serían muchos menos hogares únicos.
  Verificar si `DIRECTORIO` se repite entre meses **antes** de fijar priors o reportar precisión.
- **Diccionario GEIH desactualizado:** todos los códigos de tabla terminan en `2401` (versión
  2024), igual que el formulario. Refuerza el pendiente de comparabilidad semántica.
- **Mezcla ENPH 2016-2017 con GEIH 2025:** ~9 años de diferencia. Declarar qué calibra cada
  fuente y por qué.

## Reproducibilidad
- Código determinista: `SEED = 42` global (random, numpy, torch, CTGAN); documentar otras semillas.
- Rutas **relativas** a la raíz del repo, vía `pathlib`. Nada de rutas absolutas, de Colab ni de Drive.
- `requirements.txt` con versiones fijas. Cada corrida de modelo escribe `outputs/manifest.json`
  (versiones, semillas, commit, parámetros, entorno CPU/GPU).
- Notebooks deben correr de punta a punta con "Restart & Run All".

## Forma de trabajo
- Antes de tocar datos o código: plan breve y esperar aprobación.
- Una tarea por sesión. Al terminar: verificar los criterios de aceptación con evidencia
  (asserts, conteos, tablas) y escribir un resumen de 5 líneas en `docs/bitacora.md`.
- No marcar nada como validado sin haberlo ejecutado.
- Si un supuesto no se puede verificar con los datos a la mano, **decirlo**; no rellenar.
  Distinguir siempre «verificado» de «inferido» y de «supuesto».
- Commits pequeños, mensaje en español: `[chat-NN] qué cambió`.
- `docs/historico/` es archivo de referencia, solo lectura. Nunca parchear ni reutilizar su
  código: el análisis se reconstruye desde cero sobre `data/raw` normalizado.
- Los permisos bloquean la escritura en `data/raw/` de forma intencional. Escribe los scripts;
  Sara los ejecuta. No intentes evadir el bloqueo.
