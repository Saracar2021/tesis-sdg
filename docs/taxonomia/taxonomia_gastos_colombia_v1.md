# Taxonomía de categorías de gasto para transacciones financieras en el contexto colombiano

**Versión 1.0.0 — 19 de julio de 2026**
Documento de acompañamiento del esquema `taxonomia_gastos_colombia_v1.json`. Entregable del Objetivo Específico 2 del Trabajo de Grado.

## 1. Propósito y triple uso

Esta taxonomía cumple tres funciones simultáneas dentro del pipeline: define el espacio de salida del clasificador automático de gastos, estructura el protocolo de etiquetado manual de las transacciones reales para la validación TSTR, y especifica el esquema de categorías que el generador sintético debe producir. Que las tres funciones compartan un único esquema es una condición de validez del paradigma TSTR: si el generador produce categorías distintas de las que el anotador usa para etiquetar los datos reales, la comparación deja de ser interpretable.

## 2. Principios de diseño

El diseño responde a cuatro principios. Primero, **anclaje en COICOP**: las categorías de gasto se derivan de las divisiones COICOP que la propia ENPH 2016-2017 utiliza, lo que garantiza comparabilidad directa con los microdatos de calibración y con estadística internacional. Segundo, **separación de dimensiones**: la categoría del gasto, el medio de pago y la formalidad del comercio son tres dimensiones ortogonales y no se mezclan; comprar arroz en la tienda pagando con Nequi es `alimentos_mercado` con `medio_pago=billetera_digital`, no una categoría "Nequi". Tercero, **exhaustividad operativa**: además de las categorías de gasto COICOP, la taxonomía incluye las categorías operativas que aparecen en los extractos reales de billeteras y bancos —P2P, retiros de efectivo, movimientos entre cuentas propias e ingresos— porque el conjunto de validación TSTR proviene de extractos y el clasificador las encontrará inevitablemente. Cuarto, **honestidad sobre el techo de clasificabilidad**: la taxonomía reconoce explícitamente qué transacciones no pueden clasificarse a partir del texto (subtipo `p2p.indeterminada`) en lugar de forzar asignaciones arbitrarias.

## 3. Estructura general

La taxonomía tiene dieciséis categorías de nivel 1 organizadas en dos grupos: doce categorías de gasto ancladas en COICOP (alimentos y mercado, comidas fuera del hogar, transporte, vivienda y servicios, telecomunicaciones, salud, educación, entretenimiento, vestuario y cuidado personal, artículos del hogar, obligaciones financieras, otros) y cuatro categorías operativas propias del ecosistema transaccional (transferencias P2P, retiro de efectivo, movimiento propio, ingreso). Cada categoría de nivel 1 contiene subtipos de nivel 2 que son informativos y analíticos pero no entran al cómputo del F1 macro, salvo análisis secundarios.

| Categoría (nivel 1) | COICOP | Clasificabilidad por texto |
|---|---|---|
| alimentos_mercado | 01 | Alta |
| comidas_fuera | 11.1 | Alta |
| transporte | 07 | Alta |
| vivienda_servicios | 04 | Media |
| telecom_conectividad | 08 | Alta |
| salud | 06 | Alta |
| educacion | 10 | Alta |
| entretenimiento | 09 (+02) | Alta |
| vestuario_cuidado_personal | 03 + 12.1 | Media |
| hogar_articulos | 05 | Media |
| obligaciones_financieras | 12.4–12.6 | Media |
| transferencias_p2p | — | Baja |
| retiro_efectivo | — | Alta |
| movimiento_propio | — | Media |
| ingreso | — | Media |
| otros | 12 residual | Baja |

La columna de clasificabilidad anticipa el desempeño esperable de un clasificador basado solo en la descripción y orienta la interpretación de la matriz de confusión: errores en categorías de clasificabilidad baja no son fallas del modelo sino límites de la información disponible en el texto.

## 4. Anclaje documental en el instrumento ENPH

Dos listados oficiales del Cuadernillo 3 de la ENPH sustentan las dimensiones auxiliares. El listado de medio de pago de la pregunta (6), que alimenta las variables P438, contempla exactamente seis códigos: tarjeta débito (1), tarjeta de crédito (2), efectivo (3), bonos (4), cheques (5) y otro (6). El instrumento de 2016 no contempla billeteras digitales ni transferencias electrónicas, de modo que los valores `billetera_digital` y `transferencia_bancaria` del enum de medio de pago no tienen equivalencia ENPH y se calibran con la Encuesta de percepción sobre uso de instrumentos de pago 2024 del Banco de la República y el Reporte de Inclusión Financiera 2024. Esta asimetría de fuentes es una decisión metodológica declarada, no una omisión: debe figurar en la sección de supuestos de calibración de la tesis.

