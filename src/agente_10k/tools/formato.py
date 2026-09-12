"""Cómo se renderiza a texto lo que devuelven las tools.

Todo lo que sale de una herramienta lo lee el modelo, así que el formato es
interfaz, no presentación. Tres reglas que se aplican en todo el módulo:

1. **El `chunk_id` va siempre y sin reformatear.** Es lo que permite verificar
   una cita; si se omite o se embellece, el evaluador de cita no puede cerrar
   el círculo.
2. **Un hueco se responde con texto, nunca con una excepción ni con vacío.** Un
   resultado vacío le dice al modelo «no encontré» y el modelo reintenta; un
   texto que explica qué pasa y qué sí existe le permite corregirse.
3. **Compacto.** Lo que aquí se escriba de más se paga en cada pregunta, y el
   coste medio por pregunta es una columna de la tabla del informe.
"""

from __future__ import annotations

from collections.abc import Sequence

from agente_10k.dominio.modelos import Fragmento, HechoXbrl, Seccion

CARACTERES_POR_TOKEN = 4
"""Regla de tres para truncar sin cargar un tokenizador.

Es una aproximación deliberada: cargar el tokenizador del modelo dentro de una
tool añadiría medio segundo y una dependencia a cada llamada, para afinar un
truncado que solo tiene que ser aproximadamente correcto.
"""


def fragmentos(encontrados: Sequence[Fragmento]) -> str:
    """Los fragmentos recuperados, cada uno con su `chunk_id` delante."""
    if not encontrados:
        return (
            "Sin resultados para esa consulta con esos filtros. Prueba a "
            "quitar algún filtro, a reformular la búsqueda o a comprobar con "
            "list_available que el emisor y el ejercicio están en el corpus."
        )
    partes = []
    for f in encontrados:
        marca = " · contiene tabla" if f.contiene_tabla else ""
        puntuacion = "" if f.puntuacion is None else f" (similitud {f.puntuacion:.3f})"
        partes.append(
            f"[{f.chunk_id}] {f.ticker} FY{f.fiscal_year} Item {f.item}"
            f"{puntuacion}{marca}\n{f.texto}"
        )
    return "\n\n---\n\n".join(partes)


def sin_recuperador(motivo: str | None = None) -> str:
    """La búsqueda de texto no está montada, y por qué.

    El modelo necesita saber que esto NO significa que el dato no exista: si lo
    tomara por una ausencia, respondería «no está en el corpus» a preguntas que
    sí tienen respuesta.
    """
    causa = f" Motivo: {motivo}." if motivo else ""
    return (
        "La búsqueda de texto no está disponible en esta instalación."
        f"{causa} Esto NO significa que el dato no exista: significa que esta "
        "herramienta no puede buscarlo. Usa get_xbrl_fact para cifras o "
        "read_section si sabes qué sección leer."
    )


def hecho_xbrl(hecho: HechoXbrl) -> str:
    """Un hecho encontrado, con todo lo que el agente necesita para el esquema.

    Lleva valor, unidad, concepto EXACTO y ejercicio para que el modelo pueda
    rellenar `RespuestaFinanciera` sin inferir nada. Que tenga que deducir la
    unidad del contexto es una fuente de error evitable.
    """
    cola = []
    if hecho.period_end:
        cola.append(f"cierre de ejercicio {hecho.period_end}")
    if hecho.form:
        cola.append(f"según el {hecho.form}")
    sufijo = f" ({', '.join(cola)})" if cola else ""
    return (
        f"{hecho.ticker} FY{hecho.fiscal_year} · {hecho.concept} = "
        f"{hecho.value:,.0f} {hecho.unit}{sufijo}"
    )


def hueco_real(
    ticker: str, fiscal_year: int, concept: str, disponibles: Sequence[str]
) -> str:
    """Un hueco REAL en us-gaap. El texto tiene que inducir `fuente='ninguna'`.

    Es distinto de un concepto mal escrito y el mensaje lo dice explícitamente:
    aquí no hay nada que corregir ni que reintentar, y estimar la cifra a
    partir de otras magnitudes sería inventarla.
    """
    lista = ", ".join(disponibles) if disponibles else "(ninguno)"
    return (
        f"{ticker} NO reporta '{concept}' en us-gaap. No es un error de "
        f"escritura ni una laguna del corpus: esa compañía no etiqueta esa "
        f"magnitud, así que el dato NO EXISTE y no debe estimarse a partir de "
        f"otras cifras. Responde que no está en el corpus, con "
        f'fuente="ninguna" y cifra=null.\n'
        f"Conceptos que {ticker} sí reporta en FY{fiscal_year}: {lista}"
    )


