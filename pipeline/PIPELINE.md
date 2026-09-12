# PIPELINE DE TRABAJO — Agente investigador sobre 10-K

**Grupo:** Piettro · Alonso · Raúl
**Asignatura:** LLMs aplicados a Finanzas (MIAX, Instituto BME) — profesor: Guillermo Fajardo
**Entrega:** miércoles **23 de septiembre, 23:59** (aula virtual: repo de GitHub + informe PDF)
**Defensa:** jueves **24 de septiembre** — 10 preguntas ciegas ejecutadas en clase + 8 minutos de presentación
**Peso:** 30% GitHub · 70% presentación

---

## 0. Lo que realmente se evalúa

Conviene tenerlo delante todo el tiempo, porque cambia las prioridades:

1. **El enrutado, no el retrieval.** El retrieval es una herramienta más. El sistema se juzga por
   si el agente elige bien entre la consulta exacta gratuita (XBRL), la búsqueda difusa y la
   lectura cara de 40 páginas.
2. **Acertar por el camino equivocado es fallo.** Hay un evaluador escrito para detectarlo. Un
   número correcto leído de la prosa de una tabla partida cuenta como error.
3. **Coste y latencia son columnas de la tabla, no una nota al pie.**
4. **Lo que no funcionó también es resultado.** La pregunta que el profesor hará a todos los
   grupos es si las mejoras mejoraron algo de verdad y qué costaron.
5. **Decir "no está en el corpus" es acertar**, cuando efectivamente no está.

El 70% es la presentación. Todo el trabajo de ingeniería existe para que esos 8 minutos tengan
números defendibles detrás.

---

## 1. Reparto de responsabilidades

| | **Piettro** | **Alonso** | **Raúl** |
|---|---|---|---|
| **Eje** | Arquitectura, tools y agente | Retrieval y su medición | Evaluación, golden set e informe |
| **Entrega principal** | Scaffold, 4 tools, middleware, guardarraíl XBRL, `responder()` | Filtro de metadatos, BM25, híbrido RRF, reescritura, tabla de ablación | 3 evaluadores, métricas, `evaluar()`, tablas del informe, PDF |
| **Rama** | `fase-1-tools`, `fase-4-agente` | `fase-3-retrieval` | `fase-2-golden`, `fase-5-evaluacion` |
| **Dueño del día 24** | Ejecuta las preguntas ciegas | Diapositiva de ablación | Diapositiva baseline vs final |

Los tres escriben preguntas del golden set (7 / 7 / 6) y los tres revisan el PR de los otros dos.
Nadie mergea su propia rama sin una aprobación.

---

## 2. Calendario

```
sáb 12 ├─ F0  Scaffold del repo (prompt maestro)                    Piettro
dom 13 ├─ F0  Corpus verificado + baseline del profesor ejecutado   Piettro
       │      HITO 0 · el repo clona y arranca en las 3 máquinas
lun 14 ├─ F1  Tools: list_available, get_xbrl_fact                  Piettro
       ├─ F2  Cada uno escribe sus preguntas (primer borrador)      los tres
mar 15 ├─ F1  Tools: search_filings, read_section + baseline congelado
       │      HITO 1 · baseline etiquetado en resultados/baseline/  ← irreversible
mié 16 ├─ F2  Consolidación del golden set + validador en verde     Raúl
       │      HITO 2 · 20 preguntas, ≥6 comparativas, validador OK
jue 17 ├─ ▶ SESIÓN 2 (2,5 h) — retrieval por dentro, guardrails, evaluadores
       │      Llegamos con baseline corriendo y las 20 preguntas escritas.
       │      Sin las dos cosas la sesión no rinde: empieza ejecutando NUESTRO
       │      baseline y clasificando SUS fallos.
vie 18 ├─ F3  Filtro de metadatos + BM25                            Alonso
       ├─ F4  Proveedor, system prompt, salida estructurada         Piettro
       ├─ F5  Evaluador de cita + evaluador de cifra                Raúl
sáb 19 ├─ F3  Híbrido RRF + reescritura de consulta                 Alonso
       ├─ F4  Middleware: limitador + guardarraíl XBRL              Piettro
       ├─ F5  Evaluador de trayectoria + métricas                   Raúl
dom 20 ├─ F3/F4  Merge a main + tabla de ablación                   Alonso/Piettro
       │      HITO 3 · sistema final integrado, evaluar() corre entero
lun 21 ├─ F5  Tablas del informe + primera lectura de resultados    Raúl
       ├─ Ejecución final sobre el golden set → resultados/final/
       │      HITO 4 · tabla baseline vs final cerrada
mar 22 ├─ Informe PDF + ensayo en clon limpio (x2)                  los tres
       ├─ Ensayo cronometrado de la presentación                    los tres
mié 23 ├─ Congelar repo, tag v1.0, subir PDF al aula virtual
       │      HITO 5 · ENTREGA — antes de las 20:00, no a las 23:58
jue 24 ├─ ▶ SESIÓN 3 — 10 preguntas ciegas + defensa de 8 minutos
```

