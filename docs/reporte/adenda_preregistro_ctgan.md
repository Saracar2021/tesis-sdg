# Adenda de pre-registro — Etapa 3 (CTGAN)

**Fecha:** 17 de noviembre de 2026 · **Registrada antes de ejecutar la Etapa 3 y de ver cualquier resultado.**
Cierra los puntos abiertos PD10/PD11 de `docs/protocolo_tecnico.md` §3.3 y §7.2. Decisiones de la autora; cualquier cambio posterior se declara como desviación.

## 1. Datos de entrada al CTGAN
- Fuente: `outputs/sintetico_reglas/transacciones.csv.gz`, filtrada a `capa == "emitida"` (122.211 filas de la corrida semilla 42).
- Join: LEFT JOIN con `outputs/sintetico_reglas/perfiles_generados.csv` por `perfil_id` para incorporar `ingreso_mensual`.
- Columnas al modelo: discretas `cuenta_tipo, categoria_n1, categoria_n2, medio_pago, origen, formalidad_comercio, canal_p2p`; continuas `monto`, `ingreso_mensual`; derivadas de `fecha`: `dia_mes`, `mes`. **Se excluye** `descripcion` (texto libre; se re-genera por plantillas).
- Tamaño: set completo (n = 122.211). Knob de cómputo declarado: épocas = 300 (respaldo 150). No se submuestrea por tiempo de reloj.

## 2. Muestreo
- La generación de la muestra sintética v1 usa la **marginal real** de `categoria_n1` de la fuente. Un muestreo balanceado/aumentado, si se usa, es solo para el entrenamiento de clasificadores (WP8) y se declara aparte.

## 3. Métricas de fidelidad y umbrales (fijados antes de correr)
- SDV `QualityReport`: Column Shapes y Column Pair Trends, calculadas contra un **holdout** de la fuente y **después** del filtro de rechazo.
- Se reportan **relativas a**: piso = muestreo de marginales independientes del train; techo = train vs. holdout de la fuente. No se usa un umbral absoluto.
- Prueba específica: **elasticidad monto–ingreso** = pendiente OLS de `log(monto)` sobre `log(ingreso_mensual)`, calculada igual sobre la fuente/train y la salida del CTGAN. Comparación a nivel transacción en ambas. Referencia = elasticidad de la **propia fuente/train** ≈ **0,347** (IC bootstrap por perfil 0,29–0,40). *[Corregido 17 nov: el ≈1,008 inicial era de `outputs/pancholi/` (reglas del pipeline de Pancholi, otro estimador), no de la capa emitida; ver §7.]*

## 4. Reglas duras de rechazo
Se descartan filas sintéticas que violen: (1) `monto ≤ 0`; (2) `medio_pago` imposible para el `cuenta_tipo`; (3) par `categoria_n1`–`categoria_n2` inexistente en la taxonomía; (4) `canal_p2p=True` con `origen ∉ {compra, pago_recurrente, ingreso_no_asalariado}` o medio ∉ {transferencia, billetera} (regla R2, corregida — ver §7); (5) fecha imposible (`dia_mes` inválido para el `mes`); (6) `signo` incompatible con el `origen` (salvo `transferencias_p2p.indeterminada`, donde ambos signos son válidos). Se reporta la **tasa de rechazo** total y por regla; tope tolerable declarado ≤ 10 %. Una tasa alta es un resultado de fidelidad, no se oculta.

## 5. Reproducibilidad
`SEED = 42`; se fijan a mano las semillas de `torch`, `numpy` y `random` más los flags deterministas. Verificación: dos entrenamientos y comparación del SHA-256 de la muestra. Si no coincide, se declara **reproducibilidad estadística** (métricas estables entre corridas), no bit a bit. Se fijan `torch`, `ctgan`/`sdv` en `requirements.txt`.

