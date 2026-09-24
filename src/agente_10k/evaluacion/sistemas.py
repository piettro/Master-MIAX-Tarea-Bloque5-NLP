"""Los sistemas que se evalúan: el agente final y el baseline del profesor.

Ambos se exponen como un `Sistema`, para que la tabla salga del mismo ejecutor
y los mismos evaluadores. `SistemaBaseline` solo adapta la salida de `miax_s2`.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from typing import Any

from agente_10k.agente.trazas import (
    RESULTADO_MAXIMO_TRAZA,
    extraer_llamadas,
    extraer_uso,
    respuesta_de,
)
from agente_10k.config import Settings, cargar_entorno, settings
from agente_10k.dominio.modelos import RespuestaFinanciera, Traza, UsoTokens

Sistema = Callable[[str], tuple[RespuestaFinanciera, Traza]]
"""Una pregunta entra; la respuesta estructurada y su traza salen."""

# Los nombres de siempre, para quien ya los importaba de aquí. La traducción de
# mensajes vive en `agente/trazas.py`, que es donde la necesita el agente.
llamadas_de_mensajes = extraer_llamadas
uso_de_mensajes = extraer_uso

__all__ = [
    "RESULTADO_MAXIMO_TRAZA",
    "Sistema",
    "SistemaBaseline",
    "cargar_entorno",
    "llamadas_de_mensajes",
    "respuesta_de",
    "sistema_final",
    "uso_de_mensajes",
]


def sistema_final(config: Settings | None = None) -> Sistema:
    """Nuestro agente, construido una sola vez desde la configuración.

    Se devuelve el agente entero y no su método: así su `descripcion` llega a
    la configuración del informe.
    """
    from agente_10k.agente.constructor import construir_agente

    return construir_agente(config or settings())


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
