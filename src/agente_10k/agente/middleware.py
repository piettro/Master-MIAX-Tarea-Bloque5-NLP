"""Middleware del agente. FASE 4. P4: Chain of Responsibility.

Dos eslabones, y los dos comparten la misma filosofía: **devolverle el problema
al modelo, no arreglárselo por detrás.**

`LimitadorLlamadas` corta la invocación al superar N llamadas a herramienta. El
notebook de la sesión 1 enseña el bucle infinito con el margen bruto de Amazon:
la tool devuelve un aviso una y otra vez y el modelo reintenta variantes del
concepto sin rendirse. Al cortar, se le inyecta un mensaje que le explica que
agotó su presupuesto y que responda con lo que tenga o declare que no lo sabe.

`GuardarraílXBRL` extrae las cifras de la respuesta estructurada y las contrasta
contra el repositorio XBRL con la tolerancia de `dominio/tolerancia.py` —la
misma que usa el evaluador de cifra, un solo sitio—. Si no cuadran, NO corrige
la cifra: le devuelve al modelo el desajuste (valor afirmado, valor XBRL,
concepto consultado) y le deja reintentar. Corregirla por su cuenta enmascara el
fallo y falsea la evaluación: la tabla diría que el sistema acierta cuando quien
acierta es el guardarraíl.

Las dos clases son lógica pura y se prueban sin LangChain. `construir_middleware`
es lo único que sabe del framework: las envuelve en los ganchos de
`create_agent`.

Cada intervención se registra en la traza. «Cuántas veces saltó el guardarraíl y
cuántas recuperó» es de las cifras más interesantes de la presentación.
"""

from __future__ import annotations

from typing import Any

from agente_10k.dominio.modelos import RespuestaFinanciera, Traza
from agente_10k.dominio.protocolos import RepositorioXbrl
from agente_10k.dominio.tolerancia import TOLERANCIA, Tolerancia

MENSAJE_LIMITE = (
    "Has agotado tu presupuesto de {maximo} llamadas a herramienta para esta "
    "pregunta. No puedes llamar a ninguna más. Responde ahora con lo que ya "
    "tengas, y si no es suficiente para afirmar nada con fundamento, dilo: "
    'fuente="ninguna" y explica en motivo_sin_dato qué te faltó.'
)

MENSAJE_DESAJUSTE = (
    "GUARDARRAÍL: la cifra que afirmas no coincide con la que reportó la "
    "compañía en XBRL.\n"
    "  afirmada : {afirmada} {unidad}\n"
    "  en XBRL  : {xbrl} {unidad_xbrl} ({ticker} FY{ejercicio} · {concepto})\n"
    "  tolerancia: {tolerancia}\n"
    "Vuelve a consultar get_xbrl_fact y corrige la respuesta. Si crees que el "
    "concepto consultado no es el que pide la pregunta, dilo explícitamente en "
    "lugar de ajustar el número."
)

# Llamadas al modelo por encima del presupuesto de herramientas antes de cortar
# en seco: el limitador ya le ha dicho que pare, esto es por si no hace caso.
HOLGURA_LLAMADAS_MODELO = 6

# Por debajo de esto una cifra lleva decimales (un BPA de 11,86 USD).
UMBRAL_SIN_DECIMALES = 1000


def _cifra(valor: float) -> str:
    """Un número legible: sin decimales si es grande, con dos si no."""
    if abs(valor) >= UMBRAL_SIN_DECIMALES:
        return f"{valor:,.0f}"
    return f"{valor:,.2f}"


class LimitadorLlamadas:
    """Corta la invocación al superar el presupuesto de llamadas."""

    def __init__(self, max_llamadas: int = 8) -> None:
        """Fija el presupuesto."""
        self.max_llamadas = max_llamadas
        self.alcanzado = False

    def mensaje(self) -> str:
        """Lo que se le dice al modelo cuando se queda sin presupuesto."""
        return MENSAJE_LIMITE.format(maximo=self.max_llamadas)

    def procesar(self, traza: Traza) -> str | None:
        """El mensaje a inyectar si se superó el límite, o `None`."""
        if self.max_llamadas == 0 or traza.n_llamadas > self.max_llamadas:
            return self.mensaje()
        return None

    def reiniciar(self) -> None:
        """Para la siguiente pregunta."""
        self.alcanzado = False


