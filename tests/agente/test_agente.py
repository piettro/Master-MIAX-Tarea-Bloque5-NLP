"""El agente. Lo verde es el prompt y los ayudantes; lo `xfail` es la fase 4.

Toda la suite corre con `ProveedorFake`: sin red, sin clave de API y sin gastar
un céntimo. Si algún test de aquí necesita una clave, está mal escrito.
"""

from __future__ import annotations

import pytest

from agente_10k.agente.prompts import (
    SYSTEM,
    TRAZABILIDAD,
    VERSION_PROMPT,
    system_prompt,
)
from agente_10k.agente.proveedores import CODIGOS_CUOTA, ProveedorFake
from agente_10k.agente.trazas import cumple_trayectoria, resumir
from agente_10k.dominio.modelos import LlamadaHerramienta, Traza, UsoTokens

FASE_4 = pytest.mark.xfail(strict=True, reason="Fase 4 · Piettro")


class TestSystemPrompt:
    def test_prohibe_leer_cifras_de_la_prosa(self):
        assert "NUNCA leas un número de la prosa" in SYSTEM

    def test_autoriza_explicitamente_la_no_respuesta(self):
        """Decir «no está en el corpus» cuando no está es la respuesta correcta,
        y el prompt tiene que decirlo con esas palabras."""
        assert "es la respuesta\nCORRECTA" in SYSTEM or "CORRECTA" in SYSTEM
        assert 'fuente="ninguna"' in SYSTEM

    def test_describe_el_criterio_de_enrutado(self):
        for tool in (
            "get_xbrl_fact",
            "search_filings",
            "list_available",
            "read_section",
        ):
            assert tool in SYSTEM

    def test_exige_cita_para_lo_extractivo(self):
        assert "cita el chunk_id" in SYSTEM

    def test_avisa_de_la_trampa_del_ejercicio_fiscal(self):
        assert "NO el año de presentación" in SYSTEM

    def test_avisa_de_la_trampa_del_concepto_xbrl(self):
        assert "no es el mismo en todas las compañías" in SYSTEM

    def test_dice_como_hacer_una_comparativa(self):
        assert "DOS consultas exactas" in SYSTEM

    def test_dice_que_el_corpus_esta_en_ingles(self):
        assert "inglés" in SYSTEM

    def test_toda_regla_se_rastrea_a_una_pregunta_del_golden_set(self):
        """Impide que el prompt crezca por acumulación de parches: para añadir
        una regla hay que poder decir qué pregunta la necesita."""
        cubiertos = {clave.split("/")[0] for clave in TRAZABILIDAD}
        for bloque in (
            "ENRUTADO",
            "COMPARATIVAS",
            "EJERCICIO FISCAL",
            "CONCEPTOS XBRL",
            "CUÁNDO NO RESPONDER",
            "IDIOMA",
            "SALIDA",
        ):
            assert bloque in SYSTEM
            assert bloque in cubiertos, (
                f"El bloque {bloque!r} del prompt no se rastrea a ninguna "
                f"pregunta del golden set."
            )

    def test_la_version_se_puede_pedir_por_nombre(self):
        assert system_prompt(VERSION_PROMPT) == SYSTEM

    def test_una_version_inexistente_falla_en_vez_de_devolver_otra(self):
        """Devolver otro prompt en silencio haría que la traza mintiera."""
        with pytest.raises(KeyError):
            system_prompt("v99")


class TestProveedorFake:
    def test_devuelve_las_respuestas_en_orden(self):
        p = ProveedorFake(respuestas=["uno", "dos"])
        assert p.invoke("a") == "uno"
        assert p.invoke("b") == "dos"

    def test_registra_lo_que_le_pidieron(self):
        p = ProveedorFake(respuestas=["uno"])
        p.invoke({"messages": []})
        assert len(p.llamadas) == 1

    def test_agotarse_es_un_error_ruidoso(self):
        """Devolver algo plausible ocultaría que el test esperaba menos vueltas."""
        p = ProveedorFake(respuestas=[])
        with pytest.raises(AssertionError, match="agotado"):
            p.invoke("a")

    def test_no_necesita_clave_ni_red(self):
        p = ProveedorFake()
        assert p.proveedor == "fake"
        assert not p.en_reserva


