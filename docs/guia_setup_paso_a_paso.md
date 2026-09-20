# Guía paso a paso — Setup local y web

**Fecha:** 20 sep 2026 · **Faltan 25 días** para la entrega final (15 oct).
**Cambio respecto a la estrategia anterior:** como puedes volver a descargar los datos, **normalizamos la estructura desde cero**. Esto elimina C1, C2 y C3 (autodetección fallida, duplicados raíz/CSV, Febrero 2026) sin escribir parches. El código queda más simple y más defendible ante el jurado.

Tiempo total: **60–90 min de setup** + descargas en segundo plano.

---

# PARTE A — Setup local (Windows)

## Paso 1 · Prerrequisitos (10 min)

Abre **PowerShell** y verifica:

```powershell
git --version
python --version
```

- **Git**: si falta → https://git-scm.com/download/win (instalador por defecto).
- **Python 3.11 o 3.12**: si falta → https://www.python.org/downloads/windows/ → marca **"Add python.exe to PATH"**.
  > No uses 3.13: varias dependencias del stack (CTGAN/SDV, torch) todavía van atrás.

## Paso 2 · Instalar Claude Code (5 min)

Sigue la guía oficial: **https://code.claude.com/docs** → *Quickstart*. Hay dos rutas; usa la que la doc marque como recomendada para Windows (instalador nativo) o, si ya manejas Node 18+:

```powershell
npm install -g @anthropic-ai/claude-code
```

Luego:

```powershell
claude doctor      # diagnóstico de la instalación
claude             # primera ejecución → /login con tu cuenta
```

Dentro de la sesión, comandos que vas a usar seguido: `/init`, `/memory`, `/permissions`, `/clear`, `/cost`.
**No corras `/init`**: tu `CLAUDE.md` ya está escrito (Paso 4).

## Paso 3 · Crear el repositorio fuera de OneDrive (5 min)

```powershell
mkdir C:\tesis-sdg
cd C:\tesis-sdg

# esqueleto
mkdir data\_descargas, data\raw, data\interim, data\processed, data\reales_anon
mkdir notebooks, src\sdg, tests, outputs, docs, tools, external, .claude
```

> **Por qué fuera de OneDrive:** un `.git` sincronizado se corrompe, y los archivos "solo en la nube" fallan al leerse desde Python. Los datos crudos sí pueden quedarse en OneDrive si quieres respaldo, pero el repo no.

## Paso 4 · Colocar los archivos de configuración (5 min)

