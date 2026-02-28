"""Grouped exports for `pages.sections`.

This module re-exports the individual section page classes and provides a
`SECTIONS` mapping and `ALL_PAGES` list to make it easy to consume sections
from other parts of the application.
"""

from pages.sections.wallpapers import WallpaperPage
from pages.sections.fetch import FetchPage
from pages.sections.gtk_themes import GtkThemesPage
from pages.sections.window_themes import WindowThemesPage
from pages.sections.icon_themes import IconThemesPage
from pages.sections.cursor_themes import CursorThemesPage
from pages.sections.panels import PanelsPage
from pages.sections.menu import MenuPage
from pages.sections.terminals import TerminalsPage
from pages.sections.more import MorePage

__all__ = [
    "WallpaperPage",
    "FetchPage",
    "GtkThemesPage",
    "WindowThemesPage",
    "IconThemesPage",
    "CursorThemesPage",
    "PanelsPage",
    "MenuPage",
    "TerminalsPage",
    "MorePage",
    "SECTIONS",
    "ALL_PAGES",
]

SECTIONS = {
    "wallpapers": WallpaperPage,
    "fetch": FetchPage,
    "gtk_themes": GtkThemesPage,
    "window_themes": WindowThemesPage,
    "icons": IconThemesPage,
    "cursors": CursorThemesPage,
    "panels": PanelsPage,
    "menu": MenuPage,
    "terminals": TerminalsPage,
    "more": MorePage,
}

ALL_PAGES = list(SECTIONS.values())


def get_section(page_id: str):
    """Return the page class for `page_id`, or `None` if not found."""
    return SECTIONS.get(page_id)
