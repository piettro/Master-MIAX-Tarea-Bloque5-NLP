# Agente investigador sobre informes 10-K

Responde preguntas sobre los 10-K de NVDA, MSFT, AAPL, GOOGL, META y AMZN
(FY2024 y FY2025, items 1A, 7, 7A y 8) **citando de dónde sale cada dato**.

Práctica de *LLMs aplicados a Finanzas* · MIAX, Instituto BME.

**Autores:** Alonso, Piettro y Raúl.

## Instalación

```bash
git clone <este-repo> agente-10k && cd agente-10k
python -m venv .venv && .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .                                 # o: make setup
cp .env.example .env                             # y pon tu OPENROUTER_API_KEY
# descomprime corpus_miax_2026.zip e indice_faiss.zip dentro de data/corpus/
agente-10k diagnostico                           # dice qué hay y qué falta
```

## Uso

Desde Python, las dos funciones que pide el enunciado (CONTRATO C5):

```python
from agente_10k import responder, evaluar

respuesta = responder("¿Cuál fue el revenue de NVIDIA en el ejercicio 2024?")
print(respuesta.cifra, respuesta.unidad, respuesta.fuente, respuesta.cita)

informe = evaluar("ciegas.jsonl")   # un JSONL de preguntas, una por línea
print(informe)                      # aciertos, coste y latencia
```

Desde la terminal, lo mismo:

```bash
agente-10k responder "¿Cuál fue el revenue de NVIDIA en el ejercicio 2024?"
agente-10k evaluar ciegas.jsonl --etiqueta ciegas
```

`evaluar` acepta preguntas con solo `id` y `pregunta`: los evaluadores que no
pueden aplicarse devuelven «no aplica» en vez de fallar. El detalle y el
resumen quedan en `resultados/<etiqueta>/`, y `agente-10k informe` regenera las
tablas en `resultados/tablas/`, incluida la comparación con las ciegas.

Sin `make` —Windows— `agente-10k` equivale a `python -m agente_10k.cli`.

## Corpus

No se versiona: lo reparte el profesor en dos ZIP. Descomprimidos:

```
data/corpus/
├── secciones.jsonl        48 secciones, el texto íntegro   → read_section
├── chunks.jsonl           1.749 fragmentos con chunk_id    → search_filings
├── xbrl_facts.parquet     135 hechos numéricos             → get_xbrl_fact
└── indice/
    ├── corpus.faiss       IndexFlatIP, 1.749 × 384
    ├── chunks_meta.parquet   alineado fila a fila con el índice
    └── MANIFEST.md        versionado: documenta el prefijo de la consulta
```

Si falta `secciones.jsonl`, el sistema deriva las secciones de los fragmentos y
**lo dice**: no son literales en las fronteras de troceado.

## Las cuatro herramientas

| Herramienta | Coste | Precisión | Para qué |
| --- | --- | --- | --- |
| `list_available()` | gratis | exacta | Comprobar qué hay antes de inventárselo |
| `get_xbrl_fact(ticker, fiscal_year, concept)` | gratis | **exacta** | Cualquier cifra. Autorizada |
| `search_filings(query, ticker, fiscal_year, item, k)` | media | difusa | Riesgos, estrategia, MD&A |
| `read_section(ticker, fiscal_year, item)` | **alta** | exacta | Último recurso: decenas de miles de tokens |

Los docstrings de `src/agente_10k/tools/contratos.py` son lo único que ve el
modelo para decidir cuál llamar: son parte funcional del sistema. Acertar una
cifra leyéndola de la prosa cuenta como fallo aunque el número salga bien, y hay
un evaluador escrito para detectarlo.

## Cómo funciona

```
pregunta ─► agente (create_agent, ReAct) ─► herramientas ─► RespuestaFinanciera
              │
              └─ middleware: reintento · modelo de reserva · límite de llamadas
                             · guardarraíl XBRL · petición de salida estructurada
```

- **Retrieval** de `search_filings`: híbrido denso + BM25, filtro de metadatos
  antes de buscar, consulta reescrita al inglés por el modelo y reordenación
  con cross-encoder fusionada por RRF. Es la configuración por defecto.
- **Guardarraíl XBRL**: si la cifra de la respuesta no cuadra con el hecho XBRL
  (0,5 % o 1 USD), le devuelve el desajuste al modelo. Nunca corrige la cifra.
- **Evaluación**: tres evaluadores —cita, cifra y trayectoria—. Acierto es
  respuesta correcta **y** camino correcto. Cada proporción lleva su intervalo
  de Wilson y la comparación entre sistemas, un contraste de McNemar exacto.

## Golden set

`golden/golden_set.jsonl`: 20 preguntas propias, 8 numéricas (3 de ellas huecos:
el dato no está en el corpus), 6 comparativas y 6 extractivas. Las extractivas
se anclan a una frase literal del informe, no a un `chunk_id`.

```bash
agente-10k validar-golden golden/golden_set.jsonl
```

## Resultados

Todo lo genera el repositorio; nada se escribe a mano.

```
resultados/
├── baseline/                      el agente del profesor, CONGELADO (SELLO.json)
├── final/                         nuestro sistema
├── final-sin-mejoras-retrieval/   el final con el retrieval del baseline
├── retrieval/                     la tabla de ablación y su contraste
├── ciegas/                        las 10 preguntas del día 24
└── tablas/                        baseline contra final, contraste y resúmenes
```

El baseline se ejecutó y congeló antes de mejorar nada: `SELLO.json` guarda el
SHA-256 de cada fichero y un test comprueba que no cambian.

## Órdenes

```bash
make setup     lint     test     cobertura
make baseline  final    informe  ablacion
make validar-golden
```

## Contratos

El código cita estos compromisos por su número. Salen del enunciado.

| | Qué fija |
| --- | --- |
| C1 | Nombres y parámetros de las cuatro herramientas |
| C2 | Sus docstrings: es lo que lee el modelo para elegir |
| C3 | El esquema `RespuestaFinanciera`; se pueden añadir campos con valor por defecto, no quitar |
| C4 | El esquema de una pregunta del golden set |
| C5 | `responder()` y `evaluar()`, ejecutables sobre un clon limpio sin tocar nada |
| C6 | Ninguna clave de API en el repositorio |

## Estructura

```
src/agente_10k/
├── dominio/      modelos, protocolos, errores, tolerancia — no sabe de LangChain
├── corpus/       los tres repositorios (secciones, fragmentos, XBRL)
├── retrieval/    recuperadores (Strategy) y mejoras (Decorator)
├── tools/        las cuatro herramientas y sus docstrings
├── agente/       proveedor, prompt, middleware y trazas
├── evaluacion/   los tres evaluadores, métricas, estadística, ejecutor y tablas
├── baseline/     la implementación del profesor, intacta
└── cli.py        la orden `agente-10k`
golden/           el golden set y su validador
resultados/       baseline congelado, final, ablación y tablas
tests/            la suite; los tests contra el modelo real se saltan sin clave
```
