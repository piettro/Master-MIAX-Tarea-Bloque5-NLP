"""Repositorio de fragmentos. P3: las tools no saben qué es un parquet.

Los 1.749 fragmentos pueden venir de dos sitios, y los dos sirven:

* `chunks.jsonl`, el fichero canónico del corpus;
* `indice/chunks_meta.parquet`, los metadatos del índice, que traen el texto
  completo de cada fragmento además de sus metadatos.

Se prefiere el parquet cuando está, porque es el que está ALINEADO con el
índice FAISS: la fila *i* describe el vector *i*. Cargar los fragmentos de un
sitio y los vectores de otro es la forma de conseguir un retrieval que devuelve
texto equivocado sin dar ningún error.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from agente_10k.corpus.normalizacion import normalizar
from agente_10k.dominio.errores import CorpusNoEncontrado
from agente_10k.dominio.modelos import Filtros, Fragmento

CAMPOS_FRAGMENTO = (
    "chunk_id",
    "ticker",
    "fiscal_year",
    "item",
    "posicion",
    "texto",
    "n_tokens",
    "contiene_tabla",
    "inicio_car",
    "fin_car",
)


def _fragmento_desde(fila: Mapping[str, Any]) -> Fragmento:
    """Un `Fragmento` a partir de una fila cruda, tolerando campos ausentes.

    La fila viene de un parquet o de un JSONL, asi que sus valores no estan
    tipados en origen: `Any` aqui es honesto, y la conversion explicita de
    cada campo es lo que convierte datos crudos en un modelo validado.
    """
    return Fragmento(
        chunk_id=str(fila["chunk_id"]),
        ticker=str(fila["ticker"]),
        fiscal_year=int(fila["fiscal_year"]),
        item=str(fila["item"]),
        posicion=int(fila.get("posicion", 0)),
        texto=str(fila["texto"]),
        n_tokens=int(fila.get("n_tokens", 0)),
        contiene_tabla=bool(fila.get("contiene_tabla", False)),
        inicio_car=int(fila.get("inicio_car", 0)),
        fin_car=int(fila.get("fin_car", 0)),
    )


class RepositorioFragmentosMemoria:
    """Los fragmentos en memoria. 1.749 filas caben de sobra.

    El orden de `todos()` es el orden de carga, que es el del índice FAISS. No
    reordenar: ese orden es lo que empareja cada vector con su texto.
    """

    def __init__(self, fragmentos: Iterable[Fragmento]) -> None:
        """Construye el repositorio a partir de una secuencia de fragmentos."""
        self._fragmentos: tuple[Fragmento, ...] = tuple(fragmentos)
        self._por_id = {f.chunk_id: f for f in self._fragmentos}
        self._normalizado = {f.chunk_id: normalizar(f.texto) for f in self._fragmentos}

    # --- construcción ------------------------------------------------------
    @classmethod
    def desde_parquet(cls, ruta: Path) -> RepositorioFragmentosMemoria:
        """Carga desde `chunks_meta.parquet`, preservando el orden de las filas."""
        import pandas as pd

        if not ruta.is_file():
            raise CorpusNoEncontrado("chunks_meta.parquet", str(ruta.parent))
        tabla = pd.read_parquet(ruta)
        faltan = [c for c in ("chunk_id", "ticker", "texto") if c not in tabla.columns]
        if faltan:
            raise CorpusNoEncontrado(
                f"columnas {faltan} en chunks_meta.parquet", str(ruta)
            )
        filas: list[Any] = tabla.to_dict(orient="records")
        return cls(_fragmento_desde(f) for f in filas)

    @classmethod
    def desde_jsonl(cls, ruta: Path) -> RepositorioFragmentosMemoria:
        """Carga desde `chunks.jsonl`, una línea por fragmento."""
        if not ruta.is_file():
            raise CorpusNoEncontrado("chunks.jsonl", str(ruta.parent))
        with ruta.open(encoding="utf-8") as f:
            filas = [json.loads(linea) for linea in f if linea.strip()]
        return cls(_fragmento_desde(fila) for fila in filas)

    # --- consultas ---------------------------------------------------------
    def obtener(self, chunk_id: str) -> Fragmento | None:
        """El fragmento con ese `chunk_id`, o `None` si no existe."""
        return self._por_id.get(chunk_id)

    def todos(self) -> Sequence[Fragmento]:
        """Todos los fragmentos, en el orden del índice."""
        return self._fragmentos

    def filtrar(self, filtros: Filtros) -> list[Fragmento]:
        """Los fragmentos que pasan los filtros de metadatos."""
        if filtros.vacios():
            return list(self._fragmentos)
        return [f for f in self._fragmentos if filtros.encaja(f)]

    def buscar_literal(self, texto: str) -> list[Fragmento]:
        """Los fragmentos que contienen `texto`, comparando ya normalizado.

        Normalizar los dos lados es lo que evita que un ancla correcta falle
        por una comilla tipográfica o por un salto de línea que metió el
        troceador. La normalización está documentada en `normalizacion.py`.
        """
        aguja = normalizar(texto)
        if not aguja:
            return []
        return [f for f in self._fragmentos if aguja in self._normalizado[f.chunk_id]]

    def posicion_de(self, chunk_id: str) -> int | None:
        """El índice de fila del fragmento, que es su posición en FAISS."""
        for i, f in enumerate(self._fragmentos):
            if f.chunk_id == chunk_id:
                return i
        return None

    def __len__(self) -> int:
        """Cuántos fragmentos hay."""
        return len(self._fragmentos)
