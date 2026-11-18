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
se indique explícitamente.

## Reevaluación del pipeline de referencia (Pancholi et al.)

El pipeline de referencia (Pancholi et al.) se ejecutó de forma reproducible (etapas 1–3, con
criterios prerregistrados antes de correr; detalle en `docs/reevaluacion_pancholi.md`). Las
limitaciones frente al contexto colombiano se contrastaron así:

- **H-P1 (ingreso):** no concluyente respecto a Colombia (falta el referente de la ENPH). Hallazgo
  firme: la salida final (CTGAN) no conserva la relación ingreso–monto (elasticidad −0,003
  [−0,008; 0,002], frente a 1,008 en la etapa de reglas).
- **H-P2 (categorías):** refutada con la definición prerregistrada (ocio = entretenimiento);
  confirmada si el hospedaje se cuenta como ocio. Solo 6 de 16 categorías de la taxonomía tienen
  registros; servicios públicos 0 %.
- **H-P3 (medio de pago):** confirmada para las etapas ejecutadas (1–3): sin campo de medio de pago
  ni registros de retiro o transferencia. La distribución de `payment_type` (etapa 4) queda no
  concluyente (no ejecutable).

## Estado actual

**Hecho y verificado:**
- Base empírica reconstruida sobre microdatos del DANE (GEIH 2025 y ENPH 2016-2017), con factores de
  expansión, archivos verificados por SHA-256 y un cargador único con pruebas automatizadas.
- Distribuciones ponderadas de Bogotá urbano para los priors (`outputs/distribuciones/`).
- **Etapa 1 — priors bayesianos** (`src/sdg/priors.py`, `src/sdg/encogimiento.py`): priors por celda
  estrato × quintil con encogimiento jerárquico hacia el nivel urbano nacional; umbral de soporte
  por verosimilitud marginal; muestreo reproducible de perfiles. Salidas en `outputs/priors/`.
- **Etapa 2 — generador por reglas** (`src/sdg/generador.py`, `gasto_enph.py`, `comercios.py`): emite
  extractos sintéticos con dos capas (gasto interno del hogar y emisión bancarizada); montos
  calibrados con la ENPH y deflactados a pesos de 2025 con el IPC del DANE (`src/sdg/ipc.py`).
  Salidas en `outputs/generador/` y `outputs/sintetico_reglas/`.
- **Etapa 3 — refinamiento con CTGAN** (`notebooks/03_ctgan_etapa3.ipynb`, `src/sdg/etapa3.py`):
  CTGAN (SDV) entrenado sobre los campos estructurados del extracto, con pre-registro de columnas,
  métricas y reglas duras (`docs/reporte/adenda_preregistro_ctgan.md`). Dataset sintético v1
  reproducible bit a bit; la relación ingreso–monto se conserva (elasticidad 0,45 vs. 0,33 del
  train, veredicto CONSERVA) y la tasa de rechazo por reglas (14,78 %) se reporta como resultado de
  fidelidad. Salidas en `outputs/ctgan/`.
- Reevaluación reproducible del pipeline de referencia (etapas 1–3), con criterios prerregistrados
  (`outputs/pancholi/`).
- Decisiones de dominio (Bogotá urbano) y de universo del generador (extractos de hogares
  bancarizados) cerradas y documentadas.

**En curso / pendiente:**
- Datos reales de validación: recolectados; falta ingesta, anonimización y anotación (dos
  anotadores con acuerdo medido por Kappa de Cohen).
- Etapa 4 — clasificadores y evaluación TSTR.
- Referente de la ENPH para cerrar H-P1 y decisión de la categoría de hospedaje para H-P2.
- Reporte (formato IEEE Transactions on AI): borrador avanzado en `docs/reporte/`
  (`main.tex`, `borrador_reporte.md`); faltan los resultados del TSTR y el diligenciamiento final.

Estado por actividad del cronograma: `docs/plan_maestro.md`. Registro fechado del trabajo:
`docs/bitacora.md`.

## Estructura del repositorio

```
docs/              plan maestro, protocolo técnico, bitácora, justificación de parámetros,
                   taxonomía, paquete de datos reales, tablas del generador
docs/reporte/      reporte IEEE: main.tex, borrador_reporte.md, adenda de pre-registro del CTGAN,
                   declaración de uso de IA, esqueleto
docs/historico/    análisis anterior, archivado como referencia de solo lectura
src/sdg/           cargador de GEIH/ENPH, pesos y códigos verificados; priors y encogimiento;
                   generador, gasto ENPH, nombres de comercio e IPC
tools/             normalización de datos, generación de tablas, construcción de priors y del
                   generador, conversión del IPC
tests/             pruebas automatizadas (unittest)
outputs/           cifras y tablas generadas por código (nunca escritas a mano): distribuciones,
                   priors, pancholi, generador, sintetico_reglas, ipc, ctgan
notebooks/         Etapa 3: notebook del CTGAN (y su copia ejecutada)
data/              microdatos del DANE y datos reales — NO se versiona (.gitignore)
CLAUDE.md          convenciones de datos y decisiones metodológicas del proyecto (no negociables)
```

