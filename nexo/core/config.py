from typing import Dict, Any
from pydantic_settings import BaseSettings

from typing import Dict, Any, Optional
import os

class ConfigManager:
    """Configuration management for NEXO MultiAgent system"""
    
    def __init__(self):
        self.environment = os.getenv("NEXO_ENV", "development")
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")
        
    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """Get configuration for a specific provider"""
        return self.PROVIDER_CONFIG[provider_name]
    
    @property
    def PROVIDER_CONFIG(self) -> Dict[str, Any]:
        """Provider configurations"""
        if not hasattr(self, "_PROVIDER_CONFIG"):
            self._PROVIDER_CONFIG = {
                "ANALYST": {"type": "ollama", "model": "gemma4:12b-mlx"},
                "EXECUTOR": {"type": "ollama", "model": "qwen2.5-coder:7b"},
                "STRATEGIST": {"type": "ollama", "model": "gemma4:12b-mlx"},
                "EVALUATOR": {"type": "ollama", "model": "gemma4:12b-mlx"},
                "orquestador": {"type": "llm", "model": "gpt-3.5-turbo"}
            }
        return self._PROVIDER_CONFIG
    
    def get_environment_variable(self, name: str) -> Optional[str]:
        """Get environment variable safely"""
        return os.getenv(name)
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
