# Diseño de la muestra y plan de recolección

**Proyecto:** Datos sintéticos de transacciones financieras — Bogotá · **Chat 02 (Track B)**
**Versión:** 1.1 · **Fecha:** 21 sep 2026 · reemplaza el plan de reclutamiento de la v1.0

Con los 20 voluntarios ya identificados, el problema deja de ser reclutar y pasa a ser **cuánto se recoge, qué se anota y cómo se evita contaminar la evaluación**.

---

## 1. Qué se recoge

| Parámetro | Valor |
|---|---|
| Personas | 20, todas de Bogotá, de distintos estratos e ingresos (declarado por Sara; no verificado) |
| Meses | Diciembre 2025, abril 2026, agosto 2026 (iguales para todos) |
| Cuentas | La principal; dos si la persona usa banco y billetera de forma habitual |
| Formato | PDF (principal), Excel/CSV o capturas |
| Volumen esperado | Del orden de **2.000 a 4.000 movimientos** (20 personas × 3 meses × 1–2 cuentas × 30–60 movimientos). Es una estimación, no un dato |

## 2. Qué se anota: muestra, no todo

Anotar 3.000 movimientos con dos anotadores independientes no cabe en una semana. Se anota una **muestra aleatoria estratificada**:

- **30 movimientos por persona, 10 por mes**, sorteados con semilla fija (`SEED = 42`) → **600 movimientos**.
- Estratificar por persona y mes garantiza que nadie domine el conjunto y que los tres meses estén representados.
- **Ambos anotadores anotan los 600.** A unos 40 segundos por movimiento son cerca de 7 horas por anotador. Si no alcanza el tiempo, el mínimo es un solapamiento de **200 movimientos** anotados por ambos para calcular el Kappa.
- Si una persona tiene menos de 10 movimientos en un mes, se toman todos y se registra.

El sorteo lo hace un script con semilla fija sobre `data/reales_anon/`, así que es reproducible.

## 3. Regla contra la contaminación de la evaluación (importante)

**Los datos reales se usan solo para evaluar. Nunca para calibrar ni ajustar el generador.**

Si los mismos extractos que miden el TSTR sirven también para calibrar montos, frecuencias o categorías del generador, la evaluación queda contaminada: el sintético se parecería al real porque se construyó mirándolo. Por eso:

- El generador se calibra **solo con ENPH y GEIH**.
- Los movimientos no sorteados (~2.400) se pueden describir en la tesis (cuántos retiros, cuántas transferencias a personas), pero **no** alimentan el generador.
- Las ~50 descripciones que se revisan para congelar la taxonomía salen de movimientos **no sorteados**, para no ver de antemano el conjunto de prueba.

> Esto corrige una sugerencia anterior del Chat 00 de usar el corpus sin etiquetar para calibrar distribuciones: habría contaminado el TSTR.

## 4. Calendario

| Fecha | Actividad | Depende de |
|---|---|---|
| Lun 21 sep | Correo a la directora (incluye consulta de ética). Mensaje de sondeo a los 20 voluntarios, **sin pedir datos** (§6) | — |
| Mar 22 – mié 23 | Respuesta sobre ética. Claude Code escribe `tools/anonimizar_extractos.py` y el script de sorteo (sin tocar datos reales) | — |
| Mié 23 | **Si no se requiere aval:** enviar consentimiento v1.1 y pedir los extractos | Ética |
| Jue 24 – dom 27 | Recepción, anonimización y revisión manual | Consentimientos firmados |
| Dom 27 | Revisar ~50 descripciones no sorteadas → insumo para la taxonomía v1.1 | Extractos anonimizados |
| Lun 28 | Congelar taxonomía v1.1. Sorteo de la muestra. Calibración conjunta de anotadores con 20 movimientos no sorteados (no cuentan para el Kappa) | Taxonomía |
| Lun 28 – vie 2 oct | Anotación independiente | Anotadores confirmados |
| Sáb 3 oct | Conciliación, etiquetas gold, Kappa | — |
| **Dom 4 oct** | **Congelar el conjunto real. Destruir el mapa de seudónimos** | — |
| Lun 5 – dom 11 oct | TSTR | Conjunto congelado + sintético |

**Si el programa exige aval de ética**, no se pide ningún extracto hasta tenerlo, y todo el calendario se corre. Ese escenario se lleva al punto de control del viernes 25 con la directora.

## 5. Pendientes para arrancar

- [ ] Respuesta sobre comité de ética
- [ ] Datos de contacto en el consentimiento (correo, teléfono, directora)
- [ ] Canal seguro de envío (carpeta con acceso restringido o enlace de subida)
- [ ] Confirmar los **2 anotadores** y que firmen compromiso de confidencialidad
- [ ] `tools/anonimizar_extractos.py` y script de sorteo (Claude Code)
- [ ] Taxonomía v1.1 congelada antes del lunes 28
- [ ] Actualizar la guía de anotación a la taxonomía v1.1 y a las rutas de `CLAUDE.md` (`data/reales_anon/`)

## 6. Mensaje de sondeo a los voluntarios (para enviar ya, sin pedir datos)

> Hola [nombre]. Te escribo por lo que hablamos de mi tesis de maestría. Estoy construyendo un generador de datos sintéticos de transacciones financieras para Colombia y necesito validarlo con movimientos reales. ¿Seguirías dispuesto(a) a compartir los extractos de tu cuenta de **diciembre de 2025, abril y agosto de 2026**?
>
> Antes de pedirte nada te voy a enviar un consentimiento que explica exactamente qué se usa: solo la descripción, el monto y la fecha de cada movimiento. Tus datos personales y los nombres de las personas a quienes transfieres se eliminan, el archivo original se borra en 15 días, y todo es para uso académico. Si te sirve, puedes mandar el PDF que descargas del banco.
>
> ¿Me confirmas si cuento contigo? Te envío el consentimiento esta semana.

## 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| Aval de ética requerido y lento | Preguntar el lunes; no recolectar antes de tenerlo |
| Menos de 20 personas envían | Con 12–15 personas el conjunto sigue siendo útil; declarar el n final |
| Extractos con muy pocos movimientos (uso intensivo de efectivo) | Es información en sí misma: se registra y se declara |
| Anotadores sin tiempo | Mínimo 200 movimientos en común para el Kappa |
| Todas las personas con perfil parecido | La diversidad de estrato e ingreso es declarada por Sara; registrar estrato aproximado de cada seudónimo, sin más datos |
