"""Los modelos del dominio. Ninguno sabe de LangChain, de FAISS ni de pandas.

Dos de ellos son contrato literal del enunciado y no se tocan:

* `RespuestaFinanciera` — CONTRATO C3. Se pueden añadir campos; no quitar ni
  renombrar los que hay. Es el `response_format` del agente y lo que leen los
  tres evaluadores.
* `Pregunta` — CONTRATO C4. El esquema exacto del golden set en JSONL.

El resto son piezas internas: fragmentos, secciones, hechos XBRL, trazas y
métricas. Todas inmutables (`frozen=True`): un fragmento recuperado o un hecho
XBRL leído del corpus no tiene por qué poder mutarse a mitad de una evaluación,
y que el tipo lo impida ahorra una clase entera de fallos difíciles de ver.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Vocabularios cerrados del corpus
# ---------------------------------------------------------------------------

Ticker = Literal["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA"]
"""Los seis emisores del corpus. Cerrado a propósito: preguntar por TSLA es un
caso legítimo que el agente debe declarar como fuera de corpus, no un ticker
que el sistema deba aceptar por descuido."""

Item = Literal["1A", "7", "7A", "8"]
"""Los cuatro epígrafes del 10-K que trae el corpus: 1A factores de riesgo,
7 discusión de la dirección, 7A riesgo de mercado, 8 estados financieros."""

Familia = Literal["extractiva", "numerica", "comparativa"]
"""Las tres familias del golden set.

El validador del profesor (celda 32 del notebook de la sesión 1) solo admite
estas tres. Las preguntas de HUECO REAL —Amazon sin `GrossProfit`— son
`numerica` o `comparativa` con `cifra_esperada=None`, y se detectan con
`Pregunta.es_hueco`, no con un cuarto valor de familia que haría que nuestro
golden set no pasara el validador oficial. Ver docs/decisiones.md, ADR-007."""

Fuente = Literal["xbrl", "texto", "ambas", "ninguna"]
"""De dónde sale el dato. `ninguna` cuando no está en el corpus: decirlo es
acertar, y es criterio de evaluación explícito del enunciado."""


# ---------------------------------------------------------------------------
# CONTRATO C3 — la salida del agente
# ---------------------------------------------------------------------------


class RespuestaFinanciera(BaseModel):
    """Respuesta trazable a una pregunta sobre informes 10-K.

    CONTRATO C3, literal del anexo del enunciado. Se pueden AÑADIR campos; no
    quitar ni renombrar los que hay. Todo lo añadido lleva valor por defecto,
    de modo que un modelo que rellene solo los ocho originales sigue validando.
    """

    respuesta: str = Field(description="Respuesta en prosa, breve y directa")
    cifra: float | None = Field(
        default=None, description="Valor numérico, si la pregunta pide uno"
    )
    unidad: str | None = Field(default=None, description="USD, shares, porcentaje…")
    ticker: str | None = None
    ejercicio: int | None = None
    fuente: Fuente = Field(
        description="De dónde sale el dato. 'ninguna' si no está en el corpus"
    )
    cita: str | None = Field(
        default=None,
        description="Texto literal del informe que respalda la respuesta",
    )
    chunk_id: str | None = Field(
        default=None,
        description="Identificador del fragmento citado, para verificar",
    )

    # --- añadidos nuestros, todos opcionales ------------------------------
    concept_xbrl: str | None = Field(
        default=None,
        description=(
            "Concepto US-GAAP consultado, si la cifra viene de XBRL. Permite "
            "al guardarraíl contrastar contra el hecho exacto en lugar de "
            "adivinar qué concepto quiso decir el modelo"
        ),
    )
    motivo_sin_dato: str | None = Field(
        default=None,
        description=(
            "Por qué no hay dato, cuando fuente='ninguna'. Distingue 'no está "
            "en el corpus' de 'no lo pude encontrar', que no es lo mismo"
        ),
    )


# ---------------------------------------------------------------------------
# CONTRATO C4 — el esquema del golden set
# ---------------------------------------------------------------------------


class Pregunta(BaseModel):
    """Una pregunta del golden set. CONTRATO C4, esquema exacto del enunciado.

    Los campos y su orden son los del anexo. `model_config` prohíbe campos
    extra: si alguien añade uno al JSONL, el validador lo dice en vez de
    ignorarlo en silencio.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    pregunta: str
    familia: Familia
    ticker: str | None = None
    fiscal_year: int | None = None
    respuesta_esperada: str | None = None
    cifra_esperada: float | None = None
    unidad: str | None = None
    concept_xbrl: str | None = None
    item_esperado: str | None = None
    ancla_texto: str | None = None
    ancla_inicio: int | None = None
    ancla_fin: int | None = None
    chunk_id_esperado: str | None = None
    herramienta_esperada: list[str] = Field(default_factory=list)
    autor: str | None = None

    @property
    def es_hueco(self) -> bool:
        """Si la respuesta correcta es que el dato NO está en el corpus.

        Una pregunta numérica cuya `cifra_esperada` es nula y que declara un
        `concept_xbrl` es una pregunta de hueco: se preguntó por una magnitud
        concreta y la compañía no la reporta. Dar una cifra plausible ahí es
        el peor fallo posible del sistema.
        """
        return (
            self.familia in {"numerica", "comparativa"}
            and self.cifra_esperada is None
            and self.concept_xbrl is not None
        )


