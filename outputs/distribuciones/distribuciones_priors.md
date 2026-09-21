# Distribuciones para los priors — Bogotá urbano

> Generado por `tools/distribuciones_priors.py`. Toda cifra sale de código. **Dominio: Bogotá urbano (caso de estudio), no nacional.** Cifras expandidas con factor de expansión; no se calcularon errores estándar (los archivos no traen identificador de segmento). Las cifras ENPH son 2016-2017 (una fila por hogar); las de GEIH son 2025 (12 meses apilados, ver sensibilidad a diciembre).

**Fuentes de códigos (cada esquema se mapea solo con la suya):** estrato ENPH → Manual ENPH (Pregunta 4); estrato GEIH → Diccionario GEIH 2025 fila 32; P438* → Cuadernillo 3 (1 débito, 2 crédito, 3 efectivo, **4 bonos, 5 cheques**, 6 otro); NC2R_CC_P6 → Cuadernillo 2 urbano (1 débito, 2 crédito, 3 efectivo, **4 fiado, 5 bonos**, 6 otra).

**No comparables entre fuentes:** ICGU (ENPH, ingreso del hogar) e INGLABO (GEIH, ingreso laboral individual).

Hogares ENPH Bogotá: 3.918 (sin ponderar), 2.555.731 expandidos.

---

### ENPH · estrato agrupado (1-2 / 3-4 / 5-6)

- **fuente:** ENPH 2016-2017, hogares/viviendas_hogares.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **variable:** P8520S1A1 «Estrato para tarifa» (energía eléctrica)
- **codigos:** MANUAL_ENPH.pdf, Pregunta 4, «Estrato para tarifa» (códigos 1-6; 0 = conexión pirata; 9 = no establecible o planta eléctrica)
- **denominador:** «% base con respuesta» = hogares con estrato 1-6; «% del total» = todos los hogares de Bogotá

| codigo | categoria | n (sin ponderar) | expandido | % base con respuesta | % del total |
|---|---|---|---|---|---|
| bajo (1-2) | bajo (1-2) | 2.256 | 1.136.926,02 | 44,67 | 44,49 |
| medio (3-4) | medio (3-4) | 1.427 | 1.259.142,06 | 49,47 | 49,27 |
| alto (5-6) | alto (5-6) | 216 | 149.294,64 | 5,87 | 5,84 |
|  | sin dato (vacío) | 7 | 3.855,72 | — | 0,15 |
| 0 | sin dato: 0 = conexión pirata (Manual ENPH) | 12 | 6.512,75 | — | 0,25 |

Los códigos 0 y 9 NO son estratos y no se asignan a ningún grupo; el vacío se reporta como sin dato (no se imputa).

Archivo: `outputs/distribuciones/enph_estrato_agrupado.csv`


### ENPH · estrato para tarifa, sin agrupar

- **fuente:** ENPH 2016-2017, hogares/viviendas_hogares.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **variable:** P8520S1A1
- **codigos:** MANUAL_ENPH.pdf, Pregunta 4, «Estrato para tarifa» (códigos 1-6; 0 = conexión pirata; 9 = no establecible o planta eléctrica)
- **denominador:** igual que la tabla agrupada

| codigo | categoria | n (sin ponderar) | expandido | % base con respuesta | % del total |
|---|---|---|---|---|---|
| 1 | Estrato 1 | 676 | 348.671,06 | 13,70 | 13,64 |
| 2 | Estrato 2 | 1.580 | 788.254,96 | 30,97 | 30,84 |
| 3 | Estrato 3 | 1.210 | 1.080.263,85 | 42,44 | 42,27 |
| 4 | Estrato 4 | 217 | 178.878,22 | 7,03 | 7,00 |
| 5 | Estrato 5 | 130 | 94.755,94 | 3,72 | 3,71 |
| 6 | Estrato 6 | 86 | 54.538,70 | 2,14 | 2,13 |
|  | sin dato (vacío) | 7 | 3.855,72 | — | 0,15 |
| 0 | sin dato: 0 = conexión pirata (Manual ENPH) | 12 | 6.512,75 | — | 0,25 |

Archivo: `outputs/distribuciones/enph_estrato_detalle.csv`


### ENPH · quintiles de ICGU (ingreso corriente de la unidad de gasto), calculados dentro de Bogotá

- **fuente:** ENPH 2016-2017, hogares/viviendas_hogares.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **variable:** ICGU (ingreso del HOGAR / unidad de gasto; no es comparable con INGLABO de GEIH)
- **cortes:** menor ICGU con F ponderada ≥ j/5: 1.127.000, 1.810.250, 2.766.667, 4.506.283
- **denominador:** hogares de Bogotá con ICGU (sin ICGU: 0)

| quintil | n | expandido | pct_hogares | icgu_min | icgu_max | hogares_icgu_cero |
|---|---|---|---|---|---|---|
| Q1 | 860 | 511.952,01 | 20,03 | 0 | 1.127.000 | 31 |
| Q2 | 820 | 510.425,31 | 19,97 | 1.127.265 | 1.810.250 | 0 |
| Q3 | 801 | 512.212,29 | 20,04 | 1.811.000 | 2.766.667 | 0 |
| Q4 | 759 | 510.416,74 | 19,97 | 2.766.767 | 4.506.283 | 0 |
| Q5 | 678 | 510.724,83 | 19,98 | 4.511.083 | 88.300.000 | 0 |

Los valores iguales a un corte quedan en el quintil inferior; por eso los % no son exactamente 20. Quintiles por ICGU del hogar, no per cápita.

Archivo: `outputs/distribuciones/enph_ingreso_quintil.csv`


### ENPH · estrato agrupado × quintil de ICGU (soporte por celda)

- **fuente:** ENPH 2016-2017, hogares/viviendas_hogares.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **variable:** P8520S1A1 agrupado × quintil ICGU
- **denominador:** hogares con estrato 1-6 e ICGU válido

| estrato_agrupado | quintil | n | expandido | pct_del_cruce | n_menor_30 |
|---|---|---|---|---|---|
| bajo (1-2) | Q1 | 653 | 327.100,76 | 12,85 | False |
| bajo (1-2) | Q2 | 572 | 291.245,82 | 11,44 | False |
| bajo (1-2) | Q3 | 520 | 263.634,80 | 10,36 | False |
| bajo (1-2) | Q4 | 382 | 188.119,51 | 7,39 | False |
| bajo (1-2) | Q5 | 129 | 66.825,14 | 2,63 | False |
| medio (3-4) | Q1 | 188 | 174.436,25 | 6,85 | False |
| medio (3-4) | Q2 | 236 | 210.953,84 | 8,29 | False |
| medio (3-4) | Q3 | 267 | 238.567,70 | 9,37 | False |
| medio (3-4) | Q4 | 356 | 308.616,34 | 12,12 | False |
| medio (3-4) | Q5 | 380 | 326.567,93 | 12,83 | False |
| alto (5-6) | Q1 | 9 | 6.673,81 | 0,26 | True |
| alto (5-6) | Q2 | 5 | 3.128,45 | 0,12 | True |
| alto (5-6) | Q3 | 13 | 9.518,94 | 0,37 | True |
| alto (5-6) | Q4 | 21 | 13.680,89 | 0,54 | True |
| alto (5-6) | Q5 | 168 | 116.292,55 | 4,57 | False |

`n_menor_30` marca celdas con menos de 30 hogares (sin ponderar): informativo; el umbral de soporte y el encogimiento jerárquico se fijan en el Chat 05.

Archivo: `outputs/distribuciones/enph_estrato_x_quintil.csv`


### ENPH · forma de pago principal declarada por el hogar (NC2R_CC_P6)

