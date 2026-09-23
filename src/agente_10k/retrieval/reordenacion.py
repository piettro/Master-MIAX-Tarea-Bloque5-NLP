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
        # Los puestos van por POSICIÓN, no por `chunk_id`: si el recuperador
        # devolviera el mismo fragmento dos veces, un diccionario por id se
        # comería una de las dos y el orden saldría mal.
        orden = sorted(
            range(len(candidatos)),
            key=lambda i: float(puntuaciones[i]),
            reverse=True,
        )
        if not self._fusionar:
            return [
                candidatos[i].con_puntuacion(float(puntuaciones[i])) for i in orden[:k]
            ]

        # RRF entre los dos órdenes: el del recuperador y el del cross-encoder.
        puesto_ce = {i: puesto for puesto, i in enumerate(orden, 1)}
        rrf = {
            i: 1 / (K_RRF + i + 1) + 1 / (K_RRF + puesto_ce[i])
            for i in range(len(candidatos))
        }
        fusionados = sorted(rrf, key=lambda i: rrf[i], reverse=True)
        return [candidatos[i].con_puntuacion(rrf[i]) for i in fusionados[:k]]
