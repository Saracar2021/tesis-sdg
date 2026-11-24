# Parches al pipeline de referencia (Pancholi et al.)

El árbol clonado **no se edita**. `tools/pancholi_ejecutar.py` verifica que `git status` del clon esté limpio
y aplica los parches en memoria antes de importar. Cada parche queda con su SHA-256 en el manifiesto.

## P1 — importación de `SingleTableMetadata` (`src/component/transaction.py`, línea 8)
- **Razón.** Con la versión que el propio repo fija (`sdv==1.19.0`, `src/Data_Synthesizer/requirements.txt`),
  `from sdv.single_table import SingleTableMetadata` lanza `ImportError`: en SDV 1.19 la clase vive en
  `sdv.metadata.single_table`, que es justo de donde la importa su otro módulo (`src/component/customer.py`).
- **Diff.** `P1_import_SingleTableMetadata.diff`.
- **Cómo se aplica.** Antes de importar su módulo: `sdv.single_table.SingleTableMetadata =
  sdv.metadata.single_table.SingleTableMetadata`. Es el mismo objeto de clase que el diff importaría.
- **Efecto esperado.** Ninguno sobre el comportamiento: solo permite importar el módulo. La clase y la
  lógica de la etapa 2 y la etapa 3 no cambian.

## P2 — muestreo por lotes en el diseño B (réplica literal, 500.000 muestras)
- **Razón.** `TransactionCTGAN.generate()` llama a `synthesizer.sample(num_rows=500000)` sin `batch_size`. Con la
  alta cardinalidad de `merchant_name` (one-hot de ~1.400 columnas), el proceso llegó a ~6 GB y el sistema lo
  terminó por memoria (OOM, límite de 7 GB del entorno) en la semilla 42.
- **Cambio.** Solo en el envoltorio (`muestrear()` en `tools/pancholi_ejecutar.py`): cuando hay más de 50.000
  muestras se llama a `synthesizer.sample(num_rows=n, batch_size=50000)` sobre el mismo modelo ajustado, y se
  añade `timestamp` con su propia función `random_timestamp_within_30_days()`, igual que hace `generate()`.
- **Diff equivalente** (si se aplicara a su archivo):
  `- synthetic_df = self.synthesizer.sample(num_rows=num_samples)`
  `+ synthetic_df = self.synthesizer.sample(num_rows=num_samples, batch_size=50000)`
- **Efecto esperado.** Misma distribución de salida (mismo modelo, mismo muestreador); cambia el orden en que se
  consume el generador aleatorio, así que las filas no son idénticas a las que daría una sola llamada. El
  diseño A (60.000 muestras) no pasa por aquí.

## P3 — `config` en memoria para la etapa 4 (`transaction_deepseek_synthesizer.py`)
- **Razón.** Su script hace `from config import API_KEY_Groq`, pero `config.py` no existe en el commit fijado
  (el commit se titula «Removed API keys»): sin él, el módulo no importa.
- **Cambio (solo en `tools/pancholi_etapa4.py`).** Antes de importar su módulo se registra
  `sys.modules["config"]` con `API_KEY_Groq` leída de `GROQ_API_KEY` en `.env` (python-dotenv). La llave no
  se imprime ni se escribe en ninguna salida.
- **Efecto esperado.** Ninguno sobre su lógica.

## P4 — sustitución de modelo (y P4b, `reasoning_effort`) en la etapa 4
- **Razón.** Su código fija `llama-3.3-70b-versatile`, que Groq retiró de los planes gratuito y developer el
  16-ago-2026 (https://console.groq.com/docs/deprecations; reemplazo recomendado: `openai/gpt-oss-120b`).
- **Cambio.** El script consulta `/models`: si su modelo está disponible lo usa sin cambios; si no, reemplaza
  el campo `model` de cada petición por `--modelo-sustituto` y lo registra como desviación en
  `manifest_etapa4.json`. Para `gpt-oss` añade `reasoning_effort="low"` (P4b), porque su `max_tokens=500`
  podría agotarse en razonamiento y devolver contenido vacío.
- **Efecto esperado.** Con sustitución, la corrida es una **variante declarada** de su etapa 4, no una
  reproducción. Prompt, temperatura (0,5), `max_tokens` y lógica de muestreo no cambian.
