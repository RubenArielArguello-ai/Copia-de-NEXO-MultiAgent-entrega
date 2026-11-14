import os
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI


def get_llm_for_role(role_name: str, config_dict: dict):
    """
    Lee la configuración de un rol específico y devuelve el modelo de lenguaje listo para usar.
    """
    # Buscamos la configuración del rol (ej. "EXECUTOR", "STRATEGIST")
    role_config = config_dict.get(role_name)

    if not role_config:
        raise ValueError(f"No se encontró configuración para el rol: {role_name}")

    provider_type = role_config.get("type")
    model_name = role_config.get("model")
    if not model_name:
        raise ValueError(f"No se especificó un modelo para el rol: {role_name}")

    # Si es un modelo local de Ollama (como Gemma o Qwen)
    if provider_type == "ollama":
        print(f"[*] Cargando modelo local Ollama: {model_name} para el rol {role_name}")
        return ChatOllama(
            model=model_name,
            temperature=0.0,  # Temperatura 0 para que sea más lógico y menos creativo
            base_url=role_config.get("base_url", os.getenv("OLLAMA_HOST", "http://localhost:11434")),
            client_kwargs={"timeout": role_config.get("timeout", 180)},
        )

    # Si es un modelo en la nube de OpenAI (como GPT)
    elif provider_type == "llm":
        print(f"[*] Cargando modelo OpenAI: {model_name} para el rol {role_name}")
        # Asegúrate de tener tu API KEY configurada en las variables de entorno de tu sistema
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY es obligatoria cuando el proveedor es 'llm'")
        return ChatOpenAI(model=model_name, temperature=0.0, api_key=api_key)

    else:
        raise ValueError(f"Proveedor desconocido: {provider_type}")
