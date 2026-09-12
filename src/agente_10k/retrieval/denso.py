"""Búsqueda densa sobre el índice FAISS. P1: una implementación de `Recuperador`.

Es el recuperador que se entrega y el punto de partida de la fase 3. Aquí está
completo y funcionando a propósito: es el BASELINE contra el que se mide todo lo
demás, y sin él ni `search_filings` ni el baseline del profesor arrancan.

Dos decisiones que conviene tener delante al leerlo:

**El índice se puede leer sin faiss.** `IndexFlatIP` sobre vectores normalizados
es, en disco, una cabecera corta seguida de los vectores en crudo, y la búsqueda
es un producto matriz-vector sobre 1.749 × 384 floats: microsegundos en numpy.
Tener ese camino significa que la suite y el `recall@k` corren en máquinas donde
faiss-cpu no tiene rueda, que es la mitad de los problemas de instalación de un
grupo de tres.

**Los filtros se aplican DESPUÉS de la búsqueda**, igual que en la
implementación del profesor. Es deliberado: así esta clase es el baseline
honesto, y el filtro por metadatos aplicado ANTES es una mejora medible de la
fase 3 y no algo que ya estuviera hecho.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agente_10k.dominio.errores import CorpusNoEncontrado, IndiceDesalineado
from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.dominio.protocolos import Codificador, RepositorioFragmentos

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np

MAGIA_FLAT = (b"IxFI", b"IxF2", b"IxFl")
"""Cabeceras de los `IndexFlat*` de faiss. El nuestro es `IxFI`, producto
interno."""


def leer_vectores_planos(ruta: Path, dimension: int) -> np.ndarray:
    """Los vectores de un índice plano de faiss, sin importar faiss.

    El fichero es una cabecera de longitud pequeña seguida de `ntotal * d`
    floats de 32 bits. La longitud de la cabecera se deduce del tamaño del
    fichero en lugar de parsear el formato entero, que cambia entre versiones
    de faiss y no aporta nada aquí.
    """
    import numpy as np

    if not ruta.is_file():
        raise CorpusNoEncontrado("corpus.faiss", str(ruta.parent))
    crudo = ruta.read_bytes()
    if not crudo.startswith(MAGIA_FLAT):
        raise ValueError(
            f"{ruta.name} no parece un IndexFlat de faiss (cabecera "
            f"{crudo[:4]!r}). Este lector solo entiende índices planos; "
            f"instala faiss-cpu para cualquier otro tipo."
        )
    bytes_por_vector = dimension * 4
    sobrante = len(crudo) % bytes_por_vector
    if sobrante == 0:
        raise ValueError(
            f"{ruta.name} no tiene cabecera: el tamaño es múltiplo exacto de "
            f"{bytes_por_vector} bytes y no se puede separar."
        )
    vectores = np.frombuffer(crudo[sobrante:], dtype="float32")
    return vectores.reshape(-1, dimension)


class RecuperadorDenso:
    """FAISS + bge-small-en-v1.5. El recuperador que se entrega."""

    def __init__(
        self,
        fragmentos: RepositorioFragmentos,
        codificador: Codificador,
        ruta_indice: Path | None = None,
        matriz: np.ndarray | None = None,
    ) -> None:
        """Monta el recuperador sobre un índice en disco o una matriz dada.

        `matriz` existe para los tests: permite construirlo con cuatro vectores
        sintéticos, sin fichero y sin modelo de embeddings.
        """
        import numpy as np

        self._fragmentos = fragmentos
        self._codificador = codificador
        if matriz is None:
            if ruta_indice is None:
                raise ValueError("Hace falta `ruta_indice` o `matriz`.")
            matriz = leer_vectores_planos(ruta_indice, codificador.dimension)
        self._matriz: np.ndarray = np.asarray(matriz, dtype="float32")

        n_filas = len(fragmentos.todos())
        if self._matriz.shape[0] != n_filas:
            raise IndiceDesalineado(int(self._matriz.shape[0]), n_filas)

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación."""
        return "denso"

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` fragmentos más parecidos, filtrados después de buscar."""
        import numpy as np

        vector = np.asarray(
            self._codificador.codificar_consulta(consulta), dtype="float32"
        )
        puntuaciones = self._matriz @ vector
        orden = np.argsort(-puntuaciones)

        todos = self._fragmentos.todos()
        filtro = filtros or Filtros()
        salida: list[Fragmento] = []
        for posicion in orden:
            fragmento = todos[int(posicion)]
            if not filtro.encaja(fragmento):
                continue
            salida.append(
                fragmento.con_puntuacion(round(float(puntuaciones[posicion]), 4))
            )
            if len(salida) >= k:
                break
        return salida
