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
        autor="equipo",
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
        autor="equipo",
    )


class TestEvaluadorCita:
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

    def test_degrada_si_la_pregunta_no_trae_ancla(self, repo_fragmentos):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        p = Pregunta(id="c-001", pregunta="¿?", familia="extractiva")
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(
            p, RespuestaFinanciera(respuesta="x", fuente="texto")
        )
        assert veredicto.veredicto == "no_aplica"


class TestEvaluadorCifra:
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

    def test_acertar_el_hueco_es_cifra_none_y_fuente_ninguna(self, repo_xbrl):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCifra

        respuesta = RespuestaFinanciera(
            respuesta="Amazon no reporta margen bruto en us-gaap.",
            cifra=None,
            fuente="ninguna",
        )
        assert EvaluadorCifra(repo_xbrl).evaluar(pregunta_hueco(), respuesta).acierto

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
    def test_el_camino_correcto_acierta(self):
        from agente_10k.dominio.modelos import LlamadaHerramienta, Traza
        from agente_10k.evaluacion.evaluadores import EvaluadorTrayectoria

        traza = Traza(
            pregunta="?", llamadas=[LlamadaHerramienta(nombre="get_xbrl_fact")]
        )
        assert EvaluadorTrayectoria().evaluar(pregunta_hueco(), traza).acierto

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

    def test_degrada_si_no_hay_herramienta_esperada(self):
        from agente_10k.dominio.modelos import Traza
        from agente_10k.evaluacion.evaluadores import EvaluadorTrayectoria

        p = Pregunta(id="c-001", pregunta="¿?", familia="numerica")
        veredicto = EvaluadorTrayectoria().evaluar(p, Traza(pregunta="?"))
        assert veredicto.veredicto == "no_aplica"


class TestDecisionesDeLosEvaluadores:
    """Lo que los evaluadores deciden más allá de la especificación mínima.

    Cada caso es una decisión que hay que poder defender el día 24, y aquí queda
    escrita como algo que se ejecuta.
    """

    def test_una_cita_recortada_con_elipsis_y_comillas_acierta(self, repo_fragmentos):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        respuesta = RespuestaFinanciera(
            respuesta="x",
            fuente="texto",
            cita="“Our AI systems offer users … powerful tools and capabilities.”",
            chunk_id="MSFT-2025-1A-0001",
        )
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(
            pregunta_extractiva(), respuesta
        )
        assert veredicto.acierto, veredicto.motivo

    def test_una_cita_literal_lejos_del_ancla_no_la_respalda(self, repo_fragmentos):
        """Existir no basta: tiene que ser el pasaje que responde la pregunta."""
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        respuesta = RespuestaFinanciera(
            respuesta="x",
            fuente="texto",
            cita="We may not be able to detect every misuse in time.",
            chunk_id="MSFT-2025-1A-0002",
        )
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(
            pregunta_extractiva(), respuesta
        )
        assert not veredicto.acierto
        assert "no_respalda_ancla" in veredicto.detalle

    def test_una_cita_de_dos_palabras_no_prueba_nada(self, repo_fragmentos):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        respuesta = RespuestaFinanciera(
            respuesta="x",
            fuente="texto",
            cita="AI systems",
            chunk_id="MSFT-2025-1A-0001",
        )
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(
            pregunta_extractiva(), respuesta
        )
        assert "cita_no_literal" in veredicto.detalle

    def test_una_respuesta_xbrl_sin_ancla_no_se_evalua_por_cita(self, repo_fragmentos):
        """Exigir frase del informe a una cifra de XBRL castigaría el camino bueno."""
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCita

        respuesta = RespuestaFinanciera(
            respuesta="x",
            fuente="xbrl",
            cifra=1.0,
            cita="NVDA FY2024 Revenues = 60,922",
        )
        veredicto = EvaluadorCita(repo_fragmentos).evaluar(pregunta_hueco(), respuesta)
        assert veredicto.veredicto == "no_aplica"

    def test_una_cifra_copiada_en_millones_falla_con_diagnostico(self, repo_xbrl):
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCifra

        p = Pregunta(
            id="n-003",
            pregunta="?",
            familia="numerica",
            ticker="NVDA",
            fiscal_year=2024,
            concept_xbrl="Revenues",
            cifra_esperada=60_922_000_000.0,
            unidad="USD",
        )
        respuesta = RespuestaFinanciera(
            respuesta="x", cifra=60_922.0, unidad="millones de USD", fuente="xbrl"
        )
        veredicto = EvaluadorCifra(repo_xbrl).evaluar(p, respuesta)
        assert not veredicto.acierto
        assert "escala" in veredicto.detalle
        assert "unidad_incoherente" not in veredicto.detalle

    def test_un_hueco_mal_marcado_no_castiga_la_cifra_correcta(self, repo_xbrl):
        """Si XBRL sí tiene el dato, manda XBRL, no la etiqueta del golden set."""
        from agente_10k.dominio.modelos import RespuestaFinanciera
        from agente_10k.evaluacion.evaluadores import EvaluadorCifra

        p = pregunta_hueco().model_copy(update={"concept_xbrl": "NetIncomeLoss"})
        respuesta = RespuestaFinanciera(
            respuesta="x", cifra=65_000_000_000.0, unidad="USD", fuente="xbrl"
        )
        evaluador = EvaluadorCifra(repo_xbrl)
        assert evaluador.evaluar(p, respuesta).acierto
        assert not evaluador.es_alucinacion_sobre_hueco(p, respuesta)

    def test_una_comparativa_necesita_cifra_y_cita(self):
        from agente_10k.dominio.modelos import VeredictoEvaluador
        from agente_10k.evaluacion.evaluadores import es_respuesta_correcta

        bien = VeredictoEvaluador(veredicto="acierto")
        mal = VeredictoEvaluador(veredicto="fallo")
        nada = VeredictoEvaluador(veredicto="no_aplica")
        assert es_respuesta_correcta("comparativa", bien, bien) is True
        assert es_respuesta_correcta("comparativa", bien, mal) is False
        assert es_respuesta_correcta("comparativa", nada, bien) is True
        assert es_respuesta_correcta("comparativa", nada, nada) is None

    def test_una_lectura_cara_de_mas_no_suspende_pero_se_anota(self):
        from agente_10k.dominio.modelos import LlamadaHerramienta, Traza
        from agente_10k.evaluacion.evaluadores import EvaluadorTrayectoria

        traza = Traza(
            pregunta="?",
            llamadas=[
                LlamadaHerramienta(nombre="read_section"),
                LlamadaHerramienta(nombre="get_xbrl_fact"),
            ],
        )
        veredicto = EvaluadorTrayectoria().evaluar(pregunta_hueco(), traza)
        assert veredicto.acierto
        assert veredicto.detalle["lectura_cara_innecesaria"] == 1


