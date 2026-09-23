"""Los sistemas que se evalúan: el agente final y el baseline del profesor.

Ambos se exponen como un `Sistema`, para que la tabla salga del mismo ejecutor
y los mismos evaluadores. `SistemaBaseline` solo adapta la salida de `miax_s2`.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from typing import Any

from agente_10k.config import RAIZ_REPO, Settings, settings
from agente_10k.dominio.modelos import (
    LlamadaHerramienta,
    RespuestaFinanciera,
    Traza,
    UsoTokens,
)

Sistema = Callable[[str], tuple[RespuestaFinanciera, Traza]]
"""Una pregunta entra; la respuesta estructurada y su traza salen."""

# Caracteres del resultado de cada herramienta que se guardan en la traza:
# `read_section` devuelve decenas de miles y `resultados/` acabaría pesando megas.
RESULTADO_MAXIMO_TRAZA = 2000


def cargar_entorno() -> None:
    """Carga `.env` en `os.environ` sin pisar lo que ya esté exportado.

    `Settings` solo lee de `.env` sus campos `AGENTE10K_*`, no las claves de API.
    """
    from dotenv import load_dotenv

    load_dotenv(RAIZ_REPO / ".env", override=False)


def sistema_final(config: Settings | None = None) -> Sistema:
    """Nuestro agente, construido una sola vez desde la configuración."""
    from agente_10k.agente.constructor import construir_agente

    return construir_agente(config or settings()).responder


class SistemaBaseline:
    """El agente del día 10 del profesor, visto como un `Sistema`."""

    def __init__(self, config: Settings | None = None) -> None:
        """Monta `miax_s2.baseline()` con el mismo modelo que el sistema final.

        Mismo modelo a propósito: la tabla compara dos sistemas, no dos modelos.
        """
        from agente_10k.baseline import miax_s2

        cfg = config or settings()
        cargar_entorno()
        if cfg.dir_corpus not in miax_s2.CANDIDATOS_CORPUS:
            miax_s2.CANDIDATOS_CORPUS.insert(0, cfg.dir_corpus)
        self._miax_s2: Any = miax_s2
        self._modelo = cfg.identificador_modelo()
        self._agente: Any = miax_s2.baseline(self._modelo)
        self.origen_coste = "sin datos"

    @property
    def descripcion(self) -> dict[str, object]:
        """Qué sistema es, para `InformeEvaluacion.configuracion`."""
        return {
            "sistema": "baseline del profesor (miax_s2.baseline, sesión 2)",
            "modelo": self._modelo,
            "limite_llamadas": None,
            "guardarrail_xbrl": False,
            "recuperador": "denso bge-small, filtros los que pase el agente",
            "origen_coste": self.origen_coste,
        }

    def __call__(self, pregunta: str) -> tuple[RespuestaFinanciera, Traza]:
        """Ejecuta el agente del profesor y traduce su salida."""
        comienzo = time.perf_counter()
        resultado = self._agente.invoke(
            {"messages": [{"role": "user", "content": pregunta}]},
            config={"configurable": {"thread_id": f"baseline-{uuid.uuid4().hex}"}},
        )
        latencia = time.perf_counter() - comienzo
        mensajes: Sequence[Any] = resultado.get("messages", [])
        uso = self._uso(mensajes)
        proveedor, _, modelo = self._modelo.partition(":")
        traza = Traza(
            pregunta=pregunta,
            llamadas=llamadas_de_mensajes(mensajes),
            uso=uso,
            latencia_s=latencia,
            version_prompt="baseline-profesor",
            proveedor=proveedor,
            modelo=modelo,
            config_retrieval={"recuperador": "denso (miax_s2.buscar_con_filtros)"},
        )
        return respuesta_de(resultado.get("structured_response"), mensajes), traza

    def _uso(self, mensajes: Sequence[Any]) -> UsoTokens:
        """Tokens de los metadatos de uso; coste del proveedor o, si no, tarifa.

        Cuál de los dos fue queda anotado en `origen_coste`.
        """
        uso = uso_de_mensajes(mensajes)
        if uso.coste_usd is not None:
            self.origen_coste = "reportado por el proveedor"
            return uso
        coste = float(
            self._miax_s2.coste_de({"messages": list(mensajes)}, self._modelo)
        )
        if coste:
            self.origen_coste = "estimado con miax_s2.PRECIOS_OPENROUTER"
            return uso.model_copy(update={"coste_usd": coste})
        return uso


# ---------------------------------------------------------------------------
# Traducción de los mensajes de LangChain. Funciones puras: se prueban sin red.
# ---------------------------------------------------------------------------

# La salida estructurada llega como una `tool_call` más, pero no es del agente
# y no entra en la trayectoria.
NOMBRE_ESQUEMA = RespuestaFinanciera.__name__


def llamadas_de_mensajes(mensajes: Sequence[Any]) -> list[LlamadaHerramienta]:
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
    """El coste que el proveedor puso en los metadatos del mensaje, si lo puso.

    Según la versión del adaptador de LangChain cae en `token_usage` o en `usage`.
    """
    metadatos = getattr(mensaje, "response_metadata", None) or {}
    for clave in ("token_usage", "usage"):
        bloque = metadatos.get(clave) or {}
        if isinstance(bloque, dict) and bloque.get("cost") is not None:
            return float(bloque["cost"])
    return None


def uso_de_mensajes(mensajes: Sequence[Any]) -> UsoTokens:
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
