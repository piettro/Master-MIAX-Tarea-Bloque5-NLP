# Resultados · final

- fecha: 2026-09-24 09:26 UTC
- modelo: openrouter:google/gemini-3.8-flash
- commit: 27e7369
- preguntas: 20 (golden\golden_set.jsonl)
- acierto total: 18/20, IC 95 % [70%, 97%]

## Resumen

| sistema | extractiva | numérica | comparativa | hueco | total | recall@5 | coste medio | latencia media | tool calls/pregunta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| final | 83% | 100% | 83% | 100% | 90% | 92% | 1.652 ¢ | 22.3 s | 2.6 |

## Por familia

| familia | preguntas | aciertos | qué falló |
| --- | --- | --- | --- |
| numerica | 8 | 8/8 | — |
| hueco | 3 | 3/3 | — |
| comparativa | 6 | 5/6 | no_respalda_ancla (1) |
| extractiva | 6 | 5/6 | sin_chunk_id (1), no_respalda_ancla (1) |

## Trayectoria

| trayectoria | preguntas | proporción |
| --- | --- | --- |
| camino correcto | 20 | 100% |
| camino equivocado, acierta | 0 | 0% |
| camino equivocado, falla | 0 | 0% |
| no aplica (sin herramienta_esperada) | 0 | — |

## Guardarraíl

| guardarraíl | valor |
| --- | --- |
| preguntas con intervención del guardarraíl | 25% |
| intervenciones totales | 5 |
| recuperadas tras intervenir (respuesta correcta) | 80% |
| preguntas que agotaron el límite de llamadas | 0 |
| alucinaciones sobre hueco | 0 |
| abstenciones indebidas (dijo «no hay dato» y sí lo había) | 0% |

## Retrieval

| recall@1 | recall@3 | recall@5 | recall@10 | MRR |
| --- | --- | --- | --- | --- |
| 67% | 92% | 92% | 92% | 0.78 |

| pregunta | puesto del ancla |
| --- | --- |
| g-r-005 | 2 |
| g-r-006 | 1 |
| g-r-007 | 1 |
| g-r-008 | 3 |
| g-r-009 | > 10 |
| g-r-010 | 1 |
| g-r-011 | 1 |
| g-r-012 | 1 |
| g-r-017 | 1 |
| g-r-018 | 1 |
| g-r-019 | 1 |
| g-r-020 | 2 |

## Por pregunta

| id | familia | acierto | herramientas | qué falló |
| --- | --- | --- | --- | --- |
| g-r-001 | numerica | sí | list_available > get_xbrl_fact |  |
| g-r-002 | numerica | sí | list_available > get_xbrl_fact |  |
| g-r-003 | numerica | sí | get_xbrl_fact |  |
| g-r-004 | numerica | sí | list_available > get_xbrl_fact > get_xbrl_fact |  |
| g-r-005 | comparativa | sí | list_available > get_xbrl_fact > get_xbrl_fact > search_filings |  |
| g-r-006 | comparativa | sí | list_available > get_xbrl_fact > get_xbrl_fact > search_filings |  |
| g-r-007 | extractiva | sí | list_available > search_filings |  |
| g-r-008 | extractiva | sí | list_available > search_filings |  |
| g-r-009 | extractiva | no | search_filings > list_available > search_filings > search_filings | sin_chunk_id (1), no_respalda_ancla (1) |
| g-r-010 | extractiva | sí | list_available > search_filings |  |
| g-r-011 | extractiva | sí | list_available > search_filings |  |
| g-r-012 | extractiva | sí | list_available > search_filings |  |
| g-r-013 | numerica | sí | get_xbrl_fact |  |
| g-r-014 | numerica | sí | list_available > get_xbrl_fact |  |
| g-r-015 | numerica | sí | list_available > get_xbrl_fact |  |
| g-r-016 | numerica | sí | list_available > get_xbrl_fact |  |
| g-r-017 | comparativa | sí | list_available > get_xbrl_fact > get_xbrl_fact > search_filings |  |
| g-r-018 | comparativa | no | get_xbrl_fact > get_xbrl_fact > search_filings | no_respalda_ancla (1) |
| g-r-019 | comparativa | sí | list_available > get_xbrl_fact > get_xbrl_fact > search_filings |  |
| g-r-020 | comparativa | sí | list_available > get_xbrl_fact > get_xbrl_fact > search_filings |  |