class TestEjecutor:
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

    def test_la_tabla_principal_remarca_el_mejor_valor(self):
        from agente_10k.dominio.modelos import InformeEvaluacion
        from agente_10k.evaluacion.informe import tabla_principal

        tabla = tabla_principal(
            InformeEvaluacion(etiqueta="baseline"),
            InformeEvaluacion(etiqueta="final"),
        )
        assert "**" in tabla


def _resultado(pid, *, acierto, familia="numerica", hueco=False, fuente="xbrl"):
    from agente_10k.dominio.modelos import RespuestaFinanciera, ResultadoPregunta

    return ResultadoPregunta(
        pregunta_id=pid,
        familia=familia,
        es_hueco=hueco,
        acierto=acierto,
        respuesta_correcta=acierto,
        respuesta=RespuestaFinanciera(respuesta="x", fuente=fuente),
    )


class TestMetricasNuevas:
    """MRR, denominadores por familia y abstención indebida."""

    def test_el_mrr_es_la_media_del_inverso_del_puesto(self):
        from agente_10k.evaluacion.metricas import mrr

        assert mrr({"a": 1, "b": 2, "c": None}) == pytest.approx((1 + 0.5 + 0) / 3)

    def test_sin_puestos_el_mrr_es_cero(self):
        from agente_10k.evaluacion.metricas import mrr

        assert mrr({}) == 0.0

    def test_guarda_el_denominador_de_cada_familia(self):
        """Sin `n`, no se puede poner un intervalo al lado de la proporción."""
        from agente_10k.evaluacion.metricas import agregar

        metricas = agregar(
            [
                _resultado("a", acierto=True),
                _resultado("b", acierto=False),
                _resultado("c", acierto=True, familia="extractiva"),
            ]
        )
        assert metricas.n_por_familia["numerica"] == 2
        assert metricas.n_por_familia["total"] == 3
        assert metricas.aciertos_por_familia["numerica"] == pytest.approx(0.5)

    def test_cuenta_la_abstencion_indebida_solo_donde_habia_dato(self):
        from agente_10k.evaluacion.metricas import agregar

        metricas = agregar(
            [
                _resultado("a", acierto=False, fuente="ninguna"),
                _resultado("b", acierto=True),
                _resultado("c", acierto=True, hueco=True, fuente="ninguna"),
            ]
        )
        # El hueco no entra: ahí abstenerse es lo correcto.
        assert metricas.tasa_abstencion_indebida == pytest.approx(0.5)


