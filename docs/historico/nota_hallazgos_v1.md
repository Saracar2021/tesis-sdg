# Nota de hallazgos — Validación de datos DANE (Chat 01)

**Autora:** Sara J. Cárdenas · **Notebook:** `01_validacion_datos.ipynb` · **Semilla:** 42
**Alcance de datos cargados:** GEIH meses = [2025-01] (n=1); ENPH 2016-2017.
Todas las cifras se derivan de `value_counts`/`groupby`/medias ponderadas en el notebook; ninguna está escrita a mano.

## Tabla de reconciliación

| Indicador | Cifra informe | Cifra recalculada | ¿Coincide? | Comentario |
|---|---|---|---|---|
| Estrato ENPH E1 (%) | 36.3% | 36.28% (cruda) / 33.80% (FEX) | sí | Cruda reproduce el informe; ponderada FEX difiere. Fuente ENPH 2016-17, no GEIH (H6). |
| Estrato ENPH E2 (%) | 34.5% | 34.51% (cruda) / 36.33% (FEX) | sí | Cruda reproduce el informe; ponderada FEX difiere. Fuente ENPH 2016-17, no GEIH (H6). |
| Estrato ENPH E3 (%) | 20.2% | 20.17% (cruda) / 22.51% (FEX) | sí | Cruda reproduce el informe; ponderada FEX difiere. Fuente ENPH 2016-17, no GEIH (H6). |
| Estrato ENPH E4+E5+E6 (%) | 7.5% | 7.48% (cruda) / 7.36% (FEX) | sí | Reproduce; el informe atribuye la distribución a GEIH pero proviene de ENPH (H6). |
| Efectivo gastos diarios NC2R_CC_P6 (%) | 73.1% | 73.06% (cruda) / 69.59% (FEX) | sí | Reproduce sin ponderar; base = todos los hogares, blanco=sin dato (25.5%). Ponderada FEX difiere. |
| Efectivo P438 gastos menos frec. (%) | 97.6% | 97.56% (cruda) / 96.15% (FEX) | sí | Reproduce la cifra hardcodeada al apilar las 29 columnas de medio de pago sin ponderar. Es proporción de instancias por subcapítulo, no de transacciones; ponderada FEX ≈ 96%. |
| Ocupados con ingreso (conteo) | 14.975 | 14,975 (enero 2025, sin ponderar) | sí | Reproduce, pero es SOLO enero (H4). Población ponderada ≈ 22,902,835. |
| Contrato verbal P6440 (%) | 40.6% | 40.60% (cruda) / 40.42% (FEX) | sí | Reproduce sin ponderar (enero). Unidad: persona ocupada. Ponderada FEX difiere. |
| Ingreso medio estrato 1 (COP) | $1,405,582 | $1,360,291 | no | Difiere ~3%: informe usó ingreso crudo sin FEX; aquí ponderado. Unidad: ocupado (H8). |
| Ingreso medio estrato 2 (COP) | $1,732,948 | $1,722,145 | no | Difiere ~1%: informe usó ingreso crudo sin FEX; aquí ponderado. Unidad: ocupado (H8). |
| Ingreso medio estrato 3 (COP) | $2,132,129 | $2,138,842 | no | Difiere ~0%: informe usó ingreso crudo sin FEX; aquí ponderado. Unidad: ocupado (H8). |
| Ingreso medio estrato 4 (COP) | $3,740,578 | $4,483,338 | no | Difiere ~20%: informe usó ingreso crudo sin FEX; aquí ponderado. Unidad: ocupado (H8). |
| Ingreso medio estrato 5 (COP) | $5,746,814 | $7,520,805 | no | Difiere ~31%: informe usó ingreso crudo sin FEX; aquí ponderado. Unidad: ocupado (H8). |
| Ingreso medio estrato 6 (COP) | $6,648,988 | $8,867,473 | no | Difiere ~33%: informe usó ingreso crudo sin FEX; aquí ponderado. Unidad: ocupado (H8). |
| Ingreso medio Q1 (COP) | $750,291 | $656,266 | no | Fronteras/medias ponderadas; informe usó qcut crudo con empates (H7). |
| Ingreso medio Q2 (COP) | $1,299,709 | $1,205,537 | no | Fronteras/medias ponderadas; informe usó qcut crudo con empates (H7). |
| Ingreso medio Q3 (COP) | $1,440,520 | $1,336,730 | no | Fronteras/medias ponderadas; informe usó qcut crudo con empates (H7). |
| Ingreso medio Q4 (COP) | $1,927,110 | $1,802,379 | no | Fronteras/medias ponderadas; informe usó qcut crudo con empates (H7). |
| Ingreso medio Q5 (COP) | $4,898,257 | $5,340,562 | no | Fronteras/medias ponderadas; informe usó qcut crudo con empates (H7). |

## Lectura de los hallazgos H1–H8

- **H1 (P438 97.6% hardcodeado):** la cifra **se reproduce** al apilar las 29 columnas de medio de pago
  de la batería P438 y tomar la proporción de efectivo (código 3) **sin ponderar** (97.56%).
  Estaba hardcodeada; ahora se deriva. Ponderada por FEX ≈ 96.1%. **Riesgo:** es proporción de
  *instancias de pago por subcapítulo*, no de transacciones ni de pesos → declarar la unidad al citarla.
- **H2 (cifras a mano):** todas las figuras salen ahora de conteos/agrupaciones reales.
- **H3 (sin FEX):** cada indicador se reporta *crudo* (reproduce el informe) y *ponderado por FEX* (corregido).
  Las versiones ponderadas difieren de las crudas → las cifras poblacionales del informe deben migrar a FEX.
- **H4 (GEIH solo enero):** confirmado — hay 1 mes(es). El conteo de 14.975 ocupados y el 40.6% verbal
  son de **enero 2025**, no "todos los meses". El notebook apila automáticamente los meses que se agreguen a
  `data/geih/AAAA-MM/` (excluyendo 2026-02) y ajusta FEX por número de meses.
- **H5 (código truncado):** el notebook corre de punta a punta sin celdas incompletas.
- **H6 (dos fuentes de estrato):** explícito — la *distribución* de estrato es ENPH 2016-17 (`P8520S1A1`) y el
  *ingreso por estrato* es GEIH 2025 (`P4030S1A1`); son encuestas y años distintos. Se muestran ambas distribuciones.
- **H7 (quintiles con qcut crudo):** se recalculan **fronteras y medias ponderadas** por FEX; difieren de la Tabla II.
- **H8 (unidad de ingreso):** `P6500` es ingreso **laboral del ocupado**, no del hogar. Las cifras por estrato/quintil
  se declaran como **ingreso laboral medio por persona ocupada**.

## Riesgos metodológicos adicionales
- `Gastos_diarios_Urbanos.csv` tiene 1,048,575 filas. Si es exactamente 1.048.575 (= 2^20−1) hay **posible truncamiento**
  al límite de Excel; verificar el export original del DANE antes de usarlo en calibración.
- El 73.1% (diario), 97.6% (menos frecuente) y 77.8% (Banrep) son **universos distintos** (hogar vs. instancias por
  subcapítulo vs. valor de transacciones). No son intercambiables: declarar cuál calibra cada etapa del protocolo.
- Cruce ocupados × hogar por `DIRECTORIO+SECUENCIA_P+HOGAR`: cobertura de estrato ≈ 98.6% (documentar la pérdida).