1. Copia el **`CLAUDE.md` v2** (adjunto en este mensaje) a `C:\tesis-sdg\CLAUDE.md`.
2. Copia `estrategia_claude_escritorio_tesis.md` a `C:\tesis-sdg\docs\`.
3. Crea `C:\tesis-sdg\.claude\settings.json` con exactamente esto:

```json
{
  "permissions": {
    "deny": [
      "Edit(data/raw/**)",
      "Edit(data/_descargas/**)",
      "Read(data/reales_crudos/**)"
    ]
  }
}
```

4. Crea `C:\tesis-sdg\.gitignore`:

```
data/
outputs/*.png
outputs/*.csv
external/
.venv/
__pycache__/
.ipynb_checkpoints/
*.pkl
*.pt
```

> `data/` no se versiona (pesa GB y son microdatos oficiales). Lo que sí se versiona es el **código que los reconstruye** y `docs/fuentes_datos.md` con los SHA-256.

## Paso 5 · Entorno de Python (10 min)

```powershell
cd C:\tesis-sdg
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install pandas numpy scipy statsmodels matplotlib openpyxl pyreadstat jupyter nbformat scikit-learn
pip freeze > requirements.txt
```

> `pyreadstat` lee `.SAV`/`.DTA` **con etiquetas de valor**, que el CSV de DANE pierde. Útil para no adivinar qué significa cada código.
> CTGAN/SDV y torch se instalan después (Chat 07), en su propio paso, para no romper el entorno ahora.

## Paso 6 · Volver a descargar los microdatos, ya ordenados (30–60 min, en paralelo)

Fuente: **microdatos.dane.gov.co** (catálogo oficial).

### Qué descargar

**GEIH 2025** — los **12 meses de 2025**, formato **CSV**, los 8 módulos:
`Características generales`, `Datos del hogar y la vivienda`, `Fuerza de trabajo`, `Migración`, `No ocupados`, `Ocupados`, `Otras formas de trabajo`, `Otros ingresos e impuestos`.
> **No descargues Febrero 2026.** Y descarga también el set `.SAV` de **un solo mes** (enero) como referencia de etiquetas.

**ENPH 2016-2017** — módulos que necesita la tesis:
`Viviendas y hogares`, `Características generales personas`, `Gastos diarios Urbanos`, `Gastos menos frecuentes - Medio de pago`, `Gastos menos frecuentes - Artículos`, y el equivalente **rural** de gastos.
> **Nuevo:** agrega el módulo de **Otros ingresos** (variables `P7510`, `P7513`: intereses, CDT, préstamos formales vs. informales). Quedó identificado como útil y no lo tenías.

**Metadatos** (ya los tienes, cópialos): diccionario GEIH `.xlsx`, DDI `.xml` de ambas encuestas, fichas metodológicas, cuadernillos ENPH.

### Dónde ponerlo

Deja **todos los `.zip` tal como los descargas** en:

```
C:\tesis-sdg\data\_descargas\
```

Sin renombrar, sin descomprimir. Un script lo hará (Paso 8), y así el proceso queda **reproducible y auditable** en vez de depender de que tú muevas carpetas a mano.

### Estructura canónica de destino (la produce el script)

```
data/raw/
├── GEIH_2025/
│   ├── 01_enero/  caracteristicas_generales.csv, datos_hogar.csv, fuerza_trabajo.csv,
│   │              migracion.csv, no_ocupados.csv, ocupados.csv,
│   │              otras_formas_trabajo.csv, otros_ingresos.csv
│   ├── 02_febrero/ ... 12_diciembre/     (idénticos: 8 archivos, mismos nombres)
│   ├── _etiquetas/ (SAV de enero)
│   └── _metadatos/
├── ENPH_2017/
│   ├── hogares/  viviendas_y_hogares.csv
│   ├── personas/ caracteristicas_generales.csv, otros_ingresos.csv
│   ├── urbano/   gastos_diarios.csv, gastos_menos_frecuentes_medio_pago.csv, ...
│   ├── rural/    ...
│   └── _metadatos/
```

Nombres en minúscula, sin tildes ni espacios. Con esto el cargador es un bucle de 5 líneas y `assert n_meses == 12` es real, no decorativo.

## Paso 7 · Primer commit y mover lo que ya existe (5 min)

```powershell
cd C:\tesis-sdg
git init
git add .
git commit -m "[setup] esqueleto del repo, CLAUDE.md y permisos"
```

Copia desde tu carpeta actual al repo:
- `3. Analisis descriptivo\01_validacion_datos.ipynb` → `notebooks\`
- `3. Analisis descriptivo\nota_hallazgos.md` → `docs\`
- `taxonomia_gastos_colombia_v1.json` y `.md` → `docs\taxonomia\`
- `plan_maestro_seguimiento_tesis.md` → `docs\plan_maestro.md`

> **No copies** `Datos_proyecto_voz` (cripto 2024, no es de la tesis).

## Paso 8 · Primera sesión de Claude Code — el normalizador

```powershell
cd C:\tesis-sdg
.\.venv\Scripts\Activate.ps1
claude
```

Pega esto (pide el plan antes de ejecutar):

```
Lee CLAUDE.md. Tarea: construir tools/normalizar_datos.py, que toma los .zip de
data/_descargas/ y produce la estructura canónica descrita en CLAUDE.md dentro de
data/raw/.

Requisitos:
- Primero INSPECCIONA los zips (nombres internos reales, encoding, separador,
  cantidad de archivos) y muéstrame una tabla antes de escribir nada.
- Mapeo módulo->nombre canónico por palabras clave, insensible a mayúsculas, tildes
  y espacios dobles. Si un zip no encaja en el mapeo, FALLA con mensaje claro; no adivines.
- Excluye explícitamente cualquier archivo de 2026.
- Idempotente: volver a correrlo no duplica ni corrompe.
- Al final escribe docs/fuentes_datos.md con: mes, módulo, ruta destino, filas,
  columnas, SHA-256, encoding y separador detectados. Y una tabla de verificación
  12 meses x 8 módulos con OK/FALTA.
Entrega: el script + el informe. No toques notebooks todavía.
```

Cuando termine: revisa el diff, corre el script, y **haz commit**.

## Paso 9 · Segunda sesión — auditoría de línea base

`/clear` o cierra y abre una sesión nueva (una tarea = una sesión):

```
Lee CLAUDE.md y docs/fuentes_datos.md. Auditoría SOLO LECTURA:
1. Verifica el truncamiento de ENPH "Gastos diarios Urbanos": compara el .csv contra
   el .txt y contra el contenido del zip (filas y llaves únicas). Concluye si la
   versión que se usó antes estaba incompleta.
2. Revisa notebooks/01_validacion_datos.ipynb: qué rutas son de Colab, qué cifras
   están hardcodeadas, y qué supuestos de estructura ya no aplican con data/raw
   normalizado.
3. Estado real de cada entregable del plan maestro (Chats 01-08): existe / corre / validado.
Entrega: docs/linea_base_2026-09-20.md con tablas y correcciones priorizadas.
No edites nada más. Resumen de 5 líneas para el Chat 00.
```

## Paso 10 · Tercera sesión — cerrar el Chat 01

```
Adapta notebooks/01_validacion_datos.ipynb a data/raw normalizado: rutas relativas,
lista blanca de los 12 meses, FEX_C18/12, assert n_meses==12, y validación de filas
por mes contra docs/fuentes_datos.md. Corre el notebook completo (Restart & Run All).
Actualiza docs/nota_hallazgos.md con la tabla "cifra del informe -> recalculada ->
¿coincide?" ahora sobre 12 meses, y marca qué cifras se movieron >1 p.p. respecto al
cálculo de solo enero. Escribe todas las cifras a outputs/. Cero valores hardcodeados.
```

Con esto quedan cerrados **H4** y el pendiente de truncamiento.

---

# PARTE B — Setup web (claude.ai)

## Paso 1 · Curar el conocimiento del proyecto

En el proyecto, deja **solo** esto (todo lo demás genera ruido y consume contexto en cada chat):

| Mantener | Quitar / no subir |
|---|---|
| `plan_maestro_seguimiento_tesis.md` | CSV o zips de microdatos |
| `informe_avance_trabajo_grado_1.docx` (o su PDF) | `dataset_summary_*.xlsx` (los reemplaza `fuentes_datos.md`) |
| `taxonomia_gastos_colombia_v1.md` / `.json` | Artículos PDF sueltos que no se citan |
| `docs/estrategia_claude_escritorio_tesis.md` | `Datos_proyecto_voz` |
| `docs/nota_hallazgos.md` (versión cerrada) | Notebooks (viven en el repo) |
| `docs/linea_base_2026-09-20.md` (cuando exista) | |

## Paso 2 · Instrucciones del proyecto

Pega esto en las instrucciones personalizadas del proyecto:

```
Tesis de maestría en IA (Sara Cárdenas, U. Javeriana): protocolo de generación de
datos sintéticos de transacciones financieras para Colombia. Responde en español,
concisa, señalando riesgos metodológicos de frente.

La ejecución técnica ocurre en Claude Code sobre el repositorio local C:\tesis-sdg.
La fuente de verdad es el repo, no este proyecto. Aquí se hace: seguimiento,
decisiones metodológicas, revisión crítica y redacción.

Reglas: todo cálculo sobre microdatos DANE usa factores de expansión; las cifras
ponderadas son las oficiales. Nunca cites una cifra de memoria: debe provenir de un
archivo de outputs/ generado por código. Entregables en .md o notebooks
reproducibles, nunca Word salvo pedido explícito.
```

## Paso 3 · Reordenar los chats

- **Chat 00 (este)** — sigue como tablero. Tráele los resúmenes de 5 líneas que produce Code.
- **Chats 01 y 01B** — se cierran como archivo histórico. Su ejecución se muda a Code.
- **Chat 02 (datos reales)** — sigue en web: es trabajo humano y documental, no código.
- **Chat 03 (taxonomía)** — web para la decisión; Code solo congela y valida el JSON.
- **Chats 04 y 09** — web (protocolo y redacción).

## Paso 4 · Conectar la carpeta en la app de escritorio

Abre la app de Claude, conecta **solo** `C:\tesis-sdg` (y, si quieres leer los PDF metodológicos, la carpeta de la tesis en OneDrive). Modo de permisos **Manual o Auto**; nunca "Skip" sobre carpetas con datos. Úsala para lectura de PDFs y armado de documentos, no para código.

---

# Riesgos que sigo viendo

| # | Riesgo | Mitigación |
|---|---|---|
| **R-a** | **El calendario.** Quedan 25 días para un pipeline de 4 etapas + TSTR + redacción, con la validación de datos aún abierta. | El setup se hace **hoy** y en bloque; a partir de mañana solo se ejecuta. Si el 27 de sep no está cerrado el Chat 07 (CTGAN), hay que renegociar alcance con la directora, no comprimir más. |
| **R-b** | **Ruta crítica humana (Chat 02).** El TSTR necesita datos reales etiquetados con doble anotación. Ningún setup acelera esto. | Reclutamiento y consentimiento tienen que estar corriendo **en paralelo desde ya**, independientemente del repo. |
| **R-c** | **Re-descargar 12 meses × 8 módulos** puede tomar más de lo previsto. | Arranca las descargas **antes** del Paso 1 y deja que corran mientras haces el resto. |
| **R-d** | Las cifras ponderadas sobre 12 meses **van a diferir** de las de enero que están en el informe. | Es esperado y correcto. Se documenta el cambio en `nota_hallazgos.md`; el informe se corrige en el Chat 09. |
| **R-e** | CSV de DANE sin etiquetas de valor → riesgo de interpretar mal un código. | Por eso el `.SAV` de enero + el diccionario. Toda recodificación debe citar la fuente de la etiqueta. |
| **R-f** | Determinismo CPU vs GPU (BETO en Colab). | Semillas fijas + `manifest.json` por corrida; declarar el entorno en la tesis. |

---

# Orden de ejecución de hoy

1. **Lanza las descargas** del DANE (corren solas).
2. Pasos 1–5 y 7 del setup local (~35 min).
3. Paso 8 cuando terminen las descargas → normalizador → commit.
4. Paso 9 → línea base.
5. Parte B, pasos 1–3 (~15 min).
6. Paso 10 → cerrar Chat 01.
