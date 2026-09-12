"""Middleware del agente. FASE 4 — Piettro. P4: Chain of Responsibility.

STUB. Las firmas y el contrato están fijados; el cuerpo es de la fase 4.

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

Cada intervención se registra en la traza. «Cuántas veces saltó el guardarraíl y
cuántas recuperó» es de las cifras más interesantes de la presentación.
"""

from __future__ import annotations

from agente_10k.dominio.modelos import RespuestaFinanciera, Traza
from agente_10k.dominio.protocolos import RepositorioXbrl
from agente_10k.dominio.tolerancia import Tolerancia

MENSAJE_LIMITE = (
    "Has agotado tu presupuesto de {maximo} llamadas a herramienta para esta "
    "pregunta. No puedes llamar a ninguna más. Responde ahora con lo que ya "
    "tengas, y si no es suficiente para afirmar nada con fundamento, dilo: "
    'fuente="ninguna" y explica en motivo_sin_dato qué te faltó.'
)

MENSAJE_DESAJUSTE = (
    "GUARDARRAÍL: la cifra que afirmas no coincide con la que reportó la "
    "compañía en XBRL.\n"
    "  afirmada : {afirmada:,.0f} {unidad}\n"
    "  en XBRL  : {xbrl:,.0f} {unidad_xbrl} ({ticker} FY{ejercicio} · {concepto})\n"
    "  tolerancia: {tolerancia}\n"
    "Vuelve a consultar get_xbrl_fact y corrige la respuesta. Si crees que el "
    "concepto consultado no es el que pide la pregunta, dilo explícitamente en "
    "lugar de ajustar el número."
)


class LimitadorLlamadas:
    """Corta la invocación al superar el presupuesto de llamadas."""

    def __init__(self, max_llamadas: int = 8) -> None:
        """Fija el presupuesto.

        Raises:
            NotImplementedError: Fase 4.
        """
        raise NotImplementedError("Fase 4 · Piettro: limitador de llamadas")

    def procesar(self, traza: Traza) -> str | None:
        """El mensaje a inyectar si se superó el límite, o `None`.

        Raises:
            NotImplementedError: Fase 4.
        """
        raise NotImplementedError("Fase 4 · Piettro: limitador de llamadas")


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

        Raises:
            NotImplementedError: Fase 4.
        """
        raise NotImplementedError("Fase 4 · Piettro: guardarraíl XBRL")

    def verificar(self, respuesta: RespuestaFinanciera) -> str | None:
        """El mensaje de desajuste, o `None` si la cifra cuadra o no aplica.

        Devuelve `None` cuando no hay cifra que contrastar, cuando la respuesta
        declara `fuente="ninguna"` —que es la respuesta correcta a un hueco— o
        cuando la cifra cuadra dentro de la tolerancia.

        Raises:
            NotImplementedError: Fase 4.
        """
        raise NotImplementedError("Fase 4 · Piettro: guardarraíl XBRL")


def construir_middleware(max_llamadas: int, xbrl: RepositorioXbrl) -> list[object]:
    """La cadena de middleware para `create_agent`.

    Raises:
        NotImplementedError: Fase 4.
    """
    raise NotImplementedError("Fase 4 · Piettro: cadena de middleware")
