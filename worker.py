from nexo.core.orquestador import ejecutar_mision_completa


def iniciar_trabajo_autonomo(objetivo_principal: str, config_dict: dict):
    """Legacy worker routed through the single mission orchestrator."""
    print(f"🚀 [WORKER] Misión coordinada por Orchestrator: {objetivo_principal}")
    result = ejecutar_mision_completa(objetivo_principal, config_dict)
    print(f"Estado: {result.get('status')} | Aprobada: {result.get('approved')}")
    print(result.get("final_answer", "Sin resultado final"))
    return result


# --- PRUEBA DE FUEGO ---
if __name__ == "__main__":
    config = {"EXECUTOR": {"type": "ollama", "model": "qwen2.5-coder:7b"}}

    mision = "Diagnostica los recursos del sistema y su conectividad de red, respaldando el resumen con evidencias reales."

    iniciar_trabajo_autonomo(mision, config)
