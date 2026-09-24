# Métricas de las preguntas ciegas

Las 10 preguntas del hold-out del profesor, ejecutadas contra el repositorio
entregado y sin cambiar el código: `evaluar("ciegas.jsonl")`.

- Fichero original del profesor: `golden/holdout.jsonl`.
- Fichero ejecutado: `ciegas.jsonl`. Es el mismo, sin los campos
  `respuesta_en_corpus` y `fuente_esperada`, que son informativos y no forman
  parte del esquema de pregunta. Ninguno interviene en la corrección.
- Resultados completos: `resultados/ciegas/` (el detalle por pregunta está en
  `detalle.csv`).
- Ejecución: 2026-09-24 16:49 UTC, modelo
  openrouter:google/gemini-3.8-flash, commit c2b5c00.

## Comparación con el golden set propio

| familia | golden (final) | ciegas | delta |
| --- | --- | --- | --- |
| extractiva | 83% | 67% | -17 pp |
| numérica | 100% | 100% | +0 pp |
| comparativa | 83% | 100% | +17 pp |
| hueco | 100% | 100% | +0 pp |
| total | 90% | 90% | +0 pp |

## Resultado de la ejecución

- fecha: 2026-09-24 16:49 UTC
- modelo: openrouter:google/gemini-3.8-flash
- commit: c2b5c00
- preguntas: 10 (ciegas.jsonl)
- acierto total: 9/10, IC 95 % [60%, 98%]

## Resumen

| sistema | extractiva | numérica | comparativa | hueco | total | recall@5 | coste medio | latencia media | tool calls/pregunta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ciegas | 67% | 100% | 100% | 100% | 90% | 100% | 1.696 ¢ | 35.8 s | 2.9 |

## Por familia

| familia | preguntas | aciertos | qué falló |
| --- | --- | --- | --- |
| extractiva | 3 | 2/3 | sin_chunk_id (1) |
| numerica | 3 | 3/3 | — |
| hueco | 2 | 2/2 | — |
| comparativa | 4 | 4/4 | — |

## Trayectoria

| trayectoria | preguntas | proporción |
| --- | --- | --- |
| camino correcto | 10 | 100% |
| camino equivocado, acierta | 0 | 0% |
| camino equivocado, falla | 0 | 0% |
| no aplica (sin herramienta_esperada) | 0 | — |

## Guardarraíl

| guardarraíl | valor |
| --- | --- |
| preguntas con intervención del guardarraíl | 10% |
| intervenciones totales | 1 |
| recuperadas tras intervenir (respuesta correcta) | 100% |
| preguntas que agotaron el límite de llamadas | 0 |
| alucinaciones sobre hueco | 0 |
| abstenciones indebidas (dijo «no hay dato» y sí lo había) | 0% |

## Retrieval

| recall@1 | recall@3 | recall@5 | recall@10 | MRR |
| --- | --- | --- | --- | --- |
| 29% | 86% | 100% | 100% | 0.58 |

| pregunta | puesto del ancla |
| --- | --- |
| ho-001 | 3 |
| ho-002 | 1 |
| ho-003 | 1 |
| ho-007 | 2 |
| ho-008 | 5 |
| ho-009 | 2 |
| ho-010 | 2 |

## Por pregunta

| id | familia | acierto | herramientas | qué falló |
| --- | --- | --- | --- | --- |
| ho-001 | extractiva | sí | search_filings |  |
| ho-002 | extractiva | no | list_available > search_filings | sin_chunk_id (1) |
| ho-003 | extractiva | sí | list_available > search_filings > get_xbrl_fact > get_xbrl_fact |  |
| ho-004 | numerica | sí | get_xbrl_fact |  |
| ho-005 | numerica | sí | list_available > get_xbrl_fact |  |
| ho-006 | numerica | sí | list_available > get_xbrl_fact |  |
| ho-007 | comparativa | sí | list_available > get_xbrl_fact > get_xbrl_fact > search_filings |  |
| ho-008 | comparativa | sí | list_available > get_xbrl_fact > get_xbrl_fact > search_filings > search_filings > search_filings |  |
| ho-009 | comparativa | sí | get_xbrl_fact > get_xbrl_fact > search_filings |  |
| ho-010 | comparativa | sí | list_available > get_xbrl_fact > get_xbrl_fact > search_filings |  |
