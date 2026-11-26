# Instrucciones para el anotador 2 (A2) — WP4

**Versión 1.0 · 2026-11-26** · Basadas en la guía de anotación v1.0 y la taxonomía v1.1.0
(`docs/taxonomia/taxonomia_gastos_colombia_v1.md`). Tiempo total estimado: **≈ 2 h 35**.

## 0. Antes de empezar

1. **Firma el compromiso de confidencialidad.** El archivo trae movimientos bancarios reales anonimizados. No lo
   copies, no lo compartas y no lo subas a ninguna herramienta en línea (tampoco a una IA).
2. **Sesión de calibración con Sara (≈ 40 min):** anotan juntos 20 ítems de práctica (`calibracion.xlsx`) que no
   cuentan para nada. Pregunta todo ahí.
3. **Después trabajas solo.** No comentes ningún ítem con Sara hasta que los dos terminen: el acuerdo entre ustedes es
   lo que se mide.

## 1. Tu archivo: `lote_A2.xlsx`

- Las columnas **grises no se editan** (están bloqueadas). Llenas cuatro columnas:

| Columna | Qué poner |
|---|---|
| `categoria_n1` | **Obligatoria.** Una de las 16 categorías (lista desplegable). |
| `categoria_n2` | Opcional. El subtipo, si es evidente (lista desplegable; debe pertenecer a la categoría de `categoria_n1`). |
| `duda` | `1` si no estás seguro; `0` o vacío si sí lo estás. |
| `notas` | Breve: por qué elegiste la categoría cuando dudaste, o qué regla aplicaste. |

- **Anota en el orden de la columna `orden`** (1 → 200). Si ordenas la hoja, vuelve a ordenarla por `orden`.
  Los **primeros 154** son prioritarios: si a las **12:00 del 26 nov** no has terminado los 200, con esos basta.
- Guarda a menudo. Al terminar, entrega solo `lote_A2.xlsx` por el canal acordado con Sara.

## 2. Qué ves en cada fila

| Campo | Significado |
|---|---|
| `cuenta_tipo` | `banco` = cuenta de ahorros · `tarjeta_credito` = tarjeta de crédito |
| `signo` | `egreso` = sale dinero · `ingreso` = entra. En tarjeta: `egreso` = compra; `ingreso` = pago a la tarjeta, reverso o devolución |
| `monto` | Pesos colombianos, sin signo |
| `descripcion` | Texto del extracto, anonimizado: `PERSONA` = nombre de una persona · `LLAVE` = llave Bre-B · `#` = dígitos borrados |

Decide **solo con lo que ves en la fila**. No hay fecha ni dueño, a propósito: el clasificador tampoco los tiene.
No busques en internet comercios que no conoces (Sara sigue la misma regla): si no puedes saber qué es, aplica R7
y marca `duda = 1`.

## 3. Reglas (aplícalas en orden)

1. **R1 — El bien manda sobre el canal.** Si reconoces el comercio o el bien, va su categoría, sin importar cómo se pagó.
2. **R2 — P2P es residual.** `transferencias_p2p` solo si la contraparte es una persona **y** no se sabe el propósito.
3. **R3 — Retiros y movimientos entre cuentas propias no son gasto:** `retiro_efectivo` o `movimiento_propio`.
4. **R4 — Domicilios de plataforma → `comidas_fuera`**, salvo evidencia de mercado.
5. **R5 — Pago de factura por PSE → la categoría de la factura** (servicios, telecom, educación…).
6. **R6 — Comprar *con* tarjeta → categoría del bien. *Pagar* la tarjeta → `obligaciones_financieras`.**
7. **R7 — No adivines.** Si tras R1–R6 no se puede saber: `transferencias_p2p` (subtipo `indeterminada`) si es entre
   personas, u `otros` (subtipo `ininteligible`) en cualquier otro caso. Marca `duda = 1`.

## 4. Las 16 categorías

