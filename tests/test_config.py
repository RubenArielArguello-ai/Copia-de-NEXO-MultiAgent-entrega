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

# NUEVO TEST PARA ENTorno DE DESARrollo
def test_environment_variables():
    """Test environment variables loading"""
    from nexo.core.config import ConfigManager
    
    config = ConfigManager()
    assert config.environment == "development", "Configuración del entorno no es development por defecto"
    
# NUEVO TEST PARA DEFAULTS
def test_default_values():
    """Test default values validation"""
    from nexo.core.config import ConfigManager
    
    config = ConfigManager()
    assert config.max_iterations == 10, "El valor default de max_iterations debe ser 10"
