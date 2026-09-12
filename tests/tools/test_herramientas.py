"""Las cuatro herramientas contra fixtures diminutas. Sin corpus, sin red."""

from __future__ import annotations

import pytest

from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.tools.implementacion import Herramientas


class RecuperadorDePrueba:
    """Devuelve los fragmentos que le pasen, filtrados. Sin modelo ni índice."""

    def __init__(self, fragmentos) -> None:
        self._fragmentos = list(fragmentos)
        self.ultima_consulta: str | None = None
        self.ultimos_filtros: Filtros | None = None

    @property
    def nombre(self) -> str:
        return "prueba"

    def recuperar(self, consulta, filtros=None, k=5):
        self.ultima_consulta = consulta
        self.ultimos_filtros = filtros
        f = filtros or Filtros()
        candidatos = [x for x in self._fragmentos if f.encaja(x)]
        return [x.con_puntuacion(0.9 - i * 0.1) for i, x in enumerate(candidatos[:k])]


class TestListAvailable:
    def test_nombra_los_emisores_del_corpus(self, herramientas):
        salida = herramientas.list_available()
        for ticker in ("NVDA", "MSFT", "AMZN"):
            assert ticker in salida

    def test_incluye_el_nombre_de_la_empresa(self, herramientas):
        assert "Microsoft Corporation" in herramientas.list_available()

    def test_nombra_ejercicios_e_items(self, herramientas):
        salida = herramientas.list_available()
        assert "2025" in salida
        assert "1A" in salida

    def test_avisa_de_la_trampa_del_ejercicio_fiscal(self, herramientas):
        assert "NO es el año de presentación" in herramientas.list_available()

    def test_cabe_de_sobra_en_400_tokens(self, herramientas, corpus_fixture):
        """Se llama al principio de muchas invocaciones: lo que gaste se paga
        en todas ellas."""
        assert len(herramientas.list_available()) < 400 * 4

    def test_sale_de_un_groupby_y_no_esta_escrito_a_mano(self, corpus_fixture):
        """Si estuviera hardcodeado, quitar una sección no cambiaría la salida."""
        from agente_10k.corpus.secciones import RepositorioSeccionesMemoria

        recortado = RepositorioSeccionesMemoria(
            [s for s in corpus_fixture.secciones.listar() if s.ticker != "AMZN"]
        )
        h = Herramientas(
            corpus_fixture.__class__(
                secciones=recortado,
                fragmentos=corpus_fixture.fragmentos,
                xbrl=corpus_fixture.xbrl,
                dir_corpus=corpus_fixture.dir_corpus,
            )
        )
        assert "AMZN" not in h.list_available()


class TestGetXbrlFact:
    def test_devuelve_la_cifra_con_unidad_y_concepto(self, herramientas):
        salida = herramientas.get_xbrl_fact("NVDA", 2024, "Revenues")
        assert "60,922,000,000" in salida
        assert "USD" in salida
        assert "Revenues" in salida
        assert "FY2024" in salida

    def test_incluye_la_fecha_de_cierre(self, herramientas):
        """El agente no debe tener que deducir el ejercicio de ninguna fecha,
        pero verla le confirma que consultó el que pedía la pregunta."""
        assert "2024-01-28" in herramientas.get_xbrl_fact("NVDA", 2024, "Revenues")

    def test_normaliza_el_ticker_a_mayusculas(self, herramientas):
        assert "60,922,000,000" in herramientas.get_xbrl_fact("nvda", 2024, "Revenues")

    def test_un_emisor_que_no_esta_remite_a_list_available(self, herramientas):
        salida = herramientas.get_xbrl_fact("TSLA", 2025, "Revenues")
        assert "No hay datos de TSLA" in salida
        assert "list_available" in salida

    def test_nunca_lanza_una_excepcion(self, herramientas):
        """Lo que ve el modelo es texto SIEMPRE, incluso cuando no hay dato."""
        assert isinstance(herramientas.get_xbrl_fact("XXXX", 1999, "Nada"), str)


class TestTrampaT2EnLaHerramienta:
    """Criterio de aceptación: pedir el concepto largo a NVDA sugiere Revenues."""

    def test_sugiere_el_sinonimo_sin_aplicarlo(self, herramientas):
        salida = herramientas.get_xbrl_fact(
            "NVDA", 2024, "RevenueFromContractWithCustomerExcludingAssessedTax"
        )
        assert "no reportó" in salida
        assert "Revenues" in salida
        assert "60,922,000,000" not in salida, (
            "La tool NO debe resolver el sinónimo por su cuenta: la decisión "
            "es del agente, o no aprende que cada emisor etiqueta distinto."
        )

    def test_lista_los_conceptos_que_si_existen(self, herramientas):
        salida = herramientas.get_xbrl_fact("NVDA", 2024, "InventadoNoExiste")
        assert "Conceptos disponibles" in salida
        assert "NetIncomeLoss" in salida

    def test_invita_a_volver_a_llamar(self, herramientas):
        """Es la mejora de mayor ratio valor/esfuerzo: convierte un callejón sin
        salida en una autocorrección en el turno siguiente."""
        salida = herramientas.get_xbrl_fact(
            "NVDA", 2024, "RevenueFromContractWithCustomerExcludingAssessedTax"
        )
        assert "Vuelve a llamar a get_xbrl_fact" in salida


