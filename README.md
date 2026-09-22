# Datos sintéticos de transacciones financieras — Colombia

Trabajo de Grado, Maestría en Inteligencia Artificial, Pontificia Universidad Javeriana.
**Autora:** Sara J. Cárdenas.

## Objetivo y pregunta de investigación

Diseñar y validar de forma preliminar un **protocolo reproducible** para generar datos sintéticos
de transacciones financieras plausibles para Colombia, y medir si esos datos sirven para entrenar
clasificadores de transacciones que funcionen sobre transacciones reales (evaluación TSTR: *train
on synthetic, test on real*).

El protocolo se organiza en cuatro etapas: (1) priors bayesianos calibrados con microdatos del
DANE, (2) un generador por reglas con nombres de comercio, (3) refinamiento con CTGAN, y (4)
clasificadores evaluados contra transacciones reales etiquetadas.

**Dominio:** el protocolo se diseña para ser colombiano y reutilizable, pero la calibración y la
validación empírica se hacen sobre **Bogotá urbano** como caso de estudio (los 20 voluntarios del
componente de datos reales son de Bogotá). Ninguna cifra de este repositorio es nacional salvo que
se indique explícitamente. Detalle de la decisión de dominio: `CLAUDE.md`.

## Hipótesis sobre el pipeline de referencia (Pancholi et al.)

El pipeline de referencia (Pancholi et al.) **no se ha ejecutado todavía**. Sus limitaciones frente
al contexto colombiano se tratan como hipótesis a contrastar con una ejecución reproducible
(WP5), no como hallazgos:

- **H-P1 (ingreso):** el paper sí calibra el gasto por ingreso y características del hogar, pero
  con la distribución de Estados Unidos (ACS 2015-2019 de Washington D.C.). La hipótesis es que esa
  calibración no reproduce la relación ingreso–gasto de los hogares colombianos.
- **H-P2 (categorías):** las categorías de gasto del pipeline de referencia, ancladas en comercios
  y hábitos de Washington D.C., no corresponden a la estructura de gasto colombiana.
- **H-P3 (medio de pago):** con D15 (ver más abajo), la hipótesis es que el pipeline de referencia
  no reproduce, en términos de registros de extracto, la estructura de retiros en cajero y
  transferencias con la que el efectivo colombiano aparece realmente en un extracto bancario.

Detalle y regla de evidencia: `docs/protocolo_tecnico.md` §1.4; `CLAUDE.md`.

## Estado actual

**Hecho y verificado:**
- Base empírica reconstruida desde cero sobre microdatos DANE (GEIH 2025 y ENPH 2016-2017),
  con factores de expansión, 112 archivos verificados por SHA-256 y cargador único con 29 pruebas
  automatizadas.
- Distribuciones ponderadas de Bogotá urbano para los priors (16+ tablas en `outputs/distribuciones/`).
- Decisión de dominio (Bogotá urbano) y de universo del generador (D15: extractos de hogares
  bancarizados) cerradas y documentadas.

**Sin hacer todavía:**
- Módulo de priors bayesianos (condicionamiento por celda, umbral de soporte y encogimiento
  jerárquico).
- Generador por reglas, refinamiento con CTGAN, clasificadores y evaluación TSTR.
- **El pipeline de referencia (Pancholi et al.) no se ha ejecutado.** Sin esa ejecución, H-P1 a
  H-P3 siguen siendo hipótesis, no resultados.
- Recolección y anotación de los datos reales de validación (paquete listo, recolección
  pendiente de resolver la consulta de ética).

Estado detallado por actividad del cronograma: `docs/plan_maestro.md`. Registro fechado del
trabajo por paquete: `docs/bitacora.md`.

## Estructura del repositorio

```
CLAUDE.md              reglas de datos y decisiones metodológicas del proyecto (no negociables)
docs/                  documentación: plan maestro, protocolo técnico, bitácora, taxonomía,
                        paquete de datos reales (consentimiento, anonimización, anotación)
docs/historico/        análisis anterior, archivado como referencia de solo lectura; no refleja
                        el estado actual y no se reutiliza
src/sdg/                cargador único de GEIH/ENPH, códigos verificados, pesos
tools/                  scripts de normalización de datos y generación de las tablas de outputs/
tests/                  pruebas automatizadas (unittest)
outputs/                cifras y tablas generadas por código (nunca escritas a mano)
data/                   microdatos DANE y datos reales anonimizados — NO se versiona (.gitignore)
notas_locales/          notas de trabajo internas — NO se versiona (.gitignore)
```

## Cómo reproducir

1. Crear y activar un entorno virtual con Python 3.11, e instalar dependencias fijas:
   ```
   python -m venv .venv
   source .venv/Scripts/activate   # Git Bash en Windows
   pip install -r requirements.txt
   ```
2. Obtener los microdatos del DANE (GEIH 2025 y ENPH 2016-2017) y colocar los zips originales en
   `data/_descargas/`. Esta carpeta y `data/raw/` no se versionan y no vienen incluidas en el
   repositorio.
3. Ejecutar, en este orden:
   ```
   python tools/normalizar_datos.py        # extrae los zips a data/raw/ (estructura canónica)
   python -m unittest discover -s tests    # 29 pruebas del cargador único, deben quedar en verde
   python tools/generar_fuentes_datos.py   # regenera docs/fuentes_datos.md y outputs/fuentes_datos.json
   python tools/verificar_fex_enph.py      # verifica el factor de expansión de ENPH
   python tools/distribuciones_priors.py   # regenera outputs/distribuciones/
   python tools/investigar_julio.py        # regenera outputs/julio/
   ```
4. Los datos reales de validación (extractos anonimizados de voluntarios) solo existen en
   `data/reales_anon/`, nunca en `data/reales_crudos/`; ver `docs/datos_reales/`.

Reproducibilidad: semilla global `SEED = 42`; rutas relativas a la raíz del repositorio; cada
corrida de modelo escribirá `outputs/manifest.json` con versiones, semillas, commit y entorno.

## Resultados

Todas las cifras salen de código y quedan escritas en `outputs/`; ninguna está escrita a mano.

- `outputs/fuentes_datos.json` y `docs/fuentes_datos.md` — referencia de integridad de los 112
  archivos DANE (filas, columnas, SHA-256, encoding, unidad de análisis, llave).
- `outputs/distribuciones/` — distribuciones ponderadas de Bogotá urbano para los priors
  (estrato, quintil de ingreso, medio de pago, formalidad, bancarización), con
  `distribuciones_priors.md` como informe legible y `manifest_distribuciones.json`.
- `outputs/julio/julio_estrato.md` — investigación de la anomalía de julio 2025 en GEIH.
- `outputs/fex_enph_verificacion.json` — verificación del factor de expansión de ENPH.

## Índice de decisiones metodológicas (D1–D15)

Las decisiones D1 a D15 (dominio, llave de hogar ENPH, división de fuentes, agrupación de
estrato, quintiles, encogimiento jerárquico, meses de GEIH, medio de pago por categoría,
formalidad, no respuesta, ausencia de intervalos de confianza, reconstrucción de la base
empírica, separación entre datos reales y calibración, y D15 — universo del generador) están
documentadas con su justificación y evidencia en `docs/protocolo_tecnico.md` §5 (tabla de
decisiones) y en `CLAUDE.md`.

## Uso de herramientas de IA

Se usó Claude (Anthropic) como asistente de programación y redacción; todas las decisiones
metodológicas, la ejecución sobre los microdatos y la verificación de resultados son de la autora.
