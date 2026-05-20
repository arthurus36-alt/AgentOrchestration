import re

with open("src/orchestrator/__init__.py", "r") as f:
    content = f.read()

parts = re.split(r'(?=# 2019)', content, maxsplit=1)
tail = parts[1] if len(parts) > 1 else ""

new_code = """\"\"\"Orchestration engine module.\"\"\"

from .engine import OrchestrationEngine
from .scheduler import TaskScheduler
from .workflow import WorkflowManager
from .webhooks import WebhookDeliveryService, WebhookEndpoint, WebhookDeliveryRecord

__all__ = ["OrchestrationEngine", "TaskScheduler", "WorkflowManager", "WebhookDeliveryService", "WebhookEndpoint", "WebhookDeliveryRecord"]
"""

with open("src/orchestrator/__init__.py", "w") as f:
    f.write(new_code + "\n" + tail)
