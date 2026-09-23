"""Los TRES evaluadores del enunciado. FASE 5 — Raúl.

**1 · CITA.** Que la cita exista y que respalde de verdad lo que se afirma.
Cuatro comprobaciones distintas que se reportan por separado porque fallan por
motivos distintos: que el texto citado aparezca literalmente en el corpus (con
la normalización de `corpus/normalizacion.py`, documentada); que el `chunk_id`
declarado contenga esa cita —citar bien y atribuir mal es un fallo de
trazabilidad, no de recuperación—; que el fragmento pertenezca al emisor,
ejercicio y sección que la pregunta pedía, porque una cita correcta del
documento equivocado es un fallo; y que la cita esté junto al ancla del golden
set, porque una frase literal que no tiene nada que ver con la pregunta existe
pero no respalda nada.

**2 · CIFRA.** Que el número coincida con XBRL dentro de la tolerancia
DOCUMENTADA, importando el mismo objeto `Tolerancia` que usa el guardarraíl de
la fase 4. Un solo sitio, o los dos números se separan y la tabla deja de ser
defendible. Caso especial obligatorio: cuando la respuesta esperada es un hueco,
acertar significa `cifra=None` y `fuente="ninguna"`; dar una cifra plausible es
el peor fallo posible del sistema y lleva categoría propia.

**3 · TRAYECTORIA.** Que la respuesta pasara por la herramienta que tocaba.
Acertar por el camino equivocado cuenta como FALLO y se reporta en su propia
columna: es el criterio central de la práctica. La regla es de INCLUSIÓN
(`agente/trazas.py::cumple_trayectoria`), la misma que usa el profesor en la
sesión 2: una llamada de más es ineficiencia y se ve en la columna de llamadas
por pregunta; que falte la herramienta esperada es el fallo.

Todos degradan a `no_aplica` cuando la pregunta no trae el campo que necesitan.
El día 24 pueden llegar diez preguntas con solo `id` y `pregunta`, y un
evaluador que aborte por eso tumba la demostración entera.
"""

from __future__ import annotations

import re

from agente_10k.agente.trazas import cumple_trayectoria
from agente_10k.corpus.normalizacion import contiene, normalizar
from agente_10k.dominio.modelos import (
    EstadoTrayectoria,
    Familia,
    Fragmento,
    Pregunta,
    RespuestaFinanciera,
    Traza,
    VeredictoEvaluador,
)
from agente_10k.dominio.protocolos import (
    RepositorioFragmentos,
    RepositorioSecciones,
    RepositorioXbrl,
)
from agente_10k.dominio.tolerancia import TOLERANCIA, Tolerancia

MINIMO_CARACTERES_CITA = 20
"""Por debajo de esto una «cita» no prueba nada.

«revenue increased» aparece en decenas de fragmentos: encontrarla en el corpus
no dice que el agente haya leído el pasaje que responde la pregunta.
"""

VENTANA_RESPALDO = 600
"""Caracteres de distancia máxima entre la cita y el ancla en la misma sección.

El agente no tiene por qué citar exactamente la frase que eligió el autor de la
pregunta: la frase anterior o la siguiente del mismo párrafo respaldan lo mismo.
Seiscientos caracteres son un párrafo largo de un 10-K; más allá ya es otro
asunto de la misma sección.
"""

ESCALAS_SOSPECHOSAS = (1e3, 1e6, 1e9)
"""Factores con los que se comprueba si una cifra fallida está en otra escala.

Las tablas del 10-K van en millones y la tentación de copiar «60,922» tal cual
es grande. Detectarlo no lo convierte en acierto: lo convierte en un fallo con
diagnóstico, que es lo que hace falta para arreglarlo.
"""

_ELIPSIS = re.compile(r"\s*(?:\[\s*(?:\.\.\.|…)\s*\]|\.\.\.|…)\s*")
_COMILLAS_EXTREMOS = "\"'“”‘’«» "


def _veredicto(detalle: dict[str, object], exito: str) -> VeredictoEvaluador:
    """`acierto` si no hay ninguna causa de fallo en `detalle`; si no, `fallo`."""
    if not detalle:
        return VeredictoEvaluador(veredicto="acierto", motivo=exito)
    motivo = "; ".join(f"{causa}: {valor}" for causa, valor in detalle.items())
    return VeredictoEvaluador(veredicto="fallo", motivo=motivo, detalle=detalle)


def _no_aplica(motivo: str) -> VeredictoEvaluador:
    return VeredictoEvaluador(veredicto="no_aplica", motivo=motivo)


