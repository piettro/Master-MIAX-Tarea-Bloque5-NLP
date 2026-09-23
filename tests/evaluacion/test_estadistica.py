"""Wilson y McNemar. Los valores esperados salen de la fórmula, no de la libreria.

Se comprueba a mano lo que con n=20 se nota: que el intervalo no se sale de
[0, 1] y que McNemar exacto da los mismos p-valores que una binomial de p=1/2.
"""

from __future__ import annotations

import math

import pytest

from agente_10k.evaluacion.estadistica import (
    Intervalo,
    mcnemar,
    wilson,
)


class TestWilson:
    def test_el_intervalo_contiene_a_la_proporcion(self):
        ic = wilson(14, 20)
        assert ic.inferior < 0.7 < ic.superior

    def test_con_cero_aciertos_no_baja_de_cero(self):
        """La normal de toda la vida da negativo aquí. Wilson no."""
        ic = wilson(0, 20)
        assert ic.inferior == 0.0
        assert 0 < ic.superior < 0.2

    def test_con_todo_acertado_no_pasa_de_uno_ni_tiene_anchura_cero(self):
        ic = wilson(20, 20)
        assert ic.superior == 1.0
        assert ic.inferior < 0.9

    def test_menos_preguntas_dan_un_intervalo_mas_ancho(self):
        assert wilson(3, 6).anchura > wilson(30, 60).anchura

    def test_sin_preguntas_no_dice_nada(self):
        assert wilson(0, 0) == Intervalo(0.0, 1.0)

    def test_mas_aciertos_que_preguntas_es_un_error(self):
        with pytest.raises(ValueError, match="no es posible"):
            wilson(21, 20)

    def test_coincide_con_la_formula(self):
        aciertos, n, z = 12, 20, 1.959963984540054
        p = aciertos / n
        den = 1 + z**2 / n
        centro = (p + z**2 / (2 * n)) / den
        radio = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
        ic = wilson(aciertos, n)
        assert ic.inferior == pytest.approx(centro - radio)
        assert ic.superior == pytest.approx(centro + radio)


class TestMcNemar:
    """Solo cuentan las preguntas en las que los dos sistemas discrepan."""

    def test_las_preguntas_en_que_coinciden_no_cuentan(self):
        a = [True, True, False, False]
        b = [True, True, False, False]
        prueba = mcnemar(a, b)
        assert prueba.discordantes == 0
        assert prueba.p_valor == 1.0

    def test_cuenta_quien_gana_cada_discordancia(self):
        a = [True, False, False]
        b = [False, True, True]
        prueba = mcnemar(a, b)
        assert (prueba.solo_a, prueba.solo_b) == (1, 2)

    def test_seis_de_seis_a_favor_es_significativo(self):
        a = [False] * 6
        b = [True] * 6
        prueba = mcnemar(a, b)
        assert prueba.p_valor == pytest.approx(2 / 2**6)
        assert prueba.significativa()

    def test_una_mejora_de_dos_preguntas_no_lo_es(self):
        """El caso que de verdad va a pasar con 20 preguntas."""
        a = [True] * 10 + [False] * 10
        b = [True] * 12 + [False] * 8
        prueba = mcnemar(a, b)
        assert prueba.solo_b == 2
        assert not prueba.significativa()

    def test_es_simetrico(self):
        a = [True, False, True, False]
        b = [False, False, True, True]
        assert mcnemar(a, b).p_valor == mcnemar(b, a).p_valor

    def test_exige_que_esten_pareados(self):
        with pytest.raises(ValueError, match="no están pareados"):
            mcnemar([True, False], [True])
