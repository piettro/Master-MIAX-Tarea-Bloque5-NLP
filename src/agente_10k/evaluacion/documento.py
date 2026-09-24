"""El informe en PDF, montado desde `resultados/`.

La plantilla es prosa con marcas `{{incluir: ruta}}`; cada marca se sustituye
por el fichero que generó el código. Es la misma regla de siempre: ninguna
cifra se escribe a mano, y si una tabla falta, el PDF sale igual con un aviso
en su sitio en vez de no salir.

El PDF lo imprime un navegador en modo headless (Edge o Chrome). No es elegante,
pero no añade una dependencia de 40 MB para una vez al mes, y en Windows siempre
hay uno de los dos.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

MARCA = re.compile(r"\{\{\s*incluir:\s*(?P<ruta>[^}]+?)\s*\}\}")

NAVEGADORES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
)

ESTILO = """
@page { size: A4; margin: 18mm 16mm; }
body { font: 10.5pt/1.5 "Segoe UI", system-ui, sans-serif; color: #17202a; }
h1 { font-size: 20pt; margin: 0 0 4pt; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; border-bottom: 1px solid #d5dbdb;
     padding-bottom: 3pt; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 8.8pt; }
th, td { border: 1px solid #d5dbdb; padding: 3pt 5pt; text-align: left; }
th { background: #f4f6f7; }
code { font-family: Consolas, monospace; font-size: 9pt; background: #f4f6f7;
       padding: 0 2pt; }
pre { background: #f4f6f7; padding: 6pt; overflow-wrap: normal; font-size: 8.5pt; }
blockquote { margin: 8pt 0; padding: 4pt 10pt; border-left: 3px solid #aeb6bf;
             color: #566573; }
.aviso { color: #a93226; font-style: italic; }
"""


def componer(plantilla: Path, raiz: Path) -> str:
    """La plantilla con cada marca sustituida por el fichero que nombra."""

    def sustituir(coincidencia: re.Match[str]) -> str:
        ruta = raiz / coincidencia.group("ruta").strip()
        if not ruta.is_file():
            return (
                f'<p class="aviso">PENDIENTE: falta {ruta.relative_to(raiz)}. '
                "Se genera ejecutando el repositorio.</p>"
            )
        return ruta.read_text(encoding="utf-8").strip()

    return MARCA.sub(sustituir, plantilla.read_text(encoding="utf-8"))


def a_html(markdown: str, titulo: str) -> str:
    """El markdown compuesto, como HTML con el estilo del informe."""
    from markdown_it import MarkdownIt

    cuerpo = MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown)
    return (
        "<!doctype html>\n<html lang='es'>\n<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{titulo}</title>\n<style>{ESTILO}</style>\n"
        f"</head>\n<body>\n{cuerpo}\n</body>\n</html>\n"
    )


def _navegador() -> str | None:
    """El primer navegador que sepa imprimir a PDF, o `None`."""
    for ruta in NAVEGADORES:
        if Path(ruta).is_file():
            return ruta
    return shutil.which("msedge") or shutil.which("chrome")


def a_pdf(html: Path, pdf: Path) -> Path | None:
    """Imprime el HTML a PDF con el navegador. `None` si no hay ninguno."""
    navegador = _navegador()
    if navegador is None:
        return None
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run(
            [
                navegador,
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--user-data-dir={perfil}",
                f"--print-to-pdf={pdf}",
                html.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    return pdf if pdf.is_file() else None


def generar(plantilla: Path, raiz: Path, destino: Path, titulo: str) -> list[Path]:
    """Compone el informe y lo deja en markdown, HTML y, si se puede, PDF."""
    destino.mkdir(parents=True, exist_ok=True)
    texto = componer(plantilla, raiz)
    ruta_md = destino / "informe.md"
    ruta_html = destino / "informe.html"
    ruta_md.write_text(texto, encoding="utf-8", newline="\n")
    ruta_html.write_text(a_html(texto, titulo), encoding="utf-8", newline="\n")
    escritos = [ruta_md, ruta_html]
    pdf = a_pdf(ruta_html, destino / "informe.pdf")
    if pdf is not None:
        escritos.append(pdf)
    return escritos
