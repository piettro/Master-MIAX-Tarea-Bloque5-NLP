# PROMPTS POR FASE — Agente 10-K (MIAX)

Cada fase es un prompt independiente para Claude Code. Están diseñados para que **los tres podáis
trabajar en paralelo sin pisaros**: cada fase toca ficheros distintos y su rama es distinta.

**Reglas comunes a todas las fases** (pégalas como preámbulo si Claude Code arranca en sesión nueva):

```text
Contexto obligatorio antes de empezar: lee `docs/PROMPT_MAESTRO.md`, `docs/enunciado.md`,
`docs/decisiones.md` y los ficheros de `class_transcription/`. Respeta los seis contratos
inviolables de la sección 2 del prompt maestro y los patrones de la sección 5. No toques
ficheros fuera de la lista "Ficheros que puedes modificar" de esta fase. Ejecuta
`make lint && make test` antes de dar la fase por terminada, y actualiza
`docs/decisiones.md` con cada decisión no obvia.
```

| Fase | Qué | Owner | Rama | Cierra |
|---|---|---|---|---|
| F0 | Scaffold (prompt maestro) | Piettro | `main` | 13 sep |
| F1 | Tools + baseline congelado | Piettro | `fase-1-tools` | 15 sep |
| F2 | Golden set de 20 preguntas | los tres, consolida Raúl | `fase-2-golden` | 16 sep |
| F3 | Retrieval medido | Alonso | `fase-3-retrieval` | 20 sep |
| F4 | Agente, middleware y guardrails | Piettro | `fase-4-agente` | 20 sep |
| F5 | Evaluadores, métricas y tablas | Raúl | `fase-5-evaluacion` | 21 sep |
| F6 | Integración, ensayo en clon limpio, informe | los tres | `main` | 23 sep |
| F7 | Preguntas ciegas y defensa | los tres | — | 24 sep |

---

## F1 — Cinturón de herramientas y baseline congelado

**Owner: Piettro** · rama `fase-1-tools`
**Ficheros que puedes modificar:** `src/agente_10k/tools/**`, `src/agente_10k/corpus/**`,
`src/agente_10k/baseline/**`, `tests/tools/**`, `tests/corpus/**`, `resultados/baseline/**`.

