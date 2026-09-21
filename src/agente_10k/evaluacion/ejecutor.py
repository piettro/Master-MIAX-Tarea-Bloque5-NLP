"""`evaluar(ruta_jsonl)`. CONTRATO C5. FASE 5 — Raúl.

El día 24 llegan diez preguntas que no ha visto nadie, se ejecutan en clase
contra el repositorio YA entregado y el resultado entra en la presentación.
Tres reglas que salen de ahí y que gobiernan este módulo:

1. **Los campos que no estén se degradan, no abortan.** Si las diez preguntas
   llegan con solo `id` y `pregunta`, `evaluar()` tiene que correr igual y
   marcar como `no_aplica` los evaluadores que no pueda aplicar.
2. **Una pregunta que lanza excepción se marca como fallo y la ejecución
   continúa.** Que la séptima rompa no puede impedir ver las otras nueve.
3. **Ninguna pregunta puede colgar la sesión.** Hay veinte minutos para diez
   preguntas: cada una tiene un tiempo máximo y, si lo agota, se marca como
   fallo y se pasa a la siguiente.
"""

from __future__ import annotations

import csv
import json
import subprocess
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as TiempoAgotado
from pathlib import Path

from agente_10k.config import RAIZ_REPO, Settings, settings
from agente_10k.corpus import Corpus, cargar_corpus
from agente_10k.corpus.normalizacion import describir as describir_normalizacion
from agente_10k.dominio.modelos import (
    InformeEvaluacion,
    Pregunta,
    RespuestaFinanciera,
    ResultadoPregunta,
    Traza,
)
from agente_10k.dominio.tolerancia import TOLERANCIA
from agente_10k.evaluacion.evaluadores import (
    EvaluadorCifra,
    EvaluadorCita,
    EvaluadorTrayectoria,
    es_respuesta_correcta,
)
from agente_10k.evaluacion.metricas import agregar, medir_recall
from agente_10k.evaluacion.sistemas import Sistema, cargar_entorno, sistema_final

TIEMPO_MAXIMO_S = 180.0
"""Segundos por pregunta antes de darla por fallida.

Una pregunta normal tarda entre 3 y 30 segundos. Tres minutos solo se agotan si
el agente entró en bucle o el proveedor no contesta, y en los dos casos esperar
más no la va a arreglar y sí se come el tiempo de las otras nueve.
"""

Progreso = Callable[[int, int, ResultadoPregunta], None]
"""`(n, total, resultado)`: lo que el CLI imprime tras cada pregunta."""