- **fuente:** ENPH 2016-2017, hogares/viviendas_hogares.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **variable:** NC2R_CC_P6
- **codigos:** Cuadernillo 2 urbano.pdf, sección D2, pregunta 2 (gastos diarios del hogar, registro de 14 días)
- **enunciado:** % de HOGARES cuya forma de pago principal declarada para los bienes del cuadernillo 2 urbano (gastos diarios, 14 días) es X
- **denominador:** «% base con respuesta» = hogares con respuesta; «% del total» = todos los hogares de Bogotá; el vacío se reporta, no se imputa

| codigo | categoria | n (sin ponderar) | expandido | % base con respuesta | % del total |
|---|---|---|---|---|---|
| 1 | Tarjeta débito | 67 | 44.703,56 | 1,97 | 1,75 |
| 2 | Tarjeta de crédito | 17 | 10.763,12 | 0,48 | 0,42 |
| 3 | Efectivo | 3.413 | 2.196.556,34 | 97,03 | 85,95 |
| 4 | Fiado | 4 | 1.992,87 | 0,09 | 0,08 |
| 5 | Bonos | 1 | 420,60 | 0,02 | 0,02 |
| 6 | Otra | 15 | 9.320,71 | 0,41 | 0,36 |
|  | sin dato (vacío) | 401 | 291.973,99 | — | 11,42 |

NO es una participación de transacciones ni de gasto: es una respuesta por hogar. El cuadernillo 2 urbano registra gastos diarios (compras frecuentes). Códigos según el cuadernillo 2 urbano (4 = Fiado, 5 = Bonos); NO usar el esquema de P438.

Archivo: `outputs/distribuciones/enph_forma_pago_nc2r.csv`


### ENPH · medio de pago principal por subcapítulo de gasto (P438*), formato largo

- **fuente:** ENPH 2016-2017, hogares/gastos_menos_frecuentes_medio_pago.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **codigos:** Cuadernillo 3.pdf, pregunta (6) de cada subcapítulo (NO es el esquema de NC2R_CC_P6)
- **enunciado:** % de HOGARES (entre los que respondieron el subcapítulo) cuyo medio de pago principal en ese subcapítulo es X
- **denominador:** hogares de Bogotá con código 1-6 en la columna del subcapítulo

_(tabla de 174 filas: solo en el CSV; el resumen está en la matriz siguiente)_

Archivo: `outputs/distribuciones/enph_p438_medio_pago_por_subcapitulo.csv`


### ENPH · cobertura de cada columna P438* (hogares con respuesta)

- **fuente:** ENPH 2016-2017, hogares/gastos_menos_frecuentes_medio_pago.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **codigos:** Cuadernillo 3.pdf, pregunta (6) de cada subcapítulo (NO es el esquema de NC2R_CC_P6)
- **enunciado:** % de HOGARES (entre los que respondieron el subcapítulo) cuyo medio de pago principal en ese subcapítulo es X
- **denominador:** «pct_hogares_bogota_con_respuesta» = expandido con respuesta / total de hogares de Bogotá

| columna | subcapitulo | grupo | detalle | n_con_respuesta | n_vacio | n_codigo_fuera_de_lista | hogares_expandidos_con_respuesta | pct_hogares_bogota_con_respuesta |
|---|---|---|---|---|---|---|---|---|
| P438A11 | A11 | Artículos de limpieza y cuidado de la vivienda | Limpieza, aseo, servicios, desechables y otros artículos para el cuidado de la vivienda | 3.811 | 107 | 0 | 2.483.502,16 | 97,17 |
| P438B11 | B11 | Artículos y servicios de cuidado personal | Jabón, champú, crema, desodorante, papel higiénico, pañales y servicios de cuidado personal | 3.813 | 105 | 0 | 2.484.741,92 | 97,22 |
| P438B12 | B12 | Artículos y servicios de cuidado personal | Máquinas de afeitar eléctricas, secadores y relojes de pulso | 366 | 3.552 | 0 | 249.840,38 | 9,78 |
| P438C11 | C11 | Alquiler, combustibles, mantenimiento y servicios de la vivienda | Alquiler de vivienda, combustibles y conexión de servicios para la vivienda | 1.770 | 2.148 | 0 | 1.250.228,20 | 48,92 |
| P438C12 | C12 | Alquiler, combustibles, mantenimiento y servicios de la vivienda | Conservación, mantenimiento, reparación y conexión de servicios para la vivienda | 1.653 | 2.265 | 0 | 1.049.351,37 | 41,06 |
| P438D11 | D11 | Prendas de vestir y accesorios personales | Prendas de vestir y calzado para hombre | 1.316 | 2.602 | 0 | 916.183,69 | 35,85 |
| P438D12 | D12 | Prendas de vestir y accesorios personales | Prendas de vestir y calzado para mujer | 1.504 | 2.414 | 0 | 1.012.674,86 | 39,62 |
| P438D13 | D13 | Prendas de vestir y accesorios personales | (sin título de subbloque localizado) | 584 | 3.334 | 0 | 415.036,23 | 16,24 |
| P438D14 | D14 | Prendas de vestir y accesorios personales | (sin título de subbloque localizado) | 567 | 3.351 | 0 | 402.770,02 | 15,76 |
| P438D15 | D15 | Prendas de vestir y accesorios personales | Prendas de vestir y calzado para bebé | 292 | 3.626 | 0 | 206.259,04 | 8,07 |
| P438D16 | D16 | Prendas de vestir y accesorios personales | Accesorios personales, joyas, lanas, hilos y servicios de alquiler y reparación de prendas y calzado | 744 | 3.174 | 0 | 490.350,66 | 19,19 |
| P438E11 | E11 | Educación: matrículas, uniformes, pensiones, textos y útiles escolares | Pensiones, transporte y artículos escolares | 1.298 | 2.620 | 0 | 874.046,54 | 34,20 |
| P438E12 | E12 | Educación: matrículas, uniformes, pensiones, textos y útiles escolares | Matrículas, uniformes, útiles y textos escolares, bonos escolares, validaciones, pregrados, posgrados y otros | 1.936 | 1.982 | 0 | 1.291.585,40 | 50,54 |
| P438F11 | F11 | Productos farmacéuticos, elementos médicos y pagos de servicios médicos | Analgésicos, antibióticos, anestésicos, antiinflamatorios, antiácidos | 2.381 | 1.537 | 0 | 1.543.168,72 | 60,38 |
| P438F12 | F12 | Productos farmacéuticos, elementos médicos y pagos de servicios médicos | Consultas médicas generales, especialistas, terapias, exámenes de laboratorio | 645 | 3.273 | 0 | 450.627,79 | 17,63 |
| P438F13 | F13 | Productos farmacéuticos, elementos médicos y pagos de servicios médicos | Servicios de salud: intervenciones quirúrgicas, maternidad, prótesis, sillas de ruedas y otros | 679 | 3.239 | 0 | 458.670,27 | 17,95 |
| P438G11 | G11 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | Artículos de cristalería, cubiertos, ollas y otros artículos del hogar | 747 | 3.171 | 0 | 499.302,88 | 19,54 |
| P438G12 | G12 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | Lencería y artículos del hogar | 1.165 | 2.753 | 0 | 784.112,57 | 30,68 |
| P438G13 | G13 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | (sin título de subbloque localizado) | 464 | 3.454 | 0 | 316.334,93 | 12,38 |
| P438G14 | G14 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | (sin título de subbloque localizado) | 461 | 3.457 | 0 | 316.498,11 | 12,38 |
| P438H11 | H11 | Transporte y comunicaciones | Servicio telefónico, internet y pasajes | 1.727 | 2.191 | 0 | 1.148.663,58 | 44,94 |
| P438H12 | H12 | Transporte y comunicaciones | Teléfonos y otros artículos relacionados con las comunicaciones y el transporte | 886 | 3.032 | 0 | 588.694,96 | 23,03 |
| P438I11 | I11 | Vehículo | (sin título de subbloque localizado) | 737 | 3.181 | 0 | 527.503,41 | 20,64 |
| P438I12 | I12 | Vehículo | (sin título de subbloque localizado) | 1.112 | 2.806 | 0 | 805.577,16 | 31,52 |
| P438J11 | J11 | Recreación, diversión, cultura y viajes | Bebidas alcohólicas, entradas a cine, teatro, museos, bibliotecas y otros, alojamiento, libros y CD | 1.578 | 2.340 | 0 | 1.057.407,85 | 41,37 |
| P438J12 | J12 | Recreación, diversión, cultura y viajes | Artículos para fiesta, juguetes, entradas a espectáculos | 414 | 3.504 | 0 | 304.673,84 | 11,92 |
| P438J13 | J13 | Recreación, diversión, cultura y viajes | (sin título de subbloque localizado) | 201 | 3.717 | 0 | 150.461,29 | 5,89 |
| P438L11 | L11 | Gastos varios | (sin título de subbloque localizado) | 467 | 3.451 | 0 | 319.501,07 | 12,50 |
| P438L12 | L12 | Gastos varios | (sin título de subbloque localizado) | 677 | 3.241 | 0 | 453.428,72 | 17,74 |

