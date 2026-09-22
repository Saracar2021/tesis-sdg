# Justificación de parámetros de diseño

Desarrolla la lista de parámetros y decisiones sin justificación escrita identificada en la
bitácora (WP0, 22 sep 2026). Tipos:

- **convención:** valor fijado por una práctica metodológica o normativa estándar, no derivado de
  un cálculo propio del proyecto.
- **cálculo:** valor derivado de un cálculo reproducible, con código y salida en `outputs/`.
- **pendiente:** sin justificación todavía; queda abierto para que lo resuelva la autora.

> **Nota sobre las filas de tipo "convención":** su justificación depende de un insumo que no
> llegó a esta sesión (quedó como marcador `[pega el grupo A]` sin reemplazar en el encargo). No
> se completan con una base inventada; quedan marcadas `[PENDIENTE: falta "grupo A"]` hasta que se
> proporcione ese contenido.

## Tabla

| Archivo:línea | Parámetro | Justificación | Tipo |
|---|---|---|---|
| `CLAUDE.md:46-47`, `docs/protocolo_tecnico.md:137,147` | Umbral de celda rala ≈ 30 observaciones (`n_menor_30`) | [PENDIENTE: falta "grupo A"] | convención |
| `CLAUDE.md:191`, `docs/protocolo_tecnico.md:268,278-281` | Umbral de diferencia material = 1 p.p. entre meses | [PENDIENTE: falta "grupo A"] | convención |
| `CLAUDE.md:276`, `docs/protocolo_tecnico.md:186,356`, `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:24` | Semilla `SEED = 42` | [PENDIENTE: falta "grupo A"] | convención |
| `docs/protocolo_tecnico.md:184,331` | Meta de ≥ 5.000 transacciones sintéticas (dataset v1) | [PENDIENTE: falta "grupo A"] | convención |
| `docs/protocolo_tecnico.md:170,351` | Congelar taxonomía tras revisar ≥ 50 descripciones reales (unificado: ambas líneas decían cifras distintas, "≥ 50" y "~50"; ver punto 2 del encargo) | [PENDIENTE: falta "grupo A"] | convención |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:14` | 20 voluntarios | [PENDIENTE: falta "grupo A"] | convención |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:15,72` | 3 meses fijos (dic-2025, abr-2026, ago-2026) | [PENDIENTE: falta "grupo A"] (la razón de cada mes en particular sí está escrita en `docs/datos_reales/01_consentimiento_informado_v1.1.md` §1; falta la razón de que sean exactamente 3) | convención |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:74` | Borrado del extracto original a los 15 días | [PENDIENTE: falta "grupo A"]. **Ley 1581 de 2012:** no pude confirmar el artículo específico que fija o sugiere un plazo de conservación para este caso — déjalo como [VERIFICAR ARTÍCULO] hasta confirmarlo | convención |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:83` | Con 12–15 personas el conjunto "sigue siendo útil" | [PENDIENTE: falta "grupo A"] | convención |
| `docs/protocolo_tecnico.md:350`, `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:65` | 2 anotadores | [PENDIENTE: falta "grupo A"] | convención |
| `docs/protocolo_tecnico.md:210,332` | Regla de soporte ≥ 10 por clase para F1 macro | Con los tamaños de muestra considerados (N = 360, 450, 600), un soporte de 10 exige una participación mínima de 2,78 %, 2,22 % y 1,67 % respectivamente. Calculado en `tools/calculos_diseno_muestral.py` → `outputs/diseno_muestral/a_soporte_minimo_por_n.csv`. El cruce contra la participación observada en ENPH Bogotá (proxy declarado, ver `b_participacion_enph_por_categoria.csv`) muestra que ninguna de las 8 categorías de la taxonomía con dato ENPH cae por debajo del umbral en ningún N; el riesgo real de soporte insuficiente se concentra en las 8 categorías sin fuente ENPH (`b_soporte_insuficiente_por_categoria_y_n.csv`), que no se pueden evaluar así | cálculo |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:24` | 30 movimientos/persona, 10/mes → 600 movimientos | El valor N = 600 es uno de los tres tamaños evaluados en `tools/calculos_diseno_muestral.py` (junto con 360 y 450); con soporte ≥ 10 exige participación ≥ 1,67 %, cumplida por las 8 categorías con dato ENPH. La magnitud de 30/10 en sí (frente a otra combinación con el mismo total) no queda resuelta por este cálculo — solo el total N | cálculo |
| `docs/datos_reales/04_diseno_muestra_y_recoleccion_v1.1.md:26` | Mínimo de 200 movimientos de solapamiento para Kappa | Calculado en `tools/calculos_diseno_muestral.py` → `outputs/diseno_muestral/c_kappa_ic95_ancho.csv`: con n = 200, acuerdo esperado por azar pe ≈ 0,137 (8 categorías con dato ENPH) y acuerdo observado hipotético de 0,80 o 0,90, el ancho aproximado del IC 95 % de kappa es de 0,128 y 0,096 respectivamente (fórmula aproximada tipo Fleiss/Sim-Wright, declarada como aproximación no verificada contra la fuente primaria). Con n = 100 el ancho sube a 0,182 y 0,136; con n = 300 baja a 0,105 y 0,079 | cálculo |
| `CLAUDE.md:264-265` | Celdas de posición ocupacional × cotiza pensión: "no requieren acción" | PENDIENTE — queda para que lo resuelva la autora | pendiente |
| `docs/protocolo_tecnico.md:308` (L6) | No se cambió a cortes fijos para las fronteras de `INGLABO` | PENDIENTE — queda para que lo resuelva la autora | pendiente |
| `docs/protocolo_tecnico.md:203` | Tres clasificadores específicos (regresión logística TF-IDF, BETO, LLaMA 3 few-shot) | PENDIENTE — queda para que lo resuelva la autora | pendiente |

## Cálculos de soporte respaldo

Generados por `tools/calculos_diseno_muestral.py` (SEED = 42, sin aleatoriedad real en el
cálculo), en `outputs/diseno_muestral/`:

- `a_soporte_minimo_por_n.csv` — participación mínima requerida para soporte ≥ 10, para N ∈ {360, 450, 600}.
- `b_participacion_enph_por_categoria.csv` — prevalencia ENPH por categoría de la taxonomía v1 (proxy declarado; 8 de 16 categorías sin dato ENPH, declaradas explícitamente, no rellenadas).
- `b_soporte_insuficiente_por_categoria_y_n.csv` — cruce de las dos tablas anteriores.
- `c_kappa_ic95_ancho.csv` — ancho aproximado del IC 95 % de kappa de Cohen para n ∈ {100, 150, 200, 300} y acuerdo observado ∈ {0,80; 0,90}.
- `manifest_diseno_muestral.json` — semilla, parámetros y fuente de cada corrida.

**Supuesto de conversión (declarado, punto 3b del encargo):** la participación en número de
transacciones **no es igual** a la participación en gasto de ENPH. No se aplica ningún supuesto de
conversión entre prevalencia de hogares (lo único disponible en `P438`, gastos menos frecuentes) y
participación de transacciones o de gasto: se usa la prevalencia de hogares tal cual, declarada
como proxy aproximado, no como una u otra magnitud.
