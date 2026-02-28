"""Cursor Themes page - migrated from main.py."""

from pages.base import BasePage
from pages import register_page


"""Compatibility shim for cursor themes section."""

from pages.sections.cursor_themes import CursorThemesPage  # noqa: F401