Vacío = no respuesta O no aplica: se separan en la tabla `enph_p438_vacios` (cruce con los registros de artículos). GAP ABIERTO: la base de artículos (CAP) tiene los subcapítulos J11-J14 y K11, pero P438 solo tiene J11, J12, J13 y ninguna columna K: no existen P438J14 ni P438K11 (los hogares con compras en J14/K11 no tienen medio de pago en la base). Además, la correspondencia de P438J13 con un bloque concreto del Cuadernillo 3 (3.J131 / 3.J13 / 3.J132) no está verificada. Los subcapítulos son categoría × periodo de referencia (mes pasado / 3 meses / 12 meses) y cubren solo compras MENOS frecuentes.

Archivo: `outputs/distribuciones/enph_p438_cobertura.csv`


### ENPH · matriz subcapítulo × medio de pago (% de hogares con respuesta)

- **fuente:** ENPH 2016-2017, hogares/gastos_menos_frecuentes_medio_pago.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **codigos:** Cuadernillo 3.pdf, pregunta (6) de cada subcapítulo (NO es el esquema de NC2R_CC_P6)
- **enunciado:** % de HOGARES (entre los que respondieron el subcapítulo) cuyo medio de pago principal en ese subcapítulo es X
- **denominador:** hogares con código 1-6 en el subcapítulo (columna n_con_respuesta)

| subcapitulo | grupo | Tarjeta débito | Tarjeta de crédito | Efectivo | Bonos | Cheques | Otro | n_con_respuesta | pct_hogares_bogota_con_respuesta |
|---|---|---|---|---|---|---|---|---|---|
| A11 | Artículos de limpieza y cuidado de la vivienda | 4,57 | 2,62 | 92,46 | 0,32 | 0,00 | 0,04 | 3.811 | 97,17 |
| B11 | Artículos y servicios de cuidado personal | 3,94 | 2,72 | 93,14 | 0,16 | 0,00 | 0,04 | 3.813 | 97,22 |
| B12 | Artículos y servicios de cuidado personal | 5,40 | 8,26 | 85,53 | 0,00 | 0,00 | 0,80 | 366 | 9,78 |
| C11 | Alquiler, combustibles, mantenimiento y servicios de la vivienda | 5,01 | 1,10 | 93,33 | 0,00 | 0,14 | 0,42 | 1.770 | 48,92 |
| C12 | Alquiler, combustibles, mantenimiento y servicios de la vivienda | 3,05 | 3,65 | 92,81 | 0,00 | 0,21 | 0,27 | 1.653 | 41,06 |
| D11 | Prendas de vestir y accesorios personales | 6,83 | 6,51 | 86,26 | 0,21 | 0,00 | 0,19 | 1.316 | 35,85 |
| D12 | Prendas de vestir y accesorios personales | 7,23 | 7,67 | 84,39 | 0,40 | 0,00 | 0,31 | 1.504 | 39,62 |
| D13 | Prendas de vestir y accesorios personales | 3,47 | 6,15 | 89,94 | 0,29 | 0,00 | 0,15 | 584 | 16,24 |
| D14 | Prendas de vestir y accesorios personales | 5,41 | 5,80 | 88,69 | 0,10 | 0,00 | 0,00 | 567 | 15,76 |
| D15 | Prendas de vestir y accesorios personales | 2,34 | 3,73 | 93,34 | 0,00 | 0,00 | 0,60 | 292 | 8,07 |
| D16 | Prendas de vestir y accesorios personales | 3,83 | 4,13 | 92,04 | 0,00 | 0,00 | 0,00 | 744 | 19,19 |
| E11 | Educación: matrículas, uniformes, pensiones, textos y útiles escolares | 2,91 | 0,68 | 95,83 | 0,16 | 0,00 | 0,43 | 1.298 | 34,20 |
| E12 | Educación: matrículas, uniformes, pensiones, textos y útiles escolares | 3,09 | 3,00 | 92,13 | 0,03 | 0,34 | 1,41 | 1.936 | 50,54 |
| F11 | Productos farmacéuticos, elementos médicos y pagos de servicios médicos | 2,42 | 1,10 | 96,41 | 0,04 | 0,00 | 0,02 | 2.381 | 60,38 |
| F12 | Productos farmacéuticos, elementos médicos y pagos de servicios médicos | 4,25 | 3,02 | 92,51 | 0,22 | 0,00 | 0,00 | 645 | 17,63 |
| F13 | Productos farmacéuticos, elementos médicos y pagos de servicios médicos | 8,76 | 9,51 | 80,55 | 0,00 | 0,09 | 1,09 | 679 | 17,95 |
| G11 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | 4,34 | 2,50 | 93,16 | 0,00 | 0,00 | 0,00 | 747 | 19,54 |
| G12 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | 5,43 | 6,77 | 86,84 | 0,23 | 0,00 | 0,73 | 1.165 | 30,68 |
| G13 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | 5,84 | 17,66 | 75,22 | 0,00 | 0,00 | 1,28 | 464 | 12,38 |
| G14 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | 5,89 | 28,01 | 64,33 | 0,00 | 0,00 | 1,77 | 461 | 12,38 |
| H11 | Transporte y comunicaciones | 1,60 | 2,63 | 95,69 | 0,09 | 0,00 | 0,00 | 1.727 | 44,94 |
| H12 | Transporte y comunicaciones | 4,96 | 22,39 | 69,52 | 0,16 | 0,00 | 2,98 | 886 | 23,03 |
| I11 | Vehículo | 5,26 | 5,47 | 89,03 | 0,00 | 0,00 | 0,25 | 737 | 20,64 |
| I12 | Vehículo | 5,57 | 8,94 | 84,36 | 0,00 | 0,17 | 0,96 | 1.112 | 31,52 |
| J11 | Recreación, diversión, cultura y viajes | 4,31 | 2,92 | 92,63 | 0,10 | 0,00 | 0,04 | 1.578 | 41,37 |
| J12 | Recreación, diversión, cultura y viajes | 5,50 | 4,52 | 89,98 | 0,00 | 0,00 | 0,00 | 414 | 11,92 |
| J13 | Recreación, diversión, cultura y viajes | 10,97 | 15,15 | 72,79 | 0,00 | 0,00 | 1,08 | 201 | 5,89 |
| L11 | Gastos varios | 1,32 | 0,00 | 98,68 | 0,00 | 0,00 | 0,00 | 467 | 12,50 |
| L12 | Gastos varios | 4,89 | 2,41 | 92,13 | 0,00 | 0,00 | 0,57 | 677 | 17,74 |

Esta es la tabla que usa el generador para condicionar `medio_pago` a la categoría de gasto (solo compras menos frecuentes). **Cobertura incompleta:** faltan los subcapítulos J14 y K11 (ver la sección «COBERTURA FALTANTE» más abajo, con el % de hogares afectados).

Archivo: `outputs/distribuciones/enph_p438_matriz_categoria_x_medio.csv`


