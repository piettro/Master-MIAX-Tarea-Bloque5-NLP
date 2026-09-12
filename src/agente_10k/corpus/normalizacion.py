"""Cómo se compara un texto con otro. Documentado porque es una decisión.

El evaluador de cita y el `recall@k` contra el ancla preguntan lo mismo: ¿este
texto aparece literalmente en aquel? «Literalmente» necesita una definición,
porque los 10-K vienen de HTML y traen comillas tipográficas, guiones largos,
espacios sin ruptura y saltos de línea metidos por el troceador en mitad de una
frase.

La normalización que se aplica a los DOS lados de cada comparación:

1. Unicode a NFKC, que unifica las variantes de compatibilidad.
2. Comillas tipográficas a rectas, guiones largos a guión simple.
3. Espacios sin ruptura y tabuladores a espacio normal.
4. Cualquier racha de espacios en blanco, saltos de línea incluidos, a un
   único espacio.
5. Recorte de los extremos.

Lo que NO se hace, y es deliberado: no se baja a minúsculas ni se quitan signos
de puntuación. «Revenue» y «revenue» son cosas distintas en una tabla
financiera, y un evaluador que las confunda deja pasar citas que no respaldan
lo que afirman.
"""

from __future__ import annotations

import re
import unicodedata

_COMILLAS = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "–": "-",
        "—": "-",
        "−": "-",
        " ": " ",
        " ": " ",
        " ": " ",
        "\t": " ",
    }
)

_ESPACIOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """El texto listo para comparar. Se aplica a los dos lados, siempre."""
    if not texto:
        return ""
    limpio = unicodedata.normalize("NFKC", texto).translate(_COMILLAS)
    return _ESPACIOS.sub(" ", limpio).strip()


def contiene(contenedor: str, aguja: str) -> bool:
    """Si `aguja` aparece en `contenedor` tras normalizar ambos."""
    aguja_n = normalizar(aguja)
    return bool(aguja_n) and aguja_n in normalizar(contenedor)


def describir() -> str:
    """La normalización en una línea, para el informe.

    El enunciado pide documentar la normalización del evaluador de cita. Que
    salga de aquí y no de un párrafo escrito a mano garantiza que lo que dice
    el PDF es lo que hace el código.
    """
    return (
        "NFKC; comillas tipográficas y guiones largos a ASCII; espacios sin "
        "ruptura, tabuladores y saltos de línea colapsados a un espacio; "
        "recorte de extremos. Se conservan mayúsculas y puntuación."
    )
