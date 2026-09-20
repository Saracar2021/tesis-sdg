# Estrategia de uso de Claude en escritorio — Tesis SDG Colombia

**Corte:** 17 sep 2026 · **Hitos:** avance a directora **18 sep** · tesis final **15 oct**
**Complementa:** `plan_maestro_seguimiento_tesis.md` (Chat 00). No cambia alcance ni cronograma; cambia **dónde** se ejecuta cada actividad.

---

## 0. Decisión

| Superficie | Rol | Qué se hace ahí | Qué NO se hace ahí |
|---|---|---|---|
| **Claude Code** (terminal o app de escritorio) | **Motor de ejecución — Track A** | Todo lo que es código y cifras: notebooks, `src/`, tests, FEX, priors, reglas, CTGAN, clasificadores, TSTR. Corre sobre los microdatos locales, sin subir nada. | Redacción larga de la tesis; decisiones de alcance. |
| **Claude (app de escritorio) con tu carpeta conectada** — lo que antes se llamaba *Cowork*, hoy integrado en la app | **Asistente documental sobre archivos** | Inventarios, lectura de PDFs metodológicos (DANE, artículos), revisión del informe `.docx` (solo lectura), preparación de paquetes `.md` (avance a directora), organización de carpetas. | Tocar microdatos o código del repo (evita dos agentes editando lo mismo). |
| **Proyecto en claude.ai (chat)** | **Gobierno y pensamiento** — Chat 00 | Seguimiento, decisiones metodológicas, revisión crítica, mensaje a directora, redacción (Chat 09). Conocimiento curado del proyecto. | Ejecutar sobre datos (ya no hace falta subir CSV). |

**Regla de oro — una sola fuente de verdad:** el **repositorio git en disco**. El proyecto de claude.ai recibe *copias* de entregables cerrados, nunca al revés. Si hay conflicto, gana el repo.

**Por qué Code como motor y no la app:** el grueso del trabajo pendiente (Chats 01, 01B, 05–08) es software reproducible sobre archivos grandes. Code ejecuta en tu máquina con tu Python, maneja git, corre tests y deja diffs revisables — exactamente lo que exige tu criterio (determinismo, rutas relativas, reproducible de punta a punta).

---

## 1. Riesgos de la configuración actual (de frente)

Detectados solo con el `tree` (no pude abrir archivos: esta conversación no está enlazada a tu computador y los dos `.xlsx` llegaron vacíos).

| # | Riesgo | Impacto | Acción |
|---|---|---|---|
| **C1** | **El notebook del Chat 01 autodetecta `GEIH_2025/<Mes> 2025 CSV/`.** En tu disco solo `Enero 2025 CSV` sigue ese patrón; los demás están en `<Mes> 2025/CSV/`. | Corriéndolo local cargaría **solo enero sin error** → H4 quedaría “cerrado” en falso y `FEX_C18/n_meses` dividiría por 1. | Ajustar cargador + `assert n_meses == 12` y conteo de filas por mes. **Primera tarea en Code.** |
| **C2** | Estructura GEIH inconsistente: `Diciembre 2025/CSV/` **no** tiene `Ocupados` ni `Datos del hogar` (solo en la raíz del mes); todos los meses tienen esos dos CSV duplicados en raíz; Nov/Dic usan carpeta `DAT/` con `.DTA`; Agosto tiene doble espacio en “salud y  educación” y un `.SAV` en minúscula. | Cargar la copia equivocada o duplicar registros. | Hash (SHA-256) raíz vs `CSV/` por mes; decidir fuente canónica y documentarla en `docs/fuentes_datos.md`. |
| **C3** | `Febrero 2026.zip` convive con 2025. | Contaminar el año de referencia. | Exclusión explícita en el cargador (lista blanca de 12 meses). |
| **C4** | Todo está dentro de **OneDrive**. | Archivos “solo en la nube” (Files On-Demand) que fallan al leer; bloqueos de sincronización; un `.git` sincronizado se corrompe. | Repo **fuera** de OneDrive; datos enlazados por *junction* (§2). Marcar la carpeta de datos como “Mantener siempre en este dispositivo”. |
| **C5** | Microdatos editables por el agente. | Una escritura accidental sobre `raw` invalida la reproducibilidad. | Doble barrera: permisos de Claude Code + atributo de solo lectura en Windows. |
| **C6** | Verificación de truncamiento de `Gastos diarios Urbanos` quedó pendiente. Ahora tienes **`.csv` y `.txt` locales**. | Cifras ENPH sobre archivo incompleto. | Comparar filas/llaves `.csv` vs `.txt` vs zip. Cierra el pendiente del Chat 01. |
| **C7** | El repo de **Pancholi (Chat 01B)** no aparece en el árbol. | 01B no ejecutable localmente. | Clonarlo dentro de `external/` con commit fijado. |
| **C8** | **Datos reales (Chat 02)**: extractos de voluntarios = datos personales financieros (Ley 1581/2012). | Exposición de datos sensibles en OneDrive/agentes. | Crudos **fuera** del repo y fuera del alcance de Claude; Claude solo ve la versión anonimizada. |
| **C9** | `Datos_proyecto_voz` (cripto 2024) no pertenece a la tesis. | Ruido de contexto / confusión. | No conectarla ni enlazarla al repo. |
| **C10** | Cómputo: BETO fine-tuning necesita GPU; CTGAN con ~5.000 filas corre en CPU. | Diferencias CPU/GPU rompen determinismo exacto. | CTGAN local; BETO en Colab con el mismo `requirements.txt` y semillas; resultados vuelven al repo con `manifest.json`. |
| **C11** | Oportunidad no aprovechada: el módulo GEIH **“Otros ingresos e impuestos”** sí está en disco (el Chat 01 lo daba por ausente). | Ingresos no laborales para priors. | Evaluarlo en Chat 05, no ahora. |