### ENPH · subcapítulos P438* con efectivo > 85 % (resumen de la matriz)

- **fuente:** ENPH 2016-2017, hogares/gastos_menos_frecuentes_medio_pago.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **codigos:** Cuadernillo 3.pdf, pregunta (6) de cada subcapítulo (NO es el esquema de NC2R_CC_P6)
- **enunciado:** % de HOGARES (entre los que respondieron el subcapítulo) cuyo medio de pago principal en ese subcapítulo es X
- **denominador:** hogares con código 1-6 en el subcapítulo (columna n_con_respuesta)
- **umbral:** efectivo > 85 % (comparación estricta, sobre el valor sin redondear)

| subcapitulo | grupo | efectivo_pct | n_con_respuesta |
|---|---|---|---|
| G14 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | 64,33 | 461 |
| H12 | Transporte y comunicaciones | 69,52 | 886 |
| J13 | Recreación, diversión, cultura y viajes | 72,79 | 201 |
| G13 | Electrodomésticos, muebles, enseres, utensilios domésticos y lencería para el hogar | 75,22 | 464 |
| F13 | Productos farmacéuticos, elementos médicos y pagos de servicios médicos | 80,55 | 679 |
| I12 | Vehículo | 84,36 | 1.112 |
| D12 | Prendas de vestir y accesorios personales | 84,39 | 1.504 |

**El efectivo supera el 85 % en 22 de 29 subcapítulos.** La tabla del informe lista solo los 7 subcapítulos donde NO lo supera; el CSV trae los 29. Cada subcapítulo es un % de hogares con respuesta en ese subcapítulo (no de transacciones). No incluye J14 ni K11 (sin columna P438).

Archivo: `outputs/distribuciones/enph_p438_resumen_efectivo.csv`


### ENPH · vacíos de P438*: no respuesta vs no aplica (cruce con registros de artículos)

- **fuente:** ENPH 2016-2017, gastos_menos_frecuentes_medio_pago.csv × gastos_menos_frecuentes_articulos.txt (llave DIRECTORIO + CAP = subcapítulo)
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **codigos:** Cuadernillo 3.pdf, pregunta (6) de cada subcapítulo (NO es el esquema de NC2R_CC_P6)
- **enunciado:** % de HOGARES (entre los que respondieron el subcapítulo) cuyo medio de pago principal en ese subcapítulo es X
- **definiciones:** responde = hay base de compra y medio 1-6 · **no respuesta** = hay base de compra y NO hay medio · **no aplica** = no hay base de compra y no hay medio · medio_sin_base = hay medio pero no hay registros/compras (inconsistencia entre tablas)
- **denominador:** pct_no_respuesta_de_hogares_con_base: hogares con base de compra; pct_vacios_*: hogares con columna vacía; pct_hogares_no_aplica: todos los hogares de Bogotá (todo ponderado con FEX_C)

| subcapitulo | base_de_compra | n_hogares_con_base | n_no_respuesta | pct_no_respuesta_de_hogares_con_base | pct_vacios_que_son_no_respuesta | pct_vacios_que_son_no_aplica | n_medio_sin_base |
|---|---|---|---|---|---|---|---|
| A11 | cualquier registro en el subcapítulo | 3.822 | 13 | 0,26 | 8,90 | 91,10 | 2 |
| A11 | compra (FORMA=1, inferido) | 3.809 | 0 | 0,00 | 0,00 | 100,00 | 2 |
| B11 | cualquier registro en el subcapítulo | 3.820 | 11 | 0,18 | 6,17 | 93,83 | 4 |
| B11 | compra (FORMA=1, inferido) | 3.809 | 0 | 0,00 | 0,00 | 100,00 | 4 |
| B12 | cualquier registro en el subcapítulo | 400 | 34 | 6,77 | 0,79 | 99,21 | 0 |
| B12 | compra (FORMA=1, inferido) | 366 | 0 | 0,00 | 0,00 | 100,00 | 0 |
| C11 | cualquier registro en el subcapítulo | 1.785 | 16 | 0,82 | 0,80 | 99,20 | 1 |
| C11 | compra (FORMA=1, inferido) | 1.769 | 0 | 0,00 | 0,00 | 100,00 | 1 |
| C12 | cualquier registro en el subcapítulo | 1.683 | 34 | 1,83 | 1,29 | 98,71 | 4 |
| C12 | compra (FORMA=1, inferido) | 1.649 | 0 | 0,00 | 0,00 | 100,00 | 4 |
| D11 | cualquier registro en el subcapítulo | 1.409 | 93 | 6,05 | 3,60 | 96,40 | 0 |
| D11 | compra (FORMA=1, inferido) | 1.316 | 0 | 0,00 | 0,00 | 100,00 | 0 |
| D12 | cualquier registro en el subcapítulo | 1.633 | 130 | 8,01 | 5,71 | 94,29 | 1 |
| D12 | compra (FORMA=1, inferido) | 1.503 | 0 | 0,00 | 0,00 | 100,00 | 1 |
| D13 | cualquier registro en el subcapítulo | 620 | 37 | 5,61 | 1,15 | 98,85 | 1 |
| D13 | compra (FORMA=1, inferido) | 583 | 0 | 0,00 | 0,00 | 100,00 | 1 |
| D14 | cualquier registro en el subcapítulo | 611 | 45 | 7,60 | 1,54 | 98,46 | 1 |
| D14 | compra (FORMA=1, inferido) | 566 | 0 | 0,00 | 0,00 | 100,00 | 1 |
| D15 | cualquier registro en el subcapítulo | 318 | 26 | 7,12 | 0,67 | 99,33 | 0 |
| D15 | compra (FORMA=1, inferido) | 292 | 0 | 0,00 | 0,00 | 100,00 | 0 |
| D16 | cualquier registro en el subcapítulo | 785 | 43 | 5,66 | 1,42 | 98,58 | 2 |
| D16 | compra (FORMA=1, inferido) | 742 | 0 | 0,00 | 0,00 | 100,00 | 2 |
| E11 | cualquier registro en el subcapítulo | 1.318 | 22 | 1,68 | 0,89 | 99,11 | 2 |
| E11 | compra (FORMA=1, inferido) | 1.295 | 0 | 0,00 | 0,00 | 100,00 | 3 |
| E12 | cualquier registro en el subcapítulo | 1.966 | 39 | 1,82 | 1,88 | 98,12 | 9 |
| E12 | compra (FORMA=1, inferido) | 1.927 | 0 | 0,00 | 0,00 | 100,00 | 9 |
| F11 | cualquier registro en el subcapítulo | 2.453 | 84 | 3,55 | 5,59 | 94,41 | 12 |
| F11 | compra (FORMA=1, inferido) | 2.369 | 0 | 0,00 | 0,00 | 100,00 | 12 |
| F12 | cualquier registro en el subcapítulo | 686 | 43 | 5,65 | 1,28 | 98,72 | 2 |
| F12 | compra (FORMA=1, inferido) | 643 | 0 | 0,00 | 0,00 | 100,00 | 2 |
| F13 | cualquier registro en el subcapítulo | 812 | 134 | 16,42 | 4,29 | 95,71 | 1 |
| F13 | compra (FORMA=1, inferido) | 678 | 0 | 0,00 | 0,00 | 100,00 | 1 |
| G11 | cualquier registro en el subcapítulo | 808 | 65 | 7,59 | 1,99 | 98,01 | 4 |
| G11 | compra (FORMA=1, inferido) | 743 | 0 | 0,00 | 0,00 | 100,00 | 4 |
| G12 | cualquier registro en el subcapítulo | 1.253 | 89 | 6,54 | 3,10 | 96,90 | 1 |
| G12 | compra (FORMA=1, inferido) | 1.164 | 0 | 0,00 | 0,00 | 100,00 | 1 |
| G13 | cualquier registro en el subcapítulo | 517 | 53 | 9,72 | 1,52 | 98,48 | 0 |
| G13 | compra (FORMA=1, inferido) | 464 | 0 | 0,00 | 0,00 | 100,00 | 0 |
| G14 | cualquier registro en el subcapítulo | 509 | 50 | 9,28 | 1,44 | 98,56 | 2 |
| G14 | compra (FORMA=1, inferido) | 459 | 0 | 0,00 | 0,00 | 100,00 | 2 |
| H11 | cualquier registro en el subcapítulo | 1.732 | 12 | 0,62 | 0,51 | 99,49 | 7 |
| H11 | compra (FORMA=1, inferido) | 1.720 | 0 | 0,00 | 0,00 | 100,00 | 7 |
| H12 | cualquier registro en el subcapítulo | 956 | 70 | 7,20 | 2,32 | 97,68 | 0 |
| H12 | compra (FORMA=1, inferido) | 886 | 0 | 0,00 | 0,00 | 100,00 | 0 |
| I11 | cualquier registro en el subcapítulo | 738 | 3 | 0,34 | 0,09 | 99,91 | 2 |
| I11 | compra (FORMA=1, inferido) | 735 | 0 | 0,00 | 0,00 | 100,00 | 2 |
| I12 | cualquier registro en el subcapítulo | 1.114 | 4 | 0,31 | 0,14 | 99,86 | 2 |
| I12 | compra (FORMA=1, inferido) | 1.110 | 0 | 0,00 | 0,00 | 100,00 | 2 |
| J11 | cualquier registro en el subcapítulo | 1.644 | 75 | 4,37 | 3,21 | 96,79 | 9 |
| J11 | compra (FORMA=1, inferido) | 1.569 | 0 | 0,00 | 0,00 | 100,00 | 9 |
| J12 | cualquier registro en el subcapítulo | 453 | 41 | 8,53 | 1,26 | 98,74 | 2 |
| J12 | compra (FORMA=1, inferido) | 412 | 0 | 0,00 | 0,00 | 100,00 | 2 |
| J13 | cualquier registro en el subcapítulo | 207 | 12 | 4,67 | 0,30 | 99,70 | 6 |
| J13 | compra (FORMA=1, inferido) | 195 | 0 | 0,00 | 0,00 | 100,00 | 6 |
| L11 | cualquier registro en el subcapítulo | 460 | 1 | 0,15 | 0,02 | 99,98 | 8 |
| L11 | compra (FORMA=1, inferido) | 459 | 0 | 0,00 | 0,00 | 100,00 | 8 |
| L12 | cualquier registro en el subcapítulo | 946 | 286 | 29,12 | 8,65 | 91,35 | 17 |
| L12 | compra (FORMA=1, inferido) | 660 | 0 | 0,00 | 0,00 | 100,00 | 17 |

