"""Decorador que reescribe la consulta con el LLM. FASE 3 — Alonso.

STUB. Las firmas y el contrato están fijados; el cuerpo es de la fase 3.

P2: Decorator, igual que el filtro. Reescribe la consulta antes de pasarla al
recuperador envuelto: la pregunta del usuario llega en español y en lenguaje de
persona, y el corpus está en inglés y en lenguaje de abogado. «¿Qué riesgos de
IA añadió Microsoft?» recupera peor que «risks related to the development,
deployment and use of artificial intelligence systems».

**Esta mejora CUESTA.** Añade una llamada al modelo por búsqueda, y eso entra en
la columna de coste y en la de latencia de la tabla del informe. Es el ejemplo
de libro de un arreglo razonable que puede no compensar: medirlo y contarlo, aun
si no compensa, es la sección más valiosa de la presentación.

La reescritura se cachea por consulta: reejecutar el golden set no puede costar
dinero dos veces.
"""

from __future__ import annotations

from agente_10k.dominio.modelos import Filtros, Fragmento, UsoTokens
from agente_10k.dominio.protocolos import ProveedorLLM, Recuperador


class ConReescritura:
    """Envuelve un recuperador y reescribe la consulta antes de buscar."""

    def __init__(
        self,
        interno: Recuperador,
        proveedor: ProveedorLLM,
        cachear: bool = True,
    ) -> None:
        """Envuelve `interno` con una reescritura previa de la consulta.

        Args:
            interno: El recuperador envuelto.
            proveedor: Quien reescribe. En los tests, un `ProveedorFake`.
            cachear: Si se guarda la reescritura de cada consulta en disco.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: reescritura de consulta")

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación."""
        return "reescritura+?"

    def reescribir(self, consulta: str) -> str:
        """La consulta reescrita para el corpus: en inglés y con su jerga.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: reescritura de consulta")

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` mejores para la consulta reescrita.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: recuperación con reescritura")

    def uso_acumulado(self) -> UsoTokens:
        """Tokens y coste que ha añadido la reescritura.

        Va a la columna de coste de la tabla de ablación: sin esto, la fila de
        la reescritura parecería gratis.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: contabilidad de la reescritura")
