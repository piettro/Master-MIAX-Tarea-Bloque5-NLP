"""Decorador que filtra por metadatos ANTES de buscar.

P2: Decorator. Recibe un `Recuperador` y devuelve un `Recuperador`, de modo que
la mejora se activa y se desactiva por configuración y la fila «+ filtro de
metadatos» de la tabla de ablación sale del mismo runner que las demás.

**Antes, no después.** La implementación del profesor busca sobre el corpus
entero y descarta luego lo que no encaja: con `k=5` y un filtro por MSFT FY2025,
si los cinco primeros son de otras compañías, la llamada devuelve cero
resultados habiendo gastado el presupuesto entero. Filtrar antes significa
restringir el espacio de búsqueda a los fragmentos candidatos y que los cinco
que vuelven sean cinco útiles.
"""

from __future__ import annotations

from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.dominio.protocolos import Recuperador, RepositorioFragmentos


class ConFiltroMetadatos:
    """Envuelve un recuperador y le restringe el espacio de búsqueda."""

    def __init__(
        self,
        interno: Recuperador,
        fragmentos: RepositorioFragmentos,
    ) -> None:
        """Envuelve `interno` para que filtre antes de buscar.

        Args:
            interno: El recuperador envuelto.
            fragmentos: El repositorio, necesario para saber qué subconjunto
                cumple los filtros sin recorrer el índice entero.
        """
        self._interno = interno
        self._fragmentos = fragmentos

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación.

        Compone el nombre con el del recuperador que envuelve —"filtro+denso",
        "filtro+hibrido"— para que la traza diga exactamente qué pila se usó, no
        solo que había un filtro por medio.
        """
        return f"filtro+{self._interno.nombre}"

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` mejores dentro del subconjunto que cumple los filtros.

        Sin filtros no hay nada que restringir y se delega tal cual: el
        decorador debe ser transparente cuando no aporta, para que la fila base
        de la ablación y esta coincidan cuando la pregunta no lleva metadatos.

        Con filtros, la garantía es doble y por eso es robusta ante cualquier
        recuperador envuelto:

        1. Se le pasan los filtros al interno, para que un recuperador que sepa
           filtrar (el denso, el léxico) lo haga durante su propia pasada.
        2. Se sobre-muestrea al TAMAÑO DEL CORPUS y luego se recorta a los que de
           verdad pasan el filtro. Pedir el corpus entero es la única cota que
           garantiza el resultado aunque el interno IGNORE los filtros: si solo
           pidiéramos `len(permitidos)` candidatos y el interno devolviera los
           primeros del índice sin filtrar, podrían no caer ahí los del emisor
           pedido y saldrían menos de `k` —o cero—. Así los `k` que salen son
           siempre `k` del subconjunto, no del corpus entero.

        El coste de pedir de más es despreciable (1.749 fragmentos), y a cambio
        el resultado es correcto sea cual sea el recuperador de dentro.
        """
        filtro = filtros or Filtros()
        if filtro.vacios():
            return self._interno.recuperar(consulta, filtro, k)

        permitidos = {f.chunk_id for f in self._fragmentos.filtrar(filtro)}
        if not permitidos:
            # El emisor o el ejercicio no existen en el corpus: mejor lista vacía
            # que una búsqueda condenada. Que el agente lo interprete como
            # "no está" es justo lo que queremos, no un error.
            return []

        # El corpus entero como cota de sobre-muestreo (ver punto 2 del docstring).
        n_total = len(self._fragmentos.todos())
        candidatos = self._interno.recuperar(consulta, filtro, k=n_total)
        return [f for f in candidatos if f.chunk_id in permitidos][:k]
