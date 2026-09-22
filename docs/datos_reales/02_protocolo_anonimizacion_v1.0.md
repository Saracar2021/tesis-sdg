# Protocolo de anonimización de extractos (Nequi / Daviplata / banco)

> **Versión reemplazada por v1.1; se conserva por trazabilidad.**

**Proyecto:** Datos sintéticos de transacciones financieras — Colombia · **WP4 (Track B)**
**Versión:** 1.0 · **Fecha:** 15 sep 2026

Objetivo: reducir cada extracto a **tres campos por transacción** —descripción, monto, fecha— eliminando en origen todo dato personal, **antes** de que el archivo llegue a la investigadora. La regla rectora es **minimización**: si un dato no es necesario para clasificar el gasto, no se recoge.

---

## 1. Qué se conserva y qué se elimina

**Se conserva (los únicos 3 campos):**

| Campo | Ejemplo | Nota |
|---|---|---|
| `descripcion` | `"Pago Nequi FRUVER LA 68"` | Texto tal cual, tras depurar PII (§2). |
| `monto` | `35000` | En COP, entero. Signo o columna aparte para ingreso/egreso. |
| `fecha` | `2026-08-14` | Solo fecha (`AAAA-MM-DD`); se elimina la hora. |

**Se elimina siempre (nunca sale del dispositivo del voluntario):**
números de cuenta/tarjeta/celular, saldos y cupos, cédula, direcciones, correos, **nombres y apellidos de personas** (titular y contrapartes), referencias/IDs de transacción largos, códigos de autorización, y cualquier metadato del PDF.

## 2. Reglas de depuración de la descripción

La descripción es útil (dice *qué* se compró) pero es el campo con más riesgo. Reglas, en orden:

- **R-A. Nombres de personas → rol o marcador.** `"Transferencia a Juan Pérez Gómez"` → `"Transferencia a PERSONA"`. Si el voluntario declara el propósito, puede anotarse el **rol**, no el nombre: `"Transferencia a PERSONA (arriendo)"`, `"Nequi a PERSONA (mototaxi)"`.
- **R-B. Números largos → `#`.** Celulares, cuentas, referencias: `"Envio Daviplata 3xx-xxx-4521"` → `"Envio Daviplata #"`. Nunca dejar dígitos parciales que sigan siendo identificables.
- **R-C. Comercios formales se conservan.** `"COMPRA EXITO CALLE 80"`, `"FARMATODO"`, `"RAPPI COLOMBIA"`, `"NETFLIX.COM"` se dejan intactos: son la señal que el clasificador debe aprender y no identifican a una persona.
- **R-D. Micronegocios con nombre de persona → genérico.** `"Pago a Barbería Doña Marta"` puede quedar; `"Pago a Marta Sánchez"` → `"Pago a PERSONA (barbería)"` solo si el voluntario declara el rubro. Ante la duda, generalizar.
- **R-E. Ubicación fina → gruesa o fuera.** Barrio/dirección específicos se recortan a ciudad si aportan (`"...CALLE 80"` puede quedar como referencia de sucursal genérica; una dirección residencial se elimina).
- **R-F. Sin adivinar.** Si un texto es ambiguo, se deja tal cual **tras** aplicar R-A/R-B; la clasificación se resuelve en la anotación, no borrando información.

## 3. Ruta recomendada según cómo llegue el extracto

**Preferida — el voluntario transcribe/edita y envía solo los 3 campos** (menor exposición):
1. Exporta o abre su extracto.
2. Copia a una plantilla `.csv`/hoja con columnas `descripcion,monto,fecha` (plantilla en §4).
3. Aplica §2 mientras copia.
4. Envía el `.csv` por el canal seguro.

**Alternativa — envía PDF/imagen y la reducción la hace la investigadora:**
1. El voluntario **tacha visualmente** cuenta, cédula, saldos y nombres antes de enviar.
2. La investigadora transcribe a los 3 campos aplicando §2 y **destruye el PDF/imagen** en ≤15 días (ver consentimiento §7).
3. Menos deseable: más PII transita. Usar solo si el voluntario no puede exportar.

> **Nunca** se pide acceso a la app, credenciales, ni conexión vía agregadores/API bancaria. Solo el extracto que el propio voluntario decide compartir.

## 4. Esquema de salida (insumo para la anotación y para WP8)

Un archivo por voluntario: `data/reales/crudos/<seudonimo>.csv` (p. ej. `V07.csv`), UTF-8, columnas:

```
tx_id,seudonimo,fecha,descripcion,monto,signo
```

- `tx_id`: correlativo dentro del voluntario (`V07-001`). Determinista, sin azar.
- `signo`: `egreso` | `ingreso` (evita perder el sentido del monto).
- Sin encabezados de banco, sin columnas extra.

El seudónimo `Vnn` se asigna en una tabla **cifrada y separada** (`data/reales/_mapa_seudonimos.enc`, fuera del repositorio versionado) que se **destruye al congelar** el conjunto.

## 5. Seguridad operativa

- Canal de envío cifrado / carpeta con acceso restringido; evitar adjuntar el archivo con datos por WhatsApp o correo abierto.
- Repositorio de datos reales **fuera de control de versiones público** (añadir `data/reales/` a `.gitignore`).
- Acceso limitado a investigadora + 2 anotadores, todos con compromiso de confidencialidad.
- Registro simple de recepción/borrado de originales (fecha de recepción, fecha de destrucción del PDF).

## 6. Riesgos metodológicos y de privacidad (de frente)

- **Seudonimización ≠ anonimización.** Mientras exista el mapa `Vnn → persona`, el dato sigue siendo personal bajo la Ley 1581. La anonimización real solo se logra al **destruir el mapa**; hasta entonces aplican todos los deberes y el derecho de retiro total.
- **Re-identificación residual.** Con 15–20 personas, un perfil de gasto puede ser único (k-anonimato no garantizado). Mitigación: no difundir crudo, reportar agregado, prohibir intentos de re-identificación. Declararlo como limitación en la tesis.
- **Fuga por transcripción manual.** El voluntario puede olvidar tachar un nombre. Mitigación: revisión de la investigadora al ingresar cada archivo (barrido por dígitos largos y mayúsculas sospechosas) antes de mover a `crudos`.
- **Datos de terceros.** Las contrapartes no consintieron; por eso sus nombres se eliminan siempre (R-A) y solo se conserva el rol si el voluntario lo declara.
- **FEX no aplica aquí.** Los factores de expansión son para los microdatos DANE (muestra probabilística). Estas 300 tx son una **muestra por conveniencia**: no se les aplican ponderadores ni se presentan como cifras poblacionales; son un **conjunto de validación** (TSTR), no una estimación de Colombia.
