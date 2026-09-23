"""El montaje del informe. Sin navegador: lo que se prueba es la composición."""

from __future__ import annotations

import pytest

from agente_10k.evaluacion.documento import a_html, componer, generar


@pytest.fixture
def raiz(tmp_path):
    (tmp_path / "resultados").mkdir()
    (tmp_path / "resultados" / "tabla.md").write_text(
        "| a | b |\n| --- | --- |\n| 1 | 2 |\n", encoding="utf-8"
    )
    return tmp_path


def test_sustituye_la_marca_por_el_fichero(raiz):
    plantilla = raiz / "plantilla.md"
    plantilla.write_text(
        "Antes\n\n{{incluir: resultados/tabla.md}}\n", encoding="utf-8"
    )
    texto = componer(plantilla, raiz)
    assert "| 1 | 2 |" in texto
    assert "incluir:" not in texto


def test_una_tabla_que_falta_no_rompe_el_informe(raiz):
    """El día antes de la entrega faltan tablas. El PDF tiene que salir igual."""
    plantilla = raiz / "plantilla.md"
    plantilla.write_text("{{incluir: resultados/no_existe.md}}", encoding="utf-8")
    texto = componer(plantilla, raiz)
    assert "PENDIENTE" in texto
    assert "no_existe.md" in texto


def test_tolera_espacios_en_la_marca(raiz):
    plantilla = raiz / "plantilla.md"
    plantilla.write_text("{{ incluir:  resultados/tabla.md  }}", encoding="utf-8")
    assert "| 1 | 2 |" in componer(plantilla, raiz)


def test_el_html_lleva_las_tablas_y_la_codificacion():
    html = a_html("# Título\n\n| a |\n| --- |\n| 1 |\n", "Informe")
    assert 'charset="utf-8"' in html
    assert "<table>" in html
    assert "<title>Informe</title>" in html


def test_genera_markdown_y_html(raiz, monkeypatch):
    """El PDF necesita navegador; sin él quedan el markdown y el HTML."""
    monkeypatch.setattr("agente_10k.evaluacion.documento._navegador", lambda: None)
    plantilla = raiz / "plantilla.md"
    plantilla.write_text(
        "# Informe\n\n{{incluir: resultados/tabla.md}}", encoding="utf-8"
    )
    escritos = generar(plantilla, raiz, raiz / "salida", "Informe")
    assert [r.name for r in escritos] == ["informe.md", "informe.html"]
    assert all(r.is_file() for r in escritos)
