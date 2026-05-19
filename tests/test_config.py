import pytest
import os
from src.common.config import Config, ConfigError

def test_config_branch_replacement_protection():
    config = Config()
    
    # Setup initial branch
    config.set("app.name", "orchestrator")
    config.set("app.port", 8080)
    
    # Attempting to override the "app" branch with a scalar string should fail
    with pytest.raises(ConfigError) as excinfo:
        config.set("app", "override")
        
    assert "Cannot replace dict branch" in str(excinfo.value)
    
    # Verify the branch wasn't destroyed
    assert config.get("app.name") == "orchestrator"

def test_config_scalar_traversal_protection():
    config = Config()
    
    # Setup initial scalar
    config.set("app", "test_app")
    
    # Attempting to traverse through the scalar should fail
    with pytest.raises(ConfigError) as excinfo:
        config.set("app.name", "override")
        
    assert "Cannot traverse scalar value" in str(excinfo.value)

def test_config_env_override_protection(monkeypatch):
    # Setup initial branch
    config = Config()
    config.set("app.name", "test")
    
    # Mock environment variable that would cause a conflict
    monkeypatch.setenv("AO_APP", "override")
    
    # Loading env overrides should trigger the protection
    with pytest.raises(ConfigError) as excinfo:
        config._load_env_overrides()
        
    assert "Cannot replace dict branch" in str(excinfo.value)
