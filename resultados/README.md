# resultados/

Aquí vive la mitad del informe. Nada de esto se escribe a mano: todo lo genera
el repositorio y se puede regenerar ejecutándolo.

```
resultados/
├── baseline/   la implementación del profesor, CONGELADA. No se toca.
├── final/      nuestro sistema. Se regenera con `make final`.
├── retrieval/  la tabla de ablación. Se regenera con `make ablacion`.
└── ciegas/     las 10 preguntas del día 24. Vacío hasta ese día.
```

## El protocolo del baseline

**El baseline se ejecuta y se congela ANTES de tocar nada.** Es el error más
caro posible del proyecto y no tiene arreglo: si empezamos a mejorar sin haberlo
guardado, para recuperarlo habría que volver al commit de aquel día y reejecutar
con el mismo modelo, que para entonces ya habrá cambiado de versión. Media tabla
del informe, perdida.

El orden es este y no otro:

1. Las cuatro herramientas funcionan contra el corpus real desde el REPL.
2. `make baseline` ejecuta la implementación del profesor —`src/agente_10k/
   baseline/`, sin modificar— sobre el golden set.
3. La salida se guarda en `resultados/baseline/` **etiquetada**: fecha, modelo
   exacto, hash del commit y configuración.
4. `python scripts/comprobar_baseline.py` escribe `SELLO.json` con el SHA-256 de
   cada fichero.
5. A partir de ahí el directorio es de solo lectura. El gancho de pre-commit y
   `tests/test_contratos_publicos.py::TestBaselineCongelado` fallan si cambia.

Si de verdad hay que regenerarlo —por ejemplo, porque el primer intento corrió
con el corpus incompleto— se borra `SELLO.json` a mano y **se deja constancia en
`docs/decisiones.md`** de por qué. Que cueste un gesto deliberado es el punto.

## Qué lleva cada ejecución

Todo fichero de resultados incluye, en su cabecera o en un `meta.json` al lado:

| Campo | Por qué |
| --- | --- |
| `fecha` | Para ordenar ejecuciones |
| `modelo` y `proveedor` | Dos ejecuciones con modelos distintos no son comparables |
| `en_reserva` | Si el fallback conmutó a mitad, la ejecución es mixta |
| `commit` | Para reproducirla |
| `configuracion` | Recuperador, filtros, límites, versión del prompt |
| `avisos_corpus` | Si el corpus estaba incompleto o las secciones reconstruidas |

Sin esto, dentro de una semana nadie sabrá si la tabla compara dos sistemas o
dos modelos.

## El día 24

Las diez preguntas ciegas se guardan en `resultados/ciegas/preguntas.jsonl` con
el mismo esquema. Si llegan en prosa, solo `id` y `pregunta` son obligatorios:
`evaluar()` tolera campos ausentes y degrada los evaluadores que no pueda
aplicar. **Eso está probado** —`tests/evaluacion/test_evaluacion.py::
TestLecturaTolerante`— porque es el fallo más probable de toda la práctica.

Después se calcula el delta contra el golden set propio. Si baja, esa es la
diapositiva más valiosa de la presentación: hay que explicar qué parte de la
mejora era general y qué parte era memoria del conjunto con el que iteramos.
Es un hallazgo sobre sobreajuste al set de desarrollo, no un suspenso, y conviene
llevar la hipótesis escrita de antemano.
