"""Fábrica de proveedores de LLM. P5: Factory + Adapter.

El proveedor se elige por variable de entorno y LangChain abstrae el resto:
`init_chat_model("openrouter:google/gemini-3.8-flash")` y
`init_chat_model("anthropic:claude-opus-5")` devuelven el mismo objeto. Cambiar
de proveedor es cambiar una cadena, no tocar código.

**El fallback es una VARIABLE DE ESTADO, no un try/except por llamada.** Cuando
el primario devuelve 401, 402 o 429, se conmuta al alternativo y NO se vuelve a
intentar el primario en la llamada siguiente. El pseudocódigo que el profesor
escribió en clase reintentaba el gratuito cada vez, y él mismo señaló que está
mal: con veinte preguntas son veinte llamadas fallidas de más, veinte latencias
de más y una tabla de coste que no cuadra con nada.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from agente_10k.config import Settings
from agente_10k.dominio.modelos import UsoTokens

CODIGOS_CUOTA = (401, 402, 429)
"""401 credenciales, 402 sin saldo, 429 límite de tasa. Los tres conmutan."""


def codigo_http(exc: BaseException) -> int | None:
    """El código HTTP de un error del cliente, venga del SDK que venga."""
    for origen in (exc, getattr(exc, "response", None)):
        codigo = getattr(origen, "status_code", None) or getattr(origen, "status", None)
        if isinstance(codigo, int):
            return codigo
    return None


def es_error_de_cuota(exc: BaseException) -> bool:
    """Si el error es de los que conmutan al modelo de reserva."""
    return codigo_http(exc) in CODIGOS_CUOTA


def estimar_coste(mensajes: Sequence[object], identificador: str) -> float:
    """Coste en USD con la tarifa de `miax_s2.PRECIOS_OPENROUTER`.

    Solo para cuando el proveedor no manda el coste en los metadatos. Es la
    misma tabla que usa el baseline, así que las dos columnas son comparables.
    """
    from agente_10k.baseline import miax_s2

    return float(miax_s2.coste_de({"messages": list(mensajes)}, identificador))


class _ChatQueAnota:
    """El chat del modelo activo, que anota el uso y conmuta ante cuota."""

    def __init__(self, proveedor: ProveedorLangChain) -> None:
        self._proveedor = proveedor

    def invoke(self, mensajes: object) -> object:
        """Invoca el modelo activo; si se queda sin cuota, pasa al de reserva."""
        try:
            respuesta = self._proveedor.modelo_langchain().invoke(mensajes)
        except Exception as exc:
            if not (es_error_de_cuota(exc) and self._proveedor.conmutar()):
                raise
            respuesta = self._proveedor.modelo_langchain().invoke(mensajes)
        self._proveedor.anotar([respuesta])
        return respuesta


class ProveedorLangChain:
    """Adaptador sobre `init_chat_model`, con fallback ordenado."""

    def __init__(self, config: Settings) -> None:
        """Prepara el proveedor sin crear todavía el cliente.

        Crear el cliente aquí obligaría a tener la clave para construir el
        objeto, y los tests y la fábrica lo construyen sin llamar a nada.
        """
        self._cfg = config
        self._en_reserva = False
        self._modelos: dict[str, Any] = {}
        self._uso = UsoTokens()
        self.origen_coste = "sin datos"

    @property
    def _identificador(self) -> str:
        if self._en_reserva and self._cfg.llm_model_fallback:
            return f"{self._cfg.llm_provider}:{self._cfg.llm_model_fallback}"
        return self._cfg.identificador_modelo()

    @property
    def modelo(self) -> str:
        """El modelo activo ahora mismo: el primario o el de reserva."""
        return self._identificador.partition(":")[2]

    @property
    def proveedor(self) -> str:
        """El proveedor activo."""
        return self._identificador.partition(":")[0]

    @property
    def identificador(self) -> str:
        """`proveedor:modelo` del modelo activo, el formato de `init_chat_model`."""
        return self._identificador

    @property
    def en_reserva(self) -> bool:
        """Si ya se conmutó al modelo de reserva. Va a la traza.

        Una ejecución del golden set hecha a medias con dos modelos distintos no
        es comparable con otra, y sin este campo no habría forma de saberlo.
        """
        return self._en_reserva

    def conmutar(self) -> bool:
        """Pasa al modelo de reserva. `False` si no hay a dónde pasar.

        Es de un solo sentido: una vez en reserva, no se vuelve al primario.
        """
        reserva = self._cfg.llm_model_fallback
        if self._en_reserva or not reserva or reserva == self._cfg.llm_model:
            return False
        self._en_reserva = True
        return True

    def modelo_langchain(self) -> Any:  # noqa: ANN401 — es el tipo de LangChain
        """El chat de LangChain del modelo activo, para `create_agent`."""
        identificador = self._identificador
        if identificador not in self._modelos:
            from langchain.chat_models import init_chat_model

            self._modelos[identificador] = init_chat_model(
                identificador, temperature=self._cfg.temperatura
            )
        return self._modelos[identificador]

    def chat(self) -> object:
        """El chat del modelo activo, que anota el uso de cada llamada."""
        return _ChatQueAnota(self)

    def completar_coste(self, uso: UsoTokens, mensajes: Sequence[object]) -> UsoTokens:
        """El uso con coste: el del proveedor si lo mandó, la tarifa si no."""
        if uso.coste_usd is not None:
            self.origen_coste = "reportado por el proveedor"
            return uso
        coste = estimar_coste(mensajes, self._identificador)
        if not coste:
            return uso
        self.origen_coste = "estimado con miax_s2.PRECIOS_OPENROUTER"
        return uso.model_copy(update={"coste_usd": coste})

    def anotar(self, mensajes: Sequence[object]) -> None:
        """Guarda el uso de la última llamada, con su coste."""
        from agente_10k.agente.trazas import extraer_uso

        self._uso = self.completar_coste(extraer_uso(mensajes), mensajes)

    def uso_ultima_llamada(self) -> UsoTokens:
        """Tokens y coste de la última llamada hecha con `chat()`."""
        return self._uso


class ProveedorFake:
    """Un proveedor que no llama a nada. Es el doble de toda la suite.

    Devuelve trayectorias predefinidas: una lista de respuestas que va
    entregando en orden. Con esto se prueban el limitador, el guardarraíl, el
    reintento y la salida estructurada sin gastar un céntimo ni depender de que
    haya red en el aula el día 24.
    """

    def __init__(
        self,
        respuestas: list[object] | None = None,
        modelo: str = "fake",
        uso: UsoTokens | None = None,
    ) -> None:
        """Prepara el doble con las respuestas que irá devolviendo en orden."""
        self._respuestas = list(respuestas or [])
        self._modelo = modelo
        self._uso = uso or UsoTokens(
            tokens_entrada=100, tokens_salida=50, coste_usd=0.0
        )
        self.llamadas: list[object] = []

    @property
    def modelo(self) -> str:
        """El identificador del modelo simulado."""
        return self._modelo

    @property
    def proveedor(self) -> str:
        """Siempre 'fake'."""
        return "fake"

    @property
    def en_reserva(self) -> bool:
        """Un doble nunca conmuta."""
        return False

    def chat(self) -> object:
        """El propio doble hace de objeto de chat."""
        return self

    def uso_ultima_llamada(self) -> UsoTokens:
        """El uso fijo con el que se construyó."""
        return self._uso

    def invoke(self, entrada: object) -> object:
        """Devuelve la siguiente respuesta predefinida.

        Raises:
            AssertionError: Si se pidieron más respuestas de las preparadas.
                Es una señal de que el test esperaba una trayectoria más corta
                y conviene que salte en vez de devolver algo plausible.
        """
        self.llamadas.append(entrada)
        if not self._respuestas:
            raise AssertionError(
                f"ProveedorFake agotado: se pidió la llamada "
                f"{len(self.llamadas)} y solo se prepararon "
                f"{len(self.llamadas) - 1} respuestas."
            )
        return self._respuestas.pop(0)


def construir_proveedor(config: Settings) -> ProveedorLangChain:
    """El proveedor que describe la configuración. P5: Factory."""
    return ProveedorLangChain(config)
