"""Agente investigador sobre informes 10-K de la SEC.

CONTRATO C5: este módulo expone `responder()` y `evaluar()`, ejecutables sobre
un clon limpio del repositorio sin editar nada. El día 24 se ejecutan diez
preguntas ciegas contra ellas, en clase, en veinte minutos. Si alguna necesita
que alguien toque una ruta, un notebook o una variable, el sistema está roto.

    git clone <repo> && cd <repo>
    pip install -e .
    export OPENROUTER_API_KEY=...
    python -c "from agente_10k import responder; print(responder('...'))"

Los imports pesados —LangChain, faiss, sentence-transformers— son perezosos: se
hacen dentro de las funciones y no aquí. Importar `agente_10k` tiene que ser
instantáneo y no debe fallar porque falte una dependencia opcional.
"""

from __future__ import annotations

from pathlib import Path

from agente_10k.dominio.modelos import (
    InformeEvaluacion,
    Pregunta,
    RespuestaFinanciera,
    Traza,
)

__version__ = "0.1.0"

__all__ = [
    "InformeEvaluacion",
    "Pregunta",
    "RespuestaFinanciera",
    "Traza",
    "evaluar",
    "responder",
]


def responder(pregunta: str) -> RespuestaFinanciera:
    """Responde una pregunta sobre los 10-K del corpus. CONTRATO C5.

    Construye el agente desde `Settings` —proveedor, modelo, recuperador,
    límites— sin ningún argumento obligatorio más que la pregunta.

    Args:
        pregunta: La pregunta, en español o en inglés.

    Returns:
        Una `RespuestaFinanciera` validada. Si el sistema no consigue
        responder, devuelve una con `fuente="ninguna"` y el motivo en
        `motivo_sin_dato`: nunca una excepción, porque una excepción aquí
        abortaría la ejecución de las diez preguntas ciegas.
    """
    from agente_10k.agente.constructor import construir_agente

    respuesta, _ = construir_agente().responder(pregunta)
    return respuesta


def responder_con_traza(pregunta: str) -> tuple[RespuestaFinanciera, Traza]:
    """Como `responder()`, pero devolviendo también la traza.

    Es lo que usa el ejecutor de la evaluación: el evaluador de trayectoria
    necesita el camino, no solo la respuesta.
    """
    from agente_10k.agente.constructor import construir_agente

    return construir_agente().responder(pregunta)


def evaluar(ruta_jsonl: str | Path) -> InformeEvaluacion:
    """Evalúa el sistema sobre un JSONL de preguntas. CONTRATO C5.

    Ejecuta `responder()` sobre cada pregunta, aplica los tres evaluadores,
    agrega las métricas y escribe el detalle y el resumen a `resultados/`.

    Tolera campos ausentes: si las preguntas llegan con solo `id` y `pregunta`,
    los evaluadores que no puedan aplicarse devuelven `no_aplica` en lugar de
    abortar. Una pregunta que lance excepción se marca como fallo y la
    ejecución continúa con las demás.

    Args:
        ruta_jsonl: El fichero de preguntas, en el esquema del CONTRATO C4.

    Returns:
        El informe con el detalle por pregunta y las métricas agregadas.
    """
    from agente_10k.evaluacion.ejecutor import evaluar as _evaluar

    return _evaluar(ruta_jsonl)
