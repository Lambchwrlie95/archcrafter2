"""Builder Home page - migrated from main.py."""

from pages.base import BasePage


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
        widget = builder.get_object("page_builder_home")
        self.widget = widget
        return widget
