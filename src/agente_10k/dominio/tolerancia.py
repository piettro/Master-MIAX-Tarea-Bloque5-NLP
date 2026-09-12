"""La tolerancia con la que se compara una cifra contra XBRL. UN SOLO SITIO.

Este módulo existe porque hay dos consumidores de la misma regla:

* el `GuardarraílXBRL` del middleware (F4), que decide si le devuelve el
  desajuste al modelo para que reintente;
* el evaluador de cifra (F5), que decide si la respuesta cuenta como acierto.

Si cada uno llevara su propio número, acabarían separándose y la tabla del
informe dejaría de ser defendible: el guardarraíl aceptaría cifras que el
evaluador suspende, o al revés. Aquí hay uno, documentado, y los dos lo
importan.
"""

from __future__ import annotations

from dataclasses import dataclass

TOLERANCIA_RELATIVA: float = 0.005
"""0,5 % relativo.

Por qué ese número y no cero: los informes expresan las mismas magnitudes en
millones redondeados en la prosa («$60.9 billion») y en unidades exactas en la
tabla XBRL (60.922.000.000). Un agente que cite bien y redondee a la décima de
billón está acertando, y 60.900/60.922 es un 0,036 % de desvío. Un agente que
lea el número de otra compañía o de otro ejercicio se desvía mucho más que un
0,5 %, así que el umbral separa las dos cosas sin ambigüedad.

Por qué no es más generoso: el revenue de MSFT crece un 14,9 % entre FY2024 y
FY2025. Una tolerancia del 1 % ya no distinguiría un redondeo de haber cogido
el ejercicio equivocado en algunas magnitudes pequeñas.
"""

TOLERANCIA_ABSOLUTA: float = 1.0
"""Un dólar.

Necesaria para las magnitudes que valen cero o casi: con solo tolerancia
relativa, comparar contra 0 nunca casa.
"""


@dataclass(frozen=True)
class Tolerancia:
    """La regla de comparación de cifras, con su porqué escrito al lado."""

    relativa: float = TOLERANCIA_RELATIVA
    absoluta: float = TOLERANCIA_ABSOLUTA

    def coincide(self, afirmada: float, esperada: float) -> bool:
        """Si `afirmada` cuadra con `esperada` dentro de la tolerancia."""
        desvio = abs(afirmada - esperada)
        return desvio <= max(self.absoluta, abs(esperada) * self.relativa)

    def desvio_relativo(self, afirmada: float, esperada: float) -> float:
        """El desvío relativo, o `inf` si lo esperado es cero y lo dicho no."""
        if esperada == 0:
            return 0.0 if afirmada == 0 else float("inf")
        return abs(afirmada - esperada) / abs(esperada)

    def describir(self) -> str:
        """La tolerancia en una línea, para la traza y para el informe."""
        return (
            f"{self.relativa:.3%} relativo o {self.absoluta:g} en valor "
            f"absoluto, lo que sea mayor"
        )


TOLERANCIA = Tolerancia()
"""La instancia que importan el guardarraíl y el evaluador de cifra."""
