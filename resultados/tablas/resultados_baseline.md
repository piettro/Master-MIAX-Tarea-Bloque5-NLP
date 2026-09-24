# Resultados · baseline

- fecha: 2026-09-23 19:35 UTC
- modelo: openrouter:google/gemini-3.8-flash
- commit: 6800450
- preguntas: 20 (golden\golden_set.jsonl)
- acierto total: 11/20, IC 95 % [34%, 74%]

## Resumen

| sistema | extractiva | numérica | comparativa | hueco | total | recall@5 | coste medio | latencia media | tool calls/pregunta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 83% | 75% | 0% | 33% | 55% | 25% | 1.234 ¢ | 17.7 s | 3.4 |

## Por familia

| familia | preguntas | aciertos | qué falló |
| --- | --- | --- | --- |
| numerica | 8 | 6/8 | fuente_no_ninguna (2), cita_no_literal (1), alucinacion_sobre_hueco (1) |
| hueco | 3 | 1/3 | fuente_no_ninguna (2), cita_no_literal (1), alucinacion_sobre_hueco (1) |
| comparativa | 6 | 0/6 | cifra_no_coincide (5), cita_no_literal (1), no_respalda_ancla (1) |
| extractiva | 6 | 5/6 | error de ejecución (1) |

## Trayectoria

| trayectoria | preguntas | proporción |
| --- | --- | --- |
| camino correcto | 19 | 100% |
| camino equivocado, acierta | 0 | 0% |
| camino equivocado, falla | 0 | 0% |
| no aplica (sin herramienta_esperada) | 1 | — |

## Guardarraíl

| guardarraíl | valor |
| --- | --- |
| preguntas con intervención del guardarraíl | 0% |
| intervenciones totales | 0 |
| recuperadas tras intervenir (respuesta correcta) | 0% |
| preguntas que agotaron el límite de llamadas | 0 |
| alucinaciones sobre hueco | 1 |
| abstenciones indebidas (dijo «no hay dato» y sí lo había) | 0% |

## Retrieval

| recall@1 | recall@3 | recall@5 | recall@10 | MRR |
| --- | --- | --- | --- | --- |
| 0% | 0% | 25% | 25% | 0.06 |

| pregunta | puesto del ancla |
| --- | --- |
| g-r-005 | > 10 |
| g-r-006 | > 10 |
| g-r-007 | > 10 |
| g-r-008 | > 10 |
| g-r-009 | > 10 |
| g-r-010 | > 10 |
| g-r-011 | 5 |
| g-r-012 | > 10 |
| g-r-017 | > 10 |
| g-r-018 | > 10 |
| g-r-019 | 4 |
| g-r-020 | 4 |

## Por pregunta

| id | familia | acierto | herramientas | qué falló |
| --- | --- | --- | --- | --- |
| g-r-001 | numerica | no | list_available > get_xbrl_fact > search_filings > search_filings > search_filings > get_xbrl_fact > get_xbrl_fact | cita_no_literal (1), alucinacion_sobre_hueco (1), fuente_no_ninguna (1) |
| g-r-002 | numerica | sí | list_available > get_xbrl_fact > search_filings > get_xbrl_fact |  |
| g-r-003 | numerica | sí | get_xbrl_fact |  |
| g-r-004 | numerica | sí | list_available > get_xbrl_fact |  |
| g-r-005 | comparativa | no | list_available > get_xbrl_fact > get_xbrl_fact > search_filings | cifra_no_coincide (1) |
| g-r-006 | comparativa | no | list_available > get_xbrl_fact > get_xbrl_fact > search_filings | cifra_no_coincide (1) |
| g-r-007 | extractiva | sí | list_available > search_filings |  |
| g-r-008 | extractiva | sí | list_available > search_filings |  |
| g-r-009 | extractiva | error | — | error de ejecución (1) |
| g-r-010 | extractiva | sí | list_available > search_filings |  |
| g-r-011 | extractiva | sí | list_available > search_filings > search_filings |  |
| g-r-012 | extractiva | sí | list_available > search_filings |  |
| g-r-013 | numerica | sí | list_available > get_xbrl_fact > search_filings > get_xbrl_fact > get_xbrl_fact |  |
| g-r-014 | numerica | sí | list_available > get_xbrl_fact |  |
| g-r-015 | numerica | sí | list_available > get_xbrl_fact |  |
| g-r-016 | numerica | no | list_available > get_xbrl_fact > search_filings > search_filings | fuente_no_ninguna (1) |
| g-r-017 | comparativa | no | list_available > get_xbrl_fact > get_xbrl_fact > search_filings | cita_no_literal (1) |
| g-r-018 | comparativa | no | list_available > get_xbrl_fact > get_xbrl_fact > search_filings | no_respalda_ancla (1), cifra_no_coincide (1) |
| g-r-019 | comparativa | no | list_available > get_xbrl_fact > get_xbrl_fact > get_xbrl_fact > search_filings | cifra_no_coincide (1) |
| g-r-020 | comparativa | no | list_available > get_xbrl_fact > get_xbrl_fact > search_filings > search_filings | cifra_no_coincide (1) |