## 6. Alcance declarado (no son cambios al protocolo, van en la discusión)
- **Texto por plantillas:** la `descripcion` se re-genera por plantillas condicionadas a la categoría; un clasificador de texto mediría las plantillas, no el CTGAN. El TSTR (WP8) incluye un brazo de control entrenado solo con campos estructurados para aislar el aporte del refinamiento.
- **Fidelidad a las reglas, no a Colombia:** el CTGAN se entrena sobre la capa emitida (ya sintética); sus métricas miden cercanía a la salida de las reglas. La prueba frente a la realidad es el TSTR contra datos reales.

## 7. Desviaciones aceptadas y criterio de elasticidad (17 nov, antes de la corrida oficial de 300 épocas)

Tras implementar el notebook (`notebooks/03_ctgan_etapa3.ipynb`, `src/sdg/etapa3.py`), se aceptan cuatro desviaciones, todas derivadas de propiedades de la **fuente** (no de resultados del CTGAN), por lo que no vulneran el prerregistro:

1. **Referencia de elasticidad:** se usa la elasticidad de la fuente/train con el mismo OLS = **0,347** (IC 0,29–0,40), no el 1,008 (que era de las reglas de Pancholi, `outputs/pancholi/`, con otro estimador).
2. **Regla dura de `canal_p2p` corregida:** por la regla R2 de la taxonomía, `canal_p2p=True` = pago a persona con propósito declarado. La regla literal original rechazaba el 7,06 % de la fuente. Se reemplaza por: con `True`, `origen ∈ {compra, pago_recurrente, ingreso_no_asalariado}` y medio ∈ {transferencia, billetera}. Con las cinco reglas, la fuente tiene 0 violaciones.
3. **Holdout por perfil:** se aparta el 20 % de los **perfiles** (no de las filas); train = 96.386 filas. Partir por fila filtraría los mismos hogares a ambos lados.
4. **Piso/techo solo en Column Pair Trends:** el piso de marginales independientes conserva las marginales, así que piso≈techo en Column Shapes (0,979 vs 0,979); para Column Shapes y Overall se reporta la brecha absoluta al techo.

**Criterio de conservación de la elasticidad (contra el train).** Referencia = elasticidad del **train** (ê_train ≈ 0,33; IC del train calculado en la corrida, humo ≈ [0,267; 0,388]). Sea `r = ê_ctgan / ê_train`:
- **CONSERVA:** ê_ctgan > 0, su IC excluye 0, y **r ≥ 0,70** (incluye r > 1, "amplifica").
- **ATENÚA:** ê_ctgan > 0, su IC excluye 0, y **0,30 ≤ r < 0,70**.
- **NO CONSERVA:** **r < 0,30**, o ê_ctgan ≤ 0, o su IC incluye 0.

Se reportan ê_ctgan, su IC (bootstrap de filas), ê_train y `r`. Umbrales 0,70/0,30 declarados aquí, antes de correr. La comparación con el −0,003 de Pancholi es **cualitativa** (su IC era entre 10 semillas de entrenamiento, otra fuente de varianza), no un test de solape de IC.

**Añadidos:** `signo` entra como octava columna discreta (observable del clasificador, no deducible en `transferencias_p2p.indeterminada`) y tiene regla dura (§4.6). Si la tasa de rechazo > 10 %, se marca como resultado de fidelidad negativo, se reporta y se discute; la corrida continúa.

**Entorno:** `.venv-ctgan` aparte con `requirements-ctgan.txt` (sdv/rdt/sdmetrics exigen `pandas<3`; el repo fija `pandas==3.0.6`). Reproducibilidad: doble corrida + comparación de SHA-256; si no coincide a 300 épocas, se declara reproducibilidad estadística.

## Salidas
`outputs/ctgan/` con el dataset sintético v1, el `QualityReport`, la tasa de rechazo, la elasticidad comparada (con veredicto) y `manifest.json` (versiones, semillas, SHA-256, entorno).
