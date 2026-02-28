"""Builder Home section page (moved from pages/builder)."""

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from pages import register_page
from pages.base import BasePage


@register_page
class BuilderHomePage(BasePage):
    id = "builder_home"
    title = "Builder Home"
    icon = "applications-development-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            (
                "builder_home",
                "Builder Home",
                "applications-development-symbolic",
                "Build and organize module structure",
            ),
            (
                "builder_layout",
                "Layout",
                "view-list-symbolic",
                "Arrange containers and spacing",
            ),
            (
                "builder_widgets",
                "Widgets",
                "insert-object-symbolic",
                "Manage widget templates and IDs",
            ),
            (
                "builder_signals",
                "Signals",
                "network-transmit-receive-symbolic",
                "Wire and review signal handlers",
            ),
            (
                "builder_assets",
                "Assets",
                "folder-symbolic",
                "Review assets and integration points",
            ),
            (
                "builder_menus",
                "Menus",
                "ac-jgmenu-symbolic",
                "Build and customize launcher/menu presets",
            ),
        ]

    def build(self, app, builder):
        # Try to get from Glade, but create placeholder if not found (builder UI not yet implemented)
        widget = builder.get_object("page_builder_home")
        if widget is None:
            widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            label = Gtk.Label(label="Builder mode not yet implemented")
            widget.pack_start(label, True, True, 0)
            widget.show_all()
        self.widget = widget
        return widget
