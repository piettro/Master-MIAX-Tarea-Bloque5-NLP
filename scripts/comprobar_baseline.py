"""Gancho que protege `resultados/baseline/`. HITO 1, irreversible.

El baseline es media tabla del informe. Si se sobrescribe después de haberlo
congelado no hay forma de recuperarlo: habría que volver al commit de aquel día
y reejecutar con el mismo modelo, que para entonces ya habrá cambiado.

Se ejecuta desde pre-commit y desde `tests/test_baseline_congelado.py`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_BASELINE = RAIZ / "resultados" / "baseline"
RUTA_SELLO = DIR_BASELINE / "SELLO.json"
IGNORADOS = {"SELLO.json", "README.md", ".gitkeep"}


def huellas() -> dict[str, str]:
    """SHA-256 de cada fichero de resultados/baseline/, salvo el propio sello."""
    salida: dict[str, str] = {}
    if not DIR_BASELINE.is_dir():
        return salida
    for ruta in sorted(DIR_BASELINE.rglob("*")):
        if not ruta.is_file() or ruta.name in IGNORADOS:
            continue
        clave = ruta.relative_to(DIR_BASELINE).as_posix()
        salida[clave] = hashlib.sha256(ruta.read_bytes()).hexdigest()
    return salida


def sellar() -> dict[str, object]:
    """Escribe SELLO.json con las huellas actuales y el commit que las generó."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ, text=True
        ).strip()
    except (subprocess.SubprocessError, OSError):
        commit = "(sin commit)"
    sello: dict[str, object] = {"commit": commit, "huellas": huellas()}
    DIR_BASELINE.mkdir(parents=True, exist_ok=True)
    RUTA_SELLO.write_text(
        json.dumps(sello, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return sello


def verificar() -> list[str]:
    """Los ficheros del baseline que ya no coinciden con su sello."""
    if not RUTA_SELLO.is_file():
        return []  # todavía no se ha congelado nada
    sello = json.loads(RUTA_SELLO.read_text(encoding="utf-8"))
    esperadas: dict[str, str] = sello["huellas"]
    actuales = huellas()
    problemas = [
        f"{nombre}: BORRADO desde que se congeló el baseline"
        for nombre in esperadas
        if nombre not in actuales
    ]
    problemas += [
        f"{nombre}: MODIFICADO desde que se congeló el baseline"
        for nombre, h in esperadas.items()
        if nombre in actuales and actuales[nombre] != h
    ]
    return problemas


def main() -> int:
    """Falla si el baseline congelado cambió."""
    problemas = verificar()
    if not problemas:
        return 0
    print("resultados/baseline/ está CONGELADO (HITO 1) y ha cambiado:")
    for p in problemas:
        print(f"  - {p}")
    print(
        "\nEs media tabla del informe. Si de verdad hay que volver a generarlo, "
        "borra SELLO.json a mano y deja constancia en docs/decisiones.md de "
        "por qué."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
