from __future__ import annotations

from pathlib import Path

from .settings import SettingsStore


class WallpaperNameStore:
    """Persistent display-name overrides for wallpapers."""

    def __init__(self, settings: SettingsStore):
        self.settings = settings

    def _section(self) -> dict:
        return self.settings.get_section("wallpapers", default={})

    def _overrides(self) -> dict[str, str]:
        section = self._section()
        value = section.get("name_overrides", {})
        if not isinstance(value, dict):
            value = {}
            section["name_overrides"] = value
        return value

    def _key(self, path: Path) -> str:
        p = Path(path).expanduser()
        try:
            return str(p.resolve())
        except Exception:
            return str(p.absolute())

    def get(self, path: Path, fallback: str) -> str:
        key = self._key(path)
        value = self._overrides().get(key)
        if isinstance(value, str):
            cleaned = " ".join(value.split()).strip()
            if cleaned:
                return cleaned
        return fallback

    def set(self, path: Path, name: str | None) -> str:
        key = self._key(path)
        overrides = self._overrides()

        cleaned = ""
        if isinstance(name, str):
            cleaned = " ".join(name.split()).strip()

        if cleaned:
            overrides[key] = cleaned
        else:
            overrides.pop(key, None)

        self.settings.save()
        return cleaned

    def remove(self, path: Path) -> None:
        key = self._key(path)
        overrides = self._overrides()
        if key in overrides:
            overrides.pop(key, None)
            self.settings.save()
