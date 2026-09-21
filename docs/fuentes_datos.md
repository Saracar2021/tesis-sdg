# Fuentes de datos — referencia de integridad

> Generado por `tools/generar_fuentes_datos.py` desde `data/raw/` (solo lectura). Todas las cifras salen de código; las mismas están en `outputs/fuentes_datos.json`. Para regenerar: `.venv\Scripts\python.exe tools\generar_fuentes_datos.py`.

## 0. Reglas de lectura (fijas)

| Grupo | Encoding de carga | Separador | Nota |
|---|---|---|---|
| GEIH `.csv` | `cp1252` | `;` | Decodifica todo ASCII; los pocos bytes no ASCII son 0xD1/0xF1 (Ñ/ñ). Nunca UTF-8. |
| ENPH `.csv` | `utf-8-sig` | `;` | Trae BOM; con `utf-8` la primera columna sale como `\ufeffDIRECTORIO`. |
| ENPH `.txt` | `utf-8` | tab | ASCII, sin BOM. Conservan la extensión `.txt`. |

Los archivos se extrajeron **tal cual** (bytes intactos); el SHA-256 de cada uno coincide con el del contenido del zip (`outputs/normalizar_datos_log.json`). La columna «Encoding detectado» es el real, por decodificación estricta (sin chardet, que dio `CP874`/`Big5` sobre archivos cp1252).

## 1. Riesgos metodológicos y pendientes

| # | Tema | Estado | Resumen |
|---|---|---|---|
| 1 | Comparabilidad **estructural** GEIH | VERIFICADO | Los encabezados de las 96 tablas son idénticos entre meses (mismas columnas, mismo orden): 8 de 8 módulos, 12/12 meses. |
| 2 | Comparabilidad **semántica** GEIH (redacción/definición de preguntas) | PENDIENTE | El control de cambios de `_metadatos/` no cubre 2025; ver §7. No se puede afirmar ni descartar. |
| 3 | Menos filas en diciembre | PENDIENTE (no explicado) | Diferencia pequeña y difusa; la documentación disponible no la explica; ver §8. |
| 4 | `gastos_diarios_hogar.txt` | VERIFICADO (autoconsistencia) | Descarga fresca del 20 sep 2026; conteo de referencia en §5. No hay cifra oficial contra la cual cotejar. |
| 5 | Unidad de análisis y **llave de hogar** ENPH | RIESGO (afecta una regla de CLAUDE.md) | Solo 3 de 16 archivos son una fila por hogar/persona; los otros 13 son registros de gasto. En ENPH el hogar se identifica solo por `DIRECTORIO`; la regla de unión `DIRECTORIO + SECUENCIA_P + HOGAR` es de GEIH y en ENPH pierde filas (ver §4). |
| 6 | DDI de GEIH desactualizado | RIESGO | Título «GRAN ENCUESTA INTEGRADA DE HOGARES 2016 metodologia», «estructura … aplica para el 2023», `caseQnty` = 0. No usar como fuente de conteos ni de etiquetas 2025. |
| 7 | Definición de Bogotá | RIESGO | En GEIH, `AREA=11` (urbano) y `DPTO=11` (incluye zona rural) no son equivalentes; en ENPH solo existe el texto `BOGOTÁ` (sin código). Ver §10.1. |
| 8 | Tamaño de muestra de Bogotá | RIESGO | Cruce estrato × quintil: 12 de 30 celdas con <30 observaciones en ENPH (3.918 hogares); 8 de 30 en GEIH con 12 meses apilados y 16–20 con un solo mes. Ver §10.3. |
| 9 | Prefijo `NC2R_` | RIESGO | No está documentado y `NC2R_CC_P6` viene rellena en hogares urbanos: no usar el prefijo para filtrar por área. Ver §10.4. |
| 10 | Rotación / independencia de los 12 meses de GEIH | PENDIENTE (parcial) | Ningún hogar aparece en más de un mes (292.942 hogares únicos = filas apiladas), pero `DIRECTORIO` es un contador por mes y la frecuencia de revisita no está documentada; sin identificador de segmento no hay errores estándar de diseño. `FEX_C18/12` sigue siendo válido. Ver §11. |

**Sobre 1 y 2 (son dos cosas distintas).** Que los nombres y el orden de columnas coincidan sostiene el apilamiento *técnico* de los 12 meses. No sostiene la comparabilidad *semántica*: un cambio de redacción de una pregunta, de una alternativa de respuesta o de una definición no altera el nombre de la columna. Esa revisión depende del control de cambios del formulario, y ese documento no llega a 2025 (§7).

## 2. Verificación GEIH 2025: 12 meses × 8 módulos

`OK` = existe, SHA-256 igual al del zip, encabezado idéntico al de enero, `MES` y `PERIODO` (2025) coherentes con la carpeta, ≥1 fila, sin filas irregulares, decodifica con la regla fija y la unidad declarada es consistente con las llaves. `FALTA` = no existe. `REVISAR` = existe pero falla algún control.

| Mes | caracteristicas_generales | datos_hogar | fuerza_trabajo | migracion | no_ocupados | ocupados | otras_formas_trabajo | otros_ingresos |
|---|---|---|---|---|---|---|---|---|
| 01_enero | OK | OK | OK | OK | OK | OK | OK | OK |
| 02_febrero | OK | OK | OK | OK | OK | OK | OK | OK |
| 03_marzo | OK | OK | OK | OK | OK | OK | OK | OK |
| 04_abril | OK | OK | OK | OK | OK | OK | OK | OK |
| 05_mayo | OK | OK | OK | OK | OK | OK | OK | OK |
| 06_junio | OK | OK | OK | OK | OK | OK | OK | OK |
| 07_julio | OK | OK | OK | OK | OK | OK | OK | OK |
| 08_agosto | OK | OK | OK | OK | OK | OK | OK | OK |
| 09_septiembre | OK | OK | OK | OK | OK | OK | OK | OK |
| 10_octubre | OK | OK | OK | OK | OK | OK | OK | OK |
| 11_noviembre | OK | OK | OK | OK | OK | OK | OK | OK |
| 12_diciembre | OK | OK | OK | OK | OK | OK | OK | OK |

Resumen: 96 OK, 0 REVISAR, 0 FALTA (de 96). `n_meses` = 12.

**ENPH 2016-2017 (16 archivos):**

| Archivo | Estado |
|---|---|
| `ENPH_2017/hogares/viviendas_hogares.csv` | OK |
| `ENPH_2017/hogares/gastos_menos_frecuentes_medio_pago.csv` | OK |
| `ENPH_2017/hogares/gastos_menos_frecuentes_articulos.txt` | OK |
| `ENPH_2017/personas/caracteristicas_generales_personas.csv` | OK |
| `ENPH_2017/urbano/gastos_diarios_hogar_comidas_fuera.csv` | OK |
| `ENPH_2017/urbano/gastos_diarios_personales.csv` | OK |
| `ENPH_2017/urbano/gastos_diarios_capitulo_c.txt` | OK |
| `ENPH_2017/urbano/gastos_diarios_mercados.csv` | OK |
| `ENPH_2017/urbano/gastos_diarios_hogar.txt` | OK |
| `ENPH_2017/urbano/gastos_personales_comidas_fuera.csv` | OK |
| `ENPH_2017/rural/gastos_personales_comidas_fuera.csv` | OK |
| `ENPH_2017/rural/gastos_personales.csv` | OK |
| `ENPH_2017/rural/gastos_semanales_capitulo_c.csv` | OK |
| `ENPH_2017/rural/gastos_semanales_comidas_fuera.csv` | OK |
| `ENPH_2017/rural/gastos_semanales_mercados.csv` | OK |
| `ENPH_2017/rural/gastos_semanales.csv` | OK |

Criterio de `OK` en ENPH: existe, SHA-256 igual al del zip, decodifica con la regla fija, sin filas irregulares y unidad declarada consistente con las llaves (§4).

## 3. GEIH 2025 — detalle por archivo (96)

Unidad: `persona` = una fila por (`DIRECTORIO`, `SECUENCIA_P`, `HOGAR`, `ORDEN`); `hogar` = una fila por (`DIRECTORIO`, `SECUENCIA_P`, `HOGAR`). Factor de expansión: `FEX_C18` (presente en los 8 módulos); al apilar los 12 meses, `FEX_C18 / 12`.

| Módulo | Unidad de análisis | Columnas | Filas (mín–máx) | Encabezado igual 12/12 | Llave única 12/12 | Llaves ⊂ CG 12/12 |
|---|---|---|---|---|---|---|
| caracteristicas_generales | una fila por persona del hogar | 55 | 66.559–68.710 | sí | sí | n/a |
| datos_hogar | una fila por hogar | 49 | 24.109–24.774 | sí | sí | n/a |
| fuerza_trabajo | una fila por persona (subconjunto de características generales) | 42 | 53.461–55.085 | sí | sí | sí |
| migracion | una fila por persona | 43 | 66.559–68.710 | sí | sí | sí |
| no_ocupados | una fila por persona no ocupada (subconjunto) | 37 | 23.850–25.753 | sí | sí | sí |
| ocupados | una fila por persona ocupada (subconjunto) | 202 | 28.317–30.939 | sí | sí | sí |
| otras_formas_trabajo | una fila por persona (subconjunto) | 112 | 53.461–55.085 | sí | sí | sí |
| otros_ingresos | una fila por persona (subconjunto) | 59 | 53.461–55.085 | sí | sí | sí |


