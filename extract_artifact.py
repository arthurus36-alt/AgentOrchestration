import sys

skip = False
with open("../pr109.diff", "r") as f:
    for line in f:
        if line.startswith("diff --git a/src/agent/__init__.py") or line.startswith("diff --git a/src/common/metrics.py"):
            skip = True
        elif skip and line.startswith("diff --git"):
            skip = False
            
        if not skip:
            sys.stdout.write(line)
