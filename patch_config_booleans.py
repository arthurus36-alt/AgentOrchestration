import re

with open("src/common/config.py", "r") as f:
    content = f.read()

parts = re.split(r'(?=# 2019)', content, maxsplit=1)
tail = parts[1] if len(parts) > 1 else ""

new_code = """\"\"\"Configuration management module.\"\"\"

import os
import json
from json import JSONDecodeError
from typing import Any, Dict, Optional

from src.common.errors import ConfigurationError

class Config:
    def __init__(self, config_path: Optional[str] = None):
        self._data: Dict[str, Any] = {}
        if config_path:
            self.load(config_path)
        self._load_env_overrides()

    def load(self, path: str) -> None:
        try:
            with open(path) as f:
                self._data = json.load(f)
        except JSONDecodeError as exc:
            raise ConfigurationError(
                f"failed to parse JSON config file '{path}' at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc

    def _coerce_value(self, value: str) -> Any:
        lower = value.lower()
        if lower == "true":
            return True
        elif lower == "false":
            return False
        return value

    def _load_env_overrides(self) -> None:
        prefix = "AO_"
        mapped_keys = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower().replace("_", ".")
                if config_key in mapped_keys:
                    raise ValueError(f"Case collision detected for env overrides: '{mapped_keys[config_key]}' and '{key}' both map to '{config_key}'")
                mapped_keys[config_key] = key
                self._set_nested(config_key, self._coerce_value(value))

    def _set_nested(self, key: str, value: Any) -> None:
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return default
            else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
        self._set_nested(key, value)

    def to_dict(self) -> Dict:
        return self._data
"""

with open("src/common/config.py", "w") as f:
    f.write(new_code + "\n" + tail)