| Mes | Módulo | Ruta destino | Unidad | Filas | Cols | SHA-256 | Encoding detectado | Sep |
|---|---|---|---|---|---|---|---|---|
| enero | caracteristicas_generales | `GEIH_2025/01_enero/caracteristicas_generales.csv` | persona | 67.857 | 55 | `b69c4ebb584abc29d5cd947369b54cef2c5dc93505700824107be5aa7e808a53` | ASCII | `;` |
| enero | datos_hogar | `GEIH_2025/01_enero/datos_hogar.csv` | hogar | 24.109 | 49 | `50e846ae35b8e80a249ebfcd9dbd9568d8e11924a9049d7b68ffa53a8d198568` | cp1252 (bytes 0xD1) | `;` |
| enero | fuerza_trabajo | `GEIH_2025/01_enero/fuerza_trabajo.csv` | persona | 54.070 | 42 | `28ee662da6eb2588d7087792ecb85766fb88559304632466f376275f750732ba` | cp1252 (bytes 0xD1, 0xF1) | `;` |
| enero | migracion | `GEIH_2025/01_enero/migracion.csv` | persona | 67.857 | 43 | `6b2a3a34d7f6163413c76fb726a7060d4f4e8d57cc4661002934988be1ca4feb` | cp1252 (bytes 0xD1) | `;` |
| enero | no_ocupados | `GEIH_2025/01_enero/no_ocupados.csv` | persona | 25.753 | 37 | `ba4793cfdc2425e0f5835922f234e91d3651e920e8dfb57addf2e537d27a776c` | ASCII | `;` |
| enero | ocupados | `GEIH_2025/01_enero/ocupados.csv` | persona | 28.317 | 202 | `cffae16cf91033ed8a45684216ed0be8992c76a6a9363f09a95e639229e6f271` | cp1252 (bytes 0xD1) | `;` |
| enero | otras_formas_trabajo | `GEIH_2025/01_enero/otras_formas_trabajo.csv` | persona | 54.070 | 112 | `d6498fab86732ab50251589e07f7c4c973dc1c1210a68bb07194986ca8bec36b` | ASCII | `;` |
| enero | otros_ingresos | `GEIH_2025/01_enero/otros_ingresos.csv` | persona | 54.070 | 59 | `44b358d38e7390293d26102e8ffd3ba0132469f889c1951b0ce791b4066b00d6` | cp1252 (bytes 0xD1) | `;` |
| febrero | caracteristicas_generales | `GEIH_2025/02_febrero/caracteristicas_generales.csv` | persona | 67.953 | 55 | `8aca3bbe535a4be74522f78cd0ac10f946f2e2929ab5e6f7d1171fa03d281cc9` | ASCII | `;` |
| febrero | datos_hogar | `GEIH_2025/02_febrero/datos_hogar.csv` | hogar | 24.313 | 49 | `0754771f92c15e182bdba0cb40e5ae3caab02996baa2629492e7fbde7513c2d4` | cp1252 (bytes 0xD1) | `;` |
| febrero | fuerza_trabajo | `GEIH_2025/02_febrero/fuerza_trabajo.csv` | persona | 54.436 | 42 | `98df9a436f39c06ec05a8304cebcbb7a52dc2ac734678df897312e18431b70e1` | cp1252 (bytes 0xD1) | `;` |
| febrero | migracion | `GEIH_2025/02_febrero/migracion.csv` | persona | 67.953 | 43 | `b0eaaa982b79c5bb3d0920c2f8345c84a3aa107e5dfa4f6b5e2fc99823cecb8e` | cp1252 (bytes 0xD1) | `;` |
| febrero | no_ocupados | `GEIH_2025/02_febrero/no_ocupados.csv` | persona | 25.225 | 37 | `78cdf13d22fb49b1446e1eca24013b3d64db8b8fc9fda5aaf44001dd5e099e3d` | ASCII | `;` |
| febrero | ocupados | `GEIH_2025/02_febrero/ocupados.csv` | persona | 29.211 | 202 | `614900f5f2b9d85bcdde66228611a84f557597b2341adb0021e58d35b4a1cde1` | cp1252 (bytes 0xD1) | `;` |
| febrero | otras_formas_trabajo | `GEIH_2025/02_febrero/otras_formas_trabajo.csv` | persona | 54.436 | 112 | `069c8629c8521888565b74bbfa70c1a0edc724742eb88edae0beac14788d9217` | ASCII | `;` |
| febrero | otros_ingresos | `GEIH_2025/02_febrero/otros_ingresos.csv` | persona | 54.436 | 59 | `5acf860ea33d331627f5da2c9c3b486cb16aabaedf63334b22d6e79e9546b8ce` | ASCII | `;` |
| marzo | caracteristicas_generales | `GEIH_2025/03_marzo/caracteristicas_generales.csv` | persona | 68.083 | 55 | `ebcd0cd2dee38c18101e5b5d5160c3ff5e18aa211f4e7d26aa9a2c2747afbc9a` | ASCII | `;` |
| marzo | datos_hogar | `GEIH_2025/03_marzo/datos_hogar.csv` | hogar | 24.193 | 49 | `0634b93ce9b61235b72624628ea4bb6bbf359af217a4ba12dac02108cb5ec452` | ASCII | `;` |
| marzo | fuerza_trabajo | `GEIH_2025/03_marzo/fuerza_trabajo.csv` | persona | 54.372 | 42 | `3b679ebbba0556f88a323c7e6cd72b68b2ccff2f07e0bc7522bd9f7be9e4d74d` | cp1252 (bytes 0xD1, 0xF1) | `;` |
| marzo | migracion | `GEIH_2025/03_marzo/migracion.csv` | persona | 68.083 | 43 | `8b3da305eb6377499806b72e05bd5c3b8a1649aefe8e451fd9e005ac0279bef8` | cp1252 (bytes 0xD1) | `;` |
| marzo | no_ocupados | `GEIH_2025/03_marzo/no_ocupados.csv` | persona | 24.901 | 37 | `8f1398fd825d1ccb5d5b14fd6193e38fb30119c775e073c5c5bc3d7f2eeee7f7` | ASCII | `;` |
| marzo | ocupados | `GEIH_2025/03_marzo/ocupados.csv` | persona | 29.471 | 202 | `4a471d9fd3546c7c6d421fef392d042b85481070f612a56db1ec8fe28ac98683` | cp1252 (bytes 0xD1) | `;` |
| marzo | otras_formas_trabajo | `GEIH_2025/03_marzo/otras_formas_trabajo.csv` | persona | 54.372 | 112 | `1009ae33ad5b7f35b9dfb31aa940dee04e517fb2800cede8530808531e938c9f` | ASCII | `;` |
| marzo | otros_ingresos | `GEIH_2025/03_marzo/otros_ingresos.csv` | persona | 54.372 | 59 | `9fd2974b31a5226b8c07f3a3102148e644ab1b26f443a376099e67245fc56da7` | cp1252 (bytes 0xD1) | `;` |
| abril | caracteristicas_generales | `GEIH_2025/04_abril/caracteristicas_generales.csv` | persona | 68.253 | 55 | `b81065604b3644bad09911e1affb871dceed19ec663a4d95fd75973bce5a7178` | ASCII | `;` |
| abril | datos_hogar | `GEIH_2025/04_abril/datos_hogar.csv` | hogar | 24.253 | 49 | `ca5661becbd424c09baf10029080cd0a6f04f0ca7eca1a666886fac23251b39e` | cp1252 (bytes 0xD1) | `;` |
| abril | fuerza_trabajo | `GEIH_2025/04_abril/fuerza_trabajo.csv` | persona | 54.331 | 42 | `4669e358ec4bf2298be55bb168ebe901d351f83cbad5eb87ec9c4c9891897f1d` | cp1252 (bytes 0xD1) | `;` |
| abril | migracion | `GEIH_2025/04_abril/migracion.csv` | persona | 68.253 | 43 | `9c0e35f2a2a4fa4acd187b9de76cfdcf0bec1834128433bc207c1009fa0ff5f5` | cp1252 (bytes 0xD1) | `;` |
| abril | no_ocupados | `GEIH_2025/04_abril/no_ocupados.csv` | persona | 24.817 | 37 | `bc7940a98ec86dd5f01ff2cd6acd67149ce4411d07cc264862919b0b68ca1984` | ASCII | `;` |
| abril | ocupados | `GEIH_2025/04_abril/ocupados.csv` | persona | 29.514 | 202 | `168c3c3edb804d9a2709d25f6ed1b712655755db3667358dcaac712241db78a6` | cp1252 (bytes 0xD1) | `;` |
| abril | otras_formas_trabajo | `GEIH_2025/04_abril/otras_formas_trabajo.csv` | persona | 54.331 | 112 | `1c67542e65de3f821d6cb22e96ca22fb2bfbbcee90026eb296e8d7c56371e60e` | ASCII | `;` |
| abril | otros_ingresos | `GEIH_2025/04_abril/otros_ingresos.csv` | persona | 54.331 | 59 | `45a4c8a3dccb9aec615724a40470ec3248740fb3f23958c98d01ab9bd14a9ee0` | cp1252 (bytes 0xD1) | `;` |
| mayo | caracteristicas_generales | `GEIH_2025/05_mayo/caracteristicas_generales.csv` | persona | 68.421 | 55 | `0a452c7836f02b529b06e0af494ec3e06917cc74158d4e6aa9292f9dc5fbaca0` | ASCII | `;` |
| mayo | datos_hogar | `GEIH_2025/05_mayo/datos_hogar.csv` | hogar | 24.401 | 49 | `146e849e0d1bf263d1ebff6d037febdf8c2c444221ce5d14016489bfea04ec45` | ASCII | `;` |
| mayo | fuerza_trabajo | `GEIH_2025/05_mayo/fuerza_trabajo.csv` | persona | 54.662 | 42 | `70e0ac4f934814569c86c5c6249db2740e62c1706fbd167487736e12e9be1d2e` | cp1252 (bytes 0xD1, 0xF1) | `;` |
| mayo | migracion | `GEIH_2025/05_mayo/migracion.csv` | persona | 68.421 | 43 | `68f975c5eb704d8e40f4f9cd10673ead0d89b6bc3acd60b1af27a68fb9395adb` | ASCII | `;` |
| mayo | no_ocupados | `GEIH_2025/05_mayo/no_ocupados.csv` | persona | 24.705 | 37 | `a08e30e4cb5d4ab873d6a2e1dd92416e3961e6be392949985e17be31fab901c9` | ASCII | `;` |
| mayo | ocupados | `GEIH_2025/05_mayo/ocupados.csv` | persona | 29.957 | 202 | `8ecb7dbdce91ad2f8372e9d95fe60466aaaacd38b66a7805f1fd601c1f8ef305` | cp1252 (bytes 0xD1, 0xF1) | `;` |
| mayo | otras_formas_trabajo | `GEIH_2025/05_mayo/otras_formas_trabajo.csv` | persona | 54.662 | 112 | `293bbfdfa8ebffc7e3eb983fe47156a4eb190405a06682dec952f8ad2ecf54f2` | ASCII | `;` |
| mayo | otros_ingresos | `GEIH_2025/05_mayo/otros_ingresos.csv` | persona | 54.662 | 59 | `ec5c65d9a6c6b7b4017e2416462723f7477ca89d425016ad3b1c0be523a030d8` | cp1252 (bytes 0xD1) | `;` |
| junio | caracteristicas_generales | `GEIH_2025/06_junio/caracteristicas_generales.csv` | persona | 67.856 | 55 | `5ba6ed02c0465f96fb34359b98835fe4f198b745cd6a281efdb0bb067063f4d8` | ASCII | `;` |
| junio | datos_hogar | `GEIH_2025/06_junio/datos_hogar.csv` | hogar | 24.337 | 49 | `a069af0160cdc4490364a03d2bd1a89242773ce1590a21e333c83cf7fba2ee15` | ASCII | `;` |
| junio | fuerza_trabajo | `GEIH_2025/06_junio/fuerza_trabajo.csv` | persona | 54.450 | 42 | `bc4adf3cdf1116c2124539e40d3851b187071ab1abd73a102cad7c93e0b817d6` | cp1252 (bytes 0xD1, 0xF1) | `;` |
| junio | migracion | `GEIH_2025/06_junio/migracion.csv` | persona | 67.856 | 43 | `fef8ae7ca40017fdd440af5fcd298ff412f7353bce362de39586328b61018211` | cp1252 (bytes 0xD1, 0xF1) | `;` |
| junio | no_ocupados | `GEIH_2025/06_junio/no_ocupados.csv` | persona | 24.744 | 37 | `cb6a829ca28573334ab85cf1320ec604257aad49119bff6e6439de09ed4fe8de` | ASCII | `;` |
| junio | ocupados | `GEIH_2025/06_junio/ocupados.csv` | persona | 29.706 | 202 | `a4f7aef8e960a91fee51b85d4162c2d022d4d73d9b38cfa54f32a6625d4ebf91` | cp1252 (bytes 0xD1) | `;` |
| junio | otras_formas_trabajo | `GEIH_2025/06_junio/otras_formas_trabajo.csv` | persona | 54.450 | 112 | `3de54664911c7b4f1f5f8310ff9cab48648058e0c576c546a8bb182eb8ba763a` | ASCII | `;` |
| junio | otros_ingresos | `GEIH_2025/06_junio/otros_ingresos.csv` | persona | 54.450 | 59 | `1023dd2db541ac63968b3fa8b67ed32b76995f0c1949841eb241c4734726dc6b` | ASCII | `;` |
| julio | caracteristicas_generales | `GEIH_2025/07_julio/caracteristicas_generales.csv` | persona | 68.436 | 55 | `7de3c6028d8fe8c0e7fb802f691676cb6f04a2dd81fd393bc794645f2469f2dc` | ASCII | `;` |
| julio | datos_hogar | `GEIH_2025/07_julio/datos_hogar.csv` | hogar | 24.546 | 49 | `aa4dccec613c090a249c251fecc58a18660455967f2baf59f521a59f34e70009` | ASCII | `;` |
| julio | fuerza_trabajo | `GEIH_2025/07_julio/fuerza_trabajo.csv` | persona | 54.630 | 42 | `1c3969665bc1d5247144b366d3eaf49d3fcba3e6e97146f2430c21a0a262670c` | cp1252 (bytes 0xD1, 0xF1) | `;` |
| julio | migracion | `GEIH_2025/07_julio/migracion.csv` | persona | 68.436 | 43 | `67c4a4ccbe175eb4ba2d5b747f859f1017d9aacb114e7f1f267bb15fba6ec9ab` | cp1252 (bytes 0xD1) | `;` |
| julio | no_ocupados | `GEIH_2025/07_julio/no_ocupados.csv` | persona | 24.477 | 37 | `e3b3fc1df3f97974f6f22d0b04bbe12a0366623741835a1e11d3cd9b72e70534` | ASCII | `;` |
| julio | ocupados | `GEIH_2025/07_julio/ocupados.csv` | persona | 30.153 | 202 | `c0ec1d20a7327d17532ce40ab718ed0f94a0a66a0727a5a430fc6d254fc4af08` | cp1252 (bytes 0xD1) | `;` |
| julio | otras_formas_trabajo | `GEIH_2025/07_julio/otras_formas_trabajo.csv` | persona | 54.630 | 112 | `78d683ca8c8a535396a126c42ad6a2be2bcb4cdcac4b861c73d0cbf92de7abf2` | cp1252 (bytes 0xD1) | `;` |
| julio | otros_ingresos | `GEIH_2025/07_julio/otros_ingresos.csv` | persona | 54.630 | 59 | `37060e748d127f33592e9c7a43891f67335481299a26cd7ccb5c882c93e88b64` | ASCII | `;` |
| agosto | caracteristicas_generales | `GEIH_2025/08_agosto/caracteristicas_generales.csv` | persona | 68.577 | 55 | `a1adf5c39b661449c2d66564e43f76a7f4a877293f119a997428952e5c85ee00` | ASCII | `;` |
| agosto | datos_hogar | `GEIH_2025/08_agosto/datos_hogar.csv` | hogar | 24.609 | 49 | `e74d44e72213909c5657d58ead2e05b2555a3bef06431575e6c1d0122171f524` | ASCII | `;` |
| agosto | fuerza_trabajo | `GEIH_2025/08_agosto/fuerza_trabajo.csv` | persona | 54.791 | 42 | `c60078e1d01e50fd3a5c82455a33bdcd302d95b4e65dc2a3a8024699efbb585d` | cp1252 (bytes 0xD1) | `;` |
| agosto | migracion | `GEIH_2025/08_agosto/migracion.csv` | persona | 68.577 | 43 | `aba177673c338f5a55109c0d4eaa82d5083901e3f2fe066709f82e3052e81290` | cp1252 (bytes 0xD1) | `;` |
| agosto | no_ocupados | `GEIH_2025/08_agosto/no_ocupados.csv` | persona | 24.636 | 37 | `3466d5f2be1e55b60d755cb9b3347c84abd98c3b0e79e398b04dc1fa293b7ab4` | ASCII | `;` |
| agosto | ocupados | `GEIH_2025/08_agosto/ocupados.csv` | persona | 30.155 | 202 | `91a6ddb55eeb518b9d1b9bfa3e19ddb0d0a7de482f2ec2ddcb9136c1aa932ab2` | cp1252 (bytes 0xD1) | `;` |
| agosto | otras_formas_trabajo | `GEIH_2025/08_agosto/otras_formas_trabajo.csv` | persona | 54.791 | 112 | `79d48db326cb6c1f7b3d3f9570528617e7323005523f751bdd4468ca790b24b0` | ASCII | `;` |
| agosto | otros_ingresos | `GEIH_2025/08_agosto/otros_ingresos.csv` | persona | 54.791 | 59 | `516ec207924fe54f093183b0301197952fd03d5680bb6b798ba9d5daaf89f8d7` | cp1252 (bytes 0xD1) | `;` |
| septiembre | caracteristicas_generales | `GEIH_2025/09_septiembre/caracteristicas_generales.csv` | persona | 68.263 | 55 | `72c164270869232d23bee4e9bce23ce2ddf36b30db892172910daef5722dc6a3` | ASCII | `;` |
| septiembre | datos_hogar | `GEIH_2025/09_septiembre/datos_hogar.csv` | hogar | 24.524 | 49 | `5fe81446654a21dddb986d64dba7ea7a70b8a25362641427eb680918bfead9a6` | ASCII | `;` |
| septiembre | fuerza_trabajo | `GEIH_2025/09_septiembre/fuerza_trabajo.csv` | persona | 54.543 | 42 | `083a4c959bc79c822a15f258f55a8f65470a737673e98536414ec2941ffa0f59` | cp1252 (bytes 0xD1) | `;` |
| septiembre | migracion | `GEIH_2025/09_septiembre/migracion.csv` | persona | 68.263 | 43 | `20e29a601c04a2c1a5602fbf91007da0b111d7637f12e349ec7e9c315e8386cd` | cp1252 (bytes 0xD1) | `;` |
| septiembre | no_ocupados | `GEIH_2025/09_septiembre/no_ocupados.csv` | persona | 24.355 | 37 | `4294aefbfeba35e8dd15aae54b2bb495baebaf69e2079a49acb6dc4bbb556cdf` | ASCII | `;` |
| septiembre | ocupados | `GEIH_2025/09_septiembre/ocupados.csv` | persona | 30.188 | 202 | `026a62e6bd30ce5b1cbf9975a9f98cf7f9ace58e284c8c722a942f70c6efbeaa` | cp1252 (bytes 0xD1) | `;` |
| septiembre | otras_formas_trabajo | `GEIH_2025/09_septiembre/otras_formas_trabajo.csv` | persona | 54.543 | 112 | `61dac0d2c0c7838f2507a76acca11811610759f5f9e178ac403c757bb7057c83` | ASCII | `;` |
| septiembre | otros_ingresos | `GEIH_2025/09_septiembre/otros_ingresos.csv` | persona | 54.543 | 59 | `369bfc27ec13cb522bbbef8d126d6d89535fa610cfcc7a1091ec54692789e351` | cp1252 (bytes 0xD1) | `;` |
| octubre | caracteristicas_generales | `GEIH_2025/10_octubre/caracteristicas_generales.csv` | persona | 68.710 | 55 | `af2a0e2ed580041a0d36c5f826842a3b026fac4d5ad15537f3f687f7b55b7e0c` | ASCII | `;` |
| octubre | datos_hogar | `GEIH_2025/10_octubre/datos_hogar.csv` | hogar | 24.774 | 49 | `78deb481802d5721e9c0b1b171bd8162b13d1b135d72546add862939859319c5` | cp1252 (bytes 0xD1) | `;` |
| octubre | fuerza_trabajo | `GEIH_2025/10_octubre/fuerza_trabajo.csv` | persona | 55.085 | 42 | `095d027e90ac7d7a6ea25ad18a6cef81baa48f9aa14ea92b5ba9b21a5ec4e27c` | cp1252 (bytes 0xD1) | `;` |
| octubre | migracion | `GEIH_2025/10_octubre/migracion.csv` | persona | 68.710 | 43 | `666446fc67f921d85647b5fce7caab758fa0bb52d1ee27d8a5abaadcb68c9ea0` | cp1252 (bytes 0xD1) | `;` |
| octubre | no_ocupados | `GEIH_2025/10_octubre/no_ocupados.csv` | persona | 24.278 | 37 | `a2c4718124270f20a5cd8c43a88b2d3e15bb760e90eba1af840012885a7e064a` | ASCII | `;` |
| octubre | ocupados | `GEIH_2025/10_octubre/ocupados.csv` | persona | 30.807 | 202 | `b3b303ee034553213fdb5a06c91dd856af425e631a2c6dc072ca61021ba7c624` | cp1252 (bytes 0xD1) | `;` |
| octubre | otras_formas_trabajo | `GEIH_2025/10_octubre/otras_formas_trabajo.csv` | persona | 55.085 | 112 | `a3515117e0748db3a5ed061a77b5a41146afa4ace8800223ec721ce5e32822b6` | ASCII | `;` |
| octubre | otros_ingresos | `GEIH_2025/10_octubre/otros_ingresos.csv` | persona | 55.085 | 59 | `c14247264380f6f1c2041985d5f3d892a11f230e7150f81b51b5cc7dbf5e7453` | cp1252 (bytes 0xD1) | `;` |
| noviembre | caracteristicas_generales | `GEIH_2025/11_noviembre/caracteristicas_generales.csv` | persona | 68.582 | 55 | `026302b97c1a54cae30b98d7575e51361e0237be2912b015e69c6e2491bc569b` | ASCII | `;` |
| noviembre | datos_hogar | `GEIH_2025/11_noviembre/datos_hogar.csv` | hogar | 24.724 | 49 | `94488a8ff3800b7e27351655d213efc4a15169d38a48cfe1d8236f31876d31bc` | ASCII | `;` |
| noviembre | fuerza_trabajo | `GEIH_2025/11_noviembre/fuerza_trabajo.csv` | persona | 55.008 | 42 | `9d887345e6a470ede58e22076a96c1da9b98ee552aa331e07d07911af1e16d9e` | cp1252 (bytes 0xD1) | `;` |
| noviembre | migracion | `GEIH_2025/11_noviembre/migracion.csv` | persona | 68.582 | 43 | `8fe3aeb9d529188e593db7ba3a4dd0873b184a04cb001ae6d34ec51d18284a53` | cp1252 (bytes 0xD1) | `;` |
| noviembre | no_ocupados | `GEIH_2025/11_noviembre/no_ocupados.csv` | persona | 24.069 | 37 | `b7c7f677fc098a7464bc97141fe0a342757e5b64b4bb7b12f220477d08038b7c` | ASCII | `;` |
| noviembre | ocupados | `GEIH_2025/11_noviembre/ocupados.csv` | persona | 30.939 | 202 | `0b07ee90b60b21770f45e6abb588258765c105ac93b86f234aa36aef2067aefc` | cp1252 (bytes 0xD1) | `;` |
| noviembre | otras_formas_trabajo | `GEIH_2025/11_noviembre/otras_formas_trabajo.csv` | persona | 55.008 | 112 | `9e5384129d672f2f90db84c83b7df7c3fff2ea212d1b2c71a732f5198ad37b37` | cp1252 (bytes 0xD1) | `;` |
| noviembre | otros_ingresos | `GEIH_2025/11_noviembre/otros_ingresos.csv` | persona | 55.008 | 59 | `d4e9dd9e5dae963768913ee1eafbaad2c04ae21bc283804a30d28701452c0540` | cp1252 (bytes 0xD1) | `;` |
| diciembre | caracteristicas_generales | `GEIH_2025/12_diciembre/caracteristicas_generales.csv` | persona | 66.559 | 55 | `8eb927c0a1f30c9bff84662a72bed980c87f39b709bf6ba27722f2160ca71ee4` | ASCII | `;` |
| diciembre | datos_hogar | `GEIH_2025/12_diciembre/datos_hogar.csv` | hogar | 24.159 | 49 | `18dce1f0fddcd3a4f80979c50a251dbebec0a6b08a490a303e105512a7cec543` | ASCII | `;` |
| diciembre | fuerza_trabajo | `GEIH_2025/12_diciembre/fuerza_trabajo.csv` | persona | 53.461 | 42 | `225d4e8d0e9b4f0da286db40b73e27745ecd7caea1f52c772bdf2709311c8503` | cp1252 (bytes 0xD1) | `;` |
| diciembre | migracion | `GEIH_2025/12_diciembre/migracion.csv` | persona | 66.559 | 43 | `77cf01ce7aec157b633ff02d30844b6623797d6851b702ac30556465518026ed` | cp1252 (bytes 0xD1) | `;` |
| diciembre | no_ocupados | `GEIH_2025/12_diciembre/no_ocupados.csv` | persona | 23.850 | 37 | `a5568a00bdc1bba3b385b92799d8ebeae2b4431cef804f94b96314798aa9d2c6` | ASCII | `;` |
| diciembre | ocupados | `GEIH_2025/12_diciembre/ocupados.csv` | persona | 29.611 | 202 | `0385c6fecf48ca30a3c59f86b37c898f713a5d324f0448327f21e670bb77c1d0` | cp1252 (bytes 0xD1) | `;` |
| diciembre | otras_formas_trabajo | `GEIH_2025/12_diciembre/otras_formas_trabajo.csv` | persona | 53.461 | 112 | `ec791fafc60db1cd43ad7e4dab748353927ed37b1819a8659f862dd57243fedf` | ASCII | `;` |
| diciembre | otros_ingresos | `GEIH_2025/12_diciembre/otros_ingresos.csv` | persona | 53.461 | 59 | `f27db66bfaa77d1d7af17e7357fe0a53dfd0894a6b0509a1b6ec50f4682ca74a` | cp1252 (bytes 0xD1) | `;` |