class TestSignificancia:
    """La tabla que dice si la mejora aguanta un contraste."""

    def _informe(self, etiqueta, aciertos):
        from agente_10k.dominio.modelos import InformeEvaluacion
        from agente_10k.evaluacion.metricas import agregar

        resultados = [_resultado(f"p{i}", acierto=a) for i, a in enumerate(aciertos, 1)]
        return InformeEvaluacion(
            etiqueta=etiqueta, resultados=resultados, metricas=agregar(resultados)
        )

    def test_lleva_los_dos_intervalos_y_el_p_valor(self):
        from agente_10k.evaluacion.informe import tabla_significancia

        a = self._informe("baseline", [True] * 4 + [False] * 8)
        b = self._informe("final", [True] * 11 + [False])
        tabla = tabla_significancia(a, b)
        assert "4/12" in tabla and "11/12" in tabla
        assert "IC 95 %" in tabla
        assert "p = 0.016" in tabla
        assert "significativa" in tabla

    def test_dice_cuando_no_se_puede_descartar_el_ruido(self):
        from agente_10k.evaluacion.informe import tabla_significancia

        a = self._informe("baseline", [True] * 10 + [False] * 10)
        b = self._informe("final", [True] * 12 + [False] * 8)
        assert "no se puede descartar" in tabla_significancia(a, b)

    def test_sin_preguntas_comunes_lo_dice_en_vez_de_inventar(self):
        from agente_10k.dominio.modelos import InformeEvaluacion
        from agente_10k.evaluacion.informe import tabla_significancia

        tabla = tabla_significancia(
            InformeEvaluacion(etiqueta="a"), InformeEvaluacion(etiqueta="b")
        )
        assert "no comparten" in tabla


class TestGenerarTodo:
    """El camino que se recorre el día de la entrega, de punta a punta."""

    def _escribir(self, dir_resultados, etiqueta, aciertos):
        from agente_10k.dominio.modelos import InformeEvaluacion
        from agente_10k.evaluacion.metricas import agregar

        resultados = [_resultado(f"p{i}", acierto=a) for i, a in enumerate(aciertos, 1)]
        informe = InformeEvaluacion(
            etiqueta=etiqueta, resultados=resultados, metricas=agregar(resultados)
        )
        destino = dir_resultados / etiqueta
        destino.mkdir(parents=True)
        (destino / "informe.json").write_text(
            informe.model_dump_json(indent=2), encoding="utf-8", newline="\n"
        )

    def test_saca_todas_las_tablas_cuando_estan_los_tres_informes(self, tmp_path):
        from agente_10k.evaluacion.informe import generar_todo

        resultados = tmp_path / "resultados"
        self._escribir(resultados, "baseline", [True] * 4 + [False] * 8)
        self._escribir(resultados, "final", [True] * 10 + [False] * 2)
        self._escribir(resultados, "ciegas", [True] * 6 + [False] * 6)

        escritos = {r.name for r in generar_todo(resultados, tmp_path / "docs")}
        assert "tabla_principal.md" in escritos
        assert "tabla_principal.csv" in escritos
        assert "significancia.md" in escritos
        assert "delta_ciegas.md" in escritos
        assert {"resultados_baseline.md", "resultados_final.md"} <= escritos

    def test_con_solo_el_baseline_no_inventa_la_comparacion(self, tmp_path):
        """Es el estado real hasta que la fase 4 aterriza."""
        from agente_10k.evaluacion.informe import generar_todo

        resultados = tmp_path / "resultados"
        self._escribir(resultados, "baseline", [True, False])
        escritos = {r.name for r in generar_todo(resultados, tmp_path / "docs")}
        assert escritos == {"resultados_baseline.md"}

    def test_el_delta_de_ciegas_va_en_puntos_porcentuales(self, tmp_path):
        from agente_10k.evaluacion.informe import cargar_informe, tabla_delta

        resultados = tmp_path / "resultados"
        self._escribir(resultados, "final", [True] * 10 + [False] * 2)
        self._escribir(resultados, "ciegas", [True] * 6 + [False] * 6)
        tabla = tabla_delta(
            cargar_informe(resultados / "final" / "informe.json"),
            cargar_informe(resultados / "ciegas" / "informe.json"),
        )
        assert "pp" in tabla
        assert "-33 pp" in tabla or "−33 pp" in tabla


def test_con_variantes_del_final_saca_la_tabla_de_todos(tmp_path):
    """La ablación a nivel agente: baseline, variantes y final, en ese orden."""
    from agente_10k.evaluacion.informe import generar_todo

    escritor = TestGenerarTodo()
    resultados = tmp_path / "resultados"
    escritor._escribir(resultados, "baseline", [True, False])
    escritor._escribir(resultados, "final", [True, True])
    escritor._escribir(resultados, "final-sin-mejoras-retrieval", [True, False])
    generar_todo(resultados, tmp_path / "docs")
    tabla = (tmp_path / "docs" / "tabla_sistemas.md").read_text(encoding="utf-8")
    filas = [f.split("|")[1].strip() for f in tabla.splitlines()[2:]]
    assert filas == ["baseline", "final-sin-mejoras-retrieval", "final"]
