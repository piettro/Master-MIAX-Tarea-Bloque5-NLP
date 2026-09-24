"""Línea de órdenes. El único sitio del paquete donde se permite `print`.

agente-10k responder "¿Cuál fue el revenue de NVIDIA en el ejercicio 2024?"
agente-10k evaluar golden/golden_set.jsonl --etiqueta final
agente-10k validar-golden golden/golden_set.jsonl
agente-10k comparar baseline final
agente-10k diagnostico
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

import typer

from agente_10k.config import RAIZ_REPO, settings

if TYPE_CHECKING:
    from agente_10k.dominio.modelos import ResultadoPregunta
    from agente_10k.dominio.protocolos import ProveedorLLM

RUTA_GOLDEN_POR_DEFECTO = typer.Argument(Path("golden/golden_set.jsonl"))

app = typer.Typer(
    add_completion=False,
    help="Agente investigador sobre informes 10-K de la SEC.",
    no_args_is_help=True,
)


@app.callback()
def _entorno() -> None:
    """Carga `.env` antes de cualquier orden, para que la clave llegue al SDK."""
    from agente_10k.config import cargar_entorno

    cargar_entorno()


def _imprimir_progreso(n: int, total: int, r: ResultadoPregunta) -> None:
    """Una línea por pregunta mientras se evalúa: el día 24 hay que ver avanzar."""
    if r.error:
        estado = f"ERROR {r.error[:90]}"
    else:
        estado = {True: "acierto", False: "fallo", None: "sin veredicto"}[r.acierto]
    camino = " > ".join(r.traza.trayectoria) if r.traza else ""
    segundos = f"{r.traza.latencia_s:.1f} s" if r.traza else ""
    print(f"[{n}/{total}] {r.pregunta_id:<10} {estado:<14} {segundos:>7}  {camino}")


@app.command()
def diagnostico() -> None:
    """Dice qué hay montado y qué falta. Lo primero que ejecutar tras clonar."""
    from agente_10k.corpus import cargar_corpus

    cfg = settings()
    print(f"corpus        : {cfg.dir_corpus}")
    print(f"proveedor     : {cfg.llm_provider} · modelo {cfg.llm_model}")
    print(f"clave {cfg.variable_clave:<15}: {'sí' if cfg.hay_clave() else 'NO'}")
    print(f"recuperador   : {cfg.recuperador} (filtro={cfg.filtro_metadatos})")

    try:
        corpus = cargar_corpus(cfg)
    except Exception as exc:
        print(f"\nNo se pudo cargar el corpus: {exc}")
        raise typer.Exit(1) from exc

    print(f"\nsecciones     : {len(corpus.secciones)}")
    print(f"fragmentos    : {len(corpus.fragmentos)}")
    print(f"hechos XBRL   : {len(corpus.xbrl)}")
    print(f"índice FAISS  : {'sí' if cfg.ruta_indice.is_file() else 'NO'}")

    avisos = corpus.avisos()
    if avisos:
        print("\nAVISOS:")
        for aviso in avisos:
            print(f"  - {aviso}")
    else:
        print("\nTodo montado.")


@app.command()
def responder(pregunta: str) -> None:
    """Responde una pregunta y muestra la respuesta estructurada y la traza."""
    from agente_10k import responder_con_traza
    from agente_10k.agente.trazas import resumir

    respuesta, traza = responder_con_traza(pregunta)
    print(json.dumps(respuesta.model_dump(), indent=2, ensure_ascii=False))
    print(f"\n{resumir(traza)}")


@app.command()
def evaluar(
    ruta_jsonl: Path,
    etiqueta: str | None = typer.Option(
        None, help="Subcarpeta de resultados/. Por defecto final, o ciegas."
    ),
    sistema: str = typer.Option("final", help="final | baseline"),
    recall: bool = typer.Option(True, help="Medir el recall@k del retrieval"),
) -> None:
    """Ejecuta el sistema sobre un JSONL de preguntas y escribe los resultados."""
    from agente_10k.evaluacion.ejecutor import evaluar as _evaluar
    from agente_10k.evaluacion.informe import tabla_comparada
    from agente_10k.evaluacion.sistemas import SistemaBaseline

    elegido = SistemaBaseline() if sistema == "baseline" else None
    informe = _evaluar(
        ruta_jsonl,
        etiqueta=etiqueta,
        sistema=elegido,
        medir_retrieval=recall,
        progreso=_imprimir_progreso,
    )
    print(f"\n{informe}\n")
    print(tabla_comparada([informe]))
    print(f"escrito en {settings().dir_resultados / informe.etiqueta}")


@app.command(name="validar-golden")
def validar_golden(ruta_jsonl: Path) -> None:
    """Valida el golden set y explica qué falta. CONTRATO C4."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from golden.validador import informe_legible, validar_fichero

    problemas = validar_fichero(ruta_jsonl)
    print(informe_legible(ruta_jsonl, problemas))
    raise typer.Exit(1 if problemas else 0)


