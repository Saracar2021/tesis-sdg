# Bitácora

Registro fechado del trabajo técnico del proyecto, organizado por paquete de trabajo (WP).
Reemplaza la bitácora anterior, organizada por conversación de trabajo («chat»); la tabla de
equivalencias de abajo mapea esa numeración original a los WP para no perder trazabilidad con
commits y documentos anteriores que todavía la citan.

## Tabla de equivalencias (numeración original → paquete de trabajo)

| Numeración original | Paquete de trabajo | Nota |
|---|---|---|
| Chat 00 | WP0 — Entorno y seguimiento | Seguimiento transversal del proyecto y decisiones metodológicas; sus entradas de contenido técnico se listan también bajo el WP que corresponde (ver abajo) |
| Chat 01 | WP1 — Perfilado DANE **y** WP3 — Priors | Se reparte: cargador único, verificación de `FEX_C`/códigos y la investigación de julio/marzo son WP1; las distribuciones para priors y el análisis de fronteras de amontonamiento son WP3 (detalle en el registro de abajo) |
| Chat 01B | WP5 — Pipeline de referencia | Reevaluación del pipeline de Pancholi et al. |
| Chat 02 | WP4 — Datos reales | Consentimiento, anonimización, diseño de muestra |
| Chat 03 | WP2 — Taxonomía | |
| Chat 04 | WP4 — Datos reales | Según los commits reales (`1dde8ee`, `dfede1c`): paquete de datos reales v1.1 y correcciones transversales (estrato ENPH, taxonomía T2–T4, cuantiles, DP1). `docs/plan_maestro.md` lo había planeado como «documento técnico del protocolo» (esa actividad se registra aquí como WP0); ese documento no se redactó bajo esta etiqueta |
| Chat 05 | WP3 — Priors **y** WP6 — Generador | Se reparte: umbral de soporte y encogimiento jerárquico son WP3; la reponderación de los priors por bancarización es un entregable de WP3 hecho para satisfacer la decisión D15 de WP6 (detalle abajo) |
| Chat 06 | WP6 — Generador | |
| Chat 07 | WP7 — CTGAN | Aún no iniciado |
| Chat 08 | WP8 — Evaluación TSTR | Aún no iniciado |
| Chat 09 | *(sin WP técnico)* | Redacción de la tesis y comunicación con la directora; fuera del alcance de WP0–WP8 |
| Chat 10 | *(sin WP técnico)* | Comunicación con la directora |

---

## Registro de trabajo

### 2026-09-20 — WP1: cargador único y verificaciones de fuentes DANE
- `src/sdg/carga.py` (+ `pesos.py`, `codigos.py`, `medio_pago.py`): cargador GEIH/ENPH con validación de filas contra `outputs/fuentes_datos.json`, `FEX_C18/len(meses)`, dominio Bogotá, rural bloqueado, uniones que reportan % enlazado y `estrato_agrupado()`.
- `FEX_C` de ENPH verificado (Metodología §2.2.4.1 + constante por `DIRECTORIO` e igual al de `viviendas_hogares` en 10 tablas; rural no cubierto). Códigos verificados contra su fuente: estrato ENPH (Manual, 0 = pirata, 9 = no establecible), estrato GEIH (dicc. fila 32), `P438*` (Cuadernillo 3: 4 = bonos, 5 = cheques; 29 columnas = subcapítulo = categoría × periodo) y `NC2R_CC_P6` (Cuadernillo 2 urbano: 4 = fiado, 5 = bonos). `P6450`: 9 = No sabe.
- Cómo se verificó: 29 pruebas automatizadas en `tests/` (`python -m unittest discover -s tests`), en verde.
- Cierre de este bloque de trabajo: `CLAUDE.md` v4, `requirements.txt` con versiones fijas. Pendientes dejados abiertos en ese momento: umbral de soporte y método de encogimiento (WP3); definición oficial DANE de formalidad, solo si hace falta una sola variable; fijar `torch`, `ctgan` y `jupyter` en `requirements.txt` cuando se instalen.
- Archivo / commit: `src/sdg/`, `tests/`; commits hasta `2aebb9e` (ver `docs/plan_maestro.md` §3).

