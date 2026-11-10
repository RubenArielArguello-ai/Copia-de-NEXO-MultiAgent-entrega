"""
API — Configuración central del sistema.

Centraliza modelos, timeouts, proveedores y comportamientos
sin tocar el código de los agentes.
Permite sobreescritura dinámica mediante variables de entorno.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────
#  Validación de entradas y manejo seguro de variables de entorno
# ─────────────────────────────────────────────

def validate_env_var(var_name: str, default_value: Any = None) -> Any:
    """Valida una variable de entorno y devuelve su valor."""
    value = os.getenv(var_name)
    if value is not None:
        try:
            # Attempt to convert the value to a specific type
            return type(default_value)(value)
        except ValueError:
            print(f"Warning: Invalid value for {var_name}. Using default.")
            return default_value
    else:
        print(f"Warning: Missing environment variable {var_name}. Using default.")
        return default_value

# ─────────────────────────────────────────────
#  Entorno y URLs
# ─────────────────────────────────────────────
API_HOST: str = validate_env_var("NEXO_API_HOST", "0.0.0.0")
API_PORT: int = validate_env_var("NEXO_API_PORT", 8000)

# ─────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────
LOG_LEVEL = validate_env_var("NEXO_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
