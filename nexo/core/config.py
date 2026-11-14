"""Compatibilidad de configuración para el núcleo histórico de NEXO."""

from __future__ import annotations

import os
from typing import Any
from nexo.config import ORCHESTRATOR_CONFIG


PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "ANALYST": {"type": "ollama", "model": os.getenv("NEXO_MODEL_ANALYST", "qwen2.5-coder:7b")},
    "EXECUTOR": {"type": "ollama", "model": os.getenv("NEXO_MODEL_EXECUTOR", "qwen2.5-coder:7b")},
    "STRATEGIST": {"type": "ollama", "model": os.getenv("NEXO_MODEL_STRATEGIST", "qwen2.5-coder:7b")},
    "EVALUATOR": {"type": "ollama", "model": os.getenv("NEXO_MODEL_EVALUATOR", "qwen2.5-coder:7b")},
    "ORCHESTRATOR": {"type": "ollama", "model": os.getenv("NEXO_MODEL_ORCHESTRATOR", "qwen2.5-coder:7b")},
    # Alias conservado para consumidores antiguos.
    "orquestador": {"type": "ollama", "model": os.getenv("NEXO_MODEL_ORCHESTRATOR", "qwen2.5-coder:7b")},
}


class ConfigManager:
    """Configuración sencilla para compatibilidad con módulos anteriores."""

    def __init__(self):
        self.environment = os.getenv("NEXO_ENV", "development")
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")
        self.max_iterations = int(os.getenv("NEXO_MAX_ITERATIONS", str(ORCHESTRATOR_CONFIG["max_iterations"])))
        self.provider_config = {key: dict(value) for key, value in PROVIDER_CONFIG.items()}

    @property
    def PROVIDER_CONFIG(self) -> dict[str, dict[str, Any]]:
        return self.provider_config

    @property
    def MAX_ITERATIONS(self) -> int:
        return self.max_iterations

    def get_provider_config(self, provider_name: str) -> dict[str, Any]:
        key = provider_name.upper()
        if key not in self.provider_config and provider_name.lower() == "orquestador":
            key = "ORCHESTRATOR"
        if key not in self.provider_config:
            raise KeyError(f"Proveedor desconocido: {provider_name}")
        return dict(self.provider_config[key])

    def get_environment_variable(self, name: str) -> str | None:
        return os.getenv(name)
