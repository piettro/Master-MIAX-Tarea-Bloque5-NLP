"""Captura de la trayectoria, los tokens, el coste y la latencia. FASE 4.

La traza es la entrada del evaluador de trayectoria y de toda la tabla del
informe. Sin ella no se puede distinguir una respuesta correcta de una respuesta
correcta por casualidad, que es el criterio central de la práctica.

El coste se LEE de los metadatos del mensaje cuando el proveedor lo manda.
OpenRouter no siempre lo manda: entonces lo estima el proveedor con la tarifa,
y la traza dice cuál de las dos cosas fue.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from agente_10k.dominio.modelos import (
    LlamadaHerramienta,
    RespuestaFinanciera,
    Traza,
    UsoTokens,
)

# La salida estructurada llega como una `tool_call` más, pero no es del agente
# y no entra en la trayectoria.
NOMBRE_ESQUEMA = RespuestaFinanciera.__name__

# Caracteres del resultado de cada herramienta que se guardan en la traza:
# `read_section` devuelve decenas de miles y `resultados/` acabaría pesando megas.
RESULTADO_MAXIMO_TRAZA = 2000


def extraer_llamadas(mensajes: Sequence[object]) -> list[LlamadaHerramienta]:
    """Las llamadas a herramienta, emparejadas con su resultado por `tool_call_id`.

    Por identificador y no por orden: el modelo puede pedir varias en un turno.
    """
    resultados = {
        getattr(m, "tool_call_id", None): str(getattr(m, "content", ""))
        for m in mensajes
        if getattr(m, "type", "") == "tool"
    }
    llamadas: list[LlamadaHerramienta] = []
    for mensaje in mensajes:
        for llamada in getattr(mensaje, "tool_calls", None) or []:
            if llamada.get("name") == NOMBRE_ESQUEMA:
                continue
            resultado = resultados.get(llamada.get("id"), "")
            llamadas.append(
                LlamadaHerramienta(
                    nombre=str(llamada.get("name", "")),
                    argumentos=dict(llamada.get("args") or {}),
                    resultado=resultado[:RESULTADO_MAXIMO_TRAZA],
                )
            )
    return llamadas


def _coste_reportado(mensaje: object) -> float | None:
    """El coste que el proveedor puso en los metadatos, si lo puso.

    Según la versión del adaptador cae en `token_usage` o en `usage`.
    """
    metadatos = getattr(mensaje, "response_metadata", None) or {}
    for clave in ("token_usage", "usage"):
        bloque = metadatos.get(clave) or {}
        if isinstance(bloque, dict) and bloque.get("cost") is not None:
            return float(bloque["cost"])
    return None


def extraer_uso(mensajes: Sequence[object]) -> UsoTokens:
    """Tokens y coste acumulados de todos los mensajes del modelo."""
    total = UsoTokens()
    for mensaje in mensajes:
        uso = getattr(mensaje, "usage_metadata", None) or {}
        if not uso:
            continue
        total = total + UsoTokens(
            tokens_entrada=int(uso.get("input_tokens", 0) or 0),
            tokens_salida=int(uso.get("output_tokens", 0) or 0),
            coste_usd=_coste_reportado(mensaje),
        )
    return total


def respuesta_de(estructurada: object, mensajes: Sequence[Any]) -> RespuestaFinanciera:
    """La `RespuestaFinanciera` del agente, o una de `fuente="ninguna"` si no hay.

    Sin salida estructurada se guarda el último texto como prosa, sin inventar nada.
    """
    if estructurada is not None:
        datos = (
            estructurada.model_dump()
            if hasattr(estructurada, "model_dump")
            else estructurada
        )
        return RespuestaFinanciera.model_validate(datos)
    ultimo = str(getattr(mensajes[-1], "content", "")) if mensajes else ""
    return RespuestaFinanciera(
        respuesta=ultimo[:1000],
        fuente="ninguna",
        motivo_sin_dato="el agente no produjo salida estructurada",
    )


def cumple_trayectoria(trayectoria: Sequence[str], esperadas: Sequence[str]) -> bool:
    """Si la trayectoria pasó por todas las herramientas esperadas.

    Se comprueba INCLUSIÓN, no igualdad ni orden: que el agente llame primero a
    `list_available` para comprobar que el emisor existe y luego a
    `get_xbrl_fact` es exactamente lo que queremos, y penalizarlo por dar ese
    paso de más sería premiar al que adivina.

    Lo que sí es fallo es lo contrario: que `get_xbrl_fact` no aparezca en una
    pregunta numérica. Eso significa que la cifra salió del texto.
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

    def __init__(
        self,
        pregunta: str,
        version_prompt: str = "v1",
        *,
        proveedor: str = "",
        modelo: str = "",
        config_retrieval: dict[str, object] | None = None,
    ) -> None:
        """Arranca el cronómetro de una invocación."""
        self._pregunta = pregunta
        self._version = version_prompt
        self._proveedor = proveedor
        self._modelo = modelo
        self._config = dict(config_retrieval or {})
        self._comienzo = time.perf_counter()

    def cerrar(self, resultado: object) -> Traza:
        """La traza completa a partir del resultado del agente."""
        mensajes: Sequence[Any] = (
            resultado.get("messages", []) if isinstance(resultado, dict) else []
        )
        return Traza(
            pregunta=self._pregunta,
            llamadas=extraer_llamadas(mensajes),
            uso=extraer_uso(mensajes),
            latencia_s=time.perf_counter() - self._comienzo,
            version_prompt=self._version,
            proveedor=self._proveedor,
            modelo=self._modelo,
            config_retrieval=self._config,
        )