### 2026-09-20 — WP3: distribuciones para priors
- `tools/distribuciones_priors.py` → `outputs/distribuciones/` (16 tablas + informe + manifest): Bogotá urbano con FEX. Vacíos de `P438*` cruzados con artículos: con `FORMA=1` como compra la no respuesta es 0 en los 29 subcapítulos (todo vacío es «no aplica»); con «cualquier registro» aparece no respuesta solo en hogares con registros no comprados. Gaps abiertos: no existen `P438J14` ni `P438K11`; `P438J13` sin verificar contra el cuadernillo.
- Fronteras de grupos de ingreso: el amontonamiento en valores redondos afecta a `INGLABO` (hasta ~6 % del peso en un valor) y no a `ICGU` (< 0,1 %). Declarado como limitación; sin cortes fijos. Sensibilidades (> 1 p.p.): sin diciembre, sin julio y sin marzo, todas en `outputs/distribuciones/`.
- Celdas de posición ocupacional × cotiza pensión: declaradas como pequeñas e inestables en `distribuciones_priors.md`. No requieren acción adicional en este bloque.
- Cómo se verificó: cifras regeneradas por `tools/distribuciones_priors.py`, sin aleatoriedad; manifest en `outputs/distribuciones/manifest_distribuciones.json`.
- Archivo / commit: `outputs/distribuciones/`; commits hasta `2aebb9e`.

### 2026-09-20 — WP1: investigación de julio y marzo, decisión sobre los 12 meses
- Julio 2025 (GEIH `datos_hogar`, estrato) sin explicar: `tools/investigar_julio.py`, `outputs/julio/julio_estrato.md`. No es «sin dato»; es un desplazamiento 3 → 1-2; se repite, más fuerte, en las 23 ciudades y atenuado a nivel nacional; otras variables del módulo no se mueven. Registrado como evidencia para pedir al DANE el control de cambios 2501-2512 (evidencia para consultar, no prueba de cambio de instrumento). Hallazgo colateral: en `ocupados` de Bogotá el mes más extremo es marzo.
- Decisión (cerrada): se usan los 12 meses. Razón: estrato agrupado (máx. 0,73 p.p. sin julio; 0,31 sin marzo) y formalidad (0,29 y 0,52 p.p.) quedan bajo el umbral de 1 p.p. en ambas versiones; las familias de ENPH (quintil de `ICGU`, forma de pago) no dependen de los meses de GEIH; lo único que supera 1 p.p. es `INGLABO` (grupos G1/G2 sin julio), con causa identificada (el corte pasa de 1.300.000 a 1.200.000 por el amontonamiento ya declarado, efecto de frontera y no de composición).
- Marzo y julio quedan como anomalías declaradas en la tesis, con sus sensibilidades en `outputs/distribuciones/` como respaldo. No se investigan más las causas sin el control de cambios del DANE (2501-2512).
- Cómo se verificó: `outputs/julio/julio_estrato.md`, `geih_sensibilidad_{julio,marzo,diciembre}.csv`.
- Archivo / commit: `tools/investigar_julio.py`, `outputs/julio/`; `CLAUDE.md` (regla de fuentes: ENPH aporta ingreso y gasto, GEIH estructura demográfica y laboral; `INGLABO` solo descriptivo).