# ---------------------------------------------------------------------------
# Piezas del corpus
# ---------------------------------------------------------------------------


class Fragmento(BaseModel):
    """Un trozo del corpus, con lo que hace falta para citarlo y verificarlo."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    ticker: str
    fiscal_year: int
    item: str
    posicion: int
    texto: str
    n_tokens: int
    contiene_tabla: bool = False
    inicio_car: int = 0
    fin_car: int = 0
    puntuacion: float | None = None

    def con_puntuacion(self, puntuacion: float) -> Fragmento:
        """El mismo fragmento con otra puntuación. No muta el original."""
        return self.model_copy(update={"puntuacion": puntuacion})


class Seccion(BaseModel):
    """Una sección completa de un 10-K: lo que sirve `read_section`."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    fiscal_year: int
    item: str
    texto: str
    n_tokens: int
    empresa: str | None = None
    titulo: str | None = None
    url: str | None = None
    item_origen: str | None = Field(
        default=None,
        description=(
            "Item del que salió realmente el contenido. NVIDIA no pone sus "
            "estados financieros bajo el Item 8 sino bajo el 15, y el corpus "
            "sirve el contenido correcto bajo la clave '8' dejando aquí "
            "constancia"
        ),
    )
    reconstruida: bool = Field(
        default=False,
        description=(
            "Si el texto se derivó de los fragmentos en vez de leerse de "
            "secciones.jsonl. Una sección reconstruida NO es literal en las "
            "fronteras de troceado: ver ADR-004"
        ),
    )


class HechoXbrl(BaseModel):
    """Un hecho numérico tal y como lo reportó la compañía. Fuente autorizada."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    fiscal_year: int
    concept: str
    value: float
    unit: str
    period_end: str | None = None
    form: str | None = None


class Filtros(BaseModel):
    """Filtros de metadatos de una búsqueda. Todos opcionales."""

    model_config = ConfigDict(frozen=True)

    ticker: str | None = None
    fiscal_year: int | None = None
    item: str | None = None

    def vacios(self) -> bool:
        """Si no hay nada por lo que filtrar."""
        return self.ticker is None and self.fiscal_year is None and self.item is None

    def encaja(self, fragmento: Fragmento) -> bool:
        """Si el fragmento pasa los filtros declarados."""
        if self.ticker is not None and fragmento.ticker != self.ticker:
            return False
        if self.fiscal_year is not None and fragmento.fiscal_year != self.fiscal_year:
            return False
        return not (self.item is not None and fragmento.item != self.item)


# ---------------------------------------------------------------------------
# Trazas — la entrada del evaluador de trayectoria y de la tabla del informe
# ---------------------------------------------------------------------------


class LlamadaHerramienta(BaseModel):
    """Una llamada a herramienta, con lo que se le pidió y lo que devolvió."""

    model_config = ConfigDict(frozen=True)

    nombre: str
    argumentos: dict[str, object] = Field(default_factory=dict)
    resultado: str = ""
    latencia_s: float | None = None
    error: str | None = None


class UsoTokens(BaseModel):
    """Tokens y coste de una invocación.

    El coste se LEE de los metadatos de uso que devuelve el proveedor; no se
    estima multiplicando tokens por una tarifa de memoria, que es como se
    consiguen tablas que no coinciden con la factura.
    """

    model_config = ConfigDict(frozen=True)

    tokens_entrada: int = 0
    tokens_salida: int = 0
    coste_usd: float | None = None

    @property
    def tokens_total(self) -> int:
        """Tokens de entrada más los de salida."""
        return self.tokens_entrada + self.tokens_salida

    def __add__(self, otro: UsoTokens) -> UsoTokens:
        """Suma dos usos, propagando `None` en el coste si falta en alguno."""
        coste: float | None
        if self.coste_usd is None and otro.coste_usd is None:
            coste = None
        else:
            coste = (self.coste_usd or 0.0) + (otro.coste_usd or 0.0)
        return UsoTokens(
            tokens_entrada=self.tokens_entrada + otro.tokens_entrada,
            tokens_salida=self.tokens_salida + otro.tokens_salida,
            coste_usd=coste,
        )


class Traza(BaseModel):
    """Todo lo que pasó durante una invocación. Serializable a JSON."""

    pregunta: str
    llamadas: list[LlamadaHerramienta] = Field(default_factory=list)
    uso: UsoTokens = Field(default_factory=UsoTokens)
    latencia_s: float = 0.0
    intervenciones_guardarrail: int = 0
    reintentos_guardarrail: int = 0
    limite_alcanzado: bool = False
    version_prompt: str = ""
    proveedor: str = ""
    modelo: str = ""
    config_retrieval: dict[str, object] = Field(default_factory=dict)
    error: str | None = None
    fecha: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def trayectoria(self) -> list[str]:
        """Los nombres de las herramientas, en el orden en que se llamaron."""
        return [ll.nombre for ll in self.llamadas]

    @property
    def n_llamadas(self) -> int:
        """Cuántas llamadas a herramienta hubo en esta invocación."""
        return len(self.llamadas)


# ---------------------------------------------------------------------------
# Evaluación
# ---------------------------------------------------------------------------

Veredicto = Literal["acierto", "fallo", "no_aplica"]
"""Resultado de un evaluador sobre una pregunta. `no_aplica` cuando la pregunta
no trae el campo que ese evaluador necesita: el día 24 pueden llegar diez
preguntas con solo `id` y `pregunta`, y degradar es obligatorio."""

EstadoTrayectoria = Literal[
    "camino_correcto",
    "camino_incorrecto_respuesta_correcta",
    "camino_incorrecto_respuesta_incorrecta",
    "no_aplica",
]
"""Los tres estados del evaluador de trayectoria, más el degradado.

