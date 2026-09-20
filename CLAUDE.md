# CLAUDE.md — Tesis SDG Colombia (Sara Cárdenas, Maestría en IA, U. Javeriana)

> v3 — 20 sep 2026. Incorpora los hallazgos de `docs/fuentes_datos.md` (llave ENPH,
> unidad de análisis, diciembre, comparabilidad semántica) y la decisión de dominio.

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
  de ingreso**: la sensibilidad al ingreso es la contribución central de la tesis (limitación 1
  de Pancholi), así que esa dimensión no se sacrifica. Estrato e ingreso están muy
  correlacionados en Colombia, de modo que agrupar estrato pierde poca información.
  Revalidar el conteo de celdas tras agrupar; lo que siga ralo va a encogimiento jerárquico
  hacia urbano nacional, con el umbral declarado.
- **Ingreso — no confundir fuentes:** ENPH usa ingreso del hogar (`ICGU`, ingreso corriente de
  la unidad de gasto) y GEIH `INGLABO` es ingreso **laboral individual**. No son comparables.
  Declarar en cada tabla cuál se usa y qué calibra. Los quintiles se calculan **dentro de
  Bogotá**, no sobre el total nacional.


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
- ENPH 2016-2017: la columna `FEX_C` existe en los 16 archivos, pero **NO está verificado que
  sea el factor correcto para cada unidad de registro**. Antes de ponderar cualquier cifra de
  ENPH hay que confirmarlo contra la metodología y dejarlo escrito en `docs/fuentes_datos.md`.
  Ponderar registros de gasto con el factor del hogar produce cifras mal calculadas.

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
- **`NC2R_CC_P6` — CORREGIDO (20 sep).** El prefijo `NC2R_` NO implica rural: la variable vive
  en `hogares/viviendas_hogares.csv`, su etiqueta coincide con la redacción del cuadernillo
  urbano y está diligenciada en 61.930 hogares urbanos (3.517 de 3.918 en Bogotá, 89,8 %).
  **Pero su unidad es otra cosa:** la etiqueta es «La principal forma de pago usada para comprar
  los bienes mencionados en este cuadernillo fue:» → es la forma de pago **principal declarada
  por hogar**, acotada a **un cuadernillo**, no una participación de transacciones.
  Un 73,1 % así NO significa «73,1 % de las transacciones son en efectivo». Antes de reusar esa
  cifra hay que (a) precisar a qué cuadernillo se refiere «este cuadernillo» y (b) corregir su
  enunciado en el informe. Decidir además cómo se trata el 10,2 % sin dato.
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