---

## 2. Setup (≤ 1 hora — no más, mañana hay entrega)

1. **Instala Claude Code** siguiendo la guía oficial (code.claude.com/docs). Verifica con `claude doctor`. Instala Git y Python 3.11 si no los tienes.
2. **Crea el repo fuera de OneDrive**, p. ej. `C:\tesis-sdg`, y enlaza los datos (cmd, sin admin):
   ```bat
   mkdir C:\tesis-sdg\data
   mklink /J C:\tesis-sdg\data\raw "C:\Users\julia\OneDrive\Escritorio\Sara Cardenas\Universidad Javeriana\Tesis de grado - Sara Cardenas\2. Preparar datos"
   attrib +R "C:\tesis-sdg\data\raw\*" /S
   ```
   Así el código usa rutas relativas (`data/raw/GEIH_2025/...`) sin mover nada.
3. **Estructura del repo:**
   ```
   tesis-sdg/
   ├── CLAUDE.md              ← reglas permanentes (archivo adjunto)
   ├── .claude/settings.json  ← permisos (deny escritura en data/raw)
   ├── data/raw/ (junction, solo lectura)  data/interim/  data/processed/  data/reales_anon/
   ├── external/pancholi/     ← repo 01B, commit fijado
   ├── notebooks/             ← 01_validacion_datos.ipynb (mover desde "3. Analisis descriptivo"), 01B_, 05_, 07_, 08_
   ├── src/sdg/               ← carga.py, fex.py, priors.py, reglas.py, ctgan_train.py, clasif.py
   ├── tests/  outputs/  docs/ (plan_maestro.md, bitacora.md, nota_hallazgos.md, fuentes_datos.md, taxonomia/)
   └── requirements.txt (versiones fijas)  .gitignore (data/, outputs pesados)
   ```
4. **Permisos** en `.claude/settings.json` (verifícalos luego con `/permissions`):
   ```json
   { "permissions": { "deny": ["Edit(data/raw/**)", "Read(data/reales_crudos/**)"] } }
   ```
5. **Copia `CLAUDE.md`** (adjunto) a la raíz del repo. No uses `/init` para generarlo: ya contiene tus reglas.
6. `git init` + primer commit. Desde aquí: **un commit por paso aceptado**.
7. En la **app de escritorio**, conecta solo la carpeta de la tesis (sin `Datos_proyecto_voz`) y usa modo de permisos **Manual o Auto**, nunca “Skip” sobre carpetas con datos.

---

## 3. Evaluación de línea base (primera sesión en Claude Code)

Objetivo: saber **qué existe, qué corre y qué cifras se sostienen** hoy, con evidencia. Pega esto en Code, **en modo plan** (solo lectura, sin editar):

