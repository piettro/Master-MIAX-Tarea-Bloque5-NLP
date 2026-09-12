"""El agente: proveedor, prompt, middleware, constructor y trazas. FASE 4."""

from __future__ import annotations

from agente_10k.agente.constructor import AgenteInvestigador, construir_agente
from agente_10k.agente.prompts import SYSTEM, VERSION_PROMPT, system_prompt
from agente_10k.agente.proveedores import ProveedorFake, construir_proveedor
from agente_10k.agente.trazas import cumple_trayectoria, resumir

__all__ = [
    "SYSTEM",
    "VERSION_PROMPT",
    "AgenteInvestigador",
    "ProveedorFake",
    "construir_agente",
    "construir_proveedor",
    "cumple_trayectoria",
    "resumir",
    "system_prompt",
]
