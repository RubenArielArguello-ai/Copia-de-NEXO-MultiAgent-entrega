def test_provider_configuration():
    """Test basic configuration loading"""
    from nexo.core.config import PROVIDER_CONFIG
    
    # Verificar existencia de configuraciones básicas
    required_agents = ["ANALYST", "EXECUTOR", "STRATEGIST", "EVALUATOR"]
    
    for agent in required_agents:
        assert agent in PROVIDER_CONFIG, f"Configuración del agente {agent} no encontrada"
        
    # Verificar tipos de proveedores
    assert all(isinstance(conf["type"], str) for conf in PROVIDER_CONFIG.values()), "Todos los proveedores deben tener un tipo de modelo"
    
    # Verificar formatos esperados
    for agent, config in PROVIDER_CONFIG.items():
        assert "model" in config, f"Configuración del agente {agent} no tiene modelo definido"

def test_provider_types():
    """Test provider configuration types"""
    from nexo.core.config import PROVIDER_CONFIG
    
    required_types = {
        "ANALYST": "ollama",
        "EXECUTOR": "ollama",
        "STRATEGIST": "ollama",
        "EVALUATOR": "ollama"
    }
    
    for agent, expected_type in required_types.items():
        assert PROVIDER_CONFIG[agent]["type"] == expected_type, f"El tipo del proveedor {agent} no coincide con {expected_type}"

def test_environment_variables():
    """Test environment variables loading"""
    from nexo.core.config import ConfigManager
    
    config = ConfigManager()
    assert config.environment == "development", "Configuración del entorno no es development por defecto"
    
def test_default_values():
    """Test default values validation"""
    from nexo.core.config import ConfigManager
    
    config = ConfigManager()
    assert config.max_iterations == 10, "El valor default de max_iterations debe ser 10"

def test_orquestador_model():
    """Test orquestador model configuration"""
    from nexo.core.config import PROVIDER_CONFIG
    
    assert "orquestador" in PROVIDER_CONFIG, "Configuración del Orquestador no encontrada"
    assert PROVIDER_CONFIG["orquestador"]["model"] == "gemma4:12b-mlx", "Modelo del Orquestador no coincide con el esperado"

def test_required_fields():
    """Test required fields in provider configurations"""
    from nexo.core.config import PROVIDER_CONFIG
    
    required_fields = ["type", "model"]
    
    for agent, config in PROVIDER_CONFIG.items():
        assert all(field in config for field in required_fields), f"Falta campo obligatorio en configuración de {agent}"
