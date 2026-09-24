"""Acceso a los datos. P3: Repository.

`cargar_corpus()` monta los tres repositorios desde `Settings` y es el único
sitio del paquete que sabe dónde están los ficheros. Las tools reciben
repositorios ya construidos y no abren nada.

La carga está cacheada por ruta porque leer 1.749 fragmentos en cada llamada a
una tool sería absurdo. No es un singleton oculto: `cargar_corpus.cache_clear()`
lo vacía, y los tests construyen sus propios repositorios con fixtures sin
pasar por aquí.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from agente_10k.config import Settings, settings
from agente_10k.corpus.fragmentos import RepositorioFragmentosMemoria
from agente_10k.corpus.secciones import RepositorioSeccionesMemoria
from agente_10k.corpus.xbrl import RepositorioXbrlMemoria
from agente_10k.dominio.errores import CorpusNoEncontrado

__all__ = [
    "Corpus",
    "RepositorioFragmentosMemoria",
    "RepositorioSeccionesMemoria",
    "RepositorioXbrlMemoria",
    "cargar_corpus",
]


@dataclass(frozen=True)
class Corpus:
    """Los tres repositorios, ya montados, más el diagnóstico de la carga."""

    secciones: RepositorioSeccionesMemoria
    fragmentos: RepositorioFragmentosMemoria
    xbrl: RepositorioXbrlMemoria
    dir_corpus: Path
    secciones_reconstruidas: bool = False

    def avisos(self) -> list[str]:
        """Lo que falta o está degradado. Va a la traza y al informe.

        Existe para que una ejecución hecha sobre un corpus incompleto se pueda
        identificar después, en vez de descubrirlo al comparar tablas.
        """
        problemas: list[str] = []
        if self.secciones_reconstruidas:
            problemas.append(
                "secciones.jsonl no está: las secciones se derivaron de los "
                "fragmentos y NO son literales en las fronteras de troceado."
            )
        if not self.xbrl.disponible():
            problemas.append(
                "xbrl_facts.parquet no está: get_xbrl_fact no puede devolver "
                "ninguna cifra y el guardarraíl no puede contrastar nada."
            )
        return problemas


@lru_cache(maxsize=4)
def _cargar(dir_corpus: Path, permitir_reconstruidas: bool) -> Corpus:
    """Monta los tres repositorios desde una carpeta de corpus."""
    ruta_meta = dir_corpus / "indice" / "chunks_meta.parquet"
    ruta_chunks = dir_corpus / "chunks.jsonl"

    if ruta_meta.is_file():
        # Se prefiere el parquet del índice: es el que está ALINEADO con los
        # vectores, fila i <-> vector i.
        fragmentos = RepositorioFragmentosMemoria.desde_parquet(ruta_meta)
    elif ruta_chunks.is_file():
        fragmentos = RepositorioFragmentosMemoria.desde_jsonl(ruta_chunks)
    else:
        raise CorpusNoEncontrado(
            "chunks.jsonl ni indice/chunks_meta.parquet", str(dir_corpus)
        )

    ruta_secciones = dir_corpus / "secciones.jsonl"
    reconstruidas = False
    if ruta_secciones.is_file():
        secciones = RepositorioSeccionesMemoria.desde_jsonl(ruta_secciones)
    elif permitir_reconstruidas:
        secciones = RepositorioSeccionesMemoria.desde_fragmentos(fragmentos.todos())
        reconstruidas = True
    else:
        raise CorpusNoEncontrado("secciones.jsonl", str(dir_corpus))

    xbrl = RepositorioXbrlMemoria.desde_parquet(dir_corpus / "xbrl_facts.parquet")

    return Corpus(
        secciones=secciones,
        fragmentos=fragmentos,
        xbrl=xbrl,
        dir_corpus=dir_corpus,
        secciones_reconstruidas=reconstruidas,
    )


def cargar_corpus(config: Settings | None = None) -> Corpus:
    """Los tres repositorios montados desde la configuración."""
    cfg = config or settings()
    return _cargar(cfg.dir_corpus, cfg.permitir_secciones_reconstruidas)


def limpiar_cache() -> None:
    """Vacía la caché de carga. Para tests y para `make limpiar`."""
    _cargar.cache_clear()