```text
Implementa el cinturón de herramientas del agente, respetando el CONTRATO C1 (nombres y
parámetros exactos) y el CONTRATO C2 (los docstrings son parte del sistema).

1. `list_available()`
   Devuelve, en texto compacto, el universo del corpus: empresa, ticker, ejercicios
   disponibles e items disponibles. Una línea por emisor. Construido con un groupby sobre
   el repositorio de secciones, nunca hardcodeado. Objetivo declarado en clase: que el
   agente NO intente buscar en un emisor o ejercicio que no existe; que lo diga en vez de
   lanzar un retrieval condenado a fallar. Menos de 400 tokens de salida.

2. `get_xbrl_fact(ticker, fiscal_year, concept)`
   Fuente autorizada para cualquier cifra. Implementa la TRAMPA T2 del prompt maestro:
   cuando el concepto no existe para ese (ticker, fiscal_year), NO devuelvas un error seco.
   Devuelve un texto que (a) diga que ese concepto no está reportado por ese emisor,
   (b) liste los conceptos que SÍ existen para ese ticker y ejercicio, y (c) si hay un
   sinónimo plausible (Revenues ↔ RevenueFromContractWithCustomerExcludingAssessedTax),
   lo sugiera EXPLÍCITAMENTE sin aplicarlo por su cuenta. La decisión la toma el agente,
   no la tool. Distingue en el texto dos casos que no son lo mismo: "concepto mal escrito
   o no aplicable" y "hueco real en us-gaap" (Amazon sin GrossProfit, Liabilities ni
   ResearchAndDevelopmentExpense; Meta y Alphabet sin GrossProfit). En el segundo caso el
   texto debe inducir `fuente="ninguna"`, no una estimación.
   Devuelve siempre valor, unidad, concepto exacto y ejercicio, para que el agente pueda
   rellenar el schema sin inferir nada.

3. `search_filings(query, ticker, fiscal_year, item, k)`
   De momento delega en el recuperador denso que ya existe (FAISS + bge-small-en-v1.5).
   OJO: el manifiesto del índice documenta un prefijo que va en la CONSULTA y no en los
   fragmentos; si lo pones en ambos o en ninguno, el recall se hunde en silencio. Escribe
   un test que lo fije.
   El retorno incluye, por fragmento: chunk_id, ticker, fiscal_year, item, score y texto.
   El chunk_id es lo que permite verificar una cita: nunca lo omitas ni lo reformatees.
   La mejora del recuperador es la fase 3 (Alonso): aquí solo defines la interfaz estable
   contra `dominio/protocolos.py::Recuperador` para que él pueda enchufar el suyo.

4. `read_section(ticker, fiscal_year, item)`
   Texto completo de una sección. Es CARA (decenas de miles de tokens; el item 1A de Meta
   ronda los 34.000). El docstring debe decir explícitamente cuándo es el último recurso.
   Añade un parámetro OPCIONAL con valor por defecto que permita truncar o paginar
   (p.ej. `max_tokens: int | None = None`) — está permitido por el contrato y baja el
   coste medio por pregunta, que es una columna de la tabla del informe.

5. Baseline.
   Copia la implementación del profesor a `src/agente_10k/baseline/` SIN modificarla.
   Ejecútala sobre el corpus y guarda en `resultados/baseline/` la salida etiquetada con
   fecha, versión del modelo y hash del commit. A partir de ese momento ese directorio es
   de solo lectura: es media tabla del informe. Añade un test que falle si cambia.

Criterios de aceptación:
  [ ] Las cuatro tools devuelven str y son invocables desde el REPL sin API key.
  [ ] Tests con fixtures diminutas, sin corpus completo y sin red.
  [ ] Test que verifica el prefijo de la consulta en el recuperador denso.
  [ ] `get_xbrl_fact("AMZN", 2025, "GrossProfit")` produce un texto de hueco real.
  [ ] `get_xbrl_fact("NVDA", 2024, "RevenueFromContractWithCustomerExcludingAssessedTax")`
      sugiere `Revenues`.
  [ ] `resultados/baseline/` congelado y documentado.
```

---

## F2 — Golden set propio (20 preguntas)

**Owner: los tres escriben, Raúl consolida** · rama `fase-2-golden`
**Ficheros:** `golden/**`, `tests/golden/**`.

> **Reparto para evitar duplicados y colisiones de id:**
> Piettro `g-p-001…007` · Alonso `g-a-001…007` · Raúl `g-r-001…006`.
> Cada uno escribe **en su propio fichero** `golden/parciales/<nombre>.jsonl`; Raúl los fusiona
> en `golden/golden_set.jsonl`. Así no hay merge conflicts en un JSONL.