class TestTrampaT3EnLaHerramienta:
    """Criterio de aceptación: AMZN/GrossProfit da un mensaje de hueco, no error."""

    def test_el_hueco_real_se_declara_como_tal(self, herramientas):
        salida = herramientas.get_xbrl_fact("AMZN", 2025, "GrossProfit")
        assert "NO reporta 'GrossProfit'" in salida
        assert "no es un error de escritura" in salida.lower()

    def test_el_hueco_real_induce_fuente_ninguna(self, herramientas):
        salida = herramientas.get_xbrl_fact("AMZN", 2025, "GrossProfit")
        assert 'fuente="ninguna"' in salida
        assert "cifra=null" in salida

    def test_el_hueco_real_prohibe_estimar(self, herramientas):
        """Dar una cifra plausible aquí es el peor fallo posible del sistema."""
        salida = herramientas.get_xbrl_fact("AMZN", 2025, "GrossProfit")
        assert "no debe estimarse" in salida

    def test_el_hueco_es_distinto_de_un_concepto_mal_escrito(self, herramientas):
        hueco = herramientas.get_xbrl_fact("AMZN", 2025, "GrossProfit")
        typo = herramientas.get_xbrl_fact("AMZN", 2025, "GrosProfit")
        assert hueco != typo
        assert 'fuente="ninguna"' not in typo

    def test_xbrl_no_cargado_no_se_confunde_con_un_hueco(self, corpus_fixture):
        """Si el agente lo tomara por un hueco respondería «no está» a preguntas
        que sí tienen respuesta."""
        from agente_10k.corpus.xbrl import RepositorioXbrlMemoria

        sin_xbrl = corpus_fixture.__class__(
            secciones=corpus_fixture.secciones,
            fragmentos=corpus_fixture.fragmentos,
            xbrl=RepositorioXbrlMemoria((), cargado=False),
            dir_corpus=corpus_fixture.dir_corpus,
        )
        salida = Herramientas(sin_xbrl).get_xbrl_fact("AMZN", 2025, "GrossProfit")
        assert "no está disponible en esta instalación" in salida
        assert "NO significa que el dato no exista" in salida


class TestSearchFilings:
    def test_devuelve_los_fragmentos_con_su_chunk_id(
        self, corpus_fixture, config_fixture
    ):
        recuperador = RecuperadorDePrueba(corpus_fixture.fragmentos.todos())
        h = Herramientas(corpus_fixture, recuperador, config_fixture)
        salida = h.search_filings(
            "AI misuse", ticker="MSFT", fiscal_year=2025, item="1A"
        )
        assert "[MSFT-2025-1A-0000]" in salida

    def test_pasa_los_filtros_al_recuperador(self, corpus_fixture, config_fixture):
        recuperador = RecuperadorDePrueba(corpus_fixture.fragmentos.todos())
        h = Herramientas(corpus_fixture, recuperador, config_fixture)
        h.search_filings("x", ticker="msft", fiscal_year="2025", item="1a")  # type: ignore[arg-type]
        assert recuperador.ultimos_filtros == Filtros(
            ticker="MSFT", fiscal_year=2025, item="1A"
        )

    def test_respeta_k(self, corpus_fixture, config_fixture):
        recuperador = RecuperadorDePrueba(corpus_fixture.fragmentos.todos())
        h = Herramientas(corpus_fixture, recuperador, config_fixture)
        salida = h.search_filings("x", ticker="MSFT", fiscal_year=2025, item="1A", k=2)
        assert salida.count("[MSFT-") == 2

    def test_sin_resultados_explica_que_aflojar(self, corpus_fixture, config_fixture):
        recuperador = RecuperadorDePrueba([])
        h = Herramientas(corpus_fixture, recuperador, config_fixture)
        salida = h.search_filings("nada")
        assert "Sin resultados" in salida
        assert "list_available" in salida

    def test_sin_recuperador_lo_dice_en_vez_de_romper(self, herramientas):
        salida = herramientas.search_filings("AI risk")
        assert "no está disponible" in salida
        assert isinstance(salida, str)

    def test_marca_los_fragmentos_que_traen_tabla(self, corpus_fixture, config_fixture):
        """Es la señal de que el número que se ve ahí viene de una tabla
        aplanada, que es exactamente de donde NO hay que leerlo."""
        recuperador = RecuperadorDePrueba(corpus_fixture.fragmentos.todos())
        h = Herramientas(corpus_fixture, recuperador, config_fixture)
        salida = h.search_filings("revenue", ticker="NVDA", fiscal_year=2024, item="7")
        assert "contiene tabla" in salida