### 2026-09-20 — WP4: paquete de datos reales v1.1 y rótulo «Fiado»
- Paquete de consentimiento, anonimización, guía de anotación y diseño de muestra llevado a v1.1 en `docs/datos_reales/`.
- `NC2R_CC_P6` código 4: el Cuadernillo 2 urbano es la fuente autoritativa del instrumento y dice «Fiado» (no «Fiador», como rotula el DDI). Adoptado como rótulo en `sdg.codigos.FORMA_PAGO_NC2R_FUENTE` y en los documentos originales de `outputs/`.
- Cómo se verificó: contraste directo del Cuadernillo 2 urbano contra el DDI; commit `1dde8ee`.
- Archivo / commit: `docs/datos_reales/`; commit `1dde8ee`.

### 2026-09-20 — WP1/WP2/WP3: correcciones de cuantiles, estrato ENPH y taxonomía T2–T4
- Cuantiles unificados: `docs/fuentes_datos.md` y `outputs/distribuciones/` usaban poblaciones distintas para calcular los cortes de quintil; ambos scripts pasaron a usar la misma función (`sdg.pesos.cortes_ponderados`) sobre todos los hogares de Bogotá con `ICGU`.
- Estrato ENPH verificado contra el Manual ENPH, pregunta 4 (no era «supuesto no verificado» como decía una versión anterior de `docs/fuentes_datos.md`).
- Taxonomía `docs/taxonomia/pendientes_v1.1.md`: T2 y T4 verificados; T3 desbloqueado.
- Resumen de efectivo (`enph_p438_resumen_efectivo.csv`) y decisión DP1 (predecesora de D15) documentados.
- Cómo se verificó: recontraste de fuente primaria (Manual ENPH, Cuadernillo 3) y regeneración de `docs/fuentes_datos.md`.
- Archivo / commit: `docs/fuentes_datos.md`, `docs/taxonomia/`; commit `dfede1c`.

### 2026-09-22 — WP5: regla de evidencia sobre el pipeline de Pancholi
- El pipeline de Pancholi no se ha ejecutado; ninguna de sus salidas (USD 12 entre perfiles, 5 perfiles, 149 tx, categorías de ocio, 100 % `credit_card`) es un resultado. Pasan a ser hipótesis H-P1 a H-P3, a contrastar en WP5.
- Se puede citar el diseño documentado en el paper (ACS 2015-2019 de D.C., Yelp y comercios de D.C., reglas calibradas por ingreso, CTGAN; Tabla 5 como ejemplo, no proporción).
- Documentos corregidos: `CLAUDE.md`, `docs/protocolo_tecnico.md` (D6 y §1.4), `docs/taxonomia/taxonomia_gastos_colombia_v1.md` §7, `docs/taxonomia/pendientes_v1.1.md` (T5), `docs/plan_maestro.md`. Sin tocar: informe de avance y presentación (documentos de la autora, fuera del repositorio de código).
- Cómo se verificó: relectura del paper de Pancholi et al. contra cada afirmación retirada.
- Archivo / commit: commit `173c992`.

### 2026-09-22 — WP6 (decisión) / WP3 (implementación): D15 — universo del generador = hogares bancarizados
- Decisión (cerrada): el generador emite extractos sintéticos (capa interna de gasto del hogar calibrada con ENPH + capa de emisión bancarizada); reemplaza la decisión abierta DP1. Registrada en `CLAUDE.md` v5 y `docs/protocolo_tecnico.md` §5 (D15), con supuestos declarados (cadencia/monto de retiros, medios digitales vía Banrep 2024, cuenta principal del voluntario) y reformulación de la limitación 3 de Pancholi (H-P3).
- Consecuencia para los priors (WP3, ejecutada para satisfacer la decisión D15 de WP6): la población que calibra el generador es la de hogares bancarizados. `tools/distribuciones_priors.py` (+ `sdg.codigos.PRODUCTOS_FINANCIEROS_P5222`, filas 93-104 del Diccionario GEIH 2025) calcula tenencia de `P5222S*` en Bogotá (12 meses): 93,47 % de los hogares tiene al menos un producto; sin ninguno: 9,37 % (estrato bajo), 4,54 % (medio), 0,27 % (alto).
- El perfil `enph_estrato_x_quintil.csv` se repondera por `P(bancarizado | estrato agrupado)` de GEIH → `enph_estrato_x_quintil_bancarizado.csv`, bajo un supuesto de independencia condicional declarado (no verificable: ENPH no tiene `P5222S*`, GEIH no tiene `ICGU`). Limitación L16 en `protocolo_tecnico.md`.
- Salidas nuevas en `outputs/distribuciones/`: `geih_bancarizacion_total.csv`, `geih_bancarizacion_x_estrato.csv`, `enph_estrato_x_quintil_bancarizado.csv` (20 tablas en total, script re-ejecutado de punta a punta).
- Pendientes abiertos por esta decisión (WP6): cadencia/tamaño de retiros (PD8), cifras concretas de medios digitales de Banrep (PD7).
- Cómo se verificó: `tools/distribuciones_priors.py` re-ejecutado de punta a punta; conteos contra el Diccionario GEIH 2025.
- Archivo / commit: `outputs/distribuciones/`, `CLAUDE.md`, `docs/protocolo_tecnico.md`; commit `89a65c0`.