```text
Escribe y valida el golden set propio, conforme al CONTRATO C4.

Composición obligatoria (20 preguntas):
  - ≥ 6 COMPARATIVAS entre dos ejercicios (FY2024 vs FY2025 del mismo emisor, o dos
    emisores en el mismo ejercicio). Miden si el agente encadena dos consultas exactas
    en vez de improvisar.
  - EXTRACTIVAS: miden retrieval y trazabilidad. La verdad se ancla a una FRASE LITERAL
    del informe, de una sola frase, en `ancla_texto`. NO a un chunk_id: el identificador
    cambia en cuanto se re-trocea el corpus, y el grupo que mejore el troceado no puede
    salir penalizado por haberlo mejorado. `chunk_id_esperado` queda a null.
  - NUMÉRICAS: miden el guardarraíl contra XBRL. `concept_xbrl` y `cifra_esperada`
    obligatorios, y `herramienta_esperada` = ["get_xbrl_fact"].
  - ≥ 2 preguntas de HUECO REAL (Amazon GrossProfit / Liabilities / R&D; Meta o Alphabet
    GrossProfit). Respuesta esperada: que el dato no está en el corpus. `cifra_esperada`
    null, `unidad` null, `fuente` esperada "ninguna".
  - ≥ 1 pregunta trampa de FISCAL YEAR: formulada de modo que confundir año de
    presentación con ejercicio dé una respuesta distinta (NVDA FY2025 cerró en enero de
    2025; GOOGL FY2025 se presentó en 2026).
  - ≥ 1 pregunta trampa de CONCEPTO XBRL: revenue de un emisor cuyo concepto no es el
    que usa la mayoría.

Reglas de calidad, no negociables:
  - Cada `ancla_texto` debe aparecer LITERALMENTE en `secciones.jsonl`. El validador lo
    comprueba; si no aparece, la pregunta es inválida, no "casi bien".
  - `respuesta_esperada` en prosa, breve, con la unidad explícita.
  - `cifra_esperada` en unidades base (USD, no millones) y verificada contra
    `xbrl_facts.parquet`, nunca contra el texto.
  - `herramienta_esperada` refleja el CAMINO CORRECTO, no cualquier camino que acierte.
    Es la entrada del evaluador de trayectoria: acertar por el camino equivocado es fallo.
  - `autor` con tu identificador, para poder auditar de dónde vino cada pregunta.

Además:
  - Extiende `golden/validador.py` con las reglas de arriba y haz que su salida sea un
    informe legible ("faltan 2 comparativas", "g-a-004: el ancla no aparece en el corpus").
  - Escribe `tests/golden/test_golden_set.py` que ejecute el validador sobre el fichero
    real y falle si el set no cumple. Esto tiene que estar en verde antes del 17 de sep:
    la sesión 2 empieza ejecutando nuestro baseline y clasificando sus fallos.
```

---

## F3 — Mejora medida del retrieval

**Owner: Alonso** · rama `fase-3-retrieval`
**Ficheros:** `src/agente_10k/retrieval/**`, `tests/retrieval/**`, `resultados/retrieval/**`.

```text
Partiendo del recuperador denso que se entrega, implementa y MIDE al menos las tres
mejoras que exige el enunciado. La palabra clave es "medida": un arreglo razonable que no
mueve la métrica es un resultado publicable, y hay que llevarlo a la presentación.

Implementa como Strategy + Decorator (sección 5 del prompt maestro):
  1. `filtro_metadatos.py` — decorador que aplica ticker / fiscal_year / item ANTES de la
     búsqueda, no después (filtrar después de recuperar k desperdicia el presupuesto de k).
  2. `lexico.py` — BM25 sobre los mismos 1.749 fragmentos. Documenta el tokenizador: en
     texto financiero, los números y los guiones importan.
  3. `hibrido.py` — fusión de denso + BM25. Usa Reciprocal Rank Fusion (no suma de scores:
     no son comparables entre sí). El parámetro k de RRF va en configuración, no fijo.
  4. `reescritura.py` — decorador que reescribe la consulta con el propio LLM antes de
     buscar. Mide también su COSTE: añade una llamada por pregunta y eso entra en la tabla.

Medición (esto es la mitad del trabajo de la fase):
  - Métrica: recall@k contra el ANCLA DE TEXTO del golden set, no contra chunk_id. Un
    fragmento cuenta como acierto si contiene el ancla literal. Reporta k ∈ {1, 3, 5, 10}.
  - Tabla de ablación, generada por código a `resultados/retrieval/ablacion.csv` y .md:
        configuración | recall@1 | recall@3 | recall@5 | recall@10 | latencia media | coste medio
        denso (base)
        + filtro metadatos
        + BM25 (híbrido RRF)
        + reescritura de consulta
        todo
  - Cada fila se obtiene ejecutando el MISMO runner con una configuración distinta. Si
    tienes que duplicar código para sacar una fila, el diseño está mal.
  - Guarda también el detalle por pregunta, para poder explicar en la defensa QUÉ
    preguntas arregló cada mejora y cuáles rompió. Una mejora que sube la media y rompe
    tres preguntas concretas es una historia mucho mejor contada que un número suelto.

Criterios de aceptación:
  [ ] Cambiar de configuración es cambiar Settings, no editar código.
  [ ] `make retrieval-ablacion` regenera la tabla entera desde cero.
  [ ] Tests unitarios de RRF con rankings sintéticos (sin modelo, sin red).
  [ ] En `docs/decisiones.md`: qué probaste que NO funcionó y por qué crees que no funcionó.
```

