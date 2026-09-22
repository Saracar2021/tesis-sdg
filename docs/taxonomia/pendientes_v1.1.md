# Taxonomía — correcciones pendientes para v1.1

> No regenerar la taxonomía todavía. Este archivo acumula lo que hay que corregir cuando
> se abra el Chat 03. Fecha de apertura: 20 sep 2026.

## Condiciones para congelar v1.1
1. ~~Cerrada la verificación de `P438*` (¿es medio de pago por subcapítulo de gasto?).~~ **Cumplida (20 sep 2026):** son 29 columnas, una por subcapítulo del Cuadernillo 3, con sus códigos verificados (T2). Gaps abiertos que **no** bloquean el congelamiento pero deben declararse: no existen `P438J14` ni `P438K11`, y la correspondencia de `P438J13` con un bloque del Cuadernillo 3 no está verificada (`outputs/distribuciones/enph_p438_gaps.csv`).
2. Revisadas al menos 50 descripciones reales de extractos, para validar que las categorías
   y los ejemplos corresponden a cómo aparecen los comercios en la práctica.

Congelar antes de (2) es congelar a ciegas: el esquema existe para anotar transacciones reales.

## Correcciones factuales ya identificadas

| # | Dónde | Dice | Debe decir | Estado |
|---|---|---|---|---|
| T1 | `metadata.fuentes` | «variable NC2R_CC_P6 (forma de pago, gastos diarios cuadernillo C)» | Cuadernillo **2, capítulo D**: gastos diarios urbanos (14 días) / semanales rurales. No es «cuadernillo C». | Verificado 20 sep |
| T2 | `metadata.fuentes` | Códigos P438: 1 débito, 2 crédito, 3 efectivo, **4 bonos, 5 cheques**, 6 otro | **Los códigos de la taxonomía son correctos.** Verificados contra `Cuadernillo 3.pdf`, pregunta (6) de cada subcapítulo: 1 débito, 2 crédito, 3 efectivo, **4 bonos, 5 cheques**, 6 otro. Los de `NC2R_CC_P6` son otros (Cuadernillo 2 urbano, sección D2, pregunta 2): 1 débito, 2 crédito, 3 efectivo, **4 fiado**, **5 bonos**, 6 otra. Los dos esquemas difieren en 4 y 5. El DDI rotula el 4 de `NC2R_CC_P6` como «fiador»: es un error de rotulado, el cuadernillo dice «Fiado». | **Verificado 20 sep** (`CLAUDE.md`, `docs/bitacora.md`) |
| T3 | `dimension_medio_pago.*.equivalencia_enph_p438` | Cada valor mapea a un código P438 | Los esquemas difieren (T2), así que hacen falta **dos** campos de equivalencia, uno por variable (`P438*` y `NC2R_CC_P6`), nunca uno solo. Un mismo medio no tiene el mismo código en ambas: p. ej. «bonos» es 4 en `P438*` y 5 en `NC2R_CC_P6`. | **Desbloqueado (T2 verificado).** Falta aplicarlo al regenerar la taxonomía v1.1 |
| T4 | `dimension_medio_pago` | `fiado_credito_tienda` con `equivalencia_enph_p438: null` | `NC2R_CC_P6 = 4` es **fiado** (no «fiador»): esa categoría **sí** tiene anclaje en ENPH, solo para gastos frecuentes y en el campo de `NC2R_CC_P6`. `P438*` no tiene código de fiado, así que `equivalencia_enph_p438` sigue en `null` para gastos menos frecuentes. Es un anclaje débil: 4 hogares en la muestra de Bogotá (0,09 % de los hogares con respuesta; `outputs/distribuciones/enph_forma_pago_nc2r.csv`). | **Verificado 20 sep.** Falta aplicarlo en v1.1 |

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

## T5 — Afirmaciones sobre el pipeline de Pancholi (22 sep 2026)

El §7 de la taxonomía v1 decía que las categorías de ocio de Washington D.C. «dominaban espuriamente el output del generador original» y que las diferencias responden a «tres fallas empíricas documentadas». El pipeline no se ha ejecutado: son hipótesis. Ya corregido en el `.md` v1 del repo; la v1.1 debe mantener esa redacción y no citar salidas de Pancholi hasta que el Chat 01B las produzca.