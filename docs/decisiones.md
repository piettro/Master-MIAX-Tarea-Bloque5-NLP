# Decisiones

Un registro por decisión no obvia: contexto, opciones, decisión, consecuencia.
Este fichero es la materia prima de la sección de arquitectura del informe, así
que se escribe pensando en que alguien lo va a leer para preguntarnos por qué.

Las decisiones de las fases 1 a 5 se añaden al final, sin reescribir las de
arriba. Una decisión que se revierte se marca como **revertida** y se explica
por qué; no se borra.

---

## ADR-001 · El material de clase viaja dentro del repositorio

**Contexto.** El `.gitignore` que había ignoraba `class_transcription/`,
`prompts/`, `pipeline/` y `materials/`. `PIPELINE.md` (HITO 0) exige lo
contrario: que las transcripciones y `docs/enunciado.md` estén *dentro* del
repo. Son dos instrucciones incompatibles.

**Opciones.** (a) Mantener el ignore y depender de que los tres tengamos los
ficheros en local. (b) Versionarlo todo, incluidos los `.docx` y los ZIP. (c)
Versionar el material textual y dejar fuera los binarios originales.

**Decisión.** (c). `class_transcription/`, `docs/enunciado.md`, `pipeline/` y
`prompts/` se versionan; `materials/` —los `.docx` y los ZIP tal cual llegaron
del aula virtual— no. `docs/enunciado.md` se genera del `.docx` y es la copia
que manda.

**Consecuencia.** El repositorio es autocontenido: quien lo clone puede leer el
enunciado y las clases sin pedir nada. A cambio, hay una conversión `.docx →
.md` que no se regenera automáticamente; si el profesor publica una corrección,
hay que rehacerla a mano.

---

## ADR-002 · Versiones fijadas, no rangos

**Contexto.** LangChain publica cada pocos días y sus cambios rompen. El
notebook de la sesión 1 dice explícitamente que los notebooks de la edición
anterior del curso ya no ejecutan: `create_react_agent`, `MemorySaver`,
`with_structured_output` y `RunnableWithMessageHistory` eran la API correcta
hace un año y hoy son otra cosa.

**Opciones.** (a) Rangos (`>=1.3`) y confiar en semver. (b) Versiones exactas,
las mismas del notebook del profesor. (c) Vendorizar.

**Decisión.** (b). `pyproject.toml` fija `langchain==1.3.18`,
`langchain-core==1.6.1`, `langgraph==1.2.11`, `langchain-openrouter==0.2.8`,
`langchain-huggingface==1.2.2`, `sentence-transformers==6.0.1`,
`faiss-cpu==1.15.0` y `rank-bm25==0.2.2`: exactamente las del notebook,
verificadas contra la documentación oficial el **2 de septiembre de 2026**.

**Consecuencia.** El clon limpio del día 24 instala lo mismo que probamos. La
fecha de verificación va escrita al lado del pin para saber cómo de viejo es lo
que estamos leyendo. Antes de tocar cualquier API de LangChain hay que consultar
documentación actualizada (Context7), nunca la memoria de un modelo.

---

## ADR-003 · Python 3.13 y el stack completo

**Contexto.** El Python por defecto de la máquina es 3.14, que todavía no tiene
ruedas para torch, faiss ni sentence-transformers. El prompt maestro pide 3.11+.

**Opciones.** (a) 3.14 con el retrieval degradado. (b) 3.13 con el stack
completo. (c) 3.10, máxima compatibilidad pero sin la sintaxis moderna de tipos
que exige el estándar de código.

**Decisión.** (b). `requires-python = ">=3.11"`, entorno sobre el 3.13 que ya
está instalado.

**Consecuencia.** Todo el stack instala. Aun así, el recuperador denso puede
leer el índice **sin faiss** (ver ADR-005), de modo que un fallo de instalación
en la máquina de cualquiera de los tres no bloquea la suite ni las métricas.

---

## ADR-004 · Secciones reconstruidas desde los fragmentos

**Contexto.** El corpus llega en dos ZIP. Hoy tenemos el del índice
(`corpus.faiss` + `chunks_meta.parquet`) pero no `corpus_miax_2026.zip`, así que
faltan `secciones.jsonl`, `chunks.jsonl` y `xbrl_facts.parquet`.
`chunks_meta.parquet` sí trae el texto completo de cada fragmento y sus offsets
`inicio_car` / `fin_car`.

**Opciones.** (a) Bloquear todo hasta tener el ZIP. (b) Reconstruir las
secciones pegando los fragmentos por sus offsets. (c) Dejar `read_section` sin
implementar.

