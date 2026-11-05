def test_provider_configuration():
    """Test basic configuration loading"""
    from nexo.core.config import PROVIDER_CONFIG
    
    assert "ANALYST" in PROVIDER_CONFIG
    assert "EXECUTOR" in PROVIDER_CONFIG
    assert all(isinstance(conf["type"], str) for conf in PROVIDER_CONFIG.values())
