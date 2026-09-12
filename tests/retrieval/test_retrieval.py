"""Retrieval. Lo verde es el denso; lo `xfail` es la especificación de la fase 3.

Los `xfail(strict=True)` son deliberados: la suite queda verde, pero la
especificación sigue visible y en cuanto alguien implemente la pieza el test
pasa a `XPASS` y falla, obligando a quitar la marca. Es un recordatorio que no
se puede ignorar.
"""

from __future__ import annotations

import numpy as np
import pytest

from agente_10k.dominio.modelos import Filtros
from agente_10k.retrieval.codificador import PREFIJO_CONSULTA_BGE, CodificadorBge
from agente_10k.retrieval.denso import RecuperadorDenso, leer_vectores_planos

FASE_3 = pytest.mark.xfail(strict=True, reason="Fase 3 · Alonso")


class CodificadorDePrueba:
    """Codificador determinista sin modelo: hash de palabras a 8 dimensiones."""

    def __init__(self) -> None:
        self.consultas: list[str] = []

    @property
    def dimension(self) -> int:
        return 8

    def _vector(self, texto: str) -> list[float]:
        v = np.zeros(8, dtype="float32")
        for palabra in texto.lower().split():
            v[hash(palabra) % 8] += 1.0
        norma = float(np.linalg.norm(v)) or 1.0
        return [float(x) / norma for x in v]

    def codificar_consulta(self, consulta):
        self.consultas.append(consulta)
        return self._vector(consulta)

    def codificar_pasajes(self, pasajes):
        return [self._vector(p) for p in pasajes]


@pytest.fixture
def denso(repo_fragmentos):
    codificador = CodificadorDePrueba()
    matriz = np.array(
        codificador.codificar_pasajes(f.texto for f in repo_fragmentos.todos()),
        dtype="float32",
    )
    return RecuperadorDenso(repo_fragmentos, codificador, matriz=matriz)


class ModeloDeEmbeddingsDePrueba:
    """Hace de `SentenceTransformer` y apunta exactamente qué se le pasó.

    Es aquí donde hay que comprobar el prefijo: es lo último que toca el texto
    antes de convertirse en vector.
    """

    def __init__(self) -> None:
        self.textos: list[str] = []

    def encode(self, textos, normalize_embeddings=True, convert_to_numpy=True):
        self.textos.extend(textos)
        return np.ones((len(textos), 384), dtype="float32") / np.sqrt(384)


class TestPrefijoBge:
    """El fallo silencioso del retrieval: omitir el prefijo no da error, solo
    recupera peor. Y ponerlo en los dos lados es igual de malo."""

    def test_la_consulta_lleva_prefijo(self):
        modelo = ModeloDeEmbeddingsDePrueba()
        CodificadorBge(modelo_cargado=modelo).codificar_consulta("AI misuse risk")
        assert modelo.textos == [PREFIJO_CONSULTA_BGE + "AI misuse risk"]

    def test_los_pasajes_NO_llevan_prefijo(self):
        """Ponerlo en los dos lados hunde el recall igual que no ponerlo, y es
        todavía menos evidente."""
        modelo = ModeloDeEmbeddingsDePrueba()
        CodificadorBge(modelo_cargado=modelo).codificar_pasajes(["un pasaje"])
        assert modelo.textos == ["un pasaje"]

    def test_el_prefijo_es_el_del_manifiesto(self):
        assert PREFIJO_CONSULTA_BGE == (
            "Represent this sentence for searching relevant passages: "
        )

    def test_es_el_mismo_prefijo_que_usa_el_baseline_del_profesor(self):
        """Si se separan, nuestro retrieval mide contra otro índice."""
        from tests.conftest import RAIZ

        texto = (RAIZ / "src/agente_10k/baseline/miax_s1.py").read_text(
            encoding="utf-8"
        )
        assert PREFIJO_CONSULTA_BGE.strip() in texto

    def test_el_codificador_real_declara_384_dimensiones(self):
        """Sin cargar el modelo: importar tiene que seguir siendo instantáneo."""
        assert CodificadorBge().dimension == 384