## Cómo reproducir

1. Entorno: Python 3.11.
   ```
   python -m venv .venv
   source .venv/Scripts/activate   # Git Bash en Windows
   pip install -r requirements.txt
   ```
2. Colocar los insumos (no se versionan): microdatos del DANE (GEIH 2025, ENPH 2016-2017) en
   `data/_descargas/`, y el anexo de índices del IPC del DANE en `data/raw/IPC/`.
3. Ejecutar en orden:
   ```
   python tools/normalizar_datos.py          # extrae los zips a data/raw/ (estructura canónica)
   python tools/generar_fuentes_datos.py     # referencia de integridad (filas, SHA-256, llaves)
   python tools/distribuciones_priors.py     # distribuciones ponderadas de Bogotá
   python tools/construir_priors.py          # Etapa 1: priors por celda -> outputs/priors/
   python tools/convertir_ipc.py             # serie de IPC a formato largo -> outputs/ipc/
   python tools/construir_generador.py       # pool y calibración del generador
   python tools/generar_sintetico_reglas.py  # Etapa 2: muestra sintética -> outputs/sintetico_reglas/
   python -m unittest discover -s tests      # suite de pruebas, debe quedar en verde
   ```
4. Etapa 3 (CTGAN) corre en un entorno aparte, porque SDV exige `pandas<3`:
   ```
   python -m venv .venv-ctgan
   source .venv-ctgan/Scripts/activate
   pip install -r requirements-ctgan.txt
   jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=-1 \
     --output 03_ctgan_etapa3.ejecutado.ipynb notebooks/03_ctgan_etapa3.ipynb   # -> outputs/ctgan/
   ```
5. Los datos reales de validación solo existen anonimizados en `data/reales_anon/`, nunca en
   `data/reales_crudos/`; ver `docs/datos_reales/`.

Reproducibilidad: semilla global `SEED = 42`; rutas relativas a la raíz; cada corrida de modelo
escribe un `manifest` con versiones, semillas, commit y entorno. Las corridas en Linux y Windows
producen el mismo SHA-256 de salidas.

## Resultados

Todas las cifras salen de código y quedan escritas en `outputs/`; ninguna está escrita a mano.

- `docs/fuentes_datos.md` y `outputs/fuentes_datos.json` — referencia de integridad de los archivos
  del DANE (filas, columnas, SHA-256, encoding, unidad de análisis, llave).
- `outputs/distribuciones/` — distribuciones ponderadas de Bogotá urbano (estrato, quintil de
  ingreso, medio de pago, formalidad, bancarización), con informe legible y manifiesto.
- `outputs/priors/` — priors por celda, soporte, celdas afectadas por el encogimiento y pruebas de
  sensibilidad.
- `outputs/ipc/` — serie del IPC en formato largo y el factor de deflación a 2025.
- `outputs/generador/` y `outputs/sintetico_reglas/` — calibración del generador y la muestra
  sintética por reglas, con sus manifiestos.
- `outputs/pancholi/` — resultados de la reevaluación del pipeline de referencia.
- `outputs/ctgan/` — dataset sintético v1 del CTGAN, QualityReport (con piso y techo), elasticidad
  con veredicto, tasa de rechazo por regla y manifest (SHA-256, versiones, reproducibilidad bit a bit).

## Índice de decisiones metodológicas (D1–D15)

Las decisiones D1 a D15 (dominio, llave de hogar en ENPH, división de fuentes, agrupación de
estrato, quintiles, encogimiento jerárquico, meses de GEIH, medio de pago por categoría,
formalidad, no respuesta, ausencia de intervalos de confianza, reconstrucción de la base empírica,
separación entre datos reales y calibración, y D15 — universo del generador) están documentadas con
su justificación y evidencia en `docs/protocolo_tecnico.md` §5.

## Uso de herramientas de IA

Este trabajo se apoyó en un asistente de IA (Claude, de Anthropic) para escribir código y redactar
borradores, siempre bajo la dirección de la autora. El diseño metodológico, todas las decisiones de
modelado, la ejecución sobre los microdatos y la verificación de los resultados son de la autora.
La reproducibilidad del repositorio —pruebas automatizadas, SHA-256, semillas fijas y cifras
generadas por código— permite auditar cada resultado de forma independiente.
