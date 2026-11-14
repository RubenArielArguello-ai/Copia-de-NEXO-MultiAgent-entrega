from nexo.agents.executor import crear_agente_ejecutor
from nexo.core.orchestrator import Orchestrator
from nexo.core.state_manager import StateManager
from nexo.config import PROVIDER_CONFIG


def ejecutar_mision(objetivo_usuario: str, config_dict: dict):
    """Ejecuta una misión por el pipeline NEXO completo y devuelve su respuesta final."""
    result = ejecutar_mision_completa(objetivo_usuario, config_dict)
    return result.get("final_answer") or "La sesión terminó sin una respuesta final."


def ejecutar_mision_completa(objetivo_usuario: str, config_dict: dict) -> dict:
    """Ejecuta el pipeline completo y devuelve estado, respuesta y trazabilidad."""
    providers = {role: dict(cfg) for role, cfg in PROVIDER_CONFIG.items()}
    providers.update({role: dict(cfg) for role, cfg in config_dict.items()})
    manager = StateManager()
    session = manager.create_session(objetivo_usuario)
    return Orchestrator(manager, provider_config=providers).run(session.session_id)


def ejecutar_mision_directa(objetivo_usuario: str, config_dict: dict) -> str:
    """Ejecuta una tarea con las herramientas LangChain de archivos y Python."""
    executor = crear_agente_ejecutor(config_dict)
    result = executor.invoke({"input": objetivo_usuario})
    return str(result.get("output", ""))
