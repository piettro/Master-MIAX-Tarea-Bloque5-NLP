"""El modelo de embeddings, y el prefijo que solo va en la consulta.

BGE pide un prefijo en la CONSULTA y no en los fragmentos indexados. Omitirlo no
da ningún error: simplemente recupera peor, que es la peor clase de fallo
posible porque no se nota hasta que alguien mide. Ponerlo en los DOS lados es
igual de malo y todavía menos evidente.

Por eso el prefijo vive aquí, en un solo sitio, con dos métodos que se llaman
distinto —`codificar_consulta` y `codificar_pasajes`— y un test que fija que uno
lo pone y el otro no.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

MODELO_EMBEDDINGS = "BAAI/bge-small-en-v1.5"
DIMENSION = 384
PREFIJO_CONSULTA_BGE = "Represent this sentence for searching relevant passages: "
"""Documentado en `indice/MANIFEST.md`. No se toca sin regenerar el índice."""


class CodificadorBge:
    """`sentence-transformers` con el prefijo de BGE puesto donde toca.

    El modelo se carga de forma perezosa: son unos 130 MB y unos segundos la
    primera vez, y importar este módulo tiene que seguir siendo instantáneo.
    """

    def __init__(
        self,
        modelo: str = MODELO_EMBEDDINGS,
        dir_cache: Path | None = None,
        modelo_cargado: object | None = None,
    ) -> None:
        """Prepara el codificador sin cargar todavía el modelo.

        Args:
            modelo: Identificador del modelo de embeddings.
            dir_cache: Dónde cachear los vectores, o `None`.
            modelo_cargado: Un modelo ya construido. Existe para poder probar
                el prefijo sin descargar 130 MB: sin esto, el único test
                posible sería sobre un doble del propio codificador, que es
                justo la pieza que hay que comprobar.
        """
        self._nombre = modelo
        self._dir_cache = dir_cache
        self._modelo: object | None = modelo_cargado

    @property
    def dimension(self) -> int:
        """Dimensión de los vectores. 384 en bge-small."""
        return DIMENSION

    @property
    def nombre(self) -> str:
        """El identificador del modelo, para la traza y el manifiesto."""
        return self._nombre

    def _cargar(self) -> object:
        """Carga el modelo la primera vez que hace falta."""
        if self._modelo is None:
            from sentence_transformers import SentenceTransformer

            self._modelo = SentenceTransformer(self._nombre)
        return self._modelo

    def codificar_consulta(self, consulta: str) -> Sequence[float]:
        """El vector de una consulta, normalizado y CON el prefijo."""
        vectores = self._codificar([PREFIJO_CONSULTA_BGE + consulta])
        return vectores[0]

    def codificar_pasajes(self, pasajes: Iterable[str]) -> Sequence[Sequence[float]]:
        """Los vectores de varios pasajes, normalizados y SIN prefijo."""
        return self._codificar(list(pasajes))

    def _codificar(self, textos: list[str]) -> list[list[float]]:
        """Codifica una lista de textos ya preparados."""
        modelo = self._cargar()
        vectores = modelo.encode(  # type: ignore[attr-defined]
            textos,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [[float(x) for x in fila] for fila in vectores]
