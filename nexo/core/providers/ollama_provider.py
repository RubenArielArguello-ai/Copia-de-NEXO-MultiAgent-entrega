import json
from typing import Dict, Any
from nexo.core.config import ConfigManager

class OllamaProvider:
    """Interface to Ollama LLM service"""
    
    def __init__(self):
        self.config = ConfigManager()
        
    async def generate_response(
        self,
        agent_id: str,
        model_name: str,
        prompt: str,
        context: Dict[str, Any] = {}
    ) -> str:
        """Generate response using the specified Ollama model"""
        # Mock implementation for testing purposes
        if not prompt:
            return ""
            
        # Simulando una llamada a Ollama
        # En un entorno real aquí iría la implementación real
        response = f"Simulated response from {model_name} for agent {agent_id}: {prompt[:50]}..."
        
        # Generar respuesta basada en el contexto del agente
        role_mapping = {
            "ANALYST": "Analista",
            "STRATEGIST": "Stratega",
            "EXECUTOR": "Ejecutor",
            "EVALUATOR": "Evaluador"
        }
        
        response += f"\n\nRole: {role_mapping.get(agent_id, 'Agente')} | Contexto: {context.get('mission', 'Sin misión')}"
        
        return response
        
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get information about a model"""
        return {
            "name": model_name,
            "type": "ollama",
            "status": "available"
        }