def concepto_ausente(
    ticker: str,
    fiscal_year: int,
    concept: str,
    disponibles: Sequence[str],
    sugerencias: Sequence[str],
) -> str:
    """Un concepto que no está, pero que podría estar mal escrito.

    Lista los conceptos que SÍ existen y sugiere el sinónimo sin aplicarlo: la
    decisión de reintentar con otro nombre es del agente. Esta es la mejora de
    mayor ratio valor/esfuerzo de la práctica, porque convierte un callejón sin
    salida en una autocorrección en el turno siguiente.
    """
    lineas = [
        f"{ticker} no reportó '{concept}' en FY{fiscal_year}.",
    ]
    if sugerencias:
        lineas.append(
            f"Puede que la magnitud que buscas esté etiquetada como "
            f"{' o '.join(sugerencias)} en este emisor: el concepto del "
            f"ingreso no es el mismo en todas las compañías. Vuelve a llamar "
            f"a get_xbrl_fact con ese nombre si es lo que querías."
        )
    lineas.append(
        f"Conceptos disponibles para {ticker} FY{fiscal_year}: "
        f"{', '.join(disponibles) if disponibles else '(ninguno)'}"
    )
    return "\n".join(lineas)


def sin_emisor(ticker: str, fiscal_year: int) -> str:
    """No hay datos de ese emisor y ejercicio."""
    return (
        f"No hay datos de {ticker} para FY{fiscal_year} en el corpus. Usa "
        f"list_available para ver qué compañías y ejercicios existen antes de "
        f"insistir."
    )


def xbrl_no_cargado() -> str:
    """El parquet de hechos XBRL no está montado.

    Es un problema de instalación, no un hueco del corpus, y el mensaje lo
    separa: si el agente lo tomara por un hueco respondería «no está en el
    corpus» a preguntas que sí tienen respuesta.
    """
    return (
        "La tabla de hechos XBRL no está disponible en esta instalación "
        "(falta xbrl_facts.parquet en el corpus). Esto NO significa que el "
        "dato no exista: significa que esta herramienta no puede consultarlo. "
        "No estimes la cifra desde el texto; dilo en la respuesta."
    )


def seccion(contenido: Seccion, max_tokens: int | None = None) -> str:
    """El texto de una sección, truncado si se pide un tope.

    El truncado deja constancia de que truncó y de cuánto queda. Un texto
    cortado en seco hace que el modelo crea que la sección termina ahí.
    """
    texto = contenido.texto
    cabecera = (
        f"{contenido.ticker} FY{contenido.fiscal_year} Item {contenido.item}"
        f" · {contenido.n_tokens:,} tokens"
    )
    if contenido.item_origen and contenido.item_origen != contenido.item:
        cabecera += (
            f" · contenido tomado del Item {contenido.item_origen}, donde esta "
            f"compañía lo presenta"
        )
    if contenido.reconstruida:
        cabecera += " · sección reconstruida desde los fragmentos"

    if max_tokens is not None and contenido.n_tokens > max_tokens:
        corte = max_tokens * CARACTERES_POR_TOKEN
        restantes = contenido.n_tokens - max_tokens
        texto = (
            texto[:corte]
            + f"\n\n[…] TRUNCADO: quedan unos {restantes:,} tokens de esta "
            f"sección. Si necesitas la parte que falta, usa search_filings "
            f"con un filtro por item en lugar de leerla entera."
        )
    return f"{cabecera}\n\n{texto}"


def seccion_ausente(ticker: str, fiscal_year: int, item: str) -> str:
    """La sección pedida no está en el corpus."""
    return (
        f"No hay Item {item} de {ticker} FY{fiscal_year} en el corpus. Usa "
        f"list_available para ver qué hay."
    )


def universo(
    lineas: Sequence[tuple[str, str | None, Sequence[int], Sequence[str]]],
) -> str:
    """El universo del corpus, una línea por emisor.

    Menos de 400 tokens de salida: esta herramienta se llama al principio de
    muchas invocaciones y lo que aquí se gaste se paga en todas ellas.
    """
    if not lineas:
        return "El corpus está vacío."
    cuerpo = [
        "Corpus de informes 10-K de la SEC. Una línea por compañía:",
        "",
    ]
    for ticker, empresa, ejercicios, items in lineas:
        nombre = f" ({empresa})" if empresa else ""
        cuerpo.append(
            f"{ticker}{nombre} · ejercicios {', '.join(str(e) for e in ejercicios)}"
            f" · items {', '.join(items)}"
        )
    cuerpo += [
        "",
        "Items: 1A factores de riesgo · 7 discusión de la dirección · "
        "7A riesgo de mercado · 8 estados financieros.",
        "El ejercicio fiscal NO es el año de presentación: los emisores "
        "cierran en meses distintos. Fíate del ejercicio que se pide, nunca "
        "de una fecha.",
        "Cualquier compañía o ejercicio que no esté en esta lista NO está en "
        "el corpus: dilo en vez de buscarlo.",
    ]
    return "\n".join(cuerpo)
