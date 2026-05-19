"""Configuration management module."""

import os
import json
from typing import Any, Dict, Optional


class ConfigError(Exception):
    """Raised when a configuration assignment violates safety policies."""
    pass


class Config:
    def __init__(self, config_path: Optional[str] = None):
        self._data: Dict[str, Any] = {}
        if config_path:
            self.load(config_path)
        self._load_env_overrides()

    def load(self, path: str) -> None:
        with open(path) as f:
            self._data = json.load(f)

    def _load_env_overrides(self) -> None:
        prefix = "AO_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower().replace("_", ".")
                self._set_nested(config_key, value)

    def _set_nested(self, key: str, value: Any) -> None:
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                raise ConfigError(f"Cannot traverse scalar value at '{part}' while setting '{key}'")
            current = current[part]
        
        last_part = parts[-1]
        
        # Fix for #12: Prevent scalar values from overwriting entire nested dict branches
        if last_part in current and isinstance(current[last_part], dict) and not isinstance(value, dict):
            raise ConfigError(f"Cannot replace dict branch '{last_part}' with scalar value")
            
        current[last_part] = value

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
