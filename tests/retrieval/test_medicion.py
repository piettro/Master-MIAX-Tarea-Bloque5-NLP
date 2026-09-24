"""El runner de la tabla de ablación.

Se prueba la LÓGICA del runner —el recall contra el ancla, la decisión de pasar
o no los filtros, el conteo del coste de la reescritura, las filas
pendientes y el formato de la tabla— sin montar el índice FAISS ni el modelo de
embeddings. La costura es el parámetro `recuperador` de `medir_configuracion`,
que deja inyectar un espía en vez de fabricar uno real.
"""

from __future__ import annotations

from agente_10k.config import Settings
from agente_10k.dominio.modelos import Filtros, Fragmento, Pregunta, UsoTokens
from agente_10k.retrieval.medicion import (
    FilaAblacion,
    ejecutar_ablacion,
    escribir_ablacion,
    medir_configuracion,
    tabla_markdown,
)


def _fragmento(chunk_id: str, texto: str, ticker: str = "MSFT") -> Fragmento:
    """Un fragmento mínimo para las pruebas."""
    return Fragmento(
        chunk_id=chunk_id,
        ticker=ticker,
        fiscal_year=2025,
        item="1A",
        posicion=0,
        texto=texto,
        n_tokens=len(texto.split()),
    )


class _RecuperadorEspia:
    """Devuelve una lista fija y APUNTA con qué filtros lo llamaron.

    Es lo que permite comprobar la decisión clave: la fila base tiene que
    llamar sin filtros y la fila del filtro con ellos. Sin un espía, esa decisión
    —que es media tabla de ablación— no se podría verificar sin el corpus entero.
    """

    def __init__(
        self, fragmentos: list[Fragmento], uso: UsoTokens | None = None
    ) -> None:
        self._fragmentos = fragmentos
        self.filtros_vistos: list[Filtros | None] = []
        # `uso_acumulado` solo existe si se dio un uso, igual que en el real: un
        # recuperador que no es reescritura NO tiene el método, y así el runner
        # distingue una fila con coste de una sin coste por su mera presencia.
        if uso is not None:
            self.uso_acumulado = lambda: uso  # type: ignore[method-assign]

    @property
    def nombre(self) -> str:
        return "espia"

    def recuperar(self, consulta, filtros=None, k=5):
        self.filtros_vistos.append(filtros)
        return self._fragmentos[:k]


def _pregunta(pid: str, ancla: str | None, **extra) -> Pregunta:
    """Una pregunta de golden con el ancla que se quiera fijar."""
    base = {
        "id": pid,
        "pregunta": "da igual el texto: el espía devuelve lo mismo",
        "familia": "extractiva",
        "ancla_texto": ancla,
    }
    base.update(extra)
    return Pregunta.model_validate(base)


BASE = Settings(recuperador="denso")


class TestRecall:
    """El recall se mide contra el ANCLA de texto, no contra el chunk_id."""

    def test_acierta_cuando_el_ancla_esta_en_un_fragmento(self):
        frags = [_fragmento("c1", "AI-related risks may harm the business")]
        espia = _RecuperadorEspia(frags)
        fila = medir_configuracion(
            "x",
            {},
            None,
            [_pregunta("p1", "AI-related risks")],
            BASE,
            recuperador=espia,
        )
        assert fila.recall[1] == 1.0
        assert fila.puestos["p1"] == 1

    def test_falla_cuando_el_ancla_no_aparece(self):
        frags = [_fragmento("c1", "dividends and share repurchases")]
        espia = _RecuperadorEspia(frags)
        fila = medir_configuracion(
            "x",
            {},
            None,
            [_pregunta("p1", "AI-related risks")],
            BASE,
            recuperador=espia,
        )
        assert fila.recall[1] == 0.0
        assert fila.puestos["p1"] is None

    def test_solo_cuenta_preguntas_con_ancla(self):
        """Una pregunta sin ancla no mide retrieval y no entra en el recall."""
        frags = [_fragmento("c1", "AI-related risks")]
        espia = _RecuperadorEspia(frags)
        preguntas = [
            _pregunta("con", "AI-related risks"),
            _pregunta("sin", None, familia="numerica"),
        ]
        fila = medir_configuracion("x", {}, None, preguntas, BASE, recuperador=espia)
        assert fila.n_preguntas == 1  # solo la que tiene ancla

    def test_el_recall_depende_de_la_posicion_del_ancla(self):
        """Ancla en el 3.º fragmento: falla en k=1, acierta en k=3.

        Y el detalle por pregunta usa el MAYOR k, así que la marca como acierto
        aunque el recall@1 sea 0. Si el runner consultara con un `k` menor que el
        máximo, el ancla no llegaría y todo saldría a 0.
        """
        frags = [
            _fragmento("c1", "dividends and share repurchases"),
            _fragmento("c2", "competition in cloud services"),
            _fragmento("c3", "AI-related risks may harm the business"),
        ]
        espia = _RecuperadorEspia(frags)
        fila = medir_configuracion(
            "x",
            {},
            None,
            [_pregunta("p1", "AI-related risks")],
            BASE,
            ks=(1, 3),
            recuperador=espia,
        )
        assert fila.recall == {1: 0.0, 3: 1.0}
        assert fila.puestos["p1"] == 3