**Decisión.** (b), **marcándolo**. `Seccion.reconstruida` va a `True`,
`read_section` lo dice en su cabecera y `Corpus.avisos()` lo registra para que
aparezca en la traza y en los resultados.

**Consecuencia.** El sistema funciona hoy y `read_section` devuelve texto útil.
Pero el texto reconstruido **no es literal en las costuras**: de las 1.701
fronteras entre fragmentos, 672 solapan —y el solape se recorta bien— pero 1.029
pierden entre 2 y 4 caracteres, que es el separador que consumió el troceador.
Se inserta `"\n\n"` como conjetura informada. Un `ancla_texto` que cruce una
frontera no se podrá verificar contra la sección reconstruida; sí contra los
fragmentos, que es donde el validador la busca. **En cuanto llegue
`secciones.jsonl` esto deja de usarse solo.**

---

## ADR-005 · El índice FAISS se puede leer sin faiss

**Contexto.** `IndexFlatIP` sobre vectores normalizados es, en disco, una
cabecera corta seguida de los vectores en crudo. La búsqueda sobre 1.749 × 384
floats es un producto matriz-vector: microsegundos en numpy.

**Opciones.** (a) Depender de `faiss.read_index` siempre. (b) Leer el fichero
con numpy. (c) Las dos, faiss cuando esté.

**Decisión.** (b) como camino principal del `RecuperadorDenso`. La longitud de
la cabecera se deduce del tamaño del fichero en lugar de parsear el formato
entero, que cambia entre versiones de faiss y no aporta nada aquí.

**Consecuencia.** La suite y el `recall@k` corren en cualquier máquina, incluso
sin `faiss-cpu`, que es la mitad de los problemas de instalación de un grupo de
tres. El coste es que si el profesor cambiase a un índice IVF o HNSW, este
lector lo rechaza con un error explícito y habría que instalar faiss. Con 1.749
vectores, un índice aproximado no tendría sentido.

---

## ADR-006 · El fallback de modelo es una variable de estado

**Contexto.** En la sesión 1 se planteó encadenar un modelo gratuito con uno de
pago. El profesor escribió el pseudocódigo en la pizarra y él mismo señaló que
estaba mal: reintentaba el gratuito en cada llamada.

**Opciones.** (a) `try/except` por llamada. (b) Una variable de estado que
conmuta una vez.

**Decisión.** (b). Ante 401, 402 o 429 se conmuta al modelo de reserva y no se
vuelve a intentar el primario en ese proceso. `ProveedorLangChain.en_reserva` va
a la traza.

**Consecuencia.** Con veinte preguntas nos ahorramos veinte llamadas fallidas,
veinte latencias y una columna de coste que no cuadraría con la factura. Y como
la conmutación queda en la traza, una ejecución hecha a medias con dos modelos
distintos se puede identificar después en lugar de compararla con otra como si
nada hubiera pasado.

---

## ADR-007 · «Hueco» no es una familia del golden set

**Contexto.** El prompt maestro pide reportar «aciertos por familia
(extractiva / numérica / comparativa / hueco)». El validador oficial del
profesor —celda 32 del notebook de la sesión 1— solo admite tres familias:
`extractiva`, `numerica`, `comparativa`. Un golden set con `familia: "hueco"`
sería **rechazado por el validador que nos van a pasar**.

**Opciones.** (a) Añadir `hueco` como cuarta familia y romper el validador
oficial. (b) Tratar el hueco como una propiedad derivada.

**Decisión.** (b). `Familia` es un `Literal` de tres valores. Una pregunta de
hueco es `numerica` o `comparativa` con `cifra_esperada = null` y un
`concept_xbrl` declarado, y se detecta con `Pregunta.es_hueco`. En el informe
sigue siendo una **columna**, que es lo que pedía el prompt maestro.

**Consecuencia.** Nuestro golden set pasa el validador oficial y el informe
mantiene la columna de hueco. Es la contradicción entre el enunciado y el prompt
maestro que se pedía documentar: **manda el enunciado**.

---

## ADR-008 · La tolerancia vive en un solo módulo

**Contexto.** El guardarraíl XBRL (fase 4) y el evaluador de cifra (fase 5)
comparan la misma cosa con la misma regla, y los escriben personas distintas en
ramas distintas.

**Opciones.** (a) Un número en cada sitio. (b) Un objeto `Tolerancia`
compartido.

**Decisión.** (b). `dominio/tolerancia.py`, 0,5 % relativo o 1 USD absoluto, lo
que sea mayor, con el porqué escrito al lado: acepta el redondeo de la prosa
(«$60.9 billion» frente a 60.922.000.000 es un 0,036 %) y rechaza haber cogido
otro ejercicio u otra compañía.

