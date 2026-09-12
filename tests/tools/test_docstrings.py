"""CONTRATO C2: los docstrings son parte funcional del sistema.

El modelo decide qué herramienta llamar leyendo ESTO y nada más. Un docstring
que pierda su criterio de enrutado cambia el comportamiento del agente sin que
falle ningún otro test, y el síntoma aparece tres semanas después como «bajó el
acierto de la familia numérica».

Cada aserción de aquí corresponde a una regla que el enunciado o la sesión 1
señalan por escrito.
"""

from __future__ import annotations

import inspect
import re

import pytest

from agente_10k.tools.contratos import (
    HERRAMIENTAS,
    get_xbrl_fact,
    list_available,
    read_section,
    search_filings,
)


def doc(fn) -> str:
    """El docstring en una sola linea.

    Se colapsan los espacios porque los docstrings van envueltos a 88
    columnas y una frase puede partirse por cualquier sitio. Lo que el
    modelo lee es el parrafo, no las lineas.
    """
    return re.sub(r"\s+", " ", inspect.getdoc(fn) or "")


class TestFirmasC1:
    """Los nombres y los parámetros son contrato. El hold-out va contra ellos."""

    def test_los_cuatro_nombres_exactos(self):
        assert [f.__name__ for f in HERRAMIENTAS] == [
            "list_available",
            "get_xbrl_fact",
            "search_filings",
            "read_section",
        ]

    def test_list_available_no_tiene_parametros(self):
        assert list(inspect.signature(list_available).parameters) == []

    def test_get_xbrl_fact_conserva_sus_tres_parametros(self):
        params = inspect.signature(get_xbrl_fact).parameters
        assert list(params) == ["ticker", "fiscal_year", "concept"]
        assert all(p.default is inspect.Parameter.empty for p in params.values())

    def test_search_filings_conserva_sus_cinco_parametros_y_defaults(self):
        params = inspect.signature(search_filings).parameters
        assert list(params) == ["query", "ticker", "fiscal_year", "item", "k"]
        assert params["ticker"].default is None
        assert params["k"].default == 5

    def test_read_section_conserva_los_tres_y_anade_uno_opcional(self):
        """Añadir parámetros CON valor por defecto está permitido por C1."""
        params = inspect.signature(read_section).parameters
        assert list(params)[:3] == ["ticker", "fiscal_year", "item"]
        assert params["max_tokens"].default is None

    @pytest.mark.parametrize("fn", HERRAMIENTAS, ids=lambda f: f.__name__)
    def test_todas_devuelven_str(self, fn):
        """Lo único que lee el modelo es texto."""
        assert inspect.signature(fn).return_annotation == "str"


class TestDocstringGetXbrlFact:
    def test_dice_que_es_la_fuente_autorizada(self):
        assert "fuente autorizada" in doc(get_xbrl_fact).lower()

    def test_dice_que_se_use_SIEMPRE_en_lugar_de_leer_del_texto(self):
        """Es LA instrucción de enrutado de toda la práctica."""
        texto = doc(get_xbrl_fact)
        assert "SIEMPRE" in texto
        assert "en lugar de leer un número del texto" in texto

    def test_dice_cuando_NO_usarla(self):
        assert "NO la uses" in doc(get_xbrl_fact)

    def test_avisa_de_la_trampa_del_ejercicio_fiscal(self):
        assert "NO el año de presentación" in doc(get_xbrl_fact)

    def test_avisa_de_que_el_concepto_no_es_universal(self):
        texto = doc(get_xbrl_fact)
        assert "NO es el mismo en todas las compañías" in texto
        assert "analogía" in texto

    def test_enumera_el_vocabulario_de_conceptos(self):
        """El modelo no puede adivinar un vocabulario que no ha visto."""
        texto = doc(get_xbrl_fact)
        assert "Revenues" in texto
        assert "RevenueFromContractWithCustomerExcludingAssessedTax" in texto

    def test_explica_que_devuelve_si_no_hay_dato(self):
        texto = doc(get_xbrl_fact)
        assert "conceptos que SÍ existen" in texto
        assert "sinónimo" in texto

    def test_induce_fuente_ninguna_ante_un_hueco_real(self):
        texto = doc(get_xbrl_fact)
        assert "hueco REAL" in texto
        assert 'fuente="ninguna"' in texto
        assert "no lo estimes" in texto.lower()


class TestDocstringSearchFilings:
    def test_dice_para_que_sirve(self):
        assert "CUALITATIVAS" in doc(search_filings)

    def test_dice_que_NO_se_use_para_cifras(self):
        """Esta frase vale más que las otras cinco."""
        texto = doc(search_filings)
        assert "NO la uses para obtener cifras" in texto
        assert "get_xbrl_fact" in texto

    def test_explica_como_hacer_una_comparativa(self):
        assert "DOS VECES" in doc(search_filings)

    def test_dice_que_el_corpus_esta_en_ingles(self):
        assert "EN INGLÉS" in doc(search_filings)

    def test_enumera_el_vocabulario_de_items(self):
        texto = doc(search_filings)
        for item in ("'1A'", "'7'", "'7A'", "'8'"):
            assert item in texto

    def test_exige_citar_el_chunk_id(self):
        assert "CITA SIEMPRE el chunk_id" in doc(search_filings)

    def test_avisa_de_que_vacio_no_es_ausencia(self):
        assert "no significa que el dato no exista" in doc(search_filings)


class TestDocstringReadSection:
    def test_avisa_de_que_es_cara(self):
        texto = doc(read_section)
        assert "CARA" in texto
        assert "decenas de miles de tokens" in texto

    def test_dice_que_es_el_ultimo_recurso(self):
        assert "ÚLTIMO RECURSO" in doc(read_section)

    def test_dice_que_hay_que_haber_probado_search_filings_antes(self):
        assert "search_filings" in doc(read_section)

    def test_documenta_el_parametro_opcional(self):
        assert "max_tokens" in doc(read_section)


class TestDocstringListAvailable:
    def test_dice_que_se_use_antes_de_negar_un_dato(self):
        assert "ÚSALA SIEMPRE antes de responder que un dato no existe" in doc(
            list_available
        )

    def test_dice_que_es_gratis(self):
        assert "gratis" in doc(list_available)

    def test_dice_que_hacer_con_una_compania_que_no_esta(self):
        texto = doc(list_available)
        assert "no está en el corpus" in texto
        assert "no busques" in texto.lower()


@pytest.mark.parametrize("fn", HERRAMIENTAS, ids=lambda f: f.__name__)
def test_todo_docstring_documenta_lo_que_devuelve(fn):
    """Incluido el caso sin dato: el modelo tiene que saber qué esperar."""
    assert "Returns:" in doc(fn)


@pytest.mark.parametrize("fn", HERRAMIENTAS[1:], ids=lambda f: f.__name__)
def test_todo_docstring_con_parametros_los_documenta(fn):
    texto = doc(fn)
    assert "Args:" in texto
    for nombre in inspect.signature(fn).parameters:
        assert nombre in texto, f"{fn.__name__} no documenta el parámetro {nombre}"
