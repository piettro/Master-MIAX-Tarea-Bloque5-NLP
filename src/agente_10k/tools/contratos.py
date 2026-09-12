"""Las cuatro herramientas. CONTRATO C1: nombres y parámetros exactos.

Se puede reimplementar el cuerpo entero, añadir parámetros CON VALOR POR DEFECTO
y añadir herramientas nuevas. No se pueden renombrar ni cambiar los parámetros
existentes: las diez preguntas ciegas del día 24 se ejecutan contra estos
nombres y el evaluador de trayectoria los busca literalmente.

CONTRATO C2: los docstrings de este fichero no son documentación. Son lo ÚNICO
que ve el modelo para decidir si llama a una herramienta, y cambiarlos cambia el
comportamiento del sistema sin tocar una línea de código. Por eso están aquí,
juntos y comparables, y no repartidos junto a sus implementaciones: la decisión
que toma el modelo es entre las cuatro, y se escribe leyéndolas a la vez.

`tests/tools/test_docstrings.py` fija por escrito lo que cada uno tiene que
decir. Si alguien los acorta, la suite lo dice.
"""

from __future__ import annotations

from agente_10k.tools.implementacion import Herramientas, herramientas_por_defecto

_CINTURON: Herramientas | None = None


def _cinturon() -> Herramientas:
    """El cinturón del proceso, construido la primera vez que hace falta."""
    global _CINTURON  # noqa: PLW0603 -- caché perezosa, no estado compartido
    if _CINTURON is None:
        _CINTURON = herramientas_por_defecto()
    return _CINTURON


def usar_cinturon(cinturon: Herramientas | None) -> None:
    """Sustituye el cinturón activo. Para tests y para el runner de ablación.

    Pasar `None` lo vuelve a construir desde la configuración en la siguiente
    llamada, que es lo que hacen los tests al terminar para no contaminarse
    entre ellos.
    """
    global _CINTURON  # noqa: PLW0603
    _CINTURON = cinturon


# ---------------------------------------------------------------------------
# Las cuatro firmas
# ---------------------------------------------------------------------------


def list_available() -> str:
    """Lista qué compañías, ejercicios fiscales y secciones hay en el corpus.

    ÚSALA SIEMPRE antes de responder que un dato no existe, y antes de cualquier
    otra herramienta cuando no estés seguro de que la compañía o el ejercicio
    que te piden estén en el corpus. Es gratis e instantánea.

    El corpus contiene SOLO seis compañías y dos ejercicios. Si te preguntan por
    una compañía que no aparece en esta lista, la respuesta correcta es que no
    está en el corpus: no busques, no estimes y no uses lo que sepas de memoria.

    Returns:
        Una línea por compañía con su ticker, su nombre, los ejercicios
        fiscales disponibles y los items disponibles, más una nota sobre qué
        contiene cada item. Menos de 400 tokens.
    """
    return _cinturon().list_available()


def get_xbrl_fact(ticker: str, fiscal_year: int, concept: str) -> str:
    """Devuelve el valor EXACTO de una magnitud financiera reportada en XBRL.

    Devuelve la cifra tal y como la reportó la compañía, y es la fuente
    autorizada para cualquier cifra. ÚSALA SIEMPRE en lugar de leer
    un número del texto del informe, aunque el número aparezca en un fragmento
    que ya tengas delante: las tablas del 10-K llegan al texto aplanadas y
    partidas, y la prosa da cifras redondeadas ("$60.9 billion") junto a la
    exacta. Leer la cifra del texto cuando existe esta herramienta cuenta como
    error aunque el número salga bien.

    NO la uses para riesgos, estrategia, litigios ni comentarios de la
    dirección: para eso está search_filings.

    Args:
        ticker: Símbolo bursátil en mayúsculas, p. ej. 'NVDA'.
        fiscal_year: Ejercicio fiscal reportado, p. ej. 2024. Es el ejercicio,
            NO el año de presentación: las seis compañías cierran en meses
            distintos y el 10-K de un FY se presenta al año siguiente.
        concept: Concepto en taxonomía US-GAAP, p. ej. 'Revenues',
            'NetIncomeLoss', 'Assets', 'OperatingIncomeLoss',
            'RevenueFromContractWithCustomerExcludingAssessedTax'. El concepto
            del ingreso NO es el mismo en todas las compañías: no lo deduzcas
            por analogía con otra.

    Returns:
        El valor con su unidad, el concepto exacto, el ejercicio y la fecha de
        cierre.

        Si esa compañía no reportó ese concepto, devuelve un aviso con la lista
        de los conceptos que SÍ existen para ese emisor y ejercicio, y sugiere
        el sinónimo cuando lo hay: vuelve a llamarme con el nombre correcto.

        Si el concepto es un hueco REAL en us-gaap —hay compañías que no
        etiquetan ciertas magnitudes—, lo dice explícitamente. En ese caso el
        dato NO EXISTE: responde que no está en el corpus con fuente="ninguna"
        y cifra=null, y no lo estimes a partir de otras cifras.
    """
    return _cinturon().get_xbrl_fact(ticker, fiscal_year, concept)


