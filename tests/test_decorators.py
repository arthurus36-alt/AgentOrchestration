import pytest
from src.sdk.decorators import task, agent, on_event
import asyncio

def test_task_decorator_invalid_timeout():
    with pytest.raises(ValueError) as exc:
        @task(timeout=0)
        async def my_task():
            pass
    assert "positive number" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        @task(timeout=-5)
        async def my_negative_task():
            pass
    assert "positive number" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        @task(timeout="hello")
        async def my_string_task():
            pass
    assert "positive number" in str(exc.value)

@pytest.mark.asyncio
async def test_task_decorator_valid():
    @task(timeout=10)
    async def valid_task():
        return "success"
    
    assert valid_task.__task_config__["timeout"] == 10
    assert await valid_task() == "success"