## 4. ENPH 2016-2017 — unidad de análisis y llaves (16 archivos)

**13 de los 16 archivos son registros de gasto: ninguno es una fila por hogar.**

**Llave de hogar en ENPH = `DIRECTORIO` (verificado).** En `viviendas_hogares` hay una fila por `DIRECTORIO` y `SECUENCIA_P` y `SECUENCIA_ENCUESTA` valen siempre 1; y todo `DIRECTORIO` de los 16 archivos existe en `viviendas_hogares` (columna «DIRECTORIO ⊂ hogares»). En las tablas de gasto `SECUENCIA_ENCUESTA`, `SECUENCIA_P` y `ORDEN` se comportan como **contadores de registro** (la columna «Llave mínima única» muestra cuáles bastan para identificar una fila), no identifican al hogar. El DDI no documenta qué identifica `ORDEN` en las tablas de gasto: **no asumir que es la persona**. Llave única de un registro de gasto: `DIRECTORIO + SECUENCIA_ENCUESTA + SECUENCIA_P`.

**Aviso sobre CLAUDE.md.** La regla de unión «`DIRECTORIO + SECUENCIA_P + HOGAR (+ORDEN)`» es de GEIH (ENPH no tiene columna `HOGAR`). Aplicada a ENPH, `DIRECTORIO + SECUENCIA_P` solo enlaza la fracción de filas de la columna «% filas que enlazan» con `viviendas_hogares`; el resto se perdería en silencio. Para ENPH se debe unir por `DIRECTORIO`, con conciencia de que es uno-a-muchos.

