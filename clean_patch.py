import sys

lines = []
skip = False
with open("../pr115.diff", "r") as f:
    for line in f:
        if line.startswith("diff --git a/src/agent/__init__.py"):
            skip = True
        elif skip and line.startswith("diff --git"):
            skip = False
            
        if not skip:
            lines.append(line)

with open("../pr115_clean.diff", "w") as f:
    f.writelines(lines)
