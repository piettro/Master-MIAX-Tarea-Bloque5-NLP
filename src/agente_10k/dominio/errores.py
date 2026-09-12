"""La jerarquía de excepciones del dominio.

Dos reglas que se aplican en todo el paquete:

1. Nada de `try/except` que se trague la excepción y devuelva `None`. Si algo
   falla, o se lanza una de estas o se devuelve un texto que le explica al
   modelo qué pasó. Un `None` silencioso aparece tres capas más arriba como un
   fallo imposible de diagnosticar.
2. Lo que ve el MODELO nunca es una excepción: las tools devuelven texto
   siempre, incluso cuando no hay dato. Estas excepciones son para lo que ve el
   PROGRAMADOR: corpus mal montado, configuración inválida, índice desalineado.
"""

from __future__ import annotations


class ErrorAgente10K(Exception):  # noqa: N818 -- prefijo Error, no sufijo
    """Raíz de todo lo que puede fallar en el paquete."""


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------


class ErrorCorpus(ErrorAgente10K):
    """Algo va mal con los datos."""


class CorpusNoEncontrado(ErrorCorpus):
    """El corpus no está montado. Se lanza con instrucciones, no a secas."""

    def __init__(self, que_falta: str, donde: str) -> None:
        """Construye el error diciendo qué fichero falta y dónde se buscó."""
        super().__init__(
            f"No encuentro {que_falta} en {donde}. Descomprime "
            f"corpus_miax_2026.zip e indice_faiss.zip dentro de esa carpeta "
            f"(el índice va en indice/). Ver README, sección «Corpus»."
        )
        self.que_falta = que_falta
        self.donde = donde


class IndiceDesalineado(ErrorCorpus):
    """El índice FAISS y sus metadatos no describen los mismos fragmentos.

    Es el fallo más caro del retrieval porque no da ningún error por su cuenta:
    devuelve el texto equivocado con una puntuación perfectamente creíble.
    """

    def __init__(self, n_vectores: int, n_filas: int) -> None:
        """Construye el error con las dos cuentas que no cuadran."""
        super().__init__(
            f"El índice tiene {n_vectores} vectores y los metadatos "
            f"{n_filas} filas. Están desalineados y el retrieval devolvería "
            f"texto equivocado sin avisar: vuelve a descomprimir los dos ZIP "
            f"en la misma carpeta."
        )
        self.n_vectores = n_vectores
        self.n_filas = n_filas


class DatosNoDisponibles(ErrorCorpus):
    """Un repositorio que hace falta no tiene datos cargados."""


# ---------------------------------------------------------------------------
# Configuración y proveedor
# ---------------------------------------------------------------------------


class ErrorConfiguracion(ErrorAgente10K):
    """La configuración no permite construir el sistema."""


class FaltaClaveApi(ErrorConfiguracion):
    """No hay clave para el proveedor seleccionado."""

    def __init__(self, proveedor: str, variable: str) -> None:
        """Construye el error diciendo qué variable de entorno falta."""
        super().__init__(
            f"El proveedor '{proveedor}' necesita la variable de entorno "
            f"{variable} y no está definida. Copia .env.example a .env y "
            f"rellénala, o expórtala en tu shell. Nunca la escribas en el "
            f"código (CONTRATO C6)."
        )
        self.proveedor = proveedor
        self.variable = variable


class ProveedorNoSoportado(ErrorConfiguracion):
    """`LLM_PROVIDER` no es uno de los cuatro previstos."""


class ErrorProveedor(ErrorAgente10K):
    """El proveedor devolvió un error."""


class CuotaAgotada(ErrorProveedor):
    """401, 402 o 429. Dispara el fallback ordenado al modelo alternativo.

    La conmutación es una VARIABLE DE ESTADO: una vez agotado el primario no se
    reintenta en cada llamada, que era justo el error que el profesor señaló en
    clase sobre el pseudocódigo del fallback.
    """

    def __init__(self, modelo: str, codigo: int) -> None:
        """Construye el error con el modelo agotado y el código HTTP."""
        super().__init__(f"Cuota agotada en '{modelo}' (HTTP {codigo}).")
        self.modelo = modelo
        self.codigo = codigo


class SinProveedoresDisponibles(ErrorProveedor):
    """Se agotaron el primario y el de reserva."""


# ---------------------------------------------------------------------------
# Agente y evaluación
# ---------------------------------------------------------------------------


class ErrorAgente(ErrorAgente10K):
    """Algo falló durante la invocación del agente."""


class SalidaNoValida(ErrorAgente):
    """El modelo no consiguió producir una `RespuestaFinanciera` válida.

    No aborta la evaluación: quien la captura devuelve una respuesta con
    `fuente='ninguna'` y el motivo. Una pregunta rota no puede tumbar las otras
    diecinueve.
    """


class LimiteLlamadasSuperado(ErrorAgente):
    """El agente agotó su presupuesto de llamadas a herramienta."""


class ErrorEvaluacion(ErrorAgente10K):
    """Algo falló al evaluar."""


class GoldenSetInvalido(ErrorEvaluacion):
    """El golden set no cumple el CONTRATO C4."""

    def __init__(self, problemas: list[str]) -> None:
        """Construye el error con el informe legible de problemas."""
        detalle = "\n".join(f"  - {p}" for p in problemas)
        super().__init__(f"El golden set no es válido:\n{detalle}")
        self.problemas = problemas