def search_filings(
    query: str,
    ticker: str | None = None,
    fiscal_year: int | None = None,
    item: str | None = None,
    k: int = 5,
) -> str:
    """Busca fragmentos de texto relevantes en los informes 10-K del corpus.

    Úsala para preguntas CUALITATIVAS: qué riesgos declara una compañía, cómo
    cambiaron entre dos ejercicios, qué dice la dirección sobre sus resultados,
    litigios, estrategia.

    NO la uses para obtener cifras: para eso está get_xbrl_fact, que es exacta,
    gratuita y autorizada. Un número leído de un fragmento no está verificado.

    Para comparar dos ejercicios, llámame DOS VECES con el mismo `query` y
    distinto `fiscal_year`, y compara. Una sola búsqueda sin filtro devuelve
    fragmentos de los dos años mezclados y no permite decir qué cambió.

    El corpus está EN INGLÉS. Escribe `query` en inglés aunque la pregunta te
    llegue en español; traducirla es parte de tu trabajo.

    Args:
        query: Qué buscar, en lenguaje natural y en inglés.
        ticker: Filtra por compañía, p. ej. 'MSFT'. Ponlo siempre que la
            pregunta mencione una: sin filtro gastas el presupuesto de k en
            fragmentos de otras compañías.
        fiscal_year: Filtra por ejercicio fiscal, p. ej. 2025.
        item: Filtra por sección. Valores válidos: '1A' factores de riesgo,
            '7' discusión y análisis de la dirección, '7A' riesgo de mercado,
            '8' estados financieros. Para riesgos, '1A'.
        k: Cuántos fragmentos devolver. Por defecto 5. Súbelo solo si los
            primeros resultados no bastan: cada fragmento son unos 400 tokens.

    Returns:
        Hasta k fragmentos separados por '---', cada uno encabezado por su
        chunk_id entre corchetes, el emisor, el ejercicio, el item y la
        similitud. CITA SIEMPRE el chunk_id del fragmento en el que te apoyes:
        es lo que permite verificar la cita.

        Si no hay resultados devuelve un texto que lo dice y sugiere qué
        aflojar. Un resultado vacío no significa que el dato no exista.
    """
    return _cinturon().search_filings(query, ticker, fiscal_year, item, k)


def read_section(
    ticker: str,
    fiscal_year: int,
    item: str,
    max_tokens: int | None = None,
) -> str:
    """Devuelve el TEXTO COMPLETO de una sección de un 10-K.

    Es la herramienta CARA: puede devolver decenas de miles de tokens de una
    sola vez —el Item 1A de Meta ronda los 34.000— y se paga entera en cada
    llamada.

    Es el ÚLTIMO RECURSO. Úsala solo cuando ya hayas probado search_filings con
    filtros y los fragmentos sean insuficientes porque necesitas el contexto
    entero de una sección concreta. Nunca la uses para obtener una cifra: para
    eso está get_xbrl_fact. Nunca la llames dos veces seguidas sobre secciones
    distintas «por si acaso».

    Args:
        ticker: Símbolo bursátil en mayúsculas, p. ej. 'META'.
        fiscal_year: Ejercicio fiscal, p. ej. 2025.
        item: '1A' factores de riesgo, '7' discusión de la dirección,
            '7A' riesgo de mercado, '8' estados financieros.
        max_tokens: Tope opcional de tokens. Si lo pones, devuelvo el principio
            de la sección y aviso de cuánto queda fuera, en vez de la sección
            entera. Úsalo cuando solo necesites el comienzo.

    Returns:
        Una cabecera con el emisor, el ejercicio, el item y el tamaño en
        tokens, y a continuación el texto de la sección.

        Si esa sección no está en el corpus devuelve un aviso y te remite a
        list_available.
    """
    return _cinturon().read_section(ticker, fiscal_year, item, max_tokens)


HERRAMIENTAS = (list_available, get_xbrl_fact, search_filings, read_section)
"""Las cuatro funciones del CONTRATO C1, en el orden en que se presentan.

El orden no es decorativo: es el que se le pasa al modelo, y va de la más
barata a la más cara a propósito.
"""
