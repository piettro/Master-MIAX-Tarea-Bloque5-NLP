"""Evaluación: los tres evaluadores, las métricas, el ejecutor y las tablas."""

from __future__ import annotations

from agente_10k.evaluacion.ejecutor import evaluar, leer_preguntas
from agente_10k.evaluacion.estadistica import Intervalo, mcnemar, wilson
from agente_10k.evaluacion.evaluadores import (
    EvaluadorCifra,
    EvaluadorCita,
    EvaluadorTrayectoria,
)
from agente_10k.evaluacion.metricas import acierta_en_k, agregar, mrr, recall_at_k

__all__ = [
    "EvaluadorCifra",
    "EvaluadorCita",
    "EvaluadorTrayectoria",
    "Intervalo",
    "acierta_en_k",
    "agregar",
    "evaluar",
    "leer_preguntas",
    "mcnemar",
    "mrr",
    "recall_at_k",
    "wilson",
]
