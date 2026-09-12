"""`evaluar(ruta_jsonl)`. CONTRATO C5. FASE 5 — Raúl.

STUB salvo `leer_preguntas`, que sí está implementado porque es la pieza de la
que depende el fallo más probable de toda la práctica.

El día 24 llegan diez preguntas que no ha visto nadie, se ejecutan en clase
contra el repositorio YA entregado y el resultado entra en la presentación. Dos
reglas que salen de ahí y que gobiernan este módulo:

1. **Los campos que no estén se degradan, no abortan.** Si las diez preguntas
   llegan con solo `id` y `pregunta`, `evaluar()` tiene que correr igual y
   marcar como `no_aplica` los evaluadores que no pueda aplicar.
2. **Una pregunta que lanza excepción se marca como fallo y la ejecución
   continúa.** Que la séptima rompa no puede impedir ver las otras nueve.
"""

from __future__ import annotations

import json
from pathlib import Path

from agente_10k.dominio.modelos import InformeEvaluacion, Pregunta


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


def evaluar(
    ruta_jsonl: str | Path,
    etiqueta: str = "final",
    escribir: bool = True,
) -> InformeEvaluacion:
    """Ejecuta el sistema sobre un JSONL de preguntas y lo evalúa. CONTRATO C5.

    Para cada pregunta: llama a `responder()`, aplica los tres evaluadores,
    agrega y escribe el detalle y el resumen a `resultados/<etiqueta>/`.

    Args:
        ruta_jsonl: El fichero de preguntas.
        etiqueta: Subcarpeta de `resultados/` donde escribir.
        escribir: Si se vuelca el resultado a disco.

    Returns:
        El informe completo, con detalle por pregunta y métricas agregadas.

    Raises:
        NotImplementedError: Fase 5.
    """
    raise NotImplementedError("Fase 5 · Raúl: ejecutor de la evaluación")


def guardar(informe: InformeEvaluacion, destino: Path) -> None:
    """Vuelca el informe a `resultados/<etiqueta>/`.

    Raises:
        NotImplementedError: Fase 5.
    """
    raise NotImplementedError("Fase 5 · Raúl: volcado de resultados")
