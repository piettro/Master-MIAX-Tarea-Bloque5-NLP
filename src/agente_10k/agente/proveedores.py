"""Fábrica de proveedores de LLM. FASE 4 — Piettro. P5: Factory + Adapter.

STUB salvo `ProveedorFake`, que sí está implementado porque es lo que permite
que toda la suite del agente corra sin red y sin clave de API.

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

from agente_10k.config import Settings
from agente_10k.dominio.modelos import UsoTokens

CODIGOS_CUOTA = (401, 402, 429)
"""401 credenciales, 402 sin saldo, 429 límite de tasa. Los tres conmutan."""


class ProveedorLangChain:
    """Adaptador sobre `init_chat_model`, con fallback ordenado."""

    def __init__(self, config: Settings) -> None:
        """Prepara el proveedor sin crear todavía el cliente.

        Raises:
            NotImplementedError: Fase 4.
        """
        raise NotImplementedError("Fase 4 · Piettro: proveedor de LLM")

    @property
    def modelo(self) -> str:
        """El modelo activo ahora mismo: el primario o el de reserva."""
        raise NotImplementedError("Fase 4 · Piettro: proveedor de LLM")

    @property
    def proveedor(self) -> str:
        """El proveedor activo."""
        raise NotImplementedError("Fase 4 · Piettro: proveedor de LLM")

    @property
    def en_reserva(self) -> bool:
        """Si ya se conmutó al modelo de reserva. Va a la traza.

        Que aparezca en la traza no es un detalle: una ejecución del golden set
        hecha a medias con dos modelos distintos no es comparable con otra, y
        sin este campo no habría forma de saberlo después.
        """
        raise NotImplementedError("Fase 4 · Piettro: proveedor de LLM")

    def chat(self) -> object:
        """El objeto de chat de LangChain, ya configurado con temperature=0."""
        raise NotImplementedError("Fase 4 · Piettro: proveedor de LLM")

    def uso_ultima_llamada(self) -> UsoTokens:
        """Tokens y coste de la última llamada, LEÍDOS de `usage_metadata`.

        No se estima multiplicando tokens por una tarifa: el proveedor manda el
        dato y la tabla del informe tiene que coincidir con la factura.
        """
        raise NotImplementedError("Fase 4 · Piettro: proveedor de LLM")


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


def construir_proveedor(config: Settings) -> object:
    """El proveedor que describe la configuración. P5: Factory.

    Raises:
        NotImplementedError: Fase 4.
    """
    raise NotImplementedError("Fase 4 · Piettro: fábrica de proveedores")
