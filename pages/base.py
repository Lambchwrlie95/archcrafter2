from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from gi.repository import Gtk


class BasePage(ABC):
    """Abstract base class for all pages."""

    id: str = ""
    title: str = ""
    icon: str = ""

    _widget: Optional["Gtk.Widget"] = None

    @staticmethod
    def get_sidebar_items():
        """Returns list of sidebar items: [(row_id, title, icon, description), ...]"""
        return []

    def build(self, app, builder) -> "Gtk.Widget":
        """Build and return the page widget."""
        raise NotImplementedError

    def on_activate(self, app):
        """Called when page becomes visible."""
        pass

    def on_deactivate(self, app):
        """Called when page is hidden."""
        pass

    @property
    def widget(self) -> Optional["Gtk.Widget"]:
        return self._widget

    @widget.setter
    def widget(self, value: "Gtk.Widget"):
        self._widget = value
