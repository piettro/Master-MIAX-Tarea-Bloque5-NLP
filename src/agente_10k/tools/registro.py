"""Envuelve las cuatro funciones del CONTRATO C1 en herramientas de LangChain.

El registro está aparte de `contratos.py` por una razón práctica: importar
`contratos` no debe arrastrar LangChain. Así los tests de las tools, del formato
y del corpus corren en segundos sin instalar el framework, y solo `agente/`
paga esa dependencia.

El decorador `@tool` lee el nombre de la función, los tipos de sus parámetros y
su docstring, y manda ese esquema al modelo en cada petición. El docstring que
viaja es el de `contratos.py`, literal: aquí no se reescribe nada.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agente_10k.tools.contratos import (
    get_xbrl_fact,
    list_available,
    read_section,
    search_filings,
)

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

NOMBRES_CONTRATO = ("list_available", "get_xbrl_fact", "search_filings", "read_section")
"""Los nombres que busca el evaluador de trayectoria. No se renombran (C1)."""


def construir_tools() -> Sequence[Any]:
    """Las cuatro herramientas listas para `create_agent`.

    Returns:
        Los objetos `BaseTool` de LangChain, en orden de coste creciente.

    Raises:
        ImportError: Si LangChain no está instalado. Se deja subir a propósito:
            quien llama a esto está montando el agente, y montar el agente sin
            framework no es un caso degradado sino un error de instalación.
    """
    from langchain.tools import tool

    return [
        tool(list_available),
        tool(get_xbrl_fact),
        tool(search_filings),
        tool(read_section),
    ]


def nombres_disponibles() -> tuple[str, ...]:
    """Los nombres de las herramientas registradas."""
    return NOMBRES_CONTRATO
