# Hoja de calibración — 4 casos sin resolver en la taxonomía v1.1.0

**Sesión:** 26 nov 2026 · A1 + A2 · Pre-registro 05 v1.3 §5

> **Desviación (pre-registro v1.4, §13):** no hubo sesión de calibración antes de anotar. A1 y A2 anotaron los 200
> ítems por separado, sin convenciones previas. Las convenciones de abajo se fijaron **después de anotar, en la
> adjudicación** (26 nov), citando la taxonomía v1.1 y **antes de ver cualquier predicción de los modelos**. Se
> aplicaron a **todos** los ítems de cada caso, también a los que A1 y A2 etiquetaron igual. El κ se calcula con las
> anotaciones originales, sin la corrección.

**Cómo se decide cada convención:**
- Se elige **solo con el texto de la taxonomía v1.1** (regla o definición citada abajo). **Nunca** mirando lo que hace
  el generador sintético.
- Lo que se acuerde se aplica igual en todo el lote, queda escrito aquí y pasa como **hallazgo para la v1.2**.
- ~~En estos casos el κ mide el seguimiento de una convención pactada~~ **(superado, v1.4 §13):** como no hubo
  calibración previa, las anotaciones de estos casos también son independientes. Las convenciones se fijaron
  después, en la adjudicación, y el κ (0,934) se calculó con las anotaciones originales.

Pesos: filas del marco (2.183) · ítems en el test (200) · Σ `peso_muestreo` de esos ítems.

---

### Caso 1 — Reversos y devoluciones (tarjeta, `signo = ingreso`) · marco 6 · test 6 · Σ peso 6
Ej.: «REVERSADA - <comercio>», «ANUL. CONSUMO …», «DEVOLUCION». La taxonomía **no los menciona**.
**Se reportan como subgrupo aparte** (probablemente no existen en el sintético).
- **R1:** «si la descripción identifica el comercio o el bien/servicio, se asigna la categoría del bien».
- **`otros` (definición):** «Transacciones que no encajan en ninguna categoría o cuyo texto es ininteligible».
- **R7:** «Ante ambigüedad irresoluble tras aplicar R1-R6, usar … otros.ininteligible; nunca adivinar».
- `ingreso` (definición) enumera «salario, honorarios, ventas del negocio, subsidios estatales, rendimientos»; no
  menciona reembolsos.

**Convención acordada:** si el reverso identifica el comercio o el bien → categoría de ese bien (**R1**; p. ej.
«ANUL. CONSUMO … RAPPI» → `comidas_fuera`, por R1 + R4). Sin comercio, o con una pasarela o tienda que no permite
saber el bien (dLocal, Falabella, GW-SIA) → `otros.ininteligible` (**R7**). Los 6 ítems se reportan como subgrupo.

### Caso 2 — PSE sin facturador (`banco`, `egreso`) · marco 95 · test 0 · en la calibración: C03
Ej.: «Compra <banco o pasarela> Compras y Pagos PSE», «… Pago por PSE»: el texto nombra la pasarela, no la factura.
⚠ Pesa 4,4 % del marco, pero el sorteo no dejó ningún ítem en el test. La convención solo se aplica en la calibración.
Si el texto sí nombra al facturador (un colegio, una telefónica…), no es este caso: aplica R5 directamente.
No confundir con «PAGOS POR PSE» en tarjeta con `signo = ingreso`: eso es pago de la tarjeta (R6).
- **R5:** «Pagos de factura vía PSE/corresponsal → categoría de la factura …, no una categoría de 'pagos'».
- **R7:** «… otros.ininteligible; nunca adivinar».

**Convención acordada:** `otros.ininteligible` (**R7**). R5 no aplica porque el texto no nombra la factura. Solo
afecta a la calibración (C03); en el test hay 0 ítems.

### Caso 3 — Transferencias a/desde billetera sin persona (`banco`) · marco 254 · test 7 · Σ peso ≈ 386
Ej.: «TRANSFERENCIAS A NEQUI» (**235 transacciones**, el descriptor más repetido del marco: 3 ítems con peso ≈ 119
cada uno), «TRANSFERENCIA DESDE NEQUI». No dice si la billetera es del mismo titular.
- **`movimiento_propio` (definición):** «recarga de billetera desde cuenta bancaria»; ejemplo
  «RECARGA NEQUI DESDE BANCOLOMBIA».
- **`movimiento_propio` (caso límite):** «Distinguir p2p vs. cuenta propia exige conocer la titularidad; cuando el
  texto no lo indica, el voluntario lo declara … En inferencia pura queda como p2p.indeterminada».
- **`transferencias_p2p` (excluye):** «traslado entre cuentas propias → movimiento_propio».

**Convención acordada:** `transferencias_p2p.indeterminada`, **igual para «A» y «DESDE»**. Regla citada: caso límite
de `movimiento_propio` («en inferencia pura queda como p2p.indeterminada»), porque el texto no dice quién es el
titular de la billetera.
**Extensión por analogía (decisión de la investigadora, no texto literal de la taxonomía):** el mismo criterio se
aplica a «TRASLADO VIRTUAL OTROS BANCOS», a las transferencias por llave Bre-B (`… BREB LLAVE` / `… BREB #`) y a
«Rec.Inter TFR». En ninguno se conoce la titularidad de la cuenta de destino.

### Caso 4 — «Compra en PERSONA» · marco 48 · test 4 · Σ peso ≈ 41
Ej.: «PERSONA» sola en tarjeta (34), «PAGO QR PERSONA» (12), «COMPRA EN PERSONA» (2): un nombre de persona
anonimizado en lo que parece una compra.
- **`transferencias_p2p` (excluye):** «pago identificable a comercio o por bien/servicio, aunque el canal sea
  billetera → categoría del bien (regla R1)».
- **R2:** «transferencias_p2p solo aplica cuando la contraparte es persona natural Y el propósito no es identificable».
- **R7:** «… el subtipo *indeterminada* de P2P o la categoría otros.ininteligible».
- Formalidad (solo A1): `informal` = «persona particular vendiendo bienes/servicios».

**Convención acordada (decide el verbo), igual en tarjeta y en banco:**
- «COMPRA / PAGO (QR) / RBM\* PERSONA» o «PERSONA» sola en tarjeta → `otros.ininteligible`. Es un pago por un
  bien o servicio que no se identifica: la exclusión de `transferencias_p2p` lo saca de P2P y **R7** lo manda a `otros`.
- «TRANSF … PERSONA» (incluida «TRANSF QR NEQUI PERSONA») → `transferencias_p2p.indeterminada`. **No** va a P2P
  enviada: el anonimizador v1.2 reemplaza por `PERSONA` tanto a terceros como al **propio titular** (57 sustituciones
  del titular), así que el texto no permite distinguir entre una transferencia a otra persona y una a cuenta propia.
  Se aplica el mismo criterio que en el caso 3.
- **Extensión:** «RBM\*PERSONA» (datáfono de una persona natural) se incluye en el caso. Con eso son **7 ítems** en el
  test, no los 4 que fijó el pre-registro v1.3.
- **Hallazgo para la v1.2 de la taxonomía y del anonimizador:** distinguir `PERSONA` (tercero) de `TITULAR` (el
  propio voluntario) habría permitido resolver estos casos y parte del caso 3.

---

**Regla común (las dos anotadoras):** no buscar en internet comercios desconocidos; aplicar R7 y marcar `duda = 1`.

Convenciones fijadas en la adjudicación, 26 nov 2026, por A1 (investigadora), antes de ver predicciones. Sin sesión de calibración previa (ver la desviación arriba).