@app.command()
def baseline(
    ruta_jsonl: Path = RUTA_GOLDEN_POR_DEFECTO,
) -> None:
    """Ejecuta el baseline del profesor y lo CONGELA. Irreversible.

    El sistema es `miax_s2.baseline()`, el agente del día 10 que reparte el
    profesor, con el mismo modelo que el sistema final. El recall@k se mide con
    el retrieval de partida: denso, sin filtro previo y sin reescritura.
    """
    from agente_10k.evaluacion.ejecutor import evaluar as _evaluar
    from agente_10k.evaluacion.informe import tabla_comparada
    from agente_10k.evaluacion.sistemas import SistemaBaseline

    sys.path.insert(0, str(RAIZ_REPO / "scripts"))
    import comprobar_baseline as guardian  # type: ignore[import-not-found]

    if guardian.RUTA_SELLO.is_file():
        print(
            "resultados/baseline/ ya está CONGELADO. Si de verdad hay que "
            "regenerarlo, borra SELLO.json a mano y deja constancia en "
            "docs/decisiones.md de por qué."
        )
        raise typer.Exit(1)

    from agente_10k.retrieval.fabrica import SIN_MEJORAS

    cfg = settings().model_copy(update=dict(SIN_MEJORAS))
    informe = _evaluar(
        ruta_jsonl,
        etiqueta="baseline",
        sistema=SistemaBaseline(cfg),
        config=cfg,
        progreso=_imprimir_progreso,
    )
    print(f"\n{informe}\n")
    print(tabla_comparada([informe]))
    sello = guardian.sellar()
    print(f"CONGELADO: {len(sello['huellas'])} ficheros sellados en SELLO.json")


@app.command()
def ablacion(
    ruta_golden: Path = RUTA_GOLDEN_POR_DEFECTO,
) -> None:
    """Regenera la tabla de ablación del retrieval.

    Recorre `CONFIGURACIONES_ABLACION`, mide `recall@k` contra el ancla de texto
    del golden set y escribe `resultados/retrieval/ablacion.{md,csv}` más el
    detalle por pregunta. Necesita el corpus montado y un golden set con anclas;
    si falta algo, lo dice en vez de escribir una tabla vacía.

    La fila de la reescritura necesita la clave del modelo: si no la hay, esa
    fila sale marcada como «pendiente» y las demás se miden igual.
    """
    from agente_10k.corpus import cargar_corpus
    from agente_10k.dominio.errores import CorpusNoEncontrado
    from agente_10k.evaluacion.ejecutor import leer_preguntas
    from agente_10k.retrieval.medicion import (
        ejecutar_ablacion,
        escribir_ablacion,
        tabla_markdown,
    )

    cfg = settings()
    try:
        corpus = cargar_corpus(cfg)
    except CorpusNoEncontrado as exc:
        print(f"No se puede medir: falta el corpus ({exc}).")
        print("Descomprime corpus_miax_2026.zip e indice_faiss.zip en data/corpus/.")
        raise typer.Exit(1) from exc

    if not ruta_golden.is_file():
        print(f"No se puede medir: no existe el golden set en {ruta_golden}.")
        print("Escribe golden/golden_set.jsonl antes de medir el recall.")
        raise typer.Exit(1)

    preguntas = leer_preguntas(ruta_golden)
    con_ancla = sum(1 for p in preguntas if p.ancla_texto)
    if con_ancla == 0:
        print(
            f"El golden set tiene {len(preguntas)} preguntas pero ninguna con "
            "ancla_texto: el recall@k se mide contra el ancla, así que no hay "
            "nada que medir todavía. Añade preguntas extractivas."
        )
        raise typer.Exit(1)

    # El proveedor solo hace falta para la fila de la reescritura; si no hay
    # clave, se mide el resto y esa fila queda pendiente, sin abortar.
    proveedor: ProveedorLLM | None = None
    if cfg.hay_clave():
        from agente_10k.agente.proveedores import construir_proveedor

        proveedor = cast("ProveedorLLM", construir_proveedor(cfg))

    filas = ejecutar_ablacion(corpus, preguntas, cfg, proveedor)
    rutas = escribir_ablacion(filas, cfg.dir_resultados / "retrieval")

    origen = getattr(proveedor, "origen_coste", None)
    print(f"Medidas {con_ancla} preguntas con ancla, de {len(preguntas)}.")
    if origen:
        print(f"Coste de la reescritura: {origen}.")
    print()
    print(tabla_markdown(filas))
    for ruta in rutas:
        print(f"escrito {ruta}")