| Archivo | Unidad declarada | Filas | Hogares (`DIRECTORIO`) | Filas por hogar | DIRECTORIO ⊂ hogares | Llave mínima única | % filas que enlazan (DIR+SEC_P) | Verificación | Variable DDI que define la fila |
|---|---|---|---|---|---|---|---|---|---|
| `ENPH_2017/hogares/viviendas_hogares.csv` | una fila por hogar (vivienda y hogar) | 87.201 | 87.201 | 1,00 | sí | DIRECTORIO | 100,00 % | CONSISTENTE | — |
| `ENPH_2017/hogares/gastos_menos_frecuentes_medio_pago.csv` | una fila por hogar (medio de pago, cuadernillo 3) | 87.201 | 87.201 | 1,00 | sí | DIRECTORIO | 100,00 % | CONSISTENTE | — |
| `ENPH_2017/hogares/gastos_menos_frecuentes_articulos.txt` | registro de gasto: hogar × artículo o servicio (varias filas por hogar) | 2.111.331 | 87.193 | 24,21 | sí | DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P | 100,00 % | CONSISTENTE | `P10270` = «Nombre del artículo o servicio» |
| `ENPH_2017/personas/caracteristicas_generales_personas.csv` | una fila por persona | 291.590 | 87.201 | 3,34 | sí | DIRECTORIO+ORDEN | 100,00 % | CONSISTENTE | — |
| `ENPH_2017/urbano/gastos_diarios_hogar_comidas_fuera.csv` | registro de gasto: comida o alimento adquirido fuera del hogar (hogar) | 504.031 | 61.774 | 8,16 | sí | DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P | 7,16 % | CONSISTENTE | `NH_CGDUCFH_P1` = «Descripción de la comida o alimento adquirido» |
| `ENPH_2017/urbano/gastos_diarios_personales.csv` | registro de gasto personal diario: artículo o servicio (cuadernillo 4) | 524.948 | 58.528 | 8,97 | sí | DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P | 8,38 % | CONSISTENTE | `NC4_CC_P1_1` = «Nombre del artículo o servicio» |
| `ENPH_2017/urbano/gastos_diarios_capitulo_c.txt` | registro de gasto por alimento o grupo de alimentos (cuadernillo 2, cap. C) | 2.035.950 | 81.438 | 25,00 | sí | DIRECTORIO+ORDEN | 100,00 % | CONSISTENTE | `NC2_CC_P1` = «Alimentos o grupos de alimentos» |
| `ENPH_2017/urbano/gastos_diarios_mercados.csv` | registro de valor total de mercado no desagregado (cuadernillo 2) | 7.569 | 6.807 | 1,11 | sí | DIRECTORIO+ORDEN | 100,00 % | CONSISTENTE | `NC2_CC_P4S1` = «Valor total del mercado» |
| `ENPH_2017/urbano/gastos_diarios_hogar.txt` | registro de gasto diario urbano: una fila por artículo o servicio; mezcla gasto del hogar y personal (NH_CGDU_P10) | 3.393.520 | 79.794 | 42,53 | sí | DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P | 8,72 % | CONSISTENTE | `NH_CGDU_P1` = «Nombre del artículo o servicio» |
| `ENPH_2017/urbano/gastos_personales_comidas_fuera.csv` | registro de gasto personal: comida adquirida fuera del hogar | 475.963 | 53.641 | 8,87 | sí | DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P | 7,44 % | CONSISTENTE | `NH_CGPUCFH_P1` = «COMIDAS PREPARADAS FUERA DEL HOGAR. Descripción de la comida o alimento adquirido» |
| `ENPH_2017/rural/gastos_personales_comidas_fuera.csv` | registro de gasto personal rural: comida adquirida fuera del hogar | 6.248 | 5.763 | 1,08 | sí | DIRECTORIO+ORDEN | 100,00 % | CONSISTENTE | `NC2R_CA_P3` = «Nombre de artículo o servicio Descripción detallada de la comida» |
| `ENPH_2017/rural/gastos_personales.csv` | registro de gasto personal rural: artículo o servicio | 20.900 | 4.737 | 4,41 | sí | DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P | 26,07 % | CONSISTENTE | `NC2R_CE_P2` = «artículo o servicio» |
| `ENPH_2017/rural/gastos_semanales_capitulo_c.csv` | registro de gasto semanal por alimento o grupo (cuadernillo 2, cap. C) | 144.075 | 5.763 | 25,00 | sí | DIRECTORIO+ORDEN | 100,00 % | CONSISTENTE | `NC2_CC_P1` = «CARACTERISTICAS DEL GASTO EN ALIMENTOS DE LOS HOGARES 1. Alimentos o grupos de alimentos» |
| `ENPH_2017/rural/gastos_semanales_comidas_fuera.csv` | registro de gasto semanal: comida adquirida fuera del hogar | 11.439 | 4.741 | 2,41 | sí | DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P | 24,66 % | CONSISTENTE | `NH_CGPRCFH_P1` = «Descripción de la comida o alimento adquirido» |
| `ENPH_2017/rural/gastos_semanales_mercados.csv` | registro de valor total de mercado no desagregado (rural) | 754 | 672 | 1,12 | sí | DIRECTORIO+ORDEN | 100,00 % | CONSISTENTE | `NC2_CC_P4S1` = «Valor total del Mercado» |
| `ENPH_2017/rural/gastos_semanales.csv` | registro de gasto semanal rural: artículo o servicio | 241.067 | 5.763 | 41,83 | sí | DIRECTORIO+SECUENCIA_ENCUESTA+SECUENCIA_P | 100,00 % | CONSISTENTE | `NC2R_CA_P3` = «Nombre de artículo o servicio» |

**Factor de expansión ENPH.** Los 16 archivos traen `FEX_C`. CLAUDE.md exige documentar cuál factor se usa en cada análisis.


**`FEX_C` (ENPH): VERIFICADO como factor del hogar/vivienda.** Fuente documental: `Metodologia_ENPH.pdf`, §2.2.4.1 (Procedimiento de estimación): la calibración se hace «a nivel de vivienda» y «a la vivienda corresponde un único factor de expansión». Contraste empírico (`tools/verificar_fex_enph.py`, `outputs/fex_enph_verificacion.json`): en cada tabla `FEX_C` debe ser constante dentro de `DIRECTORIO` e igual al de `viviendas_hogares`. Se verificaron las tablas de hogares, personas y urbano (**rural fuera de alcance, no verificado**).

| Archivo | Filas | DIRECTORIO distintos | DIRECTORIO con FEX_C no constante | % filas con FEX_C = el de hogares |
|---|---|---|---|---|
| `hogares/viviendas_hogares.csv` | 87.201 | 87.201 | 0 | 100,00 % |
| `hogares/gastos_menos_frecuentes_medio_pago.csv` | 87.201 | 87.201 | 0 | 100,00 % |
| `hogares/gastos_menos_frecuentes_articulos.txt` | 2.111.331 | 87.193 | 0 | 100,00 % |
| `personas/caracteristicas_generales_personas.csv` | 291.590 | 87.201 | 0 | 100,00 % |
| `urbano/gastos_diarios_hogar_comidas_fuera.csv` | 504.031 | 61.774 | 0 | 100,00 % |
| `urbano/gastos_diarios_personales.csv` | 524.948 | 58.528 | 0 | 100,00 % |
| `urbano/gastos_diarios_capitulo_c.txt` | 2.035.950 | 81.438 | 0 | 100,00 % |
| `urbano/gastos_diarios_mercados.csv` | 7.569 | 6.807 | 0 | 100,00 % |
| `urbano/gastos_diarios_hogar.txt` | 3.393.520 | 79.794 | 0 | 100,00 % |
| `urbano/gastos_personales_comidas_fuera.csv` | 475.963 | 53.641 | 0 | 100,00 % |

**Alcance del resultado.** `FEX_C` es un factor de hogar: sirve para estimar por hogar (una fila por hogar) y para personas (el factor del hogar se aplica a cada miembro). En tablas de registros de gasto, cada fila lleva el factor de su hogar: para cifras por hogar hay que agregar primero a hogar; ponderar filas de gasto sueltas no da un total de gasto sin ese paso. No se verificó contra un total poblacional externo.