# ---------------------------------------------------------------------------
# 1 · CITA
# ---------------------------------------------------------------------------


def trozos_de_cita(cita: str) -> list[str]:
    """La cita partida por sus elipsis, sin comillas en los extremos.

    El modelo recorta: «Our AI systems … may misuse them» es una cita honesta de
    dos trozos del mismo pasaje. Cada trozo se busca por separado y los que no
    llegan a `MINIMO_CARACTERES_CITA` se descartan, porque un «and» suelto
    aparece en todas partes.
    """
    trozos = (t.strip(_COMILLAS_EXTREMOS) for t in _ELIPSIS.split(cita))
    return [t for t in trozos if len(normalizar(t)) >= MINIMO_CARACTERES_CITA]


class EvaluadorCita:
    """Evaluador 1: la cita existe y respalda lo que se afirma."""

    def __init__(
        self,
        fragmentos: RepositorioFragmentos,
        secciones: RepositorioSecciones | None = None,
        ventana_respaldo: int = VENTANA_RESPALDO,
    ) -> None:
        """Monta el evaluador sobre los repositorios del corpus.

        Args:
            fragmentos: Donde se comprueba el `chunk_id` y se busca la cita.
            secciones: Opcional. Con ellas se acepta una cita que cruce la
                frontera entre dos fragmentos y se mide la distancia al ancla
                dentro de la sección. Sin ellas, ambas cosas se miran solo
                dentro de un fragmento.
            ventana_respaldo: Ver `VENTANA_RESPALDO`.
        """
        self._fragmentos = fragmentos
        self._secciones = secciones
        self._ventana = ventana_respaldo
        self._textos_seccion: dict[tuple[str, int, str], str] | None = None

    def evaluar(
        self, pregunta: Pregunta, respuesta: RespuestaFinanciera
    ) -> VeredictoEvaluador:
        """El veredicto sobre la cita, con el motivo del fallo si lo hay.

        En `detalle` deja separadas las causas —`cita_no_literal`,
        `chunk_id_no_contiene_cita`, `documento_equivocado`,
        `no_respalda_ancla`, `sin_cita`, `sin_chunk_id`— para que el informe
        pueda decir cuál domina en vez de un porcentaje agregado.

        No aplica cuando la pregunta no trae ancla y la respuesta no cita texto:
        una cifra de XBRL no tiene frase del informe que la respalde, y exigirla
        castigaría justo el camino correcto.
        """
        cita = (respuesta.cita or "").strip()
        if not cita:
            if pregunta.ancla_texto:
                return _veredicto({"sin_cita": "la pregunta pide una cita"}, "")
            return _no_aplica("ni la pregunta trae ancla ni la respuesta cita")
        if not pregunta.ancla_texto and respuesta.fuente in {"xbrl", "ninguna"}:
            return _no_aplica(
                f"respuesta con fuente '{respuesta.fuente}': no cita texto del informe"
            )

        trozos = trozos_de_cita(cita)
        if not trozos:
            corta = f"cita de menos de {MINIMO_CARACTERES_CITA} caracteres"
            return _veredicto({"cita_no_literal": corta}, "")
        if not self._es_literal(trozos):
            return _veredicto(
                {"cita_no_literal": f"no aparece en el corpus: {cita[:80]!r}"}, ""
            )

        detalle: dict[str, object] = {}
        declarado = self._fragmento_declarado(respuesta.chunk_id, trozos, detalle)
        donde = [declarado] if declarado else self._fragmentos.buscar_literal(trozos[0])
        if donde and not any(_mismo_documento(pregunta, f) for f in donde):
            detalle["documento_equivocado"] = (
                f"la cita es de {_documento(donde[0])}, la pregunta pide "
                f"{_documento_pedido(pregunta)}"
            )
        if pregunta.ancla_texto and not self._respalda(pregunta, trozos):
            detalle["no_respalda_ancla"] = (
                f"la cita no está a menos de {self._ventana} caracteres del ancla"
            )
        return _veredicto(detalle, "cita literal, bien atribuida y junto al ancla")

    # --- piezas -------------------------------------------------------------

    def _es_literal(self, trozos: list[str]) -> bool:
        """Si todos los trozos aparecen en un fragmento o, si no, en una sección."""
        if all(self._fragmentos.buscar_literal(t) for t in trozos):
            return True
        textos = self._textos_por_seccion().values()
        return all(any(normalizar(t) in texto for texto in textos) for t in trozos)

    def _fragmento_declarado(
        self, chunk_id: str | None, trozos: list[str], detalle: dict[str, object]
    ) -> Fragmento | None:
        """El fragmento del `chunk_id`, si existe y contiene la cita.

        Anota en `detalle` por qué no vale cuando no vale. Citar bien y atribuir
        mal es fallo de trazabilidad: la cita existe, pero no se puede verificar
        desde donde el agente dice que la sacó.
        """
        if not chunk_id:
            detalle["sin_chunk_id"] = (
                "la respuesta cita texto sin decir de qué fragmento"
            )
            return None
        fragmento = self._fragmentos.obtener(chunk_id)
        if fragmento is None:
            detalle["chunk_id_no_contiene_cita"] = f"el chunk_id {chunk_id} no existe"
            return None
        if not all(contiene(fragmento.texto, t) for t in trozos):
            detalle["chunk_id_no_contiene_cita"] = (
                f"{chunk_id} existe pero no contiene la cita"
            )
            return None
        return fragmento

    def _respalda(self, pregunta: Pregunta, trozos: list[str]) -> bool:
        """Si la cita es el ancla, la contiene o está a menos de la ventana."""
        ancla = pregunta.ancla_texto or ""
        cita = " ".join(trozos)
        if contiene(cita, ancla) or any(contiene(ancla, t) for t in trozos):
            return True
        return any(
            _distancia(texto, ancla, trozos[0]) <= self._ventana
            for texto in self._textos_candidatos(pregunta, trozos[0])
        )

    def _textos_candidatos(self, pregunta: Pregunta, trozo: str) -> list[str]:
        """Donde medir la distancia entre cita y ancla, ya normalizado.

        La sección de la pregunta si hay secciones y se sabe cuál es; si no, los
        fragmentos que contienen la cita.
        """
        if self._secciones is not None and pregunta.ticker and pregunta.fiscal_year:
            return [
                texto
                for (ticker, fy, item), texto in self._textos_por_seccion().items()
                if ticker == pregunta.ticker
                and fy == pregunta.fiscal_year
                and (pregunta.item_esperado is None or item == pregunta.item_esperado)
            ]
        return [normalizar(f.texto) for f in self._fragmentos.buscar_literal(trozo)]

    def _textos_por_seccion(self) -> dict[tuple[str, int, str], str]:
        """Las secciones normalizadas, calculadas una vez y guardadas."""
        if self._textos_seccion is None:
            self._textos_seccion = (
                {
                    (s.ticker, s.fiscal_year, s.item): normalizar(s.texto)
                    for s in self._secciones.listar()
                }
                if self._secciones is not None
                else {}
            )
        return self._textos_seccion


