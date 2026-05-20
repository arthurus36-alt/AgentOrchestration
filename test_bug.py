from src.orchestrator.scheduler import TaskScheduler
import asyncio

async def main():
    s = TaskScheduler()
    s.schedule({"a": 1}, delay=0)
    await s.dequeue()

asyncio.run(main())
