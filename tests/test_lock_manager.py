import pytest
from src.orchestrator.lock_manager import LockManager

def test_lock_manager_releases_on_exception():
    manager = LockManager()
    
    with pytest.raises(ValueError, match="Test error"):
        with manager.advisory_lock("test_lock"):
            assert "test_lock" in manager._locks
            raise ValueError("Test error")
            
    assert "test_lock" not in manager._locks
    
def test_lock_manager_acquires_and_releases():
    manager = LockManager()
    with manager.advisory_lock("test_lock_2"):
        assert "test_lock_2" in manager._locks
    assert "test_lock_2" not in manager._locks
