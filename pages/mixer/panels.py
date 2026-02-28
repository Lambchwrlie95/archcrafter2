"""Panels page (polybar/tint2) - migrated from main.py."""

from pages.base import BasePage
from pages import register_page


"""Compatibility shim for panels section."""

from pages.sections.panels import PanelsPage  # noqa: F401
