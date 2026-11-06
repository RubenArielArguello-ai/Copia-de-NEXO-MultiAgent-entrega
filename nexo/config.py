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
#  Entorno y URLs
# ─────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_HOST", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))

# Tipo de proveedor predeterminado: "ollama" o "mock"
# Si NEXO_PROVIDER_TYPE no se especifica, intenta usar Ollama con fallback a Mock
DEFAULT_PROVIDER_TYPE: str = os.getenv("NEXO_PROVIDER_TYPE", "ollama").lower()

# Timeouts y reintentos para llamadas LLM
OLLAMA_TIMEOUT: int = int(os.getenv("NEXO_OLLAMA_TIMEOUT", "180"))
OLLAMA_MAX_RETRIES: int = int(os.getenv("NEXO_OLLAMA_RETRIES", "3"))

# ─────────────────────────────────────────────
#  Modelos Ollama por agente
#  Preferencias del sistema:
#    - Razonamiento/Análisis/Estrategia/Evaluación/Orquestación: gemma4:12b-mlx
#    - Tareas técnicas y código: qwen2.5-coder:7b
# ─────────────────────────────────────────────
MODEL_ANALYST: str      = os.getenv("NEXO_MODEL_ANALYST", "gemma4:12b-mlx")
MODEL_STRATEGIST: str   = os.getenv("NEXO_MODEL_STRATEGIST", "gemma4:12b-mlx")
MODEL_EXECUTOR: str     = os.getenv("NEXO_MODEL_EXECUTOR", "qwen2.5-coder:7b")
MODEL_EVALUATOR: str    = os.getenv("NEXO_MODEL_EVALUATOR", "gemma4:12b-mlx")
MODEL_ORCHESTRATOR: str = os.getenv("NEXO_MODEL_ORCHESTRATOR", "gemma4:12b-mlx")

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
    "default": {
        "type": "mock",
    },
}

# ─────────────────────────────────────────────
#  Parámetros del orquestador
# ─────────────────────────────────────────────
ORCHESTRATOR_CONFIG = {
    "max_iterations":         int(os.getenv("NEXO_MAX_ITERATIONS", "5")),
    "max_replanning_cycles":  int(os.getenv("NEXO_MAX_REPLANNING", "2")),
    "coherence_threshold":    float(os.getenv("NEXO_COHERENCE_THRESHOLD", "0.6")),
    "timeout_seconds":        int(os.getenv("NEXO_SESSION_TIMEOUT", "300")),
}

# ─────────────────────────────────────────────
#  Base de datos
# ─────────────────────────────────────────────
DB_PATH = Path(os.getenv("NEXO_DB_PATH", str(Path(__file__).parent.parent / "nexo_data.db")))

# ─────────────────────────────────────────────
#  API
# ─────────────────────────────────────────────
API_HOST = os.getenv("NEXO_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("NEXO_API_PORT", "8000"))

# ─────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────
LOG_LEVEL = os.getenv("NEXO_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def get_provider_config(agent_role: str) -> dict[str, Any]:
    """Obtiene la configuración específica para un rol de agente con fallback."""
    cfg = PROVIDER_CONFIG.get(agent_role.upper())
    if cfg:
        return dict(cfg)
    return dict(PROVIDER_CONFIG.get("default", {"type": "mock"}))
