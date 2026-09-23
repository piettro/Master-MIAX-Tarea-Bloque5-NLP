"""Reordena los candidatos del recuperador con un cross-encoder."""

from __future__ import annotations

from functools import lru_cache

from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.dominio.protocolos import Recuperador

MODELO_POR_DEFECTO = "cross-encoder/ms-marco-MiniLM-L6-v2"
PROFUNDIDAD_POR_DEFECTO = 20


@lru_cache(maxsize=2)
def _cross_encoder(nombre: str) -> object:
    # Carga perezosa: importar el paquete no debe bajar 90 MB de modelo.
    from sentence_transformers import CrossEncoder

    return CrossEncoder(nombre, max_length=512)


class ConReordenacion:
    """Recupera `profundidad` candidatos y los reordena por relevancia."""

    def __init__(
        self,
        base: Recuperador,
        modelo: str = MODELO_POR_DEFECTO,
        profundidad: int = PROFUNDIDAD_POR_DEFECTO,
    ) -> None:
        """Envuelve a `base`; el cross-encoder se carga al primer uso."""
        self._base = base
        self._modelo = modelo
        self._profundidad = profundidad

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación."""
        return f"{self._base.nombre}+reordenacion"

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` mejores tras reordenar los candidatos del recuperador base."""
        profundidad = max(k, self._profundidad)
        candidatos = self._base.recuperar(consulta, filtros, k=profundidad)
        if len(candidatos) <= 1:
            return candidatos[:k]
        pares = [(consulta, f.texto) for f in candidatos]
        modelo = _cross_encoder(self._modelo)
        puntuaciones = modelo.predict(pares)  # type: ignore[attr-defined]
        ordenados = sorted(
            zip(candidatos, puntuaciones, strict=True),
            key=lambda par: float(par[1]),
            reverse=True,
        )
        return [f.con_puntuacion(float(p)) for f, p in ordenados[:k]]
