# Guía de anotación de transacciones reales

**Basada en:** `taxonomia_gastos_colombia_v1` (a **congelar** como v1.1 en WP2 **antes** de anotar).
**Proyecto:** Datos sintéticos de transacciones — Colombia · **WP4 (Track B)** · **Versión:** 1.0 · 15 sep 2026
**Para:** 2 anotadores. Fin: producir etiquetas "gold" y medir acuerdo (**Cohen's Kappa**) para la evaluación TSTR (WP8).

> ⚠️ **La taxonomía debe estar congelada y citada antes de empezar.** Si durante la anotación aparece una ambigüedad del esquema, **no se cambia la taxonomía**: se documenta como insumo de la v2 (taxonomía §8) y se resuelve con las reglas de abajo.

---

## 1. Qué se anota: 6 campos por transacción

| Campo | Obligatorio | Valores |
|---|---|---|
| `categoria_n1` | ✅ | Una de las 16 categorías nivel 1 (§2). |
| `categoria_n2` | ⬜ | Subtipo de esa categoría (informativo; no entra al F1 macro). |
| `medio_pago` | ✅ | `efectivo · billetera_digital · tarjeta_debito · tarjeta_credito · transferencia_bancaria · fiado_credito_tienda · bono_subsidio · otro_nd` |
| `formalidad_comercio` | ✅ | `formal · informal · pequeno_comercio_indeterminado · no_aplica` |
| `canal_p2p` | ⬜ | `true` si el propósito fue **declarado por el voluntario** pero el canal fue transferencia a persona (regla R2). Si no, `false`/vacío. |
| `fuente_etiqueta` | ✅ | `texto` (etiquetable solo con la descripción) · `declaracion_voluntario` (requirió que el voluntario dijera el propósito). |

`fuente_etiqueta` **es crítico**: separa el techo real del clasificador (solo ve texto) de lo que solo se supo por declaración. No lo omitas.

## 2. Las 16 categorías nivel 1 (resumen operativo)

**Gasto (COICOP):**
`alimentos_mercado` (01 · mercado para casa) · `comidas_fuera` (11.1 · preparada/domicilios) · `transporte` (07) · `vivienda_servicios` (04 · arriendo, servicios públicos, gas) · `telecom_conectividad` (08 · recargas, planes, internet) · `salud` (06) · `educacion` (10) · `entretenimiento` (09/02 · streaming, apuestas, bares, licor/tabaco, mascotas) · `vestuario_cuidado_personal` (03/12.1) · `hogar_articulos` (05 · muebles, aseo hogar, servicio doméstico) · `obligaciones_financieras` (12.4–12.6 · pago de TC, cuotas de crédito, seguros, PILA, GMF) · `otros` (residual · impuestos no financieros, trámites, ininteligible).

**Operativas (no-gasto / propias del ecosistema):**
`transferencias_p2p` (persona↔persona sin propósito identificable) · `retiro_efectivo` · `movimiento_propio` (entre cuentas propias) · `ingreso` (salario, honorarios, ventas, subsidios).

> Definiciones, `incluye/excluye`, subtipos y ejemplos completos: ver `taxonomia_gastos_colombia_v1.json`. Esta guía no la reemplaza; la operacionaliza.

## 3. Reglas de decisión (R1–R7) — aplícalas en orden

1. **R1 — El bien manda sobre el canal.** Si el texto identifica comercio o bien, va la categoría del bien, sin importar el medio de pago. *Pagar la tienda con Nequi NO es P2P.*
2. **R2 — P2P es residual.** `transferencias_p2p` solo si la contraparte es persona **y** el propósito no es identificable. Si el voluntario declara el propósito (arriendo, transporte, servicio doméstico…): usa la **categoría del propósito** + `canal_p2p=true` + `fuente_etiqueta=declaracion_voluntario`.
3. **R3 — Retiros y movimientos propios nunca son gasto** (van a sus categorías operativas).
4. **R4 — Domicilios → `comidas_fuera` por defecto**; `alimentos_mercado` solo con evidencia (descriptor "market" o declaración).
5. **R5 — Pago de factura por PSE/corresponsal hereda la categoría de la factura** (servicios, telecom, educación…), no una categoría de "pagos".
6. **R6 — Comprar CON tarjeta de crédito → categoría del bien; PAGAR la tarjeta → `obligaciones_financieras.pago_tarjeta_credito`.**
7. **R7 — No adivinar.** Tras R1–R6, si sigue irresoluble: `transferencias_p2p.indeterminada` o `otros.ininteligible`. La incertidumbre se **registra**, no se inventa.

## 4. Ejemplos resueltos

| Descripción | categoria_n1 | n2 | medio_pago | formalidad | canal_p2p | fuente | Regla |
|---|---|---|---|---|---|---|---|
| `COMPRA EXITO CALLE 80` | alimentos_mercado | supermercado_cadena | tarjeta_debito | formal | — | texto | — |
| `Pago Nequi FRUVER LA 68` | alimentos_mercado | plaza_fruver | billetera_digital | pequeno_comercio_indeterminado | — | texto | R1 |
| `RAPPI COLOMBIA` | comidas_fuera | domicilios_app | tarjeta_debito | formal | — | texto | R4 |
| `Transferencia a PERSONA` (sin más) | transferencias_p2p | indeterminada | billetera_digital | no_aplica | false | texto | R7 |
| `Nequi a PERSONA (arriendo)` [declarado] | vivienda_servicios | arriendo | billetera_digital | informal | **true** | declaracion_voluntario | R2 |
| `RETIRO ATM SERVIBANCA` | retiro_efectivo | cajero_atm | tarjeta_debito | no_aplica | — | texto | R3 |
| `PAGO TC BANCOLOMBIA` | obligaciones_financieras | pago_tarjeta_credito | transferencia_bancaria | no_aplica | — | texto | R6 |
| `RECARGA NEQUI DESDE BANCOLOMBIA` | movimiento_propio | recarga_billetera | transferencia_bancaria | no_aplica | — | texto | R3 |
| `ABONO NOMINA EMPRESA XYZ` | ingreso | salario_nomina | transferencia_bancaria | no_aplica | — | texto | — |
| `PAGO PSE ENEL COLOMBIA` | vivienda_servicios | servicios_publicos | transferencia_bancaria | formal | — | texto | R5 |

## 5. Esquema de salida (una fila por transacción)

`data/reales/anotado/<anotador>_<seudonimo>.csv`, columnas:

```
tx_id,seudonimo,descripcion,monto,fecha,
categoria_n1,categoria_n2,medio_pago,formalidad_comercio,canal_p2p,fuente_etiqueta,
anotador,notas
```

- `anotador`: `A1` | `A2`. `notas`: dudas/justificación (alimenta la v2 y la conciliación).
- Enums exactos como en el JSON (sin tildes ni mayúsculas alternas): facilita el cálculo de Kappa.

## 6. Doble anotación y Cohen's Kappa (procedimiento)

1. **Independencia.** A1 y A2 anotan **por separado**, sin ver las etiquetas del otro. Con n = 200–300 tx es viable que **ambos anoten el 100%**; hazlo así. (Si el tiempo apremia, garantiza un solapamiento común de **≥ 80 tx** para el Kappa y reparte el resto.)
2. **Kappa por dimensión**, no uno solo:
   - `categoria_n1` → **métrica principal** (16 clases).
   - `medio_pago` y `formalidad_comercio` → por separado.
   - `canal_p2p` y `fuente_etiqueta` → acuerdo booleano (informativo).
3. **Interpretación (Landis & Koch):** <0.20 pobre · 0.21–0.40 aceptable · 0.41–0.60 moderado · 0.61–0.80 sustancial · 0.81–1 casi perfecto. **Meta: κ ≥ 0.61** en `categoria_n1`.
4. **Reporta también** el % de acuerdo bruto y la matriz de confusión entre anotadores por categoría: con clases desbalanceadas, Kappa solo puede engañar (paradoja de prevalencia).
5. **Conciliación (adjudicación).** Donde A1 ≠ A2, resolver por discusión o con un tercer adjudicador → producir la **etiqueta gold** (`categoria_n1_gold`, etc.). Registrar cada desacuerdo con su causa.
6. **Congelar** `transacciones_reales_etiquetadas.csv` (gold) + reporte de Kappa. Los desacuerdos que revelen fallas del esquema → **lista de cambios para v2**, no se toca la taxonomía en curso.

Snippet de referencia (determinista, ruta relativa; WP8 lo reusa):

```python
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

a1 = pd.read_csv("data/reales/anotado/A1_todos.csv")
a2 = pd.read_csv("data/reales/anotado/A2_todos.csv")
m = a1.merge(a2, on="tx_id", suffixes=("_a1", "_a2"))

for dim in ["categoria_n1", "medio_pago", "formalidad_comercio"]:
    k = cohen_kappa_score(m[f"{dim}_a1"], m[f"{dim}_a2"])
    print(f"{dim}: kappa={k:.3f}  acuerdo={ (m[f'{dim}_a1']==m[f'{dim}_a2']).mean():.3f }")
```

## 7. Regla de soporte para el reporte TSTR (recordatorio)

El F1 macro (WP8) se calcula sobre categorías nivel 1 con **soporte ≥ 10** en el conjunto real; las de soporte menor se **colapsan en `otros`** para el cómputo y se describen aparte. Con 200–300 tx y 16 categorías, varias caerán bajo el umbral: es esperable y está previsto en la taxonomía.

## 8. Riesgos metodológicos (de frente)

- **Kappa inestable con clases raras.** Categorías con 3–4 ejemplos inflan la varianza; por eso se colapsa a `otros` en el reporte y se prioriza κ de `categoria_n1`.
- **`declaracion_voluntario` = ruido de medición.** Depende de la memoria y honestidad del voluntario; por eso se marca y la evaluación se hace **separada** (texto vs. declaración): solo el subconjunto `texto` es el techo justo del clasificador.
- **Contaminación entre anotadores.** Si A1 y A2 discuten antes de terminar, el Kappa deja de medir acuerdo independiente. Mantener la fase 1 estrictamente separada.
- **Deriva del anotador.** En sesiones largas cambia el criterio. Mitigación: anotar en bloques, releer esta guía al inicio de cada bloque, y hacer una mini-calibración de 15–20 tx conjuntas **antes** de la fase independiente (esas no cuentan para el Kappa).
