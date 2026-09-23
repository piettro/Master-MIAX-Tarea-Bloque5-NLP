"""Reordenación con cross-encoder. Sin modelo real: se inyecta uno falso."""

from __future__ import annotations

import pytest

from agente_10k.dominio.modelos import Filtros, Fragmento
from agente_10k.retrieval import reordenacion
from agente_10k.retrieval.reordenacion import ConReordenacion


def frag(chunk_id: str, texto: str) -> Fragmento:
    return Fragmento(
        chunk_id=chunk_id,
        ticker="MSFT",
        fiscal_year=2025,
        item="1A",
        posicion=0,
        texto=texto,
        n_tokens=10,
        puntuacion=0.5,
    )


class RecuperadorFalso:
    def __init__(self, fragmentos):
        self.fragmentos = fragmentos
        self.k_pedida = None

    @property
    def nombre(self):
        return "falso"

    def recuperar(self, consulta, filtros=None, k=5):
        self.k_pedida = k
        return list(self.fragmentos[:k])


class CrossEncoderFalso:
    """Puntúa por cuántas palabras de la consulta aparecen en el texto."""

    def __init__(self):
        self.pares = []

    def predict(self, pares):
        self.pares = pares
        return [sum(p in t.lower() for p in c.lower().split()) for c, t in pares]


@pytest.fixture
def cross_encoder_falso(monkeypatch):
    falso = CrossEncoderFalso()
    monkeypatch.setattr(reordenacion, "_cross_encoder", lambda nombre: falso)
    return falso


def test_reordena_por_puntuacion_del_cross_encoder(cross_encoder_falso):
    base = RecuperadorFalso(
        [frag("a", "nada que ver"), frag("b", "riesgo de tipo de cambio")]
    )
    salida = ConReordenacion(base, profundidad=10).recuperar("tipo de cambio", k=2)
    assert [f.chunk_id for f in salida] == ["b", "a"]
    assert salida[0].puntuacion == 3


def test_pide_mas_candidatos_de_los_que_devuelve(cross_encoder_falso):
    base = RecuperadorFalso([frag(str(i), f"texto {i}") for i in range(30)])
    ConReordenacion(base, profundidad=20).recuperar("texto", k=5)
    assert base.k_pedida == 20


def test_con_un_solo_candidato_no_llama_al_modelo(cross_encoder_falso):
    base = RecuperadorFalso([frag("a", "solo uno")])
    salida = ConReordenacion(base).recuperar("lo que sea", Filtros(ticker="MSFT"), k=5)
    assert len(salida) == 1
    assert cross_encoder_falso.pares == []


def test_el_nombre_dice_que_hay_reordenacion(cross_encoder_falso):
    assert ConReordenacion(RecuperadorFalso([])).nombre == "falso+reordenacion"
