"""Fixtures de la suite. Diminutas, sin corpus real, sin red, sin clave de API.

Tres secciones, veinte fragmentos y diez hechos XBRL bastan para cubrir las tres
trampas del enunciado:

* **T1 fiscal_year** — NVDA tiene FY2024 (cierre 26/01) y FY2025 (cierre 26/01
  del año siguiente); MSFT cierra en junio y AMZN en diciembre.
* **T2 concepto XBRL** — NVDA reporta `Revenues` y NO
  `RevenueFromContractWithCustomerExcludingAssessedTax`; MSFT al revés.
* **T3 hueco real** — AMZN no reporta `GrossProfit` en la fixture, igual que en
  el corpus real.

La suite entera tiene que correr en segundos. Cualquier test que necesite el
corpus completo lleva `@pytest.mark.corpus` y se omite si no está montado.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from agente_10k.config import Settings
from agente_10k.corpus import Corpus
from agente_10k.corpus.fragmentos import RepositorioFragmentosMemoria
from agente_10k.corpus.secciones import RepositorioSeccionesMemoria
from agente_10k.corpus.xbrl import RepositorioXbrlMemoria
from agente_10k.dominio.modelos import HechoXbrl
from agente_10k.tools.implementacion import Herramientas

DIR_FIXTURES = Path(__file__).parent / "fixtures"
RAIZ = Path(__file__).resolve().parent.parent


def _leer_jsonl(nombre: str) -> list[dict[str, object]]:
    ruta = DIR_FIXTURES / nombre
    return [
        json.loads(linea)
        for linea in ruta.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]


@pytest.fixture
def repo_fragmentos() -> RepositorioFragmentosMemoria:
    """Veinte fragmentos, con solapes y huecos como en el corpus real."""
    return RepositorioFragmentosMemoria.desde_jsonl(DIR_FIXTURES / "chunks.jsonl")


@pytest.fixture
def repo_secciones() -> RepositorioSeccionesMemoria:
    """Tres secciones leídas de fichero, no reconstruidas."""
    return RepositorioSeccionesMemoria.desde_jsonl(DIR_FIXTURES / "secciones.jsonl")


@pytest.fixture
def repo_xbrl() -> RepositorioXbrlMemoria:
    """Diez hechos XBRL con las dos trampas de conceptos dentro."""
    return RepositorioXbrlMemoria(
        HechoXbrl.model_validate(fila) for fila in _leer_jsonl("xbrl_facts.jsonl")
    )


@pytest.fixture
def corpus_fixture(
    repo_secciones: RepositorioSeccionesMemoria,
    repo_fragmentos: RepositorioFragmentosMemoria,
    repo_xbrl: RepositorioXbrlMemoria,
) -> Corpus:
    """Los tres repositorios de fixture montados como un `Corpus`."""
    return Corpus(
        secciones=repo_secciones,
        fragmentos=repo_fragmentos,
        xbrl=repo_xbrl,
        dir_corpus=DIR_FIXTURES,
    )


@pytest.fixture
def config_fixture() -> Settings:
    """Configuración apuntando a las fixtures, sin caché ni red."""
    return Settings(
        dir_corpus=DIR_FIXTURES,
        cache_activa=False,
        llm_provider="openrouter",
        llm_model="fake",
    )


@pytest.fixture
def herramientas(corpus_fixture: Corpus, config_fixture: Settings) -> Herramientas:
    """El cinturón montado sobre las fixtures, sin recuperador."""
    return Herramientas(corpus_fixture, recuperador=None, config=config_fixture)


@pytest.fixture
def cinturon_fixture(herramientas: Herramientas) -> Iterator[Herramientas]:
    """Instala el cinturón de fixture en `contratos` y lo retira al terminar."""
    from agente_10k.tools import contratos

    contratos.usar_cinturon(herramientas)
    yield herramientas
    contratos.usar_cinturon(None)


# ---------------------------------------------------------------------------
# Corpus real: opcional
# ---------------------------------------------------------------------------


def hay_corpus_real() -> bool:
    """Si el corpus completo está montado en `data/corpus`."""
    return (RAIZ / "data" / "corpus" / "indice" / "chunks_meta.parquet").is_file()


@pytest.fixture
def corpus_real() -> Corpus:
    """El corpus completo. Omite el test si no está montado."""
    if not hay_corpus_real():
        pytest.skip("el corpus real no está en data/corpus")
    from agente_10k.corpus import cargar_corpus

    return cargar_corpus(Settings(dir_corpus=RAIZ / "data" / "corpus"))
