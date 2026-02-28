"""Window Themes page - migrated from main.py."""

from pages.base import BasePage
from pages import register_page


"""Compatibility shim for window themes section."""

from pages.sections.window_themes import WindowThemesPage  # noqa: F401