«Base de compra» se reporta de dos formas porque FORMA (forma de adquisición) tiene códigos INFERIDOS (1 = compra; el cuadernillo lista las formas por letra, sin imprimir los números): (1) cualquier registro del hogar en el subcapítulo, que no depende de FORMA, y (2) registro con FORMA = 1. Si ambas coinciden en lo sustantivo, el supuesto sobre FORMA no pesa. Es un cruce entre dos tablas del mismo cuadernillo; no verifica que los registros de artículos estén completos.

Archivo: `outputs/distribuciones/enph_p438_vacios.csv`


### ENPH · COBERTURA FALTANTE de la matriz categoría × medio de pago: subcapítulos J14 y K11

- **fuente:** ENPH 2016-2017, hogares/gastos_menos_frecuentes_medio_pago.csv
- **dominio:** Bogotá (DOMINIO = 'BOGOTÁ'), hogares
- **unidad:** hogar
- **peso:** FEX = FEX_C (factor del hogar; verificado, docs/fuentes_datos.md §4)
- **codigos:** Cuadernillo 3.pdf, pregunta (6) de cada subcapítulo (NO es el esquema de NC2R_CC_P6)
- **enunciado:** % de HOGARES (entre los que respondieron el subcapítulo) cuyo medio de pago principal en ese subcapítulo es X
- **denominador:** % de hogares de Bogotá (expandido con FEX_C) con al menos un registro de artículos en el subcapítulo

| cap_en_articulos | columna_p438 | n_hogares_con_registros | hogares_expandidos | pct_hogares_bogota |
|---|---|---|---|---|
| J14 | NO EXISTE | 910 | 617.374,10 | 24,16 |
| K11 | NO EXISTE | 574 | 352.582,59 | 13,80 |

**Limitación del instrumento (declarar en la tesis).** La matriz categoría × medio de pago (`enph_p438_matriz_categoria_x_medio`) NO cubre los subcapítulos J14, K11: la base de artículos tiene registros en ellos, pero `gastos_menos_frecuentes_medio_pago` no trae columna P438 para ninguno (en el Cuadernillo 3 la pregunta (6) existe, pero el medio de pago no llegó a la base publicada). Hogares de Bogotá afectados (con registros en el subcapítulo): J14: 24,16 % (910 hogares en la muestra); K11: 13,80 % (574 hogares en la muestra); en conjunto, el 31,92 % de los hogares tiene al menos un registro en uno de los dos. Para esas categorías el generador no tiene medio de pago observado y no debe inventarse desde otro subcapítulo sin declararlo. GAP ABIERTO: la base de artículos (CAP) tiene los subcapítulos J11-J14 y K11, pero P438 solo tiene J11, J12, J13 y ninguna columna K: no existen P438J14 ni P438K11 (los hogares con compras en J14/K11 no tienen medio de pago en la base). Además, la correspondencia de P438J13 con un bloque concreto del Cuadernillo 3 (3.J131 / 3.J13 / 3.J132) no está verificada.

Archivo: `outputs/distribuciones/enph_p438_gaps.csv`


### GEIH · estrato agrupado del hogar (1-2 / 3-4 / 5-6)

- **fuente:** GEIH 2025, datos_hogar.csv
- **dominio:** Bogotá urbano (AREA = 11), 12 meses apilados
- **unidad:** hogar (promedio anual)
- **peso:** FEX = FEX_C18 / 12
- **variable:** P4030S1A1 «Estrato para tarifa»
- **codigos:** Diccionario GEIH 2025, fila 32 (P4030S1A1; rango 0-6 ó 9; sin etiquetas para 0 y 9)
- **denominador:** «% base con respuesta» = hogares con estrato 1-6; «% del total» = todos los hogares de Bogotá

| codigo | categoria | n (sin ponderar) | expandido | % base con respuesta | % del total |
|---|---|---|---|---|---|
| bajo (1-2) | bajo (1-2) | 4.671 | 1.481.139,99 | 47,26 | 47,16 |
| medio (3-4) | medio (3-4) | 4.444 | 1.440.189,37 | 45,96 | 45,86 |
| alto (5-6) | alto (5-6) | 601 | 212.376,11 | 6,78 | 6,76 |
| 0 | sin dato: 0 (sin etiqueta en el diccionario GEIH) | 17 | 6.937,19 | — | 0,22 |

Los códigos 0 y 9 no se asignan a ningún grupo (el diccionario GEIH no los etiqueta).

Archivo: `outputs/distribuciones/geih_estrato_agrupado.csv`


### GEIH · estrato para tarifa, sin agrupar

- **fuente:** GEIH 2025, datos_hogar.csv
- **dominio:** Bogotá urbano (AREA = 11), 12 meses apilados
- **unidad:** hogar (promedio anual)
- **peso:** FEX = FEX_C18 / 12
- **variable:** P4030S1A1
- **codigos:** Diccionario GEIH 2025, fila 32 (P4030S1A1; rango 0-6 ó 9; sin etiquetas para 0 y 9)

