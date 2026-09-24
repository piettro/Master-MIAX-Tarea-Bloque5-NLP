"""Construye el pipeline de retrieval desde `Settings`.

Este es el sitio donde P1 y P2 se convierten en una tabla: cada fila de la
ablación es una `Settings` distinta pasada por aquí, y el runner de medición es
siempre el mismo. Si para sacar una fila hiciera falta duplicar código, el
diseño estaría mal.

El orden de envoltura importa y no es arbitrario:

    base (denso | léxico | híbrido)
      └─ ConFiltroMetadatos      ... restringe el espacio ANTES de buscar
           └─ ConReescritura     ... cambia la consulta ANTES de todo lo demás

La reescritura va por fuera porque actúa sobre la consulta, y el filtro por
dentro porque actúa sobre el espacio de búsqueda. Invertirlos haría que se
filtrara sobre la consulta original.
"""

from __future__ import annotations

from agente_10k.config import Settings, settings
from agente_10k.corpus import Corpus
from agente_10k.dominio.protocolos import ProveedorLLM, Recuperador
from agente_10k.retrieval.codificador import CodificadorBge
from agente_10k.retrieval.denso import RecuperadorDenso


def proveedor_de_reescritura(cfg: Settings) -> ProveedorLLM | None:
    """Quien reescribe la consulta, si la configuración lo pide.

    Está aquí y no en cada llamante para que el agente y la medición del
    recall usen exactamente el mismo recuperador: medir una configuración
    distinta de la que responde no vale nada.
    """
    if not cfg.reescritura_consulta:
        return None
    from agente_10k.agente.proveedores import construir_proveedor

    return construir_proveedor(cfg)


def construir_recuperador(
    corpus: Corpus,
    config: Settings | None = None,
    proveedor: ProveedorLLM | None = None,
) -> Recuperador:
    """El pipeline de retrieval que describe la configuración.

    Args:
        corpus: Los repositorios ya cargados.
        config: La configuración; por defecto, la del proceso.
        proveedor: Necesario solo si `reescritura_consulta` está activa.

    Returns:
        Un `Recuperador`, ya envuelto en los decoradores que pida la
        configuración.

    Raises:
        NotImplementedError: Si se pide un recuperador o un decorador de la
            fase 3 que todavía no está implementado. Es deliberado: mejor un
            error que diga qué falta que caer en silencio al denso y publicar
            una tabla de ablación en la que todas las filas son iguales.
    """
    cfg = config or settings()

    # Las precondiciones se comprueban ANTES de construir nada: montar el
    # índice denso para luego descubrir que falta el proveedor tarda segundos
    # y da un error que no habla de lo que de verdad pasa.
    if cfg.reescritura_consulta and proveedor is None:
        raise ValueError(
            "reescritura_consulta está activa pero no se pasó proveedor. La "
            "reescritura llama al modelo: no hay forma de hacerla sin él."
        )

    base = _base(corpus, cfg)
    if cfg.filtro_metadatos:
        from agente_10k.retrieval.filtro_metadatos import ConFiltroMetadatos

        base = ConFiltroMetadatos(base, corpus.fragmentos)
    if cfg.reordenacion:
        from agente_10k.retrieval.reordenacion import ConReordenacion

        # Va por dentro de la reescritura: el cross-encoder puntúa con la
        # consulta ya traducida, que es donde gana.
        base = ConReordenacion(
            base,
            cfg.modelo_reordenacion,
            cfg.profundidad_reordenacion,
            fusionar=cfg.fusion_reordenacion,
        )
    if cfg.reescritura_consulta:
        from agente_10k.retrieval.reescritura import ConReescritura

        ruta_cache = (cfg.dir_cache / "reescrituras.json") if cfg.cache_activa else None
        base = ConReescritura(
            base,
            proveedor,  # type: ignore[arg-type]
            cachear=cfg.cache_activa,
            ruta_cache=ruta_cache,
        )
    return base


def _base(corpus: Corpus, cfg: Settings) -> Recuperador:
    """El recuperador base, sin decoradores."""
    if cfg.recuperador == "denso":
        return RecuperadorDenso(
            fragmentos=corpus.fragmentos,
            codificador=CodificadorBge(dir_cache=cfg.dir_cache),
            ruta_indice=cfg.ruta_indice,
        )
    if cfg.recuperador == "lexico":
        from agente_10k.retrieval.lexico import RecuperadorLexico

        return RecuperadorLexico(corpus.fragmentos)
    if cfg.recuperador == "hibrido":
        from agente_10k.retrieval.hibrido import RecuperadorHibrido
        from agente_10k.retrieval.lexico import RecuperadorLexico

        return RecuperadorHibrido(
            [
                RecuperadorDenso(
                    fragmentos=corpus.fragmentos,
                    codificador=CodificadorBge(dir_cache=cfg.dir_cache),
                    ruta_indice=cfg.ruta_indice,
                ),
                RecuperadorLexico(corpus.fragmentos),
            ],
            k_rrf=cfg.rrf_k,
        )
    raise ValueError(f"Recuperador desconocido: {cfg.recuperador!r}")


SIN_MEJORAS: dict[str, object] = {
    "recuperador": "denso",
    "filtro_metadatos": False,
    "reescritura_consulta": False,
    "reordenacion": False,
    "fusion_reordenacion": False,
}
"""El retrieval de partida: el denso del profesor, sin nada encima.

Cada fila de la ablación se mide sobre ESTO más sus overrides, no sobre los
valores por defecto de `Settings`, que son los del sistema final (ADR-022). Si
se midiera sobre los de por defecto, la fila «denso (base)» llevaría puestas
todas las mejoras sin decirlo.
"""

CONFIGURACIONES_ABLACION: tuple[tuple[str, dict[str, object]], ...] = (
    ("denso (base)", {"recuperador": "denso", "filtro_metadatos": False}),
    ("+ filtro metadatos", {"recuperador": "denso", "filtro_metadatos": True}),
    ("+ BM25 (híbrido RRF)", {"recuperador": "hibrido", "filtro_metadatos": True}),
    (
        "+ reescritura de consulta",
        {
            "recuperador": "denso",
            "filtro_metadatos": True,
            "reescritura_consulta": True,
        },
    ),
    (
        "todo",
        {
            "recuperador": "hibrido",
            "filtro_metadatos": True,
            "reescritura_consulta": True,
        },
    ),
    (
        "+ reordenación (cross-encoder)",
        {
            "recuperador": "denso",
            "filtro_metadatos": True,
            "reordenacion": True,
        },
    ),
    (
        "+ reescritura + reordenación",
        {
            "recuperador": "denso",
            "filtro_metadatos": True,
            "reescritura_consulta": True,
            "reordenacion": True,
        },
    ),
    (
        "todo + reordenación",
        {
            "recuperador": "hibrido",
            "filtro_metadatos": True,
            "reescritura_consulta": True,
            "reordenacion": True,
        },
    ),
    (
        "+ reescritura + reordenación (RRF)",
        {
            "recuperador": "denso",
            "filtro_metadatos": True,
            "reescritura_consulta": True,
            "reordenacion": True,
            "fusion_reordenacion": True,
        },
    ),
    (
        "todo + reordenación (RRF)",
        {
            "recuperador": "hibrido",
            "filtro_metadatos": True,
            "reescritura_consulta": True,
            "reordenacion": True,
            "fusion_reordenacion": True,
        },
    ),
)
"""Las filas de la tabla de ablación, como datos.

Cada una es un conjunto de overrides sobre `Settings`. El runner de la fase 3
recorre esta tupla; añadir una fila es añadir una tupla, nunca escribir código.
"""
