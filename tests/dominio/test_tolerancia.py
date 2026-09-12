"""La tolerancia, con los casos que la justifican.

Cada test de aquí es un caso real del corpus, no un número inventado: es lo que
permite defender el 0,5 % en la presentación en lugar de decir «nos pareció
razonable».
"""

from __future__ import annotations

from agente_10k.dominio.tolerancia import TOLERANCIA, Tolerancia


class TestTolerancia:
    def test_acepta_el_redondeo_de_la_prosa(self):
        """«$60.9 billion» frente a 60.922.000.000 en XBRL: 0,036 % de desvío."""
        assert TOLERANCIA.coincide(60_900_000_000.0, 60_922_000_000.0)

    def test_rechaza_el_ejercicio_equivocado(self):
        """NVDA FY2024 son 60.922 M y FY2025 son 130.497 M: no se confunden."""
        assert not TOLERANCIA.coincide(130_497_000_000.0, 60_922_000_000.0)

    def test_rechaza_la_compania_equivocada(self):
        assert not TOLERANCIA.coincide(245_122_000_000.0, 60_922_000_000.0)

    def test_acepta_la_cifra_exacta(self):
        assert TOLERANCIA.coincide(60_922_000_000.0, 60_922_000_000.0)

    def test_rechaza_un_desvio_del_uno_por_ciento(self):
        assert not TOLERANCIA.coincide(101.0 * 1e9, 100.0 * 1e9)

    def test_la_tolerancia_absoluta_salva_el_cero(self):
        """Con solo tolerancia relativa, comparar contra 0 nunca casaría."""
        assert TOLERANCIA.coincide(0.0, 0.0)
        assert TOLERANCIA.coincide(0.5, 0.0)
        assert not TOLERANCIA.coincide(1000.0, 0.0)

    def test_desvio_relativo_contra_cero_es_infinito(self):
        assert TOLERANCIA.desvio_relativo(5.0, 0.0) == float("inf")
        assert TOLERANCIA.desvio_relativo(0.0, 0.0) == 0.0

    def test_se_puede_endurecer_sin_tocar_el_codigo(self):
        estricta = Tolerancia(relativa=0.0, absoluta=0.0)
        assert not estricta.coincide(60_900_000_000.0, 60_922_000_000.0)

    def test_describir_menciona_las_dos_partes(self):
        """El informe imprime esto: tiene que decir las dos, no solo la relativa."""
        texto = TOLERANCIA.describir()
        assert "relativo" in texto
        assert "absoluto" in texto


def test_el_guardarrail_y_el_evaluador_comparten_la_instancia():
    """Un solo sitio. Si se separan, la tabla del informe deja de ser defendible."""
    from agente_10k import dominio
    from agente_10k.dominio import tolerancia

    assert dominio.TOLERANCIA is tolerancia.TOLERANCIA