| codigo | categoria | n (sin ponderar) | expandido | % base con respuesta | % del total |
|---|---|---|---|---|---|
| 1 | Estrato 1 | 836 | 255.538,27 | 8,15 | 8,14 |
| 2 | Estrato 2 | 3.835 | 1.225.601,72 | 39,11 | 39,02 |
| 3 | Estrato 3 | 3.333 | 1.068.018,21 | 34,08 | 34,01 |
| 4 | Estrato 4 | 1.111 | 372.171,16 | 11,88 | 11,85 |
| 5 | Estrato 5 | 357 | 122.319,30 | 3,90 | 3,89 |
| 6 | Estrato 6 | 244 | 90.056,81 | 2,87 | 2,87 |
| 0 | sin dato: 0 (sin etiqueta en el diccionario GEIH) | 17 | 6.937,19 | — | 0,22 |

Archivo: `outputs/distribuciones/geih_estrato_detalle.csv`


### GEIH · posición ocupacional de los ocupados (P6430)

- **fuente:** GEIH 2025, ocupados.csv
- **dominio:** Bogotá urbano (AREA = 11), 12 meses apilados
- **unidad:** persona ocupada
- **peso:** FEX = FEX_C18 / 12
- **variable:** P6430 «En este trabajo … es»
- **codigos:** Diccionario GEIH 2025, filas 708-715
- **denominador:** ocupados de Bogotá con P6430

| codigo | categoria | n (sin ponderar) | expandido | % base con respuesta | % del total |
|---|---|---|---|---|---|
| 1 | Obrero o empleado de empresa particular | 7.901 | 2.537.778,39 | 58,87 | 58,87 |
| 2 | Obrero o empleado del gobierno | 573 | 186.650,83 | 4,33 | 4,33 |
| 3 | Empleado doméstico | 400 | 115.666,92 | 2,68 | 2,68 |
| 4 | Trabajador por cuenta propia | 4.205 | 1.316.826,16 | 30,55 | 30,55 |
| 5 | Patrón o empleador | 363 | 119.283,28 | 2,77 | 2,77 |
| 6 | Trabajador familiar sin remuneración | 105 | 32.953,48 | 0,76 | 0,76 |
| 7 | Jornalero o peón | 1 | 200,58 | 0,00 | 0,00 |
| 8 | Otro | 4 | 1.257,24 | 0,03 | 0,03 |

El diccionario menciona «P6430 = 9» en la regla de P6430S1 (fila 716) pero no lista el código 9 entre las categorías; aquí cualquier código fuera de 1-8 se reporta como «código fuera de lista».

Archivo: `outputs/distribuciones/geih_posicion_ocupacional.csv`


### GEIH · componentes de formalidad laboral (contrato, pensión, ARL)

- **fuente:** GEIH 2025, ocupados.csv
- **dominio:** Bogotá urbano (AREA = 11), 12 meses apilados
- **unidad:** persona ocupada
- **peso:** FEX = FEX_C18 / 12
- **variable:** P6440 (tiene contrato), P6450 (verbal/escrito), P6920 (cotiza a pensión), P6990 (afiliado a ARL)
- **codigos:** Diccionario GEIH 2025, filas 680-684 (P6440/P6450), 983-985 (P6920), 995-997 (P6990); P6450: 1 Verbal, 2 Escrito, 9 No sabe (NO 3)
- **denominador:** P6450: «% base con respuesta» = con contrato y P6450 en {1,2}; P6990 y P6920: ocupados con respuesta válida

| variable | codigo | categoria | n (sin ponderar) | expandido | % base con respuesta | % del total |
|---|---|---|---|---|---|---|
| P6440 | 1 | Sí | 9.869 | 3.159.615,55 | 73,30 | 73,30 |
| P6440 | 2 | No | 3.683 | 1.151.001,32 | 26,70 | 26,70 |
| P6450 | 1 | Verbal | 2.008 | 622.776,94 | 19,71 | 14,45 |
| P6450 | 2 | Escrito | 7.861 | 2.536.838,60 | 80,29 | 58,85 |
| P6450 |  | sin dato (vacío) | 3.683 | 1.151.001,32 | — | 26,70 |
| P6920 | 1 | Sí | 8.541 | 2.762.180,49 | 64,08 | 64,08 |
| P6920 | 2 | No | 4.630 | 1.439.647,06 | 33,40 | 33,40 |
| P6920 | 3 | Ya es pensionado | 381 | 108.789,31 | 2,52 | 2,52 |
| P6990 | 1 | Sí | 8.357 | 2.696.865,76 | 62,59 | 62,56 |
| P6990 | 2 | No | 5.189 | 1.611.787,96 | 37,41 | 37,39 |
| P6990 | 9 | sin dato: No sabe, no informa | 6 | 1.963,15 | — | 0,05 |

No se define aquí una variable «formal/informal» compuesta: es decisión metodológica pendiente (cada componente se reporta por separado). P6450 vacío ⇔ P6440 = 2 (sin contrato, no aplica) en 13.552 de 13.552 ocupados-mes.

Archivo: `outputs/distribuciones/geih_formalidad_componentes.csv`


### GEIH · posición ocupacional × cotiza a pensión (% dentro de cada posición)

- **fuente:** GEIH 2025, ocupados.csv
- **dominio:** Bogotá urbano (AREA = 11), 12 meses apilados
- **unidad:** persona ocupada
- **peso:** FEX = FEX_C18 / 12
- **variable:** P6430 × P6920
- **denominador:** ocupados con P6920 válido, dentro de cada posición

| P6430 | posicion | P6920 | cotiza_pension | n | expandido | pct_dentro_de_posicion |
|---|---|---|---|---|---|---|
| 1 | Obrero o empleado de empresa particular | 1 | Sí | 6.418 | 2.074.660,90 | 81,75 |
| 1 | Obrero o empleado de empresa particular | 2 | No | 1.388 | 436.078,60 | 17,18 |
| 1 | Obrero o empleado de empresa particular | 3 | Ya es pensionado | 95 | 27.038,89 | 1,07 |
| 2 | Obrero o empleado del gobierno | 1 | Sí | 558 | 182.538,22 | 97,80 |
| 2 | Obrero o empleado del gobierno | 3 | Ya es pensionado | 15 | 4.112,61 | 2,20 |
| 3 | Empleado doméstico | 1 | Sí | 160 | 47.261,41 | 40,86 |
| 3 | Empleado doméstico | 2 | No | 211 | 60.834,37 | 52,59 |
| 3 | Empleado doméstico | 3 | Ya es pensionado | 29 | 7.571,14 | 6,55 |
| 4 | Trabajador por cuenta propia | 1 | Sí | 1.245 | 403.503,89 | 30,64 |
| 4 | Trabajador por cuenta propia | 2 | No | 2.751 | 853.459,41 | 64,81 |
| 4 | Trabajador por cuenta propia | 3 | Ya es pensionado | 209 | 59.862,86 | 4,55 |
| 5 | Patrón o empleador | 1 | Sí | 149 | 50.728,09 | 42,53 |
| 5 | Patrón o empleador | 2 | No | 187 | 60.156,04 | 50,43 |
| 5 | Patrón o empleador | 3 | Ya es pensionado | 27 | 8.399,15 | 7,04 |
| 6 | Trabajador familiar sin remuneración | 1 | Sí | 10 | 3.154,73 | 9,57 |
| 6 | Trabajador familiar sin remuneración | 2 | No | 89 | 27.994,07 | 84,95 |
| 6 | Trabajador familiar sin remuneración | 3 | Ya es pensionado | 6 | 1.804,67 | 5,48 |
| 7 | Jornalero o peón | 2 | No | 1 | 200,58 | 100,00 |
| 8 | Otro | 1 | Sí | 1 | 333,24 | 26,51 |
| 8 | Otro | 2 | No | 3 | 924,00 | 73,49 |

**Celdas pequeñas e inestables (declarado; no requiere acción).** 8 de 20 celdas tienen menos de 30 ocupados (sin ponderar) y varias posiciones (familiar sin remuneración, jornalero, otro, y en parte patrón y empleado doméstico) tienen pocos casos: sus % dentro de la posición se mueven más de 1 p.p. al quitar un solo mes (ver las sensibilidades sin julio y sin marzo). No se usan como insumo de calibración; se reportan de forma descriptiva.

