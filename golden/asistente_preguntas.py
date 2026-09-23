"""Ayuda para escribir preguntas del golden set sin transcribir nada a mano.

Las dos causas que más preguntas invalidan son un `ancla_texto` escrito de
memoria y una `cifra_esperada` leída del texto en lugar de XBRL. Este script
saca las dos cosas del corpus, de modo que lo que se pega en el JSONL es
literal por construcción.

    python golden/asistente_preguntas.py xbrl AMZN 2025
    python golden/asistente_preguntas.py buscar MSFT 2025 7 "net income"
    python golden/asistente_preguntas.py ancla MSFT 2025 7 "Net income increased ..."

`ancla` imprime los cuatro campos listos para el JSONL: `item_esperado`,
`ancla_texto`, `ancla_inicio` y `ancla_fin`. Los offsets son la posición de la
frase en el texto de `secciones.jsonl`, igual que en el golden set oficial.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_CORPUS = RAIZ / "data" / "corpus"

_FRASE = re.compile(r"[^.\n]*?(?:\.(?=\s)|\n|$)")


def _seccion(ticker: str, fiscal_year: int, item: str) -> str:
    """El texto literal de una sección de `secciones.jsonl`."""
    with (DIR_CORPUS / "secciones.jsonl").open(encoding="utf-8") as f:
        for linea in f:
            s = json.loads(linea)
            clave = (s["ticker"], s["fiscal_year"], s["item"])
            if clave == (ticker, fiscal_year, item):
                return str(s["texto"])
    raise SystemExit(f"No hay sección {item} de {ticker} FY{fiscal_year}.")


def xbrl(ticker: str, fiscal_year: int) -> None:
    """Los hechos XBRL de un emisor y ejercicio, en unidades base."""
    import pandas as pd

    hechos = pd.read_parquet(DIR_CORPUS / "xbrl_facts.parquet")
    filas = hechos[(hechos.ticker == ticker) & (hechos.fiscal_year == fiscal_year)]
    if filas.empty:
        raise SystemExit(f"{ticker} FY{fiscal_year} no tiene hechos XBRL.")
    for _, f in filas.sort_values("concept").iterrows():
        print(
            f"{f['concept']:<55} {f['value']:>22,.2f} {f['unit']:<10} {f['period_end']}"
        )


def buscar(ticker: str, fiscal_year: int, item: str, termino: str) -> None:
    """Las frases de una sección que contienen `termino`, con su posición."""
    texto = _seccion(ticker, fiscal_year, item)
    patron = termino.lower()
    for m in _FRASE.finditer(texto):
        frase = m.group().strip()
        if patron in frase.lower() and len(frase) > len(termino):
            print(f"[{m.start()}] {frase}\n")


def ancla(ticker: str, fiscal_year: int, item: str, frase: str) -> None:
    """Los cuatro campos del ancla, o por qué la frase no sirve."""
    texto = _seccion(ticker, fiscal_year, item)
    inicio = texto.find(frase)
    if inicio < 0:
        raise SystemExit(
            "La frase NO aparece literalmente en la sección. Cópiala de la "
            "salida de `buscar`, sin retocarla."
        )
    if texto.find(frase, inicio + 1) >= 0:
        print("AVISO: la frase aparece más de una vez; se usa la primera.")
    campos = {
        "item_esperado": item,
        "ancla_texto": frase,
        "ancla_inicio": inicio,
        "ancla_fin": inicio + len(frase),
    }
    print(json.dumps(campos, ensure_ascii=False, indent=2))


def main(argumentos: list[str]) -> None:
    """Despacha la orden de la línea de comandos."""
    if not argumentos:
        raise SystemExit(__doc__)
    orden, *resto = argumentos
    if orden == "xbrl" and len(resto) == 2:  # noqa: PLR2004
        xbrl(resto[0], int(resto[1]))
    elif orden == "buscar" and len(resto) == 4:  # noqa: PLR2004
        buscar(resto[0], int(resto[1]), resto[2], resto[3])
    elif orden == "ancla" and len(resto) == 4:  # noqa: PLR2004
        ancla(resto[0], int(resto[1]), resto[2], resto[3])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
