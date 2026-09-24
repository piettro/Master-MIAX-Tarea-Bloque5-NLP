# golden/

El golden set propio: **20 preguntas**, de las cuales **≥6 comparativas**,
**≥2 de hueco real**, **≥1 trampa de `fiscal_year`** y **≥1 trampa de concepto
XBRL**. CONTRATO C4.

## Escribir en paralelo

Un JSONL es un fichero donde git no sabe resolver conflictos. Si se escriben
preguntas en varias tandas a la vez, cada una va en su fichero y se fusionan con
un script, no con un merge:

```python
from pathlib import Path
from golden.validador import fusionar_parciales

fusionar_parciales(Path("tandas/"), Path("golden/golden_set.jsonl"))
```

La fusión rechaza un `id` repetido entre ficheros.

## Antes de dar una pregunta por buena

```bash
python -m agente_10k.cli validar-golden golden/golden_set.jsonl
```

Lo que más preguntas invalida, y lo que más tiempo ahorra descubrir aquí y no el
día 23: **el `ancla_texto` tiene que aparecer LITERALMENTE en el corpus**.
Cópiala del texto; no la escribas de memoria. Si no aparece, la pregunta no es
«casi válida»: es inválida, porque el evaluador de cita nunca podrá darla por
buena.

Y **`cifra_esperada` se verifica contra `xbrl_facts.parquet`, nunca contra el
texto.** El texto da cifras redondeadas junto a las exactas, que es justo el
error que el evaluador existe para detectar.

## Las trampas, como preguntas

| Trampa | Cómo se convierte en pregunta |
| --- | --- |
| `fiscal_year` ≠ año de presentación | NVDA FY2025 cerró en enero de 2025; GOOGL FY2025 se presentó en 2026 |
| El concepto XBRL no es universal | Revenue de NVDA (`Revenues`) frente al de MSFT (`RevenueFromContract…`) |
| Huecos reales | Margen bruto de Amazon, de Meta o de Alphabet: la respuesta es que no está |

`golden_set_ejemplo.jsonl` es el fichero de tres preguntas que reparte el
profesor. Sirve para ver el esquema; no cuenta para las 20.
