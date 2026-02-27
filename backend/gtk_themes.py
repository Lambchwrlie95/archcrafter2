from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .settings import SettingsStore


@dataclass(frozen=True)
class GtkThemeEntry:
    name: str
    path: Path


class GtkThemeService:
    def __init__(self, base_dir: Path, settings: SettingsStore):
        self.base_dir = Path(base_dir)
        self.settings = settings
        self.system_dirs = [Path("/usr/share/themes")]
        self.user_dirs = [
            Path("~/.themes").expanduser(),
            Path("~/.local/share/themes").expanduser(),
        ]

    def list_themes(self) -> list[GtkThemeEntry]:
        found: dict[str, GtkThemeEntry] = {}
        search_paths = [p for p in self.system_dirs + self.user_dirs if p.exists()]

        for folder in search_paths:
            try:
                entries = list(folder.iterdir())
            except Exception:
                continue

            for p in entries:
                if not p.is_dir():
                    continue
                # GTK3 app: prioritize themes that provide GTK3 assets.
                if (p / "gtk-3.0").exists() or (p / "gtk-2.0").exists():
                    found[p.name] = GtkThemeEntry(name=p.name, path=p)

        return sorted(found.values(), key=lambda x: x.name.lower())

    def get_current_theme(self) -> str | None:
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                value = res.stdout.strip().strip("'")
                return value or None
        except Exception:
            pass
        return None

    def apply_theme(self, theme_name: str) -> tuple[bool, str]:
        available = {t.name for t in self.list_themes()}
        if theme_name not in available:
            return False, f"Theme not found: {theme_name}"

        try:
            res = subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", theme_name],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return True, f"Applied GTK theme: {theme_name}"

            error_text = (res.stderr or "").strip() or "gsettings set failed"
            return False, f"Failed to apply GTK theme: {error_text}"
        except Exception as exc:
            return False, f"Failed to apply GTK theme: {exc}"
