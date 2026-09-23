| configuración | recall@1 | recall@3 | recall@5 | recall@10 | MRR | latencia media (s) | coste medio ($) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| denso (base) | 0.00 | 0.00 | 0.25 | 0.25 | 0.06 | 751.8 ms | 0.00000 |
| + filtro metadatos | 0.25 | 0.50 | 0.67 | 0.83 | 0.44 | 252.8 ms | 0.00000 |
| + BM25 (híbrido RRF) | 0.25 | 0.50 | 0.58 | 0.67 | 0.40 | 256.4 ms | 0.00000 |
| + reescritura de consulta | 0.67 | 0.67 | 0.75 | 0.92 | 0.71 | 4904.4 ms | 0.00192 |
| todo | 0.58 | 0.83 | **0.92** | **1.00** | 0.74 | 4920.3 ms | 0.00192 |
| + reordenación (cross-encoder) | 0.17 | 0.25 | 0.58 | 0.75 | 0.32 | 711.3 ms | 0.00000 |
| + reescritura + reordenación | **0.83** | 0.83 | 0.83 | 0.92 | 0.85 | 5198.3 ms | 0.00192 |
| todo + reordenación | **0.83** | 0.83 | 0.83 | 0.92 | 0.85 | 5212.9 ms | 0.00192 |
| + reescritura + reordenación (RRF) | 0.67 | 0.75 | **0.92** | 0.92 | 0.74 | 5196.7 ms | 0.00192 |
| todo + reordenación (RRF) | 0.67 | **0.92** | **0.92** | 0.92 | 0.78 | 5167.6 ms | 0.00192 |