def leer_preguntas(ruta: str | Path) -> list[Pregunta]:
    """Lee un JSONL de preguntas tolerando todo lo que falte menos el texto.

    Solo `id` y `pregunta` son obligatorios. El resto se rellena con `None` y
    los evaluadores que necesiten un campo ausente devolverán `no_aplica`.

    Args:
        ruta: El fichero JSONL.

    Returns:
        Las preguntas leídas, en el orden del fichero.

    Raises:
        FileNotFoundError: Si el fichero no existe.
        ValueError: Si una línea no es JSON válido o le falta `pregunta`. Se
            señala con el número de línea: un fichero mal formado el día 24 se
            arregla en veinte segundos si el error dice dónde.
    """
    camino = Path(ruta)
    if not camino.is_file():
        raise FileNotFoundError(f"No existe el fichero de preguntas: {camino}")

    preguntas: list[Pregunta] = []
    for numero, linea in enumerate(camino.read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        try:
            cruda = json.loads(linea)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{camino}:{numero} no es JSON válido: {exc}") from exc
        if "pregunta" not in cruda:
            raise ValueError(f"{camino}:{numero} no tiene campo 'pregunta'.")
        cruda.setdefault("id", f"{camino.stem}-{numero:03d}")
        cruda.setdefault("familia", "extractiva")
        preguntas.append(Pregunta.model_validate(cruda))
    return preguntas


def etiqueta_por_defecto(ruta: str | Path) -> str:
    """`ciegas` si el fichero es el de las preguntas ciegas; si no, `final`.

    El día 24 se ejecuta `evaluar("resultados/ciegas/preguntas.jsonl")` o
    `evaluar("holdout.jsonl")` sin más argumentos, y el resultado no puede ir a
    pisar `resultados/final/`, que es la mitad de la tabla del informe.
    """
    texto = Path(ruta).as_posix().lower()
    return "ciegas" if "ciega" in texto or "holdout" in texto else "final"


class _Evaluadores:
    """Los tres evaluadores montados sobre el corpus, o degradados sin él."""

    def __init__(self, corpus: Corpus | None) -> None:
        self.cita = (
            EvaluadorCita(corpus.fragmentos, corpus.secciones) if corpus else None
        )
        self.cifra = EvaluadorCifra(corpus.xbrl) if corpus else None
        self.trayectoria = EvaluadorTrayectoria()

    def aplicar(
        self, pregunta: Pregunta, respuesta: RespuestaFinanciera, traza: Traza
    ) -> ResultadoPregunta:
        """La pregunta evaluada por los tres, con el acierto final calculado."""
        cita = self.cita.evaluar(pregunta, respuesta) if self.cita else None
        cifra = self.cifra.evaluar(pregunta, respuesta) if self.cifra else None
        trayectoria = self.trayectoria.evaluar(pregunta, traza)
        correcta = es_respuesta_correcta(pregunta.familia, cita, cifra)
        acierto = (
            None if correcta is None else correcta and trayectoria.veredicto != "fallo"
        )
        return ResultadoPregunta(
            pregunta_id=pregunta.id,
            familia=pregunta.familia,
            es_hueco=pregunta.es_hueco,
            respuesta_correcta=correcta,
            acierto=acierto,
            respuesta=respuesta,
            traza=traza,
            cita=cita,
            cifra=cifra,
            trayectoria=trayectoria,
            estado_trayectoria=self.trayectoria.clasificar(
                pregunta, traza, respuesta_correcta=bool(correcta)
            ),
            alucinacion_sobre_hueco=bool(
                self.cifra
                and self.cifra.es_alucinacion_sobre_hueco(pregunta, respuesta)
            ),
        )


def _sin_sistema(motivo: str) -> Sistema:
    """Un sistema que falla siempre con `motivo`.

    Si el agente no se puede construir —falta la clave, falta una pieza de la
    fase 4—, cada pregunta se marca como fallo con ese motivo en lugar de que
    `evaluar()` explote antes de empezar sin dejar nada escrito.
    """

    def responder(_: str) -> tuple[RespuestaFinanciera, Traza]:
        raise RuntimeError(motivo)

    return responder


def _ejecutar_con_limite(
    sistema: Sistema, pregunta: str, tiempo_maximo_s: float
) -> tuple[RespuestaFinanciera, Traza]:
    """Llama al sistema y deja de esperarle si agota el tiempo.

    El hilo no se puede matar desde fuera; se abandona. Si el agente estaba en
    bucle seguirá gastando hasta su propio límite, pero la evaluación sigue.
    """
    ejecutor = ThreadPoolExecutor(max_workers=1)
    futuro = ejecutor.submit(sistema, pregunta)
    try:
        return futuro.result(timeout=tiempo_maximo_s)
    except TiempoAgotado as exc:
        raise TimeoutError(
            f"sin respuesta en {tiempo_maximo_s:.0f} s: se abandona la pregunta"
        ) from exc
    finally:
        ejecutor.shutdown(wait=False, cancel_futures=True)


def _medir_recall(
    preguntas: Sequence[Pregunta], corpus: Corpus | None, cfg: Settings
) -> tuple[dict[int, float], dict[str, int | None], str | None]:
    """El recall@k del pipeline de retrieval de la configuración.

    Degrada a vacío con un aviso si no se puede construir el recuperador (sin
    corpus, sin modelo de embeddings, mejora de la fase 3 aún sin hacer): el
    recall es una columna, no una condición para evaluar las respuestas.
    """
    if corpus is None or not any(p.ancla_texto for p in preguntas):
        return {}, {}, None
    try:
        from agente_10k.retrieval.fabrica import construir_recuperador

        recuperador = construir_recuperador(corpus, cfg)
        recall, puestos = medir_recall(
            preguntas, recuperador, usar_filtros=cfg.filtro_metadatos
        )
    except Exception as exc:  # degradar, nunca abortar
        return {}, {}, f"recall@k no medido: {type(exc).__name__}: {exc}"
    return recall, puestos, None


def _commit() -> str | None:
    """El commit actual, con `+cambios` si hay ficheros sin commitear."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ_REPO, text=True
        ).strip()
        sucio = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=RAIZ_REPO,
            text=True,
        ).strip()
    except (subprocess.SubprocessError, OSError):
        return None
    return f"{commit}+cambios" if sucio else commit


def evaluar(
    ruta_jsonl: str | Path,
    etiqueta: str | None = None,
    escribir: bool = True,
    *,
    sistema: Sistema | None = None,
    config: Settings | None = None,
    medir_retrieval: bool = True,
    tiempo_maximo_s: float = TIEMPO_MAXIMO_S,
    progreso: Progreso | None = None,
) -> InformeEvaluacion:
    """Ejecuta el sistema sobre un JSONL de preguntas y lo evalúa. CONTRATO C5.

    Para cada pregunta: llama al sistema, aplica los tres evaluadores, agrega y
    escribe el detalle y el resumen a `resultados/<etiqueta>/`.

    Args:
        ruta_jsonl: El fichero de preguntas. Solo `id` y `pregunta` son
            obligatorios.
        etiqueta: Subcarpeta de `resultados/`. Por defecto `final`, o `ciegas`
            si la ruta es la de las preguntas ciegas.
        escribir: Si se vuelca el resultado a disco.
        sistema: Qué se evalúa. Por defecto, nuestro agente; el baseline es
            `sistemas.SistemaBaseline()`.
        config: La configuración; por defecto, la del proceso.
        medir_retrieval: Si se mide el recall@k del pipeline de retrieval.
        tiempo_maximo_s: Límite por pregunta. Ver `TIEMPO_MAXIMO_S`.
        progreso: Se llama tras cada pregunta, para ir viendo el avance.

    Returns:
        El informe completo, con detalle por pregunta y métricas agregadas.
    """
    cargar_entorno()
    cfg = config or settings()
    preguntas = leer_preguntas(ruta_jsonl)
    etiqueta = etiqueta or etiqueta_por_defecto(ruta_jsonl)

    avisos: list[str] = []
    corpus: Corpus | None
    try:
        corpus = cargar_corpus(cfg)
        avisos += corpus.avisos()
    except Exception as exc:  # sin corpus, los evaluadores degradan
        corpus = None
        avisos.append(f"corpus no cargado ({exc}): cita y cifra quedan no_aplica")

    if sistema is None:
        try:
            sistema = sistema_final(cfg)
        except Exception as exc:  # cada pregunta lo registrará
            sistema = _sin_sistema(f"no se pudo construir el agente: {exc}")
    evaluadores = _Evaluadores(corpus)

    resultados: list[ResultadoPregunta] = []
    for n, pregunta in enumerate(preguntas, 1):
        try:
            respuesta, traza = _ejecutar_con_limite(
                sistema, pregunta.pregunta, tiempo_maximo_s
            )
            resultado = evaluadores.aplicar(pregunta, respuesta, traza)
        except Exception as exc:  # regla 2 del módulo
            resultado = ResultadoPregunta(
                pregunta_id=pregunta.id,
                familia=pregunta.familia,
                es_hueco=pregunta.es_hueco,
                acierto=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        resultados.append(resultado)
        if progreso:
            progreso(n, len(preguntas), resultado)

    recall, puestos, aviso_recall = (
        _medir_recall(preguntas, corpus, cfg) if medir_retrieval else ({}, {}, None)
    )
    if aviso_recall:
        avisos.append(aviso_recall)

    configuracion: dict[str, object] = {
        **getattr(sistema, "descripcion", {"sistema": "agente final (fase 4)"}),
        "retrieval": cfg.resumen_retrieval(),
        "max_llamadas_herramienta": cfg.max_llamadas_herramienta,
        "tolerancia_cifra": TOLERANCIA.describir(),
        "normalizacion_cita": describir_normalizacion(),
        "tiempo_maximo_s": tiempo_maximo_s,
        "puesto_del_ancla": puestos,
        "avisos": avisos,
    }
    trazas = [r.traza for r in resultados if r.traza]
    informe = InformeEvaluacion(
        etiqueta=etiqueta,
        ruta_preguntas=str(ruta_jsonl),
        modelo=trazas[0].modelo if trazas else cfg.llm_model,
        proveedor=trazas[0].proveedor if trazas else cfg.llm_provider,
        commit=_commit(),
        configuracion=configuracion,
        resultados=resultados,
        metricas=agregar(resultados, recall),
    )
    if escribir:
        guardar(informe, cfg.dir_resultados / etiqueta)
    return informe


def fila_plana(resultado: ResultadoPregunta) -> dict[str, object]:
    """Una pregunta evaluada en una fila legible: la del CSV de detalle."""
    r, t = resultado.respuesta, resultado.traza
    return {
        "id": resultado.pregunta_id,
        "familia": resultado.familia,
        "hueco": resultado.es_hueco,
        "acierto": resultado.acierto,
        "respuesta_correcta": resultado.respuesta_correcta,
        "cita": resultado.cita.veredicto if resultado.cita else None,
        "cifra": resultado.cifra.veredicto if resultado.cifra else None,
        "trayectoria": resultado.trayectoria.veredicto
        if resultado.trayectoria
        else None,
        "estado_trayectoria": resultado.estado_trayectoria,
        "alucinacion_sobre_hueco": resultado.alucinacion_sobre_hueco,
        "herramientas": " > ".join(t.trayectoria) if t else "",
        "llamadas": t.n_llamadas if t else None,
        "latencia_s": round(t.latencia_s, 2) if t else None,
        "coste_usd": t.uso.coste_usd if t else None,
        "tokens": t.uso.tokens_total if t else None,
        "guardarrail": t.intervenciones_guardarrail if t else None,
        "fuente": r.fuente if r else None,
        "cifra_dada": r.cifra if r else None,
        "respuesta": r.respuesta if r else None,
        "motivo_cita": resultado.cita.motivo if resultado.cita else None,
        "motivo_cifra": resultado.cifra.motivo if resultado.cifra else None,
        "motivo_trayectoria": resultado.trayectoria.motivo
        if resultado.trayectoria
        else None,
        "error": resultado.error,
    }


def guardar(informe: InformeEvaluacion, destino: Path) -> None:
    """Vuelca el informe a `resultados/<etiqueta>/`.

    * `informe.json` — el `InformeEvaluacion` entero. Es lo que lee
      `make informe` para regenerar las tablas: ninguna cifra se copia a mano.
    * `meta.json` — fecha, modelo, commit y configuración, para saber qué se
      ejecutó sin abrir el informe entero.
    * `detalle.csv` — una fila por pregunta, legible en una hoja de cálculo.
    * `resumen.md` — las tablas de este sistema.
    """
    from agente_10k.evaluacion.informe import tablas_de_sistema

    destino.mkdir(parents=True, exist_ok=True)
    (destino / "informe.json").write_text(
        informe.model_dump_json(indent=2), encoding="utf-8"
    )
    meta = informe.model_dump(
        mode="json",
        include={
            "etiqueta",
            "fecha",
            "ruta_preguntas",
            "modelo",
            "proveedor",
            "commit",
            "configuracion",
            "metricas",
        },
    )
    (destino / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    filas = [fila_plana(r) for r in informe.resultados]
    if filas:
        with (destino / "detalle.csv").open("w", encoding="utf-8", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=list(filas[0]))
            escritor.writeheader()
            escritor.writerows(filas)
    (destino / "resumen.md").write_text(tablas_de_sistema(informe), encoding="utf-8")
