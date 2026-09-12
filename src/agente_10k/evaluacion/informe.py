"""Genera las tablas del informe. FASE 5 — Raúl.

STUB. Las firmas y el contrato están fijados; el cuerpo es de la fase 5.

Ninguna cifra del PDF se escribe a mano. Si no sale de `make informe`, no entra.
Estas funciones leen `resultados/` y escriben markdown y csv; el PDF los incluye.

La tabla principal:

    sistema  | extractiva | numérica | comparativa | hueco | recall@5 |
             | coste medio | latencia media | tool calls/pregunta
    baseline |
    final    |

con el mejor valor de cada columna REMARCADO. Coste y latencia son COLUMNAS, no
una nota al pie: es una indicación explícita del enunciado.

Cuidado con «el mejor valor»: en coste, en latencia y en llamadas por pregunta,
mejor es MENOR. Remarcar el máximo en esas tres columnas es el error de bulto
que convierte la tabla en un argumento en contra.
"""

from __future__ import annotations

from pathlib import Path

from agente_10k.dominio.modelos import InformeEvaluacion

COLUMNAS_MENOR_ES_MEJOR = frozenset(
    {"coste medio", "latencia media", "tool calls/pregunta"}
)
"""Las columnas en las que el mejor valor es el más bajo."""


def tabla_principal(baseline: InformeEvaluacion, final: InformeEvaluacion) -> str:
    """La tabla baseline contra final, en markdown y con el mejor remarcado.

    Raises:
        NotImplementedError: Fase 5.
    """
    raise NotImplementedError("Fase 5 · Raúl: tabla principal del informe")


def tabla_por_familia(informe: InformeEvaluacion) -> str:
    """Aciertos por familia, con el detalle de qué falló en cada una.

    Raises:
        NotImplementedError: Fase 5.
    """
    raise NotImplementedError("Fase 5 · Raúl: tabla por familia")


def tabla_trayectoria(informe: InformeEvaluacion) -> str:
    """Los tres estados de trayectoria y su columna de camino equivocado.

    Raises:
        NotImplementedError: Fase 5.
    """
    raise NotImplementedError("Fase 5 · Raúl: tabla de trayectoria")


def tabla_guardarrail(informe: InformeEvaluacion) -> str:
    """Cuántas veces saltó el guardarraíl y cuántas recuperó.

    Raises:
        NotImplementedError: Fase 5.
    """
    raise NotImplementedError("Fase 5 · Raúl: tabla del guardarraíl")


def generar_todo(dir_resultados: Path, destino: Path) -> list[Path]:
    """Regenera todas las tablas desde `resultados/`. Es `make informe`.

    Returns:
        Las rutas de los ficheros escritos, markdown y csv.

    Raises:
        NotImplementedError: Fase 5.
    """
    raise NotImplementedError("Fase 5 · Raúl: generación de todas las tablas")
