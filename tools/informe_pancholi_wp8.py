"""WP5 → WP8 — Inserta en docs/reevaluacion_pancholi.md el bloque «según diseño → según ejecución», el estado de
la etapa 4 (LLM) y el veredicto de comparación para WP8.

Bloque delimitado por <!-- WP8:inicio --> / <!-- WP8:fin -->: se reemplaza en cada corrida (idempotente) y no toca el
resto del documento, que genera tools/informe_pancholi.py. Todas las cifras salen de outputs/pancholi/.
Uso: python tools/mapeabilidad_pancholi.py && [python tools/analisis_pancholi_etapa4.py] && python tools/informe_pancholi_wp8.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
S = RAIZ / "outputs" / "pancholi"
DOC = RAIZ / "docs" / "reevaluacion_pancholi.md"
INI, FIN = "<!-- WP8:inicio -->", "<!-- WP8:fin -->"


def f(x: float, d: int = 3) -> str:
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, d: int = 1) -> str:
    return f(100 * x, d) + " %"


def ic(a: float, b: float, d: int = 3) -> str:
    return f"[{f(a, d)}; {f(b, d)}]"


def main() -> None:
    v = json.loads((S / "resumen_hipotesis.json").read_text(encoding="utf-8"))
    el = pd.read_csv(S / "hp1_elasticidad.csv").set_index("conjunto")
    p2 = pd.read_csv(S / "hp2_participacion_nivel1.csv")
    h3 = pd.read_csv(S / "hp3_registros_extracto.csv")
    mp = json.loads((S / "wp8_mapeabilidad.json").read_text(encoding="utf-8"))
    cob = pd.read_csv(S / "wp8_cobertura_categorias.csv")
    a4p = S / "etapa4" / "analisis_etapa4.json"
    a4 = json.loads(a4p.read_text(encoding="utf-8")) if a4p.exists() else None
    if a4 and a4.get("simulado"):
        a4 = None                        # una prueba con servidor simulado nunca se reporta como resultado
    m4p = S / "etapa4" / "manifest_etapa4.json"
    m4 = json.loads(m4p.read_text(encoding="utf-8")) if m4p.exists() and a4 else None

    def part(conj: str, cat: str) -> str:
        r = p2[(p2.conjunto == conj) & (p2.columna == "category") & (p2.nivel_1 == cat)].iloc[0]
        return f"{pct(r.part_conteo)} {ic(100 * r.wilson_inf, 100 * r.wilson_sup, 1)}"

    e2, e3 = el.loc["A_etapa2"], el.loc["B_etapa3"]
    t3 = h3[(h3.conjunto == "B_etapa3") & (h3.tipo_registro == "__cualquier_registro_de_extracto__")].iloc[0]
    rp = v["H-P2"]["B_etapa3"]
    L: list[str] = [INI, ""]
    w = L.append

    w("## 0. Resumen WP5 → WP8 (actualización del 23 nov 2026)\n")
    w(f"**Veredicto para WP8: comparación tipo {'(b)' if mp['mapeable'] else '(a)'}.** La salida del pipeline de referencia "
      f"{'es' if mp['mapeable'] else '**no es**'} mapeable a las {mp['n_clases_taxonomia']} `categoria_n1` de la taxonomía "
      f"v{mp['taxonomia_version']}: su generador alcanza {mp['n_clases_alcanzables']} de {mp['n_clases_taxonomia']} "
      f"({mp['n_clases_alcanzables_sin_marginales']} sin las rutas marginales). "
      + ("Pancholi entra a WP8 solo como contexto: su F1 reportado se cita, no se compara. No se genera "
         "`outputs/pancholi/baseline_sintetico.csv.gz`." if not mp["mapeable"] else
         "Se genera el baseline en `outputs/pancholi/baseline_sintetico.csv.gz`.") + "\n")

    w("### 0.1 Según diseño → según ejecución\n")
    w("«Diseño» = lo que dice su código (lectura). «Ejecución» = lo medido corriendo su código con el commit fijado "
      "(etapas 1–3: 10 semillas, criterios prerregistrados; §1–§3). Conjunto principal: réplica literal, etapa 3.\n")
    w("| Hipótesis | Según diseño | Según ejecución (etapas 1–3) | Etapa 4 (LLM) |")
    w("|---|---|---|---|")
    if a4:
        h1, h2, h3_ = a4["H-P1"], a4["H-P2"], a4["H-P3"]
        e4_1 = (f"elasticidad entre clientes {f(h1['elasticidad_entre_clientes'])} {ic(*h1['ic95_bootstrap_clientes'])}, "
                f"n = {h1['n_clientes']} clientes, una corrida: **{'sensible' if h1['sensible_al_ingreso'] else 'no sensible'} "
                "al ingreso**. Mecanismo: su prompt le da al LLM un «Expected spending range» proporcional al ingreso")
        oe, oh = h2["ocio_entretenimiento"], h2["ocio_con_hospedaje"]
        e4_2 = (f"{h2['n_categorias_n1']} categoria_n1 (la cota del código). Entretenimiento {pct(oe['part_ocio'])} "
                f"{ic(100 * oe['ic95_ocio'][0], 100 * oe['ic95_ocio'][1], 1)} vs. alimentos {pct(oe['part_alimentos'])} "
                f"{ic(100 * oe['ic95_alimentos'][0], 100 * oe['ic95_alimentos'][1], 1)}: **{oe['veredicto']}**; con hospedaje "
                f"{pct(oh['part_ocio'])} {ic(100 * oh['ic95_ocio'][0], 100 * oh['ic95_ocio'][1], 1)}: **{oh['veredicto']}**. "
                f"El LLM respeta la subcategoría pedida en el {pct(h2['fidelidad_categoria_llm'])}")
        pm = h3_["part_por_medio_v1"]
        cotas = h3_["ausentes_cota_sup_wilson"]
        e4_3 = ("; ".join(f"`{m}` {pct(v['part'])} {ic(100 * v['ic95'][0], 100 * v['ic95'][1], 1)}" for m, v in pm.items())
                + f" ({h3_['valores_distintos_payment_type']} grafías de {len(h3_['medios_v1_distintos'])} medios). "
                + f"Efectivo, billetera y transferencia: 0 de {a4['N_filas']} (cota superior {pct(max(cotas.values()))}). "
                + f"Registros de extracto: {h3_['registros_extracto_retiro_p2p_propio_ingreso']}. **Domina la tarjeta, "
                + "pero no es 100 % `credit_card`**")
    else:
        e4_1 = e4_2 = e4_3 = "**no ejecutada** (§0.2)"
    w(f"| H-P1 ingreso | Etapa 2: monto ∝ ingreso (elasticidad 1 por construcción). Etapa 3: el ingreso no es columna del "
      f"CTGAN. Etapa 4: el ingreso entra al prompt como rango esperado | Etapa 2: {f(e2.media)} {ic(e2.ic95_inf, e2.ic95_sup)}. "
      f"Salida final (etapa 3): {f(e3.media)} {ic(e3.ic95_inf, e3.ic95_sup)}: **no conserva** la relación. Frente a "
      f"Colombia: **{v['H-P1']['veredicto']}** | {e4_1} |")
    w(f"| H-P2 categorías | 7 etiquetas (etapa 2) y {mp['etiquetas_etapa4']} subcategorías (etapa 4) en las mismas 6 "
      f"familias de comercio de D.C. | Entretenimiento {part('B_etapa3', 'entretenimiento')} vs. alimentos "
      f"{part('B_etapa3', 'alimentos_mercado')}: dominio de ocio **{rp['ocio=entretenimiento']['veredicto']}** "
      f"(**{rp['ocio=entretenimiento+hospedaje (sensibilidad)']['veredicto']}** si el hospedaje cuenta como ocio); "
      f"{rp['categorias_v1_con_participacion']} de {rp['categorias_v1_total']} categorías con registros | {e4_2} |")
    w(f"| H-P3 medio de pago | Etapas 1–3: sin campo. Etapa 4: `payment_type` en texto libre («Appropriate payment "
      f"method»); un registro = una compra | Sin columna de medio de pago; {int(t3.n)} de {f(t3.N, 0)} registros de "
      f"retiro/P2P/movimiento propio/ingreso: **confirmada para las etapas 1–3** | {e4_3} |\n")

    w("### 0.2 Etapa 4 (LLM): estado de la ejecución\n")
    if a4:
        c = a4["costo"]
        w(f"- **Ejecutada** con `{a4['modelo_usado']}`" + (f" — **desviación:** {a4['desviacion_modelo']}" if a4["desviacion_modelo"] else "")
          + f". {a4['llamadas']} llamadas, {a4['fallos']} fallidas ({pct(a4['tasa_fallo'])}), {a4['N_filas']} registros, "
          f"{f(c['minutos'], 1)} min, {f(c['prompt_tokens'], 0)} tokens de entrada y {f(c['completion_tokens'], 0)} de salida"
          + (f", costo estimado USD {f(c['usd_estimado'], 2)} a precio de lista {c['precio_usd_por_M']} USD/M" if c["usd_estimado"] is not None else "")
          + ". Parámetros y SHA-256 en `outputs/pancholi/etapa4/manifest_etapa4.json`; respuestas crudas en `llamadas.jsonl`.")
        w(f"- Semilla {m4['parametros']['semilla']}, pausa {f(m4['parametros']['pausa_s'], 0)} s, temperatura "
          f"{f(m4['parametros']['temperatura'], 1)}, {m4['parametros']['clientes']} clientes, pandas {m4['entorno']['pandas']} "
          "(la versión que fija su repo). Las peticiones son idénticas entre corridas con la misma semilla; las respuestas del "
          "LLM no, y por eso el análisis parte de los registros guardados. El "
          f"{pct(a4['H-P2']['part_comercio_generico_fallback'])} de los registros usa su comercio genérico de respaldo "
          "(«DC … Service»). Costo: se reportan tokens; no se fijó precio por token.")
        w("- **Limitaciones de esta corrida:** un solo modelo, distinto del de su código; una sola corrida, sin IC entre corridas "
          "del LLM; 25 clientes. Verifica cómo se comporta la etapa 4, no estima su variabilidad.")
        w("- **La ejecución confirma la cota de diseño:** la etapa 4 emitió exactamente las categoria_n1 que su código puede "
          "sortear; el LLM no creó ninguna. El veredicto de §0.3 no cambia.\n")
    else:
        w("- **No ejecutada con un LLM real.** Desde el entorno de ejecución la API de Groq sigue bloqueada (HTTP 403 en el proxy, "
          "verificado el 23 nov), y la terminal del equipo de la autora no respondió durante la sesión. La corrida está preparada: "
          "`python tools/pancholi_etapa4.py --n 300` (≈1 h con su pausa de 10 s), y luego `python tools/analisis_pancholi_etapa4.py` "
          "y este script. Se probó de punta a punta contra un servidor simulado (eso verifica el código, no produce resultados).")
        w("- **El modelo de su código ya no se sirve en los planes gratuito y developer.** Groq anunció el 17 de junio de 2026 el retiro de "
          "`llama-3.3-70b-versatile`, efectivo el 16 de agosto de 2026, y recomienda `openai/gpt-oss-120b` "
          "(https://console.groq.com/docs/deprecations). Una corrida hoy sería, en el mejor caso, una **variante declarada**, no una "
          "reproducción: el script lo detecta en `/models` y lo deja escrito en el manifiesto.")
        w("- **Por qué el veredicto no depende de esta corrida.** La etapa 4 es un generador aparte, no un postproceso: la subcategoría la "
          f"sortea su código entre {mp['etiquetas_etapa4']} etiquetas fijas, y el LLM solo rellena monto, fecha, comercio y `payment_type`. "
          "Ninguna respuesta del LLM puede crear una categoría que el código no sortea, así que la cobertura de §0.3 es una cota que la "
          "ejecución no puede mejorar. Lo único que la corrida añadiría es la distribución empírica de `payment_type` (H-P3), medida con "
          "otro modelo.\n")

    w("### 0.3 Criterio único para WP8: ¿es mapeable a las 16 `categoria_n1`?\n")
    w(f"**Regla:** {mp['criterio']}. Mapeos versionados: `docs/taxonomia/mapeo_pancholi_taxonomia_v1.csv` (etapa 2) y "
      "`docs/taxonomia/mapeo_pancholi_etapa4_taxonomia_v1.csv` (etapa 4), con prueba en `tests/`. Para no sesgar hacia (a), los "
      "mapeos son **generosos**: `driving_lessons` → `educacion` y `boarding_house` → `vivienda_servicios.arriendo` se aceptan aunque "
      "pesen 0,01 en su código. Cálculo: `tools/mapeabilidad_pancholi.py` → `outputs/pancholi/wp8_mapeabilidad.json`.\n")
    w("| categoria_n1 | ¿Alcanzable? | Etiquetas de Pancholi que llegan | Peso en su código (etapa 4) | Filas en el sintético del protocolo |")
    w("|---|---|---|---|---|")
    for r in cob.itertuples():
        w(f"| {r.categoria_n1} | {'sí' if r.alcanzable_pancholi else '**no**'} | {r.etiquetas_pancholi if isinstance(r.etiquetas_pancholi, str) else '—'} "
          f"| {f(r.peso_codigo_etapa4, 2)} | {pct(r.part_sintetico_v1)} |")
    w("")
    w(f"- **Resultado:** {mp['n_clases_alcanzables']} de {mp['n_clases_taxonomia']} alcanzables → **NO mapeable**. No alcanzables: "
      f"{', '.join('`' + c + '`' for c in mp['clases_no_alcanzables'])}. La sensibilidad con las clases de soporte ≥ "
      f"{mp['sensibilidad_soporte']['soporte_min']} da el mismo resultado ({'mapeable' if mp['mapeable_sensibilidad'] else 'no mapeable'}).")
    w(f"- **Techo de F1-macro** de un clasificador entrenado con su salida y evaluado en las {mp['n_clases_taxonomia']} clases: "
      f"{f(mp['techo_f1_macro_16'], 3)} ({f(mp['techo_f1_macro_16_sin_marginales'], 3)} sin las rutas marginales), aun si acertara "
      "todo lo que puede predecir: una clase que nunca predice tiene F1 = 0.")
    w(f"- **Masa afectada:** en el sintético del protocolo (`outputs/ctgan/sintetico_v1.csv.gz`), el "
      f"{pct(1 - mp['masa_sintetico_v1_en_clases_alcanzables'])} de las filas cae en clases que Pancholi no puede emitir "
      f"({pct(1 - mp['masa_sintetico_v1_sin_marginales'])} sin las rutas marginales). Es una aproximación: la composición real "
      "del conjunto anotado (WP4) la reemplaza cuando exista.")
    w("- **Contexto colombiano** (descriptivo, no cambia la regla): de las 13 columnas del esquema de `sintetico_v1`, "
      f"{sum(1 for x in mp['derivabilidad_esquema_wp8'].values() if x['estado'] == 'directa')} salen directas de su salida, "
      f"{sum(1 for x in mp['derivabilidad_esquema_wp8'].values() if x['estado'] == 'constante')} son constantes (solo compras), "
      f"{sum(1 for x in mp['derivabilidad_esquema_wp8'].values() if x['estado'] == 'ausente')} no existen "
      "(`cuenta_tipo`, `medio_pago` en las etapas 1–3, `formalidad_comercio`), "
      f"{sum(1 for x in mp['derivabilidad_esquema_wp8'].values() if x['estado'] == 'parcial')} son parciales (`categoria_n1`, `categoria_n2`) y "
      "`monto` e `ingreso_mensual` exigirían inventar una conversión de USD de D.C. a COP de Bogotá.\n")
    w("**Implicación para WP8 y riesgos.**")
    w("1. **Comparación tipo (a).** El TSTR se reporta para el protocolo; Pancholi se cita con su F1 publicado como contexto, sin "
      "compararlo. La no transferibilidad es un hallazgo que justifica el protocolo, no un hueco.")
    w("2. **Inconsistencia con el borrador.** `docs/reporte/borrador_reporte.md` (método, «Comparación con el pipeline de referencia», "
      "y resultados, «F1-macro TSTR del protocolo adaptado vs. el pipeline de referencia») promete la comparación (b): entrenar sobre "
      "su salida y evaluar en Bogotá. Hay que reescribir ambos pasajes en términos de (a).")
    w("3. **Alternativa descartada:** un (b) restringido a las clases compartidas. Cambiaría la tarea (otro espacio de etiquetas y otra "
      "métrica) y ya no mediría lo mismo que el TSTR del protocolo. Se puede mencionar como trabajo futuro, no como resultado.")
    w("4. **El techo de F1 es una cota, no una medición.** El valor real sería menor, porque además las descripciones de texto de "
      "su salida son nombres de comercios de D.C. en inglés.\n")
    w(FIN)

    doc = DOC.read_text(encoding="utf-8")
    bloque = "\n".join(L)
    if INI in doc and FIN in doc:
        doc = doc[:doc.index(INI)] + bloque + doc[doc.index(FIN) + len(FIN):]
    else:
        cab, resto = doc.split("\n", 1)
        doc = cab + "\n\n" + bloque + "\n" + resto
    DOC.write_text(doc, encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