**Ritual diario:** 20 minutos, por la noche. Tres preguntas cada uno: qué cerré, qué me bloquea,
qué necesito de vosotros. Si algo lleva bloqueado más de un día, se reasigna.

---

## 3. Hitos y su Definition of Done

### HITO 0 — Repo operativo (dom 13)
- [ ] `git clone` + `pip install -e .` + `make test` funciona en las máquinas de los tres.
- [ ] `data/` con el corpus descomprimido y checksums verificados; `class_transcription/` y
      `docs/enunciado.md` dentro del repo.
- [ ] `.env.example` versionado, `.env` ignorado, hook de secretos activo.
- [ ] Los tres tienen su API key (OpenRouter recomendado: cuenta gratuita, ~10 € de saldo sobran
      de largo; el coste real de la práctica es de céntimos).

### HITO 1 — Baseline congelado (mar 15) · **irreversible**
- [ ] Las cuatro tools funcionan contra el corpus real desde el REPL.
- [ ] La implementación del profesor ejecutada tal cual y su salida guardada en
      `resultados/baseline/` con fecha, modelo y hash de commit.
- [ ] Test que falla si ese directorio cambia.
> Si empezamos a mejorar antes de congelar esto, perdemos media tabla del informe y no hay forma
> de recuperarla. Es el error más caro posible del proyecto.

### HITO 2 — Golden set validado (mié 16)
- [ ] 20 preguntas, ≥6 comparativas, ≥2 de hueco real, ≥1 trampa de `fiscal_year`,
      ≥1 trampa de concepto XBRL.
- [ ] Todas las `ancla_texto` verificadas literalmente contra `secciones.jsonl`.
- [ ] Todas las `cifra_esperada` verificadas contra `xbrl_facts.parquet` (nunca contra el texto).
- [ ] `validador.py` en verde en CI.

### HITO 3 — Sistema final integrado (dom 20)
- [ ] `responder()` devuelve `RespuestaFinanciera` válida en las 20 preguntas.
- [ ] Limitador de tool calls y guardarraíl XBRL activos, con su intervención registrada en la traza.
- [ ] Tabla de ablación del retrieval generada por código.
- [ ] Todo ejecutable cambiando configuración, sin editar código.

### HITO 4 — Resultados cerrados (lun 21)
- [ ] `resultados/final/` generado y tabla baseline vs final con el mejor valor remarcado.
- [ ] Recall@k, coste medio, latencia media y tool calls por pregunta en la tabla.
- [ ] Sección "qué probamos que no funcionó" escrita, con números.

### HITO 5 — Entrega (mié 23)
- [ ] Ensayo en clon limpio hecho dos veces, la segunda por quien no escribió el código.
- [ ] Ninguna clave de API en el repo ni en su historial.
- [ ] PDF subido al aula virtual + repo con tag `v1.0`.
- [ ] Presentación ensayada y cronometrada en 8 minutos.

---

