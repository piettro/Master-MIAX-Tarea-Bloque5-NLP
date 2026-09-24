"""El runner de la tabla de ablación del retrieval.

Aquí es donde «mejora del retrieval» se convierte en «mejora MEDIDA del
retrieval», que es lo que pide el enunciado. La regla que gobierna el módulo:
cada fila de la tabla se saca ejecutando EL MISMO runner con una configuración
distinta. Si para sacar una fila hubiera que duplicar código, el diseño estaría
mal —y la comparación entre filas dejaría de ser justa, porque no estaríamos
midiendo lo mismo con distinta configuración, sino dos programas distintos—.

La métrica es `recall@k` contra el ANCLA DE TEXTO del golden set, no contra el
`chunk_id`: un fragmento cuenta como acierto si CONTIENE el ancla literal. Se
mide así a propósito (ver `metricas.recall_at_k` y ADR-004): el `chunk_id`
cambia en cuanto se re-trocea el corpus, y medir por él penalizaría justo al
grupo que mejore el troceado.

Dos decisiones de medición que conviene tener delante al leer la tabla:

* **La fila base NO recibe los filtros de metadatos.** El recuperador denso que
  entregamos filtra durante su barrido, así que si le pasáramos los filtros
  siempre, la fila «+ filtro metadatos» saldría idéntica a la base y la mejora
  parecería nula. Para que «filtrar antes» sea una mejora medible y no algo que
  el sistema ya hacía, la fila base busca sin metadatos —como haría un agente
  que no sabe de qué emisor es la pregunta— y solo las filas con
  `filtro_metadatos=True` los aplican. Es exactamente el punto de ADR-009.
* **El coste de la reescritura se lee de su contador, no se estima.** Las filas
  sin reescritura no llaman al modelo y su coste es 0: el retrieval es local. La
  fila de la reescritura añade una llamada por pregunta, y ese coste aparece en
  la columna para que se vea qué compró la mejora.
"""

from __future__ import annotations

import csv
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from agente_10k.config import Settings
from agente_10k.corpus import Corpus
from agente_10k.dominio.modelos import Filtros, Fragmento, Pregunta, UsoTokens
from agente_10k.dominio.protocolos import ProveedorLLM, Recuperador
from agente_10k.evaluacion.estadistica import mcnemar
from agente_10k.evaluacion.metricas import mrr, posicion_del_ancla, recall_at_k
from agente_10k.retrieval.fabrica import (
    CONFIGURACIONES_ABLACION,
    SIN_MEJORAS,
    construir_recuperador,
)

MINIMO_PARA_COMPARAR = 2  # con una sola configuración no hay contraste

KS_POR_DEFECTO: tuple[int, ...] = (1, 3, 5, 10)
"""Los `k` que reporta la tabla. `recall@1` dice si el mejor fragmento ya vale;
`recall@10` dice si al menos está entre los que el agente llegaría a leer."""


@dataclass
class FilaAblacion:
    """Una fila de la tabla: una configuración y lo que rindió.

    Es un objeto de datos y no una tupla suelta porque son nueve columnas y
    mezclarlas de memoria es fácil; con nombres, la que escribe el CSV y la que
    escribe el markdown leen lo mismo.
    """

    nombre: str
    recall: dict[int, float]
    latencia_media_s: float
    coste_medio_usd: float
    n_preguntas: int
    pendiente: str | None = None  # motivo si la fila no se pudo medir
    # Detalle por pregunta: id -> en qué puesto salió su ancla, o None si no
    # salió. Guardar el puesto y no un sí/no permite sacar después cualquier k,
    # el MRR, y contar en la defensa qué preguntas movió cada mejora.
    puestos: dict[str, int | None] = field(default_factory=dict)

    @property
    def mrr(self) -> float:
        """Media del inverso del puesto del ancla."""
        return mrr(self.puestos)

    def aciertos_en(self, k: int) -> dict[str, bool]:
        """Qué preguntas tuvieron su ancla en el top-`k`."""
        return {pid: bool(p and p <= k) for pid, p in self.puestos.items()}


