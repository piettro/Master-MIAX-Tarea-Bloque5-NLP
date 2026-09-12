"""Los objetivos del Makefile, en Python, para que corran en las tres máquinas.

En Windows no hay `make`. La lógica vive aquí y el Makefile delega, de modo
que no hay dos versiones de cada objetivo que puedan separarse con el tiempo.

Uso:
    python scripts/tareas.py <objetivo> [args...]
    python scripts/tareas.py --lista
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PY = sys.executable


def _correr(*orden: str, permitir_fallo: bool = False) -> int:
    """Ejecuta una orden en la raíz del repositorio y propaga su código."""
    print(f"$ {' '.join(orden)}", flush=True)
    codigo = subprocess.call(orden, cwd=RAIZ)
    if codigo != 0 and not permitir_fallo:
        sys.exit(codigo)
    return codigo


def setup(_: Sequence[str]) -> None:
    """Instala el paquete en modo editable con sus dependencias de desarrollo."""
    _correr(PY, "-m", "pip", "install", "-e", ".[dev]")
    if shutil.which("pre-commit"):
        _correr("pre-commit", "install", permitir_fallo=True)
    else:
        print("pre-commit no está en el PATH: gancho de secretos no instalado.")


def tipos(_: Sequence[str]) -> None:
    """Mypy --strict sobre el paquete."""
    _correr(PY, "-m", "mypy", "--strict", "src/agente_10k")


def lint(_: Sequence[str]) -> None:
    """Ruff (lint y formato) más mypy --strict."""
    _correr(PY, "-m", "ruff", "check", "src", "tests", "scripts")
    _correr(PY, "-m", "ruff", "format", "--check", "src", "tests", "scripts")
    tipos(())


def format_(_: Sequence[str]) -> None:
    """Aplica el formateo de ruff y arregla lo que pueda arreglar."""
    _correr(PY, "-m", "ruff", "check", "--fix", "src", "tests", "scripts")
    _correr(PY, "-m", "ruff", "format", "src", "tests", "scripts")


def test(args: Sequence[str]) -> None:
    """La suite completa. No toca la red ni necesita clave de API."""
    _correr(PY, "-m", "pytest", *args)


def cobertura(_: Sequence[str]) -> None:
    """La suite con informe de cobertura de los módulos que la exigen."""
    _correr(
        PY,
        "-m",
        "pytest",
        "--cov=agente_10k.dominio",
        "--cov=agente_10k.corpus",
        "--cov=agente_10k.evaluacion",
        "--cov-report=term-missing",
        "--cov-fail-under=80",
    )


def baseline(args: Sequence[str]) -> None:
    """Ejecuta el baseline del profesor y lo congela. HITO 1, irreversible."""
    _correr(PY, "-m", "agente_10k.cli", "baseline", *args)


def final(args: Sequence[str]) -> None:
    """Ejecuta el sistema final sobre el golden set."""
    _correr(
        PY,
        "-m",
        "agente_10k.cli",
        "evaluar",
        "golden/golden_set.jsonl",
        "--etiqueta",
        "final",
        *args,
    )


def informe(_: Sequence[str]) -> None:
    """Regenera todas las tablas del informe desde resultados/."""
    _correr(PY, "-m", "agente_10k.cli", "informe")


def ablacion(_: Sequence[str]) -> None:
    """Regenera la tabla de ablación del retrieval desde cero."""
    _correr(PY, "-m", "agente_10k.cli", "ablacion")


def validar_golden(args: Sequence[str]) -> None:
    """Pasa el validador sobre el golden set."""
    ruta = args[0] if args else "golden/golden_set.jsonl"
    _correr(PY, "-m", "agente_10k.cli", "validar-golden", ruta)


def reconstruir_secciones(_: Sequence[str]) -> None:
    """Deriva secciones.jsonl desde los chunks cuando el original no está."""
    _correr(PY, "-m", "agente_10k.cli", "reconstruir-secciones")


def limpiar(_: Sequence[str]) -> None:
    """Borra cachés de herramientas y de embeddings."""
    for patron in (
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".cache",
        "htmlcov",
        "build",
        "dist",
    ):
        objetivo = RAIZ / patron
        if objetivo.exists():
            shutil.rmtree(objetivo, ignore_errors=True)
            print(f"borrado {patron}")
    for pycache in RAIZ.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)


OBJETIVOS = {
    "setup": setup,
    "lint": lint,
    "format": format_,
    "tipos": tipos,
    "test": test,
    "cobertura": cobertura,
    "baseline": baseline,
    "final": final,
    "informe": informe,
    "ablacion": ablacion,
    "validar-golden": validar_golden,
    "reconstruir-secciones": reconstruir_secciones,
    "limpiar": limpiar,
}


def main() -> None:
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("objetivo", nargs="?", help="objetivo a ejecutar")
    parser.add_argument("resto", nargs="*", help="argumentos del objetivo")
    parser.add_argument("--lista", action="store_true", help="lista objetivos")
    ns = parser.parse_args()

    if ns.lista or not ns.objetivo:
        for nombre, fn in OBJETIVOS.items():
            doc = (fn.__doc__ or "").splitlines()[0]
            print(f"  {nombre:24s} {doc}")
        return

    if ns.objetivo not in OBJETIVOS:
        parser.error(f"objetivo desconocido: {ns.objetivo}")
    OBJETIVOS[ns.objetivo](ns.resto)


if __name__ == "__main__":
    main()
