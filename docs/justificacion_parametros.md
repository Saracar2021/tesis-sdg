# Justificación de parámetros de diseño

Desarrolla la lista de parámetros y decisiones sin justificación escrita identificada en la
bitácora (WP0, 22 sep 2026). Tipos:

- **convención:** valor fijado por una práctica metodológica o normativa estándar, no derivado de
  un cálculo propio del proyecto.
- **cálculo:** valor derivado de un cálculo reproducible, con código y salida en `outputs/`.
- **pendiente:** sin justificación todavía; queda abierto para que lo resuelva la autora.

## Tabla

| Archivo:línea | Parámetro | Justificación | Tipo |
|---|---|---|---|
| `CLAUDE.md:276`, `docs/protocolo_tecnico.md:186,356`, `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:24` | Semilla `SEED = 42` | El valor es arbitrario y no tiene significado estadístico. Lo que exige la reproducibilidad es que la semilla sea fija y esté declarada (no un valor concreto). La sensibilidad a la semilla se reporta ejecutando con varias semillas y mostrando la dispersión de los resultados. | convención |
| `docs/protocolo_tecnico.md:350`, `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:65` | 2 anotadores | El kappa de Cohen está definido para dos evaluadores. Con tres o más habría que usar el kappa de Fleiss, que mide un acuerdo distinto (acuerdo promedio entre múltiples pares) y complicaría la comparación con el criterio de aceptación planteado. Cita verificada: Cohen, J. (1960). "A Coefficient of Agreement for Nominal Scales." *Educational and Psychological Measurement*, 20(1), 37-46. DOI: 10.1177/001316446002000104. | convención |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:74` | Borrado del extracto original a los 15 días | Responde al principio de finalidad (Ley 1581 de 2012, art. 4, literal b: "El Tratamiento debe obedecer a una finalidad legítima de acuerdo con la Constitución y la Ley, la cual debe ser informada al Titular"): el archivo original solo se conserva el tiempo necesario para anonimizarlo y verificar la anonimización; cumplida esa finalidad, se suprime. El titular puede además revocar la autorización o solicitar la supresión del dato (art. 8, literal e); el texto literal de ese literal la condiciona a que el tratamiento no respete los principios, derechos o garantías legales y constitucionales, no la formula como un derecho de supresión sin condición — se declara así para no sobre-citar la norma. **No aplica** un "principio de temporalidad" de la Ley 1581: ese principio pertenece a la Ley 1266 de 2008 (hábeas data financiero), que no rige este tratamiento. **Los 15 días en sí son un plazo operativo estimado** para procesar los extractos de una tanda, no un requisito legal — la ley exige "el tiempo necesario", no un número de días. | convención |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:15,72` | 3 meses fijos (dic-2025, abr-2026, ago-2026) | Tres observaciones permiten contrastar un mes atípico contra dos de referencia; con dos no se distingue cuál de los dos es el atípico. La razón de cada mes en particular (fin de año, primer semestre, mes reciente) ya está en `docs/datos_reales/01_consentimiento_informado_v1.1.md` §1. El límite superior (no más de 3) lo impone la carga para el voluntario, que debe descargar y entregar un extracto por mes. | convención |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:14` | 20 voluntarios | Es una muestra por conveniencia, formada por personas de la red de la autora dispuestas a entregar extractos. No es una muestra probabilística y no permite inferencia a la población bogotana; su función es dar un conjunto de evaluación etiquetado, no representar a la población. **Se declara como limitación explícita en la tesis** (ya en L8, `docs/protocolo_tecnico.md`), no se resuelve aquí. | convención |
| `docs/protocolo_tecnico.md:170,351` | Congelar taxonomía tras revisar ≥ 50 descripciones reales (unificado: ambas líneas decían cifras distintas, "≥ 50" y "~50"; ya corregido a "≥ 50" en ambas, punto 2 del encargo anterior) | Criterio operativo: revisar descripciones reales hasta que dejen de aparecer categorías nuevas, con 50 como mínimo. Si a las 50 siguen apareciendo categorías nuevas, se amplía la revisión y se documenta. | convención |
| `CLAUDE.md:46-47`, `docs/protocolo_tecnico.md:137,147` | Umbral de celda rala ≈ 30 observaciones (`n_menor_30`) | PENDIENTE — no está en la base entregada para las convenciones; el propio documento ya aclara que es "una marca informativa, no el umbral" y que el real se fija en WP3 | pendiente |
| `CLAUDE.md:191`, `docs/protocolo_tecnico.md:268,278-281` | Umbral de diferencia material = 1 p.p. entre meses | PENDIENTE — no está en la base entregada | pendiente |
| `docs/protocolo_tecnico.md:184,331` | Meta de ≥ 5.000 transacciones sintéticas (dataset v1) | PENDIENTE — no está en la base entregada | pendiente |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:83` | Con 12–15 personas el conjunto "sigue siendo útil" | PENDIENTE — no está en la base entregada | pendiente |
| `docs/protocolo_tecnico.md:210,332` | Regla de soporte ≥ 10 por clase para F1 macro | Con los tamaños de muestra considerados (N = 360, 450, 600), un soporte de 10 exige una participación mínima de 2,78 %, 2,22 % y 1,67 % respectivamente. Calculado en `tools/calculos_diseno_muestral.py` → `outputs/diseno_muestral/a_soporte_minimo_por_n.csv`. El cruce contra la participación observada en ENPH Bogotá (proxy declarado, ver `b_participacion_enph_por_categoria.csv`) muestra que ninguna de las 8 categorías de la taxonomía **ya calculadas** cae por debajo del umbral en ningún N. De las 8 categorías restantes, **6 existen en ENPH pero no se han calculado todavía** (ver §"Corrección sobre las categorías sin calcular" abajo) y solo 2 no tienen fuente ENPH en absoluto; el riesgo real de soporte insuficiente no puede evaluarse para esas 6 hasta que se calculen | cálculo |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:24` | 30 movimientos/persona, 10/mes → 600 movimientos | El valor N = 600 es uno de los tres tamaños evaluados en `tools/calculos_diseno_muestral.py` (junto con 360 y 450); con soporte ≥ 10 exige participación ≥ 1,67 %, cumplida por las 8 categorías ya calculadas. La magnitud de 30/10 en sí (frente a otra combinación con el mismo total) no queda resuelta por este cálculo — solo el total N | cálculo |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:26` | Mínimo de 200 movimientos de solapamiento para Kappa | Calculado en `tools/calculos_diseno_muestral.py` → `outputs/diseno_muestral/c_kappa_ic95_ancho.csv`: con n = 200, acuerdo esperado por azar pe ≈ 0,137 (8 categorías ya calculadas) y acuerdo observado hipotético de 0,80 o 0,90, el ancho aproximado del IC 95 % de kappa es de 0,128 y 0,096 respectivamente (fórmula aproximada tipo Fleiss/Sim-Wright, declarada como aproximación no verificada contra la fuente primaria). Con n = 100 el ancho sube a 0,182 y 0,136; con n = 300 baja a 0,105 y 0,079 | cálculo |
| `CLAUDE.md:264-265` | Celdas de posición ocupacional × cotiza pensión: "no requieren acción" | PENDIENTE — queda para que lo resuelva la autora | pendiente |
| `docs/protocolo_tecnico.md:308` (L6) | No se cambió a cortes fijos para las fronteras de `INGLABO` | PENDIENTE — queda para que lo resuelva la autora | pendiente |
| `docs/protocolo_tecnico.md:203` | Tres clasificadores específicos (regresión logística TF-IDF, BETO, LLaMA 3 few-shot) | PENDIENTE — queda para que lo resuelva la autora | pendiente |

