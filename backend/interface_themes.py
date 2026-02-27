from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .settings import SettingsStore


@dataclass(frozen=True)
class InterfaceThemeEntry:
    name: str
    path: Path


class InterfaceThemeService:
    def __init__(self, base_dir: Path, settings: SettingsStore):
        self.base_dir = Path(base_dir)
        self.settings = settings
        self.system_dirs = [Path("/usr/share/icons")]
        self.user_dirs = [
            Path("~/.icons").expanduser(),
            Path("~/.local/share/icons").expanduser(),
        ]

    def _search_dirs(self) -> list[Path]:
        return [p for p in self.system_dirs + self.user_dirs if p.exists()]

    def _list_themes(self, require_cursors: bool) -> list[InterfaceThemeEntry]:
        found: dict[str, InterfaceThemeEntry] = {}
        for folder in self._search_dirs():
            try:
                entries = list(folder.iterdir())
            except Exception:
                continue

            for p in entries:
                if not p.is_dir():
                    continue
                if not (p / "index.theme").exists():
                    continue
                if require_cursors and not (p / "cursors").is_dir():
                    continue
                found[p.name] = InterfaceThemeEntry(name=p.name, path=p)

        return sorted(found.values(), key=lambda x: x.name.lower())

    def list_icon_themes(self) -> list[InterfaceThemeEntry]:
        return self._list_themes(require_cursors=False)

    def list_cursor_themes(self) -> list[InterfaceThemeEntry]:
        return self._list_themes(require_cursors=True)

    def _gsettings_get(self, key: str) -> str | None:
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", key],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                return None
            value = res.stdout.strip().strip("'")
            return value or None
        except Exception:
            return None

    def _gsettings_set(self, key: str, value: str) -> tuple[bool, str]:
        try:
            res = subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", key, value],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return True, ""
            error_text = (res.stderr or "").strip() or "gsettings set failed"
            return False, error_text
        except Exception as exc:
            return False, str(exc)

    def get_current_icon_theme(self) -> str | None:
        return self._gsettings_get("icon-theme")

    def get_current_cursor_theme(self) -> str | None:
        return self._gsettings_get("cursor-theme")

    def apply_icon_theme(self, theme_name: str) -> tuple[bool, str]:
        available = {t.name for t in self.list_icon_themes()}
        if theme_name not in available:
            return False, f"Icon theme not found: {theme_name}"
        ok, error = self._gsettings_set("icon-theme", theme_name)
        if ok:
            return True, f"Applied icon theme: {theme_name}"
        return False, f"Failed to apply icon theme: {error}"

    def apply_cursor_theme(self, theme_name: str) -> tuple[bool, str]:
        available = {t.name for t in self.list_cursor_themes()}
        if theme_name not in available:
            return False, f"Cursor theme not found: {theme_name}"
        ok, error = self._gsettings_set("cursor-theme", theme_name)
        if ok:
            return True, f"Applied cursor theme: {theme_name}"
        return False, f"Failed to apply cursor theme: {error}"
