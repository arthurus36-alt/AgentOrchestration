import sys

skip = False
with open("../pr64.diff", "r") as f:
    for line in f:
        if line.startswith("diff --git a/src/agent/__init__.py") or line.startswith("diff --git a/src/common/metrics.py") or line.startswith("diff --git a/src/orchestrator/__init__.py"):
            skip = True
        elif skip and line.startswith("diff --git"):
            skip = False
            
        if not skip:
            sys.stdout.write(line)
