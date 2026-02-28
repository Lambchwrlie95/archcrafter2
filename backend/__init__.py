"""ArchCrafter2 backend package."""

from .deps import detect_external_tools
from .fetch import FetchPreset, FetchService
from .gtk_themes import GtkThemeService
from .interface_themes import InterfaceThemeService
from .settings import SettingsStore
from .themes import WindowThemeService
from .wallpaper_names import WallpaperNameStore
from .wallpapers import WallpaperService
from .services import ServiceContainer

__all__ = [
    "SettingsStore",
    "FetchPreset",
    "FetchService",
    "WallpaperService",
    "WallpaperNameStore",
    "WindowThemeService",
    "GtkThemeService",
    "InterfaceThemeService",
    "ServiceContainer",
    "detect_external_tools",
]
