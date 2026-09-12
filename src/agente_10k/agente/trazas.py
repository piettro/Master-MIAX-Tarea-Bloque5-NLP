"""Captura de la trayectoria, los tokens, el coste y la latencia. FASE 4.

STUB salvo los ayudantes puros, que sí están implementados porque los necesitan
los tests del evaluador de trayectoria antes de que exista el agente.

La traza es la entrada del evaluador de trayectoria y de toda la tabla del
informe. Sin ella no se puede distinguir una respuesta correcta de una respuesta
correcta por casualidad, que es el criterio central de la práctica.

El coste se LEE de `usage_metadata`, que es lo que devuelve el proveedor en cada
mensaje. No se estima multiplicando tokens por una tarifa de memoria: las
tarifas cambian sin avisar y una tabla de coste que no cuadra con la factura no
defiende nada.
"""

from __future__ import annotations

from collections.abc import Sequence

from agente_10k.dominio.modelos import LlamadaHerramienta, Traza, UsoTokens


def extraer_llamadas(mensajes: Sequence[object]) -> list[LlamadaHerramienta]:
    """Las llamadas a herramienta de una lista de mensajes de LangChain.

    Empareja cada `tool_call` con su `ToolMessage` por `tool_call_id`, que es lo
    único que los relaciona cuando el modelo pide varias herramientas a la vez.

    Raises:
        NotImplementedError: Fase 4.
    """
    raise NotImplementedError("Fase 4 · Piettro: extracción de la trayectoria")


def extraer_uso(mensajes: Sequence[object]) -> UsoTokens:
    """Tokens y coste acumulados, leídos de los metadatos de uso.

    Raises:
        NotImplementedError: Fase 4.
    """
    raise NotImplementedError("Fase 4 · Piettro: contabilidad de tokens")


def cumple_trayectoria(trayectoria: Sequence[str], esperadas: Sequence[str]) -> bool:
    """Si la trayectoria pasó por todas las herramientas esperadas.

    Se comprueba INCLUSIÓN, no igualdad ni orden: que el agente llame primero a
    `list_available` para comprobar que el emisor existe y luego a
    `get_xbrl_fact` es exactamente lo que queremos, y penalizarlo por dar ese
    paso de más sería premiar al que adivina.

    Lo que sí es fallo es lo contrario: que `get_xbrl_fact` no aparezca en una
    pregunta numérica. Eso significa que la cifra salió del texto.

    Args:
        trayectoria: Los nombres de las herramientas, en orden de llamada.
        esperadas: Las que la pregunta declara como camino correcto.

    Returns:
        `True` si todas las esperadas están en la trayectoria.
    """
    usadas = set(trayectoria)
    return all(nombre in usadas for nombre in esperadas)


def resumir(traza: Traza) -> str:
    """La traza en una línea, para el REPL y para depurar el día 24."""
    camino = " → ".join(traza.trayectoria) or "(sin llamadas)"
    coste = "?" if traza.uso.coste_usd is None else f"{traza.uso.coste_usd:.5f} $"
    aviso = " [LÍMITE]" if traza.limite_alcanzado else ""
    guardarrail = (
        f" [guardarraíl x{traza.intervenciones_guardarrail}]"
        if traza.intervenciones_guardarrail
        else ""
    )
    return (
        f"{camino} · {traza.n_llamadas} llamadas · {traza.uso.tokens_total} "
        f"tokens · {coste} · {traza.latencia_s:.1f} s{aviso}{guardarrail}"
    )


class CapturadorTraza:
    """Acumula lo que pasa durante una invocación y produce la `Traza`."""

    def __init__(self, pregunta: str, version_prompt: str = "v1") -> None:
        """Arranca el cronómetro de una invocación.

        Raises:
            NotImplementedError: Fase 4.
        """
        raise NotImplementedError("Fase 4 · Piettro: capturador de trazas")

    def cerrar(self, resultado: object) -> Traza:
        """La traza completa a partir del resultado del agente.

        Raises:
            NotImplementedError: Fase 4.
        """
        raise NotImplementedError("Fase 4 · Piettro: capturador de trazas")
