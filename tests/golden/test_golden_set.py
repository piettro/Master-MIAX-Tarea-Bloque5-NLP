"""El validador del golden set. CONTRATO C4.

El test sobre el fichero real está marcado `xfail(strict=True)`: hoy el golden
set no existe y tiene que estar en verde antes del 17 de septiembre, porque la
sesión 2 empieza ejecutando nuestro baseline y clasificando sus fallos. Cuando
las 20 preguntas estén escritas, este test pasará a XPASS y obligará a quitar la
marca, que es exactamente el recordatorio que hace falta.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import ClassVar

import pytest

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from golden.validador import (  # noqa: E402
    MINIMO_COMPARATIVAS,
    MINIMO_HUECOS,
    MINIMO_PREGUNTAS,
    fusionar_parciales,
    informe_legible,
    leer,
    validar,
)

PLANTILLA = {
    "id": "g-p-001",
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
    "autor": "piettro",
}


def problemas_de(cambios: dict[str, object]) -> list[str]:
    return validar([{**PLANTILLA, **cambios}], exigir_completo=False)


def sin_avisos(problemas: list[str]) -> list[str]:
    return [p for p in problemas if "AVISO" not in p]


class TestEstructura:
    def test_la_plantilla_pasa_su_propio_validador(self):
        assert sin_avisos(problemas_de({})) == []

    def test_detecta_campos_que_faltan(self):
        incompleta = {k: v for k, v in PLANTILLA.items() if k != "unidad"}
        problemas = validar([incompleta], exigir_completo=False)
        assert any("faltan campos" in p for p in problemas)

    def test_detecta_ids_repetidos(self):
        problemas = validar([PLANTILLA, PLANTILLA], exigir_completo=False)
        assert any("id repetido" in p for p in problemas)

    def test_rechaza_una_familia_inventada(self):
        assert sin_avisos(problemas_de({"familia": "hueco"}))

    def test_rechaza_una_herramienta_que_no_existe(self):
        problemas = problemas_de({"herramienta_esperada": ["buscar_cosas"]})
        assert any("no existe" in p for p in problemas)

    def test_exige_autor(self):
        assert any("sin autor" in p for p in problemas_de({"autor": ""}))

    def test_exige_que_chunk_id_esperado_quede_a_null(self):
        """El identificador cambia en cuanto se re-trocea el corpus."""
        problemas = problemas_de({"chunk_id_esperado": "NVDA-2024-7-0000"})
        assert any("chunk_id_esperado" in p for p in problemas)

    def test_rechaza_un_item_que_no_existe(self):
        problemas = problemas_de({"item_esperado": "9Z"})
        assert any("no válido" in p for p in problemas)


class TestFamiliaNumerica:
    def test_exige_get_xbrl_fact(self):
        """Acertar leyendo la cifra del texto es fallo: el camino es contrato."""
        problemas = problemas_de({"herramienta_esperada": ["search_filings"]})
        assert any("debe pasar por get_xbrl_fact" in p for p in problemas)

    def test_exige_unidad_si_hay_cifra(self):
        assert any("sin unidad" in p for p in problemas_de({"unidad": None}))

    def test_avisa_si_la_cifra_parece_en_millones(self):
        """Las magnitudes del corpus van en USD, no en millones."""
        problemas = problemas_de({"cifra_esperada": 60922.0})
        assert any("unidades base" in p for p in problemas)

    def test_un_hueco_sin_concepto_es_ambiguo(self):
        problemas = problemas_de({"cifra_esperada": None, "concept_xbrl": None})
        assert any("hueco real" in p for p in problemas)

    def test_un_hueco_bien_declarado_pasa(self):
        assert (
            sin_avisos(
                problemas_de(
                    {
                        "id": "g-p-002",
                        "ticker": "AMZN",
                        "fiscal_year": 2025,
                        "concept_xbrl": "GrossProfit",
                        "cifra_esperada": None,
                        "unidad": None,
                    }
                )
            )
            == []
        )


class TestFamiliaExtractiva:
    BASE: ClassVar[dict[str, object]] = {
        "id": "g-p-003",
        "familia": "extractiva",
        "ticker": "MSFT",
        "fiscal_year": 2025,
        "cifra_esperada": None,
        "unidad": None,
        "concept_xbrl": None,
        "item_esperado": "1A",
        "herramienta_esperada": ["search_filings"],
    }

    def test_exige_ancla_texto(self):
        problemas = problemas_de({**self.BASE, "ancla_texto": None})
        assert any("sin ancla_texto" in p for p in problemas)

    def test_rechaza_un_ancla_de_tres_parrafos(self):
        """«Así no medís vuestro retrieval, medís vuestro tamaño de ventana»."""
        problemas = problemas_de({**self.BASE, "ancla_texto": "palabra " * 50})
        assert any("Una frase" in p for p in problemas)

    ANCLA = "Our AI systems offer users powerful tools and capabilities."

    def test_un_ancla_que_no_esta_en_el_corpus_invalida_la_pregunta(self):
        """Si no aparece literalmente está mal transcrita, y no es «casi bien»:
        el evaluador de cita nunca podrá darla por buena."""
        problemas = problemas_de(
            {**self.BASE, "ancla_texto": "Our AI systems offer powerful tools."}
        )
        assert any("NO aparece literalmente" in p for p in problemas)

    def test_un_ancla_literal_pasa(self):
        assert sin_avisos(problemas_de({**self.BASE, "ancla_texto": self.ANCLA})) == []

    def test_detecta_un_ancla_del_emisor_equivocado(self):
        problemas = problemas_de(
            {**self.BASE, "ticker": "AMZN", "ancla_texto": self.ANCLA}
        )
        assert any("no en ningún documento de AMZN" in p for p in problemas)

    def test_detecta_un_ancla_del_item_equivocado(self):
        problemas = problemas_de(
            {**self.BASE, "item_esperado": "7", "ancla_texto": self.ANCLA}
        )
        assert any("no está en el Item 7" in p for p in problemas)

    def test_detecta_offsets_incoherentes(self):
        problemas = problemas_de(
            {
                **self.BASE,
                "ancla_texto": self.ANCLA,
                "ancla_inicio": 100,
                "ancla_fin": 102,
            }
        )
        assert any("abarcan" in p for p in problemas)


class TestComposicion:
    def test_exige_veinte_preguntas(self):
        problemas = validar([PLANTILLA], exigir_completo=True)
        assert any(f"{MINIMO_PREGUNTAS} preguntas" in p for p in problemas)

    def test_exige_seis_comparativas(self):
        problemas = validar([PLANTILLA], exigir_completo=True)
        assert any(f"{MINIMO_COMPARATIVAS} comparativas" in p for p in problemas)

    def test_exige_dos_huecos_reales(self):
        problemas = validar([PLANTILLA], exigir_completo=True)
        assert any(f"{MINIMO_HUECOS} preguntas de hueco" in p for p in problemas)

    def test_exige_las_tres_familias(self):
        problemas = validar([PLANTILLA], exigir_completo=True)
        assert any("familia 'extractiva'" in p for p in problemas)
        assert any("familia 'comparativa'" in p for p in problemas)

    def test_cuenta_cuantas_faltan(self):
        """El informe tiene que decir qué arreglar, no solo que algo falla."""
        problemas = validar([PLANTILLA], exigir_completo=True)
        assert any("faltan 19" in p for p in problemas)


class TestFusionDeParciales:
    def test_fusiona_los_ficheros_de_los_tres_autores(self, tmp_path):
        """Cada autor en su fichero: así no hay conflictos de merge en un JSONL."""
        parciales = tmp_path / "parciales"
        parciales.mkdir()
        (parciales / "piettro.jsonl").write_text(
            json.dumps({**PLANTILLA, "id": "g-p-001"}) + "\n", encoding="utf-8"
        )
        (parciales / "alonso.jsonl").write_text(
            json.dumps({**PLANTILLA, "id": "g-a-001"}) + "\n", encoding="utf-8"
        )
        destino = tmp_path / "golden_set.jsonl"
        assert fusionar_parciales(parciales, destino) == 2
        assert len(leer(destino)) == 2

    def test_un_id_repetido_entre_ficheros_lo_dice(self, tmp_path):
        parciales = tmp_path / "parciales"
        parciales.mkdir()
        for nombre in ("piettro.jsonl", "alonso.jsonl"):
            (parciales / nombre).write_text(
                json.dumps(PLANTILLA) + "\n", encoding="utf-8"
            )
        with pytest.raises(ValueError, match="repetido"):
            fusionar_parciales(parciales, tmp_path / "g.jsonl")


class TestInformeLegible:
    def test_dice_que_es_valido_cuando_lo_es(self):
        assert "es válido" in informe_legible("x.jsonl", [])

    def test_enumera_los_problemas(self):
        salida = informe_legible("x.jsonl", ["a", "b"])
        assert "2 problema" in salida
        assert "- a" in salida


def test_el_golden_set_de_ejemplo_del_profesor_se_lee():
    ruta = RAIZ / "golden" / "golden_set_ejemplo.jsonl"
    if not ruta.is_file():
        pytest.skip("no está el fichero de ejemplo")
    assert len(leer(ruta)) == 3


@pytest.mark.xfail(
    strict=True,
    reason="FASE 2 · los tres: 20 preguntas, >=6 comparativas, >=2 huecos. "
    "Tiene que estar en verde antes del 17 de septiembre.",
)
def test_nuestro_golden_set_esta_completo_y_es_valido():
    ruta = RAIZ / "golden" / "golden_set.jsonl"
    problemas = (
        validar(leer(ruta), exigir_completo=True)
        if ruta.is_file()
        else ["golden/golden_set.jsonl no existe todavía"]
    )
    assert sin_avisos(problemas) == [], informe_legible(ruta, problemas)
