# CLAUDE.md — Tesis SDG Colombia (Sara Cárdenas, Maestría en IA, U. Javeriana)

> v2 — 20 sep 2026. Los microdatos se re-descargaron y viven en estructura canónica normalizada.

## Proyecto
Diseño y validación preliminar de un protocolo de generación de datos sintéticos de
transacciones financieras para el contexto colombiano.
Pipeline: (1) priors bayesianos desde DANE → (2) generador por reglas + nombres de
comercio → (3) CTGAN → (4) clasificadores + evaluación TSTR contra datos reales etiquetados.
Plan y estado: `docs/plan_maestro.md`. Bitácora: `docs/bitacora.md`. Entrega final: 15 oct 2026.

## Idioma y entregables
- Responder y documentar en **español**. Sé concisa; señala riesgos metodológicos de frente.
- Entregables en **.md** o **notebooks reproducibles**. Nunca Word salvo pedido explícito.

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
  ENPH_2017/hogares|personas|urbano|rural/   csv normalizados
  ENPH_2017/_metadatos/     cuadernillos, metodología, DDI xml
data/interim/  data/processed/  data/reales_anon/   outputs/   docs/   src/sdg/   tools/
```
- `data/raw/` y `data/_descargas/` son **solo lectura**. Nunca escribir, mover ni renombrar ahí.
  Todo derivado va a `data/interim/` o `data/processed/`.
- La regeneración de `data/raw/` es tarea exclusiva de `tools/normalizar_datos.py`.
- `docs/fuentes_datos.md` (filas, columnas, SHA-256, encoding, separador por archivo) es la
  referencia de integridad. Si un conteo no cuadra contra ese archivo, **detente y avisa**.

## Reglas de datos (no negociables)
- **Todo cálculo sobre microdatos DANE usa factores de expansión.**
  - GEIH 2025: `FEX_C18`; al apilar los 12 meses, `FEX_C18 / 12`.
  - ENPH 2016-2017: factor del módulo correspondiente (documentar cuál en cada uso).
- GEIH: **solo 2025**, los 12 meses, con `assert n_meses == 12`. Cualquier archivo de 2026 está excluido.
- Mismo módulo entre meses → apilar. Módulos distintos → unir por
  `DIRECTORIO + SECUENCIA_P + HOGAR` (+ `ORDEN` a nivel persona). Nunca "todo con todo".
- Declarar siempre unidad de análisis (persona/hogar) y dominio (urbano/rural por separado).
- Los CSV de DANE **no traen etiquetas de valor**: toda recodificación debe citar su fuente
  (diccionario, DDI o el `.SAV` de `_etiquetas/`). No inferir el significado de un código.
- Cifras ponderadas (FEX) son las oficiales. **Cero cifras hardcodeadas**: toda cifra sale de
  código y queda escrita en `outputs/`.
- Datos reales de voluntarios: solo la versión anonimizada, en `data/reales_anon/`.
  Nunca leer `data/reales_crudos/`.

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
- Commits pequeños, mensaje en español: `[chat-NN] qué cambió`.
- `docs/historico/` es archivo de referencia, solo lectura. 
  Nunca parchear ni reutilizar su código: el análisis se reconstruye desde cero sobre `data/raw` normalizado.
