"""Los TRES evaluadores del enunciado. FASE 5 — Raúl.

STUB. Las firmas y el contrato están fijados; el cuerpo es de la fase 5.

**1 · CITA.** Que la cita exista y que respalde de verdad lo que se afirma. Tres
comprobaciones distintas que se reportan por separado porque fallan por motivos
distintos: que el texto citado aparezca literalmente en el corpus (con la
normalización de `corpus/normalizacion.py`, documentada); que el `chunk_id`
declarado contenga esa cita —citar bien y atribuir mal es un fallo de
trazabilidad, no de recuperación—; y que el fragmento pertenezca al emisor,
ejercicio y sección que la pregunta pedía, porque una cita correcta del
documento equivocado es un fallo.

**2 · CIFRA.** Que el número coincida con XBRL dentro de la tolerancia
DOCUMENTADA, importando el mismo objeto `Tolerancia` que usa el guardarraíl de
la fase 4. Un solo sitio, o los dos números se separan y la tabla deja de ser
defendible. Caso especial obligatorio: cuando la respuesta esperada es un hueco,
acertar significa `cifra=None` y `fuente="ninguna"`; dar una cifra plausible es
el peor fallo posible del sistema y lleva categoría propia.

**3 · TRAYECTORIA.** Que la respuesta pasara por la herramienta que tocaba.
Acertar por el camino equivocado cuenta como FALLO y se reporta en su propia
columna: es el criterio central de la práctica.

Todos degradan a `no_aplica` cuando la pregunta no trae el campo que necesitan.
El día 24 pueden llegar diez preguntas con solo `id` y `pregunta`, y un
evaluador que aborte por eso tumba la demostración entera.
"""

from __future__ import annotations

from agente_10k.dominio.modelos import (
    EstadoTrayectoria,
    Pregunta,
    RespuestaFinanciera,
    Traza,
    VeredictoEvaluador,
)
from agente_10k.dominio.protocolos import RepositorioFragmentos, RepositorioXbrl
from agente_10k.dominio.tolerancia import Tolerancia


class EvaluadorCita:
    """Evaluador 1: la cita existe y respalda lo que se afirma."""

    def __init__(self, fragmentos: RepositorioFragmentos) -> None:
        """Monta el evaluador sobre el repositorio de fragmentos.

        Raises:
            NotImplementedError: Fase 5.
        """
        raise NotImplementedError("Fase 5 · Raúl: evaluador de cita")

    def evaluar(
        self, pregunta: Pregunta, respuesta: RespuestaFinanciera
    ) -> VeredictoEvaluador:
        """El veredicto sobre la cita, con el motivo del fallo si lo hay.

        En `detalle` deja separadas las tres causas —`cita_no_literal`,
        `chunk_id_no_contiene_cita`, `documento_equivocado`— para que el informe
        pueda decir cuál de las tres domina en vez de un porcentaje agregado.

        Raises:
            NotImplementedError: Fase 5.
        """
        raise NotImplementedError("Fase 5 · Raúl: evaluador de cita")


class EvaluadorCifra:
    """Evaluador 2: la cifra coincide con XBRL dentro de la tolerancia."""

    def __init__(
        self,
        xbrl: RepositorioXbrl,
        tolerancia: Tolerancia | None = None,
    ) -> None:
        """Monta el evaluador con la MISMA tolerancia que el guardarraíl.

        Raises:
            NotImplementedError: Fase 5.
        """
        raise NotImplementedError("Fase 5 · Raúl: evaluador de cifra")

    def evaluar(
        self, pregunta: Pregunta, respuesta: RespuestaFinanciera
    ) -> VeredictoEvaluador:
        """El veredicto sobre la cifra y sobre la coherencia de la unidad.

        Raises:
            NotImplementedError: Fase 5.
        """
        raise NotImplementedError("Fase 5 · Raúl: evaluador de cifra")

    def es_alucinacion_sobre_hueco(
        self, pregunta: Pregunta, respuesta: RespuestaFinanciera
    ) -> bool:
        """Si se dio una cifra donde la respuesta correcta era que no hay dato.

        Raises:
            NotImplementedError: Fase 5.
        """
        raise NotImplementedError("Fase 5 · Raúl: alucinación sobre hueco")


class EvaluadorTrayectoria:
    """Evaluador 3: la respuesta pasó por la herramienta que tocaba."""

    def evaluar(self, pregunta: Pregunta, traza: Traza) -> VeredictoEvaluador:
        """El veredicto sobre el camino recorrido.

        Raises:
            NotImplementedError: Fase 5.
        """
        raise NotImplementedError("Fase 5 · Raúl: evaluador de trayectoria")

    def clasificar(
        self,
        pregunta: Pregunta,
        traza: Traza,
        respuesta_correcta: bool,
    ) -> EstadoTrayectoria:
        """Los tres estados del enunciado.

        `camino_correcto`, `camino_incorrecto_respuesta_correcta` —el que da
        sentido a toda la práctica— y
        `camino_incorrecto_respuesta_incorrecta`.

        Raises:
            NotImplementedError: Fase 5.
        """
        raise NotImplementedError("Fase 5 · Raúl: clasificación de trayectoria")