Archivo: `outputs/distribuciones/geih_posicion_x_pension.csv`


### GEIH · ingreso laboral individual del ocupado (INGLABO), grupos del 20 % de los ocupados con ingreso

- **fuente:** GEIH 2025, ocupados.csv
- **dominio:** Bogotá urbano (AREA = 11), 12 meses apilados
- **unidad:** persona ocupada
- **peso:** FEX = FEX_C18 / 12
- **variable:** INGLABO: ingreso laboral de la PERSONA (no es ingreso del hogar; no comparable con ICGU; estos grupos NO son quintiles de ingreso)
- **cortes:** menor INGLABO con F ponderada ≥ j/5: 1.300.000, 1.500.000, 2.000.000, 3.700.000
- **denominador:** ocupados con INGLABO informado (sin INGLABO: 442 de 13.552 ocupados-mes)

| grupo | n | expandido | pct_ocupados_con_ingreso | inglabo_min | inglabo_max | pct_cotiza_pension |
|---|---|---|---|---|---|---|
| G1 | 3.029 | 924.387,02 | 22,20 | 0 | 1.300.000 | 12,93 |
| G2 | 2.724 | 838.592,67 | 20,14 | 1.320.000 | 1.500.000 | 73,34 |
| G3 | 2.728 | 855.598,83 | 20,55 | 1.503.500 | 2.000.000 | 71,20 |
| G4 | 2.229 | 715.848,99 | 17,20 | 2.010.000 | 3.700.000 | 82,24 |
| G5 | 2.400 | 828.615,76 | 19,90 | 3.750.000 | 103.000.000 | 90,13 |

Archivo: `outputs/distribuciones/geih_ingreso_laboral_individual.csv`


### GEIH · sensibilidad a diciembre (12 meses vs. sin diciembre (ene-nov, FEX_C18/11))

- **Regla (CLAUDE.md):** cada distribución GEIH se calcula con los 12 meses y con el conjunto alterno; se reporta toda diferencia > 1,0 p.p.
- **Comparaciones:** 86 (tabla × categoría × medida) · **con |diferencia| > 1,0 p.p.: 4** · máx. |dif| = 4,40 p.p.
- **Ocupados Bogotá:** 12 meses = 13.552 filas; alterno = 12.405 filas.

| tabla | categoria | medida | v12 | valt | dif_pp_12_menos_alt |
|---|---|---|---|---|---|
| geih_ingreso_laboral_individual | G1 | pct_ocupados_con_ingreso | 22,20 | 20,16 | 2,05 |
| geih_ingreso_laboral_individual | G2 | pct_ocupados_con_ingreso | 20,14 | 22,53 | -2,39 |
| geih_ingreso_laboral_individual | G1 | pct_cotiza_pension | 12,93 | 8,53 | 4,40 |
| geih_ingreso_laboral_individual | G2 | pct_cotiza_pension | 73,34 | 71,41 | 1,93 |

Cortes de INGLABO (relativos, %; no son p.p.):

| corte | inglabo_12 | inglabo_alt | dif_relativa_% |
|---|---|---|---|
| c1 | 1.300.000 | 1.200.000 | 8,33 |
| c2 | 1.500.000 | 1.500.000 | 0,00 |
| c3 | 2.000.000 | 2.000.000 | 0,00 |
| c4 | 3.700.000 | 3.600.000 | 2,78 |

**Lectura.** Todas las diferencias > 1,0 p.p. están en los grupos de INGLABO y coinciden con un corte que se mueve entre 12 meses y sin diciembre (ene-nov, FEX_C18/11). En INGLABO = 1.200.000: F ponderada = 19,87 % con 12 meses y 20,16 % sin diciembre (ene-nov, FEX_C18/11), y ese valor concentra 2,30 % / 2,35 % del peso (ingreso redondeado). Es un efecto de frontera sobre un ingreso amontonado en valores redondos, no un cambio de composición (ver «Fronteras y amontonamiento»); las demás distribuciones no se mueven más de 1 p.p.

Archivo: `outputs/distribuciones/geih_sensibilidad_diciembre.csv`


### GEIH · sensibilidad a julio (12 meses vs. sin julio (11 meses, FEX_C18/11))

- **Regla (CLAUDE.md):** cada distribución GEIH se calcula con los 12 meses y con el conjunto alterno; se reporta toda diferencia > 1,0 p.p.
- **Comparaciones:** 86 (tabla × categoría × medida) · **con |diferencia| > 1,0 p.p.: 7** · máx. |dif| = 4,45 p.p.
- **Ocupados Bogotá:** 12 meses = 13.552 filas; alterno = 12.391 filas.

| tabla | categoria | medida | v12 | valt | dif_pp_12_menos_alt |
|---|---|---|---|---|---|
| geih_posicion_x_pension | Empleado doméstico | Sí | pct_dentro_de_posicion | 40,86 | 39,00 | 1,86 |
| geih_posicion_x_pension | Empleado doméstico | No | pct_dentro_de_posicion | 52,59 | 54,77 | -2,17 |
| geih_posicion_x_pension | Patrón o empleador | Sí | pct_dentro_de_posicion | 42,53 | 41,14 | 1,39 |
| geih_ingreso_laboral_individual | G1 | pct_ocupados_con_ingreso | 22,20 | 20,01 | 2,20 |
| geih_ingreso_laboral_individual | G2 | pct_ocupados_con_ingreso | 20,14 | 22,45 | -2,30 |
| geih_ingreso_laboral_individual | G1 | pct_cotiza_pension | 12,93 | 8,48 | 4,45 |
| geih_ingreso_laboral_individual | G2 | pct_cotiza_pension | 73,34 | 70,76 | 2,58 |

Cortes de INGLABO (relativos, %; no son p.p.):

| corte | inglabo_12 | inglabo_alt | dif_relativa_% |
|---|---|---|---|
| c1 | 1.300.000 | 1.200.000 | 8,33 |
| c2 | 1.500.000 | 1.500.000 | 0,00 |
| c3 | 2.000.000 | 2.000.000 | 0,00 |
| c4 | 3.700.000 | 3.700.000 | 0,00 |

**Lectura.** Hay diferencias > 1 p.p. fuera de los grupos de INGLABO o sin un corte desplazado: revisar antes de fijar priors.

Archivo: `outputs/distribuciones/geih_sensibilidad_julio.csv`


### GEIH · sensibilidad a marzo (12 meses vs. sin marzo (11 meses, FEX_C18/11))

- **Regla (CLAUDE.md):** cada distribución GEIH se calcula con los 12 meses y con el conjunto alterno; se reporta toda diferencia > 1,0 p.p.
- **Comparaciones:** 86 (tabla × categoría × medida) · **con |diferencia| > 1,0 p.p.: 2** · máx. |dif| = 3,05 p.p.
- **Ocupados Bogotá:** 12 meses = 13.552 filas; alterno = 12.434 filas.

| tabla | categoria | medida | v12 | valt | dif_pp_12_menos_alt |
|---|---|---|---|---|---|
| geih_posicion_x_pension | Patrón o empleador | Sí | pct_dentro_de_posicion | 42,53 | 45,16 | -2,64 |
| geih_posicion_x_pension | Patrón o empleador | No | pct_dentro_de_posicion | 50,43 | 47,39 | 3,05 |

Cortes de INGLABO (relativos, %; no son p.p.):

| corte | inglabo_12 | inglabo_alt | dif_relativa_% |
|---|---|---|---|
| c1 | 1.300.000 | 1.300.000 | 0,00 |
| c2 | 1.500.000 | 1.500.000 | 0,00 |
| c3 | 2.000.000 | 2.000.000 | 0,00 |
| c4 | 3.700.000 | 3.800.000 | -2,63 |