### 2026-09-22 — WP5/WP6: sensibilidad al ingreso y corrección de D15 (H-P1)
- H-P1 reformulada: el paper de Pancholi sí calibra el gasto por ingreso (con el ACS 2015-2019 de D.C.); la hipótesis es que esa calibración no reproduce la relación ingreso–gasto colombiana. «Insensibilidad al ingreso» se retira de todos los documentos.
- Los 5 quintiles se justifican por la hipótesis de la tesis (proporciones de gasto por quintil observadas en Colombia), no por una falla de Pancholi. Corregidos `CLAUDE.md` y `docs/protocolo_tecnico.md` (D6 y §1.4).
- Corregida la redacción de D15: una versión anterior afirmaba que el paper «lista como limitación que no genera efectivo» y que el pipeline «asume que todo pasa por tarjeta de crédito». Ninguna de las dos está en el paper ni sale de una ejecución; queda como hipótesis H-P3.
- Informe de avance y presentación: versiones `_v1.1_revision` en la carpeta de OneDrive, con control de cambios en el informe; los originales no se tocaron.
- Cómo se verificó: relectura del paper y de los documentos citados, frase por frase.
- Archivo / commit: `CLAUDE.md`, `docs/protocolo_tecnico.md`.

### 2026-09-22 — WP5/WP6: verificación y commit de la corrección de H-P1/H-P3 y D15
- Verificada en disco la corrección anterior: «insensibilidad al ingreso» y las frases no respaldadas sobre Pancholi («no genera efectivo», «asume tarjeta de crédito») solo quedan como referencias meta a la retractación, no como afirmaciones.
- Corregida una inconsistencia encontrada: `docs/plan_maestro.md` había vuelto a rotular la decisión como «DP1» (fila de la tabla de decisiones y estado de R10); ahora dice «D15» en ambos, consistente con `CLAUDE.md` y `protocolo_tecnico.md`.
- Cómo se verificó: 29 tests en verde (`python -m unittest discover -s tests`); sin cambios de código en esta corrección, solo documentación.
- Archivo / commit: `docs/plan_maestro.md`; commit `df4f526`.

### 2026-09-22 — WP0: preparación del repositorio para revisión externa
- Reescritura de voz en todos los documentos versionados: narración en tercera persona sobre decisiones ("Sara decidió/confirmó") reemplazada por voz impersonal o primera persona según el documento; identificadores de chat reemplazados por los WP de esta tabla.
- Excluido de la reescritura de voz: `docs/historico/`, por su propia regla de solo lectura (`CLAUDE.md`).
- `docs/estrategia_claude_escritorio_tesis.md` y `docs/guia_setup_paso_a_paso.md` movidos a `notas_locales/` (fuera de seguimiento de git).
- `docs/datos_reales/01_consentimiento_informado_v1.1.md`: la nota interna «para Sara» se extrajo a `docs/datos_reales/pendientes_antes_de_circular.md` como checklist.
- README.md nuevo en la raíz con objetivo, hipótesis, estado, estructura y reproducción.
- Cómo se verificó: `python -m unittest discover -s tests` en verde; `git diff` de los dos generadores (`tools/generar_fuentes_datos.py`, `tools/distribuciones_priors.py`) limitado a cadenas de texto, sin cifras; comparación de AST (sin docstrings) idéntica en `src/sdg/*.py`, `tools/normalizar_datos.py` y `tools/investigar_julio.py`.
- Archivo / commit: commit `a349c0c` (autoría corregida sobre el commit original de esta preparación).

