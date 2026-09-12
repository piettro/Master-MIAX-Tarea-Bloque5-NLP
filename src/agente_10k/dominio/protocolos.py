"""Las fronteras del dominio. Todo lo externo entra por aquí.

Cada `Protocol` es un punto de sustitución que la práctica necesita de verdad:

* `Recuperador` (P1, Strategy) — denso, léxico e híbrido son intercambiables.
  Sin esto, medir `recall@k` de cuatro configuraciones distintas obliga a
  duplicar el runner, que es literalmente lo que pide la tarea 4 del enunciado.
* Los tres repositorios (P3, Repository) — las tools no leen ficheros ni saben
  qué es un parquet. Eso es lo que permite probarlas con fixtures diminutas y
  sin corpus.
* `ProveedorLLM` (P5, Adapter) — la suite entera corre con un `ProveedorFake`,
  sin red y sin clave de API.

Son `Protocol` y no clases base: el acoplamiento es estructural, no de
herencia, y una implementación no tiene que importar este módulo para valer.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable

from agente_10k.dominio.modelos import (
    Filtros,
    Fragmento,
    HechoXbrl,
    Seccion,
    UsoTokens,
)


@runtime_checkable
class Recuperador(Protocol):
    """Devuelve fragmentos relevantes para una consulta. P1: Strategy.

    Lo implementan el denso (FAISS), el léxico (BM25) y el híbrido (RRF), y lo
    envuelven los decoradores de filtro y de reescritura (P2). Un decorador
    recibe un `Recuperador` y devuelve un `Recuperador`: por eso la tabla de
    ablación sale de un bucle sobre configuraciones y no de código copiado.
    """

    @property
    def nombre(self) -> str:
        """Identificador corto para la traza y para la tabla de ablación."""
        ...

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` fragmentos más relevantes, ordenados de mayor a menor.

        Args:
            consulta: Qué buscar, en el idioma del corpus (inglés).
            filtros: Restricciones de metadatos, o `None` para no filtrar.
            k: Cuántos fragmentos devolver como máximo.

        Returns:
            Hasta `k` fragmentos con su `puntuacion` rellena. Lista vacía si no
            hay nada que encaje: nunca una excepción por no encontrar.
        """
        ...


@runtime_checkable
class RepositorioSecciones(Protocol):
    """Acceso a las 48 secciones completas. Lo que sirve `read_section`."""

    def obtener(self, ticker: str, fiscal_year: int, item: str) -> Seccion | None:
        """La sección pedida, o `None` si no está en el corpus."""
        ...

    def listar(self) -> list[Seccion]:
        """Todas las secciones. Es lo que alimenta `list_available`."""
        ...

    def tickers(self) -> list[str]:
        """Los tickers presentes en el corpus, ordenados."""
        ...

    def ejercicios(self, ticker: str | None = None) -> list[int]:
        """Los ejercicios disponibles, en total o para un emisor."""
        ...

    def items(self, ticker: str | None = None) -> list[str]:
        """Los items disponibles, en total o para un emisor."""
        ...


@runtime_checkable
class RepositorioFragmentos(Protocol):
    """Acceso a los 1.749 fragmentos. Lo que sirve `search_filings`."""

    def obtener(self, chunk_id: str) -> Fragmento | None:
        """El fragmento con ese `chunk_id`, o `None` si no existe."""
        ...

    def todos(self) -> Sequence[Fragmento]:
        """Todos los fragmentos, en el orden del índice.

        El orden importa: la fila *i* de los metadatos describe el vector *i*
        del índice FAISS. Reordenar aquí desalinea el retrieval sin dar ningún
        error y devuelve texto equivocado en silencio.
        """
        ...

    def filtrar(self, filtros: Filtros) -> list[Fragmento]:
        """Los fragmentos que pasan los filtros de metadatos."""
        ...

    def buscar_literal(self, texto: str) -> list[Fragmento]:
        """Los fragmentos que contienen `texto` literalmente.

        Es lo que usa el `recall@k` contra el ancla y el evaluador de cita: un
        fragmento cuenta como acierto si contiene el ancla, no si su
        `chunk_id` coincide con uno apuntado a mano.
        """
        ...


@runtime_checkable
class RepositorioXbrl(Protocol):
    """Acceso a los hechos numéricos. La fuente autorizada para cualquier cifra."""

    def obtener(self, ticker: str, fiscal_year: int, concept: str) -> HechoXbrl | None:
        """El hecho exacto, o `None` si esa compañía no reporta ese concepto."""
        ...

    def conceptos(self, ticker: str, fiscal_year: int) -> list[str]:
        """Los conceptos que SÍ existen para ese emisor y ejercicio.

        Es la mitad de la mejora T2: cuando el concepto pedido no está, la tool
        devuelve esta lista para que el agente se autocorrija en el siguiente
        turno en lugar de reintentar variantes a ciegas.
        """
        ...

    def hay_datos(self, ticker: str, fiscal_year: int) -> bool:
        """Si hay algún hecho para ese emisor y ejercicio."""
        ...

    def disponible(self) -> bool:
        """Si el repositorio tiene datos cargados.

        Existe porque `xbrl_facts.parquet` puede no estar todavía en `data/`.
        Las tools preguntan esto para dar un mensaje que dice qué falta, en
        lugar de un `None` indistinguible de un hueco real.
        """
        ...


@runtime_checkable
class ProveedorLLM(Protocol):
    """El cerebro del agente. P5: Factory + Adapter.

    Lo implementan los cuatro proveedores reales y el `ProveedorFake` de los
    tests, que devuelve trayectorias predefinidas sin tocar la red.
    """

    @property
    def modelo(self) -> str:
        """Identificador del modelo activo, para la traza."""
        ...

    @property
    def proveedor(self) -> str:
        """Identificador del proveedor activo, para la traza."""
        ...

    def chat(self) -> object:
        """El objeto de chat del framework, ya configurado.

        Devuelve `object` a propósito: el tipo concreto es de LangChain y el
        dominio no debe conocerlo. Quien lo necesita tipado es `agente/`.
        """
        ...

    def uso_ultima_llamada(self) -> UsoTokens:
        """Tokens y coste de la última llamada, leídos de los metadatos."""
        ...


@runtime_checkable
class Codificador(Protocol):
    """Convierte texto en vectores. Envuelve al modelo de embeddings.

    Está aparte del `Recuperador` porque el prefijo de BGE va en la CONSULTA y
    no en los fragmentos, y esa asimetría tiene que vivir en un solo sitio
    donde se pueda fijar con un test. Omitirlo no da error: solo recupera peor.
    """

    @property
    def dimension(self) -> int:
        """Dimensión de los vectores que produce."""
        ...

    def codificar_consulta(self, consulta: str) -> Sequence[float]:
        """El vector de una consulta, normalizado y CON el prefijo de BGE."""
        ...

    def codificar_pasajes(self, pasajes: Iterable[str]) -> Sequence[Sequence[float]]:
        """Los vectores de varios pasajes, normalizados y SIN prefijo."""
        ...
