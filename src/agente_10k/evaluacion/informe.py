"""Tablas del informe en markdown y csv, leídas de `resultados/`.

Ninguna cifra se escribe a mano: si no sale de `make informe`, no entra.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

from agente_10k.dominio.modelos import InformeEvaluacion, ResultadoPregunta
from agente_10k.evaluacion.estadistica import Intervalo, mcnemar, wilson

COLUMNAS_MENOR_ES_MEJOR = frozenset(
    {"coste medio", "latencia media", "tool calls/pregunta"}
)

COLUMNAS_PRINCIPAL: tuple[str, ...] = (
    "extractiva",
    "numérica",
    "comparativa",
    "hueco",
    "total",
    "recall@5",
    "coste medio",
    "latencia media",
    "tool calls/pregunta",
)

_CLAVE_FAMILIA = {
    "extractiva": "extractiva",
    "numérica": "numerica",
    "comparativa": "comparativa",
    "hueco": "hueco",
    "total": "total",
}

Formato = Callable[[float], str]

_FORMATOS: dict[str, Formato] = {
    "coste medio": lambda v: f"{v * 100:.3f} ¢",
    "latencia media": lambda v: f"{v:.1f} s",
    "tool calls/pregunta": lambda v: f"{v:.1f}",
}


def _porcentaje(valor: float) -> str:
    return f"{valor:.0%}"


def fila_principal(informe: InformeEvaluacion) -> dict[str, float | None]:
    """Los valores de la tabla principal para un sistema, sin formatear."""
    m = informe.metricas
    fila: dict[str, float | None] = {
        columna: m.aciertos_por_familia.get(clave)
        for columna, clave in _CLAVE_FAMILIA.items()
    }
    fila["recall@5"] = m.recall_at_k.get(5)
    fila["coste medio"] = m.coste_medio_usd
    fila["latencia media"] = m.latencia_media_s
    fila["tool calls/pregunta"] = m.llamadas_por_pregunta
    return fila


def _mejores(filas: Sequence[dict[str, float | None]], columna: str) -> set[int]:
    """Los índices de las filas con el mejor valor de la columna (empates, todos)."""
    valores = [(i, f[columna]) for i, f in enumerate(filas) if f[columna] is not None]
    if len(valores) < 2:  # noqa: PLR2004 — con una sola fila no hay nada que remarcar
        return set()
    elegir = min if columna in COLUMNAS_MENOR_ES_MEJOR else max
    mejor = elegir(v for _, v in valores if v is not None)
    return {i for i, v in valores if v == mejor}


def _celda(columna: str, valor: float | None, remarcar: bool) -> str:
    if valor is None:
        return "—"
    texto = _FORMATOS.get(columna, _porcentaje)(valor)
    return f"**{texto}**" if remarcar else texto


def _markdown(cabecera: Sequence[str], filas: Sequence[Sequence[str]]) -> str:
    lineas = [
        "| " + " | ".join(cabecera) + " |",
        "| " + " | ".join("---" for _ in cabecera) + " |",
    ]
    lineas += ["| " + " | ".join(fila) + " |" for fila in filas]
    return "\n".join(lineas) + "\n"


def tabla_comparada(informes: Sequence[InformeEvaluacion]) -> str:
    """La tabla principal para cualquier número de sistemas, mejor remarcado."""
    filas = [fila_principal(i) for i in informes]
    mejores = {c: _mejores(filas, c) for c in COLUMNAS_PRINCIPAL}
    cuerpo = [
        [informe.etiqueta]
        + [_celda(c, fila[c], i in mejores[c]) for c in COLUMNAS_PRINCIPAL]
        for i, (informe, fila) in enumerate(zip(informes, filas, strict=True))
    ]
    return _markdown(["sistema", *COLUMNAS_PRINCIPAL], cuerpo)


def tabla_principal(baseline: InformeEvaluacion, final: InformeEvaluacion) -> str:
    """La tabla baseline contra final, en markdown y con el mejor remarcado."""
    return tabla_comparada([baseline, final])


def _causas(resultados: Sequence[ResultadoPregunta]) -> str:
    """Las causas de fallo más frecuentes, para la columna «qué falló»."""
    contador: Counter[str] = Counter()
    for r in resultados:
        if r.error:
            contador["error de ejecución"] += 1
            continue
        for veredicto in (r.cita, r.cifra):
            if veredicto and veredicto.veredicto == "fallo":
                contador.update(veredicto.detalle.keys())
        if r.estado_trayectoria.startswith("camino_incorrecto"):
            contador["camino incorrecto"] += 1
    return ", ".join(f"{causa} ({n})" for causa, n in contador.most_common(3)) or "—"


def tabla_por_familia(informe: InformeEvaluacion) -> str:
    """Aciertos por familia, con el detalle de qué falló en cada una."""
    grupos: dict[str, list[ResultadoPregunta]] = {}
    for r in informe.resultados:
        grupos.setdefault(r.familia or "sin familia", []).append(r)
        if r.es_hueco:
            grupos.setdefault("hueco", []).append(r)
    filas = []
    for nombre, resultados in grupos.items():
        evaluables = [r for r in resultados if r.error or r.acierto is not None]
        aciertos = sum(1 for r in evaluables if r.acierto and not r.error)
        fallidas = [r for r in evaluables if not (r.acierto and not r.error)]
        filas.append(
            [
                nombre,
                str(len(resultados)),
                f"{aciertos}/{len(evaluables)}" if evaluables else "—",
                _causas(fallidas),
            ]
        )
    return _markdown(["familia", "preguntas", "aciertos", "qué falló"], filas)


def tabla_trayectoria(informe: InformeEvaluacion) -> str:
    """Los tres estados de trayectoria y su columna de camino equivocado."""
    estados: Counter[str] = Counter(
        str(r.estado_trayectoria) for r in informe.resultados
    )
    total = sum(n for e, n in estados.items() if e != "no_aplica")
    nombres = {
        "camino_correcto": "camino correcto",
        "camino_incorrecto_respuesta_correcta": "camino equivocado, acierta",
        "camino_incorrecto_respuesta_incorrecta": "camino equivocado, falla",
        "no_aplica": "no aplica (sin herramienta_esperada)",
    }
    filas = [
        [
            texto,
            str(estados.get(estado, 0)),
            _porcentaje(estados.get(estado, 0) / total)
            if total and estado != "no_aplica"
            else "—",
        ]
        for estado, texto in nombres.items()
    ]
    return _markdown(["trayectoria", "preguntas", "proporción"], filas)


def tabla_guardarrail(informe: InformeEvaluacion) -> str:
    """Cuántas veces saltó el guardarraíl y cuántas recuperó."""
    m = informe.metricas
    trazas = [r.traza for r in informe.resultados if r.traza]
    intervenciones = sum(t.intervenciones_guardarrail for t in trazas)
    limite = sum(1 for t in trazas if t.limite_alcanzado)
    filas = [
        [
            "preguntas con intervención del guardarraíl",
            _porcentaje(m.tasa_intervencion_guardarrail),
        ],
        ["intervenciones totales", str(intervenciones)],
        [
            "recuperadas tras intervenir (respuesta correcta)",
            _porcentaje(m.tasa_recuperacion_guardarrail),
        ],
        ["preguntas que agotaron el límite de llamadas", str(limite)],
        ["alucinaciones sobre hueco", str(m.alucinaciones_sobre_hueco)],
        [
            "abstenciones indebidas (dijo «no hay dato» y sí lo había)",
            _porcentaje(m.tasa_abstencion_indebida),
        ],
    ]
    return _markdown(["guardarraíl", "valor"], filas)


def tabla_por_pregunta(informe: InformeEvaluacion) -> str:
    """Una fila por pregunta, con la causa del fallo si lo hubo."""
    filas = []
    for r in informe.resultados:
        camino = " > ".join(r.traza.trayectoria) if r.traza else "—"
        acierto = (
            "error" if r.error else {True: "sí", False: "no", None: "—"}[r.acierto]
        )
        filas.append(
            [
                r.pregunta_id,
                r.familia or "—",
                acierto,
                camino or "(ninguna)",
                _causas([r]) if acierto == "no" or r.error else "",
            ]
        )
    return _markdown(["id", "familia", "acierto", "herramientas", "qué falló"], filas)


def tabla_recall(informe: InformeEvaluacion) -> str:
    """Recall@k del retrieval y el puesto en que apareció cada ancla."""
    recall = informe.metricas.recall_at_k
    if not recall:
        return "Sin recall@k medido en esta ejecución.\n"
    ks = sorted(recall)
    cabecera = [f"recall@{k}" for k in ks] + ["MRR"]
    valores = [_porcentaje(recall[k]) for k in ks] + [f"{informe.metricas.mrr:.2f}"]
    tabla = _markdown(cabecera, [valores])
    puestos = informe.configuracion.get("puesto_del_ancla")
    if isinstance(puestos, dict) and puestos:
        filas = [[str(pid), str(p) if p else "> 10"] for pid, p in puestos.items()]
        tabla += "\n" + _markdown(["pregunta", "puesto del ancla"], filas)
    return tabla


def _aciertos(informe: InformeEvaluacion) -> dict[str, bool]:
    """Acierto de cada pregunta, por id. Un error cuenta como fallo."""
    return {r.pregunta_id: bool(r.acierto) and not r.error for r in informe.resultados}


def _intervalo_total(informe: InformeEvaluacion) -> tuple[int, int, Intervalo]:
    m = informe.metricas
    n = m.n_por_familia.get("total", m.n_preguntas)
    aciertos = round(m.aciertos_por_familia.get("total", 0.0) * n)
    return aciertos, n, wilson(aciertos, n)


def tabla_significancia(a: InformeEvaluacion, b: InformeEvaluacion) -> str:
    """Si la mejora de `b` sobre `a` aguanta un contraste, o es ruido.

    Wilson para el intervalo de cada sistema y McNemar exacto para la
    diferencia, que es lo que toca con datos pareados.
    """
    comunes = sorted(set(_aciertos(a)) & set(_aciertos(b)))
    if not comunes:
        return "Los dos sistemas no comparten ninguna pregunta: no hay contraste.\n"
    filas = []
    for informe in (a, b):
        aciertos, n, intervalo = _intervalo_total(informe)
        filas.append([informe.etiqueta, f"{aciertos}/{n}", str(intervalo)])
    tabla = _markdown(["sistema", "aciertos", "IC 95 % (Wilson)"], filas)

    prueba = mcnemar(
        [_aciertos(a)[i] for i in comunes], [_aciertos(b)[i] for i in comunes]
    )
    veredicto = (
        "la diferencia es significativa"
        if prueba.significativa()
        else "no se puede descartar que sea ruido"
    )
    return (
        tabla + f"\nMcNemar exacto sobre las {len(comunes)} preguntas comunes: "
        f"{a.etiqueta} acierta y {b.etiqueta} falla en {prueba.solo_a}; "
        f"al revés, {prueba.solo_b}. p = {prueba.p_valor:.3f}, {veredicto} "
        "al 5 %.\n"
    )


def tabla_delta(referencia: InformeEvaluacion, ciegas: InformeEvaluacion) -> str:
    """Las preguntas ciegas contra el golden set propio, familia a familia."""
    filas = []
    for columna, clave in _CLAVE_FAMILIA.items():
        a = referencia.metricas.aciertos_por_familia.get(clave)
        b = ciegas.metricas.aciertos_por_familia.get(clave)
        delta = "—" if a is None or b is None else f"{(b - a) * 100:+.0f} pp"
        filas.append(
            [
                columna,
                "—" if a is None else _porcentaje(a),
                "—" if b is None else _porcentaje(b),
                delta,
            ]
        )
    return _markdown(
        ["familia", f"golden ({referencia.etiqueta})", "ciegas", "delta"], filas
    )


def tablas_de_sistema(informe: InformeEvaluacion) -> str:
    """Todas las tablas de una ejecución, en un único markdown."""
    m = informe.metricas
    avisos = informe.configuracion.get("avisos") or []
    cabecera = (
        f"# Resultados · {informe.etiqueta}\n\n"
        f"- fecha: {informe.fecha:%Y-%m-%d %H:%M} UTC\n"
        f"- modelo: {informe.proveedor}:{informe.modelo}\n"
        f"- commit: {informe.commit or '?'}\n"
        f"- preguntas: {m.n_preguntas} ({informe.ruta_preguntas})\n"
    )
    aciertos, n, intervalo = _intervalo_total(informe)
    if n:
        cabecera += f"- acierto total: {aciertos}/{n}, IC 95 % {intervalo}\n"
    if isinstance(avisos, list) and avisos:
        cabecera += "".join(f"- AVISO: {a}\n" for a in avisos)
    partes = [
        cabecera,
        "## Resumen\n\n" + tabla_comparada([informe]),
        "## Por familia\n\n" + tabla_por_familia(informe),
        "## Trayectoria\n\n" + tabla_trayectoria(informe),
        "## Guardarraíl\n\n" + tabla_guardarrail(informe),
        "## Retrieval\n\n" + tabla_recall(informe),
        "## Por pregunta\n\n" + tabla_por_pregunta(informe),
    ]
    return "\n".join(partes)


def cargar_informe(ruta: Path) -> InformeEvaluacion:
    """Lee un `informe.json` escrito por `ejecutor.guardar`."""
    return InformeEvaluacion.model_validate_json(ruta.read_text(encoding="utf-8"))


def _csv_principal(informes: Sequence[InformeEvaluacion], destino: Path) -> None:
    with destino.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f, lineterminator="\n")
        escritor.writerow(["sistema", *COLUMNAS_PRINCIPAL])
        for informe in informes:
            fila = fila_principal(informe)
            escritor.writerow(
                [informe.etiqueta, *(fila[c] for c in COLUMNAS_PRINCIPAL)]
            )


def generar_todo(dir_resultados: Path, destino: Path) -> list[Path]:
    """Regenera todas las tablas desde `resultados/` y devuelve lo escrito.

    La tabla principal y el delta de ciegas solo salen si están sus informes.
    """
    informes = {
        ruta.parent.name: cargar_informe(ruta)
        for ruta in sorted(dir_resultados.glob("*/informe.json"))
    }
    destino.mkdir(parents=True, exist_ok=True)
    escritos: list[Path] = []

    def escribir(nombre: str, texto: str) -> None:
        ruta = destino / nombre
        ruta.write_text(texto, encoding="utf-8", newline="\n")
        escritos.append(ruta)

    for etiqueta, informe in informes.items():
        escribir(f"resultados_{etiqueta}.md", tablas_de_sistema(informe))
    if "baseline" in informes and "final" in informes:
        comparados = [informes["baseline"], informes["final"]]
        escribir("tabla_principal.md", tabla_comparada(comparados))
        escribir("significancia.md", tabla_significancia(*comparados))
        _csv_principal(comparados, destino / "tabla_principal.csv")
        escritos.append(destino / "tabla_principal.csv")
    if "ciegas" in informes and "final" in informes:
        escribir("delta_ciegas.md", tabla_delta(informes["final"], informes["ciegas"]))
    return escritos
