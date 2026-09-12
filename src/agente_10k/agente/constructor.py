"""Ensambla el agente con LangChain. FASE 4 — Piettro.

STUB. Las firmas y el contrato están fijados; el cuerpo es de la fase 4.

Piezas, con la API verificada el 2 de septiembre de 2026 y fijada por versión en
`pyproject.toml`:

    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver

    agente = create_agent(
        model=..., tools=..., system_prompt=...,
        response_format=RespuestaFinanciera,
        checkpointer=InMemorySaver(),
    )

Si el modelo elegido no soporta salida estructurada nativa, la salida es
envolver el esquema:

    from langchain.agents.structured_output import ToolStrategy
    response_format=ToolStrategy(schema=RespuestaFinanciera)

Antes de tocar nada de esto, consultar la documentación ACTUALIZADA: la API que
un modelo de lenguaje recuerda de LangChain suele estar un año desfasada, y los
notebooks de la edición anterior de este curso ya no ejecutan por eso mismo.
"""

from __future__ import annotations

from agente_10k.config import Settings
from agente_10k.dominio.modelos import RespuestaFinanciera, Traza


class AgenteInvestigador:
    """El agente montado: herramientas, prompt, middleware y salida estructurada."""

    def __init__(self, config: Settings | None = None) -> None:
        """Monta el agente desde la configuración.

        Raises:
            NotImplementedError: Fase 4.
        """
        raise NotImplementedError("Fase 4 · Piettro: constructor del agente")

    def responder(self, pregunta: str) -> tuple[RespuestaFinanciera, Traza]:
        """Responde una pregunta y devuelve la respuesta con su traza.

        Nunca lanza por culpa del modelo: si la salida estructurada no valida
        después del reintento, devuelve una `RespuestaFinanciera` con
        `fuente="ninguna"` y el motivo. Una excepción aquí abortaría la
        evaluación del golden set entero.

        Raises:
            NotImplementedError: Fase 4.
        """
        raise NotImplementedError("Fase 4 · Piettro: bucle del agente")


def construir_agente(config: Settings | None = None) -> AgenteInvestigador:
    """El agente listo para invocar.

    Raises:
        NotImplementedError: Fase 4.
    """
    raise NotImplementedError("Fase 4 · Piettro: constructor del agente")
