import sys

with open("Makefile", "r") as f:
    content = f.read()

new_content = content.replace("docker build", "docker build --provenance=false")
if "audit-image:" not in new_content:
    new_content = new_content.replace("docker-down:\n\tdocker compose -f infra/docker-compose.yml down", "docker-down:\n\tdocker compose -f infra/docker-compose.yml down\n\naudit-image:\n\tbash scripts/audit_image_metadata.sh orchestration-agent:latest")

with open("Makefile", "w") as f:
    f.write(new_content)