## Corrección sobre las categorías sin calcular (verificado 22 sep 2026)

La entrada anterior de este documento decía que "8 de 16 categorías de la taxonomía no tienen
fuente ENPH". **Es impreciso.** Se verificó contra los METADATOS de ENPH (cuadernillos y DDI en
`data/raw/ENPH_2017/_metadatos/`, no los microdatos) si cada una de las 8 existe o no en ENPH:

| Categoría | Estado | Detalle |
|---|---|---|
| `alimentos_mercado` | **Existe, falta calcular** | Cuadernillo 2, Capítulo C ("Características del gasto en alimentos de los hogares") → `gastos_diarios_capitulo_c.txt` y `gastos_diarios_mercados.csv` |
| `comidas_fuera` | **Existe, falta calcular** | Cuadernillo 2, capítulo D1 → `gastos_diarios_hogar_comidas_fuera.csv` (hogar) y `gastos_personales_comidas_fuera.csv` (personal) |
| `telecom_conectividad` | **Existe, falta calcular** (mezclado con transporte en la pregunta de medio de pago) | Cuadernillo 3, subcapítulo H11 ("Servicio telefónico, internet y pasajes"): el propio cuadernillo imprime ítems de comunicaciones (ej. "08300501 Internet fijo") dentro de H. Separable por monto en `gastos_menos_frecuentes_articulos.txt` (columna `P10270`, códigos de 8 dígitos, prefijo "083" = comunicaciones frente a "07" = transporte — verificado contra los códigos impresos en el propio Cuadernillo 3). El medio de pago específico de telecomunicaciones seguiría sin poder separarse |
| `obligaciones_financieras` | **Existe, falta calcular** (probablemente muy ralo) | Cuadernillo 3, grupo K ("Gastos financieros y erogaciones monetarias"), subcapítulos K11 y K12. Monto en `gastos_menos_frecuentes_articulos.txt` (CAP = K11/K12); el medio de pago (P438K) no existe en la base publicada (gap ya documentado). En una muestra de 200.000 filas de `articulos.txt` solo aparecieron 8 registros con CAP=K11 y ninguno con K12 |
| `transferencias_p2p` | **Existe parcialmente, en otra forma** | Familia `P7510` (a, b) en `caracteristicas_generales_personas.csv`: incidencia ANUAL de recibir dinero de otros hogares/personas, no participación de transacciones. Ya señalado como "por verificar" en `docs/plan_maestro.md` P13 |
| `ingreso` | **Existe parcialmente, en otra forma** | `ICGU` (nivel de ingreso del hogar, ya usado en la calibración) y familia `P7510` (e-h) / `P7513` (incidencia anual de intereses, dividendos, rendimientos, ventas ocasionales). Ninguna da participación de transacciones de tipo ingreso sin transformarla primero |
| `retiro_efectivo` | **No existe en ENPH** | Es mecánica bancaria (retiro en cajero del efectivo acumulado en la capa interna del generador, D15), no una categoría de gasto en bienes o servicios |
| `movimiento_propio` | **No existe en ENPH** | Transferencia entre cuentas propias del mismo titular; mismo motivo que `retiro_efectivo` |

