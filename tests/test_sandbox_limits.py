import pytest
from src.agent.sandbox import ResourceLimits, ResourceLimitsError

def test_valid_resource_limits():
    limits = ResourceLimits(cpu_time=100, memory_mb=1024, disk_mb=500)
    assert limits.cpu_time == 100
    assert limits.memory_mb == 1024
    assert limits.disk_mb == 500

def test_string_conversion_resource_limits():
    limits = ResourceLimits(cpu_time="100", memory_mb="1024", disk_mb="500")
    assert limits.cpu_time == 100
    assert limits.memory_mb == 1024
    assert limits.disk_mb == 500

def test_negative_cpu_time():
    with pytest.raises(ResourceLimitsError) as exc:
        ResourceLimits(cpu_time=-1)
    assert "cpu_time must be positive" in str(exc.value)

def test_zero_memory():
    with pytest.raises(ResourceLimitsError) as exc:
        ResourceLimits(memory_mb=0)
    assert "memory_mb must be positive" in str(exc.value)

def test_negative_disk():
    with pytest.raises(ResourceLimitsError) as exc:
        ResourceLimits(disk_mb=-500)
    assert "disk_mb must be positive" in str(exc.value)

def test_invalid_type():
    with pytest.raises(ResourceLimitsError) as exc:
        ResourceLimits(cpu_time="invalid")
    assert "must be numeric" in str(exc.value)