### 2026-09-22 — WP0: recupera evidencia perdida en la reescritura de la bitácora
- Al comparar `docs/bitacora.md` reescrita contra `git show HEAD~1:docs/bitacora.md` se encontraron 4 datos concretos perdidos: el cierre "CLAUDE.md v4 / `requirements.txt`" y sus pendientes (torch/ctgan/jupyter, umbral de soporte, definición DANE de formalidad); la nota de celdas de posición ocupacional × cotiza pensión; los grupos G1/G2 afectados por el corte de `INGLABO` en julio; y la ubicación (carpeta de OneDrive) de las revisiones del informe de avance.
- Cómo se verificó: `diff` línea por línea contra la versión anterior; 29 tests en verde; sin cambios de cifras.
- Archivo / commit: `docs/bitacora.md`; commit `f75aea4`.

### 2026-09-22 — WP4: justificación de parámetros de diseño
- `docs/justificacion_parametros.md`: tabla de los parámetros y decisiones sin justificación escrita identificados el 22 sep (archivo:línea, parámetro, justificación, tipo convención/cálculo/pendiente).
- Unificado `docs/protocolo_tecnico.md:170` y `:351`: ambos decían "≥ 50 descripciones reales" y "~50 descripciones reales"; queda "≥ 50" en los dos.
- `tools/calculos_diseno_muestral.py` (SEED = 42) → `outputs/diseno_muestral/`: (a) participación mínima por categoría para soporte ≥ 10 con N ∈ {360, 450, 600}; (b) cruce con la prevalencia ENPH por categoría de la taxonomía v1 (proxy declarado: prevalencia de hogares con compra en P438, no participación de transacciones ni de gasto; 8 de 16 categorías sin calcular en este cálculo); (c) ancho aproximado del IC 95 % de kappa de Cohen para n ∈ {100, 150, 200, 300} y acuerdo observado ∈ {0,80; 0,90}, con pe calculado sobre las 8 categorías ya calculadas.
- Pendiente crítico sin resolver en esta entrada: las filas de tipo "convención" de `justificacion_parametros.md` (umbral n≈30, umbral 1 p.p., `SEED=42`, ≥5.000 transacciones, ≥50 descripciones, 20 voluntarios, 3 meses, 15 días de borrado, 12-15 personas, 2 anotadores) quedaron marcadas `[PENDIENTE: falta "grupo A"]`: el encargo original citaba una base a pegar («grupo A») que no llegó a esta sesión. La cita de la Ley 1581 de 2012 para el borrado a 15 días también queda como `[VERIFICAR ARTÍCULO]`.
- Marcados PENDIENTE (a resolver por la autora, no por falta de insumo): posición ocupacional × cotiza pensión, L6 (cortes fijos de `INGLABO`), elección de los tres clasificadores.
- Cómo se verificó: `python -m unittest discover -s tests` en verde (29); `tools/calculos_diseno_muestral.py` ejecutado de punta a punta, sin aleatoriedad real pese a `SEED=42`.
- Archivo / commit: `docs/justificacion_parametros.md`, `tools/calculos_diseno_muestral.py`, `outputs/diseno_muestral/`, `docs/protocolo_tecnico.md`; commit `ae10cc3`.