| Archivo | Zip origen | Filas | Cols | SHA-256 | Encoding detectado | Carga | Sep |
|---|---|---|---|---|---|---|---|
| `ENPH_2017/hogares/viviendas_hogares.csv` | `Viviendas y hogares.zip` | 87.201 | 105 | `0ea7fed8f37c1358e3dc4f64e45bfc2f1a09c3264907f53b285d094d50fe9dba` | UTF-8 con BOM (con acentos) | `utf-8-sig` | `;` |
| `ENPH_2017/hogares/gastos_menos_frecuentes_medio_pago.csv` | `Gastos menos frecuentes - Medio de pago.zip` | 87.201 | 134 | `419d8a01418c8a43fbb513bf101caa6da405088eee7445e40f02606f50456b86` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |
| `ENPH_2017/hogares/gastos_menos_frecuentes_articulos.txt` | `Gastos menos frecuentes - Articulos.zip` | 2.111.331 | 12 | `f6ec098201f22ea2ba35afc65c5faddfcfb7032e09644cbad20b2b1365f63400` | ASCII | `utf-8` | tab |
| `ENPH_2017/personas/caracteristicas_generales_personas.csv` | `Caracteristicas generales personas.zip` | 291.590 | 263 | `f606087298d77884e660fa951d12199dd8c71f87649cb3c4996a4f0f85b5eaf2` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |
| `ENPH_2017/urbano/gastos_diarios_hogar_comidas_fuera.csv` | `Gastos diarios del hogar Urbano - Comidas preparadas fuera del hogar.zip` | 504.031 | 15 | `f5463d5a31b8dc850b7e9da5d5f1e56de0f5d54604eb65d07080a5a98d0f3442` | UTF-8 con BOM (con acentos) | `utf-8-sig` | `;` |
| `ENPH_2017/urbano/gastos_diarios_personales.csv` | `Gastos diarios personales Urbano.zip` | 524.948 | 11 | `fc478e76893328fc166ae8dc4ab2719519a05e63d70e2ebea33e7fd2e7fb6181` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |
| `ENPH_2017/urbano/gastos_diarios_capitulo_c.txt` | `Gastos diarios Urbano - Capitulo C.zip` | 2.035.950 | 9 | `d8e8dcb2ff8559db0ed9b914723889a2de3a8efa6bf5e32ae53bee5bbee9d4e7` | ASCII | `utf-8` | tab |
| `ENPH_2017/urbano/gastos_diarios_mercados.csv` | `Gastos diarios Urbanos - Mercados.zip` | 7.569 | 7 | `6ccb91f4e961774909cf64fc578519a2aee6d903eb713f23953d4d52c92eff6c` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |
| `ENPH_2017/urbano/gastos_diarios_hogar.txt` | `Gastos diarios Urbanos.zip` | 3.393.520 | 17 | `93ef359a15210c84ae3e763ccd1db3ed77916d16296eaa7c8281d6790e5317ed` | ASCII | `utf-8` | tab |
| `ENPH_2017/urbano/gastos_personales_comidas_fuera.csv` | `Gastos personales Urbano - Comidas preparadas fuera del hogar.zip` | 475.963 | 14 | `805e6f2b7dc3b14d14088c4a3c5700c85dcc02e50fa2ab13e86f9c1d682232f9` | UTF-8 con BOM (con acentos) | `utf-8-sig` | `;` |
| `ENPH_2017/rural/gastos_personales_comidas_fuera.csv` | `Gastos personales Rural - Comidas preparadas fuera del Hogar.zip` | 6.248 | 13 | `aee41c96a86d4e39f430f78ae2c2afe277e1c9cc296177b9759324d412626ea5` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |
| `ENPH_2017/rural/gastos_personales.csv` | `Gastos personales Rural.zip` | 20.900 | 13 | `36cc580771a47b63b6e3bfbb158892d18d8311bc4a44527f88a8b43b5d83ffe3` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |
| `ENPH_2017/rural/gastos_semanales_capitulo_c.csv` | `Gastos semanales Rural - Capitulo C.zip` | 144.075 | 9 | `14d3ba7f649d98d2f1de73d3d4b35035d398b973d6ba4e107b21dd40189ea4cc` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |
| `ENPH_2017/rural/gastos_semanales_comidas_fuera.csv` | `Gastos semanales Rural - Comidas preparadas fuera del hogar.zip` | 11.439 | 16 | `9216baeeaa8773aa4c636f01c3c1a644122239d26c10ac74127524e4c1bdf78a` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |
| `ENPH_2017/rural/gastos_semanales_mercados.csv` | `Gastos semanales Rurales - Mercados.zip` | 754 | 7 | `69a7ce9303a4436e449907eb4d41a7ee14460304f890d395544ae505478d2138` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |
| `ENPH_2017/rural/gastos_semanales.csv` | `Gastos semanales Rurales.zip` | 241.067 | 16 | `508a0e56ce1cda0072fd6cbce73e6ee225073a3f906a001a6a0342f65a8b257c` | UTF-8 con BOM (solo ASCII) | `utf-8-sig` | `;` |


## 5. Procedencia de `urbano/gastos_diarios_hogar.txt`

- **Declarado por Sara Cárdenas (2026-09-20):** es una descarga fresca del DANE del 20 sep 2026 y reemplaza la copia anterior, sobre la que existía una sospecha de truncamiento. Esa declaración no se puede verificar desde los archivos; lo que sí se midió:

| Evidencia | Valor |
|---|---|
| Zip origen | `Gastos diarios Urbanos.zip` (103.563.556 B) |
| SHA-256 del zip | `afd23b384110a674129028868def32ab5374da4e936f04315957a12ec292c0a9` |
| Fecha de modificación del zip en `_descargas/` | 2026-09-20T02:53:45 |
| Fecha interna del `.txt` dentro del zip | 2018-08-02 14:57 |
| SHA-256 del `.txt` | `93ef359a15210c84ae3e763ccd1db3ed77916d16296eaa7c8281d6790e5317ed` |
| **Filas (cifra de referencia)** | **3.393.520** filas × 17 columnas |
| Prueba CRC del zip (`testzip`) | OK |
| Filas × columnas del `.sav` del mismo zip | 3.393.520 × 17 (coincide con el `.txt`) |
| Filas con nº de campos distinto al encabezado | 0 |
| El archivo termina en salto de línea | sí |

**Alcance.** La cifra es de *autoconsistencia* (CRC del zip, `.txt` = `.sav`, sin filas cortadas, cierre limpio). No existe una cifra oficial contra la cual cotejarla: el DDI declara `caseQnty` = 0 (marcador vacío). Un truncamiento que afecte igual al `.txt` y al `.sav` de un mismo zip no se detectaría con estas pruebas. No se conserva la copia anterior, así que no se puede comparar contra ella. La fecha interna del `.txt` es la de creación por el DANE, no la de descarga; la fecha de descarga solo se apoya en la de modificación del zip.

## 6. `P7510` y `P7513` en ENPH

Viven en **`ENPH_2017/personas/caracteristicas_generales_personas.csv`** (Caracteristicas generales personas, cuadernillo 1). **No** están en `hogares/viviendas_hogares.csv` (P7510: 0 columnas; P7513: 0) ni en ningún otro archivo ENPH.

No existen columnas llamadas exactamente `P7510` o `P7513`: son familias con sufijos. `P7510*`: 16 columnas; `P7513*`: 25. Etiqueta DDI de ejemplo: `P7510S1` = «Durante los últimos doce meses recibió: a. Dinero de otros hogares o personas residentes en el país?»; `P7513S1` = «Durante los últimos 12 meses recibió ingresos ocasionales por: a. Ventas de casas, apartamentos fincas, lotes, terrenos?». Los sufijos `S#` son ítems (a, b, c…) y `S#A1` su valor. Unidad: persona, con referencia de 12 meses.

## 7. Control de cambios del formulario GEIH (comparabilidad semántica)

Fuente: `GEIH_2025/_metadatos/CONTROL DE CAMBIOS FORMULARIO GEIH.xlsx`. Su instructivo dice cubrir «desde el año 2022 hasta el 2024».

| Año | Trimestre | Etapas | Cambios | Por tipo |
|---|---|---|---|---|
| 2022 | I | 2201 - 2202 - 2203 | 109 | O: 8, EP: 21, IC: 3, IP: 60, IA: 7, EA: 7, EC: 4 |
| 2022 | II | 2204 - 2205 - 2206 | 3 | O: 2, IC: 1 |
| 2022 | III | 2207 - 2208 - 2209 | 2 | O: 1, EC: 1 |
| 2022 | IV | 2210 - 2211 - 2212 | 4 | O: 1, IP: 2, IC: 1 |
| 2023 | N/A | 2301 - 2312 | 9 | O: 4, IP: 2, IC: 1, EA: 1, IA: 1 |
| 2024 | N/A | 2401 - 2412 | 2 | O: 2 |

Tipos: IC/EC = ingresa/elimina capítulo; IP/EP = pregunta; IA/EA = alternativa de respuesta; O = otro.

**Conclusión: PENDIENTE — no hay evidencia sobre 2025.**

- Entradas de 2025 en el control de cambios: **ninguna**. El último bloque es 2024 (etapas 2401 - 2412).
- El `FORMULARIO_GEIH.pdf` de `_metadatos/` es de las etapas 2401–2412 (Enero - Diciembre 2024), es decir, **2024**, no 2025.
- Solo el Manual de Recolección es de 2025. Busqué en su texto («novedad», «cambios al formulario», «modificación», «versión», «respecto a 2024», «a partir de») y no trae un listado de cambios frente a 2024.
- Por tanto **no se puede afirmar que el formulario no cambió durante 2025**, ni que sí. Riesgo: cambios de redacción, alternativas de respuesta o definiciones (que no alteran el nombre de la columna) podrían afectar el apilamiento de los 12 meses, sobre todo en `ocupados`, `fuerza_trabajo` y `otros_ingresos`.
- Para cerrarlo hace falta el control de cambios o el formulario de las etapas 2501–2512 (o confirmación del DANE). Mientras tanto, tratar cualquier variable de opinión/definición como no verificada entre meses.

## 8. Diciembre 2025 tiene menos filas

Diciembre: 66.559 personas (mediana de los otros 11 meses: 68.263, razón 0,975) y 24.159 hogares (mediana 24.401, razón 0,990). La diferencia es de 1.704 personas y 242 hogares.

| Módulo | Diciembre = mes con menos filas | Posición desde abajo | Meses con menos filas que diciembre |
|---|---|---|---|
| caracteristicas_generales | sí | 1 | — |
| datos_hogar | no | 2 | enero |
| fuerza_trabajo | sí | 1 | — |
| migracion | sí | 1 | — |
| no_ocupados | sí | 1 | — |
| ocupados | no | 5 | enero, febrero, marzo, abril |
| otras_formas_trabajo | sí | 1 | — |
| otros_ingresos | sí | 1 | — |

Es decir, **«proporcional en todos los módulos» no se sostiene del todo**: diciembre es el mínimo solo en los módulos donde la tabla dice «sí».

**Dónde está la diferencia**

| CLASE (DANE) | Personas dic | Media otros | Mín. otros | Hogares dic | Media otros | Mín. otros |
|---|---|---|---|---|---|---|
| 1 | 57.908 | 59.518 | 59.094 | 21.037 | 21.332 | 21.020 |
| 2 | 8.651 | 8.754 | 8.622 | 3.122 | 3.103 | 3.056 |

- Personas por hogar en diciembre: 2,755 (mediana otros: 2,788); es el valor más bajo del año. El mes con menos hogares es **enero**, no diciembre.
- Departamentos por debajo de su propio mínimo de los otros meses: 9 de 33 (personas); 7 de 33 (hogares). Diferencia difusa, sin un solo departamento que la explique.
- Semanas de recolección: diciembre tiene 4 (`PERIODO` 49–52). Filas de la última semana: 28.337 (otros meses de 4 semanas: 28.812–29.333). No falta una semana completa.
- Suma de `FEX_C18` (personas), millones: diciembre 52,296; crece cada mes: sí. Los factores compensan el menor n, así que los totales expandidos no caen; sí aumenta la varianza.
- Diseño (Metodología general §2.2.11): «en promedio se espera encuestar mensualmente 18.500 hogares en las 32 ciudades capitales … y 6.970 en el resto» = 25.470 (la frase está cortada en el propio PDF). Observado: 24.109–24.774 hogares por mes, **todos los meses** por debajo de esa media.

**Conclusión: PENDIENTE — no se puede calificar ni de «esperado por diseño» ni de anomalía.**

