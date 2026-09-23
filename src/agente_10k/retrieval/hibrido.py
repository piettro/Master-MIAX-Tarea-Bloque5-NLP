"""Fusión de varios recuperadores por RRF. FASE 3 — Alonso.

**Reciprocal Rank Fusion, no suma de puntuaciones.** La similitud coseno del
denso vive en [-1, 1] y la puntuación BM25 no tiene cota superior ni escala
fija: sumarlas o promediarlas es comparar magnitudes que no son comparables, y
el resultado lo domina siempre el que tenga los números más grandes. RRF ignora
las puntuaciones y usa solo el PUESTO de cada documento en cada lista:

    RRF(d) = Σ_recuperadores  peso · 1 / (k + puesto(d))

`puesto(d)` empieza en 1 (el primero de la lista), como en el paper original.
El `k` de RRF amortigua cuánto pesa estar el primero frente a estar el tercero:
con `k` grande las diferencias entre puestos se aplanan; con `k` pequeño el
primer puesto manda. Va en configuración (`Settings.rrf_k`, por defecto 60, el
valor del paper) y no fijo en el código, porque es un parámetro de la ablación.
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
        PURA sobre rankings: no toca el modelo, el índice ni la red, y por eso se
        prueba con listas sintéticas. El desempate a igualdad de puntuación es
        por `chunk_id`, para que el resultado sea determinista entre ejecuciones.
    """
    if pesos is None:
        # Sin pesos declarados, todos los recuperadores valen lo mismo. Es el
        # caso por defecto: denso y BM25 aportan por igual y que gane uno u otro
        # lo decide el consenso de puestos, no un peso puesto a mano.
        pesos = [1.0] * len(rankings)

    acumulado: dict[str, float] = {}
    for ranking, peso in zip(rankings, pesos, strict=False):
        for indice, chunk_id in enumerate(ranking):
            puesto = indice + 1  # el paper cuenta desde 1, no desde 0
            acumulado[chunk_id] = acumulado.get(chunk_id, 0.0) + peso / (k_rrf + puesto)

    # Orden estable y reproducible: primero por puntuación (desc), y a empate por
    # chunk_id (asc). Sin el segundo criterio, dos documentos empatados podrían
    # salir en orden distinto entre ejecuciones y la tabla dejaría de ser fija.
    return sorted(acumulado.items(), key=lambda par: (-par[1], par[0]))


class RecuperadorHibrido:
    """Combina varios recuperadores. P1: estrategia que compone estrategias.

    Es a la vez un `Recuperador` y una composición de recuperadores: por fuera se
    usa igual que el denso, por dentro pregunta a cada uno y funde sus rankings.
    """

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
            factor_sobremuestreo: A cada recuperador se le piden `k * factor`
                candidatos antes de fusionar. Pedir exactamente `k` a cada uno
                desperdicia la fusión: un documento que el denso ve en el puesto
                7 y BM25 en el puesto 6 nunca llegaría a sumar sus dos puestos si
                a cada uno solo le pedimos 5. Sobre-muestrear es lo que deja que
                el consenso rescate lo que uno solo ve tarde.
        """
        minimo = 2  # con uno solo no hay nada que fusionar
        if len(recuperadores) < minimo:
            raise ValueError(
                "El híbrido necesita al menos dos recuperadores; con uno solo "
                "no hay nada que fusionar."
            )
        self._recuperadores = tuple(recuperadores)
        self._k_rrf = k_rrf
        self._pesos = pesos
        self._factor = factor_sobremuestreo

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

        Pide a cada recuperador `k * factor` candidatos con LOS MISMOS filtros
        —así el filtro por metadatos, si está, se aplica en cada rama y no
        después—, funde los rankings por RRF y devuelve los `k` primeros. La
        puntuación que se rellena es la RRF, no la coseno ni la BM25: es la única
        que tiene sentido comparar entre fragmentos que vinieron por vías
        distintas.
        """
        candidatos = max(k * self._factor, k)

        rankings: list[list[str]] = []
        # Guardamos el objeto Fragmento de cada chunk_id visto para poder
        # reconstruir la salida sin volver a preguntar al repositorio: el híbrido
        # no tiene acceso a él, solo a lo que devuelven sus recuperadores.
        por_id: dict[str, Fragmento] = {}
        for recuperador in self._recuperadores:
            encontrados = recuperador.recuperar(consulta, filtros, candidatos)
            rankings.append([f.chunk_id for f in encontrados])
            for fragmento in encontrados:
                por_id.setdefault(fragmento.chunk_id, fragmento)

        fusionados = fusionar_rrf(rankings, k_rrf=self._k_rrf, pesos=self._pesos)
        return [
            por_id[chunk_id].con_puntuacion(round(puntuacion, 6))
            for chunk_id, puntuacion in fusionados[:k]
        ]
