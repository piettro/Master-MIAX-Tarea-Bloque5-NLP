"""Reordena los candidatos del recuperador con un cross-encoder.

El cross-encoder ve la consulta y el pasaje juntos, no dos vectores calculados
por separado, así que discrimina mucho mejor arriba del todo. Lo que no hace es
recuperar: solo puede reordenar lo que le den, y si se equivoca, hunde un
pasaje que el recuperador ya tenía en el top-10.

Por eso hay dos modos. `fusionar=False` ordena por la puntuación del
cross-encoder y punto: sube el recall@1 y puede bajar el recall@10.
`fusionar=True` mezcla el orden del recuperador y el del cross-encoder con RRF
—el mismo que usa el híbrido—, y así el cross-encoder decide arriba sin poder
tirar a nadie fuera de la lista.
"""

from __future__ import annotations

from functools import lru_cache

from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.dominio.protocolos import Recuperador

MODELO_POR_DEFECTO = "cross-encoder/ms-marco-MiniLM-L6-v2"
PROFUNDIDAD_POR_DEFECTO = 20
# La constante de RRF, la misma que el híbrido: amortigua los puestos de abajo.
K_RRF = 60


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
        fusionar: bool = False,
    ) -> None:
        """Envuelve a `base`; el cross-encoder se carga al primer uso."""
        self._base = base
        self._modelo = modelo
        self._profundidad = profundidad
        self._fusionar = fusionar

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación."""
        sufijo = "reordenacion-rrf" if self._fusionar else "reordenacion"
        return f"{self._base.nombre}+{sufijo}"

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
        if not self._fusionar:
            return [f.con_puntuacion(float(p)) for f, p in ordenados[:k]]

        # RRF entre los dos órdenes: el del recuperador y el del cross-encoder.
        puesto_base = {f.chunk_id: i for i, f in enumerate(candidatos, 1)}
        puesto_ce = {f.chunk_id: i for i, (f, _) in enumerate(ordenados, 1)}
        fusionados = sorted(
            candidatos,
            key=lambda f: (
                1 / (K_RRF + puesto_base[f.chunk_id])
                + 1 / (K_RRF + puesto_ce[f.chunk_id])
            ),
            reverse=True,
        )
        return [
            f.con_puntuacion(
                1 / (K_RRF + puesto_base[f.chunk_id])
                + 1 / (K_RRF + puesto_ce[f.chunk_id])
            )
            for f in fusionados[:k]
        ]
