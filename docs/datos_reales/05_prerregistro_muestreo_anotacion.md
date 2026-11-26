# Pre-registro — muestreo y anotación del conjunto real de test (WP4 → WP8)

**Estado:** CERRADO **v1.3** — 2026-11-26 (v1.0 y v1.1 del 25 nov; v1.2 y v1.3 del 26 nov). Las decisiones de
diseño (D-M1 a D-M7) se aprobaron **antes de muestrear**; las enmiendas v1.1 a v1.3 se aprobaron **antes de cualquier
anotación**.
Al cerrar este documento **no existe ninguna etiqueta**.
**Taxonomía:** v1.1.0 congelada (`docs/taxonomia/taxonomia_gastos_colombia_v1.json`, `metadata.version = 1.1.0`).
**Insumo:** `data/reales_anon/V04.csv … V10.csv`, **v3** del 25 nov (2.471 filas; SHA-256 de cada archivo en
`data/reales_anon/anotacion/_resumen_muestreo.md`). Nada de `data/` va a git.
**Script:** `tools/muestreo_wp4.py`, SHA-256 `42d205e319e0ea4e95f610ff4c08a7f3bac3a21f3d61be61835ae41a143db4da` (v1.1;
la v1.0 era `117f9d3c…511e`: el plan B y el orden de A2 no cambian ni el marco, ni la muestra, ni `lote_A1`).

> El diseño solo usa variables observables (descripción, monto, signo, cuenta_tipo, mes, grupo). El real **solo
> evalúa** (D14): ni la muestra, ni la heurística de estratificación, ni las etiquetas alimentan el generador o las
> plantillas de texto.

## 1. Marco muestral

| Paso | Filas | Motivo |
|---|---|---|
| Conjunto anonimizado v3 | 2.471 | — |
| − octubre 2026 | −213 | V04 13, V05 23, V06 32, V09 112, V10 33. Ver la razón del corte abajo. |
| − noviembre 2026 | −75 | V08 1 (su única fila), V09 28, V10 46. |
| **Marco** | **2.183** | 2025-12 a 2026-09 · **6 grupos de extractos** (V04, V05, V06, V07, V09, V10) |