def _filtros_de(pregunta: Pregunta) -> Filtros:
    """Los filtros de metadatos que la pregunta trae consigo.

    El emisor, el ejercicio y el item que la pregunta ya conoce son justo lo que
    un agente pasaría a `search_filings`. Restringir con ellos es lo que la fila
    «+ filtro metadatos» está midiendo.
    """
    return Filtros(
        ticker=pregunta.ticker,
        fiscal_year=pregunta.fiscal_year,
        item=pregunta.item_esperado,
    )


def _preguntas_con_ancla(preguntas: Sequence[Pregunta]) -> list[Pregunta]:
    """Solo las preguntas que anclan a una frase del texto.

    El `recall@k` mide retrieval, y solo lo miden las preguntas con `ancla_texto`
    (las extractivas). Una numérica pura se responde por XBRL y no dice nada del
    recuperador: meterla aquí solo diluiría la métrica.
    """
    return [p for p in preguntas if p.ancla_texto]


def medir_configuracion(
    nombre: str,
    overrides: dict[str, object],
    corpus: Corpus,
    preguntas: Sequence[Pregunta],
    base: Settings,
    *,
    proveedor: ProveedorLLM | None = None,
    ks: Sequence[int] = KS_POR_DEFECTO,
    recuperador: Recuperador | None = None,
) -> FilaAblacion:
    """Mide una sola configuración sobre las preguntas con ancla.

    Construye el recuperador que describen los `overrides`, lanza cada pregunta
    con el `k` máximo pedido y calcula el recall contra el ancla, la latencia
    media por consulta y el coste medio (el de la reescritura, si la hay).

    Si la configuración pide algo que no se puede montar —la reescritura sin
    clave de API para el modelo— la fila se marca como
    `pendiente` con el motivo, en vez de abortar la tabla entera. Una fila que
    falta con su porqué es más honesta que una tabla que no se genera.

    `recuperador` permite INYECTAR uno ya construido en vez de fabricarlo desde
    la configuración. Es la costura que usan los tests: sin ella, medir cualquier
    fila obligaría a montar el índice FAISS y el modelo de embeddings, y no se
    podría comprobar la lógica del runner —el recall, el coste, la decisión de
    pasar o no los filtros— sin 130 MB de descarga. En producción va a `None`.
    """
    cfg = base.model_copy(update={**SIN_MEJORAS, **overrides})
    k_max = max(ks)

    if recuperador is None:
        try:
            recuperador = construir_recuperador(corpus, cfg, proveedor)
        except (ValueError, NotImplementedError) as exc:
            return FilaAblacion(
                nombre=nombre,
                recall=dict.fromkeys(ks, 0.0),
                latencia_media_s=0.0,
                coste_medio_usd=0.0,
                n_preguntas=0,
                pendiente=str(exc),
            )

    utiles = _preguntas_con_ancla(preguntas)
    recuperaciones: list[tuple[Sequence[Fragmento], str]] = []
    puestos: dict[str, int | None] = {}
    tiempo_total = 0.0

    for pregunta in utiles:
        # La fila base busca SIN filtros (ver cabecera del módulo); las filas con
        # el filtro activo los aplican. Así la mejora del filtro es real y no un
        # artefacto de que el denso ya filtraba en su barrido.
        filtros = _filtros_de(pregunta) if cfg.filtro_metadatos else None

        inicio = time.perf_counter()
        encontrados = recuperador.recuperar(pregunta.pregunta, filtros, k=k_max)
        tiempo_total += time.perf_counter() - inicio

        ancla = pregunta.ancla_texto or ""
        recuperaciones.append((encontrados, ancla))
        # El puesto, no un sí/no: es lo que permite decir "esta mejora arregló
        # g-a-003 pero rompió g-a-007" y de paso sacar el MRR.
        puestos[pregunta.id] = posicion_del_ancla(pregunta, encontrados)

    recall = recall_at_k(recuperaciones, ks)
    n = len(utiles)
    # Lo que la caché de reescrituras se ahorró vuelve a la cuenta: la tabla
    # compara técnicas, y la primera vez que se reescribe una consulta se paga.
    tiempo_total += _latencia_ahorrada(recuperador)
    latencia_media = tiempo_total / n if n else 0.0

    # El coste solo lo añade la reescritura, y solo ella lo sabe contar. Se le
    # pregunta si el recuperador construido expone el contador; las demás
    # configuraciones no llaman al modelo y su coste es 0.
    coste_total = _coste_reescritura(recuperador)
    coste_medio = (coste_total / n) if (n and coste_total is not None) else 0.0

    return FilaAblacion(
        nombre=nombre,
        recall=recall,
        latencia_media_s=latencia_media,
        coste_medio_usd=coste_medio,
        n_preguntas=n,
        puestos=puestos,
    )


