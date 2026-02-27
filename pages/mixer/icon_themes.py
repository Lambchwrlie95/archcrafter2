"""Icon Themes page - migrated from main.py."""

from pages.base import BasePage


class IconThemesPage(BasePage):
    id = "icons"
    title = "Icons"
    icon = "preferences-desktop-icons-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            (
                "icons",
                "Icons",
                "preferences-desktop-icons-symbolic",
                "Icon theme selection",
            ),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_icon_themes")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_icon_themes()