def _distancia(texto: str, ancla: str, trozo: str) -> float:
    """Caracteres entre el ancla y la cita dentro de `texto` ya normalizado.

    `inf` si alguna de las dos no está. Se mide de borde a borde, no de inicio a
    inicio: dos frases contiguas están a distancia cero.
    """
    a, c = normalizar(ancla), normalizar(trozo)
    ia, ic = texto.find(a), texto.find(c)
    if ia < 0 or ic < 0:
        return float("inf")
    if ic >= ia:
        return max(0, ic - (ia + len(a)))
    return max(0, ia - (ic + len(c)))


def _mismo_documento(pregunta: Pregunta, fragmento: Fragmento) -> bool:
    """Si el fragmento es del emisor, ejercicio y sección que se pedían.

    Solo se comparan los campos que la pregunta declara: una pregunta ciega sin
    `item_esperado` no puede suspender por la sección.
    """
    return (
        (pregunta.ticker is None or fragmento.ticker == pregunta.ticker)
        and (
            pregunta.fiscal_year is None
            or fragmento.fiscal_year == pregunta.fiscal_year
        )
        and (pregunta.item_esperado is None or fragmento.item == pregunta.item_esperado)
    )


def _documento(fragmento: Fragmento) -> str:
    return f"{fragmento.ticker} FY{fragmento.fiscal_year} Item {fragmento.item}"


def _documento_pedido(pregunta: Pregunta) -> str:
    partes = [
        pregunta.ticker or "?",
        f"FY{pregunta.fiscal_year}" if pregunta.fiscal_year else "FY?",
    ]
    if pregunta.item_esperado:
        partes.append(f"Item {pregunta.item_esperado}")
    return " ".join(partes)


# ---------------------------------------------------------------------------
# 2 · CIFRA
# ---------------------------------------------------------------------------


