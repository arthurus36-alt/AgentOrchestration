import re

with open("src/api/routes.py", "r") as f:
    content = f.read()

parts = re.split(r'(?=# 2019)', content, maxsplit=1)
tail = parts[1] if len(parts) > 1 else ""

with open("patch_batch_only.py", "r") as f:
    new_code = f.read()

with open("src/api/routes.py", "w") as f:
    f.write(new_code + "\n" + tail)
