"""Terminals page - migrated from main.py."""

from pages.base import BasePage
from pages import register_page


"""Compatibility shim for terminals section."""

from pages.sections.terminals import TerminalsPage  # noqa: F401