class TestCumpleTrayectoria:
    def test_una_llamada_de_mas_no_penaliza(self):
        """Comprobar el corpus antes de consultar es exactamente lo que queremos;
        penalizarlo sería premiar al que adivina."""
        assert cumple_trayectoria(
            ["list_available", "get_xbrl_fact"], ["get_xbrl_fact"]
        )

    def test_falta_la_herramienta_esperada(self):
        """Una numérica que no pasó por get_xbrl_fact leyó la cifra del texto."""
        assert not cumple_trayectoria(["search_filings"], ["get_xbrl_fact"])

    def test_el_orden_no_importa(self):
        assert cumple_trayectoria(
            ["get_xbrl_fact", "search_filings"], ["search_filings", "get_xbrl_fact"]
        )

    def test_sin_esperadas_siempre_cumple(self):
        assert cumple_trayectoria([], [])


class TestResumirTraza:
    def test_muestra_el_camino_y_el_coste(self):
        traza = Traza(
            pregunta="?",
            llamadas=[LlamadaHerramienta(nombre="get_xbrl_fact")],
            uso=UsoTokens(tokens_entrada=100, tokens_salida=50, coste_usd=0.0012),
            latencia_s=2.5,
        )
        salida = resumir(traza)
        assert "get_xbrl_fact" in salida
        assert "0.00120 $" in salida
        assert "2.5 s" in salida

    def test_marca_el_limite_y_el_guardarrail(self):
        traza = Traza(pregunta="?", limite_alcanzado=True, intervenciones_guardarrail=2)
        salida = resumir(traza)
        assert "LÍMITE" in salida
        assert "guardarraíl x2" in salida

    def test_un_coste_desconocido_no_se_imprime_como_cero(self):
        assert "?" in resumir(Traza(pregunta="?"))


def test_los_codigos_de_cuota_son_los_tres():
    """401 credenciales, 402 sin saldo, 429 límite de tasa."""
    assert set(CODIGOS_CUOTA) == {401, 402, 429}


# ---------------------------------------------------------------------------
# FASE 4 — la especificación, en rojo
# ---------------------------------------------------------------------------


class TestLimitadorLlamadas:
    @FASE_4
    def test_corta_en_la_llamada_n_mas_uno(self):
        from agente_10k.agente.middleware import LimitadorLlamadas

        limitador = LimitadorLlamadas(max_llamadas=2)
        traza = Traza(
            pregunta="?",
            llamadas=[LlamadaHerramienta(nombre="get_xbrl_fact")] * 2,
        )
        assert limitador.procesar(traza) is None
        traza.llamadas.append(LlamadaHerramienta(nombre="get_xbrl_fact"))
        assert "presupuesto" in (limitador.procesar(traza) or "")

    @FASE_4
    def test_el_mensaje_autoriza_a_rendirse(self):
        """El bucle infinito del margen bruto de Amazon termina aquí."""
        from agente_10k.agente.middleware import LimitadorLlamadas

        limitador = LimitadorLlamadas(max_llamadas=0)
        mensaje = limitador.procesar(Traza(pregunta="?")) or ""
        assert 'fuente="ninguna"' in mensaje