@app.command()
def informe(
    pdf: bool = typer.Option(False, help="Montar además el informe en PDF"),
) -> None:
    """Regenera todas las tablas del informe desde resultados/."""
    from agente_10k.evaluacion.informe import generar_todo

    cfg = settings()
    destino = RAIZ_REPO / "docs" / "informe"
    escritos = generar_todo(cfg.dir_resultados, destino)
    if pdf:
        from agente_10k.evaluacion.documento import generar

        plantilla = destino / "plantilla.md"
        if not plantilla.is_file():
            print(f"No hay plantilla en {plantilla}.")
            raise typer.Exit(1)
        montados = generar(
            plantilla,
            RAIZ_REPO,
            destino,
            "Un agente investigador sobre informes 10-K",
        )
        escritos += montados
        if not any(r.suffix == ".pdf" for r in montados):
            print("Sin Edge ni Chrome: queda el HTML, imprímelo desde el navegador.")
    for ruta in escritos:
        print(f"escrito {ruta}")


@app.command()
def comparar(
    baseline_etiqueta: str = "baseline",
    final_etiqueta: str = "final",
) -> None:
    """La tabla baseline contra final, con el mejor valor remarcado."""
    from agente_10k.evaluacion.informe import cargar_informe, tabla_comparada

    dir_resultados = settings().dir_resultados
    rutas = [
        dir_resultados / etiqueta / "informe.json"
        for etiqueta in (baseline_etiqueta, final_etiqueta)
    ]
    faltan = [str(r) for r in rutas if not r.is_file()]
    if faltan:
        print(f"Falta ejecutar antes: {', '.join(faltan)}")
        raise typer.Exit(1)
    print(tabla_comparada([cargar_informe(r) for r in rutas]))


@app.command(name="reconstruir-secciones")
def reconstruir_secciones() -> None:
    """Deriva secciones.jsonl desde los fragmentos cuando el original no está.

    Lo que produce NO es literal en las fronteras de troceado. Ver ADR-004.
    """
    from agente_10k.corpus import cargar_corpus

    cfg = settings()
    corpus = cargar_corpus(cfg)
    destino = cfg.ruta_secciones_derivadas
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as f:
        for seccion in corpus.secciones.listar():
            f.write(json.dumps(seccion.model_dump(), ensure_ascii=False) + "\n")
    print(f"escritas {len(corpus.secciones)} secciones en {destino}")
    if corpus.secciones_reconstruidas:
        print(
            "AVISO: derivadas de los fragmentos. No son literales en las "
            "fronteras de troceado; no valen para verificar un ancla que las "
            "cruce."
        )


@app.command()
def tools(
    ticker: str = "NVDA",
    fiscal_year: int = 2024,
    concept: str = "Revenues",
) -> None:
    """Prueba las cuatro herramientas contra el corpus real, sin modelo."""
    from agente_10k.tools import contratos

    print("--- list_available ---")
    print(contratos.list_available())
    print(f"\n--- get_xbrl_fact({ticker}, {fiscal_year}, {concept}) ---")
    print(contratos.get_xbrl_fact(ticker, fiscal_year, concept))
    print(f"\n--- read_section({ticker}, {fiscal_year}, 7A) [200 tokens] ---")
    print(contratos.read_section(ticker, fiscal_year, "7A", max_tokens=200)[:800])


if __name__ == "__main__":
    app()