| `categoria_n1` | Incluye | Ejemplos (de la taxonomía) |
|---|---|---|
| `alimentos_mercado` | Mercado para el hogar: supermercado, tienda, fruver | `COMPRA EXITO CALLE 80`, `D1 SAS` |
| `comidas_fuera` | Comida preparada: restaurantes, cafeterías, comida rápida, domicilios | `RAPPI COLOMBIA`, `FRISBY SA` |
| `transporte` | Transporte público, apps, taxi, combustible, peajes, parqueadero | `RECARGA TULLAVE`, `UBER BV` |
| `vivienda_servicios` | Arriendo, administración, energía, agua, gas | `PAGO PSE ENEL COLOMBIA`, `VANTI SA ESP` |
| `telecom_conectividad` | Celular, datos, internet hogar, TV por suscripción | `RECARGA CLARO`, `WOM COLOMBIA` |
| `salud` | Farmacia, consultas, exámenes, odontología, óptica | `CRUZ VERDE`, `DROGUERIA LA REBAJA` |
| `educacion` | Matrículas, pensiones, cursos, útiles, plataformas educativas | `PAGO PSE UNIVERSIDAD NACIONAL`, `PLATZI` |
| `entretenimiento` | Streaming, cine, eventos, bares, licor, apuestas, mascotas | `NETFLIX.COM`, `SPOTIFY` |
| `vestuario_cuidado_personal` | Ropa, calzado, peluquería, cosméticos, aseo personal | `ARTURO CALLE`, `KOAJ` |
| `hogar_articulos` | Muebles, electrodomésticos, aseo del hogar, servicio doméstico | `HOMECENTER`, `ALKOSTO` |
| `obligaciones_financieras` | Pago de tarjeta, cuotas de crédito, seguros, seguridad social, comisiones y 4×1000 | `PAGO TC BANCOLOMBIA`, `CUOTA CREDITO DAVIVIENDA` |
| `transferencias_p2p` | Dinero entre personas sin propósito identificable | `Transferencia enviada a PERSONA` |
| `retiro_efectivo` | Cajero o corresponsal | `RETIRO ATM SERVIBANCA` |
| `movimiento_propio` | Entre productos del mismo titular: recarga de billetera, traslados, bolsillos | `RECARGA NEQUI DESDE BANCOLOMBIA` |
| `ingreso` | Salario, honorarios, ventas, subsidios, intereses y rendimientos | `PAGO NOMINA EMPRESA XYZ`, `ABONO INTERESES` |
| `otros` | Impuestos, trámites, donaciones, o texto ininteligible | `PAGO SIM PREDIAL`, `PAGO REF 99213` |

Definiciones completas y subtipos: `docs/taxonomia/taxonomia_gastos_colombia_v1.md`.

## 5. Casos frecuentes en extractos

| Si ves… | Aplica |
|---|---|
| Compra con tarjeta en un comercio que reconoces | R1/R6: categoría del comercio |
| Pago a la tarjeta (en la cuenta, o `ingreso` en la tarjeta) | R6: `obligaciones_financieras` · `pago_tarjeta_credito` |
| PSE con facturador identificable | R5: categoría de la factura |
| PSE sin facturador (solo el banco o la pasarela) | R7 |
| Intereses o rendimientos de la cuenta | `ingreso` · `rendimientos` |
| Gravamen 4×1000, comisiones, cuota de manejo | `obligaciones_financieras` · `comisiones_gmf` |
| Transferencia a o de `PERSONA` | R2/R7: `transferencias_p2p` (`enviada_persona`, `recibida_persona` o `indeterminada`) |
| Comercio que no reconoces | R7 + `duda = 1` |
| Caso que la taxonomía no cubre | R7 + `duda = 1` + nota corta (p. ej. «reverso») |

Cuatro casos que la taxonomía no resuelve (reversos y devoluciones, PSE sin facturador, transferencias a billeteras
sin decir si son propias, compras a nombre de una persona) se acuerdan en la calibración, con la hoja
`07_hoja_calibracion_casos.md`. Aplica lo acordado igual en todo el archivo.