- Búsqueda manual con `pdftotext` (no automatizada en este script): en la Metodología general busqué diciembre, festivos, vacaciones, temporada, rotación y muestra mensual/trimestral; en la Ficha metodológica y el Manual de Recolección 2025, diciembre, festivos, vacaciones y temporada. No encontré ninguna referencia a un tamaño de muestra distinto para diciembre (las menciones a diciembre son históricas o de encabezado). El texto disponible da una media mensual, sin decir si varía por mes; y la frase clave está cortada en el PDF, así que la ausencia de una regla mensual no está demostrada.
- Lo observado es pequeño (-2,5 % en personas, -1,0 % en hogares), más marcado en cabeceras (CLASE 1) y con menor tamaño de hogar; no falta ninguna semana ni un departamento. Podría ser variación de cobertura o de respuesta en época de fin de año, pero **eso es una hipótesis, no algo que los datos o la documentación confirmen**.
- Para cerrarlo: la tasa de respuesta/cobertura de diciembre 2025 en el boletín técnico del DANE, o una consulta al DANE. Impacto práctico: con `FEX_C18 / 12` los totales no se distorsionan; se recomienda una prueba de sensibilidad excluyendo diciembre antes de fijar priors definitivos.

## 9. Metadatos y etiquetas (integridad)

`_etiquetas/` contiene los `.SAV` de **enero** (única fuente de etiquetas de valor para GEIH; no se verificó que las etiquetas sean iguales en los otros 11 meses).

| Ruta | Bytes | SHA-256 |
|---|---|---|
| `GEIH_2025/_etiquetas/Características generales, seguridad social en salud y educación.SAV` | 192.728.874 | `d299f86c9093786d5ab74d579e7922917e1e7a5ee71aba0e701723dfb3cf7019` |
| `GEIH_2025/_etiquetas/Datos del hogar y la vivienda.SAV` | 58.067.456 | `b99b3ab2f70bbe462248725f0ce7e14fe234355c06ef726e7ccbee16c9660d0a` |
| `GEIH_2025/_etiquetas/Fuerza de trabajo.SAV` | 236.198.292 | `239aec8e28025cb51b2f88cd2c02c16423f57e9f9b8e8a390a40ef58e221ec20` |
| `GEIH_2025/_etiquetas/Migración.SAV` | 93.922.416 | `8f6bc20e4306e2d683564d4535baa1d25a32591cbc0b5494e49dc3eadf8e267b` |
| `GEIH_2025/_etiquetas/No ocupados.SAV` | 33.589.555 | `98b89eb221cbaeb2e879a5021f63c9a289adba86a9dbd763935ab7f0793fdaec` |
| `GEIH_2025/_etiquetas/Ocupados.SAV` | 1.016.399.036 | `7434692840fd5e28374eba9b325d217d461e24147bddeef369b544d9973ca593` |
| `GEIH_2025/_etiquetas/Otras formas de trabajo.SAV` | 211.977.655 | `d985a4a88b5a53687e74e5a97453ebe0c92b70fe097431d8d958d0d430311213` |
| `GEIH_2025/_etiquetas/Otros ingresos e impuestos.SAV` | 80.033.553 | `387afd69b95b0a37f844946000d82280bfa4e0d749966557e367ae90217e9bc5` |
| `GEIH_2025/_metadatos/CONTROL DE CAMBIOS FORMULARIO GEIH.xlsx` | 114.314 | `d026d9387868bd25a2b067646de33ead19ac6b97922070bdcfc108e876356cbb` |
| `GEIH_2025/_metadatos/CONTROL DE CAMBIOS FORMULARIO GEIH.zip` | 106.733 | `6d8b74bf8e3e59f1bd70ff6037f1077aefdbc47e026da27740a1552227833b8e` |
| `GEIH_2025/_metadatos/DANE-DIMPE-GEIH-2025.json` | 111.279 | `5145d1748cb1efc2348dcbce8039c4ca06f7b7cf910a3f0d3a0fd7334867b61a` |
| `GEIH_2025/_metadatos/DANE-DIMPE-GEIH-2025.xml` | 1.912.958 | `a09d981f434ffa8bc215240c43947bed1485622521d1edde378d6b591b3af67b` |
| `GEIH_2025/_metadatos/Diccionario de datos - GEIH 2025.xlsx` | 354.910 | `563fec4cdaf39c2a5067e55bd218368da4418fe71ddcd5c2e980e32f3d61823a` |
| `GEIH_2025/_metadatos/FICHA METODOLÓGICA GRAN ENCUESTA INTEGRADA DE HOGARES.pdf` | 384.362 | `db23ab3d00050a2b2e61b7e9979ed496b178a108676433173d15426f65930b4a` |
| `GEIH_2025/_metadatos/FORMULARIO_GEIH.pdf` | 1.292.281 | `4d31a3575e564b74b7176e92b0c1df21d964ecc148536c3d7239030081f6d0cc` |
| `GEIH_2025/_metadatos/ManualRecoleccion-GEIH-2025.pdf` | 2.472.491 | `32fa17c70bad5a0fe8423a6eb51504f43db114dba2c9c7d9ec78d966b430fc6f` |
| `GEIH_2025/_metadatos/METODOLOGÍA GENERAL GRAN ENCUESTA INTEGRADA DE HOGARES GEIH.pdf` | 1.738.551 | `179837eaf693cdc2283464b89c2107cd4da26a46278c14ce65b663dcd9342c23` |
| `ENPH_2017/_metadatos/boletin-enph-2017.pdf` | 343.045 | `d5ef612ac6eebc47ae40fd632d966acb1b4a5de4763a70b03ece02e1c3333e0c` |
| `ENPH_2017/_metadatos/CUADERNILLOS/Cuadernillo 1.pdf` | 2.432.506 | `694aea1caeb7b8ccece983df5e17de407ce128a6a5fadcc74f88043f21e39093` |
| `ENPH_2017/_metadatos/CUADERNILLOS/Cuadernillo 2 rural.pdf` | 870.722 | `517def3b4b84a2ad382f6078d71dc1cc6bcdf5594a021c5ac97bfa5ed7343bb3` |
| `ENPH_2017/_metadatos/CUADERNILLOS/Cuadernillo 2 urbano.pdf` | 611.928 | `719f53a0b69ddcddcff21ffe6d8c4e549ce614f8e63f3e81d966ced61e038d92` |
| `ENPH_2017/_metadatos/CUADERNILLOS/Cuadernillo 3.pdf` | 2.834.548 | `01ab79c3c404fc4f84602bdb01aad7f4bb54baab2416078b23bbe7a123e49162` |
| `ENPH_2017/_metadatos/CUADERNILLOS/Cuadernillo 4.pdf` | 1.268.143 | `a541592c38ae8f7ad6ab7ce6c4a9cd271b781e852a90919b05a06b40eedd7796` |
| `ENPH_2017/_metadatos/DANE-DIMPE-ENPH-2016-2017.json` | 41.836 | `2d639b76a637e099f685612af55b219d9ca2fe112a57a083bf72591eea475cbb` |
| `ENPH_2017/_metadatos/DANE-DIMPE-ENPH-2016-2017.xml` | 1.270.052 | `6ec12d0f54232145256d4695b5553c1bd4169351761784cf5dd7c8856915a009` |
| `ENPH_2017/_metadatos/Encuesta Nacional de Presupuestos de los Hogares - ENPH.pdf` | 885.874 | `1569c54f7e1d237196ae315491f3c5117aa99dee9f2134c37253d118800e2aff` |
| `ENPH_2017/_metadatos/Ficha_metodologica_ENPH.pdf` | 580.256 | `e04c00c249d9de959013efc3b23bbd4aba0a9e4fa8920604889083c1c3473de3` |
| `ENPH_2017/_metadatos/MANUAL_ENPH.pdf` | 4.794.339 | `7b32810c03418df2369705d49032de23da0e1f1da16fcf7067346e3b5062d0db` |
| `ENPH_2017/_metadatos/Metodologia_ENPH.pdf` | 2.763.605 | `ddcdaae8cfc6d0ea06cef514d4d51c9380347173fb17efb87715c4081789e559` |

## 10. Verificaciones previas: Bogotá

Las tres se hicieron antes de escribir código de análisis. Los códigos se leen de las fuentes (no se escriben a mano).

### 10.1 ¿Qué variable identifica a Bogotá?

| Base | Variable | Valor de Bogotá | Fuente (cita) | Estado |
|---|---|---|---|---|
| GEIH 2025 | `AREA` (identificador de área metropolitana / ciudad) | `11` | Diccionario de datos GEIH 2025, hoja «Plantilla Diccionario de Datos», fila 169: «11 | BOGOTA» (se repite en 8 tablas del diccionario). DDI GEIH: «11 Bogotá DC». | CONCORDANTE |
| GEIH 2025 | `DPTO` (identificador de departamento) | `11` | Diccionario, fila 112: «11 | BOGOTA» (9 tablas). DDI GEIH: «11 Bogotá DC». | CONCORDANTE |
| ENPH 2016-2017 | `DOMINIO` (en `viviendas_hogares.csv`) | texto `BOGOTÁ` | No existe código numérico: en el CSV y en el `.sav` el valor es texto y el DDI no lista categorías. Respaldo: la lista de «dominios de estudio: 32 ciudades de departamento» del DDI menciona Bogotá. | TEXTO, sin código |
| ENPH 2016-2017 | `REGION` (idéntico a `DOMINIO` para Bogotá) | texto `BOGOTÁ` | El DDI lista las regiones en el texto de la pregunta («…BOGOTÁ…»). `REGION` y `DOMINIO` seleccionan exactamente los mismos hogares. | TEXTO, sin código |

**Lo que NO pude confirmar.** Los 5 cuadernillos de ENPH mencionan «Bogotá» 0 veces (son formularios en blanco, sin listas de códigos de dominio), así que no sirven de respaldo para ese valor. Los `.SAV` de enero de GEIH traen 0 etiquetas de valor para `AREA`, 0 para `DPTO` y 0 para `CLASE`; la fuente de los códigos de GEIH es el diccionario (y el DDI), no el SAV.

**Precisión en GEIH: `AREA` y `DPTO` no son lo mismo.**

- `AREA == '11'` es siempre un subconjunto de `DPTO == '11'` (hogares con `AREA` de Bogotá fuera de `DPTO` de Bogotá: 0). `DPTO == '11'` agrega 237 hogares en los 12 meses (rurales, `CLASE` de resto, con `AREA` vacía).
- Para comparar con **ENPH urbano** (todo Bogotá en ENPH es «Cabeceras»: `P3` = 1: 3.918) el equivalente es `AREA == '11'`. `DPTO == '11'` incluye la zona rural de Bogotá D.C.
- `CLASE` está etiquetada distinto según la fuente: diccionario «1 Cabecera; 2 Resto» vs. DDI «1 Urbano; 2 Rural». No usar la etiqueta para filtrar; usar los códigos.
- El diccionario de GEIH tiene todos sus códigos de tabla en la etapa **2401** (2024): es la misma versión 2024 del formulario, otro indicio del pendiente de comparabilidad semántica de §7.

### 10.2 Tamaño de la submuestra de Bogotá (sin ponderar)

Son tamaños muestrales (observaciones), no poblaciones expandidas.

| ENPH 2016-2017 | Bogotá | Total ENPH | % del total |
|---|---|---|---|
| Hogares (`viviendas_hogares`, `DOMINIO`) | 3.918 | 87.201 | 4,5 % |
| Personas (`caracteristicas_generales_personas`, por `DIRECTORIO`) | 12.279 | 291.590 | 4,2 % |

