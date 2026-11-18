# Declaración de uso de herramientas de inteligencia artificial

> **BORRADOR para que la autora revise, ajuste y firme.** Cumple la política de integridad académica de la Pontificia Universidad Javeriana sobre el uso de asistentes de IA. Completar los campos marcados `[...]` y verificar que describe fielmente el trabajo real.

## Herramientas utilizadas
Durante el desarrollo de este Trabajo de Grado se emplearon asistentes de inteligencia artificial conversacional (Claude, de Anthropic, en sus modos Opus y Fable) como apoyo a la programación, la depuración, el análisis y la redacción. Su uso fue instrumental: la autora definió la metodología, tomó todas las decisiones de diseño, verificó los resultados y es la única responsable del contenido.

## Alcance del uso por fase

| Fase | Asistencia de IA | Decisiones y verificación de la autora |
|---|---|---|
| Reconstrucción y perfilado de microdatos DANE | Diseño y depuración de los scripts de carga, normalización y cálculo | Reglas metodológicas (dominio Bogotá, «ENPH calibra / GEIH estructura», uso de factores de expansión); verificación de cada cifra contra `outputs/` |
| Etapa 1 — Priors bayesianos | Implementación del Dirichlet jerárquico y el encogimiento | Diseño de las 15 celdas, estimación de κ̂ por verosimilitud, criterio de celda rala |
| Etapa 2 — Generador por reglas e IPC | Implementación de los módulos | Decisiones de diseño D1–D15 (incl. la arquitectura de dos capas y el deflactor IPC) |
| Reevaluación del pipeline de referencia (Pancholi) | Ejecución y scripts de análisis | Criterios de evaluación prerregistrados antes de ejecutar |
| Etapa 3 — CTGAN | Implementación del notebook, el módulo y las pruebas | Pre-registro completo (columnas, métricas, umbrales, reglas duras, criterio de elasticidad) fijado antes de correr |
| Biblioteca de comercios y plantillas de descriptor | `[la autora describe el grado de asistencia]` | Curaduría a partir de comercios de conocimiento público y de la taxonomía propia; pesos de plausibilidad declarados |
| Redacción del reporte | Borrador asistido a partir del material ya existente en el repositorio | Revisión, corrección y responsabilidad final del texto y de todas las cifras |

## Garantías de integridad
- **Ninguna cifra fue inventada por la IA:** todos los valores provienen de los microdatos oficiales del DANE y de código reproducible; los documentos resumen, el repositorio deriva.
- **Reproducibilidad:** semilla fija (`SEED=42`), rutas relativas, verificación por SHA-256 (incluida la reproducibilidad bit a bit del CTGAN) y prerregistro de los criterios de evaluación.
- **Verificación independiente:** la autora contrastó los resultados contra los archivos de `outputs/` y revisó críticamente cada afirmación metodológica.
- **Lo que la IA no hizo:** no determinó la pregunta de investigación ni las hipótesis, no eligió la metodología, no fabricó datos ni resultados, y no sustituyó el criterio de la autora.

## Declaración
`[Nombre completo]`, autora de este Trabajo de Grado, declara que el uso de herramientas de IA se limitó a lo aquí descrito, que revisó y validó todo el material generado con su asistencia, y que asume la responsabilidad plena del contenido.

Bogotá, `[fecha]`.
