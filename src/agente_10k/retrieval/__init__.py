"""Retrieval. P1 (Strategy) para los recuperadores, P2 (Decorator) para las mejoras.

`denso.py` está implementado: es el recuperador que se entrega y el baseline
contra el que se mide. El resto —léxico, híbrido, filtro previo y reescritura—
son los stubs de la fase 3, con sus firmas fijadas y sus tests en rojo.
"""

from __future__ import annotations

from agente_10k.retrieval.codificador import (
    MODELO_EMBEDDINGS,
    PREFIJO_CONSULTA_BGE,
    CodificadorBge,
)
from agente_10k.retrieval.denso import RecuperadorDenso
from agente_10k.retrieval.fabrica import (
    CONFIGURACIONES_ABLACION,
    construir_recuperador,
)

__all__ = [
    "CONFIGURACIONES_ABLACION",
    "MODELO_EMBEDDINGS",
    "PREFIJO_CONSULTA_BGE",
    "CodificadorBge",
    "RecuperadorDenso",
    "construir_recuperador",
]
