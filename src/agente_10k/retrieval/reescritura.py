"""Decorador que reescribe la consulta con el LLM. FASE 3 — Alonso.

P2: Decorator, igual que el filtro. Reescribe la consulta antes de pasarla al
recuperador envuelto: la pregunta del usuario llega en español y en lenguaje de
persona, y el corpus está en inglés y en lenguaje de abogado. «¿Qué riesgos de
IA añadió Microsoft?» recupera peor que «risks related to the development,
deployment and use of artificial intelligence systems».

**Esta mejora CUESTA.** Añade una llamada al modelo por búsqueda, y eso entra en
la columna de coste y en la de latencia de la tabla del informe. Es el ejemplo
de libro de un arreglo razonable que puede no compensar: medirlo y contarlo, aun
si no compensa, es la sección más valiosa de la presentación. Por eso el coste
se contabiliza aparte (`uso_acumulado`) en lugar de esconderse.

La reescritura se cachea por consulta: reejecutar el golden set no puede costar
dinero dos veces. La caché es en memoria del proceso —suficiente para una
ejecución del set entero— y no persiste a disco; hacerlo persistente es una
mejora posible, pero añade una fuente de resultados viejos que preferimos no
arrastrar mientras iteramos.
"""

from __future__ import annotations

from agente_10k.dominio.modelos import Filtros, Fragmento, UsoTokens
from agente_10k.dominio.protocolos import ProveedorLLM, Recuperador

# El sistema de la reescritura vive aquí, versionado como el resto de prompts:
# le pedimos una consulta, no una conversación, y en el idioma y la jerga del
# corpus. "Devuelve solo la consulta" evita que el modelo conteste con prosa que
# luego contaminaría la búsqueda.
_SISTEMA_REESCRITURA = (
    "Rewrite the user's question as a concise English search query for a corpus "
    "of SEC 10-K filings. Use the terminology of the filings themselves. "
    "Return only the rewritten query, with no explanation."
)


class ConReescritura:
    """Envuelve un recuperador y reescribe la consulta antes de buscar."""

    def __init__(
        self,
        interno: Recuperador,
        proveedor: ProveedorLLM,
        cachear: bool = True,
    ) -> None:
        """Envuelve `interno` con una reescritura previa de la consulta.

        Args:
            interno: El recuperador envuelto.
            proveedor: Quien reescribe. En los tests, un `ProveedorFake`.
            cachear: Si se guarda la reescritura de cada consulta en memoria para
                no volver a llamar al modelo —ni a pagar— por la misma pregunta.
        """
        self._interno = interno
        self._proveedor = proveedor
        self._cachear = cachear
        self._cache: dict[str, str] = {}
        # Coste acumulado de TODAS las reescrituras reales (las que fueron a
        # modelo, no las servidas de caché). Empieza en cero y solo crece cuando
        # hay una llamada de verdad: así la columna de coste refleja el gasto
        # real y no cuenta dos veces la misma consulta.
        self._uso = UsoTokens()

    @property
    def nombre(self) -> str:
        """Identificador para la traza y la tabla de ablación."""
        return f"reescritura+{self._interno.nombre}"

    def reescribir(self, consulta: str) -> str:
        """La consulta reescrita para el corpus: en inglés y con su jerga.

        Si la consulta ya está en caché, se devuelve sin llamar al modelo y sin
        sumar coste. Si no, se llama una vez, se suma su uso y se guarda.
        """
        if self._cachear and consulta in self._cache:
            return self._cache[consulta]

        chat = self._proveedor.chat()
        respuesta = chat.invoke(  # type: ignore[attr-defined]
            [("system", _SISTEMA_REESCRITURA), ("human", consulta)]
        )
        # La respuesta puede ser un mensaje del framework (con `.content`) o —en
        # el `ProveedorFake` de los tests— la cadena tal cual. `getattr` cubre
        # los dos casos sin acoplar el dominio al tipo de LangChain.
        texto = getattr(respuesta, "content", respuesta)
        reescrita = str(texto).strip()

        # El coste se LEE del proveedor (usage_metadata), no se estima: es lo que
        # hace que la fila de la reescritura en la tabla cuadre con la factura.
        self._uso = self._uso + self._proveedor.uso_ultima_llamada()
        if self._cachear:
            self._cache[consulta] = reescrita
        return reescrita

    def recuperar(
        self,
        consulta: str,
        filtros: Filtros | None = None,
        k: int = 5,
    ) -> list[Fragmento]:
        """Los `k` mejores para la consulta reescrita.

        La reescritura solo cambia la CONSULTA; los filtros y `k` pasan intactos
        al recuperador envuelto.
        """
        return self._interno.recuperar(self.reescribir(consulta), filtros, k)

    def uso_acumulado(self) -> UsoTokens:
        """Tokens y coste que ha añadido la reescritura.

        Va a la columna de coste de la tabla de ablación: sin esto, la fila de
        la reescritura parecería gratis, que es justo el error que la práctica
        pide no cometer.
        """
        return self._uso
