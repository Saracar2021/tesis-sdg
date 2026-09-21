"""Códigos y etiquetas verificados, cada uno con su fuente (CLAUDE.md: no inferir códigos).

Regla: cada esquema se mapea SOLO con su propia fuente. P438* y NC2R_CC_P6 tienen códigos
distintos en 4 y 5 y no deben intercambiarse (ver MEDIO_PAGO_P438 vs FORMA_PAGO_NC2R).
"""
from __future__ import annotations

# --- ENPH: estrato para tarifa de energía eléctrica (viviendas_hogares.P8520S1A1) -------------
# Fuente: MANUAL_ENPH.pdf, Pregunta 4 (servicios de la vivienda), «Estrato para tarifa»:
#   «el estrato para tarifa es 1 a 6 en la mayoría de las ciudades o cero si la conexión es
#   pirata, y 9 si no es posible establecer el estrato o la vivienda cuenta con planta eléctrica».
# Cuadernillo 1.pdf NO trae los códigos (solo la casilla). El DDI de ENPH tampoco.
# Vacío (' ') = sin dato: la vivienda no reporta servicio de energía o no se diligenció (no verificado cuál).
ESTRATO_ENPH_FUENTE = "MANUAL_ENPH.pdf, Pregunta 4, «Estrato para tarifa» (códigos 1-6; 0 = conexión pirata; 9 = no establecible o planta eléctrica)"
ESTRATO_ENPH_SIN_ESTRATO = {"0": "0 = conexión pirata (Manual ENPH)", "9": "9 = no establecible / planta eléctrica (Manual ENPH)"}

# --- GEIH: estrato para tarifa (datos_hogar.P4030S1A1) --------------------------------------------
# Fuente: Diccionario de datos - GEIH 2025, hoja «Plantilla Diccionario de Datos», fila 32:
#   «P4030S1A1 ¿Con cuáles de los siguientes servicios cuenta la vivienda? Estrato para tarifa»,
#   regla de validación «Rango entre 0 y 6 ó 9». El diccionario NO etiqueta 0 ni 9.
ESTRATO_GEIH_FUENTE = "Diccionario GEIH 2025, fila 32 (P4030S1A1; rango 0-6 ó 9; sin etiquetas para 0 y 9)"
ESTRATO_GEIH_SIN_ESTRATO = {"0": "0 (sin etiqueta en el diccionario GEIH)", "9": "9 (sin etiqueta en el diccionario GEIH)"}

# --- ENPH: medio de pago por subcapítulo, gastos menos frecuentes (P438*) ------------------------
# Fuente: Cuadernillo 3.pdf, pregunta (6) de cada subcapítulo: «El medio de pago usado
# principalmente para comprar los artículos y servicios enunciados en este subcapítulo fue:
# a. Tarjeta débito 1, b. Tarjeta de crédito 2, c. Efectivo 3, d. Bonos 4, e. Cheques 5, f. Otro 6».
MEDIO_PAGO_P438 = {"1": "Tarjeta débito", "2": "Tarjeta de crédito", "3": "Efectivo", "4": "Bonos", "5": "Cheques", "6": "Otro"}
MEDIO_PAGO_P438_FUENTE = "Cuadernillo 3.pdf, pregunta (6) de cada subcapítulo"

# --- ENPH: forma de pago principal declarada por hogar (viviendas_hogares.NC2R_CC_P6) -----------
# Fuente: Cuadernillo 2 urbano.pdf, sección D2 (gastos diarios), pregunta 2: «La principal forma de
# pago usada para comprar los bienes mencionados en este cuadernillo fue: a. Tarjeta débito 1,
# b. Tarjeta de crédito 2, c. Efectivo 3, d. Fiado 4, e. Bonos 5, f. Otra 6». La redacción coincide
# con la etiqueta del DDI de NC2R_CC_P6; el Cuadernillo 2 rural dice «comprar o adquirir»
# (misma codificación). Nótese «Fiado» (crédito informal del comercio), no «fiador».
FORMA_PAGO_NC2R = {"1": "Tarjeta débito", "2": "Tarjeta de crédito", "3": "Efectivo", "4": "Fiado", "5": "Bonos", "6": "Otra"}
FORMA_PAGO_NC2R_FUENTE = "Cuadernillo 2 urbano.pdf, sección D2, pregunta 2 (gastos diarios del hogar, registro de 14 días)"

# --- GEIH ocupados: variables laborales -----------------------------------------------------------
# Fuente: Diccionario GEIH 2025, «Plantilla Diccionario de Datos» (filas indicadas).
POSICION_OCUPACIONAL_P6430 = {  # filas 708-715
    "1": "Obrero o empleado de empresa particular", "2": "Obrero o empleado del gobierno", "3": "Empleado doméstico",
    "4": "Trabajador por cuenta propia", "5": "Patrón o empleador", "6": "Trabajador familiar sin remuneración",
    "7": "Jornalero o peón", "8": "Otro"}