`camino_incorrecto_respuesta_correcta` es el estado que da sentido a toda la
práctica: acertar por el camino equivocado cuenta como fallo."""


class VeredictoEvaluador(BaseModel):
    """El dictamen de un evaluador sobre una pregunta, con su porqué."""

    model_config = ConfigDict(frozen=True)

    veredicto: Veredicto
    motivo: str = ""
    detalle: dict[str, object] = Field(default_factory=dict)

    @property
    def acierto(self) -> bool:
        """Si el veredicto fue acierto."""
        return self.veredicto == "acierto"


class ResultadoPregunta(BaseModel):
    """Una pregunta evaluada: la respuesta, la traza y los tres veredictos."""

    pregunta_id: str
    familia: Familia | None = None
    es_hueco: bool = Field(
        default=False,
        description="Si la respuesta correcta era que el dato no está (columna hueco)",
    )
    respuesta_correcta: bool | None = Field(
        default=None,
        description=(
            "Si la respuesta es correcta sin mirar el camino. `None` cuando "
            "ningún evaluador pudo aplicarse: pregunta ciega sin esquema"
        ),
    )
    acierto: bool | None = Field(
        default=None,
        description=(
            "Respuesta correcta Y por el camino correcto. Es lo que cuenta en la "
            "tabla: acertar por el camino equivocado es fallo"
        ),
    )
    respuesta: RespuestaFinanciera | None = None
    traza: Traza | None = None
    cita: VeredictoEvaluador | None = None
    cifra: VeredictoEvaluador | None = None
    trayectoria: VeredictoEvaluador | None = None
    estado_trayectoria: EstadoTrayectoria = "no_aplica"
    alucinacion_sobre_hueco: bool = Field(
        default=False,
        description=(
            "El sistema dio una cifra donde la respuesta correcta era que el "
            "dato no está. Es el peor fallo posible y lleva categoría propia"
        ),
    )
    error: str | None = Field(
        default=None,
        description=(
            "Si la pregunta lanzó excepción. Se marca como fallo y la "
            "ejecución continúa: una pregunta rota no puede abortar las otras "
            "nueve el día 24"
        ),
    )


class Metricas(BaseModel):
    """Las columnas de la tabla del informe. Todas salen de código."""

    model_config = ConfigDict(frozen=True)

    n_preguntas: int = 0
    aciertos_por_familia: dict[str, float] = Field(default_factory=dict)
    recall_at_k: dict[int, float] = Field(default_factory=dict)
    coste_medio_usd: float | None = None
    latencia_media_s: float = 0.0
    llamadas_por_pregunta: float = 0.0
    tasa_camino_correcto: float = 0.0
    tasa_acierto_por_camino_equivocado: float = 0.0
    tasa_intervencion_guardarrail: float = 0.0
    tasa_recuperacion_guardarrail: float = 0.0
    alucinaciones_sobre_hueco: int = 0


class InformeEvaluacion(BaseModel):
    """El retorno de `evaluar()`. CONTRATO C5.

    Lleva el detalle por pregunta y el agregado. Se serializa entero a
    `resultados/<etiqueta>/`, que es lo que hace que ninguna cifra del PDF se
    escriba a mano.
    """

    etiqueta: str
    fecha: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ruta_preguntas: str = ""
    modelo: str = ""
    proveedor: str = ""
    commit: str | None = None
    configuracion: dict[str, object] = Field(default_factory=dict)
    resultados: list[ResultadoPregunta] = Field(default_factory=list)
    metricas: Metricas = Field(default_factory=Metricas)

    def __str__(self) -> str:
        """Una línea legible, para el REPL y para el día 24."""
        m = self.metricas
        coste = "?" if m.coste_medio_usd is None else f"{m.coste_medio_usd:.5f} $"
        return (
            f"InformeEvaluacion({self.etiqueta}: {m.n_preguntas} preguntas, "
            f"camino correcto {m.tasa_camino_correcto:.0%}, "
            f"coste medio {coste}, latencia media {m.latencia_media_s:.1f} s)"
        )
