"""Los contratos C5 y C6, y la congelación del baseline.

Estos tests protegen lo que se rompe sin que nadie se entere hasta el día 24.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

import pytest

RAIZ = Path(__file__).resolve().parent.parent


class TestContratoC5:
    """`responder()` y `evaluar()`, ejecutables en un clon limpio sin editar nada."""

    def test_se_importan_desde_la_raiz_del_paquete(self):
        from agente_10k import evaluar, responder

        assert callable(responder)
        assert callable(evaluar)

    def test_el_import_funciona_en_un_proceso_limpio(self):
        """Es literalmente lo que hará el evaluador externo el día 24."""
        r = subprocess.run(
            [sys.executable, "-c", "from agente_10k import responder, evaluar"],
            check=False,
            capture_output=True,
            text=True,
            cwd=RAIZ,
        )
        assert r.returncode == 0, r.stderr

    def test_responder_solo_pide_la_pregunta(self):
        import inspect

        from agente_10k import responder

        params = inspect.signature(responder).parameters
        assert list(params) == ["pregunta"]

    def test_evaluar_solo_pide_la_ruta(self):
        import inspect

        from agente_10k import evaluar

        assert list(inspect.signature(evaluar).parameters) == ["ruta_jsonl"]

    def test_importar_el_paquete_no_arrastra_langchain(self):
        """Importar `agente_10k` tiene que ser instantáneo y no fallar porque
        falte una dependencia opcional."""
        r = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, agente_10k; "
                "assert 'langchain' not in sys.modules, sorted(sys.modules)[:5]",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=RAIZ,
        )
        assert r.returncode == 0, r.stdout + r.stderr

    def test_las_rutas_de_settings_no_dependen_del_directorio_actual(self, tmp_path):
        """El día 24 se ejecuta desde donde sea."""
        r = subprocess.run(
            [
                sys.executable,
                "-c",
                "from agente_10k.config import Settings; "
                "print(Settings().dir_corpus.is_absolute())",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        assert r.stdout.strip() == "True", r.stderr


class TestContratoC6:
    """Ninguna clave de API en el repositorio."""

    # Los prefijos se componen en tiempo de ejecucion para que la cadena
    # literal no exista en el fichero: asi una auditoria a base de `grep -r`
    # sobre el repositorio no se encuentra a si misma y devuelve limpio.
    _SK = "s" + "k-"
    PATRONES: ClassVar[tuple[re.Pattern[str], ...]] = (
        re.compile(_SK + r"[A-Za-z0-9]{16,}"),
        re.compile(_SK + r"or-v1-[A-Za-z0-9]{8,}"),
        re.compile(r"""(?i)api[_-]?key\s*=\s*["'][A-Za-z0-9\-_]{16,}["']"""),
    )

    def _ficheros(self):
        for patron in (
            "src/**/*.py",
            "tests/**/*.py",
            "golden/**/*.py",
            "scripts/**/*.py",
            "notebooks/**/*.ipynb",
            "*.toml",
            "*.md",
        ):
            yield from RAIZ.glob(patron)

    def test_no_hay_claves_en_el_codigo(self):
        encontrados = []
        for ruta in self._ficheros():
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            for patron in self.PATRONES:
                if patron.search(texto):
                    encontrados.append(f"{ruta.relative_to(RAIZ)}: {patron.pattern}")
        assert not encontrados, f"Posibles secretos: {encontrados}"

    def test_env_esta_ignorado_y_env_example_no(self):
        gitignore = (RAIZ / ".gitignore").read_text(encoding="utf-8")
        assert "\n.env\n" in gitignore
        assert "!.env.example" in gitignore
        assert (RAIZ / ".env.example").is_file()

    def test_env_example_no_lleva_valores(self):
        for linea in (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines():
            if "API_KEY" in linea and not linea.startswith("#"):
                assert linea.strip().endswith("="), f"{linea!r} parece traer valor"

    def test_hay_gancho_de_secretos(self):
        config = (RAIZ / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        assert "detect-secrets" in config


class TestBaselineCongelado:
    """Congelarlo es irreversible, y es media tabla del informe."""

    def test_el_codigo_del_profesor_esta_preservado(self):
        assert (RAIZ / "src/agente_10k/baseline/miax_s1.py").is_file()

    def test_el_prefijo_de_bge_no_se_toco_al_copiarlo(self):
        texto = (RAIZ / "src/agente_10k/baseline/miax_s1.py").read_text(
            encoding="utf-8"
        )
        assert "Represent this sentence for searching relevant passages: " in texto

    def test_nuestro_prefijo_es_el_mismo_que_el_suyo(self):
        """Si se separan, nuestro retrieval mide contra otro índice."""
        from agente_10k.retrieval.codificador import PREFIJO_CONSULTA_BGE

        texto = (RAIZ / "src/agente_10k/baseline/miax_s1.py").read_text(
            encoding="utf-8"
        )
        assert PREFIJO_CONSULTA_BGE.strip() in texto

    def test_el_guardian_no_protesta_si_no_hay_nada_congelado(self):
        sys.path.insert(0, str(RAIZ / "scripts"))
        from comprobar_baseline import verificar

        assert verificar() == []

    def test_el_guardian_detecta_una_modificacion(self, tmp_path, monkeypatch):
        sys.path.insert(0, str(RAIZ / "scripts"))
        import comprobar_baseline as guardian

        monkeypatch.setattr(guardian, "DIR_BASELINE", tmp_path)
        monkeypatch.setattr(guardian, "RUTA_SELLO", tmp_path / "SELLO.json")
        (tmp_path / "detalle.json").write_text("original", encoding="utf-8")
        guardian.sellar()
        assert guardian.verificar() == []

        (tmp_path / "detalle.json").write_text("modificado", encoding="utf-8")
        problemas = guardian.verificar()
        assert any("MODIFICADO" in p for p in problemas)

    def test_el_guardian_detecta_un_borrado(self, tmp_path, monkeypatch):
        sys.path.insert(0, str(RAIZ / "scripts"))
        import comprobar_baseline as guardian

        monkeypatch.setattr(guardian, "DIR_BASELINE", tmp_path)
        monkeypatch.setattr(guardian, "RUTA_SELLO", tmp_path / "SELLO.json")
        fichero = tmp_path / "detalle.json"
        fichero.write_text("original", encoding="utf-8")
        guardian.sellar()
        fichero.unlink()
        assert any("BORRADO" in p for p in guardian.verificar())


class TestOrganizacionDelRepo:
    def test_el_enunciado_viaja_dentro_del_repo(self):
        """El repo tiene que leerse sin el aula virtual delante."""
        assert (RAIZ / "docs/enunciado.md").is_file()

    def test_el_material_de_clase_no_se_publica(self):
        """ADR-020: las transcripciones y los notebooks del profesor no son
        nuestros y se quedan en local."""
        import subprocess

        versionados = subprocess.check_output(
            ["git", "ls-files", "class_transcription", "notebooks"],
            cwd=RAIZ,
            text=True,
        )
        assert versionados.strip() == ""

    def test_hay_registro_de_decisiones(self):
        assert (RAIZ / "docs/decisiones.md").is_file()

    def test_el_manifiesto_del_indice_esta_versionado(self):
        """Es lo que permite comprobar que las tres máquinas tienen el mismo
        corpus sin versionar los 5,6 MB.

        Se comprueba contra git y no solo con `is_file()`: un patrón
        `data/corpus/**` excluye también los DIRECTORIOS, y git no desciende a
        un directorio excluido, así que la negación del manifiesto no llegaría
        a aplicarse nunca. El fichero estaría en disco y fuera del repositorio.
        """
        manifiesto = RAIZ / "data/corpus/indice/MANIFEST.md"
        assert manifiesto.is_file()
        r = subprocess.run(
            ["git", "check-ignore", "data/corpus/indice/MANIFEST.md"],
            check=False,
            capture_output=True,
            text=True,
            cwd=RAIZ,
        )
        assert r.returncode != 0, "el manifiesto está en .gitignore"

    def test_el_corpus_pesado_no_se_versiona(self):
        """5,6 MB que reparte el profesor y que no tienen por qué viajar."""
        r = subprocess.run(
            ["git", "check-ignore", "data/corpus/indice/chunks_meta.parquet"],
            check=False,
            capture_output=True,
            text=True,
            cwd=RAIZ,
        )
        assert r.returncode == 0, "chunks_meta.parquet debería estar ignorado"

    def test_resultados_tiene_su_protocolo_escrito(self):
        assert (RAIZ / "resultados/README.md").is_file()


@pytest.mark.parametrize(
    "objetivo",
    ["setup", "lint", "test", "baseline", "final", "informe", "validar-golden"],
)
def test_el_makefile_y_el_script_no_se_han_separado(objetivo):
    """El Makefile delega en el script: un objetivo en uno y no en el otro
    significa que en Windows no se puede ejecutar."""
    sys.path.insert(0, str(RAIZ / "scripts"))
    import tareas

    assert objetivo in tareas.OBJETIVOS
    assert objetivo in (RAIZ / "Makefile").read_text(encoding="utf-8")