def _latencia_ahorrada(recuperador: object) -> float:
    """Los segundos de reescritura que la caché no volvió a gastar."""
    ahorrada = getattr(recuperador, "latencia_ahorrada", None)
    return float(ahorrada()) if ahorrada is not None else 0.0


def _coste_reescritura(recuperador: object) -> float | None:
    """El coste en USD que añadió la reescritura, o 0 si no hubo.

    La reescritura es el único decorador que gasta dinero, y expone
    `uso_acumulado()`. Se busca ese método sin acoplarse al tipo: si el
    recuperador no lo tiene, es que no hubo reescritura y el coste es 0.
    """
    usar = getattr(recuperador, "uso_acumulado", None)
    if usar is None:
        return 0.0
    uso = usar()
    return uso.coste_usd if isinstance(uso, UsoTokens) else 0.0


def ejecutar_ablacion(
    corpus: Corpus,
    preguntas: Sequence[Pregunta],
    base: Settings | None = None,
    proveedor: ProveedorLLM | None = None,
    ks: Sequence[int] = KS_POR_DEFECTO,
) -> list[FilaAblacion]:
    """La tabla entera: una fila por configuración de `CONFIGURACIONES_ABLACION`.

    Recorre las configuraciones declaradas como datos en la fábrica. Añadir una
    fila a la tabla es añadir una tupla allí, nunca tocar este runner: esa es la
    prueba de que el diseño Strategy + Decorator cumplió su promesa.
    """
    cfg = base or Settings()
    return [
        medir_configuracion(
            nombre, dict(overrides), corpus, preguntas, cfg, proveedor=proveedor, ks=ks
        )
        for nombre, overrides in CONFIGURACIONES_ABLACION
    ]


# ---------------------------------------------------------------------------
# Escritura de la tabla: markdown para el informe, csv para reprocesar
# ---------------------------------------------------------------------------


def _cabeceras(ks: Sequence[int]) -> list[str]:
    """Las columnas de la tabla, en orden."""
    return (
        ["configuración"]
        + [f"recall@{k}" for k in ks]
        + ["MRR", "latencia media (s)", "coste medio ($)"]
    )


def tabla_markdown(
    filas: Sequence[FilaAblacion], ks: Sequence[int] = KS_POR_DEFECTO
) -> str:
    """La tabla de ablación en markdown, con el mejor recall remarcado.

    En recall, mejor es MAYOR y se remarca el máximo de cada columna. En
    latencia y en coste, mejor es MENOR: no se remarcan aquí para no invitar a
    leerlas al revés, pero se muestran, porque son el precio de cada mejora y el
    enunciado pide que sean columnas y no una nota al pie.
    """
    cabeceras = _cabeceras(ks)
    medibles = [f for f in filas if f.pendiente is None]
    # El mejor recall de cada k, para poder remarcarlo en negrita.
    mejor = {k: max((f.recall.get(k, 0.0) for f in medibles), default=0.0) for k in ks}

    lineas = ["| " + " | ".join(cabeceras) + " |"]
    lineas.append("| " + " | ".join("---" for _ in cabeceras) + " |")
    for fila in filas:
        if fila.pendiente is not None:
            celdas = [fila.nombre] + ["—"] * (len(cabeceras) - 1)
            celdas[-1] = f"pendiente: {fila.pendiente}"
            lineas.append("| " + " | ".join(celdas) + " |")
            continue
        celdas = [fila.nombre]
        for k in ks:
            valor = fila.recall.get(k, 0.0)
            texto = f"{valor:.2f}"
            if valor >= mejor[k] > 0.0:
                texto = f"**{texto}**"  # el mejor de la columna, remarcado
            celdas.append(texto)
        celdas.append(f"{fila.mrr:.2f}")
        celdas.append(f"{fila.latencia_media_s * 1000:.1f} ms")
        celdas.append(f"{fila.coste_medio_usd:.5f}")
        lineas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(lineas) + "\n"