class TestDecisionDeFiltros:
    """La fila base no filtra; la fila del filtro sí."""

    def test_la_fila_base_no_pasa_filtros(self):
        espia = _RecuperadorEspia([_fragmento("c1", "AI-related risks")])
        medir_configuracion(
            "base",
            {"filtro_metadatos": False},
            None,
            [_pregunta("p1", "AI-related risks", ticker="MSFT")],
            BASE,
            recuperador=espia,
        )
        assert espia.filtros_vistos == [None]

    def test_la_fila_del_filtro_pasa_los_metadatos_de_la_pregunta(self):
        espia = _RecuperadorEspia([_fragmento("c1", "AI-related risks")])
        medir_configuracion(
            "filtro",
            {"filtro_metadatos": True},
            None,
            [_pregunta("p1", "AI-related risks", ticker="MSFT", fiscal_year=2025)],
            BASE,
            recuperador=espia,
        )
        visto = espia.filtros_vistos[0]
        assert visto is not None
        assert visto.ticker == "MSFT"
        assert visto.fiscal_year == 2025


class TestCoste:
    """Solo la reescritura cuesta; las demás filas van a 0."""

    def test_suma_el_coste_de_la_reescritura(self):
        espia = _RecuperadorEspia(
            [_fragmento("c1", "AI-related risks")],
            uso=UsoTokens(tokens_entrada=100, tokens_salida=20, coste_usd=0.004),
        )
        fila = medir_configuracion(
            "reescritura",
            {},
            None,
            [_pregunta("p1", "AI-related risks")],
            BASE,
            recuperador=espia,
        )
        assert fila.coste_medio_usd == 0.004  # 0.004 total / 1 pregunta

    def test_sin_reescritura_el_coste_es_cero(self):
        espia = _RecuperadorEspia([_fragmento("c1", "AI-related risks")])  # sin uso
        fila = medir_configuracion(
            "denso",
            {},
            None,
            [_pregunta("p1", "AI-related risks")],
            BASE,
            recuperador=espia,
        )
        assert fila.coste_medio_usd == 0.0


class TestFilaPendiente:
    """Una config que no se puede construir no aborta la tabla: sale pendiente."""

    def test_reescritura_sin_proveedor_sale_pendiente(self, corpus_fixture):
        fila = medir_configuracion(
            "reescritura",
            {"reescritura_consulta": True},
            corpus_fixture,
            [_pregunta("p1", "AI-related risks")],
            Settings(dir_corpus=corpus_fixture.dir_corpus),
        )
        assert fila.pendiente is not None
        assert "proveedor" in fila.pendiente.lower()


class TestTablaMarkdown:
    """El markdown remarca el mejor recall y muestra las filas pendientes."""

    def test_remarca_el_mejor_recall_de_cada_columna(self):
        filas = [
            FilaAblacion("base", {1: 0.40, 3: 0.60}, 0.01, 0.0, 10),
            FilaAblacion("mejor", {1: 0.70, 3: 0.60}, 0.02, 0.0, 10),
        ]
        md = tabla_markdown(filas, ks=(1, 3))
        assert "**0.70**" in md  # el mejor recall@1, en negrita
        assert "0.40" in md and "**0.40**" not in md  # el peor, sin negrita

    def test_muestra_la_fila_pendiente_sin_romperse(self):
        filas = [FilaAblacion("x", {}, 0.0, 0.0, 0, pendiente="falta proveedor")]
        md = tabla_markdown(filas, ks=(1,))
        assert "pendiente: falta proveedor" in md


class TestEscritura:
    """Escribe los tres ficheros con las cabeceras esperadas."""

    def test_escribe_md_csv_y_detalle(self, tmp_path):
        filas = [
            FilaAblacion(
                "denso",
                {1: 0.5, 3: 0.7},
                0.01,
                0.0,
                2,
                puestos={"p1": 1},
            )
        ]
        rutas = escribir_ablacion(filas, tmp_path, ks=(1, 3))
        nombres = {r.name for r in rutas}
        assert nombres == {
            "ablacion.md",
            "ablacion.csv",
            "ablacion_detalle.csv",
            "significancia.md",
        }
        assert all(r.is_file() for r in rutas)
        detalle = (tmp_path / "ablacion_detalle.csv").read_text(encoding="utf-8")
        assert "pregunta_id" in detalle and "p1" in detalle


class TestEjecutarAblacionCompleta:
    """El barrido produce una fila por configuración declarada, en orden.

    Se sustituye la fábrica por un espía para no montar el índice FAISS: lo que
    se prueba aquí es que el runner RECORRE las configuraciones de la fábrica,
    no el recuperador concreto (eso lo prueban los tests de cada pieza).
    """

    def test_una_fila_por_configuracion_declarada(self, monkeypatch):
        from agente_10k.retrieval import medicion
        from agente_10k.retrieval.fabrica import CONFIGURACIONES_ABLACION

        espia = _RecuperadorEspia([_fragmento("c1", "AI-related risks")])
        monkeypatch.setattr(medicion, "construir_recuperador", lambda *a, **k: espia)
        preg = _pregunta("p1", "AI-related risks", ticker="MSFT")
        filas = ejecutar_ablacion(None, [preg], Settings())

        assert len(filas) == len(CONFIGURACIONES_ABLACION)
        assert filas[0].nombre == "denso (base)"
