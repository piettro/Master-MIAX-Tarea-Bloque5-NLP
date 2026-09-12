"""Evaluación: los tres evaluadores, las métricas, el ejecutor y las tablas."""

from __future__ import annotations

from agente_10k.evaluacion.ejecutor import evaluar, leer_preguntas
from agente_10k.evaluacion.evaluadores import (
    EvaluadorCifra,
    EvaluadorCita,
    EvaluadorTrayectoria,
)
from agente_10k.evaluacion.metricas import acierta_en_k, agregar, recall_at_k

__all__ = [
    "EvaluadorCifra",
    "EvaluadorCita",
    "EvaluadorTrayectoria",
    "acierta_en_k",
    "agregar",
    "evaluar",
    "leer_preguntas",
    "recall_at_k",
]
