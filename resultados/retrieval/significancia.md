Contraste contra «denso (base)» sobre recall@5, 12 preguntas con ancla. McNemar exacto, pareado.

| configuración | recall@5 | arregla | rompe | p |
| --- | --- | --- | --- | --- |
| + filtro metadatos | 0.67 | 5 | 0 | 0.062 (n. s.) |
| + BM25 (híbrido RRF) | 0.58 | 4 | 0 | 0.125 (n. s.) |
| + reescritura de consulta | 0.75 | 6 | 0 | 0.031 |
| todo | 0.92 | 8 | 0 | 0.008 |
| + reordenación (cross-encoder) | 0.58 | 4 | 0 | 0.125 (n. s.) |
| + reescritura + reordenación | 0.83 | 7 | 0 | 0.016 |
| todo + reordenación | 0.83 | 7 | 0 | 0.016 |
| + reescritura + reordenación (RRF) | 0.92 | 8 | 0 | 0.008 |
| todo + reordenación (RRF) | 0.92 | 8 | 0 | 0.008 |