def unidad_canonica(unidad: str | None) -> str | None:
    """La unidad reducida a una categoría comparable.

    El modelo escribe «USD», «$», «dólares» o «millones de dólares» para lo
    mismo. Lo que importa es no confundir dinero con acciones o con porcentaje;
    la escala (millones) la juzga la cifra, no la etiqueta.
    """
    texto = normalizar(unidad or "").lower()
    if not texto:
        return None
    if "%" in texto or "porcent" in texto or "percent" in texto:
        return "porcentaje"
    if any(m in texto for m in ("per share", "por acci", "/share", "/acci")):
        return "USD/accion"
    if "share" in texto or "acci" in texto:
        return "acciones"
    if any(m in texto for m in ("usd", "$", "dólar", "dolar", "dollar")):
        return "USD"
    return texto


class EvaluadorCifra:
    """Evaluador 2: la cifra coincide con XBRL dentro de la tolerancia."""

    def __init__(
        self,
        xbrl: RepositorioXbrl,
        tolerancia: Tolerancia | None = None,
    ) -> None:
        """Monta el evaluador con la MISMA tolerancia que el guardarraíl.

        Args:
            xbrl: La fuente autorizada. Manda sobre `cifra_esperada` cuando la
                pregunta declara concepto, emisor y ejercicio.
            tolerancia: Por defecto, `dominio.tolerancia.TOLERANCIA`: la
                instancia que importa también el guardarraíl.
        """
        self._xbrl = xbrl
        self._tolerancia = tolerancia or TOLERANCIA

    def evaluar(
        self, pregunta: Pregunta, respuesta: RespuestaFinanciera
    ) -> VeredictoEvaluador:
        """El veredicto sobre la cifra y sobre la coherencia de la unidad."""
        if self._es_hueco(pregunta):
            return self._evaluar_hueco(respuesta)
        esperada = self._esperada(pregunta)
        if esperada is None:
            return _no_aplica("la pregunta no pide ninguna cifra")
        if respuesta.cifra is None:
            return _veredicto(
                {"sin_cifra": f"se esperaba {esperada:,.0f} y no se dio cifra"}, ""
            )

        detalle: dict[str, object] = {}
        if not self._tolerancia.coincide(respuesta.cifra, esperada):
            detalle["cifra_no_coincide"] = (
                f"{respuesta.cifra:,.0f} frente a {esperada:,.0f} "
                f"({self._tolerancia.desvio_relativo(respuesta.cifra, esperada):.2%})"
            )
            escala = self._escala_probable(respuesta.cifra, esperada)
            if escala:
                detalle["escala"] = f"coincide multiplicada por {escala:g}"
        pedida, dada = (
            unidad_canonica(pregunta.unidad),
            unidad_canonica(respuesta.unidad),
        )
        if pedida and dada and pedida != dada:
            detalle["unidad_incoherente"] = f"se pedía {pedida} y se dio {dada}"
        return _veredicto(
            detalle, f"coincide con XBRL ({self._tolerancia.describir()})"
        )

    def es_alucinacion_sobre_hueco(
        self, pregunta: Pregunta, respuesta: RespuestaFinanciera
    ) -> bool:
        """Si se dio una cifra donde la respuesta correcta era que no hay dato."""
        return self._es_hueco(pregunta) and respuesta.cifra is not None

    # --- piezas -------------------------------------------------------------

    def _evaluar_hueco(self, respuesta: RespuestaFinanciera) -> VeredictoEvaluador:
        detalle: dict[str, object] = {}
        if respuesta.cifra is not None:
            detalle["alucinacion_sobre_hueco"] = (
                f"dio {respuesta.cifra:,.0f} donde la compañía no reporta el dato"
            )
        if respuesta.fuente != "ninguna":
            detalle["fuente_no_ninguna"] = f"fuente='{respuesta.fuente}'"
        return _veredicto(detalle, "declaró que el dato no está en el corpus")

    def _hecho(self, pregunta: Pregunta) -> float | None:
        """El valor XBRL del concepto de la pregunta, si se puede consultar."""
        if not (
            pregunta.concept_xbrl
            and pregunta.ticker
            and pregunta.fiscal_year
            and self._xbrl.disponible()
        ):
            return None
        hecho = self._xbrl.obtener(
            pregunta.ticker, pregunta.fiscal_year, pregunta.concept_xbrl
        )
        return None if hecho is None else hecho.value

    def _esperada(self, pregunta: Pregunta) -> float | None:
        """La cifra contra la que se compara: XBRL si se puede, si no el golden.

        El enunciado dice que la cifra se contrasta con XBRL. El golden set se
        verificó contra XBRL al escribirlo, así que en el caso normal las dos
        coinciden; si algún día no, manda la fuente autorizada.
        """
        hecho = self._hecho(pregunta)
        return hecho if hecho is not None else pregunta.cifra_esperada

    def _es_hueco(self, pregunta: Pregunta) -> bool:
        """Hueco según la pregunta, salvo que XBRL diga que el dato SÍ existe.

        Una pregunta marcada como hueco cuyo concepto sí se reporta tiene el
        golden set mal escrito; el validador lo avisa y aquí no se castiga al
        agente por dar la cifra correcta.
        """
        return pregunta.es_hueco and self._hecho(pregunta) is None

    def _escala_probable(self, afirmada: float, esperada: float) -> float | None:
        for factor in ESCALAS_SOSPECHOSAS:
            if self._tolerancia.coincide(afirmada * factor, esperada):
                return factor
        return None


