"""Agregación de resultados en las columnas de la tabla. FASE 5 — Raúl.

STUB. Las firmas y el contrato están fijados; el cuerpo es de la fase 5.

`recall_at_k` sí está implementado: es una función pura sobre listas de
fragmentos y la necesita el runner de ablación de la fase 3, que va antes.

La métrica de retrieval se mide contra el ANCLA DE TEXTO, no contra el
`chunk_id`. Un fragmento cuenta como acierto si CONTIENE el ancla literal. Si se
midiera por `chunk_id`, el grupo que mejorase el troceado saldría penalizado por
haberlo mejorado, porque en cuanto se re-trocea el corpus todos los
identificadores son otros.
"""

from __future__ import annotations

from collections.abc import Sequence

from agente_10k.corpus.normalizacion import contiene
from agente_10k.dominio.modelos import Fragmento, Metricas, ResultadoPregunta


def acierta_en_k(recuperados: Sequence[Fragmento], ancla: str, k: int) -> bool:
    """Si alguno de los `k` primeros fragmentos contiene el ancla literal."""
    return any(contiene(f.texto, ancla) for f in recuperados[:k])


def recall_at_k(
    recuperaciones: Sequence[tuple[Sequence[Fragmento], str]],
    ks: Sequence[int] = (1, 3, 5, 10),
) -> dict[int, float]:
    """Recall@k para varios `k`, contra el ancla de texto.

    Args:
        recuperaciones: Por cada pregunta, los fragmentos recuperados en orden
            y el ancla literal que debía aparecer.
        ks: Los valores de `k` a reportar.

    Returns:
        `k -> proporción de preguntas cuyo ancla apareció en el top-k`. Las
        preguntas sin ancla se excluyen del denominador: no miden retrieval y
        meterlas solo diluiría la métrica.
    """
    utiles = [(frs, ancla) for frs, ancla in recuperaciones if ancla]
    if not utiles:
        return dict.fromkeys(ks, 0.0)
    return {
        k: sum(acierta_en_k(frs, ancla, k) for frs, ancla in utiles) / len(utiles)
        for k in ks
    }


def agregar(resultados: Sequence[ResultadoPregunta]) -> Metricas:
    """Las métricas agregadas de una ejecución. Las columnas del informe.

    Incluye aciertos por familia, coste medio, latencia media, llamadas por
    pregunta, tasa de camino correcto, tasa de acierto por camino equivocado y
    la tasa de intervención y de recuperación del guardarraíl.

    Raises:
        NotImplementedError: Fase 5.
    """
    raise NotImplementedError("Fase 5 · Raúl: agregación de métricas")


def aciertos_por_familia(
    resultados: Sequence[ResultadoPregunta],
) -> dict[str, float]:
    """Proporción de aciertos en cada familia, más la de hueco por separado.

    El hueco no es una familia del esquema —el validador oficial solo admite
    tres— pero sí una columna del informe: se deriva de `Pregunta.es_hueco`.

    Raises:
        NotImplementedError: Fase 5.
    """
    raise NotImplementedError("Fase 5 · Raúl: aciertos por familia")
