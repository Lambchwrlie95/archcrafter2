"""ArchCrafter2 backend package."""

from .deps import detect_external_tools
from .gtk_themes import GtkThemeService
from .interface_themes import InterfaceThemeService
from .settings import SettingsStore
from .themes import WindowThemeService
from .wallpaper_names import WallpaperNameStore
from .wallpapers import WallpaperService

__all__ = [
    "SettingsStore",
    "WallpaperService",
    "WallpaperNameStore",
    "WindowThemeService",
    "GtkThemeService",
    "InterfaceThemeService",
    "detect_external_tools",
]