# ---------------------------------------------------------------------------
# 3 · TRAYECTORIA
# ---------------------------------------------------------------------------


class EvaluadorTrayectoria:
    """Evaluador 3: la respuesta pasó por la herramienta que tocaba."""

    def evaluar(self, pregunta: Pregunta, traza: Traza) -> VeredictoEvaluador:
        """El veredicto sobre el camino recorrido.

        Acierto si todas las herramientas de `herramienta_esperada` aparecen en
        la trayectoria (regla de inclusión). En `detalle` quedan las usadas, las
        que faltan y si hubo una `read_section` que la pregunta no pedía, que es
        la llamada cara y la que más mueve la columna de coste.
        """
        esperadas = pregunta.herramienta_esperada
        if not esperadas:
            return _no_aplica("la pregunta no declara herramienta_esperada")
        usadas = traza.trayectoria
        if cumple_trayectoria(usadas, esperadas):
            return VeredictoEvaluador(
                veredicto="acierto",
                motivo=f"pasó por {', '.join(esperadas)}",
                detalle=self._info(esperadas, usadas),
            )
        faltan = [h for h in esperadas if h not in usadas]
        return VeredictoEvaluador(
            veredicto="fallo",
            motivo=f"no pasó por {', '.join(faltan)}; usó {usadas or 'ninguna'}",
            detalle={"faltan": faltan, **self._info(esperadas, usadas)},
        )

    def clasificar(
        self,
        pregunta: Pregunta,
        traza: Traza,
        respuesta_correcta: bool,
    ) -> EstadoTrayectoria:
        """Los tres estados del enunciado.

        `camino_correcto`, `camino_incorrecto_respuesta_correcta` —el que da
        sentido a toda la práctica— y `camino_incorrecto_respuesta_incorrecta`.
        `no_aplica` si la pregunta no declara el camino.
        """
        veredicto = self.evaluar(pregunta, traza)
        if veredicto.veredicto == "no_aplica":
            return "no_aplica"
        if veredicto.acierto:
            return "camino_correcto"
        if respuesta_correcta:
            return "camino_incorrecto_respuesta_correcta"
        return "camino_incorrecto_respuesta_incorrecta"

    @staticmethod
    def _info(esperadas: list[str], usadas: list[str]) -> dict[str, object]:
        info: dict[str, object] = {"usadas": list(usadas)}
        if "read_section" in usadas and "read_section" not in esperadas:
            info["lectura_cara_innecesaria"] = usadas.count("read_section")
        return info


# ---------------------------------------------------------------------------
# Qué es «respuesta correcta»
# ---------------------------------------------------------------------------


def es_respuesta_correcta(
    familia: Familia | None,
    cita: VeredictoEvaluador | None,
    cifra: VeredictoEvaluador | None,
) -> bool | None:
    """Si la respuesta es correcta, sin mirar todavía el camino.

    * numérica: manda la cifra (el hueco incluido: acertar es no dar cifra);
    * extractiva: manda la cita;
    * comparativa: tienen que acertar las dos, porque la pregunta pide la
      variación Y su explicación, y acertar media pregunta no es acertarla.

    Si un evaluador no aplica, decide el otro. `None` si no aplica ninguno: es
    el caso de una pregunta ciega que llega sin esquema, y ahí no se inventa un
    veredicto.
    """
    aplicables = [v for v in (cita, cifra) if v and v.veredicto != "no_aplica"]
    if not aplicables:
        return None
    if familia == "numerica" and cifra and cifra.veredicto != "no_aplica":
        return cifra.acierto
    if familia == "extractiva" and cita and cita.veredicto != "no_aplica":
        return cita.acierto
    return all(v.acierto for v in aplicables)
