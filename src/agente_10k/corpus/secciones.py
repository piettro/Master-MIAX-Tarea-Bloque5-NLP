"""Repositorio de secciones. P3: lo que sirve `read_section`.

Dos fuentes, en este orden:

1. `secciones.jsonl`, el fichero canónico. 48 líneas, el texto íntegro.
2. Las secciones RECONSTRUIDAS desde los fragmentos, si el fichero no está.

La segunda no es equivalente a la primera y el código lo dice en voz alta:
`Seccion.reconstruida` va a `True` y la traza lo registra. Los fragmentos
cubren la sección entera mediante `inicio_car`/`fin_car`, pero en 1.029 de las
1.701 fronteras se pierden entre 2 y 4 caracteres —el separador que consumió el
troceador—, así que el texto reconstruido NO es literal en esas costuras. Sirve
para que `read_section` funcione y para leer; no sirve para verificar un ancla
que cruce una frontera.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from agente_10k.dominio.errores import CorpusNoEncontrado
from agente_10k.dominio.modelos import Fragmento, Seccion

SEPARADOR_RECONSTRUCCION = "\n\n"
"""Lo que se inserta en los huecos de 2 caracteres entre fragmentos.

Es una conjetura informada: los cortes del troceador caen en fronteras de
párrafo, y en los fragmentos que sí solapan se ve que lo que hay ahí es un
salto doble. No es una certeza, y por eso la sección queda marcada."""


class RepositorioSeccionesMemoria:
    """Las 48 secciones en memoria, indexadas por (ticker, ejercicio, item)."""

    def __init__(self, secciones: Iterable[Seccion]) -> None:
        """Construye el repositorio a partir de una secuencia de secciones."""
        self._secciones: tuple[Seccion, ...] = tuple(secciones)
        self._por_clave = {
            (s.ticker, s.fiscal_year, s.item): s for s in self._secciones
        }

    # --- construcción ------------------------------------------------------
    @classmethod
    def desde_jsonl(cls, ruta: Path) -> RepositorioSeccionesMemoria:
        """Carga desde `secciones.jsonl`, una línea por sección."""
        if not ruta.is_file():
            raise CorpusNoEncontrado("secciones.jsonl", str(ruta.parent))
        with ruta.open(encoding="utf-8") as f:
            filas = [json.loads(linea) for linea in f if linea.strip()]
        return cls(
            Seccion(
                ticker=str(fila["ticker"]),
                fiscal_year=int(fila["fiscal_year"]),
                item=str(fila["item"]),
                texto=str(fila["texto"]),
                n_tokens=int(fila.get("n_tokens", 0)),
                empresa=fila.get("empresa"),
                titulo=fila.get("titulo"),
                url=fila.get("url"),
                item_origen=fila.get("item_origen"),
            )
            for fila in filas
        )

    @classmethod
    def desde_fragmentos(
        cls, fragmentos: Sequence[Fragmento]
    ) -> RepositorioSeccionesMemoria:
        """Reconstruye las secciones pegando los fragmentos por sus offsets.

        Los fragmentos de una misma sección se ordenan por `inicio_car` y se
        pegan recortando el solape. Donde hay hueco se inserta
        `SEPARADOR_RECONSTRUCCION`. El resultado es legible y utilizable, pero
        no es literal en las costuras: por eso `reconstruida=True`.
        """
        por_seccion: dict[tuple[str, int, str], list[Fragmento]] = {}
        for f in fragmentos:
            por_seccion.setdefault((f.ticker, f.fiscal_year, f.item), []).append(f)

        secciones: list[Seccion] = []
        for (ticker, fy, item), trozos in por_seccion.items():
            trozos.sort(key=lambda f: (f.inicio_car, f.posicion))
            texto = _pegar(trozos)
            secciones.append(
                Seccion(
                    ticker=ticker,
                    fiscal_year=fy,
                    item=item,
                    texto=texto,
                    n_tokens=_estimar_tokens(trozos, texto),
                    reconstruida=True,
                )
            )
        secciones.sort(key=lambda s: (s.ticker, s.fiscal_year, s.item))
        return cls(secciones)

    # --- consultas ---------------------------------------------------------
    def obtener(self, ticker: str, fiscal_year: int, item: str) -> Seccion | None:
        """La sección pedida, o `None` si no está en el corpus."""
        return self._por_clave.get((ticker, int(fiscal_year), item))

    def listar(self) -> list[Seccion]:
        """Todas las secciones, ordenadas por emisor, ejercicio e item."""
        return sorted(self._secciones, key=lambda s: (s.ticker, s.fiscal_year, s.item))

    def tickers(self) -> list[str]:
        """Los tickers presentes en el corpus, ordenados."""
        return sorted({s.ticker for s in self._secciones})

    def ejercicios(self, ticker: str | None = None) -> list[int]:
        """Los ejercicios disponibles, en total o para un emisor."""
        return sorted(
            {
                s.fiscal_year
                for s in self._secciones
                if ticker is None or s.ticker == ticker
            }
        )

    def items(self, ticker: str | None = None) -> list[str]:
        """Los items disponibles, en el orden en que aparecen en el 10-K."""
        presentes = {
            s.item for s in self._secciones if ticker is None or s.ticker == ticker
        }
        orden = ["1A", "7", "7A", "8"]
        conocidos = [i for i in orden if i in presentes]
        return conocidos + sorted(presentes - set(orden))

    def empresa(self, ticker: str) -> str | None:
        """El nombre de la compañía, si el corpus lo trae."""
        for s in self._secciones:
            if s.ticker == ticker and s.empresa:
                return s.empresa
        return None

    def alguna_reconstruida(self) -> bool:
        """Si alguna sección se derivó de los fragmentos en vez de leerse."""
        return any(s.reconstruida for s in self._secciones)

    def __len__(self) -> int:
        """Cuántas secciones hay. En el corpus completo, 48."""
        return len(self._secciones)


def _pegar(trozos: Sequence[Fragmento]) -> str:
    """Pega fragmentos ordenados recortando solapes y marcando los huecos."""
    if not trozos:
        return ""
    partes = [trozos[0].texto]
    cursor = trozos[0].fin_car
    for trozo in trozos[1:]:
        if trozo.inicio_car >= cursor:
            partes.append(SEPARADOR_RECONSTRUCCION)
            partes.append(trozo.texto)
        else:
            solape = cursor - trozo.inicio_car
            partes.append(trozo.texto[solape:] if solape < len(trozo.texto) else "")
        cursor = max(cursor, trozo.fin_car)
    return "".join(partes)


def _estimar_tokens(trozos: Sequence[Fragmento], texto: str) -> int:
    """Tokens de la sección reconstruida, prorrateando los de los fragmentos.

    Los fragmentos solapan, así que sumar sus `n_tokens` sobreestima. Se
    escala por la razón entre los caracteres del texto pegado y la suma de los
    caracteres de los trozos, que es la corrección de primer orden correcta.
    """
    caracteres = sum(len(t.texto) for t in trozos)
    tokens = sum(t.n_tokens for t in trozos)
    if caracteres == 0:
        return 0
    return round(tokens * len(texto) / caracteres)
