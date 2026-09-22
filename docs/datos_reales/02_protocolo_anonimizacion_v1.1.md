# Protocolo de anonimización de extractos

**Proyecto:** Datos sintéticos de transacciones financieras — Bogotá · **Chat 02 (Track B)**
**Versión:** 1.1 · **Fecha:** 21 sep 2026 · reemplaza la v1.0 del 15 de septiembre

**Qué cambia frente a la v1.0:** el formato principal pasa a ser el **PDF del banco** (la v1.0 lo trataba como alternativa), con capturas y Excel/CSV también admitidos; son **tres meses fijos por persona**; y la reducción la hace **la investigadora en su computador con un script local**, con revisión manual obligatoria. Las rutas se alinean con `CLAUDE.md`.

Objetivo: reducir cada extracto a **tres campos por movimiento** —descripción, monto, fecha— eliminando todo dato personal, y garantizar que **ningún extracto original llegue a una herramienta de IA ni al repositorio**.

---

## 1. Principio operativo

| Etapa | Dónde vive | Quién lo toca |
|---|---|---|
| Original (PDF, captura, Excel) | `data/reales_crudos/originales/` | Solo Sara. Claude Code tiene la lectura **bloqueada** por permisos |
| Mapa seudónimo → persona | `data/reales_crudos/_mapa_seudonimos` (cifrado) | Solo Sara. Se destruye el 4 oct |
| Extracción sin depurar | `data/reales_crudos/extraido/` | Solo Sara |
| **Versión anonimizada** (3 campos) | `data/reales_anon/<seudonimo>.csv` | Sara, anotadores y Claude Code |

`data/` está en `.gitignore`: **nada de esto se sube a GitHub**.

Es el mismo patrón que con los microdatos del DANE: **Claude Code escribe el script, Sara lo ejecuta** sobre los originales, y Claude solo ve el resultado anonimizado.

## 2. Qué se conserva y qué se elimina

**Se conserva:**

| Campo | Ejemplo | Nota |
|---|---|---|
| `descripcion` | `COMPRA EXITO CALLE 80` | Tras aplicar las reglas de §3 |
| `monto` | `35000` | COP, entero, siempre positivo |
| `signo` | `egreso` / `ingreso` | Separado del monto para no perder el sentido |
| `fecha` | `2026-08-14` | Sin hora |

**Se elimina siempre:** nombre, cédula, dirección, correo y celular del titular; números de cuenta, tarjeta y referencia; códigos de autorización; saldos y cupos; **nombres de contrapartes (terceros)**; encabezados, pies y metadatos del documento.

## 3. Reglas de depuración de la descripción

Se aplican en orden. Las R-A y R-B las hace el script; **la revisión manual (§5) las verifica todas**.

- **R-A. Nombres de personas → `PERSONA`.** `TRANSFERENCIA A JUAN PEREZ GOMEZ` → `TRANSFERENCIA A PERSONA`. Si el voluntario declara el propósito, se anota el rol en una columna aparte, nunca el nombre.
- **R-B. Secuencias de 6 o más dígitos → `#`.** Celulares, cuentas, referencias: `ENVIO DAVIPLATA 3001234521` → `ENVIO DAVIPLATA #`. No se dejan dígitos parciales.
- **R-C. Comercios se conservan intactos.** `FARMATODO`, `RAPPI COLOMBIA`, `NETFLIX.COM`: son la señal que el clasificador debe aprender y no identifican a nadie.
- **R-D. Negocio con nombre de persona → genérico.** `PAGO A MARTA SANCHEZ` → `PAGO A PERSONA`. Ante la duda, generalizar.
- **R-E. Direcciones residenciales → fuera.** Las referencias de sucursal comercial (`CALLE 80`) pueden quedar.
- **R-F. No adivinar ni borrar información útil.** Lo ambiguo se deja tal cual tras aplicar R-A y R-B; la clasificación se resuelve en la anotación.

## 4. Flujo por formato