## 4. Riesgos y mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| `evaluar()` no traga las 10 preguntas ciegas por campos ausentes | **Alta** | Crítico | Probar con un JSONL de solo `id`+`pregunta` antes del 22. Degradar evaluadores, nunca abortar |
| Empezar a mejorar sin haber congelado el baseline | Media | Crítico | Hito 1 irreversible y test que lo protege |
| Breaking changes de LangChain / documentación desfasada en el LLM | **Alta** | Medio | Versiones fijadas en `pyproject.toml`; consultar documentación actualizada (Context7) antes de usar su API |
| Anclas de texto mal transcritas → preguntas inválidas | Alta | Medio | Validador que comprueba literalidad; correr en CI |
| Quota agotada el día 24 en mitad de la ejecución | Media | Alto | Fallback de proveedor implementado y **probado**; saldo cargado el día 22 |
| Sobreajuste al golden set propio → caída en las ciegas | Media | Medio | Aceptarlo y prepararlo: diapositiva de delta con hipótesis escrita de antemano |
| Merge conflicts en `golden_set.jsonl` | Alta | Bajo | Ficheros parciales por autor, fusión por script |
| Llegar al 22 sin informe | Media | Alto | Raúl escribe el informe en paralelo desde el 18, con las tablas vacías ya maquetadas |

---

## 5. Presupuesto de tokens y coste

Referencia dada en clase: el corpus entero son ~650.000 tokens. Con un modelo barato tipo
Gemini Flash (~0,75 $/M tokens de entrada), leerlo entero cuesta menos de 0,75 $. Una pregunta
bien enrutada cuesta céntimos; una sesión completa de 20 preguntas, entre 0,10 y 0,30 $.

Con caché de embeddings y de llamadas, reejecutar el golden set no debería costar nada. Aun así:
**medir el coste no es curiosidad, es una columna de la tabla.** Lee el metadato de uso que
devuelve el proveedor en cada mensaje; no lo estimes multiplicando tokens a mano.

Presupuesto del grupo: 10 € cargados en OpenRouter cubren la práctica entera con holgura.

---

## 6. Convenciones de trabajo

- **Ramas:** `fase-N-<tema>`. Nunca commits directos a `main` salvo en F6.
- **PRs:** pequeños, con una aprobación obligatoria de otro miembro. Descripción con qué cambia
  y qué métrica mueve.
- **Commits:** `feat:`, `fix:`, `test:`, `docs:`, `refactor:` en inglés imperativo.
- **Decisiones:** toda decisión no obvia va a `docs/decisiones.md` (contexto, opciones, decisión,
  consecuencia). Ese fichero es la materia prima de la sección de arquitectura del informe.
- **Números:** ninguna cifra se escribe a mano en el PDF. Si no sale de `make informe`, no entra.
- **Definición de "terminado":** el código pasa `lint`, `mypy --strict` y `test`; la métrica está
  regenerada; el ADR está escrito; alguien más lo ha revisado.

---

## 7. Checklist final de entrega (imprimir el 23)

**GitHub**
- [ ] Código del agente, las 4 herramientas y los 3 evaluadores
- [ ] Golden set en JSONL: 20 preguntas, ≥6 comparativas, pasa el validador
- [ ] `responder()` y `evaluar()` ejecutables en clon limpio sin editar nada
- [ ] Tabla baseline vs final con aciertos por familia, recall@k, coste medio, latencia media y
      tool calls por pregunta, con el mejor valor remarcado
- [ ] Ficheros de resultados de baseline y final, regenerables ejecutando el repo
- [ ] Ninguna clave de API en el repositorio ni en su historial
- [ ] El código genera **todas** las tablas reportadas

**Informe PDF**
- [ ] Arquitectura y criterio de enrutado
- [ ] Tabla baseline vs final y su lectura: qué mejoró, cuánto, a qué coste
- [ ] Ablación del retrieval con recall@k tras cada arreglo
- [ ] Guardarraíles: qué protege de afirmar una cifra no verificada y cuántas veces actuó
- [ ] Qué se probó que no funcionó
- [ ] Limitaciones

**Presentación (8 min)**
- [ ] Guion cronometrado y ensayado
- [ ] Diapositiva de preguntas ciegas preparada **en blanco**, lista para rellenar en clase
- [ ] Respuesta preparada a: *"¿vuestras mejoras mejoraron algo de verdad y qué costaron?"*
