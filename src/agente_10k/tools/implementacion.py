"""El cuerpo de las cuatro herramientas.

Vive en una clase y no en funciones sueltas para que los tests puedan montarla
con fixtures diminutas —tres secciones, veinte fragmentos, diez hechos XBRL— sin
corpus real, sin red y sin clave de API. Las funciones del CONTRATO C1 están en
`contratos.py` y delegan aquí.

La clase no construye nada: recibe los repositorios y el recuperador ya hechos.
Eso es lo que permite que la fase 3 enchufe su recuperador híbrido sin tocar una
línea de este fichero.
"""

from __future__ import annotations

from agente_10k.config import Settings, settings
from agente_10k.corpus import Corpus, cargar_corpus
from agente_10k.dominio.modelos import Filtros
from agente_10k.dominio.protocolos import Recuperador
from agente_10k.tools import formato


class Herramientas:
    """Las cuatro tools, con sus dependencias inyectadas."""

    def __init__(
        self,
        corpus: Corpus,
        recuperador: Recuperador | None = None,
        config: Settings | None = None,
    ) -> None:
        """Monta el cinturón sobre un corpus y un recuperador concretos."""
        self.corpus = corpus
        self.recuperador = recuperador
        self.config = config or settings()

    # -- list_available -----------------------------------------------------
    def list_available(self) -> str:
        """El universo del corpus, construido con un groupby, nunca a mano."""
        repo = self.corpus.secciones
        lineas = [
            (
                ticker,
                repo.empresa(ticker),
                repo.ejercicios(ticker),
                repo.items(ticker),
            )
            for ticker in repo.tickers()
        ]
        return formato.universo(lineas)

    # -- get_xbrl_fact ------------------------------------------------------
    def get_xbrl_fact(self, ticker: str, fiscal_year: int, concept: str) -> str:
        """La cifra exacta, o un texto que permite al agente autocorregirse.

        Cuatro salidas distintas, y la diferencia entre ellas es el trabajo de
        esta herramienta:

        1. el hecho, con unidad y concepto exacto;
        2. hueco REAL en us-gaap, que debe inducir `fuente="ninguna"`;
        3. concepto ausente que puede estar mal escrito, con los conceptos que
           sí existen y el sinónimo sugerido pero NO aplicado;
        4. emisor o ejercicio que no están en el corpus.
        """
        repo = self.corpus.xbrl
        if not repo.disponible():
            return formato.xbrl_no_cargado()

        ticker = ticker.strip().upper()
        concept = concept.strip()
        fiscal_year = int(fiscal_year)

        hecho = repo.obtener(ticker, fiscal_year, concept)
        if hecho is not None:
            return formato.hecho_xbrl(hecho)

        if not repo.hay_datos(ticker, fiscal_year):
            return formato.sin_emisor(ticker, fiscal_year)

        disponibles = repo.conceptos(ticker, fiscal_year)
        if repo.es_hueco_conocido(ticker, concept):
            return formato.hueco_real(ticker, fiscal_year, concept, disponibles)

        sugerencias = repo.sugerencias(ticker, fiscal_year, concept)
        return formato.concepto_ausente(
            ticker, fiscal_year, concept, disponibles, sugerencias
        )

    # -- search_filings -----------------------------------------------------
    def search_filings(
        self,
        query: str,
        ticker: str | None = None,
        fiscal_year: int | None = None,
        item: str | None = None,
        k: int = 5,
    ) -> str:
        """Los `k` fragmentos más relevantes, cada uno con su `chunk_id`."""
        if self.recuperador is None:
            return (
                "La búsqueda de texto no está disponible en esta instalación: "
                "falta el índice de fragmentos. Usa get_xbrl_fact para cifras "
                "o read_section si sabes qué sección leer."
            )
        filtros = Filtros(
            ticker=None if ticker is None else ticker.strip().upper(),
            fiscal_year=None if fiscal_year is None else int(fiscal_year),
            item=None if item is None else item.strip().upper(),
        )
        encontrados = self.recuperador.recuperar(query, filtros, max(1, int(k)))
        return formato.fragmentos(encontrados)

    # -- read_section -------------------------------------------------------
    def read_section(
        self,
        ticker: str,
        fiscal_year: int,
        item: str,
        max_tokens: int | None = None,
    ) -> str:
        """El texto completo de una sección, opcionalmente truncado."""
        seccion = self.corpus.secciones.obtener(
            ticker.strip().upper(), int(fiscal_year), item.strip().upper()
        )
        if seccion is None:
            return formato.seccion_ausente(ticker, int(fiscal_year), item)
        tope = max_tokens if max_tokens is not None else self.config.max_tokens_seccion
        return formato.seccion(seccion, tope)


def herramientas_por_defecto(config: Settings | None = None) -> Herramientas:
    """El cinturón montado desde la configuración del proceso.

    El recuperador se construye de forma perezosa y tolerante: si el índice o
    el modelo de embeddings no están disponibles, `search_filings` devuelve un
    texto que lo explica en vez de que falle el import del paquete. Las otras
    tres herramientas siguen funcionando.
    """
    cfg = config or settings()
    corpus = cargar_corpus(cfg)
    recuperador: Recuperador | None
    try:
        from agente_10k.retrieval.fabrica import construir_recuperador

        recuperador = construir_recuperador(corpus, cfg)
    except Exception:
        recuperador = None
    return Herramientas(corpus, recuperador, cfg)
