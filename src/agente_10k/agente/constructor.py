"""Ensambla el agente con LangChain. FASE 4.

    create_agent(
        model=..., tools=..., system_prompt=...,
        response_format=ToolStrategy(schema=RespuestaFinanciera),
        checkpointer=InMemorySaver(),
        middleware=[reintento, reserva, limitador, tope, guardarraíl],
    )

`ToolStrategy` y no la salida nativa: el esquema viaja como una herramienta
más, que es lo que soportan todos los modelos de OpenRouter, y así cambiar de
modelo no rompe la salida estructurada.

Cada pregunta va en su propio `thread_id`. Con `InMemorySaver` y un hilo fijo,
la pregunta 7 del golden set vería la conversación de las seis anteriores.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import ValidationError

from agente_10k.agente.middleware import (
    GuardarrailXbrl,
    LimitadorLlamadas,
    construir_middleware,
)
from agente_10k.agente.prompts import system_prompt
from agente_10k.agente.proveedores import construir_proveedor
from agente_10k.agente.trazas import CapturadorTraza, respuesta_de
from agente_10k.config import Settings, cargar_entorno, settings
from agente_10k.dominio.modelos import RespuestaFinanciera, Traza

MENSAJE_SIN_SALIDA = (
    "No has devuelto la respuesta estructurada. Devuélvela ahora con el esquema "
    "RespuestaFinanciera, usando lo que ya has consultado. Si no basta para "
    'afirmar nada, fuente="ninguna" y explica en motivo_sin_dato qué faltó.'
)
"""Lo que se le dice al modelo cuando termina sin salida estructurada.

Gemini a veces consulta bien, tiene la cifra delante y cierra con un mensaje
vacío. Pedírsela en el mismo hilo cuesta una llamada; repetir la pregunta,
todas las consultas otra vez.
"""


class AgenteInvestigador:
    """El agente montado: herramientas, prompt, middleware y salida estructurada."""

    def __init__(
        self,
        config: Settings | None = None,
        proveedor: Any = None,  # noqa: ANN401 — un ProveedorLangChain o un doble
    ) -> None:
        """Monta el agente desde la configuración.

        Carga el corpus una vez, monta el cinturón de herramientas con el mismo
        proveedor que responde —la reescritura de `search_filings` gasta del
        mismo sitio— y deja el agente listo para invocar.
        """
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy
        from langgraph.checkpoint.memory import InMemorySaver

        from agente_10k.corpus import cargar_corpus
        from agente_10k.tools.contratos import usar_cinturon
        from agente_10k.tools.implementacion import herramientas_por_defecto
        from agente_10k.tools.registro import construir_tools

        cargar_entorno()
        self._cfg = config or settings()
        self._proveedor = proveedor or construir_proveedor(self._cfg)
        corpus = cargar_corpus(self._cfg)
        usar_cinturon(herramientas_por_defecto(self._cfg, self._proveedor, corpus))

        self._limitador = LimitadorLlamadas(self._cfg.max_llamadas_herramienta)
        self._guardarrail = GuardarrailXbrl(
            corpus.xbrl, max_reintentos=self._cfg.max_reintentos_guardarrail
        )
        self._agente: Any = create_agent(
            model=self._proveedor.modelo_langchain(),
            tools=list(construir_tools()),
            system_prompt=system_prompt(self._cfg.version_prompt),
            response_format=ToolStrategy(schema=RespuestaFinanciera),
            checkpointer=InMemorySaver(),
            middleware=construir_middleware(  # type: ignore[arg-type]
                self._cfg.max_llamadas_herramienta,
                corpus.xbrl,
                proveedor=self._proveedor,
                limitador=self._limitador,
                guardarrail=self._guardarrail,
            ),
        )

    @property
    def descripcion(self) -> dict[str, object]:
        """Qué sistema es, para `InformeEvaluacion.configuracion`."""
        return {
            "sistema": "agente final (fase 4)",
            "modelo": f"{self._proveedor.proveedor}:{self._proveedor.modelo}",
            "en_reserva": self._proveedor.en_reserva,
            "limite_llamadas": self._cfg.max_llamadas_herramienta,
            "guardarrail_xbrl": True,
            "reintentos_guardarrail": self._cfg.max_reintentos_guardarrail,
            "version_prompt": self._cfg.version_prompt,
            "origen_coste": getattr(self._proveedor, "origen_coste", "sin datos"),
        }

    def responder(self, pregunta: str) -> tuple[RespuestaFinanciera, Traza]:
        """Responde una pregunta y devuelve la respuesta con su traza.

        Nunca lanza por culpa del modelo: si la salida estructurada no valida,
        devuelve una `RespuestaFinanciera` con `fuente="ninguna"` y el motivo.
        Los errores del proveedor sí suben, después de los reintentos: tragarlos
        convertiría una caída de red en un «no está en el corpus», que en una
        pregunta hueco contaría como acierto.
        """
        if not pregunta.strip():
            return (
                RespuestaFinanciera(
                    respuesta="No se ha recibido ninguna pregunta.",
                    fuente="ninguna",
                    motivo_sin_dato="la pregunta llegó vacía",
                ),
                Traza(pregunta=pregunta, version_prompt=self._cfg.version_prompt),
            )

        self._limitador.reiniciar()
        self._guardarrail.reiniciar()
        capturador = CapturadorTraza(
            pregunta,
            self._cfg.version_prompt,
            config_retrieval=self._cfg.resumen_retrieval(),
        )
        hilo = {"configurable": {"thread_id": f"pregunta-{uuid.uuid4().hex}"}}
        resultado = self._agente.invoke(
            {"messages": [{"role": "user", "content": pregunta}]}, config=hilo
        )
        if resultado.get("structured_response") is None:
            # Mismo hilo: el modelo conserva lo que ya consultó, y la traza
            # recoge las dos vueltas porque el estado es el del hilo entero.
            resultado = self._agente.invoke(
                {"messages": [{"role": "user", "content": MENSAJE_SIN_SALIDA}]},
                config=hilo,
            )
        mensajes = resultado.get("messages", [])
        traza = capturador.cerrar(resultado)
        uso = (
            self._proveedor.completar_coste(traza.uso, mensajes)
            if hasattr(self._proveedor, "completar_coste")
            else traza.uso
        )
        traza = traza.model_copy(
            update={
                "uso": uso,
                "proveedor": self._proveedor.proveedor,
                "modelo": self._proveedor.modelo,
                "intervenciones_guardarrail": self._guardarrail.intervenciones,
                "limite_alcanzado": self._limitador.alcanzado,
            }
        )
        try:
            respuesta = respuesta_de(resultado.get("structured_response"), mensajes)
        except ValidationError as exc:
            respuesta = RespuestaFinanciera(
                respuesta="",
                fuente="ninguna",
                motivo_sin_dato=f"la salida estructurada no validó: {exc}"[:500],
            )
        return respuesta, traza

    def __call__(self, pregunta: str) -> tuple[RespuestaFinanciera, Traza]:
        """El agente es un `Sistema`: el ejecutor lo llama como a una función."""
        return self.responder(pregunta)


def construir_agente(config: Settings | None = None) -> AgenteInvestigador:
    """El agente listo para invocar."""
    return AgenteInvestigador(config)