### 2026-09-22 — WP1/WP3: verificación de las 8 categorías sin calcular, y justificación de las convenciones
- **Corrección de un error de la entrada anterior.** "8 de 16 categorías sin fuente ENPH" era impreciso: se verificó contra los METADATOS de ENPH (cuadernillos y DDI en `data/raw/ENPH_2017/_metadatos/`, no los microdatos), no si el cálculo ya existía. Resultado: 6 de las 8 **sí existen en ENPH y solo faltan por calcular** (`alimentos_mercado`: Cuadernillo 2 Capítulo C; `comidas_fuera`: Cuadernillo 2 D1; `telecom_conectividad`: Cuadernillo 3 H11/H12, mezclado con transporte en el medio de pago pero separable por monto vía el prefijo COICOP "083" en la columna `P10270` de `gastos_menos_frecuentes_articulos.txt`; `obligaciones_financieras`: Cuadernillo 3 grupo K, `CAP`=K11/K12 en el mismo archivo [cifra de rareza retirada de aquí el 22 sep: ver la entrada de corrección más abajo]; `transferencias_p2p` e `ingreso`: familia `P7510`/`P7513`, incidencia anual, no participación de transacciones). Solo `retiro_efectivo` y `movimiento_propio` no tienen fuente ENPH en absoluto (son mecánica bancaria, no gasto en bienes o servicios).
- `tools/calculos_diseno_muestral.py` y `docs/justificacion_parametros.md` corregidos: la columna/estado ahora distingue `calculado` / `existe_falta_calcular` / `no_existe_en_enph`, con la fuente y el módulo/variable citados para cada una de las 6 que faltan.
- `docs/plan_maestro.md` §8: agregados P19 (calcular las 6 categorías, WP1/WP3) y P20 (decidir fuente para `retiro_efectivo`/`movimiento_propio`, WP6) — **como pendientes de trabajo, no como limitación de la tesis**. También unificado `~50` → `≥ 50` en P10 (mismo criterio que protocolo_tecnico.md).
- **Justificación de las 10 filas de tipo "convención"** en `docs/justificacion_parametros.md`, con la base que se entregó explícitamente (sin agregar fundamentos fuera de ella): `SEED=42` (arbitrario, exige solo que sea fija y declarada), 2 anotadores (kappa de Cohen definido para dos evaluadores; Fleiss mediría otra cosa), borrado a 15 días (Ley 1581 art. 4 lit. b, principio de finalidad; plazo operativo, no legal — NO se usa un "principio de temporalidad", que es de la Ley 1266 de 2008), 3 meses fijos (tres observaciones distinguen un mes atípico de dos de referencia; el tope lo impone la carga del voluntario), 20 voluntarios (muestra por conveniencia, declarada como limitación, no representa a la población), y el criterio operativo de "≥50" descripciones. Las 4 filas de convención que la base no cubría (umbral n≈30, umbral 1 p.p., ≥5.000 transacciones, 12-15 personas) se reclasificaron como tipo `pendiente`.
- Cita verificada por búsqueda web (no solo por memoria): Cohen, J. (1960), "A Coefficient of Agreement for Nominal Scales", *Educational and Psychological Measurement*, 20(1), 37-46, DOI 10.1177/001316446002000104. Ley 1581 de 2012 art. 4 lit. b y art. 8 lit. e verificados contra el texto de la ley (el lit. e condiciona la revocación/supresión a un incumplimiento de principios o derechos, no la formula como derecho incondicional "en cualquier momento"; se declaró así en vez de repetir la simplificación).
- Cómo se verificó: lectura de los cuadernillos ENPH y del DDI con `pdftotext`; inspección de `gastos_menos_frecuentes_articulos.txt` (columnas `CAP`, `P10270`); búsqueda web para Cohen (1960) y los artículos de la Ley 1581; `python -m unittest discover -s tests` en verde (29).
- Archivo / commit: `docs/justificacion_parametros.md`, `tools/calculos_diseno_muestral.py`, `outputs/diseno_muestral/`, `docs/plan_maestro.md`; commit `aef7b9d`.

