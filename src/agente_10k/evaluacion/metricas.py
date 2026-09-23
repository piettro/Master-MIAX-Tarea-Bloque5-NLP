"""Agregación de resultados en las columnas de la tabla. FASE 5 — Raúl.

La métrica de retrieval se mide contra el ANCLA DE TEXTO, no contra el
`chunk_id`. Un fragmento cuenta como acierto si CONTIENE el ancla literal. Si se
midiera por `chunk_id`, el grupo que mejorase el troceado saldría penalizado por
haberlo mejorado, porque en cuanto se re-trocea el corpus todos los
identificadores son otros.

`medir_recall` añade la comprobación de documento que hace `miax_s2.acierta`
del profesor: un fragmento del ejercicio equivocado NO cuenta aunque contenga el
ancla. Los 10-K repiten los factores de riesgo palabra por palabra de un año
para otro; sin esa comprobación, recuperar el FY2024 puntuaría como si se
hubiera encontrado el FY2025. Es la primitiva que debe usar también el runner
de ablación de la fase 3, para que las dos tablas midan lo mismo.

Qué cuenta como ACIERTO en la tabla principal: respuesta correcta Y camino
correcto (`evaluadores.es_respuesta_correcta` y el evaluador de trayectoria).
Acertar por el camino equivocado es fallo, y tiene su propia tasa aparte.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import fmean

from agente_10k.corpus.normalizacion import contiene
from agente_10k.dominio.modelos import (
    Filtros,
    Fragmento,
    Metricas,
    Pregunta,
    ResultadoPregunta,
)
from agente_10k.dominio.protocolos import Recuperador

KS_POR_DEFECTO: tuple[int, ...] = (1, 3, 5, 10)
"""Los `k` que se reportan. `recall@5` es la columna de la tabla principal."""


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


def del_documento(pregunta: Pregunta, fragmento: Fragmento) -> bool:
    """Si el fragmento es del emisor y ejercicio de la pregunta.

    Solo compara lo que la pregunta declara. La sección no se exige: el ancla ya
    fija el texto, y un mismo párrafo puede aparecer en el Item 7 y en el 7A.
    """
    return (pregunta.ticker is None or fragmento.ticker == pregunta.ticker) and (
        pregunta.fiscal_year is None or fragmento.fiscal_year == pregunta.fiscal_year
    )


def posicion_del_ancla(
    pregunta: Pregunta, recuperados: Sequence[Fragmento]
) -> int | None:
    """En qué puesto (desde 1) aparece el ancla en su documento, o `None`.

    `recall@5` dice sí o no; esto dice por cuánto. Un ancla en el puesto 7 y
    otra en el 1.400 fallan las dos, y no son el mismo problema.
    """
    ancla = pregunta.ancla_texto
    if not ancla:
        return None
    for puesto, fragmento in enumerate(recuperados, 1):
        if del_documento(pregunta, fragmento) and contiene(fragmento.texto, ancla):
            return puesto
    return None


def medir_recall(
    preguntas: Sequence[Pregunta],
    recuperador: Recuperador,
    ks: Sequence[int] = KS_POR_DEFECTO,
    usar_filtros: bool = False,
) -> tuple[dict[int, float], dict[str, int | None]]:
    """Recall@k de un recuperador sobre las preguntas con ancla.

    La consulta es el texto de la pregunta tal cual: si el sistema la reescribe,
    lo hace el decorador de reescritura que envuelve al recuperador, que es lo
    que se quiere medir.

    Args:
        preguntas: El golden set. Las que no traen ancla no miden retrieval y
            quedan fuera del denominador.
        recuperador: El pipeline de retrieval de la configuración a medir.
        ks: Los `k` a reportar.
        usar_filtros: Si se pasan a la búsqueda el emisor, el ejercicio y la
            sección que declara la pregunta. Es lo que haría un agente que
            rellena bien los parámetros de `search_filings`, y es la primera
            mejora de la tabla del profesor: sin filtros, con filtros.

    Returns:
        `(k -> recall, id -> puesto del ancla)`. El puesto es `None` si el ancla
        no apareció en los `max(ks)` primeros.
    """
    con_ancla = [p for p in preguntas if p.ancla_texto]
    if not con_ancla:
        return dict.fromkeys(ks, 0.0), {}
    profundidad = max(ks)
    puestos: dict[str, int | None] = {}
    for p in con_ancla:
        filtros = (
            Filtros(ticker=p.ticker, fiscal_year=p.fiscal_year, item=p.item_esperado)
            if usar_filtros
            else None
        )
        recuperados = recuperador.recuperar(p.pregunta, filtros, k=profundidad)
        puestos[p.id] = posicion_del_ancla(p, recuperados)
    recall = {
        k: sum(1 for puesto in puestos.values() if puesto and puesto <= k)
        / len(con_ancla)
        for k in ks
    }
    return recall, puestos


def _media(valores: Sequence[float]) -> float | None:
    return fmean(valores) if valores else None


def _proporcion(aciertos: Sequence[bool]) -> float:
    return sum(aciertos) / len(aciertos) if aciertos else 0.0


def agregar(
    resultados: Sequence[ResultadoPregunta],
    recall: dict[int, float] | None = None,
) -> Metricas:
    """Las métricas agregadas de una ejecución. Las columnas del informe.

    Incluye aciertos por familia, coste medio, latencia media, llamadas por
    pregunta, tasa de camino correcto, tasa de acierto por camino equivocado y
    la tasa de intervención y de recuperación del guardarraíl.

    Coste, latencia y llamadas se promedian sobre las preguntas que llegaron a
    producir traza: una que lanzó excepción no tiene coste que medir, y ya
    cuenta como fallo en los aciertos. El coste medio es `None` si el proveedor
    no lo reportó en ninguna: mejor una celda vacía que un cero falso.

    Args:
        resultados: Las preguntas ya evaluadas.
        recall: El recall@k medido aparte con `medir_recall`, si se midió.
    """
    trazas = [r.traza for r in resultados if r.traza is not None]
    costes = [t.uso.coste_usd for t in trazas if t.uso.coste_usd is not None]
    caminos = [
        r.estado_trayectoria for r in resultados if r.estado_trayectoria != "no_aplica"
    ]
    intervenidas = [
        r for r in resultados if r.traza and r.traza.intervenciones_guardarrail
    ]
    return Metricas(
        n_preguntas=len(resultados),
        aciertos_por_familia=aciertos_por_familia(resultados),
        recall_at_k=dict(recall or {}),
        coste_medio_usd=_media(costes),
        latencia_media_s=_media([t.latencia_s for t in trazas]) or 0.0,
        llamadas_por_pregunta=_media([float(t.n_llamadas) for t in trazas]) or 0.0,
        tasa_camino_correcto=_proporcion([c == "camino_correcto" for c in caminos]),
        tasa_acierto_por_camino_equivocado=_proporcion(
            [c == "camino_incorrecto_respuesta_correcta" for c in caminos]
        ),
        tasa_intervencion_guardarrail=_proporcion(
            [bool(t.intervenciones_guardarrail) for t in trazas]
        ),
        tasa_recuperacion_guardarrail=_proporcion(
            [bool(r.respuesta_correcta) for r in intervenidas]
        ),
        alucinaciones_sobre_hueco=sum(r.alucinacion_sobre_hueco for r in resultados),
    )


def aciertos_por_familia(
    resultados: Sequence[ResultadoPregunta],
) -> dict[str, float]:
    """Proporción de aciertos en cada familia, más la de hueco y el total.

    El hueco no es una familia del esquema —el validador oficial solo admite
    tres— pero sí una columna del informe: se deriva de `Pregunta.es_hueco` y se
    guarda en `ResultadoPregunta.es_hueco`. Una pregunta de hueco cuenta en su
    familia Y en la columna de hueco.

    Una pregunta que lanzó excepción cuenta como fallo. Una sin veredicto
    posible (`acierto=None`: ciega sin esquema) no entra en el denominador. Las
    familias sin preguntas evaluables no aparecen en el diccionario: la celda
    queda vacía en la tabla, no a cero.
    """
    grupos: dict[str, list[bool]] = {}
    for r in resultados:
        acierto = False if r.error else r.acierto
        if acierto is None:
            continue
        claves = [r.familia or "sin_familia", "total"]
        if r.es_hueco:
            claves.append("hueco")
        for clave in claves:
            grupos.setdefault(clave, []).append(acierto)
    return {clave: _proporcion(valores) for clave, valores in grupos.items()}
