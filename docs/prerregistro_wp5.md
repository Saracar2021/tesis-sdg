# WP5 — Prerregistro de criterios de decisión (escrito ANTES de ejecutar)

Fecha: 23 sep 2026. Su SHA-256 queda en `outputs/pancholi/manifest.json` junto con la hora de la primera
corrida: si el archivo cambia después, el hash no coincide. Pipeline: `aman-jaglan/Capstone_Project`,
commit `d0a61e783353f52123b1821bc1876824d608d2a1`.

## Qué se ejecuta
- **Diseño A — rejilla de ingreso (etapas 2 y 3).** 12 niveles de ingreso anual, espaciados en escala log entre
  el mínimo y el máximo del ingreso que produce la etapa 1 del propio repo (`synthetic_customer_gan.csv`; los
  calcula el código). 13 clientes por nivel (156, la escala del repo: 155), hogar de 2 personas (mediana de su
  etapa 1), ZIP 20001. Etapa 2: `TransactionSimulator`, 30 tx/cliente (su valor). Etapa 3: `TransactionCTGAN`,
  100 épocas (su valor). Evaluación: un segundo sorteo de la etapa 2 con ≈5.000 tx por nivel y 60.000 muestras
  del CTGAN (≈5.000 por nivel), unidas al ingreso por `customer_id`. Semillas 42–51.
- **Diseño B — réplica literal de `transaction_synthesizer.py`.** 155 clientes de `synthetic_customers_deepseek.csv`,
  30 tx/cliente, CTGAN 100 épocas, 500.000 muestras. Semillas 42–51.
- **Diseño C (si el tiempo lo permite) — etapa 1 reentrenada** (`AdvancedIncomeModel`, 100 épocas, semilla 42).
- **Etapas 4 y 5 no se ejecutan:** requieren la API de Groq, bloqueada desde este entorno (HTTP 403, verificado),
  y la etapa 5 falla por código (KeyError `age`).

## Unidad y remuestreo
Unidad: registro de transacción sintético. Intervalos de conteos: Wilson 95 % sobre los registros agregados de
todas las semillas, más la desviación entre semillas. Parámetros derivados (elasticidad, pendientes): bootstrap
percentil 95 % remuestreando semillas con reemplazo (B = 10.000). Con 10 semillas el IC entre semillas es
aproximado; se reporta también el rango.

## H-P1 — relación ingreso–gasto
- **M1:** elasticidad β del monto medio por transacción respecto al ingreso (MCO de log monto medio por nivel
  sobre log ingreso, por semilla).
- **M2:** pendiente de la participación de `alimentos_mercado` en el monto sobre log(ingreso).
- **M3:** participación por categoría (conteo y monto) por nivel.
- **Sensibilidad al ingreso (hallazgo descriptivo):** «sensible» si el IC de β excluye 0.
- **H-P1 (no correspondencia con Colombia):** exige un referente colombiano (participación de alimentos por
  quintil de `ICGU`, ENPH Bogotá, `FEX_C`, a nivel hogar). **Este entorno no recibe microdatos**, así que el
  veredicto aquí es **NO CONCLUYENTE por diseño**. Regla para cuando exista el referente: confirmada si el IC de
  M2 del pipeline no se solapa con el IC de la misma pendiente en ENPH; refutada si se solapan.

## H-P2 — categorías
- **(a) Dominio de ocio:** ocio = `entretenimiento` (principal) y `entretenimiento` + hospedaje (sensibilidad).
  **Confirmada** si la participación por conteo del ocio supera a la de cada otra categoría nivel 1 con Wilson sin
  solapamiento; **refutada** si es menor que la de `alimentos_mercado` sin solapamiento; si no, no concluyente.
  Se reporta además la participación de las cuatro licencias citadas en el informe (Athletic Exhibition, Special
  Events, Inn And Motel, Skating Rink), cruzando `merchant_name` con el archivo de comercios.
- **(b) Cobertura (descriptivo):** participación de `alimentos_mercado`, `transporte` y
  `vivienda_servicios.servicios_publicos`; número de categorías nivel 1 de v1 con participación > 0.
- Etiqueta principal: `category`; `mapped_category` como sensibilidad (el CTGAN puede desacoplarlas).

## H-P3 — medio de pago y registros de extracto (D15)
- **(a)** ¿La salida ejecutada tiene un campo de medio de pago?
- **(b)** Participación (Wilson) de registros en `retiro_efectivo`, `transferencias_p2p`, `movimiento_propio` e
  `ingreso`.
- **Confirmada para las etapas ejecutadas** si no hay campo de medio de pago y (b) = 0 con cota superior de
  Wilson < 0,1 %. **Distribución de `payment_type` (etapa 4): NO CONCLUYENTE** (no ejecutable aquí). La lectura
  del prompt de la etapa 4 se reporta como *inferido*, no como resultado.
