"""GTK Themes page - migrated from main.py."""

from pages.base import BasePage
from pages import register_page


"""Compatibility shim for gtk themes section."""

from pages.sections.gtk_themes import GtkThemesPage  # noqa: F401