---

## F4 — Agente, middleware y guardarraíles

**Owner: Piettro** · rama `fase-4-agente`
**Ficheros:** `src/agente_10k/agente/**`, `src/agente_10k/config.py`,
`src/agente_10k/__init__.py`, `tests/agente/**`.

```text
Monta el agente con salida estructurada obligatoria y sus guardarraíles.

1. Proveedor de LLM (Factory + Adapter).
   `LLM_PROVIDER` y `LLM_MODEL` por entorno. Soporta openrouter | anthropic | google |
   openai. Fallback ordenado ante 401/402/429 hacia un modelo alternativo, con VARIABLE DE
   ESTADO: una vez agotado el primario, no se reintenta en cada llamada. temperature=0.

2. System prompt (`prompts.py`, versionado con un identificador que se guarda en la traza).
   Debe: fijar el rol; describir el criterio de enrutado entre tool exacta y tool difusa;
   autorizar EXPLÍCITAMENTE la no-respuesta cuando el dato no está en el corpus; prohibir
   leer cifras de la prosa cuando existe la vía XBRL; exigir cita literal para todo lo
   extractivo. Cada regla del prompt debe poder rastrearse a una pregunta del golden set.

3. Salida estructurada: `RespuestaFinanciera` (CONTRATO C3) como response format del
   agente. Si el modelo no consigue producirla, un reintento con el error de validación
   devuelto; si vuelve a fallar, respuesta con `fuente="ninguna"` y el motivo, nunca una
   excepción que rompa la ejecución del golden set.

4. Middleware (Chain of Responsibility):
   a) `LimitadorLlamadas(max_llamadas=N)`. N configurable, por defecto 8. Al superarlo,
      corta e inyecta un mensaje que explica al modelo que agotó su presupuesto y debe
      responder con lo que tenga o declarar que no lo sabe.
   b) `GuardarraílXBRL`. Extrae la(s) cifra(s) de la respuesta estructurada y las
      contrasta contra el repositorio XBRL. Tolerancia DOCUMENTADA (p.ej. 0,5% relativo
      o redondeo a millones declarado) y definida en un solo sitio, compartida con el
      evaluador de cifra de la fase 5. Si no cuadra: devuelve el desajuste al modelo
      (valor afirmado vs valor XBRL vs concepto consultado) y deja que reintente. NO
      corrige la cifra por su cuenta: eso enmascara el fallo y falsea la evaluación.
      Registra en la traza cada intervención: "cuántas veces saltó el guardarraíl" es de
      las cifras más interesantes de la presentación.

5. Trazas (`trazas.py`). Por invocación, captura: secuencia de tool calls con sus
   argumentos, tokens prompt/completion, coste (leído de los metadatos de uso del
   proveedor, no estimado a mano), latencia total y por paso, reintentos del guardarraíl,
   versión del prompt y configuración de retrieval. Serializable a JSON: es la entrada
   del evaluador de trayectoria y de toda la tabla del informe.

6. `responder(pregunta: str) -> RespuestaFinanciera` expuesto en `agente_10k/__init__.py`
   (CONTRATO C5), construyendo el agente desde Settings, sin argumentos obligatorios.

Criterios de aceptación:
  [ ] Toda la suite de tests del agente corre con un `ProveedorFake`, sin red ni API key.
  [ ] Test: el limitador corta a la llamada N+1.
  [ ] Test: ante una cifra deliberadamente errónea, el guardarraíl devuelve el desajuste
      y la traza registra el reintento.
  [ ] Test: pregunta sobre un emisor fuera del corpus → `fuente="ninguna"`, sin retrieval.
  [ ] `responder("¿Cuál fue el revenue de NVIDIA en el ejercicio 2024?")` devuelve
      `fuente="xbrl"` y la trayectoria pasa por `get_xbrl_fact`.
```

