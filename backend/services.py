from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .deps import detect_external_tools
from .fetch import FetchService
from .gtk_themes import GtkThemeService
from .interface_themes import InterfaceThemeService
from .settings import SettingsStore
from .themes import WindowThemeService
from .wallpapers import WallpaperService


class ServiceContainer:
    """Lightweight container holding service instances.

    Services are created once and may be accessed by attribute (e.g.
    ``container.wallpapers``) or dictionary lookup.
    """

    def __init__(self, base_dir: Path, settings_file: Path):
        self.base_dir = Path(base_dir)
        self.settings_file = Path(settings_file)
        self.settings = SettingsStore(self.settings_file)
        self.wallpapers = WallpaperService(self.base_dir, self.settings)
        self.gtk_themes = GtkThemeService(self.base_dir, self.settings)
        self.window_themes = WindowThemeService(self.base_dir, self.settings)
        self.interface_themes = InterfaceThemeService(self.base_dir, self.settings)
        self.fetch = FetchService(self.base_dir, self.settings)
        self.external_tools = detect_external_tools()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "settings": self.settings,
            "wallpapers": self.wallpapers,
            "gtk_themes": self.gtk_themes,
            "window_themes": self.window_themes,
            "interface_themes": self.interface_themes,
            "fetch": self.fetch,
            "external_tools": self.external_tools,
        }