class GuardarrailXbrl:
    """Contrasta las cifras afirmadas contra XBRL y devuelve el desajuste."""

    def __init__(
        self,
        xbrl: RepositorioXbrl,
        tolerancia: Tolerancia | None = None,
        max_reintentos: int = 1,
    ) -> None:
        """Monta el guardarraíl sobre el repositorio XBRL.

        Args:
            xbrl: De dónde sale la verdad.
            tolerancia: La de `dominio.tolerancia` por defecto. Es la MISMA que
                usa el evaluador de cifra: si aquí se pasara otra, el sistema
                aceptaría cifras que la evaluación suspende.
            max_reintentos: Cuántas veces se le devuelve el desajuste al modelo
                antes de dejar pasar la respuesta con el desajuste registrado.
        """
        self._xbrl = xbrl
        self.tolerancia = tolerancia or TOLERANCIA
        self.max_reintentos = max_reintentos
        self.intervenciones = 0

    def verificar(self, respuesta: RespuestaFinanciera) -> str | None:
        """El mensaje de desajuste, o `None` si la cifra cuadra o no aplica.

        Devuelve `None` cuando no hay cifra que contrastar, cuando la respuesta
        declara `fuente="ninguna"` —que es la respuesta correcta a un hueco— o
        cuando la cifra cuadra dentro de la tolerancia. Nunca toca la respuesta.
        """
        if respuesta.cifra is None or respuesta.fuente == "ninguna":
            return None
        if not (respuesta.ticker and respuesta.ejercicio and respuesta.concept_xbrl):
            return None
        hecho = self._xbrl.obtener(
            respuesta.ticker, int(respuesta.ejercicio), respuesta.concept_xbrl
        )
        if hecho is None:
            return None  # sin hecho no hay contra qué contrastar
        if self.tolerancia.coincide(float(respuesta.cifra), float(hecho.value)):
            return None
        return MENSAJE_DESAJUSTE.format(
            afirmada=_cifra(float(respuesta.cifra)),
            unidad=respuesta.unidad or "",
            xbrl=_cifra(float(hecho.value)),
            unidad_xbrl=hecho.unit,
            ticker=hecho.ticker,
            ejercicio=hecho.fiscal_year,
            concepto=hecho.concept,
            tolerancia=self.tolerancia.describir(),
        )

    def intervenir(self, respuesta: RespuestaFinanciera) -> str | None:
        """Como `verificar`, pero respetando el máximo de reintentos."""
        if self.intervenciones >= self.max_reintentos:
            return None
        mensaje = self.verificar(respuesta)
        if mensaje is not None:
            self.intervenciones += 1
        return mensaje

    def reiniciar(self) -> None:
        """Para la siguiente pregunta."""
        self.intervenciones = 0


def _herramientas_hechas(estado: Any) -> int:  # noqa: ANN401 — estado de LangGraph
    mensajes = estado.get("messages", []) if isinstance(estado, dict) else []
    return sum(1 for m in mensajes if getattr(m, "type", "") == "tool")


def construir_middleware(
    max_llamadas: int,
    xbrl: RepositorioXbrl,
    *,
    proveedor: Any = None,  # noqa: ANN401 — un ProveedorLangChain, o nada
    limitador: LimitadorLlamadas | None = None,
    guardarrail: GuardarrailXbrl | None = None,
) -> list[object]:
    """La cadena de middleware para `create_agent`, de fuera hacia dentro.

    1. Reintento ante errores transitorios del proveedor —los 5xx y el
       «Provider returned error» de OpenRouter—, salvo los de cuota.
    2. Conmutación al modelo de reserva ante 401/402/429, si hay proveedor.
    3. Limitador: pasado el presupuesto, la herramienta no se ejecuta y el
       modelo recibe el aviso de que responda con lo que tenga.
    4. Tope duro de llamadas al modelo, por si no hace caso al aviso.
    5. Guardarraíl XBRL sobre la respuesta estructurada.
    """
    from langchain.agents.middleware import (
        ModelCallLimitMiddleware,
        ModelRetryMiddleware,
        after_model,
        wrap_model_call,
        wrap_tool_call,
    )
    from langchain_core.messages import HumanMessage, ToolMessage

    from agente_10k.agente.proveedores import es_error_de_cuota

    limitador = limitador or LimitadorLlamadas(max_llamadas)
    guardarrail = guardarrail or GuardarrailXbrl(xbrl)

    def _transitorio(exc: Exception) -> bool:
        return not es_error_de_cuota(exc)

    cadena: list[object] = [
        ModelRetryMiddleware(
            max_retries=2, retry_on=_transitorio, on_failure="error", initial_delay=2.0
        )
    ]

    if proveedor is not None and hasattr(proveedor, "conmutar"):

        @wrap_model_call
        def conmutar_ante_cuota(request: Any, handler: Any) -> Any:  # noqa: ANN401
            if proveedor.en_reserva:
                request = request.override(model=proveedor.modelo_langchain())
            try:
                return handler(request)
            except Exception as exc:
                if not (es_error_de_cuota(exc) and proveedor.conmutar()):
                    raise
                return handler(request.override(model=proveedor.modelo_langchain()))

        cadena.append(conmutar_ante_cuota)

    @wrap_tool_call
    def limitar_llamadas(request: Any, handler: Any) -> Any:  # noqa: ANN401
        if _herramientas_hechas(request.state) >= limitador.max_llamadas:
            limitador.alcanzado = True
            return ToolMessage(
                content=limitador.mensaje(),
                tool_call_id=request.tool_call["id"],
                name=request.tool_call.get("name"),
            )
        return handler(request)

    cadena.append(limitar_llamadas)
    cadena.append(
        ModelCallLimitMiddleware(
            run_limit=max_llamadas + HOLGURA_LLAMADAS_MODELO, exit_behavior="end"
        )
    )

    @after_model(can_jump_to=["model"])
    def guardarrail_xbrl(state: Any, runtime: Any) -> Any:  # noqa: ANN401
        estructurada = state.get("structured_response")
        if estructurada is None:
            return None
        datos = (
            estructurada.model_dump()
            if hasattr(estructurada, "model_dump")
            else estructurada
        )
        mensaje = guardarrail.intervenir(RespuestaFinanciera.model_validate(datos))
        if mensaje is None:
            return None
        return {
            "messages": [HumanMessage(content=mensaje)],
            "structured_response": None,
            "jump_to": "model",
        }

    cadena.append(guardarrail_xbrl)
    return cadena
