"""Valida el golden set. CONTRATO C4.

Un golden set que no pasa esto no se corrige: se devuelve. La salida es un
informe legible —«faltan 2 comparativas», «g-a-004: el ancla no aparece en el
corpus»— y no un booleano, porque quien lo ejecuta lo que necesita es saber qué
arreglar.

Es una superconjunto del validador del profesor (celda 32 del notebook de la
sesión 1) y conserva sus tres familias: `extractiva`, `numerica`, `comparativa`.
Las preguntas de hueco real NO son una cuarta familia —el validador oficial las
rechazaría— sino numéricas o comparativas con `cifra_esperada` nula.

La regla que más preguntas invalida, y la que más tiempo ahorra encontrar aquí y
no el día 23: **el `ancla_texto` tiene que aparecer LITERALMENTE en el corpus.**
Si no aparece, está mal transcrita y la pregunta no es «casi válida»: es
inválida, porque el evaluador de cita nunca podrá darla por buena.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "src") not in sys.path:  # permite ejecutarlo sin instalar
    sys.path.insert(0, str(RAIZ / "src"))

from agente_10k.corpus import Corpus  # noqa: E402
from agente_10k.dominio.modelos import Pregunta  # noqa: E402

CAMPOS_OBLIGATORIOS = frozenset(
    {
        "id",
        "pregunta",
        "familia",
        "ticker",
        "fiscal_year",
        "respuesta_esperada",
        "cifra_esperada",
        "unidad",
        "concept_xbrl",
        "item_esperado",
        "ancla_texto",
        "ancla_inicio",
        "ancla_fin",
        "chunk_id_esperado",
        "herramienta_esperada",
        "autor",
    }
)

FAMILIAS = frozenset({"extractiva", "numerica", "comparativa"})
HERRAMIENTAS = frozenset(
    {"list_available", "get_xbrl_fact", "search_filings", "read_section"}
)
ITEMS = frozenset({"1A", "7", "7A", "8"})

MINIMO_PREGUNTAS = 20
MINIMO_COMPARATIVAS = 6
MINIMO_HUECOS = 2
MAXIMO_PALABRAS_ANCLA = 40
MINIMO_UNIDADES_BASE = 1e6
"""Por debajo de un millon, una cifra en USD huele a estar en millones."""
HOLGURA_OFFSETS = 5
"""Caracteres de margen entre ancla_fin - ancla_inicio y len(ancla_texto)."""


def _corpus() -> Corpus | None:
    """El corpus, o `None` si no está montado.

    El validador tiene que poder correr sin corpus: comprueba entonces todo lo
    estructural y avisa de que no pudo verificar anclas ni cifras. Un validador
    que no arranca sin los datos no se ejecuta en CI, y uno que no se ejecuta en
    CI no sirve de nada.
    """
    try:
        from agente_10k.corpus import cargar_corpus

        return cargar_corpus()
    except Exception:
        return None


def validar(
    preguntas: Sequence[dict[str, object]],
    exigir_completo: bool = True,
) -> list[str]:
    """Los problemas del golden set, uno por línea. Lista vacía es correcto.

    Args:
        preguntas: Las preguntas ya leídas del JSONL.
        exigir_completo: Si se comprueban los mínimos de composición (20
            preguntas, 6 comparativas, 2 huecos). Se desactiva mientras el set
            está a medias.

    Returns:
        Los problemas encontrados, en orden de gravedad decreciente.
    """
    problemas: list[str] = []
    corpus = _corpus()
    vistos: set[str] = set()

    for cruda in preguntas:
        pid = str(cruda.get("id", "(sin id)"))

        faltan = CAMPOS_OBLIGATORIOS - set(cruda)
        if faltan:
            problemas.append(f"{pid}: faltan campos {sorted(faltan)}")
            continue

        try:
            p = Pregunta.model_validate(cruda)
        except Exception as exc:
            problemas.append(f"{pid}: no cumple el esquema C4: {exc}")
            continue

        if p.id in vistos:
            problemas.append(f"{pid}: id repetido")
        vistos.add(p.id)

        problemas += _validar_estructura(p, corpus)
        problemas += _validar_familia(p, corpus)

    if exigir_completo:
        problemas += _validar_composicion(preguntas)
    if corpus is None:
        problemas.append(
            "AVISO: el corpus no está montado. No se han podido verificar ni "
            "las anclas contra el texto ni las cifras contra XBRL. Ejecuta "
            "`agente-10k diagnostico` para ver qué falta."
        )
    return problemas


def _validar_estructura(p: Pregunta, corpus: object) -> list[str]:
    """Comprobaciones que no dependen de la familia."""
    problemas: list[str] = []

    if p.familia not in FAMILIAS:
        problemas.append(
            f"{p.id}: familia '{p.familia}' no válida. Las del validador "
            f"oficial son {sorted(FAMILIAS)}; el hueco real es una numérica "
            f"o comparativa con cifra_esperada null."
        )
    if not p.herramienta_esperada:
        problemas.append(f"{p.id}: sin herramienta_esperada")
    desconocidas = set(p.herramienta_esperada) - HERRAMIENTAS
    if desconocidas:
        problemas.append(
            f"{p.id}: herramienta_esperada {sorted(desconocidas)} no existe. "
            f"Son {sorted(HERRAMIENTAS)} (CONTRATO C1)."
        )
    if p.item_esperado is not None and p.item_esperado not in ITEMS:
        problemas.append(
            f"{p.id}: item_esperado '{p.item_esperado}' no válido; son {sorted(ITEMS)}."
        )
    if not p.autor:
        problemas.append(f"{p.id}: sin autor. Hace falta para auditar de dónde vino.")
    if p.chunk_id_esperado is not None:
        problemas.append(
            f"{p.id}: chunk_id_esperado debe quedar a null. La verdad se ancla "
            f"a una frase literal, no a un identificador que cambia en cuanto "
            f"se re-trocea el corpus."
        )

    if corpus is None:
        return problemas

    if p.ticker is not None and p.ticker not in corpus.secciones.tickers():  # type: ignore[attr-defined]
        problemas.append(
            f"{p.id}: {p.ticker} no está en el corpus. Emisores: "
            f"{', '.join(corpus.secciones.tickers())}."  # type: ignore[attr-defined]
        )
    if p.fiscal_year is not None and p.fiscal_year not in corpus.secciones.ejercicios():  # type: ignore[attr-defined]
        problemas.append(f"{p.id}: FY{p.fiscal_year} no está en el corpus.")
    return problemas


def _validar_familia(p: Pregunta, corpus: object) -> list[str]:
    """Comprobaciones específicas de cada familia."""
    problemas: list[str] = []

    if p.familia in {"numerica", "comparativa"}:
        problemas += _validar_numerica(p, corpus)
    if p.familia in {"extractiva", "comparativa"}:
        problemas += _validar_ancla(p, corpus)
    return problemas


def _validar_numerica(p: Pregunta, corpus: object) -> list[str]:
    """Cifra y concepto de una pregunta numérica o comparativa."""
    problemas: list[str] = []

    if p.cifra_esperada is None and p.concept_xbrl is None:
        problemas.append(
            f"{p.id}: numérica sin cifra_esperada ni concept_xbrl. Si es una "
            f"pregunta de hueco real, declara el concept_xbrl que NO se "
            f"reporta y deja cifra_esperada a null."
        )
    if p.cifra_esperada is not None and not p.unidad:
        problemas.append(f"{p.id}: cifra_esperada sin unidad")
    # Solo para magnitudes en USD: un BPA de 2,94 USD/accion o un porcentaje
    # son legitimos por debajo del millon.
    fuera_de_escala = (
        p.cifra_esperada is not None
        and (p.unidad or "").upper() == "USD"
        and 0 < abs(p.cifra_esperada) < MINIMO_UNIDADES_BASE
    )
    if fuera_de_escala:
        problemas.append(
            f"{p.id}: cifra_esperada = {p.cifra_esperada:,.0f}. ¿Está en "
            f"unidades base? Las magnitudes del corpus van en USD, no en "
            f"millones."
        )
    if "get_xbrl_fact" not in p.herramienta_esperada:
        problemas.append(
            f"{p.id}: una pregunta numérica debe pasar por get_xbrl_fact. "
            f"Acertar leyendo la cifra del texto es fallo."
        )

    if corpus is None or p.ticker is None or p.fiscal_year is None:
        return problemas

    xbrl = corpus.xbrl  # type: ignore[attr-defined]
    if not xbrl.disponible():
        problemas.append(
            f"{p.id}: AVISO, no se pudo verificar la cifra: falta xbrl_facts.parquet."
        )
        return problemas

    if p.concept_xbrl:
        hecho = xbrl.obtener(p.ticker, p.fiscal_year, p.concept_xbrl)
        if hecho is None and p.cifra_esperada is not None:
            problemas.append(
                f"{p.id}: {p.ticker} no reporta '{p.concept_xbrl}' en "
                f"FY{p.fiscal_year}, pero la pregunta espera una cifra. El "
                f"concepto se mira en xbrl_facts.parquet, nunca por analogía "
                f"con otra compañía."
            )
        elif hecho is not None and p.cifra_esperada is None:
            problemas.append(
                f"{p.id}: se declara como hueco, pero {p.ticker} SÍ reporta "
                f"'{p.concept_xbrl}' en FY{p.fiscal_year} "
                f"({hecho.value:,.0f} {hecho.unit})."
            )
        elif hecho is not None and p.cifra_esperada is not None:
            from agente_10k.dominio.tolerancia import TOLERANCIA

            if not TOLERANCIA.coincide(p.cifra_esperada, hecho.value):
                problemas.append(
                    f"{p.id}: cifra_esperada {p.cifra_esperada:,.0f} no "
                    f"coincide con XBRL {hecho.value:,.0f} "
                    f"({TOLERANCIA.describir()}). Verifica contra "
                    f"xbrl_facts.parquet, nunca contra el texto."
                )
    return problemas


def _validar_ancla(p: Pregunta, corpus: object) -> list[str]:
    """El ancla de una pregunta extractiva o comparativa."""
    problemas: list[str] = []

    if not p.ancla_texto:
        problemas.append(
            f"{p.id}: {p.familia} sin ancla_texto. La verdad se ancla a una "
            f"frase literal del informe."
        )
        return problemas

    palabras = len(p.ancla_texto.split())
    if palabras > MAXIMO_PALABRAS_ANCLA:
        problemas.append(
            f"{p.id}: ancla de {palabras} palabras. Una frase. Así no mides tu "
            f"retrieval, mides tu tamaño de ventana."
        )

    if corpus is None:
        return problemas

    encontrados = corpus.fragmentos.buscar_literal(p.ancla_texto)  # type: ignore[attr-defined]
    if not encontrados:
        problemas.append(
            f"{p.id}: el ancla NO aparece literalmente en el corpus. Está mal "
            f"transcrita y la pregunta es inválida: cópiala del texto, no la "
            f"escribas de memoria. Ancla: {p.ancla_texto[:70]!r}"
        )
        return problemas

    if p.ticker and not any(f.ticker == p.ticker for f in encontrados):
        problemas.append(
            f"{p.id}: el ancla existe, pero no en ningún documento de "
            f"{p.ticker}. Aparece en: "
            f"{sorted({f.ticker for f in encontrados})}."
        )
    if p.item_esperado and not any(f.item == p.item_esperado for f in encontrados):
        problemas.append(
            f"{p.id}: el ancla no está en el Item {p.item_esperado}; aparece "
            f"en {sorted({f.item for f in encontrados})}."
        )
    if p.ancla_inicio is not None and p.ancla_fin is not None:
        largo = p.ancla_fin - p.ancla_inicio
        if largo <= 0:
            problemas.append(f"{p.id}: ancla_fin no es posterior a ancla_inicio")
        elif abs(largo - len(p.ancla_texto)) > HOLGURA_OFFSETS:
            problemas.append(
                f"{p.id}: ancla_inicio/ancla_fin abarcan {largo} caracteres "
                f"pero ancla_texto tiene {len(p.ancla_texto)}."
            )
    return problemas


def _validar_composicion(preguntas: Sequence[dict[str, object]]) -> list[str]:
    """Los mínimos de composición del enunciado."""
    problemas: list[str] = []
    n = len(preguntas)
    if n < MINIMO_PREGUNTAS:
        problemas.append(
            f"hacen falta {MINIMO_PREGUNTAS} preguntas, hay {n} "
            f"(faltan {MINIMO_PREGUNTAS - n})"
        )

    comparativas = sum(p.get("familia") == "comparativa" for p in preguntas)
    if comparativas < MINIMO_COMPARATIVAS:
        problemas.append(
            f"hacen falta {MINIMO_COMPARATIVAS} comparativas, hay "
            f"{comparativas} (faltan {MINIMO_COMPARATIVAS - comparativas})"
        )

    huecos = sum(
        p.get("familia") in {"numerica", "comparativa"}
        and p.get("cifra_esperada") is None
        and p.get("concept_xbrl") is not None
        for p in preguntas
    )
    if huecos < MINIMO_HUECOS:
        problemas.append(
            f"hacen falta {MINIMO_HUECOS} preguntas de hueco real (Amazon sin "
            f"GrossProfit / Liabilities / R&D; Meta o Alphabet sin "
            f"GrossProfit), hay {huecos}"
        )

    familias = {p.get("familia") for p in preguntas}
    for familia in sorted(FAMILIAS - familias):
        problemas.append(f"no hay ninguna pregunta de la familia '{familia}'")
    return problemas


def leer(ruta: str | Path) -> list[dict[str, object]]:
    """Lee un JSONL de preguntas.

    Raises:
        FileNotFoundError: Si el fichero no existe.
        ValueError: Si alguna línea no es JSON válido, diciendo cuál.
    """
    camino = Path(ruta)
    if not camino.is_file():
        raise FileNotFoundError(f"No existe {camino}")
    preguntas: list[dict[str, object]] = []
    for numero, linea in enumerate(camino.read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        try:
            preguntas.append(json.loads(linea))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{camino}:{numero} no es JSON válido: {exc}") from exc
    return preguntas


def validar_fichero(ruta: str | Path, exigir_completo: bool = True) -> list[str]:
    """Lee y valida un fichero de golden set."""
    return validar(leer(ruta), exigir_completo=exigir_completo)


def fusionar_parciales(dir_parciales: Path, destino: Path) -> int:
    """Fusiona los `*.jsonl` de un directorio en un único golden set.

    Cada tanda de preguntas va en su fichero y esta función los junta. Es lo que
    evita los conflictos de merge en un JSONL, que es un fichero donde git no
    sabe resolver nada.

    Returns:
        Cuántas preguntas se escribieron.

    Raises:
        ValueError: Si hay ids repetidos entre ficheros, diciendo cuáles.
    """
    todas: list[dict[str, object]] = []
    procedencia: dict[str, str] = {}
    for fichero in sorted(dir_parciales.glob("*.jsonl")):
        for p in leer(fichero):
            pid = str(p.get("id", ""))
            if pid in procedencia:
                raise ValueError(
                    f"id '{pid}' repetido en {fichero.name} y "
                    f"{procedencia[pid]}. Cada tanda tiene que usar sus propios ids."
                )
            procedencia[pid] = fichero.name
            todas.append(p)

    todas.sort(key=lambda p: str(p.get("id", "")))
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as f:
        for p in todas:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return len(todas)


def informe_legible(ruta: str | Path, problemas: Sequence[str]) -> str:
    """El resultado de la validación, en un texto para leer."""
    if not problemas:
        return f"{ruta}: el golden set es válido."
    cabecera = f"{ruta}: {len(problemas)} problema(s)."
    cuerpo = "\n".join(f"  - {p}" for p in problemas)
    return f"{cabecera}\n{cuerpo}"


def main() -> int:
    """Valida el fichero que se le pase por línea de órdenes."""
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "golden/golden_set.jsonl"
    if not ruta.is_file():
        print(
            f"{ruta} no existe. Escribe las preguntas en un JSONL con el "
            f"esquema de golden_set_ejemplo.jsonl."
        )
        return 1
    problemas = validar_fichero(ruta)
    print(informe_legible(ruta, problemas))
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