---

## F5 — Los tres evaluadores, métricas e informe

**Owner: Raúl** · rama `fase-5-evaluacion`
**Ficheros:** `src/agente_10k/evaluacion/**`, `tests/evaluacion/**`, `docs/informe/**`.

```text
Escribe los tres evaluadores del enunciado y el aparato de métricas que genera las tablas
del informe. Ninguna cifra del PDF se escribe a mano: todas salen de aquí.

Evaluador 1 — CITA. Verifica que la cita existe y que respalda de verdad lo que se afirma.
  - La cita debe aparecer literalmente en el corpus (match exacto normalizado; documenta
    la normalización: espacios, comillas tipográficas, saltos de línea).
  - El chunk_id declarado debe contener esa cita. Si el agente cita bien pero atribuye mal
    el chunk_id, es fallo de trazabilidad y se reporta aparte.
  - Debe cubrir la sección/emisor/ejercicio que la pregunta pedía: una cita correcta del
    documento equivocado es fallo.

Evaluador 2 — CIFRA. Verifica que el número coincide con XBRL dentro de una tolerancia
  DOCUMENTADA, y que la unidad declarada es coherente. Importa el mismo objeto de
  tolerancia que usa el guardarraíl de la fase 4: un solo sitio, o los dos números se
  separarán y la tabla dejará de ser defendible. Caso especial obligatorio: cuando la
  respuesta esperada es un hueco, acertar significa `cifra=None` y `fuente="ninguna"`;
  dar una cifra plausible es el peor fallo posible y debe reportarse como categoría
  propia ("alucinación sobre hueco").

Evaluador 3 — TRAYECTORIA. Verifica que la respuesta pasó por la herramienta que tocaba,
  comparando la secuencia de tool calls de la traza con `herramienta_esperada`. Acertar
  por el camino equivocado cuenta como FALLO y se reporta en su propia columna: es el
  criterio central de la práctica. Distingue tres estados: camino correcto, camino
  incorrecto con respuesta correcta, camino incorrecto con respuesta incorrecta.

Métricas y agregación (`metricas.py`):
  - Aciertos por familia (extractiva / numérica / comparativa / hueco).
  - recall@k del retrieval (consume el runner de la fase 3, no lo reimplementa).
  - Coste medio por pregunta, latencia media, llamadas a herramienta por pregunta.
  - Tasa de intervención del guardarraíl y tasa de recuperación tras intervención.

`evaluar(ruta_jsonl) -> InformeEvaluacion` (CONTRATO C5): lee un JSONL de preguntas,
ejecuta `responder()` sobre cada una, aplica los tres evaluadores, agrega y escribe a
`resultados/<etiqueta>/` el detalle por pregunta y el resumen. Tiene que funcionar el día
24 sobre 10 preguntas ciegas, en clase, sin tocar código y sin que un fallo en una
pregunta aborte las otras nueve.

`informe.py` genera la TABLA PRINCIPAL del informe en markdown y csv:

    sistema  | aciertos extractiva | numérica | comparativa | hueco | recall@5 | coste medio | latencia media | tool calls/pregunta
    baseline |
    final    |

  con el mejor valor de cada columna REMARCADO. Coste y latencia son columnas de la
  tabla, no una nota al pie.

Criterios de aceptación:
  [ ] `evaluar()` sobre el golden set produce la tabla completa sin intervención manual.
  [ ] Tests de cada evaluador con trazas sintéticas: caso correcto, caso con cita del
      documento equivocado, caso de acierto por camino equivocado, caso de alucinación
      sobre hueco.
  [ ] Una pregunta que lanza excepción se marca como fallo y la ejecución continúa.
  [ ] `make informe` regenera todas las tablas desde `resultados/`.
```

