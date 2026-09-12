"""El cinturón de herramientas del agente. CONTRATO C1 y CONTRATO C2."""

from __future__ import annotations

from agente_10k.tools.contratos import (
    HERRAMIENTAS,
    get_xbrl_fact,
    list_available,
    read_section,
    search_filings,
    usar_cinturon,
)
from agente_10k.tools.implementacion import Herramientas, herramientas_por_defecto

__all__ = [
    "HERRAMIENTAS",
    "Herramientas",
    "get_xbrl_fact",
    "herramientas_por_defecto",
    "list_available",
    "read_section",
    "search_filings",
    "usar_cinturon",
]