### 2026-09-22 — WP3: limitación del medio de pago en ENPH y correcciones de trazabilidad
- **Corrección 1 — cifra sin FEX retirada.** "8 registros de K11 en una muestra de 200.000 filas" (entrada anterior) venía de una lectura ad hoc por Bash, con `nrows=200000` (no el archivo completo) y sin `FEX_C`, fuera de `src/sdg/carga.py`. Se retiró de los cuatro lugares donde había quedado escrita: `docs/justificacion_parametros.md`, esta bitácora (entrada anterior), `tools/calculos_diseno_muestral.py` (comentario) y `outputs/diseno_muestral/manifest_diseno_muestral.json`. El archivo completo tiene 11.009 filas brutas con `CAP=K11` (no 8): la lectura truncada cortó antes de donde empiezan a aparecer. Se escribió `rareza_subcapitulo_k_financiero()` en `tools/calculos_diseno_muestral.py` (agregación a hogar, `FEX_C`, dominio Bogotá, archivo completo) — **no se invoca desde `main()` ni se ejecutó**: queda para que la autora la corra (PD20, `docs/protocolo_tecnico.md`).
- **Corrección 2 — colisión de nombre GEIH/ENPH.** `P7510`/`P7513` existen como variables en **ambas** encuestas, con sub-ítems y periodo de referencia distintos: en ENPH viven en `personas/caracteristicas_generales_personas.csv` (confirmado en el DDI y en el encabezado real del archivo); en GEIH, en `otros_ingresos.csv` (confirmado en el encabezado de `data/raw/GEIH_2025/01_enero/otros_ingresos.csv` y en su DDI). Se agregó una nota general en `CLAUDE.md` ("Códigos de variable compartidos entre encuestas") y se aclaró la encuesta y el archivo en cada mención de `P7510`/`P7513` (`docs/plan_maestro.md` P13, P19; `docs/justificacion_parametros.md`; `tools/calculos_diseno_muestral.py`).
- **Corrección 3 — L17 nueva: medio de pago por subcapítulo, no por artículo.** Verificado contra el texto impreso del Cuadernillo 3: la pregunta "(6) El medio de pago usado principalmente para comprar los artículos y servicios enunciados en este subcapítulo fue" es una sola respuesta por subcapítulo, no por artículo. Cuando el subcapítulo mezcla categorías de la taxonomía, el medio de pago de cada categoría por separado no es observable en ENPH bajo ningún cálculo — es un límite del cuestionario. Confirmado contra el título impreso para 5 subcapítulos: H11 y H12 (transporte + telecom_conectividad), E11 (educación + transporte), I12 (transporte + obligaciones_financieras), J11 (entretenimiento + comidas_fuera). Un intento de detectar el resto por prefijo COICOP de `P10270` (`mezcla_categorias_p438()`, corrido y guardado en `outputs/diseno_muestral/e_mezcla_categorias_p438_preliminar.csv`) **no es confiable**: el subcapítulo E12 (título 100 % educación) clasifica por código como 43 % "entretenimiento", lo que prueba que el mapeo de 2 dígitos de COICOP falla para las divisiones 02, 09 y 12 — se guardó marcado como preliminar, no como hallazgo, con PD19 para revisarlo a mano contra el cuadernillo. Agregada como L17 en `docs/protocolo_tecnico.md`, con referencias cruzadas en el detalle de D15 (medio de pago no observable para las categorías mezcladas) y en la formulación de H-P3 (la comparación por medio de pago solo se sostiene para las categorías sin mezcla).
- **Verificación del punto 4 del encargo (97,0 % de efectivo):** revisadas todas las menciones en el repo (`docs/fuentes_datos.md`, `docs/plan_maestro.md`, `docs/protocolo_tecnico.md`, `docs/taxonomia/pendientes_v1.1.md`, `CLAUDE.md`, `outputs/distribuciones/`); en ninguna dice "los hogares pagan en efectivo" sin aclarar que es la forma de pago principal declarada (`NC2R_CC_P6`, Cuadernillo 2, una respuesta por hogar). No se pudo revisar el informe de avance ni la presentación (fuera del repositorio, en OneDrive) — pendiente de que la autora los revise por la misma razón.
- Cómo se verificó: encabezados reales de `caracteristicas_generales_personas.csv` (ENPH) y `otros_ingresos.csv` (GEIH, enero 2025); DDI de ambas encuestas; conteo completo (sin `nrows`) de `gastos_menos_frecuentes_articulos.txt`; lectura de texto impreso del Cuadernillo 3 con `pdftotext`; `python -m unittest discover -s tests` en verde (29); `tools/calculos_diseno_muestral.py` ejecutado de punta a punta (sin la función de rareza K, que queda para la autora).
- Archivo / commit: `CLAUDE.md`, `docs/plan_maestro.md`, `docs/justificacion_parametros.md`, `docs/protocolo_tecnico.md`, `tools/calculos_diseno_muestral.py`, `outputs/diseno_muestral/`; commit `b69dd01`.