| Mes | Hogares `AREA=11` | Ocupados `AREA=11` | Hogares `DPTO=11` | Ocupados `DPTO=11` |
|---|---|---|---|---|
| enero | 797 | 1.083 | 818 | 1.113 |
| febrero | 822 | 1.160 | 845 | 1.188 |
| marzo | 793 | 1.118 | 810 | 1.139 |
| abril | 805 | 1.096 | 822 | 1.119 |
| mayo | 795 | 1.097 | 815 | 1.126 |
| junio | 796 | 1.116 | 816 | 1.142 |
| julio | 808 | 1.161 | 828 | 1.194 |
| agosto | 811 | 1.090 | 831 | 1.111 |
| septiembre | 839 | 1.126 | 859 | 1.149 |
| octubre | 811 | 1.162 | 831 | 1.188 |
| noviembre | 849 | 1.196 | 870 | 1.222 |
| diciembre | 807 | 1.147 | 825 | 1.175 |
| **12 meses** | **9.733** | **13.552** | **9.970** | **13.866** |
| mín–máx mensual | 793–849 | 1.083–1.196 | 810–870 | 1.111–1.222 |

*Ocupados* = filas de `ocupados.csv` (personas ocupadas). Los meses no son muestras independientes de hogares distintos: hay rotación de segmentos, y este documento no verificó cuántos hogares se repiten entre meses.

### 10.3 Cruce estrato × quintil de ingreso (solo Bogotá)

Los cuantiles se calculan **ponderados por el factor de expansión** dentro de Bogotá; los conteos de celda son **observaciones sin ponderar**. Los empates de ingreso quedan en el mismo quintil, por lo que los quintiles no son exactamente del 20 % (ver «% de peso»). **Se hicieron dos cruces porque la pregunta no decía cuál fuente; son unidades distintas y no comparables entre sí.** Celda «pequeña» = menos de 30 observaciones (en negrita).

**A) ENPH — hogares de Bogotá** (unidad: hogar/unidad de gasto). Estrato: `P8520S1A1` («¿Con cuáles de los siguientes servicios cuenta la vivienda? a. Energía eléctrica Estrato para tarifa:»). Ingreso: `ICGU` («Ingreso Corriente de la Unidad de Gasto»), ponderado con `FEX_C`. 3.899 de 3.918 hogares entran al cruce (excluidos por estrato fuera de 1–6 o vacío: 19; hogares con `ICGU` = 0 incluidos: 31).

| Estrato \ Quintil | Q1 | Q2 | Q3 | Q4 | Q5 | Total |
|---|---|---|---|---|---|---|
| 1 | 248 | 170 | 158 | 79 | **21** | 676 |
| 2 | 405 | 402 | 362 | 303 | 108 | 1580 |
| 3 | 172 | 215 | 253 | 312 | 258 | 1210 |
| 4 | **16** | **21** | **14** | 44 | 122 | 217 |
| 5 | **5** | **2** | **12** | **17** | 94 | 130 |
| 6 | **4** | **3** | **1** | **4** | 74 | 86 |

**Celdas con menos de 30 observaciones: 12 de 30** (vacías: 0; mínimo: 1). Cortes del quintil (ICGU, COP): 1.127.000, 1.810.250, 2.766.667, 4.506.283. % de peso por quintil: 20,0, 19,9, 20,1, 20,1, 20,0.
Sensibilidad a la variable de ingreso (celdas < 30): `ICGU` 12 de 30; `IT` 12 de 30; `ICMUG` 11 de 30; `ICMDUG` 11 de 30.

**B) GEIH — ocupados de Bogotá (`AREA=11`), 12 meses apilados** (unidad: persona ocupada; pesos `FEX_C18/12`). Estrato: `P4030S1A1` del hogar («0 Conexión pirata; 1 Bajo - bajo; 2 Bajo…», DDI GEIH). Ingreso: `INGLABO` (ingresos laborales de la persona, **no** ingreso del hogar). 13.081 de 13.552 ocupados entran (sin estrato válido: 29; sin ingreso: 442; con ingreso 0 incluidos: 45).

| Estrato \ Quintil | Q1 | Q2 | Q3 | Q4 | Q5 | Total |
|---|---|---|---|---|---|---|
| 1 | 431 | 348 | 229 | 110 | **25** | 1143 |
| 2 | 1546 | 1496 | 1371 | 775 | 269 | 5457 |
| 3 | 938 | 773 | 953 | 1018 | 833 | 4515 |
| 4 | 78 | 67 | 123 | 249 | 782 | 1299 |
| 5 | **18** | **21** | **25** | 57 | 290 | 411 |
| 6 | **6** | **9** | **21** | **19** | 201 | 256 |

**Celdas con menos de 30 observaciones: 8 de 30** (vacías: 0; mínimo: 6). Si se usara **un solo mes** (cruce mensual): entre 16 y 20 de 30 celdas con menos de 30 (mediana 18).

**Decisiones mías que conviene que confirmes:** (1) quintiles calculados dentro de Bogotá, no sobre el total nacional; (2) ingreso del hogar completo (`ICGU`) en ENPH pero solo ingreso laboral individual en GEIH, porque en los 8 módulos GEIH no construí un ingreso del hogar; (3) estratos válidos = 1 a 6 (se excluyen `0`, `9` y vacío, que no son estratos). **Códigos de estrato VERIFICADOS (20 sep 2026):** ENPH `P8520S1A1` según MANUAL_ENPH.pdf, Pregunta 4, «Estrato para tarifa» (códigos 1-6; 0 = conexión pirata; 9 = no establecible o planta eléctrica) (el DDI trae 0 categorías y el Cuadernillo 1 solo dice «Estrato para tarifa»: no son fuente de códigos); GEIH `P4030S1A1` según Diccionario GEIH 2025, fila 32 (P4030S1A1; rango 0-6 ó 9; sin etiquetas para 0 y 9). Cada esquema se mapea solo con su fuente.

**Cortes de quintil:** se calculan sobre TODOS los hogares (u ocupados) con ingreso, con la misma función y regla que `tools/distribuciones_priors.py` (`sdg.pesos.cortes_ponderados`: menor valor con F ponderada ≥ j/5); después se cruza con el estrato válido. Los conteos de celda de este apartado coinciden con `outputs/distribuciones/enph_estrato_x_quintil.csv` (ENPH, estrato agrupado).

**C) ENPH — estrato agrupado en 3 (1-2, 3-4, 5-6) × 5 quintiles de `ICGU`.** Los conteos de celda son observaciones **sin ponderar**. Los cortes de quintil se calcularon con `FEX_C` (regla de CLAUDE.md); como sensibilidad se reporta también el resultado con cortes **sin ponderar**. Los quintiles se calculan dentro de cada población (Bogotá; urbano nacional).

*Bogotá* — 3.899 de 3.918 hogares entran al cruce (estrato fuera de 1–6 o vacío: 19).

| Estrato \ Quintil | Q1 | Q2 | Q3 | Q4 | Q5 | Total |
|---|---|---|---|---|---|---|
| 1-2 | 653 | 572 | 520 | 382 | 129 | 2256 |
| 3-4 | 188 | 236 | 267 | 356 | 380 | 1427 |
| 5-6 | **9** | **5** | **13** | **21** | 168 | 216 |

**Celdas con menos de 30 observaciones: 4 de 15** con cortes ponderados (mínimo 5); con cortes sin ponderar: 4 de 15 (mínimo 5).

*Urbano nacional (P3=1, incluye Bogotá)* — 80.725 de 81.438 hogares entran al cruce (estrato fuera de 1–6 o vacío: 713).

| Estrato \ Quintil | Q1 | Q2 | Q3 | Q4 | Q5 | Total |
|---|---|---|---|---|---|---|
| 1-2 | 14186 | 13543 | 12546 | 10134 | 6313 | 56722 |
| 3-4 | 2334 | 2900 | 4099 | 5254 | 7283 | 21870 |
| 5-6 | 71 | 76 | 140 | 244 | 1602 | 2133 |

**Celdas con menos de 30 observaciones: 0 de 15** con cortes ponderados (mínimo 71); con cortes sin ponderar: 0 de 15 (mínimo 67).

### 10.4 Prefijo `NC2R_` y la variable `NC2R_CC_P6`

**Respuesta corta: no está confirmado que `NC2R_` signifique «cuadernillo 2 rural», y para `NC2R_CC_P6` los datos lo contradicen.**

- **Dónde vive:** `ENPH_2017/hogares/viviendas_hogares.csv` (tabla DDI «Viviendas y hogares»), **no** en un archivo rural de gasto. Un hogar por fila.
- **Etiqueta exacta (DDI):** «La principal forma de pago usada para comprar los bienes mencionados en este cuadernillo fue:». Categorías: 1 Tarjeta Débito; 2 Tarjeta de Crédito; 3 Efectivo; 4 Fiador; 5 Bonos; 6 Otro.
- **Pregunta en los cuadernillos:** Cuadernillo 2 rural: «La principal forma de pago usada para comprar o adquirir los bienes mencionados en este cuadernillo fue:» | Cuadernillo 2 urbano: «La principal forma de pago usada para comprar los bienes mencionados en este cuadernillo fue:». La etiqueta del DDI coincide con la redacción del cuadernillo **urbano** («comprar los bienes…»), no con la del rural («comprar o adquirir los bienes…»).
- **A quién se le aplicó (datos):** viene rellena en 61.930 de 81.438 hogares urbanos (`P3`=1) y en 3.517 de 3.918 hogares de Bogotá; por clase: `P3`=1: 61.930/81.438; `P3`=2: 1.327/3.005; `P3`=3: 1.736/2.758. Es decir, **no es exclusiva de hogares rurales**.
- **Documentación del prefijo:** 65 menciones de «NC2R» en 10 PDFs de ENPH (listado de variables), pero 0 definiciones del prefijo. No está documentado.
- **Evidencia a favor de «rural»:** las demás familias `NC2R_*` (`NC2R_CA`, `NC2R_CE`, `NC2R_CE1`, `NC2R_CJ`) viven en archivos rurales de gasto (`gastos_personales_comidas_fuera.csv`, `gastos_personales.csv`, `gastos_semanales_comidas_fuera.csv`, `gastos_semanales.csv`).
- **Evidencia en contra de que la «R» sea una regla:** archivos rurales que usan `NC2_` **sin** «R» (`gastos_semanales_capitulo_c.csv`, `gastos_semanales_mercados.csv`); y `NC2R_CC_*` está poblada en hogares urbanos.
- **Hipótesis compatible con todo lo anterior (no documentada):** el DANE unificó en una sola columna de `viviendas_hogares` la respuesta de las preguntas equivalentes de los cuadernillos 2 urbano y rural, y la nombró con el prefijo rural. Explicaría por qué está rellena en hogares urbanos y por qué la etiqueta usa la redacción urbana. No la puedo verificar con los archivos disponibles.
- **Conclusión operativa:** tratar `NC2R_` como un nombre heredado de la codificación del cuadernillo 2, no como un indicador de área. Para filtrar por área usar `P3`/`DOMINIO`, nunca el prefijo.
- **Relevante para la tesis (forma de pago):** variables con «forma/medio de pago» en su etiqueta DDI: «Gastos menos frecuentes - Medio de pago»: 29 (p. ej. `P438A11`, `P438B11`, `P438B12`, `P438C11`); «Viviendas y hogares»: 1 (p. ej. `NC2R_CC_P6`).

### 10.5 ¿A qué cuadernillo se refiere «los bienes mencionados en este cuadernillo»?

**Al cuadernillo 2 (versión urbana o rural, según el hogar). No al cuadernillo 3.** Comparación del texto de los cinco cuadernillos:

