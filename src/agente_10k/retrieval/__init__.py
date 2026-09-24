"""Retrieval. P1 (Strategy) para los recuperadores, P2 (Decorator) para las mejoras.

`denso.py` es el recuperador que se entrega y el punto de partida contra el
que se mide. Encima van el léxico, el híbrido y los decoradores: filtro previo,
reescritura de la consulta y reordenación con cross-encoder.
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
