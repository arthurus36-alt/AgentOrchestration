import pytest
import os
from src.agent.registry import AgentRegistry, RegistryError

def test_handler_name_path_traversal():
    registry = AgentRegistry()
    agent_id = registry.register("test", "test.type")
    
    with pytest.raises(RegistryError) as excinfo:
        registry.save_plugin_metadata(agent_id, "../../../etc/passwd", {"malicious": True})
        
    assert "path traversal attempt detected" in str(excinfo.value)
    
def test_handler_name_absolute_path():
    registry = AgentRegistry()
    agent_id = registry.register("test", "test.type")
    
    with pytest.raises(RegistryError) as excinfo:
        registry.load_plugin_metadata(agent_id, "/etc/shadow")
        
    assert "path traversal attempt detected" in str(excinfo.value)
    
def test_valid_handler_metadata_lifecycle():
    registry = AgentRegistry()
    agent_id = registry.register("test", "test.type")
    
    # Save valid metadata
    assert registry.save_plugin_metadata(agent_id, "valid_handler_name", {"config": 123}) == True
    
    # Load valid metadata
    data = registry.load_plugin_metadata(agent_id, "valid_handler_name")
    assert data["config"] == 123
    
    # Verify cleanup on delete
    registry.delete(agent_id)
    assert not (registry.metadata_root / agent_id).exists()
