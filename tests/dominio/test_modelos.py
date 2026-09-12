"""Los contratos C3 y C4, fijados por escrito.

Estos tests existen para que nadie "mejore" el esquema sin darse cuenta de que
lo está rompiendo. El día 24 el evaluador externo importa `RespuestaFinanciera`
y lee campos por su nombre: un renombrado aquí es un suspenso allí.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agente_10k.dominio.modelos import (
    Fragmento,
    Pregunta,
    RespuestaFinanciera,
    Traza,
    UsoTokens,
)

CAMPOS_C3 = {
    "respuesta",
    "cifra",
    "unidad",
    "ticker",
    "ejercicio",
    "fuente",
    "cita",
    "chunk_id",
}

CAMPOS_C4 = {
    "id",
    "pregunta",
    "familia",
    "ticker",
    "fiscal_year",
    "respuesta_esperada",
    "cifra_esperada",
    "unidad",
    "concept_xbrl",
    "item_esperado",
    "ancla_texto",
    "ancla_inicio",
    "ancla_fin",
    "chunk_id_esperado",
    "herramienta_esperada",
    "autor",
}


class TestContratoC3:
    def test_estan_los_ocho_campos_del_enunciado(self):
        assert set(RespuestaFinanciera.model_fields) >= CAMPOS_C3

    def test_solo_respuesta_y_fuente_son_obligatorios(self):
        r = RespuestaFinanciera(respuesta="No está en el corpus.", fuente="ninguna")
        assert r.cifra is None
        assert r.chunk_id is None

    def test_fuente_es_un_vocabulario_cerrado(self):
        with pytest.raises(ValidationError):
            RespuestaFinanciera(respuesta="x", fuente="inventada")

    @pytest.mark.parametrize("valor", ["xbrl", "texto", "ambas", "ninguna"])
    def test_los_cuatro_valores_de_fuente(self, valor):
        assert RespuestaFinanciera(respuesta="x", fuente=valor).fuente == valor

    def test_los_campos_anadidos_son_opcionales(self):
        """Un modelo que solo rellene los ocho originales tiene que validar."""
        original = {"respuesta": "60.922 millones", "fuente": "xbrl"}
        assert RespuestaFinanciera.model_validate(original).concept_xbrl is None


class TestContratoC4:
    def test_estan_los_dieciseis_campos_del_esquema(self):
        assert set(Pregunta.model_fields) == CAMPOS_C4

    def test_rechaza_campos_extra(self):
        """Un campo de más en el JSONL se dice, no se ignora en silencio."""
        with pytest.raises(ValidationError):
            Pregunta(id="x", pregunta="?", familia="numerica", inventado=1)

    def test_familia_es_un_vocabulario_cerrado_de_tres(self):
        """El validador oficial solo admite tres familias. 'hueco' no es una."""
        with pytest.raises(ValidationError):
            Pregunta(id="x", pregunta="?", familia="hueco")

    def test_es_hueco_cuando_falta_la_cifra_y_hay_concepto(self):
        p = Pregunta(
            id="g-p-001",
            pregunta="¿Cuál fue el margen bruto de Amazon en FY2025?",
            familia="numerica",
            ticker="AMZN",
            fiscal_year=2025,
            concept_xbrl="GrossProfit",
            cifra_esperada=None,
        )
        assert p.es_hueco

    def test_no_es_hueco_si_hay_cifra(self):
        p = Pregunta(
            id="g-p-002",
            pregunta="¿Revenue de NVDA en FY2024?",
            familia="numerica",
            concept_xbrl="Revenues",
            cifra_esperada=60922000000.0,
        )
        assert not p.es_hueco

    def test_no_es_hueco_una_extractiva_sin_cifra(self):
        p = Pregunta(id="g-p-003", pregunta="¿Qué riesgos?", familia="extractiva")
        assert not p.es_hueco

    def test_el_ejemplo_del_enunciado_valida(self):
        crudo = {
            "id": "g3-007",
            "pregunta": "¿Cuál fue el revenue de NVIDIA en el ejercicio 2024?",
            "familia": "numerica",
            "ticker": "NVDA",
            "fiscal_year": 2024,
            "respuesta_esperada": "60.922 millones de dólares",
            "cifra_esperada": 60922000000.0,
            "unidad": "USD",
            "concept_xbrl": "Revenues",
            "item_esperado": None,
            "ancla_texto": None,
            "ancla_inicio": None,
            "ancla_fin": None,
            "chunk_id_esperado": None,
            "herramienta_esperada": ["get_xbrl_fact"],
            "autor": "grupo-3",
        }
        assert Pregunta.model_validate(crudo).cifra_esperada == 60922000000.0


class TestUsoTokens:
    def test_suma_tokens_y_coste(self):
        a = UsoTokens(tokens_entrada=100, tokens_salida=20, coste_usd=0.001)
        b = UsoTokens(tokens_entrada=50, tokens_salida=10, coste_usd=0.002)
        total = a + b
        assert total.tokens_total == 180
        assert total.coste_usd == pytest.approx(0.003)

    def test_el_coste_desconocido_se_propaga_como_desconocido(self):
        """Si ningún lado trae coste, el total no es 0: es desconocido.

        Un 0 en la tabla del informe diría que el sistema es gratis.
        """
        total = UsoTokens(tokens_entrada=10) + UsoTokens(tokens_entrada=5)
        assert total.coste_usd is None

    def test_un_coste_conocido_y_otro_no_suman_lo_conocido(self):
        total = UsoTokens(coste_usd=0.5) + UsoTokens()
        assert total.coste_usd == pytest.approx(0.5)


class TestTraza:
    def test_la_trayectoria_conserva_el_orden(self):
        from agente_10k.dominio.modelos import LlamadaHerramienta

        traza = Traza(
            pregunta="?",
            llamadas=[
                LlamadaHerramienta(nombre="list_available"),
                LlamadaHerramienta(nombre="get_xbrl_fact"),
                LlamadaHerramienta(nombre="get_xbrl_fact"),
            ],
        )
        assert traza.trayectoria == [
            "list_available",
            "get_xbrl_fact",
            "get_xbrl_fact",
        ]
        assert traza.n_llamadas == 3

    def test_serializa_a_json(self):
        """La traza es la entrada del evaluador de trayectoria: tiene que volcar."""
        traza = Traza(pregunta="¿Revenue de NVDA en FY2024?")
        assert "pregunta" in traza.model_dump_json()


class TestFragmento:
    def test_con_puntuacion_no_muta_el_original(self):
        f = Fragmento(
            chunk_id="X-2024-7-0000",
            ticker="X",
            fiscal_year=2024,
            item="7",
            posicion=0,
            texto="t",
            n_tokens=1,
        )
        g = f.con_puntuacion(0.9)
        assert f.puntuacion is None
        assert g.puntuacion == 0.9

    def test_es_inmutable(self):
        f = Fragmento(
            chunk_id="X-2024-7-0000",
            ticker="X",
            fiscal_year=2024,
            item="7",
            posicion=0,
            texto="t",
            n_tokens=1,
        )
        with pytest.raises(ValidationError):
            f.texto = "otro"
