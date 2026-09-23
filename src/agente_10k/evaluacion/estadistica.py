"""Intervalos de confianza y contraste pareado.

Con 20 preguntas, una tabla de proporciones a pelo no dice nada: 12/20 y 14/20
es el mismo resultado. Dos cosas lo arreglan, y las dos son estándar:

- Wilson para el intervalo de una proporción. No la normal de toda la vida, que
  con n pequeño o p cerca de 0 o 1 se sale de [0, 1] y da intervalos de ancho
  cero cuando aciertas todo.
- McNemar exacto para comparar dos sistemas. Exacto, no chi-cuadrado, porque la
  aproximación pide unos 25 pares discordantes y aquí habrá cuatro o cinco.

Los dos sistemas responden LAS MISMAS preguntas, así que los datos son pareados
y comparar dos proporciones independientes sería tirar información: lo que
importa es en cuántas preguntas uno acierta y el otro no.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

Z_95 = 1.959963984540054  # cuantil 0,975 de la normal estándar


@dataclass(frozen=True)
class Intervalo:
    """Un intervalo de confianza para una proporción."""

    inferior: float
    superior: float

    def __str__(self) -> str:
        """Como se lee en la tabla."""
        return f"[{self.inferior:.0%}, {self.superior:.0%}]"

    @property
    def anchura(self) -> float:
        """Lo ancho que es. Con 20 preguntas, ancho."""
        return self.superior - self.inferior


@dataclass(frozen=True)
class Comparacion:
    """El resultado de comparar dos sistemas sobre las mismas preguntas."""

    solo_a: int  # preguntas que acierta A y falla B
    solo_b: int
    p_valor: float

    @property
    def discordantes(self) -> int:
        """Las preguntas en las que los dos sistemas no coinciden."""
        return self.solo_a + self.solo_b

    def significativa(self, alfa: float = 0.05) -> bool:
        """Si la diferencia pasa el umbral."""
        return self.p_valor < alfa

    def __str__(self) -> str:
        """Una línea para el informe."""
        return (
            f"A gana {self.solo_a}, B gana {self.solo_b}, p = {self.p_valor:.3f}"
            f"{'' if self.significativa() else ' (no significativo)'}"
        )


def wilson(aciertos: int, n: int, z: float = Z_95) -> Intervalo:
    """Intervalo de Wilson para `aciertos` de `n`."""
    if n <= 0:
        return Intervalo(0.0, 1.0)
    if aciertos < 0 or aciertos > n:
        raise ValueError(f"{aciertos} aciertos de {n} no es posible")
    p = aciertos / n
    denominador = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / denominador
    radio = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominador
    return Intervalo(max(0.0, centro - radio), min(1.0, centro + radio))


def _binomial_dos_colas(exitos: int, n: int) -> float:
    """p-valor exacto de una binomial con p = 1/2, a dos colas."""
    if n == 0:
        return 1.0
    casos = sum(math.comb(n, i) for i in range(min(exitos, n - exitos) + 1))
    return min(1.0, 2 * math.ldexp(casos, -n))


def mcnemar(a: Sequence[bool], b: Sequence[bool]) -> Comparacion:
    """Contraste de McNemar exacto entre dos sistemas, pregunta a pregunta.

    `a` y `b` son los aciertos de cada sistema EN EL MISMO ORDEN.
    """
    if len(a) != len(b):
        raise ValueError(f"{len(a)} resultados contra {len(b)}: no están pareados")
    solo_a = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    solo_b = sum(1 for x, y in zip(a, b, strict=True) if y and not x)
    return Comparacion(solo_a, solo_b, _binomial_dos_colas(solo_a, solo_a + solo_b))
