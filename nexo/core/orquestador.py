from typing import Dict, Any, Optional
from nexo.core.config import ConfigManager

class ConfigManagerSingleton:
    _instance = None

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = ConfigManager()
        return cls._instance
from nexo.core.schemas.messages import (
    AgentMessage,
    OrquestradorCommand,
    StatusUpdate
)

class Orquestador:
    """Main coordinator agent managing the cognitive process"""
    
    def __init__(self):
        self.config = ConfigManagerSingleton.getInstance()
        self.agent_status: Dict[str, str] = {}
        self.current_mission: str = ""
        self.iteration_count = 0
        self.max_iterations = self.config.get_provider_config("orquestador").get("temperature", 1.0)
        
    def start_mission(self, mission: str) -> None:
        """Initialize and distribute the mission to all agents"""
        self.current_mission = mission
        self.iteration_count = 0
        self.agent_status = {agent: "idle" for agent in PROVIDER_CONFIG.keys()}
        
        # Obtener todos los agentes disponibles
        agents = [agent for agent in self.config.PROVIDER_CONFIG.keys() if agent != "orquestador"]
        
        # Distribuir órdenes iniciales basadas en los roles
        for agent in agents:
            role = agent.replace("AGENT_", "").lower()
            command_data = {
                "mission": mission,
                "role": role,
                "model_settings": self.config.get_provider_config(agent).get("model_settings", {})
            }
            
            self.send_command(OrquestradorCommand(
                to=agent,
                action="initiate",
                data=command_data
            ))
    
    def send_command(self, command: OrquestradorCommand) -> None:
        """Send a command to a specific agent"""
        # TODO: Implement actual communication channel
        pass
    
    def update_status(self, status_update: StatusUpdate) -> None:
        """Receive and process status updates from agents"""
        self.agent_status[status_update.from_agent] = status_update.status
        
        # Check for stalled agents
        if status_update.status == "stalled":
            if status_update.details:
                # TODO: Implement recovery logic
                pass
                
    def get_agent_state(self, agent_id: str) -> Dict[str, Any]:
        """Return detailed state of an agent"""
        return {
            "status": self.agent_status[agent_id],
            "current_mission": self.current_mission,
            "iteration_count": self.iteration_count
        }
