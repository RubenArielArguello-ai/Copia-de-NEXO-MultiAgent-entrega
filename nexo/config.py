"""
NEXO — Configuración central del sistema.

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
            return type(default_value)(value)
        except ValueError:
            import logging
            logging.getLogger("nexo.config").warning("Invalid value for %s; using configured default", var_name)
            return default_value
    else:
        # An unset override is the normal default-config path, not a warning.
        return default_value

# ─────────────────────────────────────────────
#  Entorno y URLs
# ─────────────────────────────────────────────
OLLAMA_BASE_URL: str = validate_env_var("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_PROVIDER_TYPE: str = validate_env_var("NEXO_PROVIDER_TYPE", "ollama").lower()

# Timeouts y reintentos para llamadas LLM
OLLAMA_TIMEOUT: int = validate_env_var("NEXO_OLLAMA_TIMEOUT", 180)
OLLAMA_MAX_RETRIES: int = validate_env_var("NEXO_OLLAMA_RETRIES", 3)

# ─────────────────────────────────────────────
#  Modelos Ollama por agente
#  Preferencias del sistema:
#    - Todos los agentes: qwen2.5-coder:7b (contratos JSON validados)
# ─────────────────────────────────────────────
MODEL_ANALYST: str      = validate_env_var("NEXO_MODEL_ANALYST", "qwen2.5-coder:7b")
MODEL_STRATEGIST: str   = validate_env_var("NEXO_MODEL_STRATEGIST", "qwen2.5-coder:7b")
MODEL_EXECUTOR: str     = validate_env_var("NEXO_MODEL_EXECUTOR", "qwen2.5-coder:7b")
MODEL_EVALUATOR: str    = validate_env_var("NEXO_MODEL_EVALUATOR", "qwen2.5-coder:7b")
MODEL_ORCHESTRATOR: str = validate_env_var("NEXO_MODEL_ORCHESTRATOR", "qwen2.5-coder:7b")

PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "ANALYST": {
        "type": DEFAULT_PROVIDER_TYPE,
        "model": MODEL_ANALYST,
        "base_url": OLLAMA_BASE_URL,
        "timeout": OLLAMA_TIMEOUT,
        "retries": OLLAMA_MAX_RETRIES,
    },
    "STRATEGIST": {
        "type": DEFAULT_PROVIDER_TYPE,
        "model": MODEL_STRATEGIST,
        "base_url": OLLAMA_BASE_URL,
        "timeout": OLLAMA_TIMEOUT,
        "retries": OLLAMA_MAX_RETRIES,
    },
    "EXECUTOR": {
        "type": DEFAULT_PROVIDER_TYPE,
        "model": MODEL_EXECUTOR,
        "base_url": OLLAMA_BASE_URL,
        "timeout": OLLAMA_TIMEOUT,
        "retries": OLLAMA_MAX_RETRIES,
    },
    "EVALUATOR": {
        "type": DEFAULT_PROVIDER_TYPE,
        "model": MODEL_EVALUATOR,
        "base_url": OLLAMA_BASE_URL,
        "timeout": OLLAMA_TIMEOUT,
        "retries": OLLAMA_MAX_RETRIES,
    },
    "ORCHESTRATOR": {
        "type": DEFAULT_PROVIDER_TYPE,
        "model": MODEL_ORCHESTRATOR,
        "base_url": OLLAMA_BASE_URL,
        "timeout": OLLAMA_TIMEOUT,
        "retries": OLLAMA_MAX_RETRIES,
    },
}

# ─────────────────────────────────────────────
#  Parámetros del orquestador
# ─────────────────────────────────────────────
ORCHESTRATOR_CONFIG = {
    "max_iterations":         validate_env_var("NEXO_MAX_ITERATIONS", 5),
    "max_replanning_cycles":  validate_env_var("NEXO_MAX_REPLANNING", 2),
    "coherence_threshold":    validate_env_var("NEXO_COHERENCE_THRESHOLD", 0.6),
    "timeout_seconds":        validate_env_var("NEXO_SESSION_TIMEOUT", 300),
}

# ─────────────────────────────────────────────
#  Base de datos
# ─────────────────────────────────────────────
DB_PATH = Path(validate_env_var("NEXO_DB_PATH", str(Path(__file__).parent.parent / "nexo_data.db")))

# ─────────────────────────────────────────────
#  API
# ─────────────────────────────────────────────
API_HOST = validate_env_var("NEXO_API_HOST", "127.0.0.1")
API_PORT = int(validate_env_var("NEXO_API_PORT", 8000))

# ─────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────
LOG_LEVEL = validate_env_var("NEXO_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def get_provider_config(agent_role: str) -> dict[str, Any]:
    """Obtiene la configuración específica para un rol de agente."""
    key = agent_role.upper()
    if key == "ORQUESTADOR":
        key = "ORCHESTRATOR"
    cfg = PROVIDER_CONFIG.get(key)
    if cfg:
        return dict(cfg)
    raise KeyError(f"No hay configuración para el rol {agent_role}")
