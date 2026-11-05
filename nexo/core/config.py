from typing import Dict, Any
from pydantic import BaseSettings

class ConfigManager:
    """Configuration management for NEXO MultiAgent system"""
    
    def __init__(self):
        self.environment = "development"
        self.max_iterations = 10
        self.provider_config = {
            "ANALYST": {"type": "ollama", "model": "gemma4:12b-mlx"},
            "EXECUTOR": {"type": "ollama", "model": "qwen2.5-coder:7b"},
            "STRATEGIST": {"type": "ollama", "model": "gemma4:12b-mlx"},
            "EVALUATOR": {"type": "ollama", "model": "gemma4:12b-mlx"},
            "orquestador": {"type": "ollama", "model": "gemma4:12b-mlx"}
        }
    
    @property
    def PROVIDER_CONFIG(self) -> Dict[str, Any]:
        return self.provider_config
    
    @property
    def MAX_ITERATIONS(self) -> int:
        return self.max_iterations