### 4.1 PDF del banco (formato principal)
1. El voluntario descarga el extracto de cada mes y lo envía por el canal seguro (§6). No necesita tachar nada.
2. Si tiene contraseña, la quita antes (imprimir a PDF) o la envía **por un canal distinto** al archivo.
3. Sara guarda el PDF en `data/reales_crudos/originales/<seudonimo>/` y registra la fecha de recepción.
4. Sara corre `tools/anonimizar_extractos.py`, que extrae la tabla de movimientos, aplica R-A y R-B y escribe el borrador en `data/reales_crudos/extraido/`.
5. Revisión manual (§5), luego se mueve a `data/reales_anon/`.
6. **El PDF se borra a más tardar 15 días después de recibido**, y se registra la fecha de borrado.

### 4.2 Excel o CSV exportado
Igual que el PDF desde el paso 3. Es el formato más fácil de procesar.

### 4.3 Capturas de pantalla
Transcripción manual de Sara a la plantilla de §7, aplicando §3 mientras copia. No se usa OCR en la nube. Las capturas se borran igual que los PDF.

> **Nunca** se pide acceso a la aplicación, credenciales ni conexión por API o agregadores bancarios.

## 5. Revisión manual obligatoria (antes de mover a `reales_anon/`)

Por cada archivo, Sara verifica:

- [ ] Ninguna secuencia de 6 o más dígitos quedó sin reemplazar.
- [ ] Ningún nombre propio de persona quedó en transferencias, envíos o pagos a personas.
- [ ] El nombre del titular no aparece en ninguna línea.
- [ ] El número de filas coincide con el número de movimientos del original.
- [ ] Los meses son los tres acordados.
- [ ] Se registró cuántos movimientos excluyó el voluntario a petición propia (solo el número).

El script produce un **reporte de sospechas** (líneas con palabras en mayúscula seguidas que no son comercios conocidos, dígitos residuales) para enfocar la revisión. El reporte no reemplaza la revisión.

## 6. Seguridad operativa

- Canal de envío: carpeta compartida con acceso restringido o enlace de subida. **No** WhatsApp ni correo abierto para el archivo.
- Contraseñas de PDF: nunca por el mismo canal del archivo.
- Registro de custodia en `data/reales_crudos/registro_custodia.csv`: seudónimo, mes, fecha de recepción, fecha de borrado del original, número de movimientos excluidos.
- Acceso a `data/reales_anon/`: Sara y los dos anotadores, con compromiso de confidencialidad.
- **El 4 de octubre** se destruye el mapa de seudónimos. Desde ese momento el conjunto queda anonimizado.

## 7. Esquema de salida

`data/reales_anon/<seudonimo>.csv`, UTF-8:

```
tx_id,seudonimo,mes_referencia,fecha,descripcion,monto,signo,cuenta_tipo,proposito_declarado
```

- `tx_id`: `V07-2512-001` (seudónimo, año-mes, correlativo). Determinista.
- `mes_referencia`: `2025-12`, `2026-04` o `2026-08`.
- `cuenta_tipo`: `banco` / `billetera` / `tarjeta_credito`. Ayuda a interpretar el medio de pago.
- `proposito_declarado`: vacío salvo que el voluntario lo diga; nunca un nombre.

## 8. Riesgos (de frente)

- **Seudonimización no es anonimización.** Mientras exista el mapa, los datos siguen siendo personales bajo la Ley 1581 y aplica el retiro total.
- **Reidentificación residual.** Con 20 personas, un patrón de gasto puede ser único. Se mitiga reportando solo agregados y sin publicar el conjunto.
- **El script no detecta todos los nombres.** Por eso la revisión manual es obligatoria y no opcional.
- **Sesgo de selección del voluntario.** Si alguien borra movimientos, el conjunto deja de ser representativo de su gasto. Por eso se pide el extracto completo y se registra el número de exclusiones.
- **Los extractos no ven el efectivo.** Un retiro en cajero es una fila, no las compras que financia. Es una limitación del instrumento (L7 del plan maestro).
- **Los factores de expansión no aplican aquí.** Es una muestra por conveniencia: conjunto de validación, no estimación poblacional.
