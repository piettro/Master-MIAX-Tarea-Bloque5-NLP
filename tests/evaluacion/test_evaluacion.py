"""Evaluación. Lo verde son recall@k y la lectura tolerante; lo `xfail`, la fase 5.

El caso que más importa de este fichero es `TestLecturaTolerante`: es el fallo
más probable de toda la práctica. El día 24 llegan diez preguntas que pueden
venir con solo `id` y `pregunta`, y `evaluar()` tiene que tragarlas.
"""

from __future__ import annotations

import json

import pytest

from agente_10k.dominio.modelos import Fragmento, Pregunta
from agente_10k.evaluacion.ejecutor import leer_preguntas
from agente_10k.evaluacion.metricas import acierta_en_k, recall_at_k

FASE_5 = pytest.mark.xfail(strict=True, reason="Fase 5 · Raúl")

ANCLA = "Our AI systems offer users powerful tools and capabilities."


def frag(chunk_id: str, texto: str) -> Fragmento:
    return Fragmento(
        chunk_id=chunk_id,
        ticker="MSFT",
        fiscal_year=2025,
        item="1A",
        posicion=0,
        texto=texto,
        n_tokens=10,
    )


class TestRecallContraElAncla:
    """Se mide contra el ANCLA, no contra el chunk_id: quien mejore el troceado
    no puede salir penalizado por haberlo mejorado."""

    def test_acierta_si_el_ancla_esta_en_el_top_k(self):
        recuperados = [frag("a", "nada"), frag("b", f"...{ANCLA}...")]
        assert acierta_en_k(recuperados, ANCLA, 2)
        assert not acierta_en_k(recuperados, ANCLA, 1)

    def test_el_chunk_id_es_irrelevante(self):
        """Re-trocear el corpus cambia todos los identificadores y no debe
        cambiar la métrica."""
        assert acierta_en_k([frag("OTRO-ID-9999", ANCLA)], ANCLA, 1)

    def test_tolera_diferencias_de_espaciado(self):
        roto = ANCLA.replace(" ", "\n  ")
        assert acierta_en_k([frag("a", roto)], ANCLA, 1)

    def test_recall_at_k_devuelve_una_proporcion_por_k(self):
        recuperaciones = [
            ([frag("a", ANCLA)], ANCLA),
            ([frag("b", "nada"), frag("c", ANCLA)], ANCLA),
        ]
        resultado = recall_at_k(recuperaciones, ks=(1, 3))
        assert resultado[1] == pytest.approx(0.5)
        assert resultado[3] == pytest.approx(1.0)

    def test_las_preguntas_sin_ancla_no_entran_en_el_denominador(self):
        """Meterlas solo diluiría la métrica: no miden retrieval."""
        recuperaciones = [([frag("a", ANCLA)], ANCLA), ([frag("b", "x")], "")]
        assert recall_at_k(recuperaciones, ks=(1,))[1] == pytest.approx(1.0)

    def test_sin_recuperaciones_utiles_devuelve_cero(self):
        assert recall_at_k([], ks=(1, 5)) == {1: 0.0, 5: 0.0}


