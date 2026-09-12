"""Decorador que filtra por metadatos ANTES de buscar. FASE 3 — Alonso.

STUB. Las firmas y el contrato están fijados; el cuerpo es de la fase 3.

P2: Decorator. Recibe un `Recuperador` y devuelve un `Recuperador`, de modo que
la mejora se activa y se desactiva por configuración y la fila «+ filtro de
metadatos» de la tabla de ablación sale del mismo runner que las demás.

**Antes, no después.** El recuperador que se entrega busca sobre el corpus
entero y descarta luego lo que no encaja: con `k=5` y un filtro por MSFT FY2025,
si los cinco primeros son de otras compañías, la llamada devuelve cero
resultados habiendo gastado el presupuesto entero. Filtrar antes significa
restringir el espacio de búsqueda a los fragmentos candidatos y que los cinco
que vuelven sean cinco útiles.
"""

from __future__ import annotations

from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.dominio.protocolos import Recuperador, RepositorioFragmentos


class ConFiltroMetadatos:
    """Envuelve un recuperador y le restringe el espacio de búsqueda."""

    def __init__(
        self,
        interno: Recuperador,
        fragmentos: RepositorioFragmentos,
    ) -> None:
        """Envuelve `interno` para que filtre antes de buscar.

        Args:
            interno: El recuperador envuelto.
            fragmentos: El repositorio, necesario para saber qué subconjunto
                cumple los filtros sin recorrer el índice entero.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: filtro de metadatos previo")

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación."""
        return "filtro+?"

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` mejores dentro del subconjunto que cumple los filtros.

        Raises:
            NotImplementedError: Fase 3.
        """
        raise NotImplementedError("Fase 3 · Alonso: recuperación filtrada")