El listado oficial de "Lugar de compra" del mismo cuadernillo proporciona el anclaje de la dimensión de formalidad del comercio. Los códigos de vendedores ambulantes (13) y persona particular (20) fundamentan el valor `informal`; los de almacenes de cadena (1), supermercados de cajas de compensación (4), farmacias (17), ferias (21) y televentas (23) fundamentan el valor `formal`; y los de tiendas de barrio (6), plazas de mercado (10) y sanandresitos (14) fundamentan el valor `pequeno_comercio_indeterminado`, reconociendo que la formalidad de estos establecimientos no es determinable desde la descripción de una transacción. Usar el listado del DANE como fundamento evita que la operacionalización de "informalidad comercial" parezca una construcción ad hoc del autor.

## 5. Reglas de decisión

Siete reglas ordenadas resuelven los casos ambiguos; el detalle está en el campo `reglas_de_decision` del JSON. La regla estructurante es R1, predominio del bien sobre el canal: si la descripción identifica el comercio o el bien, se asigna la categoría del bien sin importar cómo se pagó. Su complemento es R2, P2P residual: las transferencias a personas naturales solo son P2P cuando el propósito no es identificable; cuando el voluntario declara el propósito (arriendo, transporte informal, servicio doméstico), la transacción recibe la categoría del propósito y el marcador `canal_p2p=true`. Este marcador es analíticamente valioso: permite cuantificar cuánto gasto real de los hogares viaja "disfrazado" de transferencia P2P, un fenómeno característico de la economía informal digitalizada que ningún trabajo previo ha medido para Colombia.

Las reglas restantes cubren los retiros y movimientos propios como no-gasto (R3), los domicilios de plataforma (R4), los pagos de factura por PSE que heredan la categoría de la factura (R5), la distinción entre comprar con tarjeta de crédito y pagar la tarjeta (R6), y el mandato de no adivinar ante ambigüedad irresoluble (R7).

## 6. Implicaciones para la anotación y el reporte TSTR

Cada transacción real se anota con seis campos: categoría de nivel 1 (obligatoria), subtipo de nivel 2 (opcional), medio de pago, formalidad del comercio, el marcador `canal_p2p` y el campo `fuente_etiqueta`, que registra si la etiqueta pudo derivarse del texto o requirió declaración del voluntario. Este último campo es la pieza que conecta la taxonomía con la discusión de resultados: el desempeño del clasificador debe evaluarse por separado sobre las transacciones etiquetables por texto y sobre las que requirieron declaración, porque solo las primeras constituyen el techo alcanzable para un modelo que ve únicamente la descripción.

Para el reporte de métricas se adopta una regla de soporte mínimo: el F1 macro se calcula sobre las categorías de nivel 1 con al menos diez ejemplos en el conjunto real; las categorías con soporte menor se colapsan en `otros` para el cómputo y se describen por separado. Esto evita que el F1 macro quede dominado por la varianza de categorías con tres o cuatro ejemplos, un riesgo real con un conjunto de 200 a 300 transacciones y dieciséis categorías.

## 7. Diferencias con la taxonomía del modelo de referencia

Frente al esquema de Pancholi et al., esta taxonomía introduce cinco diferencias sustantivas: la existencia misma de la categoría P2P con su subtipo indeterminado; las categorías operativas de retiro de efectivo y movimiento propio, inexistentes en un esquema pensado para tarjetas de crédito estadounidenses; la dimensión de formalidad del comercio anclada en códigos DANE; la dimensión de medio de pago con billetera digital y fiado; y la eliminación de las categorías de ocio hiperespecíficas propias de un registro de negocios de Washington D.C. (por ejemplo, Athletic Exhibition o Skating Rink). Cada diferencia responde a una de las tres **hipótesis** sobre el pipeline de referencia (ingreso, categorías, medio de pago), que están **sin verificar** hasta ejecutarlo (Chat 01B); la afirmación de que esas categorías dominaban su salida no tiene respaldo de ejecución.

## 8. Versionado y evolución

El esquema sigue versionado semántico. Cambios que agreguen subtipos de nivel 2 o ejemplos incrementan la versión menor; cambios que agreguen, eliminen o fusionen categorías de nivel 1 incrementan la versión mayor y obligan a re-etiquetar o mapear el conjunto real ya anotado. La versión utilizada en el etiquetado TSTR debe congelarse antes de iniciar la recolección de agosto y citarse en la tesis; los desacuerdos entre anotadores que revelen ambigüedades del esquema se documentan como insumo de la versión 2, no se resuelven cambiando la taxonomía a mitad del etiquetado.
