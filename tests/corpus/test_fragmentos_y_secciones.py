"""Los repositorios de fragmentos y secciones, y la trampa T1 del troceado."""

from __future__ import annotations

import pytest

from agente_10k.corpus.normalizacion import contiene, normalizar
from agente_10k.corpus.secciones import RepositorioSeccionesMemoria
from agente_10k.dominio.modelos import Filtros


class TestRepositorioFragmentos:
    def test_carga_los_veinte_de_la_fixture(self, repo_fragmentos):
        assert len(repo_fragmentos) == 20

    def test_obtiene_por_chunk_id(self, repo_fragmentos):
        f = repo_fragmentos.obtener("MSFT-2025-1A-0001")
        assert f is not None
        assert f.ticker == "MSFT"
        assert "Our AI systems offer users powerful tools" in f.texto

    def test_un_chunk_id_inventado_devuelve_none(self, repo_fragmentos):
        assert repo_fragmentos.obtener("XXXX-2099-1A-9999") is None

    def test_filtra_por_metadatos(self, repo_fragmentos):
        filtrados = repo_fragmentos.filtrar(
            Filtros(ticker="MSFT", fiscal_year=2025, item="1A")
        )
        assert {f.chunk_id for f in filtrados} == {
            "MSFT-2025-1A-0000",
            "MSFT-2025-1A-0001",
            "MSFT-2025-1A-0002",
        }

    def test_sin_filtros_devuelve_todo(self, repo_fragmentos):
        assert len(repo_fragmentos.filtrar(Filtros())) == 20

    def test_el_orden_de_todos_es_el_de_carga(self, repo_fragmentos):
        """Fila i <-> vector i. Reordenar desalinea el retrieval en silencio."""
        assert repo_fragmentos.todos()[0].chunk_id == "NVDA-2024-1A-0000"
        assert repo_fragmentos.todos()[-1].chunk_id == "AMZN-2025-8-0000"


class TestBusquedaLiteral:
    """Es lo que usan el recall@k contra el ancla y el evaluador de cita."""

    def test_encuentra_un_ancla_literal(self, repo_fragmentos):
        encontrados = repo_fragmentos.buscar_literal(
            "Our AI systems offer users powerful tools and capabilities."
        )
        assert [f.chunk_id for f in encontrados] == ["MSFT-2025-1A-0001"]

    def test_un_ancla_solapada_aparece_en_dos_fragmentos(self, repo_fragmentos):
        """Los chunks solapan 80 tokens: la misma frase está en dos chunk_id.

        Por eso el recall se mide contra el ancla y no contra un chunk_id
        apuntado a mano: cuál de los dos «es» el correcto es arbitrario.
        """
        encontrados = repo_fragmentos.buscar_literal("Third parties may misuse them.")
        assert {f.chunk_id for f in encontrados} == {
            "MSFT-2025-1A-0001",
            "MSFT-2025-1A-0002",
        }

    def test_tolera_saltos_de_linea_del_troceador(self, repo_fragmentos):
        """El ancla se copia de un PDF y trae el salto donde el corpus no lo tiene."""
        encontrados = repo_fragmentos.buscar_literal(
            "ITEM 1A. RISK FACTORS\nIssues in the development, deployment, and use"
        )
        assert [f.chunk_id for f in encontrados] == ["MSFT-2025-1A-0000"]

    def test_un_ancla_inventada_no_aparece(self, repo_fragmentos):
        assert repo_fragmentos.buscar_literal("esto no está en ningún 10-K") == []

    def test_un_ancla_vacia_no_casa_con_todo(self, repo_fragmentos):
        """`"" in texto` es siempre True: sin esta guarda, toda pregunta sin
        ancla contaría como acierto de retrieval."""
        assert repo_fragmentos.buscar_literal("") == []
        assert repo_fragmentos.buscar_literal("   ") == []


class TestNormalizacion:
    def test_colapsa_espacios_y_saltos(self):
        assert normalizar("a  b\n\tc") == "a b c"

    def test_unifica_comillas_tipograficas(self):
        assert normalizar("“AI”") == normalizar('"AI"')

    def test_unifica_guiones_largos(self):
        assert normalizar("AI—related") == normalizar("AI-related")

    def test_conserva_mayusculas_y_puntuacion(self):
        """«Revenue» y «revenue» son cosas distintas en una tabla financiera."""
        assert normalizar("Revenue") != normalizar("revenue")
        assert "." in normalizar("Fin.")

    def test_contiene_normaliza_los_dos_lados(self):
        assert contiene("We use  derivatives\ninstruments", "derivatives instruments")

    def test_contiene_con_aguja_vacia_es_falso(self):
        assert not contiene("cualquier cosa", "")


