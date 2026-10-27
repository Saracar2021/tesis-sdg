# Esqueleto del reporte final — formato IEEE Transactions on AI

**Entrega:** 27 nov 2026 · **Extensión:** ≤ 24 pp (promedio de la maestría: 12 ± 3) · **Autores:** Sara J. Cárdenas (primera autora); asesores y tutora como últimos autores.
**Plantilla:** IEEE Transactions on AI, desde https://template-selector.ieee.org/ (hay versión LaTeX y Word; recomendado Overleaf con la plantilla LaTeX).

> Este archivo es **andamiaje**: define secciones, qué va en cada una, el presupuesto de páginas y de dónde portar el contenido que ya existe en el repo. El texto lo redacta la autora. No es el reporte.

## Presupuesto de páginas (objetivo ~14–16 pp de 24)

| Sección | Págs | Estado del insumo |
|---|---|---|
| Abstract + Index Terms | — | Adaptar del abstract del informe de avance |
| I. Introducción | 1,5 | ✅ Existe (informe §I; protocolo §1; plan §0) |
| II. Trabajo relacionado | 2 | ✅ Existe (informe «Estado del arte») |
| III. Problema e hipótesis | 1 | ✅ Existe (informe) |
| IV. Datos y metodología | 3,5 | ✅ Mayoría existe (protocolo §2–§5, fuentes_datos) |
| V. Reevaluación del pipeline de referencia | 1,5 | ✅ Existe (reevaluacion_pancholi.md) |
| VI. Diseño experimental | 1,5 | 🟡 Parcial (se completa con WP6–WP8) |
| VII. Resultados | 2,5 | ⬜ Pendiente (WP7 fidelidad, WP8 TSTR) |
| VIII. Discusión y limitaciones | 1,5 | ✅ Limitaciones existen (protocolo §6, L1–L17) |
| IX. Conclusiones y trabajo futuro | 1 | 🟡 Esbozo |
| Declaración de ética / consentimiento | 0,25 | 🟡 Según datos reales |
| Referencias | — | ✅ Existe (informe) |

## Estructura sección por sección

### Abstract + Index Terms
- 150–250 palabras: problema (sin datos transaccionales públicos en Colombia), propuesta (protocolo calibrado DANE, Bogotá), método (priors→reglas→CTGAN→TSTR), y el hallazgo principal una vez corran los experimentos.
- Portar/adaptar: abstract del informe de avance. Index Terms: datos sintéticos, CTGAN, clasificación de transacciones, TSTR, informalidad financiera, Colombia.

### I. Introducción
- Barrera de datos (Ley 1266/Habeas Data), por qué no se transfiere un modelo de otro país, contribución y pregunta de investigación + hipótesis.
- **Portar de:** informe §I; protocolo §1; plan §0. Actualizar el encuadre: protocolo colombiano, **calibración/validación sobre Bogotá** como caso de estudio.

### II. Trabajo relacionado
- Generación de datos sintéticos financieros (PaySim, CTGAN, Altman, Hounwanou, Karst); clasificación de transacciones; paradigma TSTR.
- **Portar de:** informe «Estado del arte». Revisar que las citas sigan vigentes.

### III. Planteamiento del problema e hipótesis
- Contradicción estructural (datos privados por diseño) y la hipótesis (F1 macro TSTR del protocolo adaptado > pipeline de referencia).
- **Portar de:** informe. **Ajustar la hipótesis** a la redacción con D15 (ver plan P16): ENPH actúa en la capa interna; la mezcla observable en extractos usa Banrep 2024.

### IV. Datos y metodología
- IV.A Fuentes DANE (GEIH 2025, ENPH 2016-2017), dominio Bogotá, factores de expansión, llaves y unidad de análisis. **Portar:** protocolo §2 y §4; `fuentes_datos.md`.
- IV.B Decisiones metodológicas clave (D1–D15), estrato agrupado × quintil, encogimiento jerárquico, D15 (universo = extractos bancarizados). **Portar:** protocolo §5.
- IV.C Taxonomía de categorías. **Portar:** taxonomía v1.1 (cuando se congele).
- IV.D Las cuatro etapas del protocolo. **Portar:** protocolo §3.

### V. Reevaluación del pipeline de referencia (Pancholi et al.)
- Diseño reproducible (criterios prerregistrados), resultados H-P1/H-P2/H-P3, qué sostiene la motivación.
- **Portar de:** `reevaluacion_pancholi.md`. Incluir la tabla de veredictos y la figura de elasticidad por etapa.

### VI. Diseño experimental
- Dataset sintético v1 (tamaño, CTGAN, semilla); conjunto real de validación (voluntarios Bogotá, anonimización, anotación con 2 anotadores + Kappa); protocolo TSTR; clasificadores (logístico, BETO, LLaMA 3); métricas (F1 macro con regla de soporte ≥10, Kappa, AUC).
- **Completar con:** WP6 (generador), WP7 (CTGAN), WP8 (TSTR). Dejar los parámetros exactos para cuando corran.

### VII. Resultados
- VII.A Fidelidad del dataset sintético (métricas SDV). VII.B TSTR: F1 por clasificador, matriz de confusión por categoría. VII.C Comparación vs. pipeline de referencia.
- **Pendiente:** se llena con WP7/WP8. Toda cifra sale de `outputs/`, nunca a mano.

### VIII. Discusión y limitaciones
- Interpretación; amenazas a la validez; limitaciones L1–L17 (sin UPM/segmento → sin IC de diseño; ENPH 2016-17; muestra por conveniencia; extractos no ven efectivo; etc.).
- **Portar de:** protocolo §6.

### IX. Conclusiones y trabajo futuro
- Contribuciones (protocolo replicable; primer dataset sintético público colombiano; taxonomía con P2P; evidencia de contextualización). Trabajo futuro: otras ciudades, medios digitales, etapas 4–5 de la referencia.
- **Portar de:** informe «Contribuciones esperadas».

### Declaración de ética / consentimiento
- Consentimiento informado de los voluntarios, anonimización, y si aplica aval de comité (confirmar con la tutora).

### Referencias
- **Portar de:** informe (formato IEEE ya aproximado). Verificar DOIs y completar las nuevas.

## Notas de tope de páginas
- Si se excede de 24: comprimir II (trabajo relacionado) y mover detalle de IV a material suplementario; las tablas largas (D1–D15, L1–L17) van condensadas, con el detalle citado al repo.
- Figuras candidatas: pirámide de estrato, matriz medio de pago × categoría, elasticidad Pancholi por etapa, matriz de confusión TSTR.
