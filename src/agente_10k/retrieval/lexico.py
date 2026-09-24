"""BM25 sobre los mismos 1.749 fragmentos.

Por qué hace falta además del denso: la búsqueda densa falla justo donde más
duele en finanzas. Un ticker, un nombre propio o una cifra concreta no tienen
vecindario semántico —«60,922» no se «parece» a nada— y el léxico los encuentra
exactamente. Fusionarlos es lo que sube el recall sin romper lo que ya iba bien.

Lo que hubo que decidir y DOCUMENTAR al implementarlo es el tokenizador. En
texto financiero los números y los guiones importan: un tokenizador que parta
«60,922» en «60» y «922», o que tire los guiones de «AI-related», destruye
exactamente la ventaja por la que se añade BM25. Ver `tokenizar` más abajo.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.dominio.protocolos import RepositorioFragmentos

# El corazón de la decisión del tokenizador.
#
# Un término es una tirada de letras o dígitos que puede llevar DENTRO un punto,
# una coma o un guion, siempre que a ambos lados haya de nuevo letra o dígito.
# Eso conserva "60,922", "10-k", "ai-related" y "u.s." como una sola unidad, y a
# la vez no se traga el "$", el espacio ni el punto final de una frase (que no
# tienen dígito/letra a la derecha). Es exactamente lo contrario de lo que hace
# un `str.split()` ingenuo o un tokenizador que parta por todo signo de
# puntuación, que son los dos que rompen el caso financiero.
_PATRON_TERMINO = re.compile(r"[a-z0-9]+(?:[.,\-][a-z0-9]+)*")


def tokenizar(texto: str) -> list[str]:
    """Parte un texto en términos para BM25.

    Args:
        texto: El texto a tokenizar.

    Returns:
        Los términos, en minúsculas, conservando los números completos con sus
        separadores de millar («60,922») y las palabras con guion («ai-related»)
        como una sola unidad. Mantener esos dos casos juntos es la razón de ser
        de este tokenizador: son las consultas donde BM25 gana al denso.
    """
    # Minúsculas primero para que "AI-related" y "ai-related" sean el mismo
    # término, y para que la consulta y el índice se comparen en el mismo caso.
    return _PATRON_TERMINO.findall(texto.lower())


class RecuperadorLexico:
    """BM25 sobre los fragmentos del corpus. P1: otra estrategia intercambiable.

    Implementa el mismo `Recuperador` que el denso, así que la fábrica lo enchufa
    igual y la tabla de ablación lo mide con el mismo runner. Indexa una sola vez
    en el constructor: BM25 es barato, pero re-tokenizar 1.749 fragmentos en cada
    búsqueda sería tirar trabajo a la basura sin motivo.
    """

    def __init__(
        self,
        fragmentos: RepositorioFragmentos,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        """Indexa los fragmentos con BM25.

        Args:
            fragmentos: El repositorio de fragmentos. Se conserva el ORDEN de
                `todos()`, que es el del índice FAISS, para que el híbrido pueda
                cruzar puntuaciones densas y léxicas por posición sin desalinear.
            k1: Saturación de frecuencia de término. El valor clásico (1.5) va
                bien; se expone para poder barrerlo en la ablación si hiciera
                falta, no para tocarlo a ojo.
            b: Normalización por longitud del documento (0.75, el valor clásico).
        """
        # Import perezoso: `rank_bm25` es una dependencia real y no queremos que
        # importar este módulo (que hace la fábrica siempre) obligue a tenerla si
        # la configuración activa es solo densa.
        from rank_bm25 import BM25Okapi

        # Materializamos el orden UNA vez y no volvemos a tocarlo: es el contrato
        # que empareja la fila i del índice con el fragmento i.
        self._fragmentos: tuple[Fragmento, ...] = tuple(fragmentos.todos())
        corpus_tokenizado = [tokenizar(f.texto) for f in self._fragmentos]
        # BM25Okapi guarda las estadísticas del corpus (idf, longitudes medias):
        # ahí está el coste, y por eso se hace en el constructor y no por búsqueda.
        self._bm25 = BM25Okapi(corpus_tokenizado, k1=k1, b=b)

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación."""
        return "lexico"

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` fragmentos con mayor puntuación BM25.

        Filtra igual que el denso: recorre los fragmentos en orden de puntuación
        y se queda con los `k` primeros que pasen los metadatos, en vez de cortar
        a `k` y filtrar después (que devolvería menos de `k`, o cero, si los
        mejores son de otra compañía). Devuelve lista vacía —nunca una
        excepción— cuando el filtro no deja nada.
        """
        import numpy as np

        puntuaciones = self.puntuaciones(consulta)
        # argsort ascendente y le damos la vuelta: de mayor a menor puntuación.
        orden = np.argsort(puntuaciones)[::-1]

        filtro = filtros or Filtros()
        salida: list[Fragmento] = []
        for posicion in orden:
            fragmento = self._fragmentos[int(posicion)]
            if not filtro.encaja(fragmento):
                continue
            salida.append(
                fragmento.con_puntuacion(round(float(puntuaciones[posicion]), 4))
            )
            if len(salida) >= k:
                break
        return salida

    def puntuaciones(self, consulta: str) -> Sequence[float]:
        """La puntuación BM25 de cada fragmento, en el orden del repositorio.

        La necesita el híbrido para fusionar sin volver a indexar, y la usa
        `recuperar` para ordenar. La consulta se tokeniza con EL MISMO
        `tokenizar` que el corpus: si se tokenizaran distinto, "60,922" en la
        pregunta no casaría con "60,922" en el fragmento y se perdería la única
        ventaja que BM25 tiene sobre el denso.
        """
        return list(self._bm25.get_scores(tokenizar(consulta)))
