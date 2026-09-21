# Taxonomía — correcciones pendientes para v1.1

> No regenerar la taxonomía todavía. Este archivo acumula lo que hay que corregir cuando
> se abra el Chat 03. Fecha de apertura: 20 sep 2026.

## Condiciones para congelar v1.1
1. Cerrada la verificación de `P438*` (¿es medio de pago por subcapítulo de gasto?).
2. Revisadas al menos 50 descripciones reales de extractos, para validar que las categorías
   y los ejemplos corresponden a cómo aparecen los comercios en la práctica.

Congelar antes de (2) es congelar a ciegas: el esquema existe para anotar transacciones reales.

## Correcciones factuales ya identificadas

| # | Dónde | Dice | Debe decir | Estado |
|---|---|---|---|---|
| T1 | `metadata.fuentes` | «variable NC2R_CC_P6 (forma de pago, gastos diarios cuadernillo C)» | Cuadernillo **2, capítulo D**: gastos diarios urbanos (14 días) / semanales rurales. No es «cuadernillo C». | Verificado 20 sep |
| T2 | `metadata.fuentes` | Códigos P438: 1 débito, 2 crédito, 3 efectivo, **4 bonos, 5 cheques**, 6 otro | Verificar contra `Cuadernillo 3.pdf`. **Conflicto:** el DDI da para `NC2R_CC_P6` 4 fiador, 5 bonos, 6 otro. Los dos esquemas difieren en 4 y 5. | Por verificar |
| T3 | `dimension_medio_pago.*.equivalencia_enph_p438` | Cada valor mapea a un código P438 | Depende de T2. Si los esquemas difieren, hacen falta **dos** campos de equivalencia, uno por variable, nunca uno solo. | Bloqueado por T2 |
| T4 | `dimension_medio_pago` | `fiado_credito_tienda` con `equivalencia_enph_p438: null` | Si `NC2R_CC_P6 = 4` es fiador, esa categoría **sí** tiene anclaje en ENPH para gastos frecuentes. | Bloqueado por T2 |

## Decisiones de alcance que afectan la taxonomía

- **Dominio: Bogotá urbano.** Los anclajes a «lugar de compra» rural del cuadernillo 2 rural
  quedan fuera de alcance. Revisar `dimension_formalidad_comercio.anclaje_enph_lugar`.
- **Unidad de las cifras de medio de pago:** son «% de hogares cuya forma de pago principal
  es X», no participación de transacciones. La nota metodológica de la taxonomía no debe
  sugerir lo contrario.
- **Sesgo de los datos reales:** un extracto bancario no ve el efectivo (un retiro en cajero
  es una fila, no quince compras). La taxonomía se usará para anotar transacciones
  bancarizadas; el `medio_pago = efectivo` quedará subrepresentado en el conjunto real
  frente a lo que dice ENPH. Declararlo en la nota metodológica.
- **Regla de soporte ≥ 10** para F1 macro: revisar el umbral cuando se sepa el tamaño real
  del corpus anotado.
