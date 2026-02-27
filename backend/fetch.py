from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FetchPreset:
    engine: str
    name: str
    path: Path


class FetchService:
    def __init__(self, base_dir: Path, settings: object):
        self.base_dir = Path(base_dir)
        self.settings = settings

    def list_presets(self, engine: str) -> list[FetchPreset]:
        if not self._is_safe_engine_name(engine):
            return []

        root = self.base_dir / "library" / "fetch" / engine
        if not root.is_dir():
            return []

        exts: set[str] = {".json", ".jsonc"} if engine == "fastfetch" else {".conf"}

        presets: list[FetchPreset] = []
        try:
            paths = sorted(root.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            return []

        for path in paths:
            try:
                if not path.is_file():
                    continue
                suffix = path.suffix.lower()
            except OSError:
                continue
            if suffix not in exts:
                continue
            presets.append(FetchPreset(engine=engine, name=path.stem, path=path))

        return presets

    @staticmethod
    def _is_safe_engine_name(engine: str) -> bool:
        if not engine or engine in {".", ".."}:
            return False

        candidate = Path(engine)
        if candidate.is_absolute():
            return False

        if "/" in engine or "\\" in engine:
            return False

        return candidate.name == engine

    def get_fetch_section(self) -> dict[str, object]:
        return self.settings.get_section(
            "fetch",
            default={
                "engine": "fastfetch",
                "preset_dirs": [],
                "default_preset": "",
                "search_text": "",
                "auto_refresh": True,
            },
        )