```
Lee CLAUDE.md y docs/plan_maestro.md. Haz una auditoría de línea base, SOLO LECTURA:
1. Inventario de data/raw: por fuente/mes/módulo → ruta, tamaño, filas, columnas,
   SHA-256. Marca duplicados (raíz del mes vs CSV/), faltantes (Diciembre/CSV),
   formatos anómalos (DAT/), y Febrero 2026 como excluido.
2. Verifica truncamiento: "Gastos diarios Urbanos" .csv vs .txt (filas, llaves únicas).
3. Revisa notebooks/01_validacion_datos.ipynb: ¿qué meses cargaría con la estructura
   local? ¿qué rutas son de Colab? ¿qué cifras están hardcodeadas?
4. Estado de cada entregable del plan maestro (Chats 01–08): existe / corre / validado.
Entregable: docs/linea_base_2026-09-17.md con tablas y una lista priorizada de
correcciones. No edites nada más. Al final, resumen de 5 líneas para el Chat 00.
```

Después, en una **sesión nueva** (una tarea = una sesión):

```
Aplica las correcciones C1–C3 al cargador de 01_validacion_datos: lista blanca de los
12 meses 2025, fuente canónica según docs/fuentes_datos.md, assert n_meses==12,
FEX_C18/12. Corre el notebook completo, compara contra nota_hallazgos.md y actualiza
la tabla "cifra informe → recalculada → ¿coincide?". Marca cambios >1 p.p. vs enero.
```

---

## 4. Mapa de chats → superficie

| Chat | Superficie | Nota |
|---|---|---|
| 00 Plan maestro | **Proyecto (chat)** | Recibe los resúmenes de 5 líneas; ahora también `docs/bitacora.md` del repo. |
| 01 Validación DANE | **Code** | Continuar desde la línea base; cerrar H4 y truncamiento. |
| 01B Pancholi | **Code** | `external/pancholi`, `MODE="http"`, commit fijado en `manifest.json`. |
| 02 Datos reales | **Proyecto** (protocolos) + **Code** (Kappa, solo sobre anonimizados) | Los crudos nunca entran al repo ni a Claude. |
| 03 Taxonomía v1.1 | **Proyecto** (revisión humana) → **Code** (congelar JSON + validador de esquema) | La decisión es tuya; Code solo versiona y valida. |
| 04 Protocolo | **Proyecto** o app con carpeta | Documento `.md` en `docs/`. |
| 05 Priors · 06 Reglas · 07 CTGAN · 08 TSTR | **Code** | BETO en Colab (C10). |
| 09 Redacción | **Proyecto** | Cifras solo desde `outputs/` del repo, nunca de memoria. |
| 10 Mensaje a directora (18 sep) | **Proyecto** | Usar `linea_base_2026-09-17.md` como evidencia. |

---

## 5. Secuencia inmediata

- **Hoy noche (máx. 1 h):** setup §2 + auditoría §3 (solo lectura). Si algo se traba, **no insistas**: la entrega de mañana no depende del setup.
- **18 sep (mañana):** Chat 10 en el proyecto → mensaje a directora con la línea base como evidencia de ejecución. Sube `linea_base_2026-09-17.md` al proyecto.
- **19–20 sep:** Code cierra Chat 01 (12 meses + truncamiento) y levanta 01B. En paralelo, tú congelas taxonomía (03) y avanzas reclutamiento (02).
- **Desde 21 sep:** cronograma del plan maestro, Fase 1 en Code.

---

## 6. Buenas prácticas (las que más mueven el resultado)

1. **`CLAUDE.md` es tu contrato.** Todo lo que repites en cada chat (FEX, semilla, rutas relativas, `.md`, español) vive ahí y Code lo lee siempre. Cuando corrijas algo dos veces, agrégalo al archivo.
2. **Plan antes de ejecutar** en todo lo que toque datos: pide primero el plan, revísalo, luego autoriza.
3. **Una tarea por sesión**; limpia contexto entre tareas. Sesiones largas degradan criterio.
4. **Criterios de aceptación verificables** en cada pedido (asserts, conteos, tabla de reconciliación). Tu plantilla de brief sigue valiendo: cámbiale “adjunto CSV” por rutas del repo.
5. **Revisa diffs y haz commit** tras cada paso aceptado; si algo sale mal, `git` te devuelve.
6. **Verificación independiente para cifras que van a la tesis:** pide a Code que un subagente revisor, sin ver el trabajo previo, recalcule 3–5 cifras clave desde cero.
7. **Nunca cifras de memoria**: toda cifra en el informe debe apuntar a un archivo de `outputs/` generado por código.
8. **Nada sensible sin anonimizar** frente a cualquier superficie de Claude (C8).
9. **Proyecto de claude.ai curado:** solo plan maestro, informe, taxonomía, `nota_hallazgos.md`, línea base y bitácora. Sin CSV crudos.
