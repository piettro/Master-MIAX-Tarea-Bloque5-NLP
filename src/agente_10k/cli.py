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

import typer

from agente_10k.config import settings

RUTA_GOLDEN_POR_DEFECTO = typer.Argument(Path("golden/golden_set.jsonl"))

app = typer.Typer(
    add_completion=False,
    help="Agente investigador sobre informes 10-K de la SEC.",
    no_args_is_help=True,
)


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
    etiqueta: str = typer.Option("final", help="Subcarpeta de resultados/"),
) -> None:
    """Ejecuta el sistema sobre un JSONL de preguntas y escribe los resultados."""
    from agente_10k.evaluacion.ejecutor import evaluar as _evaluar

    informe = _evaluar(ruta_jsonl, etiqueta=etiqueta)
    print(informe)


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
    """Ejecuta el baseline del profesor y lo CONGELA. HITO 1, irreversible."""
    print(
        "El baseline se ejecuta con la implementación del profesor, que está "
        "en src/agente_10k/baseline/ sin modificar.\n"
        "Pendiente de la fase 1: ver resultados/README.md para el protocolo "
        "de congelación."
    )
    raise typer.Exit(1)


@app.command()
def ablacion() -> None:
    """Regenera la tabla de ablación del retrieval. FASE 3."""
    print("Pendiente de la fase 3 (Alonso): retrieval/ y su runner de medición.")
    raise typer.Exit(1)


@app.command()
def informe() -> None:
    """Regenera todas las tablas del informe desde resultados/. FASE 5."""
    from agente_10k.evaluacion.informe import generar_todo

    cfg = settings()
    escritos = generar_todo(cfg.dir_resultados, Path("docs/informe"))
    for ruta in escritos:
        print(f"escrito {ruta}")


@app.command()
def comparar(
    baseline_etiqueta: str = "baseline",
    final_etiqueta: str = "final",
) -> None:
    """La tabla baseline contra final. FASE 5."""
    print(
        f"Pendiente de la fase 5 (Raúl): comparar '{baseline_etiqueta}' con "
        f"'{final_etiqueta}'."
    )
    raise typer.Exit(1)


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
