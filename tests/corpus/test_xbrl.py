"""Las trampas T2 y T3, fijadas como tests.

Son la parte del corpus que más fácil es romper sin enterarse, porque no fallan
con una excepción: fallan devolviendo una cifra creíble de otra compañía.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agente_10k.corpus.xbrl import HUECOS_CONOCIDOS, RepositorioXbrlMemoria
from agente_10k.dominio.modelos import HechoXbrl


class TestLecturaYConsulta:
    def test_encuentra_el_hecho_exacto(self, repo_xbrl):
        hecho = repo_xbrl.obtener("NVDA", 2024, "Revenues")
        assert hecho is not None
        assert hecho.value == 60_922_000_000.0
        assert hecho.unit == "USD"
        assert hecho.period_end == "2024-01-28"

    def test_devuelve_none_si_no_existe(self, repo_xbrl):
        assert repo_xbrl.obtener("AMZN", 2025, "GrossProfit") is None

    def test_el_ejercicio_se_normaliza_a_entero(self, repo_xbrl):
        assert repo_xbrl.obtener("NVDA", "2024", "Revenues") is not None  # type: ignore[arg-type]

    def test_conceptos_lista_solo_los_de_ese_emisor_y_ejercicio(self, repo_xbrl):
        assert repo_xbrl.conceptos("NVDA", 2024) == [
            "GrossProfit",
            "NetIncomeLoss",
            "Revenues",
        ]
        assert repo_xbrl.conceptos("NVDA", 2025) == ["Revenues"]

    def test_hay_datos_distingue_emisor_ausente_de_concepto_ausente(self, repo_xbrl):
        assert repo_xbrl.hay_datos("NVDA", 2024)
        assert not repo_xbrl.hay_datos("TSLA", 2024)
        assert not repo_xbrl.hay_datos("NVDA", 2023)

    def test_un_parquet_que_no_esta_no_rompe_el_import(self, tmp_path):
        """Sin el fichero, repositorio vacío y NO disponible. No excepción."""
        repo = RepositorioXbrlMemoria.desde_parquet(tmp_path / "no_existe.parquet")
        assert not repo.disponible()
        assert len(repo) == 0

    def test_disponible_distingue_vacio_de_no_cargado(self):
        vacio_pero_cargado = RepositorioXbrlMemoria((), cargado=True)
        assert vacio_pero_cargado.disponible()

    def test_lee_de_parquet(self, tmp_path):
        pd = pytest.importorskip("pandas")
        origen = Path(__file__).parent.parent / "fixtures" / "xbrl_facts.jsonl"
        filas = [
            json.loads(linea)
            for linea in origen.read_text(encoding="utf-8").splitlines()
            if linea.strip()
        ]
        ruta = tmp_path / "xbrl_facts.parquet"
        pd.DataFrame(filas).to_parquet(ruta)

        repo = RepositorioXbrlMemoria.desde_parquet(ruta)
        assert repo.disponible()
        assert len(repo) == 10
        assert repo.obtener("MSFT", 2025, "GrossProfit").value == 196_000_000_000.0

    def test_un_parquet_sin_las_columnas_lo_dice(self, tmp_path):
        pd = pytest.importorskip("pandas")
        ruta = tmp_path / "malo.parquet"
        pd.DataFrame([{"ticker": "NVDA"}]).to_parquet(ruta)
        with pytest.raises(ValueError, match="columnas"):
            RepositorioXbrlMemoria.desde_parquet(ruta)


class TestTrampaT2ConceptoNoUniversal:
    """El concepto del ingreso no es el mismo en todas las compañías."""

    def test_nvda_usa_revenues_y_no_el_largo(self, repo_xbrl):
        assert repo_xbrl.obtener("NVDA", 2024, "Revenues") is not None
        assert (
            repo_xbrl.obtener(
                "NVDA", 2024, "RevenueFromContractWithCustomerExcludingAssessedTax"
            )
            is None
        )

    def test_msft_usa_el_largo_y_no_revenues(self, repo_xbrl):
        assert (
            repo_xbrl.obtener(
                "MSFT", 2025, "RevenueFromContractWithCustomerExcludingAssessedTax"
            )
            is not None
        )
        assert repo_xbrl.obtener("MSFT", 2025, "Revenues") is None

    def test_sugiere_el_sinonimo_que_ese_emisor_si_reporta(self, repo_xbrl):
        sugerencias = repo_xbrl.sugerencias(
            "NVDA", 2024, "RevenueFromContractWithCustomerExcludingAssessedTax"
        )
        assert sugerencias == ["Revenues"]

    def test_no_sugiere_un_sinonimo_que_tampoco_existe(self, repo_xbrl):
        """Sugerir algo que tampoco está sería mandar al agente a un segundo fallo."""
        assert repo_xbrl.sugerencias("NVDA", 2025, "GrossProfit") == []

    def test_el_repositorio_nunca_traduce_por_su_cuenta(self, repo_xbrl):
        """Si tradujera, el agente acertaría sin aprender que cada emisor etiqueta
        a su manera, y la siguiente compañía volvería a fallar."""
        assert (
            repo_xbrl.obtener(
                "NVDA", 2024, "RevenueFromContractWithCustomerExcludingAssessedTax"
            )
            is None
        )


class TestTrampaT3HuecosReales:
    """Amazon no reporta GrossProfit, Liabilities ni R&D; Meta y Alphabet tampoco
    GrossProfit. Son preguntas legítimas con respuesta «no está»."""

    @pytest.mark.parametrize(
        ("ticker", "concepto"),
        [
            ("AMZN", "GrossProfit"),
            ("AMZN", "Liabilities"),
            ("AMZN", "ResearchAndDevelopmentExpense"),
            ("META", "GrossProfit"),
            ("GOOGL", "GrossProfit"),
        ],
    )
    def test_los_huecos_del_enunciado_estan_declarados(
        self, repo_xbrl, ticker, concepto
    ):
        assert repo_xbrl.es_hueco_conocido(ticker, concepto)

    def test_un_concepto_mal_escrito_no_es_un_hueco(self, repo_xbrl):
        """Son dos situaciones distintas y el agente debe reaccionar distinto."""
        assert not repo_xbrl.es_hueco_conocido("AMZN", "GrosProfit")
        assert not repo_xbrl.es_hueco_conocido("NVDA", "GrossProfit")

    @pytest.mark.corpus
    def test_los_huecos_siguen_siendo_huecos_en_el_corpus_real(self, corpus_real):
        """Si el profesor regenera el corpus y uno deja de serlo, que se sepa aquí
        y no cuando el sistema responda «no está» a algo que sí está."""
        xbrl = corpus_real.xbrl
        if not xbrl.disponible():
            pytest.skip("xbrl_facts.parquet no está montado")
        for ticker, concepto in sorted(HUECOS_CONOCIDOS):
            for fy in (2024, 2025):
                if xbrl.hay_datos(ticker, fy):
                    assert xbrl.obtener(ticker, fy, concepto) is None, (
                        f"{ticker} SÍ reporta {concepto} en FY{fy}: "
                        f"HUECOS_CONOCIDOS está desactualizado."
                    )


def test_los_hechos_son_inmutables():
    hecho = HechoXbrl(
        ticker="NVDA", fiscal_year=2024, concept="Revenues", value=1.0, unit="USD"
    )
    with pytest.raises(Exception):  # noqa: B017
        hecho.value = 2.0