### 2026-09-22 — WP1: `obligaciones_financieras` no es ralo; K12 no tiene datos por razón estructural
- **Resultado de `rareza_subcapitulo_k_financiero()`** (ejecutada por la autora, confirmada y ahora escrita en un CSV): `K11` aparece en **574 de 3.918 hogares** de la muestra de Bogotá — **13,80 % de los hogares expandidos** (352.583 de 2.555.731 con `FEX_C`); a nivel nacional, 8,39 % (1.203.392 de 14.349.250 hogares expandidos, 7.429 de 87.193 hogares en la muestra). **Reemplaza la sospecha anterior de que era una celda rala: no lo es.** `obligaciones_financieras` se mantiene en la taxonomía con prioridad alta.
- **Por qué K12 da 0 (Bogotá y nacional, verificado):** no es baja prevalencia. El Cuadernillo 3 sí imprime "3.K12. SERVICIOS FINANCIEROS", pero su pregunta es un filtro Sí/No sobre si el hogar pagó cuota de un préstamo para gastos del hogar (excluye vivienda), seguido de las características del préstamo (entidad, tipo, tasa, plazo) — no una lista de artículos con código y valor como el resto de subcapítulos. Esa estructura no puede generar filas en `gastos_menos_frecuentes_articulos.txt` (que solo tiene registros artículo+valor con código `P10270`), sin importar cuántos hogares respondan que sí. Se buscó en el DDI de ENPH una variable cuya etiqueta coincidiera con esa pregunta y no se encontró: **no se determinó si la respuesta a K12 se publicó en otro archivo o si no se publicó en absoluto** — queda declarado como pendiente sin resolver, no como un supuesto.
- `rareza_subcapitulo_k_financiero()` ahora calcula Bogotá y Nacional en una sola corrida y escribe `outputs/diseno_muestral/f_rareza_obligaciones_financieras.csv`. `docs/justificacion_parametros.md` y `docs/protocolo_tecnico.md` (PD20, marcado resuelto) actualizados con el resultado.
- Cómo se verificó: `tools/calculos_diseno_muestral.py` ejecutado (`rareza_subcapitulo_k_financiero()`), agregado a hogar con `sdg.carga.cargar_enph`, `FEX_C`, dominio Bogotá y "todo" (nacional); cifras confirmadas contra lo reportado por la autora; `python -m unittest discover -s tests` en verde (29).
- Archivo / commit: `tools/calculos_diseno_muestral.py`, `outputs/diseno_muestral/f_rareza_obligaciones_financieras.csv`, `docs/justificacion_parametros.md`, `docs/protocolo_tecnico.md`; commit en este mismo cierre.