class TestLecturaTolerante:
    """El fallo más probable del día 24: campos ausentes en las preguntas ciegas."""

    def test_lee_una_pregunta_con_solo_id_y_texto(self, tmp_path):
        ruta = tmp_path / "ciegas.jsonl"
        ruta.write_text(
            json.dumps({"id": "c-001", "pregunta": "¿Revenue de NVDA en FY2024?"})
            + "\n",
            encoding="utf-8",
        )
        preguntas = leer_preguntas(ruta)
        assert len(preguntas) == 1
        assert preguntas[0].ticker is None
        assert preguntas[0].cifra_esperada is None

    def test_inventa_un_id_si_falta(self, tmp_path):
        ruta = tmp_path / "ciegas.jsonl"
        ruta.write_text(json.dumps({"pregunta": "¿?"}) + "\n", encoding="utf-8")
        assert leer_preguntas(ruta)[0].id == "ciegas-001"

    def test_sin_texto_de_pregunta_falla_diciendo_la_linea(self, tmp_path):
        ruta = tmp_path / "malas.jsonl"
        ruta.write_text(json.dumps({"id": "x"}) + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match=":1"):
            leer_preguntas(ruta)

    def test_json_roto_dice_el_numero_de_linea(self, tmp_path):
        ruta = tmp_path / "rotas.jsonl"
        ruta.write_text('{"pregunta": "ok"}\n{roto\n', encoding="utf-8")
        with pytest.raises(ValueError, match=":2"):
            leer_preguntas(ruta)

    def test_ignora_las_lineas_en_blanco(self, tmp_path):
        ruta = tmp_path / "p.jsonl"
        ruta.write_text('\n{"id":"a","pregunta":"?"}\n\n', encoding="utf-8")
        assert len(leer_preguntas(ruta)) == 1

    def test_un_fichero_que_no_existe_lo_dice(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            leer_preguntas(tmp_path / "no_existe.jsonl")

    def test_lee_el_golden_set_de_ejemplo_del_profesor(self):
        from tests.conftest import RAIZ

        ruta = RAIZ / "golden" / "golden_set_ejemplo.jsonl"
        if not ruta.is_file():
            pytest.skip("no está el fichero de ejemplo")
        preguntas = leer_preguntas(ruta)
        assert len(preguntas) == 3
        assert preguntas[0].concept_xbrl == "Revenues"


# ---------------------------------------------------------------------------
# FASE 5 — la especificación, en rojo
# ---------------------------------------------------------------------------


def pregunta_extractiva() -> Pregunta:
    return Pregunta(
        id="g-r-001",
        pregunta="¿Qué dice Microsoft sobre el uso indebido de sus sistemas de IA?",
        familia="extractiva",
        ticker="MSFT",
        fiscal_year=2025,
        item_esperado="1A",
        ancla_texto=ANCLA,
        herramienta_esperada=["search_filings"],
        autor="raul",
    )


def pregunta_hueco() -> Pregunta:
    return Pregunta(
        id="g-r-002",
        pregunta="¿Cuál fue el margen bruto de Amazon en FY2025?",
        familia="numerica",
        ticker="AMZN",
        fiscal_year=2025,
        concept_xbrl="GrossProfit",
        cifra_esperada=None,
        herramienta_esperada=["get_xbrl_fact"],
        autor="raul",
    )


class TestEvaluadorCita:
    @FASE_5
    def test_una_cita_literal_y_bien_atribuida_acierta(self, repo_fragmentos):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        respuesta = RespuestaFinanciera(
            respuesta="Pueden usarse indebidamente.",
            fuente="texto",
            cita=ANCLA,
            chunk_id="MSFT-2025-1A-0001",
        )
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(
            pregunta_extractiva(), respuesta
        )
        assert veredicto.acierto

    @FASE_5
    def test_una_cita_inventada_falla(self, repo_fragmentos):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        respuesta = RespuestaFinanciera(
            respuesta="x",
            fuente="texto",
            cita="Esta frase no está en ningún 10-K.",
            chunk_id="MSFT-2025-1A-0001",
        )
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(
            pregunta_extractiva(), respuesta
        )
        assert not veredicto.acierto
        assert "cita_no_literal" in veredicto.detalle

    @FASE_5
    def test_citar_bien_y_atribuir_mal_es_fallo_de_trazabilidad(self, repo_fragmentos):
        """Se reporta APARTE: no es lo mismo que inventarse la cita."""
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        respuesta = RespuestaFinanciera(
            respuesta="x", fuente="texto", cita=ANCLA, chunk_id="AMZN-2025-1A-0000"
        )
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(
            pregunta_extractiva(), respuesta
        )
        assert not veredicto.acierto
        assert "chunk_id_no_contiene_cita" in veredicto.detalle

    @FASE_5
    def test_una_cita_correcta_del_documento_equivocado_es_fallo(self, repo_fragmentos):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        p = pregunta_extractiva()
        p = p.model_copy(update={"ticker": "AMZN"})
        respuesta = RespuestaFinanciera(
            respuesta="x", fuente="texto", cita=ANCLA, chunk_id="MSFT-2025-1A-0001"
        )
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(p, respuesta)
        assert not veredicto.acierto
        assert "documento_equivocado" in veredicto.detalle

    @FASE_5
    def test_degrada_si_la_pregunta_no_trae_ancla(self, repo_fragmentos):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        p = Pregunta(id="c-001", pregunta="¿?", familia="extractiva")
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(
            p, RespuestaFinanciera(respuesta="x", fuente="texto")
        )
        assert veredicto.veredicto == "no_aplica"


class TestEvaluadorCifra:
    @FASE_5
    def test_acierta_dentro_de_la_tolerancia(self, repo_xbrl):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCifra

        p = Pregunta(
            id="n-001",
            pregunta="¿Revenue de NVDA en FY2024?",
            familia="numerica",
            ticker="NVDA",
            fiscal_year=2024,
            concept_xbrl="Revenues",
            cifra_esperada=60_922_000_000.0,
            unidad="USD",
            herramienta_esperada=["get_xbrl_fact"],
        )
        respuesta = RespuestaFinanciera(
            respuesta="60,9 mil millones",
            cifra=60_900_000_000.0,
            unidad="USD",
            fuente="xbrl",
        )
        assert EvaluadorCifra(repo_xbrl).evaluar(p, respuesta).acierto

    @FASE_5
    def test_acertar_el_hueco_es_cifra_none_y_fuente_ninguna(self, repo_xbrl):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCifra

        respuesta = RespuestaFinanciera(
            respuesta="Amazon no reporta margen bruto en us-gaap.",
            cifra=None,
            fuente="ninguna",
        )
        assert EvaluadorCifra(repo_xbrl).evaluar(pregunta_hueco(), respuesta).acierto

    @FASE_5
    def test_dar_una_cifra_en_un_hueco_es_alucinacion(self, repo_xbrl):
        """El peor fallo posible del sistema. Lleva categoría propia."""
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCifra

        evaluador = EvaluadorCifra(repo_xbrl)
        respuesta = RespuestaFinanciera(
            respuesta="Unos 300.000 millones.",
            cifra=300_000_000_000.0,
            unidad="USD",
            fuente="xbrl",
        )
        assert not evaluador.evaluar(pregunta_hueco(), respuesta).acierto
        assert evaluador.es_alucinacion_sobre_hueco(pregunta_hueco(), respuesta)

    @FASE_5
    def test_una_unidad_incoherente_es_fallo(self, repo_xbrl):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCifra

        p = Pregunta(
            id="n-002",
            pregunta="?",
            familia="numerica",
            ticker="NVDA",
            fiscal_year=2024,
            concept_xbrl="Revenues",
            cifra_esperada=60_922_000_000.0,
            unidad="USD",
        )
        respuesta = RespuestaFinanciera(
            respuesta="x", cifra=60_922_000_000.0, unidad="shares", fuente="xbrl"
        )
        assert not EvaluadorCifra(repo_xbrl).evaluar(p, respuesta).acierto


class TestEvaluadorTrayectoria:
    @FASE_5
    def test_el_camino_correcto_acierta(self):
        from agente_10k.dominio.modelos import LlamadaHerramienta, Traza
        from agente_10k.evaluacion.evaluadores import EvaluadorTrayectoria

        traza = Traza(
            pregunta="?", llamadas=[LlamadaHerramienta(nombre="get_xbrl_fact")]
        )
        assert EvaluadorTrayectoria().evaluar(pregunta_hueco(), traza).acierto

    @FASE_5
    def test_acertar_por_el_camino_equivocado_es_FALLO(self):
        """El criterio central de la práctica. Columna propia en el informe."""
        from agente_10k.dominio.modelos import LlamadaHerramienta, Traza
        from agente_10k.evaluacion.evaluadores import EvaluadorTrayectoria

        traza = Traza(
            pregunta="?", llamadas=[LlamadaHerramienta(nombre="search_filings")]
        )
        evaluador = EvaluadorTrayectoria()
        assert not evaluador.evaluar(pregunta_hueco(), traza).acierto
        assert (
            evaluador.clasificar(pregunta_hueco(), traza, respuesta_correcta=True)
            == "camino_incorrecto_respuesta_correcta"
        )

    @FASE_5
    def test_degrada_si_no_hay_herramienta_esperada(self):
        from agente_10k.dominio.modelos import Traza
        from agente_10k.evaluacion.evaluadores import EvaluadorTrayectoria

        p = Pregunta(id="c-001", pregunta="¿?", familia="numerica")
        veredicto = EvaluadorTrayectoria().evaluar(p, Traza(pregunta="?"))
        assert veredicto.veredicto == "no_aplica"


class TestEjecutor:
    @FASE_5
    def test_una_pregunta_que_lanza_no_aborta_las_demas(self, tmp_path):
        from agente_10k.evaluacion.ejecutor import evaluar

        ruta = tmp_path / "p.jsonl"
        ruta.write_text(
            '{"id":"a","pregunta":"?"}\n{"id":"b","pregunta":"?"}\n', encoding="utf-8"
        )
        informe = evaluar(ruta, etiqueta="prueba", escribir=False)
        assert len(informe.resultados) == 2


class TestInforme:
    def test_sabe_en_qué_columnas_menor_es_mejor(self):
        """Remarcar el máximo en coste o latencia convierte la tabla en un
        argumento en contra."""
        from agente_10k.evaluacion.informe import COLUMNAS_MENOR_ES_MEJOR

        assert "coste medio" in COLUMNAS_MENOR_ES_MEJOR
        assert "latencia media" in COLUMNAS_MENOR_ES_MEJOR
        assert "tool calls/pregunta" in COLUMNAS_MENOR_ES_MEJOR

    @FASE_5
    def test_la_tabla_principal_remarca_el_mejor_valor(self):
        from agente_10k.dominio.modelos import InformeEvaluacion
        from agente_10k.evaluacion.informe import tabla_principal

        tabla = tabla_principal(
            InformeEvaluacion(etiqueta="baseline"),
            InformeEvaluacion(etiqueta="final"),
        )
        assert "**" in tabla