**Razón del corte en septiembre de 2026 (enmienda v1.2, redacción definitiva).** WP8 deflacta cada monto real a pesos
de promedio 2025 con el IPC del mes de la transacción (`etapa4_tstr.py`, `deflactar_test_a_2025`) y se detiene si
falta un mes. **Septiembre de 2026 es el último mes de la serie de IPC incorporada al repositorio
(`outputs/ipc/ipc_total_nacional.csv`) al congelar el marco; el IPC de octubre (publicado por el DANE el 9 nov 2026,
[boletín técnico](https://www.dane.gov.co/files/operaciones/IPC/oct2026/bol-IPC-oct2026.pdf)) no se incorporó por
calendario.** Octubre no entra (213 filas). Noviembre tampoco (75 filas): su IPC no está publicado antes de la entrega.

- **Sin pérdidas de extracción que declarar** (D-M3 obsoleta): la v3 reconstruye las 52 filas "`de 1`" e
  incorpora 37 pagos, reversiones y devoluciones de tarjeta. El script se detiene si encuentra descripciones
  residuales (`de N` o un monto como descripción); en la v3 hay 0.
- Se conservan las **60 filas con monto 0** del marco (intereses de ahorro < $1). `bin_monto` de WP8 las asigna a
  `<1K` (verificado en el código). Por el tope por descriptor, ninguna quedó en la muestra.
- Las tarjetas ya no son 100 % egreso: el marco trae pagos, reversiones y devoluciones con `signo = ingreso`.

## 2. Estratificación

- **Estrato `estrato_muestreo`:** preclasificación heurística por palabras clave en 16 categorías + `reverso_devolucion`
  (pagos anulados y devoluciones de tarjeta, que la taxonomía no nombra) + `sin_heuristica` (26,5 % del marco).
  Es una **herramienta de muestreo, no una etiqueta**: los anotadores no la ven y no entra en ninguna métrica salvo
  como estrato del bootstrap.
- Palabras clave genéricas (verbos bancarios, cadenas y marcas nacionales), sin comercios pequeños ni empleadores
  del real. Congeladas con el script (SHA arriba).
- Sorteo: claves SHA-256(`42:etapa:tx_id`); tomar las n claves menores equivale a un muestreo aleatorio simple y es
  idéntico en cualquier máquina y versión de numpy. `--verificar` recalcula y compara los SHA-256 de las salidas.

## 3. Tamaño, asignación y tope por descriptor

- **n = 200** (D-M1), mínimo **m = 10** por estrato (o todo lo muestreable), resto proporcional a N_h.
- **Tope k = 3** filas por descriptor normalizado (mayúsculas, sin dígitos ni `#`) dentro de cada estrato.
- **Dos etapas con probabilidad exacta:** (1) por descriptor se retienen `min(3, N_d)` filas, `π1 = min(1, 3/N_d)`;
  (2) muestreo aleatorio simple de `n_h` filas entre las `R_h` retenidas, `π2 = n_h/R_h`.
  **`peso_muestreo = 1/(π1·π2)`**, guardado en `muestra_test_clave.csv`, nunca en los lotes.
- Resultado: 200 filas, **153 descriptores distintos**, Σ pesos = 2.238 (esperado ≈ 2.183).

### Corrección del tamaño efectivo (declarada)

El borrador estimaba un n efectivo (Kish) de ≈ 136. **Esa cifra era un error de cálculo**: consideraba solo los pesos
por estrato y omitía el tope por descriptor. Con las probabilidades exactas, **n efectivo = 48**: por ejemplo, 3 filas
de un descriptor que aparece 235 veces pesan ≈ 119 cada una, y los 10 ítems más pesados llevan el 36 % del peso.

| Tope k | n efectivo (Kish) | Descriptores distintos en la muestra | Máx. filas de un mismo descriptor |
|---|---|---|---|
| **3 (diseño)** | **48** | **153** | 3 |
| 5 | 55 | 142 | 4 |
| 10 | 66 | 129 | 5 |
| sin tope | 123 | 113 | 12 |

**Se mantiene k = 3.** El n efectivo de Kish supone ítems heterogéneos, y los ítems pesados son copias del mismo
texto. Por D-M5 la etiqueta se decide con lo que ve el clasificador, así que filas con la misma descripción tienen
(salvo por el monto) la misma etiqueta de referencia y la misma predicción. Por eso 48 es una **cota inferior
conservadora** de la información para la exactitud ponderada, no su valor real. A cambio, el test cubre 40
descriptores más que sin tope, que es lo que importa para la F1-macro. Consecuencia práctica: el IC de la exactitud
ponderada saldrá ancho; se reporta así.

## 4. Reporte: métricas pre-registradas (enmienda v1.1)

1. **Métrica principal:** **F1-macro sobre los 200 ítems, sin ponderar**, con la regla de soporte ≥ 10 de WP8 e IC95
   por bootstrap por fila estratificado (D-M7). La muestra está diseñada para **cobertura de clases**, no para
   representar la distribución real; se declara así.
2. **Secundaria:** **exactitud ponderada** con `peso_muestreo` (estimador de Hájek), con su IC95 por el mismo bootstrap,
   junto a la exactitud sin ponderar. Se declara que su **n efectivo es 48** (§3).
   **Sensibilidad a los ítems pesados:** los 10 ítems más pesados llevan el 36 % del peso total. Se reporta además la
   exactitud ponderada con los pesos **recortados al percentil 95** (P95 = 41,0) y renormalizados. Si las dos difieren
   en más de 5 puntos, el resultado de la exactitud ponderada se declara dependiente de pocos descriptores.
3. **Sensibilidad de la F1-macro: una fila por descripción.** F1-macro sobre las **153 descripciones únicas**
   (una fila por `descriptor_norm`; si hay varias, la de menor `item_id`, que es un orden aleatorio), sin ponderar, con
   la misma regla de soporte aplicada sobre ese subconjunto. Mide cuánto de la F1 principal depende de descripciones
   repetidas. Si la regla de soporte fusiona más clases que en la principal, se reporta cuáles.
4. Prevalencias por clase: ponderadas y sin ponderar (D-M6; nota para WP8:
   `docs/datos_reales/nota_wp4_para_wp8_pesos_e_ic.md`).
5. **Ítems con una sola anotación (enmienda v1.2).** Si los hay (§12), la F1-macro se reporta además **solo sobre los
   ítems con doble anotación**, como sensibilidad.
6. **Subgrupo aparte (enmienda v1.2):** los reversos y devoluciones de tarjeta (6 ítems) se reportan por separado;
   probablemente no existen en el sintético.
7. **Dominio ausente por azar del sorteo (declaración v1.3; corrige la v1.2).**
   - **Corrección de la cifra de la v1.2:** el patrón de texto usado contaba como «PSE sin facturador» también 6 PSE
     con facturador identificable (un colegio, una IPS, una telefónica, una tienda, una empresa de medicina), que R5
     sí resuelve. El dominio correcto, solo pasarela o banco, tiene **95 filas del marco (4,4 %)**, y la muestra tiene
     **0**. Los 4 ítems de la v1.2 eran PSE con facturador.
   - **Los pesos están bien (verificado).** Todas las filas del marco tienen probabilidad de inclusión positiva
     (mínimo 0,0038): el tope k = 3 no deja filas con probabilidad cero, así que **no hay error de cobertura**.
     Simulando el diseño completo con 400 semillas distintas, la media de Σ pesos es 2.172 (marco 2.183), la media por
     estrato es 0,98–1,02 veces su tamaño y la media en el dominio es 91,6 (N = 95). Los pesos son insesgados.
   - **Es varianza, no sesgo.** El dominio está concentrado en dos descriptores (44 y 33 filas) cuyos ítems pesarían
     263 y 198 si salieran. Se esperaba ≈ 1 ítem y en el 36 % de las réplicas sale 0, como en esta muestra. El
     estimador ponderado es insesgado en repetición del muestreo, pero en esta muestra concreta el dominio aporta peso
     0 y el estimador de Hájek reparte ese peso entre el resto.
   - **Consecuencia para el reporte:** la exactitud ponderada de esta muestra no dice nada sobre los PSE sin
     facturador, y el IC por bootstrap, que remuestrea solo lo observado, no refleja esa incertidumbre. Se declara que
     ≈ 4,4 % del marco (95 filas) es un tipo de transacción sin ninguna representación realizada en el test. No se
     re-muestrea: el diseño está congelado. El caso se practica en la calibración (ítem C03).
3. **Limitación:** el marco es una muestra por conveniencia de 6 grupos de extractos de ≤ 7 titulares. Los pesos
   corrigen el diseño muestral, **no** la representatividad poblacional.

## 5. Ronda de calibración

- 20 ítems (`calibracion.xlsx`, ids `C01–C20`) **fuera del test y de descriptores que no aparecen en el test**, para
  que discutirlos juntos no contamine el κ. Reparto por estrato en orden de tamaño (1–2 por estrato).
- Se anotan juntos con los 6 campos; no entran al κ ni al test. Después la guía no se cambia: las dudas se resuelven
  con R1–R7 y se registran como insumo de v2.
- **Cuatro casos sin resolver en la taxonomía (enmienda v1.2):** reversos/devoluciones, PSE sin facturador,
  transferencias a/desde billetera sin persona y «Compra en PERSONA». Hoja de trabajo:
  `docs/datos_reales/07_hoja_calibracion_casos.md`.
  - La convención se elige **con el texto de la taxonomía v1.1** (citando la regla o definición) y **nunca** mirando lo
    que hace el generador sintético. Queda como hallazgo para la v1.2 de la taxonomía.
  - Se registra que «TRANSFERENCIAS A NEQUI» pesa **235 transacciones** del marco (3 ítems del test con peso ≈ 119).
  - En estos casos **el κ mide el seguimiento de una convención pactada**, no un acuerdo independiente. Por eso el
    κ se reporta también **sin los ítems de los 4 casos** (identificados por patrón de texto en `tools/acuerdo_wp4.py`,
    fijado antes de anotar; el patrón de PSE se corrigió en la v1.3, también antes de anotar), como dato descriptivo.
    En el test: compra en PERSONA 4 ítems, reversos 6, transferencias a billetera 7, PSE sin facturador 0.
- **Regla para AMBAS anotadoras (enmienda v1.2):** no buscar en internet comercios desconocidos; aplicar R7 y marcar
  `duda = 1`.

## 6. Anotación doble a ciegas

- **Criterio (D-M5):** el anotador ve lo mismo que el clasificador: `cuenta_tipo`, `signo`, `monto`, `descripcion`
  (+ `item_id` opaco). Se ocultan `tx_id`, seudónimo, fecha y estrato. Única asimetría declarada: el anotador ve el
  monto exacto y el clasificador lo ve en rangos log10.
- **Lotes:** `lote_A1.xlsx` / `lote_A2.xlsx`, mismos 200 ítems, **orden distinto** (claves SHA independientes), con
  listas desplegables de los valores de la taxonomía v1.1.0 y columnas observables bloqueadas contra edición
  accidental. Los `.csv` homónimos son la versión sin anotar con SHA-256 registrado.
- **Campos (D-M4):**
  - A2 (maestrante): `categoria_n1`, `categoria_n2` (opcional), `duda` (0/1), `notas`.
  - A1 (investigadora): lo anterior + `medio_pago`, `formalidad_comercio`. Estas dos quedan con una sola anotadora,
    sin κ, y no se usan en el TSTR (WP8 nunca las usa como entrada ni como objetivo).
  - **Desviación declarada** de la guía v1.0 §6.2 (κ por dimensión): el κ se calcula solo sobre `categoria_n1`.
    El subconjunto de 60 filas de formalidad para A2 se hace solo si la formalidad se reporta; por ahora, no.
  - **`canal_p2p` y `fuente_etiqueta` se asignan por regla, no por anotación.** Taxonomía v1.1.0, regla **R2**:
    «Si el voluntario declara el propósito, se asigna la categoría del propósito y se marca canal_p2p=true»; y
    `atributos_de_anotacion.canal_p2p`: «true cuando el propósito fue declarado por el voluntario». En la v3,
    `proposito_declarado` está vacío en las **2.471 filas** (verificado), así que ninguna fila cumple la condición:
    `canal_p2p = false` y `fuente_etiqueta = texto` en todas. Consecuencia: el corte texto/declaración de WP8 no aporta
    información y el gasto «disfrazado de P2P» no es medible con este conjunto. Ambas cosas van como limitación.
- **A2** firma compromiso de confidencialidad (protocolo 02 §6) antes de recibir `lote_A2.xlsx`; entrega por canal
  restringido. Recibe **solo** su lote (y `calibracion.xlsx` en la sesión conjunta), nunca los archivos `*_clave.csv`
  ni `marco_muestreo.csv`.
- **κ:** Cohen sobre `categoria_n1`, IC95 por bootstrap (2.000 réplicas, semilla 42, remuestreo por fila
  estratificado por `estrato_muestreo`), % de acuerdo bruto, matriz de confusión A1×A2. Meta de la guía: κ ≥ 0,61.
- **Adjudicación:** cada desacuerdo se resuelve por discusión A1–A2 y se registra la causa (error de un anotador /
  ambigüedad de la regla / descripción insuficiente). Las ambigüedades del esquema van a la lista de v2.

### Declaraciones sobre la anotación (enmienda v1.1)

- **El κ se mide después de la sesión de calibración.** Mide el acuerdo entre anotadores con criterios alineados, no
  el de anotadores sin entrenamiento; puede ser mayor que el que lograrían anotadores independientes sin calibrar.
- **A1 no anota a ciegas respecto a los datos.** La investigadora revisó los extractos durante la extracción y la
  anonimización, y puede reconocer comercios, patrones o el grupo de origen. Sí es ciega respecto a las etiquetas de
  A2. Mitigación: A1 anota solo desde `lote_A1.xlsx` (sin fecha, grupo ni contexto), y en la adjudicación la etiqueta
  final debe justificarse con lo que ve el clasificador (D-M5), no con el conocimiento previo de los datos. A2 sí es
  ciego a los datos.
- **El test tiene 6 grupos de extractos** (V04, V05, V06, V07, V09, V10), de ≤ 6 titulares; V08 queda fuera por mes.

## 7. Archivo final para WP8

`data/reales_anon/test_real_wp4_<AAAAMMDD>[_planb].csv`, escrito por `tools/consolidar_test_wp4.py` (v1.3).
Primero las 8 columnas de `COLUMNAS_WP4` de `etapa4_tstr.py`, en su orden
(`descripcion, monto, fecha, signo, cuenta_tipo, categoria_n1, fuente_etiqueta, voluntario_id`, como el fixture
`tests/fixtures/real_simulado_wp4.csv`); después, columnas de análisis que WP8 nunca usa como entrada:
`item_id, tx_id, categoria_n2, medio_pago, formalidad_comercio, canal_p2p, peso_muestreo, estrato_muestreo,
doble_anotacion (si/no), origen_etiqueta (acuerdo/adjudicacion/solo_A1/solo_A2), caso_convencion (cuál o vacío),
subgrupo_reverso (si/no), unica_por_descripcion (si/no, sensibilidad §4.3)`.

- `monto` va tal cual, incluido 0: lo que se haga con monto 0 lo decide el serializador de WP8.
- Etiqueta final: acuerdo de A1 y A2; si difieren, la de `adjudicacion.xlsx` (con causa obligatoria); con un solo
  anotador, la suya. El script se detiene si falta una adjudicación, si un ítem no tiene ninguna anotación o si la
  adjudicación no corresponde a los lotes actuales.
- El script verifica el archivo con las propias funciones de WP8 (`cargar_tabla`, `deflactar_test_a_2025`,
  `serializar`); si no pasa, lo renombra a `.INVALIDO`.

- **`signo` se recodifica `egreso → -`, `ingreso → +`**, como emite el sintético (`src/sdg/generador.py`).
- `voluntario_id` = grupo de extractos (seudónimo). Un grupo no es necesariamente un voluntario (V09/V10 podrían ser
  la misma persona).

### Intervalo de confianza — desviación del arnés de WP8 (D-M7, 2026-11-25)

El arnés de WP8 tenía como IC principal el bootstrap por conglomerado (por `voluntario_id`). **Desviación:** con 6
grupos de extractos en el marco, el bootstrap por conglomerado es inestable (462 réplicas distintas posibles; clases
concentradas en un solo grupo, así que una réplica sin él pierde clases enteras). Por eso:

- **IC principal:** bootstrap por fila, estratificado por `estrato_muestreo` (el diseño).
- **Sensibilidad:** bootstrap por **grupo de extractos** (no por titular).
- **Alcance de la inferencia:** «estos extractos». No se afirma generalización a nuevos titulares.

## 8. Decisiones

| Id | Decisión | Estado |
|---|---|---|
| D-M1 | n = 200 (m = 10, k = 3) | APROBADA |
| D-M2 | Excluir octubre y noviembre 2026 (sin IPC) | APROBADA |
| D-M3 | Filas "`de 1`" | OBSOLETA: la v3 las reconstruye; sin pérdida que declarar |
| D-M4 | A2 núcleo; A1 seis campos; κ solo `categoria_n1`; `canal_p2p`/`fuente_etiqueta` por regla R2 | APROBADA con cambio (verificación de R2) |
| D-M5 | El anotador ve lo mismo que el clasificador | APROBADA |
| D-M6 | `peso_muestreo` opcional en `etapa4_tstr.py` (exactitud ponderada) | Nota enviada a WP8 |
| D-M7 | IC por fila estratificado; sensibilidad por grupo de extractos; alcance «estos extractos» | APROBADA (desviación del arnés WP8) |

## 9. Carga de anotación estimada (A2)

Modo núcleo ≈ 25 s/ítem → ≈ 1 h 25 para 200 + 30 min de guía + 40 min de calibración ≈ **2 h 35**.
Adjudicación (20–30 % de desacuerdo, ≈ 1,5 min por caso entre los dos): ≈ 1–1,5 h.

## 10. Registro de decisiones

| Fecha | Id | Decisión | Quién |
|---|---|---|---|
| 2026-11-25 | — | Borrador v0.1 escrito antes de muestrear | Claude (propuesta) |
| 2026-11-25 | D-M1 | n = 200 (m = 10, k = 3) | Investigadora |
| 2026-11-25 | D-M2 | Se excluyen octubre y noviembre 2026 | Investigadora |
| 2026-11-25 | D-M3 | Obsoleta: CSV regenerados (v3, 2.471 filas) | Investigadora |
| 2026-11-25 | D-M4 | Aprobada; `canal_p2p = false` verificado contra R2 y datos | Investigadora |
| 2026-11-25 | D-M5 | Aprobada | Investigadora |
| 2026-11-25 | D-M7 | Aprobada como desviación fechada del arnés WP8 | Investigadora |
| 2026-11-25 | — | Corrección: n efectivo real 48, no ≈ 136 (error de cálculo del borrador); se mantiene k = 3 | Claude (declarada; pendiente de visto bueno) |
| 2026-11-25 | — | Muestra generada y pre-registro cerrado v1.0 | Claude |
| 2026-11-25 | — | Visto bueno al tope k = 3 con n efectivo 48 | Investigadora |
| 2026-11-25 | v1.1 | Métricas (§4), razón del corte (§1), declaraciones (§6), plan B (§12); antes de anotar | Investigadora |
| 2026-11-26 | v1.1 | Visto bueno: plan B 154, recorte P95 con umbral 5 pts, sensibilidad por descripción única, κ sobre ≥ 80 en común | Investigadora |
| 2026-11-26 | v1.2 | Redacción del corte, regla R7 para ambas, F1 solo doble anotación, 4 casos de calibración, dominio PSE sub-representado | Investigadora / Claude (dominio PSE) |
| 2026-11-26 | v1.3 | Verificación de pesos (insesgados, sin π = 0; simulación de 400 semillas). Corrección del dominio PSE sin facturador: 95 filas, 0 en el test (la v1.2 decía 101 y 4). Patrón corregido en `acuerdo_wp4.py`. Sin cambios en ítems, lotes ni pesos. | Claude (pedido por la investigadora) |

## 11. Ejecución

- Marco 2.183 · test 200 · calibración 20 · n efectivo 48.
- Muestra por grupo: V09 51, V10 45, V05 44, V07 41, V06 12, V04 7. Por cuenta × signo: banco egreso 76, banco
  ingreso 28, tarjeta egreso 89, tarjeta ingreso 7.
- SHA-256 de las salidas (CSV):

| archivo | sha256 |
|---|---|
| marco_muestreo.csv | `bfeb7f7b3ad3338ce20da98c314c5991e1b0b66c124e10b2fb0522e873d66c76` |
| muestra_test_clave.csv | `fde28575f031dbb384ce273e17554297bbc7ed395467dd0f84a5c5506d2c2f9a` |
| lote_A1.csv | `8b73f2e351d5ffc6a3cf894724f89d8e8c86fd029ada4269a17a84806578d025` |
| lote_A2.csv (v1.1: orden por bloques + columna `orden`) | `b8b0a52847d01c645585998bf0da87b0c7bdd7d335f666ff897f710b65909a4e` |
| muestra_test_clave_planb.csv (v1.1) | `82ae9dfd97cd4a3fa6e9865d76fa4317db0bdd30350f6e41df632dd7be7f0010` |
| calibracion.csv | `55029627e4714304762c01d6ec5e8028bc13e1fb18c989df6d6af312176ba645` |
| calibracion_clave.csv | `a54e1f6b6fe95402fd6ae0d1f1b460e078415d420ba9715142dba3da3410c168` |

## 12. Plan B de calendario (enmienda v1.1)

**Disparador:** si a las **12:00 del 26 nov 2026** A2 no ha terminado los 200 ítems, se reduce el test.

**Tamaño: 154, no 150.** Con el mismo diseño (m = 10, k = 3), el mínimo posible es la suma de los mínimos por estrato:
154. Llegar a 150 exige bajar m a 8, y entonces varias categorías raras quedarían con menos de 10 ejemplos, debajo de
la regla de soporte de la F1-macro. Se prefiere conservar m.

**Anidado, sin re-muestrear.** El plan B usa las mismas claves SHA y la misma etapa 1; en la etapa 2 toma, en cada
estrato, los `n_h = min(R_h, 10)` ítems de menor clave. Por construcción son un subconjunto de los 200 (verificado por
el script). Por eso:

- `lote_A2` trae primero esos 154 ítems (orden aleatorio dentro del bloque) y después los 46 restantes, con una
  columna `orden` (1–200). A2 anota en orden. Única pista que revela el orden: los 46 últimos vienen de los estratos
  grandes (la parte proporcional). Se declara; no cambia qué ve el anotador de cada ítem.
- `lote_A1` no cambia. A1 anota los 200 en su orden propio.
- `muestra_test_clave_planb.csv` trae los 154 ítems con los **pesos del diseño de 154** (`π2 = n_h/R_h` con el `n_h`
  del plan B). n efectivo (Kish) = 27; 119 descripciones distintas. Σ pesos = 2.648: también insesgado (simulando el
diseño con 400 semillas, la media es 2.185 frente a N = 2.183); el valor observado cae en el percentil 92.

**Comandos:**

```
python tools/muestreo_wp4.py --plan-b      # estado: cuántos de los 154 tiene cada anotador y cuáles faltan
```

Si se activa, los pasos de κ, adjudicación y archivo final para WP8 se corren sobre
`data/reales_anon/anotacion/muestra_test_clave_planb.csv` en lugar de `muestra_test_clave.csv` (argumento `--clave`
de los scripts de las tareas 4 y 5). Los 46 ítems restantes no entran al test ni al κ aunque estén anotados.

**Si A2 tampoco completó los 154 a las 12:00:** el κ se calcula sobre los ítems que ambos anotaron (la guía v1.0 §6
pide un solapamiento ≥ 80), se declara el n y el test para WP8 sigue siendo el de 154 con la etiqueta de A1 en los
ítems sin doble anotación, marcados como tales.
