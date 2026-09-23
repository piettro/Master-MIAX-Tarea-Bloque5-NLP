"""Los sistemas que se evalúan: el final y el baseline del profesor. FASE 5.

`evaluar()` no sabe qué agente está ejecutando. Recibe un `Sistema`: una función
que toma el texto de una pregunta y devuelve la `RespuestaFinanciera` y la
`Traza`. Así la tabla baseline contra final sale del MISMO ejecutor con los
MISMOS evaluadores, y la única diferencia entre las dos filas es el sistema.

* `sistema_final()` es nuestro agente (`agente/constructor.py`, fase 4).
* `SistemaBaseline` envuelve `miax_s2.baseline()`: el agente del día 10 tal y
  como lo repartió el profesor en la sesión 2 —las cuatro herramientas de la
  sesión 1, su system prompt y `create_agent`—, sin límite de llamadas ni
  guardarraíl. Es el baseline que usa él mismo en la celda de la tabla final
  de la sesión 2. Su código está en `baseline/miax_s2.py`, copiado sin tocar;
  lo único que hace este adaptador es traducir su salida a nuestra traza.
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

RESULTADO_MAXIMO_TRAZA = 2000
"""Caracteres del resultado de cada herramienta que se guardan en la traza.

`read_section` devuelve decenas de miles de tokens; guardarlos enteros por cada
pregunta hace que `resultados/` pese megas sin aportar nada a la evaluación,
que solo necesita el nombre y los argumentos de cada llamada.
"""


def cargar_entorno() -> None:
    """Carga `.env` en `os.environ` sin pisar lo que ya esté exportado.

    `Settings` lee `.env` solo para sus propios campos (`AGENTE10K_*`); las
    claves de API llevan el nombre canónico de cada SDK y hay que exportarlas.
    Sin esto, `OPENROUTER_API_KEY` en `.env` no llega nunca al proveedor.
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

        Mismo modelo a propósito: la tabla tiene que comparar dos sistemas, no
        dos modelos. `miax_s2` busca el corpus en `corpus/` o `/content/corpus`
        (Colab); aquí se le antepone el `dir_corpus` de la configuración, que es
        cambiar un dato de su módulo, no su código.
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

        El coste se lee del proveedor cuando lo reporta. Si no lo reporta, se
        calcula con la tabla de precios del propio profesor
        (`miax_s2.PRECIOS_OPENROUTER`) y queda anotado en `origen_coste`, para
        que nadie compare un coste leído con uno estimado sin saberlo.
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

NOMBRE_ESQUEMA = RespuestaFinanciera.__name__
"""Con salida estructurada por herramienta, el esquema aparece como una
`tool_call` más. No es una herramienta del agente y no entra en la trayectoria."""


def llamadas_de_mensajes(mensajes: Sequence[Any]) -> list[LlamadaHerramienta]:
    """Las llamadas a herramienta, emparejadas con su resultado por `tool_call_id`.

    El emparejamiento por identificador es lo único fiable cuando el modelo
    pide varias herramientas en el mismo turno.
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

    OpenRouter lo devuelve dentro del bloque de uso; según la versión del
    adaptador de LangChain acaba en `token_usage` o en `usage`.
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

    Si el modelo no llegó a producir salida estructurada, no se inventa nada: se
    guarda el último texto como prosa y el motivo, y los evaluadores lo tratan
    como lo que es.
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
