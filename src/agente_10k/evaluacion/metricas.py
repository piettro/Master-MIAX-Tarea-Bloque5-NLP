"""Agregación de resultados en las columnas del informe.

El recall se mide contra el ancla de texto, no contra el `chunk_id`, que cambia
en cuanto se re-trocea el corpus. Acierto = respuesta correcta Y camino correcto.
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

# `recall@5` es la columna de la tabla principal.
KS_POR_DEFECTO: tuple[int, ...] = (1, 3, 5, 10)


def acierta_en_k(recuperados: Sequence[Fragmento], ancla: str, k: int) -> bool:
    """Si alguno de los `k` primeros fragmentos contiene el ancla literal."""
    return any(contiene(f.texto, ancla) for f in recuperados[:k])


def recall_at_k(
    recuperaciones: Sequence[tuple[Sequence[Fragmento], str]],
    ks: Sequence[int] = (1, 3, 5, 10),
) -> dict[int, float]:
    """Recall@k para varios `k`, contra el ancla de texto.

    Las preguntas sin ancla quedan fuera del denominador.
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

    La sección no se exige: el ancla ya fija el texto.
    """
    return (pregunta.ticker is None or fragmento.ticker == pregunta.ticker) and (
        pregunta.fiscal_year is None or fragmento.fiscal_year == pregunta.fiscal_year
    )


def posicion_del_ancla(
    pregunta: Pregunta, recuperados: Sequence[Fragmento]
) -> int | None:
    """En qué puesto (desde 1) aparece el ancla en su documento, o `None`."""
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
    """Recall@k y puesto del ancla de cada pregunta, con el recuperador dado.

    `usar_filtros` pasa a la búsqueda el emisor, ejercicio y sección declarados.
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
    """Las métricas agregadas de una ejecución: las columnas del informe.

    Coste, latencia y llamadas se promedian solo sobre las preguntas con traza.
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

    Una pregunta sin veredicto posible (`acierto=None`) no entra en el denominador.
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
