# Bitácora

## Chat 01 — cargador único y distribuciones para priors (20 sep 2026)

1. `src/sdg/carga.py` (+ `pesos.py`, `codigos.py`, `medio_pago.py`): cargador GEIH/ENPH con validación de filas contra `outputs/fuentes_datos.json`, `FEX_C18/len(meses)`, dominio Bogotá, rural bloqueado, uniones que reportan % enlazado y `estrato_agrupado()`. 29 tests en `tests/` (`python -m unittest discover -s tests`), en verde.
2. `FEX_C` de ENPH **verificado** (Metodología §2.2.4.1 + constante por `DIRECTORIO` e igual al de `viviendas_hogares` en 10 tablas; rural no cubierto). Códigos verificados contra su fuente: estrato ENPH (Manual, 0 = pirata, 9 = no establecible), estrato GEIH (dicc. fila 32), P438\* (Cuadernillo 3: 4 = bonos, 5 = cheques; 29 columnas = subcapítulo = categoría × periodo) y `NC2R_CC_P6` (Cuadernillo 2 urbano: 4 = **fiado**, 5 = bonos). `P6450`: 9 = No sabe.
3. `tools/distribuciones_priors.py` → `outputs/distribuciones/` (16 tablas + informe + manifest): Bogotá urbano con FEX. Vacíos de P438\* cruzados con artículos: con `FORMA=1` como compra la no respuesta es 0 en los 29 subcapítulos (todo vacío es «no aplica»); con «cualquier registro» aparece no respuesta solo en hogares con registros no comprados. Gaps abiertos: no existen `P438J14` ni `P438K11`; `P438J13` sin verificar contra el cuadernillo.
4. Fronteras de grupos: el amontonamiento en valores redondos afecta a `INGLABO` (hasta ~6 % del peso en un valor) y no a `ICGU` (< 0,1 %). Declarado como limitación; sin cortes fijos. Sensibilidades (>1 p.p.): sin diciembre, sin julio y sin marzo, todas en `outputs/distribuciones/`.
5. Julio 2025 (GEIH `datos_hogar`, estrato) **sin explicar** — `tools/investigar_julio.py`, `outputs/julio/julio_estrato.md`: no es «sin dato», es 3 → 1-2; se repite en 23 ciudades y atenuado a nivel nacional; otras variables no se mueven. Registrado como evidencia para pedir al DANE el control de cambios 2501-2512. Hallazgo colateral: en `ocupados` de Bogotá el mes más extremo es marzo.
6. Cierre: CLAUDE.md v4, `requirements.txt` (versiones fijas). Pendientes: umbral de soporte y encogimiento (Chat 05); definición oficial DANE de formalidad si hace falta una sola variable; fijar torch/ctgan/jupyter en `requirements.txt` cuando se instalen.

### Chat 01 — cierre: decisión sobre marzo y julio (20 sep 2026)

- **Decisión (Sara): se usan los 12 meses. Cerrado.** Estrato agrupado (máx. 0,73 p.p. sin julio, 0,31 sin marzo) y formalidad (0,29 / 0,52 p.p.) bajo el umbral de 1 p.p.; las familias de ENPH no dependen de los meses de GEIH. Lo único que supera 1 p.p. es `INGLABO` (G1/G2 sin julio): el primer corte pasa de 1.300.000 a 1.200.000 por el amontonamiento ya declarado, efecto de frontera y no de composición.
- Marzo y julio quedan como **anomalías declaradas en la tesis**, con sensibilidades en `outputs/distribuciones/` como respaldo; causa sin investigar más hasta contar con el control de cambios DANE 2501-2512.
- Regla de fuentes en CLAUDE.md: ENPH aporta ingreso (`ICGU`) y gasto; GEIH, estructura demográfica y laboral. `INGLABO` solo descriptivo, no es insumo de calibración.
- Celdas posición ocupacional × cotiza pensión: declaradas como pequeñas e inestables en `distribuciones_priors.md`. Cobertura faltante de P438\* (J14, K11) declarada como limitación del instrumento.
