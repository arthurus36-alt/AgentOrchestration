import pytest
import subprocess
from unittest.mock import Mock, patch
from src.agent.runtime import AgentRuntime, RuntimeState
from src.agent.sandbox import AgentSandbox

def test_enforce_deterministic_cleanup_on_stop():
    sandbox_mock = Mock(spec=AgentSandbox)
    runtime = AgentRuntime(sandbox_manager=sandbox_mock)
    
    with patch('subprocess.Popen') as popen_mock:
        proc_mock = Mock()
        proc_mock.poll.return_value = None
        popen_mock.return_value = proc_mock
        
        # Start
        assert runtime.start("test_agent", ["sleep", "10"])
        assert runtime.is_running("test_agent")
        
        # Stop
        # Don't mock poll() immediately since stop() checks `proc.poll() is not None` to short-circuit
        assert runtime.stop("test_agent")
        
        # Verify deterministic cleanup is called!
        sandbox_mock.destroy.assert_called_once_with("test_agent")

def test_enforce_deterministic_cleanup_on_crash():
    sandbox_mock = Mock(spec=AgentSandbox)
    runtime = AgentRuntime(sandbox_manager=sandbox_mock)
    
    with patch('subprocess.Popen') as popen_mock:
        popen_mock.side_effect = Exception("Simulated crash")
        
        # Start throws
        assert runtime.start("test_crash", ["sleep", "10"]) is False
        assert runtime.get_state("test_crash") == RuntimeState.CRASHED
        
        # Verify deterministic cleanup is called!
        sandbox_mock.destroy.assert_called_once_with("test_crash")
