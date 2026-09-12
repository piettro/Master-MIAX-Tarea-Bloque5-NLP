"""El dominio: modelos, protocolos, errores y la tolerancia compartida.

Nada de aquí importa LangChain, FAISS, pandas ni un proveedor de LLM. Es lo que
permite que la suite de tests corra en segundos, sin red y sin clave de API.
"""

from __future__ import annotations

from agente_10k.dominio.errores import (
    CorpusNoEncontrado,
    CuotaAgotada,
    ErrorAgente10K,
    GoldenSetInvalido,
    IndiceDesalineado,
    SalidaNoValida,
)
from agente_10k.dominio.modelos import (
    EstadoTrayectoria,
    Familia,
    Filtros,
    Fragmento,
    Fuente,
    HechoXbrl,
    InformeEvaluacion,
    Item,
    LlamadaHerramienta,
    Metricas,
    Pregunta,
    RespuestaFinanciera,
    ResultadoPregunta,
    Seccion,
    Ticker,
    Traza,
    UsoTokens,
    Veredicto,
    VeredictoEvaluador,
)
from agente_10k.dominio.protocolos import (
    Codificador,
    ProveedorLLM,
    Recuperador,
    RepositorioFragmentos,
    RepositorioSecciones,
    RepositorioXbrl,
)
from agente_10k.dominio.tolerancia import TOLERANCIA, Tolerancia

__all__ = [
    "TOLERANCIA",
    "Codificador",
    "CorpusNoEncontrado",
    "CuotaAgotada",
    "ErrorAgente10K",
    "EstadoTrayectoria",
    "Familia",
    "Filtros",
    "Fragmento",
    "Fuente",
    "GoldenSetInvalido",
    "HechoXbrl",
    "IndiceDesalineado",
    "InformeEvaluacion",
    "Item",
    "LlamadaHerramienta",
    "Metricas",
    "Pregunta",
    "ProveedorLLM",
    "Recuperador",
    "RepositorioFragmentos",
    "RepositorioSecciones",
    "RepositorioXbrl",
    "RespuestaFinanciera",
    "ResultadoPregunta",
    "SalidaNoValida",
    "Seccion",
    "Ticker",
    "Tolerancia",
    "Traza",
    "UsoTokens",
    "Veredicto",
    "VeredictoEvaluador",
]
