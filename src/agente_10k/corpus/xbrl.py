"""Repositorio de hechos XBRL. La fuente autorizada para cualquier cifra.

Aquí viven codificadas, como datos y no como comentarios, las dos trampas del
corpus que el enunciado avisa por escrito:

**T2 · El concepto del ingreso no es universal.** NVIDIA usa `Revenues`; Apple,
Microsoft, Meta y Amazon usan `RevenueFromContractWithCustomerExcludingAssessedTax`;
Alphabet etiqueta los dos en FY2024 y solo `Revenues` en FY2025. Razonar por
analogía entre compañías está prohibido, así que el repositorio nunca traduce
un concepto por su cuenta: se limita a decir qué conceptos existen y a
*sugerir* el sinónimo. La decisión la toma el agente.

**T3 · Hay huecos reales y son preguntas legítimas.** Amazon no reporta
`GrossProfit`, `Liabilities` ni `ResearchAndDevelopmentExpense` en us-gaap, y
Meta y Alphabet tampoco `GrossProfit`. Eso no es un fallo del corpus: la
respuesta correcta a «¿cuál fue el margen bruto de Amazon?» es que no está, con
`fuente="ninguna"` y `cifra=None`. Distinguir un hueco real de un concepto mal
escrito cambia el mensaje que recibe el modelo, y con él lo que hace después.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agente_10k.dominio.modelos import HechoXbrl

SINONIMOS: dict[str, tuple[str, ...]] = {
    "Revenues": ("RevenueFromContractWithCustomerExcludingAssessedTax",),
    "RevenueFromContractWithCustomerExcludingAssessedTax": ("Revenues",),
    "Revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    "NetIncome": ("NetIncomeLoss",),
    "OperatingIncome": ("OperatingIncomeLoss",),
    "TotalAssets": ("Assets",),
    "TotalLiabilities": ("Liabilities",),
    "ResearchAndDevelopment": ("ResearchAndDevelopmentExpense",),
}
"""Conceptos que pueden nombrar la misma magnitud.

Se usan solo para SUGERIR, nunca para traducir. Si el repositorio resolviera el
sinónimo por su cuenta, el agente acertaría la cifra sin haber aprendido que
cada emisor etiqueta a su manera, y la siguiente compañía volvería a fallar.
"""

HUECOS_CONOCIDOS: frozenset[tuple[str, str]] = frozenset(
    {
        ("AMZN", "GrossProfit"),
        ("AMZN", "Liabilities"),
        ("AMZN", "ResearchAndDevelopmentExpense"),
        ("META", "GrossProfit"),
        ("GOOGL", "GrossProfit"),
    }
)
"""Huecos REALES en us-gaap, declarados por el enunciado.

Un hueco conocido produce un mensaje que induce `fuente="ninguna"`; un concepto
ausente que no está en esta lista produce un mensaje que invita a corregir el
nombre. Son dos situaciones distintas y el agente debe reaccionar distinto a
cada una. `tests/corpus/test_xbrl.py` comprueba contra el corpus real que estos
huecos siguen siendo huecos: si el profesor regenera el corpus y uno deja de
serlo, el test lo dice en vez de que el sistema mienta.
"""

COLUMNAS = ("ticker", "fiscal_year", "concept", "value", "unit")


class RepositorioXbrlMemoria:
    """Los hechos XBRL en memoria. En el corpus completo son 135."""

    def __init__(self, hechos: Iterable[HechoXbrl], *, cargado: bool = True) -> None:
        """Construye el repositorio a partir de una secuencia de hechos."""
        self._hechos: tuple[HechoXbrl, ...] = tuple(hechos)
        self._cargado = cargado
        self._por_clave: dict[tuple[str, int, str], HechoXbrl] = {}
        self._por_emisor: dict[tuple[str, int], list[str]] = {}
        for h in self._hechos:
            self._por_clave.setdefault((h.ticker, h.fiscal_year, h.concept), h)
            self._por_emisor.setdefault((h.ticker, h.fiscal_year), []).append(h.concept)

    # --- construcción ------------------------------------------------------
    @classmethod
    def desde_parquet(cls, ruta: Path) -> RepositorioXbrlMemoria:
        """Carga desde `xbrl_facts.parquet`.

        Si el fichero no está devuelve un repositorio VACÍO y no cargado, en
        lugar de lanzar: `disponible()` lo distingue de un corpus sin hechos
        para ese emisor, y las tools dan un mensaje que dice qué falta. Que
        falte el parquet no puede tumbar el import del paquete.
        """
        if not ruta.is_file():
            return cls((), cargado=False)

        import pandas as pd

        tabla = pd.read_parquet(ruta)
        faltan = [c for c in COLUMNAS if c not in tabla.columns]
        if faltan:
            raise ValueError(
                f"{ruta.name} no trae las columnas {faltan}. Se esperan "
                f"{list(COLUMNAS)} más las opcionales period_end y form."
            )
        filas: list[Any] = tabla.to_dict(orient="records")
        return cls(
            HechoXbrl(
                ticker=str(fila["ticker"]),
                fiscal_year=int(fila["fiscal_year"]),
                concept=str(fila["concept"]),
                value=float(fila["value"]),
                unit=str(fila["unit"]),
                period_end=(
                    None if fila.get("period_end") is None else str(fila["period_end"])
                ),
                form=None if fila.get("form") is None else str(fila["form"]),
            )
            for fila in filas
        )

    # --- consultas ---------------------------------------------------------
    def obtener(self, ticker: str, fiscal_year: int, concept: str) -> HechoXbrl | None:
        """El hecho exacto, o `None` si ese emisor no reporta ese concepto."""
        return self._por_clave.get((ticker, int(fiscal_year), concept))

    def conceptos(self, ticker: str, fiscal_year: int) -> list[str]:
        """Los conceptos que SÍ existen para ese emisor y ejercicio."""
        return sorted(set(self._por_emisor.get((ticker, int(fiscal_year)), [])))

    def hay_datos(self, ticker: str, fiscal_year: int) -> bool:
        """Si hay algún hecho para ese emisor y ejercicio."""
        return bool(self._por_emisor.get((ticker, int(fiscal_year))))

    def disponible(self) -> bool:
        """Si el parquet llegó a cargarse."""
        return self._cargado

    def tickers(self) -> list[str]:
        """Los emisores con hechos cargados."""
        return sorted({h.ticker for h in self._hechos})

    def todos_los_conceptos(self) -> list[str]:
        """Todos los conceptos del corpus, ordenados."""
        return sorted({h.concept for h in self._hechos})

    # --- las dos trampas ---------------------------------------------------
    def es_hueco_conocido(self, ticker: str, concept: str) -> bool:
        """Si es uno de los huecos REALES declarados en el enunciado."""
        return (ticker, concept) in HUECOS_CONOCIDOS

    def sugerencias(self, ticker: str, fiscal_year: int, concept: str) -> list[str]:
        """Sinónimos del concepto pedido que SÍ existen para ese emisor.

        Se comprueba contra los datos, no contra la tabla de sinónimos: sugerir
        `Revenues` a un emisor que tampoco lo reporta sería mandar al agente a
        un segundo fallo.
        """
        disponibles = set(self.conceptos(ticker, fiscal_year))
        return [s for s in SINONIMOS.get(concept, ()) if s in disponibles]

    def __len__(self) -> int:
        """Cuántos hechos hay cargados."""
        return len(self._hechos)
