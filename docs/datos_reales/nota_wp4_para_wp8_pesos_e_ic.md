# Nota de WP4 para WP8 — pesos de muestreo e intervalo de confianza del test real

**Fecha:** 2026-11-25 · **Origen:** `docs/datos_reales/05_prerregistro_muestreo_anotacion.md` (D-M6, D-M7)
**Afecta a:** `tools/etapa4_tstr.py` (modo `--test`). No cambia el entrenamiento, la entrada del clasificador ni la F1-macro principal.

## 1. Por qué el test real trae pesos (D-M6)

El test real **no es una muestra proporcional** de los extractos. Se sobremuestrearon a propósito las categorías raras
(mínimo 10 filas por estrato) y se limitó a 3 filas cada descripción repetida, porque con muestreo proporcional
9 de las 16 categorías quedarían con menos de 10 ejemplos y la regla de soporte las fusionaría en `otros`.

Consecuencia: la **F1-macro** (promedio por clase) sí es interpretable sobre la muestra, pero la **exactitud** no.
La exactitud es un promedio por fila y depende de cuántas filas hay de cada clase: en la muestra, las clases
frecuentes del extracto real (p. ej. transferencias entre cuentas propias: ≈ 24 % del marco según la heurística de muestreo) pesan mucho menos que
en la realidad (≈ 8 % de la muestra). Sin corrección, la exactitud reportada describe una mezcla de clases que no
existe en ningún extracto.

Cada fila trae `peso_muestreo = 1/π`, con π su probabilidad exacta de inclusión según el diseño (dos etapas,
semilla 42). **Los pesos salen solo del diseño muestral y de variables observables; no usan etiquetas ni calibran
nada.**

## 2. Cambio pedido (mínimo)

Si el test trae la columna opcional `peso_muestreo`:

1. Añadir `accuracy_ponderada = Σ wᵢ·1[yᵢ = ŷᵢ] / Σ wᵢ` (estimador de Hájek) junto a `accuracy`, que se conserva.
2. IC95 de `accuracy_ponderada` con el mismo bootstrap (recalcular la media ponderada en cada réplica).
3. Opcional: prevalencia ponderada de cada clase real, en la tabla por clase.
4. `peso_muestreo` **nunca** es feature: no entra en `texto_entrada()`. Añadirlo a la lista de columnas de anotación.
6. Nota: el tope por descriptor deja pesos muy desiguales (n efectivo de Kish = 48 de 200; ver pre-registro §3). El
   IC de la exactitud ponderada saldrá ancho; es esperado, no un error del arnés.
5. Sin cambios: la F1-macro con regla de soporte sigue **sin ponderar** y sigue siendo la métrica principal; el
   soporte (≥ 10) se cuenta en filas de la muestra, no en filas ponderadas.

Sin la columna, el script se comporta igual que hoy.

## 3. Intervalo de confianza (D-M7)

**Desviación aprobada el 2026-11-25 (pre-registro 05 v1.0, D-M7).** Hoy, si el test trae `voluntario_id`,
`_indices_bootstrap()` remuestrea conglomerados completos y eso es el IC principal. El test real tiene **6 grupos de
extractos** en el marco (V04, V05, V06, V07, V09, V10; V08 queda fuera por mes). Un grupo no es necesariamente un
voluntario: V09/V10 podrían ser la misma persona. Con 6 unidades:

- Solo existen 462 réplicas distintas posibles; el IC percentil queda dominado por pocas combinaciones.
- Las clases están concentradas por grupo: las compras con tarjeta solo existen en V09/V10, y el 77 % de los
  ingresos y el 69 % de los retiros (por la heurística de muestreo) salen de un solo grupo. Una réplica sin ese
  grupo pierde clases enteras, la regla de soporte cambia qué clases se evalúan y el IC termina mezclando métricas
  distintas.

Por otro lado, el bootstrap por fila supone filas independientes, y las filas de un mismo titular no lo son: ese IC
**subestima** la incertidumbre entre personas. El tope de 3 filas por descripción atenúa, pero no elimina, esa
dependencia.

**Propuesta:**

- **IC principal:** bootstrap por fila, **estratificado por `estrato_muestreo`** (columna que trae el test),
  coherente con el diseño. Alcance declarado: incertidumbre de muestreo **dentro de estos extractos**, no
  generalización a nuevos titulares.
- **Sensibilidad:** el bootstrap por conglomerado actual, entendido como **grupo de extractos** (no titular),
  reportado al lado, con la nota de que 6 grupos no bastan para un IC fiable.
- Implementación sugerida: un argumento `--ic {fila,conglomerado,ambos}` (por defecto `ambos` en modo TSTR), en vez
  de decidir por la presencia de `voluntario_id`.

## 4. Columnas del test real (contrato)

`descripcion, monto, fecha, signo, cuenta_tipo, categoria_n1, fuente_etiqueta, voluntario_id` (obligatorias WP4) +
`peso_muestreo, estrato_muestreo, tx_id, categoria_n2, medio_pago, formalidad_comercio, canal_p2p` (ninguna es feature).
`signo` llega ya recodificado a `-` / `+`, como el sintético.