class TestRecuperadorDenso:
    def test_devuelve_k_fragmentos(self, denso):
        assert len(denso.recuperar("risk factors", k=3)) == 3

    def test_vienen_ordenados_de_mayor_a_menor(self, denso):
        encontrados = denso.recuperar("AI misuse", k=5)
        puntuaciones = [f.puntuacion for f in encontrados]
        assert puntuaciones == sorted(puntuaciones, reverse=True)

    def test_rellena_la_puntuacion(self, denso):
        assert denso.recuperar("risk", k=1)[0].puntuacion is not None

    def test_aplica_los_filtros(self, denso):
        encontrados = denso.recuperar("risk", Filtros(ticker="MSFT"), k=10)
        assert {f.ticker for f in encontrados} == {"MSFT"}

    def test_no_lanza_cuando_el_filtro_no_deja_nada(self, denso):
        assert denso.recuperar("risk", Filtros(ticker="TSLA"), k=5) == []

    def test_detecta_el_indice_desalineado(self, repo_fragmentos):
        """El peor fallo del retrieval: devuelve texto equivocado sin avisar."""
        from agente_10k.dominio.errores import IndiceDesalineado

        with pytest.raises(IndiceDesalineado):
            RecuperadorDenso(
                repo_fragmentos,
                CodificadorDePrueba(),
                matriz=np.zeros((3, 8), dtype="float32"),
            )


class TestLectorDeIndicePlano:
    def test_rechaza_un_fichero_que_no_es_un_indice(self, tmp_path):
        ruta = tmp_path / "falso.faiss"
        ruta.write_bytes(b"NOPE" + b"\x00" * 100)
        with pytest.raises(ValueError, match="IndexFlat"):
            leer_vectores_planos(ruta, 8)

    def test_avisa_si_no_encuentra_el_fichero(self, tmp_path):
        from agente_10k.dominio.errores import CorpusNoEncontrado

        with pytest.raises(CorpusNoEncontrado):
            leer_vectores_planos(tmp_path / "no.faiss", 8)

    @pytest.mark.corpus
    def test_lee_el_indice_real_sin_faiss(self):
        from agente_10k.config import Settings
        from tests.conftest import RAIZ, hay_corpus_real

        if not hay_corpus_real():
            pytest.skip("el corpus real no está montado")
        cfg = Settings(dir_corpus=RAIZ / "data" / "corpus")
        vectores = leer_vectores_planos(cfg.ruta_indice, 384)
        assert vectores.shape == (1749, 384)
        normas = np.linalg.norm(vectores, axis=1)
        assert np.allclose(normas, 1.0, atol=1e-4), (
            "El manifiesto dice que los vectores están normalizados y el índice "
            "usa producto interno. Si no lo están, la puntuación no es coseno."
        )


# ---------------------------------------------------------------------------
# FASE 3 — la especificación, en rojo
# ---------------------------------------------------------------------------


class TestFusionRrf:
    """RRF se prueba con rankings sintéticos: sin modelo, sin índice, sin red."""

    @FASE_3
    def test_un_documento_primero_en_las_dos_listas_gana(self):
        from agente_10k.retrieval.hibrido import fusionar_rrf

        fusion = fusionar_rrf([["a", "b", "c"], ["a", "c", "b"]], k_rrf=60)
        assert fusion[0][0] == "a"

    @FASE_3
    def test_un_documento_que_solo_ve_uno_puede_superar_a_uno_mediocre(self):
        """Es la razón de ser de la fusión: rescatar lo que un recuperador ve y
        el otro no."""
        from agente_10k.retrieval.hibrido import fusionar_rrf

        fusion = dict(fusionar_rrf([["x", "m"], ["m", "y"]], k_rrf=1))
        assert fusion["m"] > fusion["x"]

    @FASE_3
    def test_no_suma_puntuaciones_sino_puestos(self):
        """La similitud coseno vive en [-1,1] y BM25 no tiene cota: sumarlas es
        comparar magnitudes que no son comparables."""
        from agente_10k.retrieval.hibrido import fusionar_rrf

        fusion = dict(fusionar_rrf([["a"], ["b"]], k_rrf=60))
        assert fusion["a"] == pytest.approx(fusion["b"])

    @FASE_3
    def test_k_rrf_cambia_el_resultado(self):
        from agente_10k.retrieval.hibrido import fusionar_rrf

        rankings = [["a", "b"], ["b", "a"]]
        assert fusionar_rrf(rankings, k_rrf=1) != fusionar_rrf(rankings, k_rrf=1000)