**Consecuencia.** Imposible que el guardarraíl acepte cifras que el evaluador
suspende. Si alguien quiere endurecerla, la cambia en un sitio y las dos se
mueven juntas. Un test comprueba que las dos importan la misma instancia.

---

## ADR-009 · El recuperador denso se implementa; el resto es la fase 3

**Contexto.** El prompt maestro dice «no implementes todavía los recuperadores
concretos». Pero `search_filings` tiene que funcionar desde el REPL hoy
(criterio de aceptación) y el baseline no arranca sin búsqueda.

**Opciones.** (a) Dejar todo `retrieval/` en stub y no cumplir el criterio de
aceptación. (b) Implementar denso, que es el que **se entrega ya hecho** en el
material del profesor, y dejar en stub las cuatro mejoras.

**Decisión.** (b). `denso.py` está completo; `lexico`, `hibrido`,
`filtro_metadatos` y `reescritura` son stubs con tests `xfail(strict=True)`.

**Consecuencia.** El denso es el baseline honesto contra el que se mide la
ablación —incluido que **filtra después de buscar**, igual que la
implementación del profesor, para que «filtrar antes» sea una mejora medible y
no algo que ya estuviera hecho—. Alonso llega a la fase 3 con la interfaz
estable y una fila base ya ejecutable.

---

## ADR-010 · Los tests de los stubs son `xfail(strict=True)`

**Contexto.** El prompt maestro pide «tests que fallan describiendo el
comportamiento esperado», y a la vez que `make test` pase.

**Opciones.** (a) `skip`, que los esconde. (b) Fallos de verdad, que dejan la
suite roja y acaban ignorándose. (c) `xfail(strict=True)`.

**Decisión.** (c). La suite queda verde, la especificación sigue visible y, en
cuanto alguien implementa la pieza, el test pasa a `XPASS` y **falla**,
obligando a quitar la marca.

**Consecuencia.** Un recordatorio que no se puede ignorar por acumulación, a
diferencia de un `skip`. El mismo mecanismo protege al golden set: el test que
exige las 20 preguntas está en `xfail` hasta la fase 2.

---

## ADR-011 · `make` delega en `scripts/tareas.py`

**Contexto.** En Windows no hay `make`, y una de las tres máquinas del grupo lo
es. El prompt maestro pide un `Makefile`.

**Opciones.** (a) Solo Makefile. (b) Makefile y script en paralelo. (c) Makefile
como envoltorio fino de un script en Python.

**Decisión.** (c). Toda la lógica está en `scripts/tareas.py`; el `Makefile` son
trece líneas que delegan.

**Consecuencia.** `make lint` y `python scripts/tareas.py lint` hacen
exactamente lo mismo por construcción, y un test comprueba que ningún objetivo
existe en uno y no en el otro.

---

## ADR-012 · Sin XBRL sintético

**Contexto.** Falta `xbrl_facts.parquet`, que es el ground truth de la familia
numérica, del guardarraíl y del evaluador de cifra. Se consideró extraer las
cifras de las tablas del texto para tener algo con lo que trabajar.

**Opciones.** (a) Generar un parquet a partir del texto, marcado como
provisional. (b) Dejar el repositorio XBRL vacío y que las tools lo digan.

**Decisión.** (b). `RepositorioXbrlMemoria.disponible()` distingue «no hay
fichero» de «ese emisor no reporta ese concepto», y `get_xbrl_fact` da un
mensaje distinto en cada caso.

**Consecuencia.** Nada de lo que produzca el sistema puede confundirse con
ground truth. Un XBRL extraído del texto sería exactamente el error que el
evaluador de cifra existe para detectar —leer la cifra de la prosa de una tabla
partida—, y contaminaría el golden set con cifras que nadie verificó. La
contrapartida es que la familia numérica no se puede probar contra datos reales
hasta que llegue el ZIP; contra fixtures sí, y las fixtures codifican las dos
trampas.

---

## Pendiente de decidir

- **Troceado propio.** El corpus viene troceado a ~500 tokens con 80 de solape.
  Re-trocearlo es legítimo y puede subir el recall, pero invalida el índice
  entregado y obliga a reembeber. Decidir en la fase 3, con números.
- **`max_tokens_seccion` por defecto.** Hoy es `None` —sección entera, como el
  baseline—. Ponerle un tope baja el coste medio por pregunta, que es columna
  de la tabla, pero cambia el comportamiento respecto al baseline. Medir las dos
  antes de elegir.
- **Modelo para las preguntas ciegas.** `gemini-3.8-flash` es el del profesor y
  el más barato. Comparar contra uno mejor en la fase 6 y decidir con la tabla
  delante, no por intuición.