| Cuadernillo | Preguntas de forma/medio de pago | Primera redacción | «en este cuadernillo» | «este subcapítulo» |
|---|---|---|---|---|
| Cuadernillo 1 | 0 | — | 0 | 0 |
| Cuadernillo 2 rural | 1 | «La principal forma de pago usada para comprar o adquirir los bienes mencionados en este cuadernillo fue:» | 2 | 0 |
| Cuadernillo 2 urbano | 1 | «La principal forma de pago usada para comprar los bienes mencionados en este cuadernillo fue:» | 2 | 0 |
| Cuadernillo 3 | 31 | «El medio de pago usado principalmente para comprar los artículos y servicios enunciados en este subcapítulo fue:» | 1 | 32 |
| Cuadernillo 4 | 0 | — | 3 | 0 |

- **Cuadernillo 2 urbano:** la pregunta cierra el diario (el encuestador la hace «el día que recoja este cuadernillo diligenciado»); el periodo de referencia de la pregunta anterior es «los catorce días». Capítulos con encabezado detectado: C, D, D1. Capítulo D: «D. GASTOS DIARIOS (comprende los gastos diarios para el hogar y los gastos personales de quien diligencia el cuadernillo)».
- **Cuadernillo 2 rural:** misma pregunta con «comprar o adquirir»; periodo de referencia «la semana pasada». Capítulo D: «D. GASTOS SEMANALES DEL HOGAR (incluye los gastos de la persona que brinda la información)».
- **Cuadernillo 3 (gastos menos frecuentes):** no comparte la pregunta. Pregunta el medio de pago **por subcapítulo** («este subcapítulo», 32 menciones), que en los datos son las variables `P438*` del archivo `hogares/gastos_menos_frecuentes_medio_pago.csv`; no es `NC2R_CC_P6`.
- **Cuadernillo 4 (gastos diarios personales):** 0 preguntas de forma de pago; sus diarios personales quedan fuera de `NC2R_CC_P6`. Ojo: el capítulo D del cuadernillo 2 incluye «los gastos personales de quien diligencia/brinda la información», así que la respuesta puede abarcar parte del gasto personal de esa persona.
- **Alcance real de la respuesta:** una sola respuesta por hogar sobre los bienes registrados en el cuadernillo 2 (gastos frecuentes: alimentos, comidas fuera del hogar y demás diario/semanal). **No cubre todo el gasto del hogar** (los menos frecuentes son del cuadernillo 3).
- **Matiz sobre las etiquetas DDI:** `NC2R_CC_P5` dice «Durante la semana pasada (de lunes a domingo) ¿El hogar tuvo algún gasto en alimentos debido a fiestas, reuniones o invitados?» (redacción del cuadernillo **rural**: «semana pasada»), mientras `NC2R_CC_P6` usa la redacción **urbana**. Es coherente con una columna que reúne las respuestas de ambos cuadernillos, pero mezcla periodos de referencia distintos (los catorce días en el urbano; la semana pasada en el rural).

### 10.6 Forma de pago principal en Bogotá (hogares, expandido con `FEX_C`)

Enunciado correcto: **«% de hogares cuya forma de pago principal es X»**. No es un % de transacciones ni de gasto: es una respuesta por hogar, sobre los bienes del cuadernillo 2.

| Código | Forma de pago principal | Hogares en la muestra | % de hogares (expandido) |
|---|---|---|---|
| 1 | Tarjeta Débito | 67 | 1,97 % |
| 2 | Tarjeta de Crédito | 17 | 0,48 % |
| 3 | Efectivo | 3.413 | 97,03 % |
| 4 | Fiador | 4 | 0,09 % |
| 5 | Bonos | 1 | 0,02 % |
| 6 | Otro | 15 | 0,41 % |
|  | **Total con respuesta** | **3.517** | **100,00 %** |

Base: 3.517 de 3.918 hogares de Bogotá con respuesta (2.263.757 hogares expandidos). Sin respuesta: 401 hogares (11,42 % expandido); no están en el denominador de la tabla. Valores fuera de las 6 categorías: 0. La expansión con `FEX_C` no corrige la no respuesta del ítem, y no se calcularon errores estándar (el archivo no trae identificador de segmento). Con categorías de pocos hogares en la muestra, el % expandido es poco fiable.


## 11. Rotación de la muestra GEIH y apilamiento de 12 meses

### 11.1 Qué documenta el DANE

- **Metodología general (mantenimiento de la muestra):** «El agotamiento de la fuente aparece cuando se encuesta al hogar en repetidas ocasiones. Para evitar este inconveniente, se procede a rotar la medida de tamaño cada año.»
- **Ficha metodológica (texto extraído del PDF; el PDF trae letras recortadas):** «El mantenimiento de la muestra se da mediante una rotación que consiste en encuestar cada año una medid de tamaño vecina que no haya sido encuestada por alguna investigación en los dos años anteriores com mínimo.»
- **Metodología general (unidades de muestreo):** «Unidades Secundarias de Muestreo (USM): Son conglomerados de 10 viviendas contiguas en promedio, también llamados segmentos o medidas de tamaño (MT), ubicados tanto en la cabe de cada municipio, con límites fácilmente identificables en los que se encuestan todas las viviendas, hogares y personas.»
- **Metodología general (pertinencia y desgaste de la fuente):** «se generan muestras trimestrales que cumplen con los criterios estadísticos y se realiza la rotación de la muestra, en donde se selecciona una manzana o se se toma un segmento aleatoriamente, y para la siguiente iteración de la encuesta, se elige un segmento diferente al inicialmente seleccionado.»

**Lectura.** La rotación documentada es **anual** (se cambia la «medida de tamaño» o segmento cada año) y el DANE reconoce que el desgaste aparece cuando el hogar se encuesta «en repetidas ocasiones». **No documenta** cuántas veces ni en qué meses se vuelve a visitar un hogar dentro de un mismo año. Las unidades de muestreo son segmentos de ~10 viviendas donde se encuestan todos los hogares.

### 11.2 Qué muestran los archivos públicos de 2025

| Medida (`datos_hogar` de los 12 meses apilados) | Nacional | Bogotá (`AREA=11`) |
|---|---|---|
| Filas de hogares apiladas | 292.942 | 9.733 |
| Hogares únicos (`DIRECTORIO`+`SECUENCIA_P`+`HOGAR`) | 292.942 | 9.733 |
| `DIRECTORIO` únicos (viviendas) | 290.925 | 9.692 |
| Filas por hogar único | 1,000 | 1,000 |
| Meses en que aparece cada hogar (nº de meses: nº de hogares) | 1: 292.942 | 1: 9.733 |
| Meses por hogar: media | 1,00 | 1,00 |
| Meses en que aparece cada `DIRECTORIO` | 1: 290.925 | 1: 9.692 |
| Filas de personas apiladas | 817.550 | 25.655 |
| Personas únicas (llave de hogar + `ORDEN`) | 817.550 | 25.655 |

**Un hogar típico aparece en 1 mes.** La diferencia entre filas de hogares y `DIRECTORIO` únicos (2.017) viene de viviendas con más de un hogar **dentro del mismo mes** (3.680 filas comparten `DIRECTORIO` con otra del mismo mes), no de repeticiones entre meses. `HOGAR` es idéntico a `SECUENCIA_P` en todas las filas.

### 11.3 Por qué eso no basta: `DIRECTORIO` parece un contador por mes

| Mes | `DIRECTORIO` mínimo | `DIRECTORIO` máximo | % de pasos de +1 entre valores ordenados |
|---|---|---|---|
| enero | 8.086.872 | 8.115.688 | 87,8 % |
| febrero | 8.115.690 | 8.144.357 | 88,5 % |
| marzo | 8.144.358 | 8.181.795 | 88,9 % |
| abril | 8.173.631 | 8.207.970 | 88,1 % |
| mayo | 8.207.971 | 8.238.895 | 88,8 % |
| junio | 8.238.974 | 8.283.062 | 88,4 % |
| julio | 8.283.143 | 8.316.747 | 83,1 % |
| agosto | 8.316.823 | 8.345.515 | 89,2 % |
| septiembre | 8.345.569 | 8.374.030 | 89,9 % |
| octubre | 8.374.095 | 8.403.015 | 88,9 % |
| noviembre | 8.403.077 | 8.435.840 | 89,6 % |
| diciembre | 8.435.963 | 8.473.908 | 88,7 % |

Los rangos son bloques consecutivos y crecientes en el tiempo (solo se solapan los rangos de: marzo). Es compatible con un número asignado por orden de extracción (hipótesis; no está documentado) y no con un identificador persistente de vivienda. Por tanto, que ningún `DIRECTORIO` se repita entre meses **no prueba por sí solo** que los hogares no se repitan: podría ser un efecto del identificador.

### 11.4 Prueba independiente del identificador (composición del hogar)

Huella del hogar = (`DPTO`, `AREA`, sexo y edad de sus miembros). Si hubiera hogares repetidos entre meses, los pares con la misma huella serían **más frecuentes entre meses distintos que dentro del mismo mes**. Se compara la tasa de pares iguales (sobre los pares posibles del mismo estrato) en ambos casos:

| Hogares comparados | Edad | Hogares | Pares iguales, mismo mes | Pares iguales, meses distintos | Razón (entre meses / mismo mes) | Nota |
|---|---|---|---|---|---|---|
| 3 o más personas | exacta | 152.326 | 62 | 697 | 1,02 |  |
| 3 o más personas | tramos de 5 años | 152.326 | 7.041 | 78.382 | 1,01 |  |
| 4 o más personas | exacta | 83.135 | 2 | 51 | 2,32 | pocos pares: razón inestable |
| 4 o más personas | tramos de 5 años | 83.135 | 1.106 | 12.446 | 1,02 |  |

Una razón cercana a 1 significa que no hay exceso de coincidencias entre meses. La prueba detectaría una repetición sustancial de hogares, pero no repeticiones aisladas ni hogares cuya composición cambió entre visitas (nacimientos, cambios de edad de más de un tramo, mudanzas).

### 11.5 Conclusión e implicaciones

**Estado: PENDIENTE (parcial).** Lo verificado y lo no verificado, por separado:

- **Verificado en los archivos:** hogares únicos = filas apiladas (292.942 en el país; 9.733 en Bogotá); ningún hogar en más de un mes; la prueba por composición no muestra exceso de coincidencias entre meses.
- **No verificado:** que el diseño no vuelva a visitar hogares dentro del año. El DANE solo documenta rotación anual de segmentos y el identificador no es persistente; la frecuencia de revisita no está escrita en ningún documento del repositorio.
- **Apilar los 12 meses:** no hay duplicados que eliminar y no corresponde deduplicar por `DIRECTORIO` (los extra son hogares de la misma vivienda). No se detectó nada que lo contradiga: cada fila-hogar puede tratarse como un hogar distinto, con las salvedades de más abajo.
- **`FEX_C18 / 12`:** la suma mensual de `FEX_C18` (personas) va de 51,831 a 52,296 millones: es casi constante y crece de mes a mes, coherente con la calibración mensual que menciona la Metodología (no verifiqué cómo se construye `FEX_C18`). Dividir entre 12 da el promedio anual de 12 cortes mensuales, y esa aritmética no depende de que haya rotación. En principio, si hubiera hogares repetidos lo afectado sería la varianza, no el peso.
- **Lo que sí importa (conglomerados):** la metodología define segmentos de ~10 viviendas donde se encuestan todos los hogares, lo que induce correlación dentro del segmento. Los archivos **no traen identificador de segmento ni de UPM** (columnas buscadas: ninguna), así que no se pueden calcular errores estándar de diseño y los ingenuos subestiman la incertidumbre.
- **Para la partición train/test (CTGAN, TSTR):** no se detectaron hogares repetidos, así que no se espera filtración por repetición; pero las viviendas vecinas comparten características (hipótesis, no verificada). Como sensibilidad se podría particionar por bloques de `DIRECTORIO` o por mes; la decisión es tuya.
- **CLAUDE.md:** la regla `FEX_C18 / 12` sigue vigente. Conviene añadir la nota «GEIH 2025 público: sin panel detectable ni identificador de segmento».


