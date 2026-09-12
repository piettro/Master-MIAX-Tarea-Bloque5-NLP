"""BM25 sobre los mismos 1.749 fragmentos. FASE 3 — Alonso.

STUB. Las firmas y el contrato están fijados; el cuerpo es de la fase 3.

Por qué hace falta además del denso: la búsqueda densa falla justo donde más
duele en finanzas. Un ticker, un nombre propio o una cifra concreta no tienen
vecindario semántico —«60,922» no se «parece» a nada— y el léxico los encuentra
exactamente. Fusionarlos es lo que sube el recall sin romper lo que ya iba bien.

Lo que hay que decidir y DOCUMENTAR al implementarlo es el tokenizador. En texto
financiero los números y los guiones importan: un tokenizador que parta
«60,922» en «60» y «922», o que tire los guiones de «AI-related», destruye
exactamente la ventaja por la que se añade BM25.
"""

from __future__ import annotations

from collections.abc import Sequence

from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.dominio.protocolos import RepositorioFragmentos


def tokenizar(texto: str) -> list[str]:
    """Parte un texto en términos para BM25.

    Args:
        texto: El texto a tokenizar.

    Returns:
        Los términos, en minúsculas, conservando números completos con sus
        separadores de millar y las palabras con guión como una sola unidad.

    Raises:
        NotImplementedError: Fase 3.
    """
    raise NotImplementedError("Fase 3 · Alonso: tokenizador de BM25")


class RecuperadorLexico:
    """BM25 sobre los fragmentos del corpus. P1: otra estrategia intercambiable."""

    def __init__(
        self,
        fragmentos: RepositorioFragmentos,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        """Indexa los fragmentos con BM25.

        Args:
            fragmentos: El repositorio de fragmentos.
            k1: Saturación de frecuencia de término.
            b: Normalización por longitud del documento.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: índice BM25")

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación."""
        return "lexico"

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` fragmentos con mayor puntuación BM25.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: búsqueda BM25")

    def puntuaciones(self, consulta: str) -> Sequence[float]:
        """La puntuación BM25 de cada fragmento, en el orden del repositorio.

        La necesita el híbrido para fusionar sin volver a indexar.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: puntuaciones BM25")
