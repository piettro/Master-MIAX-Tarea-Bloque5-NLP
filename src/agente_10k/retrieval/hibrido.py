"""Fusión de varios recuperadores por RRF. FASE 3 — Alonso.

STUB. Las firmas y el contrato están fijados; el cuerpo es de la fase 3.

**Reciprocal Rank Fusion, no suma de puntuaciones.** La similitud coseno del
denso vive en [-1, 1] y la puntuación BM25 no tiene cota superior ni escala
fija: sumarlas o promediarlas es comparar magnitudes que no son comparables, y
el resultado lo domina siempre el que tenga los números más grandes. RRF ignora
las puntuaciones y usa solo el PUESTO de cada documento en cada lista:

    RRF(d) = Σ_recuperadores 1 / (k + puesto(d))

El `k` de RRF amortigua cuánto pesa estar el primero frente a estar el tercero.
Va en configuración (`Settings.rrf_k`, por defecto 60, que es el valor del paper
original) y no fijo en el código, porque es un parámetro de la ablación.
"""

from __future__ import annotations

from collections.abc import Sequence

from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.dominio.protocolos import Recuperador


def fusionar_rrf(
    rankings: Sequence[Sequence[str]],
    k_rrf: int = 60,
    pesos: Sequence[float] | None = None,
) -> list[tuple[str, float]]:
    """Fusiona varias listas ordenadas de `chunk_id` por RRF.

    Args:
        rankings: Una lista ordenada de `chunk_id` por cada recuperador, de
            mejor a peor.
        k_rrf: La constante de amortiguación de RRF.
        pesos: Peso de cada recuperador. `None` los pondera por igual.

    Returns:
        Los `chunk_id` con su puntuación RRF, de mayor a menor. Es una función
        pura sobre rankings: se prueba con listas sintéticas, sin modelo, sin
        índice y sin red.

    Raises:
        NotImplementedError: Fase 3.
    """
    raise NotImplementedError("Fase 3 · Alonso: fusión RRF")


class RecuperadorHibrido:
    """Combina varios recuperadores. P1: estrategia que compone estrategias."""

    def __init__(
        self,
        recuperadores: Sequence[Recuperador],
        k_rrf: int = 60,
        pesos: Sequence[float] | None = None,
        factor_sobremuestreo: int = 4,
    ) -> None:
        """Combina recuperadores por RRF.

        Args:
            recuperadores: Los que se fusionan. Al menos dos.
            k_rrf: Constante de RRF.
            pesos: Peso de cada uno, o `None` para ponderarlos igual.
            factor_sobremuestreo: A cada recuperador se le piden
                `k * factor` candidatos antes de fusionar. Pedir exactamente
                `k` a cada uno desperdicia la fusión: los documentos que solo
                uno ve en el puesto 7 nunca llegan a sumar.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: recuperador híbrido")

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación."""
        return "hibrido"

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` fragmentos mejor puntuados tras la fusión.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: búsqueda híbrida")