def escribir_ablacion(
    filas: Sequence[FilaAblacion],
    dir_salida: Path,
    ks: Sequence[int] = KS_POR_DEFECTO,
) -> list[Path]:
    """Escribe `ablacion.md`, `ablacion.csv` y el detalle por pregunta.

    Devuelve las rutas escritas. El markdown es para pegar en el informe; el csv
    es para reprocesar sin volver a ejecutar; el detalle por pregunta es para la
    defensa, donde la historia no es la media sino qué preguntas movió cada
    arreglo.
    """
    dir_salida.mkdir(parents=True, exist_ok=True)
    ruta_md = dir_salida / "ablacion.md"
    ruta_csv = dir_salida / "ablacion.csv"
    ruta_detalle = dir_salida / "ablacion_detalle.csv"

    ruta_md.write_text(tabla_markdown(filas, ks), encoding="utf-8", newline="\n")

    with ruta_csv.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f, lineterminator="\n")
        escritor.writerow([*_cabeceras(ks), "n_preguntas", "pendiente"])
        for fila in filas:
            escritor.writerow(
                [fila.nombre]
                + [f"{fila.recall.get(k, 0.0):.4f}" for k in ks]
                + [
                    f"{fila.mrr:.4f}",
                    f"{fila.latencia_media_s:.6f}",
                    f"{fila.coste_medio_usd:.6f}",
                    fila.n_preguntas,
                    fila.pendiente or "",
                ]
            )

    # Detalle: una fila por pregunta, una columna por configuración, con el
    # puesto del ancla. Es la vista que enseña qué rompió cada mejora, no solo
    # cuánto subió la media.
    ids = sorted({pid for fila in filas for pid in fila.puestos})
    with ruta_detalle.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f, lineterminator="\n")
        escritor.writerow(["pregunta_id", *(fila.nombre for fila in filas)])
        for pid in ids:
            fila_pid: list[object] = [pid]
            for fila in filas:
                if fila.pendiente:
                    fila_pid.append("")  # no se midió: celda en blanco, no un 0
                else:
                    puesto = fila.puestos.get(pid)
                    fila_pid.append("" if puesto is None else puesto)
            escritor.writerow(fila_pid)

    ruta_significancia = dir_salida / "significancia.md"
    ruta_significancia.write_text(
        tabla_significancia(filas), encoding="utf-8", newline="\n"
    )
    return [ruta_md, ruta_csv, ruta_detalle, ruta_significancia]


def tabla_significancia(filas: Sequence[FilaAblacion], k: int = 5) -> str:
    """Cada configuración contra la primera, con McNemar exacto sobre recall@k.

    Con doce preguntas con ancla, subir de 0,67 a 0,83 son dos preguntas. Esta
    tabla dice cuáles de las mejoras de la de arriba aguantan un contraste y
    cuáles son ruido; casi ninguna lo aguanta, y decirlo es parte del trabajo.
    """
    medibles = [f for f in filas if f.pendiente is None and f.puestos]
    if len(medibles) < MINIMO_PARA_COMPARAR:
        return "No hay dos configuraciones medidas que comparar.\n"
    base, *resto = medibles
    aciertos_base = base.aciertos_en(k)
    lineas = [
        f"Contraste contra «{base.nombre}» sobre recall@{k}, "
        f"{len(aciertos_base)} preguntas con ancla. McNemar exacto, pareado.",
        "",
        f"| configuración | recall@{k} | arregla | rompe | p |",
        "| --- | --- | --- | --- | --- |",
    ]
    for fila in resto:
        aciertos = fila.aciertos_en(k)
        comunes = sorted(set(aciertos_base) & set(aciertos))
        prueba = mcnemar(
            [aciertos[i] for i in comunes], [aciertos_base[i] for i in comunes]
        )
        marca = "" if prueba.significativa() else " (n. s.)"
        lineas.append(
            f"| {fila.nombre} | {fila.recall.get(k, 0.0):.2f} | {prueba.solo_a} | "
            f"{prueba.solo_b} | {prueba.p_valor:.3f}{marca} |"
        )
    return "\n".join(lineas) + "\n"