**Lectura.** Hay diferencias > 1 p.p. fuera de los grupos de INGLABO o sin un corte desplazado: revisar antes de fijar priors.

Archivo: `outputs/distribuciones/geih_sensibilidad_marzo.csv`


### Fronteras de grupo y amontonamiento en valores redondos (LIMITACIÓN)

- **Qué se mide:** para cada frontera de los grupos del 20 % (4 por variable), el % del peso que cae EXACTAMENTE en el valor de la frontera (`masa_en_el_valor_pct`) y en qué punto de ese montón cae el percentil objetivo (`fraccion_del_monton_bajo_objetivo`: 0 = al inicio, 1 = al final).
- **Máximo % de masa en un solo valor:** ICGU (ENPH, hogares, Bogotá): 0,09 %; INGLABO (GEIH, ocupados, Bogotá): 5,92 %.
- **Limitación declarada (aplica a INGLABO, NO a ICGU: en ICGU ninguna frontera concentra más del 0,1 % del peso):** el ingreso laboral individual se reporta en valores redondos, por lo que la frontera de un grupo del 20 % cae DENTRO de un montón: el percentil objetivo se alcanza en medio de un valor que reúne varios puntos porcentuales de la población, y quién queda en el grupo inferior o superior depende de la regla de desempate (aquí: los iguales al corte van al grupo inferior). Con cualquier perturbación de la muestra o de los pesos, la frontera puede saltar de un valor redondo al siguiente. Los % por grupo no son exactamente 20 y las fronteras no son estables ante cambios de meses. **No se cambió a cortes fijos** (decisión de Sara, 20 sep 2026); se declara como limitación de la calibración por quintil de ingreso.

| variable | escenario | corte | valor | objetivo_pct | masa_bajo_el_valor_pct | masa_en_el_valor_pct | cdf_hasta_el_valor_pct | sobrepaso_pp | n_en_el_valor | fraccion_del_monton_bajo_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|
| INGLABO (GEIH, ocupados, Bogotá) | 12 meses | c1 | 1.300.000 | 20,00 | 20,00 | 2,21 | 22,20 | 2,20 | 291 | 0,00 |
| INGLABO (GEIH, ocupados, Bogotá) | 12 meses | c2 | 1.500.000 | 40,00 | 36,82 | 5,52 | 42,35 | 2,35 | 752 | 0,57 |
| INGLABO (GEIH, ocupados, Bogotá) | 12 meses | c3 | 2.000.000 | 60,00 | 57,03 | 5,87 | 62,90 | 2,90 | 775 | 0,51 |
| INGLABO (GEIH, ocupados, Bogotá) | 12 meses | c4 | 3.700.000 | 80,00 | 79,86 | 0,24 | 80,10 | 0,10 | 30 | 0,60 |
| INGLABO (GEIH, ocupados, Bogotá) | sin diciembre | c1 | 1.200.000 | 20,00 | 17,81 | 2,35 | 20,16 | 0,16 | 282 | 0,93 |
| INGLABO (GEIH, ocupados, Bogotá) | sin diciembre | c2 | 1.500.000 | 40,00 | 37,24 | 5,45 | 42,69 | 2,69 | 673 | 0,51 |
| INGLABO (GEIH, ocupados, Bogotá) | sin diciembre | c3 | 2.000.000 | 60,00 | 57,43 | 5,74 | 63,17 | 3,17 | 691 | 0,45 |
| INGLABO (GEIH, ocupados, Bogotá) | sin diciembre | c4 | 3.600.000 | 80,00 | 79,66 | 0,36 | 80,02 | 0,02 | 39 | 0,95 |
| INGLABO (GEIH, ocupados, Bogotá) | sin julio | c1 | 1.200.000 | 20,00 | 17,72 | 2,29 | 20,01 | 0,01 | 276 | 1,00 |
| INGLABO (GEIH, ocupados, Bogotá) | sin julio | c2 | 1.500.000 | 40,00 | 36,87 | 5,59 | 42,45 | 2,45 | 695 | 0,56 |
| INGLABO (GEIH, ocupados, Bogotá) | sin julio | c3 | 2.000.000 | 60,00 | 57,05 | 5,92 | 62,96 | 2,96 | 713 | 0,50 |
| INGLABO (GEIH, ocupados, Bogotá) | sin julio | c4 | 3.700.000 | 80,00 | 79,78 | 0,23 | 80,01 | 0,01 | 27 | 0,97 |
| INGLABO (GEIH, ocupados, Bogotá) | sin marzo | c1 | 1.300.000 | 20,00 | 19,76 | 2,24 | 21,99 | 1,99 | 272 | 0,11 |
| INGLABO (GEIH, ocupados, Bogotá) | sin marzo | c2 | 1.500.000 | 40,00 | 36,45 | 5,40 | 41,85 | 1,85 | 677 | 0,66 |
| INGLABO (GEIH, ocupados, Bogotá) | sin marzo | c3 | 2.000.000 | 60,00 | 56,55 | 5,92 | 62,47 | 2,47 | 716 | 0,58 |
| INGLABO (GEIH, ocupados, Bogotá) | sin marzo | c4 | 3.800.000 | 80,00 | 79,84 | 0,48 | 80,32 | 0,32 | 54 | 0,33 |
| ICGU (ENPH, hogares, Bogotá) | todos los hogares | c1 | 1.127.000 | 20,00 | 19,98 | 0,05 | 20,03 | 0,03 | 2 | 0,37 |
| ICGU (ENPH, hogares, Bogotá) | todos los hogares | c2 | 1.810.250 | 40,00 | 39,99 | 0,02 | 40,00 | 0,00 | 1 | 0,79 |
| ICGU (ENPH, hogares, Bogotá) | todos los hogares | c3 | 2.766.667 | 60,00 | 59,96 | 0,09 | 60,05 | 0,05 | 2 | 0,49 |
| ICGU (ENPH, hogares, Bogotá) | todos los hogares | c4 | 4.506.283 | 80,00 | 80,00 | 0,02 | 80,02 | 0,02 | 1 | 0,09 |

Archivo: `outputs/distribuciones/fronteras_amontonamiento.csv`


### GEIH · estabilidad mes a mes de las variables que alimentan los priors

- **Qué es:** distribución por mes (FEX_C18 dentro del mes) frente a la de los 12 meses, Bogotá (AREA = 11). Contraste empírico exigido por CLAUDE.md (comparabilidad semántica GEIH 2025).
- **Alcance:** detecta saltos grandes; con ~1.000 ocupados por mes hay ruido muestral de varios p.p. `z_binomial` = desviación / error binomial simple SIN efecto de diseño (subestima el error real: el diseño es por conglomerados). Es evidencia corroborante, NO prueba de que el formulario 2025 sea el de 2024. No incluye P6500 ni P5222S*/medio de pago de GEIH (no se usan en este entregable).
- **Mayor desviación por variable:**

| variable | codigo | mes | n_mes | n_base_mes | pct_mes | pct_12_meses | desv_pp | z_binomial |
|---|---|---|---|---|---|---|---|---|
| P4030S1A1 | medio (3-4) | 7 | 317 | 808 | 38,00 | 45,96 | -7,96 | -4,54 |
| P6430 | 4 | 3 | 388 | 1.118 | 34,50 | 30,55 | 3,95 | 2,87 |
| P6440 | 2 | 3 | 334 | 1.118 | 29,60 | 26,70 | 2,90 | 2,19 |
| P6450 | 1 | 4 | 122 | 797 | 15,22 | 19,71 | -4,49 | -3,19 |
| P6920 | 2 | 3 | 429 | 1.118 | 38,33 | 33,40 | 4,93 | 3,50 |
| P6990 | 1 | 3 | 636 | 1.117 | 56,87 | 62,59 | -5,72 | -3,95 |

Archivo: `outputs/distribuciones/geih_estabilidad_mensual.csv` (todas las categorías × meses).