**Consecuencia:** esto no es una limitación de la tesis, es trabajo de cálculo pendiente. Se agregó a
`docs/plan_maestro.md` §8 como pendientes nuevos (ver PD19-PD20), no como limitación.

## Cálculos de soporte respaldo

Generados por `tools/calculos_diseno_muestral.py` (SEED = 42, sin aleatoriedad real en el
cálculo), en `outputs/diseno_muestral/`:

- `a_soporte_minimo_por_n.csv` — participación mínima requerida para soporte ≥ 10, para N ∈ {360, 450, 600}.
- `b_participacion_enph_por_categoria.csv` — prevalencia ENPH por categoría de la taxonomía v1 (proxy declarado; columna `estado` ∈ {calculado, existe_falta_calcular, no_existe_en_enph}).
- `b_soporte_insuficiente_por_categoria_y_n.csv` — cruce de las dos tablas anteriores (solo sobre las 8 categorías `calculado`).
- `c_kappa_ic95_ancho.csv` — ancho aproximado del IC 95 % de kappa de Cohen para n ∈ {100, 150, 200, 300} y acuerdo observado ∈ {0,80; 0,90}.
- `manifest_diseno_muestral.json` — semilla, parámetros y fuente de cada corrida.

**Supuesto de conversión (declarado, punto 3b del encargo anterior):** la participación en número de
transacciones **no es igual** a la participación en gasto de ENPH. No se aplica ningún supuesto de
conversión entre prevalencia de hogares (lo único disponible en `P438`, gastos menos frecuentes) y
participación de transacciones o de gasto: se usa la prevalencia de hogares tal cual, declarada
como proxy aproximado, no como una u otra magnitud.