class TestTokenizadorBm25:
    """En texto financiero los números y los guiones importan."""

    @FASE_3
    def test_no_parte_los_numeros_por_el_separador_de_millar(self):
        from agente_10k.retrieval.lexico import tokenizar

        assert "60,922" in tokenizar("Revenue $ 60,922 million")

    @FASE_3
    def test_conserva_las_palabras_con_guion(self):
        from agente_10k.retrieval.lexico import tokenizar

        assert "ai-related" in tokenizar("AI-related risks")


class TestFiltroPrevio:
    @FASE_3
    def test_filtrar_antes_no_desperdicia_el_presupuesto_de_k(self, repo_fragmentos):
        """Filtrar después de recuperar k puede devolver cero resultados
        habiendo gastado la búsqueda entera."""
        from agente_10k.retrieval.filtro_metadatos import ConFiltroMetadatos

        envuelto = ConFiltroMetadatos(
            _RecuperadorTonto(repo_fragmentos), repo_fragmentos
        )
        encontrados = envuelto.recuperar("x", Filtros(ticker="AMZN"), k=3)
        assert len(encontrados) == 3
        assert {f.ticker for f in encontrados} == {"AMZN"}

    @FASE_3
    def test_devuelve_un_recuperador(self, repo_fragmentos):
        """P2: el decorador tiene que poder envolverse otra vez."""
        from agente_10k.dominio.protocolos import Recuperador
        from agente_10k.retrieval.filtro_metadatos import ConFiltroMetadatos

        envuelto = ConFiltroMetadatos(
            _RecuperadorTonto(repo_fragmentos), repo_fragmentos
        )
        assert isinstance(envuelto, Recuperador)


class TestReescritura:
    @FASE_3
    def test_traduce_la_consulta_al_idioma_del_corpus(self, repo_fragmentos):
        from agente_10k.agente.proveedores import ProveedorFake
        from agente_10k.retrieval.reescritura import ConReescritura

        proveedor = ProveedorFake(respuestas=["AI misuse by third parties"])
        envuelto = ConReescritura(_RecuperadorTonto(repo_fragmentos), proveedor)
        assert envuelto.reescribir("¿riesgos de mal uso de la IA?") == (
            "AI misuse by third parties"
        )

    @FASE_3
    def test_contabiliza_lo_que_cuesta(self, repo_fragmentos):
        """Sin esto, la fila de la reescritura en la tabla parecería gratis."""
        from agente_10k.agente.proveedores import ProveedorFake
        from agente_10k.retrieval.reescritura import ConReescritura

        envuelto = ConReescritura(
            _RecuperadorTonto(repo_fragmentos), ProveedorFake(respuestas=["x"])
        )
        envuelto.recuperar("consulta", k=1)
        assert envuelto.uso_acumulado().tokens_total > 0


class TestFabrica:
    def test_la_tabla_de_ablacion_esta_declarada_como_datos(self):
        """Añadir una fila es añadir una tupla, nunca escribir código."""
        from agente_10k.retrieval.fabrica import CONFIGURACIONES_ABLACION

        nombres = [n for n, _ in CONFIGURACIONES_ABLACION]
        assert nombres[0] == "denso (base)"
        assert "+ filtro metadatos" in nombres
        assert "+ BM25 (híbrido RRF)" in nombres
        assert "+ reescritura de consulta" in nombres

    def test_la_reescritura_sin_proveedor_lo_dice(self, corpus_fixture):
        from agente_10k.config import Settings
        from agente_10k.retrieval.fabrica import construir_recuperador

        cfg = Settings(dir_corpus=corpus_fixture.dir_corpus, reescritura_consulta=True)
        with pytest.raises((ValueError, NotImplementedError)):
            construir_recuperador(corpus_fixture, cfg)

    def test_un_recuperador_desconocido_lo_dice(self, corpus_fixture):
        from agente_10k.config import Settings
        from agente_10k.retrieval.fabrica import construir_recuperador

        cfg = Settings(dir_corpus=corpus_fixture.dir_corpus)
        object.__setattr__(cfg, "recuperador", "inventado")
        with pytest.raises(ValueError, match="desconocido"):
            construir_recuperador(corpus_fixture, cfg)


class _RecuperadorTonto:
    """Devuelve los fragmentos en el orden del repositorio, sin filtrar."""

    def __init__(self, fragmentos) -> None:
        self._fragmentos = fragmentos

    @property
    def nombre(self) -> str:
        return "tonto"

    def recuperar(self, consulta, filtros=None, k=5):
        return list(self._fragmentos.todos())[:k]
