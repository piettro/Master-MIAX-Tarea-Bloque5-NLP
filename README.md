# Agente investigador sobre informes 10-K

Responde preguntas sobre los 10-K de NVDA, MSFT, AAPL, GOOGL, META y AMZN
(FY2024 y FY2025, items 1A, 7, 7A y 8) **citando de dónde sale cada dato**.

Práctica de *LLMs aplicados a Finanzas* · MIAX, Instituto BME · Piettro, Alonso y Raúl.

## Quickstart

```bash
git clone <este-repo> agente-10k && cd agente-10k
python -m venv .venv && .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .                                 # o: make setup
cp .env.example .env                             # y pon tu OPENROUTER_API_KEY
# descomprime corpus_miax_2026.zip e indice_faiss.zip dentro de data/corpus/
python -m agente_10k.cli diagnostico             # dice qué hay y qué falta
python -c "from agente_10k import responder; print(responder('¿Cuál fue el revenue de NVIDIA en el ejercicio 2024?'))"
python -c "from agente_10k import evaluar; print(evaluar('golden/golden_set.jsonl'))"
```

Las dos últimas líneas son el CONTRATO C5 y son lo que se ejecuta el día 24
sobre diez preguntas ciegas, sin editar nada.

## Corpus

No se versiona: lo reparte el profesor en dos ZIP. Descomprimidos, la estructura
que espera el código es la del notebook de la sesión 1:

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

`agente-10k diagnostico` dice qué falta. Si falta `secciones.jsonl`, el sistema
deriva las secciones de los fragmentos y **lo dice**: no son literales en las
fronteras de troceado (ver `docs/decisiones.md`, ADR-004).

## Las cuatro herramientas

| Herramienta | Coste | Precisión | Para qué |
| --- | --- | --- | --- |
| `list_available()` | gratis | exacta | Comprobar qué hay antes de inventárselo |
| `get_xbrl_fact(ticker, fiscal_year, concept)` | gratis | **exacta** | Cualquier cifra. Autorizada |
| `search_filings(query, ticker, fiscal_year, item, k)` | media | difusa | Riesgos, estrategia, MD&A |
| `read_section(ticker, fiscal_year, item)` | **alta** | exacta | Último recurso: decenas de miles de tokens |

Los nombres y los parámetros son contrato (C1) y no se cambian. Los docstrings
de `src/agente_10k/tools/contratos.py` son lo único que ve el modelo para
decidir cuál llamar: son parte funcional del sistema, no documentación (C2).

**La asimetría de esa tabla es el eje de la práctica.** Acertar una cifra
leyéndola de la prosa cuenta como fallo aunque el número salga bien, porque ese
camino no generaliza. Hay un evaluador escrito para detectarlo.

## Órdenes

```bash
make setup     lint     test     cobertura
make baseline  final    informe  pdf       ablacion
make validar-golden
```

`make pdf` monta `docs/informe/informe.pdf` desde `docs/informe/plantilla.md`:
la prosa es la plantilla y las tablas se incluyen desde `resultados/`. Lo que
todavía no existe sale como PENDIENTE y el PDF se genera igual.

Sin `make` —Windows— lo mismo con `python scripts/tareas.py <objetivo>`.

## Estructura

```
src/agente_10k/
├── dominio/      modelos, protocolos, errores, tolerancia — no sabe de LangChain
├── corpus/       los tres repositorios (P3)
├── retrieval/    Strategy (P1) + Decorator (P2)
├── tools/        las cuatro firmas (C1) y sus docstrings (C2)
├── agente/       proveedor (P5), prompt, middleware (P4), trazas
├── evaluacion/   los tres evaluadores, métricas, ejecutor, tablas
└── baseline/     la implementación del profesor, intacta
golden/           el golden set y su validador
resultados/       baseline congelado, final, ciegas — regenerables
docs/decisiones.md  los ADR: por qué cada cosa es como es
```

## Estado

Hechos: dominio, corpus, herramientas, retrieval con su tabla de ablación,
golden set de 20 preguntas, evaluación completa y el informe en PDF. El
baseline está ejecutado y congelado en `resultados/baseline/` con su
`SELLO.json`.

Falta la fase 4 —el agente final, su middleware y el guardarraíl XBRL—, y con
ella la mitad derecha de la tabla del informe. `docs/decisiones.md` dice por qué
cada cosa es como es.