class TestReadSection:
    def test_devuelve_el_texto_completo(self, herramientas):
        salida = herramientas.read_section("MSFT", 2025, "1A")
        assert "Our AI systems offer users powerful tools" in salida

    def test_la_cabecera_dice_el_tamano(self, herramientas):
        assert "55 tokens" in herramientas.read_section("MSFT", 2025, "1A")

    def test_avisa_cuando_el_contenido_viene_de_otro_item(self, herramientas):
        """NVIDIA deja sus estados financieros bajo el Item 15."""
        salida = herramientas.read_section("NVDA", 2024, "8")
        assert "Item 15" in salida

    def test_una_seccion_que_no_esta_remite_a_list_available(self, herramientas):
        salida = herramientas.read_section("TSLA", 2025, "1A")
        assert "No hay Item 1A de TSLA" in salida
        assert "list_available" in salida

    def test_trunca_y_lo_dice(self, herramientas):
        salida = herramientas.read_section("MSFT", 2025, "1A", max_tokens=10)
        assert "TRUNCADO" in salida
        assert "search_filings" in salida

    def test_no_trunca_si_cabe(self, herramientas):
        assert "TRUNCADO" not in herramientas.read_section("MSFT", 2025, "1A", 1000)

    def test_el_tope_por_defecto_sale_de_settings(self, corpus_fixture):
        from agente_10k.config import Settings

        cfg = Settings(dir_corpus=corpus_fixture.dir_corpus, max_tokens_seccion=10)
        h = Herramientas(corpus_fixture, None, cfg)
        assert "TRUNCADO" in h.read_section("MSFT", 2025, "1A")


class TestContratosDelegan:
    def test_las_funciones_del_contrato_usan_el_cinturon_instalado(
        self, cinturon_fixture
    ):
        from agente_10k.tools import contratos

        assert "MSFT" in contratos.list_available()
        assert "60,922,000,000" in contratos.get_xbrl_fact("NVDA", 2024, "Revenues")

    def test_usar_cinturon_none_lo_resetea(self, cinturon_fixture):
        from agente_10k.tools import contratos

        contratos.usar_cinturon(None)
        assert contratos._CINTURON is None


@pytest.mark.corpus
class TestContraCorpusReal:
    """Criterios de aceptación del prompt maestro, contra los datos de verdad."""

    def test_list_available_nombra_las_seis(self, corpus_real):
        salida = Herramientas(corpus_real).list_available()
        for ticker in ("AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA"):
            assert ticker in salida

    def test_amzn_grossprofit_es_un_mensaje_de_hueco_no_un_error(self, corpus_real):
        if not corpus_real.xbrl.disponible():
            pytest.skip("xbrl_facts.parquet no está montado")
        salida = Herramientas(corpus_real).get_xbrl_fact("AMZN", 2025, "GrossProfit")
        assert "NO reporta" in salida
        assert 'fuente="ninguna"' in salida

    def test_nvda_con_el_concepto_largo_sugiere_revenues(self, corpus_real):
        if not corpus_real.xbrl.disponible():
            pytest.skip("xbrl_facts.parquet no está montado")
        salida = Herramientas(corpus_real).get_xbrl_fact(
            "NVDA", 2024, "RevenueFromContractWithCustomerExcludingAssessedTax"
        )
        assert "Revenues" in salida

    def test_read_section_de_una_seccion_real(self, corpus_real):
        salida = Herramientas(corpus_real).read_section("MSFT", 2025, "7A")
        assert "MARKET RISK" in salida.upper()

    def test_las_cuatro_devuelven_str(self, corpus_real):
        h = Herramientas(corpus_real)
        assert isinstance(h.list_available(), str)
        assert isinstance(h.get_xbrl_fact("NVDA", 2024, "Revenues"), str)
        assert isinstance(h.search_filings("risk"), str)
        assert isinstance(h.read_section("NVDA", 2024, "7A"), str)


def test_un_fragmento_sin_puntuacion_se_renderiza_igual():
    from agente_10k.tools import formato

    f = Fragmento(
        chunk_id="X-2024-7-0000",
        ticker="X",
        fiscal_year=2024,
        item="7",
        posicion=0,
        texto="texto",
        n_tokens=1,
    )
    salida = formato.fragmentos([f])
    assert "[X-2024-7-0000]" in salida
    assert "similitud" not in salida