class TestGuardarrailXbrl:
    @FASE_4
    def test_devuelve_el_desajuste_al_modelo(self, repo_xbrl):
        from agente_10k.agente.middleware import GuardarrailXbrl
        from agente_10k.dominio.modelos import RespuestaFinanciera

        guardarrail = GuardarrailXbrl(repo_xbrl)
        respuesta = RespuestaFinanciera(
            respuesta="60.900 millones",
            cifra=99_999_000_000.0,
            unidad="USD",
            ticker="NVDA",
            ejercicio=2024,
            concept_xbrl="Revenues",
            fuente="xbrl",
        )
        mensaje = guardarrail.verificar(respuesta) or ""
        assert "GUARDARRAÍL" in mensaje
        assert "60,922,000,000" in mensaje

    @FASE_4
    def test_NO_corrige_la_cifra_por_su_cuenta(self, repo_xbrl):
        """Corregirla enmascara el fallo y falsea la evaluación: la tabla diría
        que acierta el sistema cuando quien acierta es el guardarraíl."""
        from agente_10k.agente.middleware import GuardarrailXbrl
        from agente_10k.dominio.modelos import RespuestaFinanciera

        respuesta = RespuestaFinanciera(
            respuesta="x",
            cifra=99_999_000_000.0,
            ticker="NVDA",
            ejercicio=2024,
            concept_xbrl="Revenues",
            fuente="xbrl",
        )
        GuardarrailXbrl(repo_xbrl).verificar(respuesta)
        assert respuesta.cifra == 99_999_000_000.0

    @FASE_4
    def test_acepta_el_redondeo_de_la_prosa(self, repo_xbrl):
        from agente_10k.agente.middleware import GuardarrailXbrl
        from agente_10k.dominio.modelos import RespuestaFinanciera

        respuesta = RespuestaFinanciera(
            respuesta="x",
            cifra=60_900_000_000.0,
            ticker="NVDA",
            ejercicio=2024,
            concept_xbrl="Revenues",
            fuente="xbrl",
        )
        assert GuardarrailXbrl(repo_xbrl).verificar(respuesta) is None

    @FASE_4
    def test_no_salta_ante_una_respuesta_de_hueco(self, repo_xbrl):
        """`fuente="ninguna"` con `cifra=None` es la respuesta CORRECTA."""
        from agente_10k.agente.middleware import GuardarrailXbrl
        from agente_10k.dominio.modelos import RespuestaFinanciera

        respuesta = RespuestaFinanciera(
            respuesta="No está en el corpus.", cifra=None, fuente="ninguna"
        )
        assert GuardarrailXbrl(repo_xbrl).verificar(respuesta) is None

    @FASE_4
    def test_usa_la_misma_tolerancia_que_el_evaluador(self, repo_xbrl):
        from agente_10k.agente.middleware import GuardarrailXbrl
        from agente_10k.dominio.tolerancia import TOLERANCIA

        assert GuardarrailXbrl(repo_xbrl).tolerancia is TOLERANCIA


class TestConstructor:
    @FASE_4
    def test_una_pregunta_numerica_pasa_por_get_xbrl_fact(self):
        from agente_10k.agente.constructor import construir_agente

        _, traza = construir_agente().responder(
            "¿Cuál fue el revenue de NVIDIA en el ejercicio 2024?"
        )
        assert "get_xbrl_fact" in traza.trayectoria

    @FASE_4
    def test_un_emisor_fuera_del_corpus_no_dispara_retrieval(self):
        from agente_10k.agente.constructor import construir_agente

        respuesta, traza = construir_agente().responder(
            "¿Cuál fue el revenue de Tesla en el ejercicio 2025?"
        )
        assert respuesta.fuente == "ninguna"
        assert "search_filings" not in traza.trayectoria

    @FASE_4
    def test_una_salida_invalida_no_lanza(self):
        """Una excepción aquí abortaría la evaluación del golden set entero."""
        from agente_10k.agente.constructor import construir_agente

        respuesta, _ = construir_agente().responder("")
        assert respuesta.fuente == "ninguna"
        assert respuesta.motivo_sin_dato


class TestProveedorConFallback:
    @FASE_4
    def test_conmuta_al_alternativo_ante_429(self):
        from agente_10k.agente.proveedores import ProveedorLangChain
        from agente_10k.config import Settings

        proveedor = ProveedorLangChain(Settings())
        assert not proveedor.en_reserva

    @FASE_4
    def test_no_reintenta_el_primario_en_cada_llamada(self):
        """El pseudocódigo de clase reintentaba el gratuito cada vez y el
        profesor señaló que está mal: son N llamadas fallidas de más."""
        from agente_10k.agente.proveedores import ProveedorLangChain
        from agente_10k.config import Settings

        proveedor = ProveedorLangChain(Settings())
        assert hasattr(proveedor, "en_reserva")