class TestRepositorioSecciones:
    def test_lee_las_tres_de_la_fixture(self, repo_secciones):
        assert len(repo_secciones) == 3
        assert repo_secciones.tickers() == ["AMZN", "MSFT", "NVDA"]

    def test_obtiene_una_seccion(self, repo_secciones):
        s = repo_secciones.obtener("MSFT", 2025, "1A")
        assert s is not None
        assert s.empresa == "Microsoft Corporation"
        assert not s.reconstruida

    def test_una_seccion_que_no_esta_devuelve_none(self, repo_secciones):
        assert repo_secciones.obtener("TSLA", 2025, "1A") is None

    def test_conserva_item_origen(self, repo_secciones):
        """NVIDIA deja sus estados financieros bajo el Item 15, no el 8."""
        s = repo_secciones.obtener("NVDA", 2024, "8")
        assert s is not None
        assert s.item_origen == "15"

    def test_los_items_van_en_el_orden_del_10k(self, repo_fragmentos):
        repo = RepositorioSeccionesMemoria.desde_fragmentos(repo_fragmentos.todos())
        assert repo.items("NVDA") == ["1A", "7", "7A", "8"]


class TestReconstruccionDeSecciones:
    """ADR-004: derivar secciones de los fragmentos funciona, pero no es literal."""

    def test_reconstruye_una_seccion_por_grupo(self, repo_fragmentos):
        repo = RepositorioSeccionesMemoria.desde_fragmentos(repo_fragmentos.todos())
        assert len(repo) == 15
        assert repo.alguna_reconstruida()

    def test_recorta_el_solape_en_lugar_de_duplicarlo(self, repo_fragmentos):
        repo = RepositorioSeccionesMemoria.desde_fragmentos(repo_fragmentos.todos())
        seccion = repo.obtener("MSFT", 2025, "1A")
        assert seccion is not None
        assert seccion.texto.count("Third parties may misuse them.") == 1

    def test_conserva_el_texto_de_todos_los_fragmentos(self, repo_fragmentos):
        repo = RepositorioSeccionesMemoria.desde_fragmentos(repo_fragmentos.todos())
        seccion = repo.obtener("MSFT", 2025, "1A")
        assert seccion is not None
        assert "Issues in the development, deployment" in seccion.texto
        assert "We may not be able to detect every misuse" in seccion.texto

    def test_queda_marcada_como_reconstruida(self, repo_fragmentos):
        """El sistema tiene que decirlo en voz alta, no disimularlo."""
        repo = RepositorioSeccionesMemoria.desde_fragmentos(repo_fragmentos.todos())
        assert all(s.reconstruida for s in repo.listar())

    def test_los_tokens_se_prorratean_en_vez_de_sumarse(self, repo_fragmentos):
        """Sumar los n_tokens de fragmentos que solapan sobreestima la sección."""
        repo = RepositorioSeccionesMemoria.desde_fragmentos(repo_fragmentos.todos())
        seccion = repo.obtener("MSFT", 2025, "1A")
        assert seccion is not None
        assert seccion.n_tokens < 27 + 17 + 17


@pytest.mark.corpus
class TestCorpusReal:
    def test_tiene_48_secciones_y_1749_fragmentos(self, corpus_real):
        assert len(corpus_real.secciones) == 48
        assert len(corpus_real.fragmentos) == 1749

    def test_los_seis_emisores_y_los_dos_ejercicios(self, corpus_real):
        assert corpus_real.secciones.tickers() == [
            "AAPL",
            "AMZN",
            "GOOGL",
            "META",
            "MSFT",
            "NVDA",
        ]
        assert corpus_real.secciones.ejercicios() == [2024, 2025]

    def test_los_cuatro_items(self, corpus_real):
        assert corpus_real.secciones.items() == ["1A", "7", "7A", "8"]

    def test_los_chunk_id_son_unicos(self, corpus_real):
        ids = [f.chunk_id for f in corpus_real.fragmentos.todos()]
        assert len(set(ids)) == len(ids)
