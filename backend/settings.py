from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SettingsStore:
    def __init__(self, settings_file: Path):
        self.settings_file = Path(settings_file)
        self.data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if not self.settings_file.exists():
            self.data = {}
            return
        try:
            self.data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            if not isinstance(self.data, dict):
                self.data = {}
        except Exception:
            self.data = {}

    def save(self) -> None:
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def get_section(self, key: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        value = self.data.get(key)
        if not isinstance(value, dict):
            value = dict(default or {})
            self.data[key] = value
        return value
