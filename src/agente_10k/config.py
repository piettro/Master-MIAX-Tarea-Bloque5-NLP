"""Configuración del sistema: 12-factor, todo por entorno.

Cambiar de recuperador, de modelo o de proveedor es cambiar una variable de
entorno, nunca editar código. Es lo que hace que la tabla de ablación
salga de un bucle sobre configuraciones y que `responder()` funcione
sobre un clon limpio sin tocar nada (CONTRATO C5).

Prefijo `AGENTE10K_` en todo salvo las claves de API, que llevan el nombre
canónico que espera cada SDK (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`…).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from agente_10k.dominio.errores import FaltaClaveApi, ProveedorNoSoportado

Proveedor = Literal["openrouter", "anthropic", "google", "openai"]
TipoRecuperador = Literal["denso", "lexico", "hibrido"]

VARIABLE_CLAVE: dict[str, str] = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
}

RAIZ_REPO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Toda la configuración del sistema, leída del entorno y de `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTE10K_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- proveedor de LLM (P5) --------------------------------------------
    llm_provider: Proveedor = "openrouter"
    llm_model: str = "google/gemini-3.8-flash"
    llm_model_fallback: str | None = "google/gemini-3.5-flash-lite"
    temperatura: float = 0.0
    semilla: int = 20260923

    # --- presupuesto y guardarraíles --------------------------------------
    max_llamadas_herramienta: int = Field(
        default=8,
        ge=1,
        description=(
            "Corta la invocación al superarlo. El notebook de la sesión 1 "
            "enseña el bucle infinito con el margen bruto de Amazon; esto es "
            "lo que lo para"
        ),
    )
    max_reintentos_guardarrail: int = Field(default=1, ge=0)
    max_tokens_seccion: int | None = Field(
        default=None,
        description=(
            "Trunca `read_section` a este número de tokens. `None` devuelve la "
            "sección entera, que es lo que hace el baseline. Es un parámetro "
            "con valor por defecto, permitido por el CONTRATO C1, y baja el "
            "coste medio por pregunta, que es una columna de la tabla"
        ),
    )

    # --- corpus ------------------------------------------------------------
    dir_corpus: Path = Path("data/corpus")
    permitir_secciones_reconstruidas: bool = Field(
        default=True,
        description=(
            "Si `secciones.jsonl` no está, derivar las secciones de los "
            "fragmentos. NO es literal en las fronteras de troceado. Ponlo "
            "a false para que falte el fichero sea un error"
        ),
    )

    # --- retrieval (F3) ----------------------------------------------------
    # Los valores por defecto son los del SISTEMA FINAL, la fila que ganó la
    # ablación: `responder()` sobre un clon limpio tiene que ejecutar
    # el sistema que se defiende sin exportar nada. El baseline y las filas de
    # la ablación parten de `retrieval.fabrica.SIN_MEJORAS`, no de aquí.
    recuperador: TipoRecuperador = "hibrido"
    filtro_metadatos: bool = Field(
        default=True,
        description=(
            "Aplicar los filtros ANTES de buscar. El profesor filtra después, "
            "sobre el orden que devuelve el índice; hacerlo antes es la primera "
            "fila de la tabla de ablación"
        ),
    )
    reescritura_consulta: bool = True
    reordenacion: bool = Field(
        default=True,
        description="Reordenar los candidatos con un cross-encoder",
    )
    fusion_reordenacion: bool = Field(
        default=True,
        description=(
            "Mezclar el orden del cross-encoder con el del recuperador por RRF "
            "en vez de sustituirlo. Protege el recall profundo a costa de algo "
            "de precisión arriba"
        ),
    )
    modelo_reordenacion: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    profundidad_reordenacion: int = Field(default=20, ge=2)
    rrf_k: int = Field(default=60, ge=1)
    k_por_defecto: int = Field(default=5, ge=1)

    # --- caché -------------------------------------------------------------
    cache_activa: bool = True
    dir_cache: Path = Path(".cache/agente_10k")

    # --- salida ------------------------------------------------------------
    dir_resultados: Path = Path("resultados")
    version_prompt: str = "v2"

    @field_validator("dir_corpus", "dir_cache", "dir_resultados", mode="after")
    @classmethod
    def _absolutas(cls, valor: Path) -> Path:
        """Resuelve las rutas relativas contra la raíz del repositorio.

        Sin esto, `responder()` solo funciona si el proceso arranca en la raíz.
        El día 24 se ejecuta desde donde sea, y eso no puede romper nada.
        """
        return valor if valor.is_absolute() else (RAIZ_REPO / valor).resolve()

    # --- derivadas ---------------------------------------------------------
    @property
    def ruta_secciones(self) -> Path:
        """`secciones.jsonl` dentro del corpus."""
        return self.dir_corpus / "secciones.jsonl"

    @property
    def ruta_chunks(self) -> Path:
        """`chunks.jsonl` dentro del corpus."""
        return self.dir_corpus / "chunks.jsonl"

    @property
    def ruta_xbrl(self) -> Path:
        """`xbrl_facts.parquet` dentro del corpus."""
        return self.dir_corpus / "xbrl_facts.parquet"

    @property
    def dir_indice(self) -> Path:
        """La carpeta del índice FAISS y sus metadatos."""
        return self.dir_corpus / "indice"

    @property
    def ruta_indice(self) -> Path:
        """El índice FAISS."""
        return self.dir_indice / "corpus.faiss"

    @property
    def ruta_chunks_meta(self) -> Path:
        """Los metadatos alineados con el índice. Traen el texto del fragmento."""
        return self.dir_indice / "chunks_meta.parquet"

    @property
    def ruta_secciones_derivadas(self) -> Path:
        """Dónde se escriben las secciones reconstruidas desde los chunks."""
        return RAIZ_REPO / "data" / "derivado" / "secciones_reconstruidas.jsonl"

    @property
    def variable_clave(self) -> str:
        """La variable de entorno que lleva la clave del proveedor activo."""
        try:
            return VARIABLE_CLAVE[self.llm_provider]
        except KeyError as exc:
            raise ProveedorNoSoportado(
                f"Proveedor '{self.llm_provider}' desconocido. Opciones: "
                f"{', '.join(sorted(VARIABLE_CLAVE))}."
            ) from exc

    def clave_api(self) -> str:
        """La clave del proveedor activo, o un error que dice qué exportar."""
        valor = os.environ.get(self.variable_clave, "").strip()
        if not valor:
            raise FaltaClaveApi(self.llm_provider, self.variable_clave)
        return valor

    def hay_clave(self) -> bool:
        """Si hay clave para el proveedor activo, sin lanzar nada."""
        return bool(os.environ.get(VARIABLE_CLAVE.get(self.llm_provider, ""), ""))

    def identificador_modelo(self) -> str:
        """El modelo en el formato que espera `init_chat_model`.

        LangChain admite `proveedor:modelo` en una sola cadena. Mantenerlo así
        es lo que hace que cambiar de proveedor sea cambiar una variable.
        """
        return f"{self.llm_provider}:{self.llm_model}"

    def resumen_retrieval(self) -> dict[str, object]:
        """La configuración de retrieval, para la traza y la tabla de ablación."""
        return {
            "recuperador": self.recuperador,
            "filtro_metadatos": self.filtro_metadatos,
            "reescritura_consulta": self.reescritura_consulta,
            "reordenacion": self.reordenacion,
            "fusion_reordenacion": self.fusion_reordenacion,
            "rrf_k": self.rrf_k,
            "k_por_defecto": self.k_por_defecto,
        }


def cargar_entorno() -> None:
    """Carga `.env` en `os.environ` sin pisar lo que ya esté exportado.

    `Settings` solo lee de `.env` sus campos `AGENTE10K_*`, no las claves de
    API, que el SDK busca en el entorno.
    """
    from dotenv import load_dotenv

    load_dotenv(RAIZ_REPO / ".env", override=False)


@lru_cache(maxsize=1)
def settings() -> Settings:
    """La configuración del proceso.

    Cacheada porque leer el entorno en cada llamada a una tool no aporta nada.
    NO es un singleton del LLM ni del índice —eso está prohibido—: es un objeto
    de datos inmutable que se puede sustituir en los tests con
    `settings.cache_clear()`.
    """
    return Settings()