---

## F6 — Integración y ensayo en clon limpio

**Owner: los tres** · rama `main`

```text
Cierra el proyecto. Esta fase no añade funcionalidad: la hace defendible.

1. Ensayo de clon limpio, en una máquina o contenedor distinto:
       git clone <repo> /tmp/ensayo && cd /tmp/ensayo
       pip install -e .
       export LLM_API_KEY=...
       python -c "from agente_10k import responder; print(responder('¿Cuál fue el revenue de NVIDIA en el ejercicio 2024?'))"
       python -c "from agente_10k import evaluar; evaluar('golden/golden_set.jsonl')"
   Si algo falla aquí, falla el día 24 delante de la clase. Hazlo al menos dos veces, y la
   segunda que la haga alguien que no escribió ese código.

2. Ejecuta el sistema final sobre el golden set y guarda en `resultados/final/`. Genera la
   tabla baseline vs final. Si alguna métrica empeoró, NO la escondas: explícala.

3. Informe PDF (docs/informe/). Estructura sugerida, 6–8 páginas:
   - Arquitectura y criterio de enrutado entre tool exacta y tool difusa.
   - Tabla baseline vs final y su lectura: qué mejoró, cuánto y a qué coste. La pregunta
     que se hará a todos los grupos es si las mejoras mejoraron algo DE VERDAD y qué
     costaron. Ten la respuesta con números.
   - Ablación del retrieval (tabla de la fase 3).
   - Guardarraíles: qué protege al sistema de afirmar una cifra no verificada, cuántas
     veces saltó, cuántas veces recuperó.
   - Qué se probó que NO funcionó. Un arreglo razonable que no movió la métrica es un
     resultado, y es la sección que distingue a un grupo que midió de uno que adivinó.
   - Limitaciones y qué haríamos con una semana más.

4. Higiene final:
   [ ] `git log -p | grep -i "api.key\|sk-"` no devuelve nada.
   [ ] `.env` no está versionado; `.env.example` sí.
   [ ] README con quickstart verificado.
   [ ] `resultados/baseline/` intacto desde el 15 de septiembre.
   [ ] Todas las tablas del PDF regenerables con `make informe`.

5. Presentación de 8 minutos. Guion: 1' problema y arquitectura · 2' tabla baseline vs
   final · 2' enrutado y guardarraíles · 1,5' ablación de retrieval · 1' lo que no
   funcionó · 0,5' cierre. Ensayadla cronometrada. Ocho minutos son cortísimos.
```

---

## F7 — Día 24: preguntas ciegas

**Owner: los tres**

```text
Al empezar la clase se entregan 10 preguntas que no ha visto nadie, se ejecutan en el aula
contra el repositorio YA entregado y el resultado entra en la presentación.

Protocolo, ensayado antes:
  1. Clon limpio ya hecho y dependencias instaladas ANTES de que empiece la clase.
  2. Guardar las 10 preguntas en `resultados/ciegas/preguntas.jsonl` con el mismo esquema.
     Si llegan en prosa, solo `id` y `pregunta` son obligatorios: `evaluar()` debe tolerar
     campos ausentes y degradar los evaluadores que no pueda aplicar, no abortar.
     COMPRUEBA ESTO ANTES DEL DÍA 24: es el fallo más probable de toda la práctica.
  3. `evaluar('resultados/ciegas/preguntas.jsonl')` y volcar la tabla.
  4. Calcular el DELTA contra el golden set propio.

Si el resultado BAJA respecto al golden set propio, esa es la diapositiva más valiosa que
vais a tener: hay que explicar qué parte de la mejora era general y qué parte era memoria
del conjunto con el que iterasteis. Eso es un hallazgo sobre sobreajuste al set de
desarrollo, no un suspenso. Llevadla preparada de antemano, con la hipótesis escrita.
```