TIENE_CONTRATO_P6440 = {"1": "Sí", "2": "No"}  # filas 680-681
TIPO_CONTRATO_P6450 = {"1": "Verbal", "2": "Escrito", "9": "No sabe, no informa"}  # filas 682-684 (código 9, no 3)
COTIZA_PENSION_P6920 = {"1": "Sí", "2": "No", "3": "Ya es pensionado"}  # filas 983-985
AFILIADO_ARL_P6990 = {"1": "Sí", "2": "No", "9": "No sabe, no informa"}  # filas 995-997

# --- ENPH: subcapítulos de gastos menos frecuentes ------------------------------------------------
# Grupo (letra): título del encabezado «3.X» del Cuadernillo 3.pdf, concordante con la etiqueta DDI de P438X**.
# Un subcapítulo (letra + 2 dígitos) agrupa artículos por PERIODO DE REFERENCIA (mes pasado, últimos
# tres meses, últimos doce meses; Cuadernillo 3, texto introductorio): es categoría × periodo, no
# una categoría pura. 3.K (gastos financieros) tiene pregunta (6) en el cuadernillo pero NO columna P438K en la base.
GRUPOS_P438 = {
    "A": "Artículos de limpieza y cuidado de la vivienda",
    "B": "Artículos y servicios de cuidado personal",
    "C": "Alquiler, combustibles, mantenimiento y servicios de la vivienda",
    "D": "Prendas de vestir y accesorios personales",
    "E": "Educación: matrículas, uniformes, pensiones, textos y útiles escolares",
    "F": "Productos farmacéuticos, elementos médicos y pagos de servicios médicos",
    "G": "Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar",
    "H": "Transporte y comunicaciones",
    "I": "Vehículo",
    "J": "Recreación, diversión, cultura y viajes",
    "L": "Gastos varios",
}
# Título de subbloque «3.XNN» localizado en el Cuadernillo 3 (solo los encontrados; el resto queda sin detalle).
DETALLE_P438 = {
    "A11": "Limpieza, aseo, servicios, desechables y otros artículos para el cuidado de la vivienda",
    "B11": "Jabón, champú, crema, desodorante, papel higiénico, pañales y servicios de cuidado personal",
    "B12": "Máquinas de afeitar eléctricas, secadores y relojes de pulso",
    "C11": "Alquiler de vivienda, combustibles y conexión de servicios para la vivienda",
    "C12": "Conservación, mantenimiento, reparación y conexión de servicios para la vivienda",
    "D11": "Prendas de vestir y calzado para hombre",
    "D12": "Prendas de vestir y calzado para mujer",
    "D15": "Prendas de vestir y calzado para bebé",
    "D16": "Accesorios personales, joyas, lanas, hilos y servicios de alquiler y reparación de prendas y calzado",
    "E11": "Pensiones, transporte y artículos escolares",
    "E12": "Matrículas, uniformes, útiles y textos escolares, bonos escolares, validaciones, pregrados, posgrados y otros",
    "F11": "Analgésicos, antibióticos, anestésicos, antiinflamatorios, antiácidos",
    "F12": "Consultas médicas generales, especialistas, terapias, exámenes de laboratorio",
    "F13": "Servicios de salud: intervenciones quirúrgicas, maternidad, prótesis, sillas de ruedas y otros",
    "G11": "Artículos de cristalería, cubiertos, ollas y otros artículos del hogar",
    "G12": "Lencería y artículos del hogar",
    "H11": "Servicio telefónico, internet y pasajes",
    "H12": "Teléfonos y otros artículos relacionados con las comunicaciones y el transporte",
    "J11": "Bebidas alcohólicas, entradas a cine, teatro, museos, bibliotecas y otros, alojamiento, libros y CD",
    "J12": "Artículos para fiesta, juguetes, entradas a espectáculos",
}
NOTA_P438_J = ("GAP ABIERTO: la base de artículos (CAP) tiene los subcapítulos J11-J14 y K11, pero P438 solo tiene J11, J12, J13 y ninguna columna K: "
               "no existen P438J14 ni P438K11 (los hogares con compras en J14/K11 no tienen medio de pago en la base). Además, la correspondencia "
               "de P438J13 con un bloque concreto del Cuadernillo 3 (3.J131 / 3.J13 / 3.J132) no está verificada.")


# --- ENPH: forma de adquisición (articulos.FORMA) -------------------------------------------------
# INFERIDO, no verificado: el Cuadernillo 3 (instrucciones generales) lista las formas por letra en este orden:
# a) compra, b) pago por trabajo, c) regalo o donación, d) intercambio, e) producido por el hogar (autoconsumo),
# f) tomado de un negocio propio (autosuministro), g) otra. La base trae FORMA con códigos 1-7; se asume 1 = compra
# (a) porque concentra la gran mayoría de los registros, pero el cuadernillo no imprime los códigos numéricos.
# Por eso el cruce de vacíos de P438* se reporta también con la definición «cualquier registro», que no depende de FORMA.
FORMA_ADQUISICION_INFERIDA = {"1": "Compra", "2": "Pago por trabajo", "3": "Regalo o donación", "4": "Intercambio",
                              "5": "Producido por el hogar", "6": "Tomado de un negocio propio", "7": "Otra"}
