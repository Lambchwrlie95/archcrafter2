"""Icon Themes page - migrated from main.py."""

from pages.base import BasePage
from pages import register_page


"""Compatibility shim for icon themes section."""

from pages.sections.icon_themes import IconThemesPage  # noqa: F401
