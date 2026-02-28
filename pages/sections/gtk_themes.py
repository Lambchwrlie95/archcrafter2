"""GTK Themes section page (moved from pages/mixer)."""

from pages.base import BasePage
from pages import register_page


@register_page
class GtkThemesPage(BasePage):
    id = "gtk_themes"
    title = "GTK Themes"
    icon = "preferences-desktop-theme-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            (
                "gtk_themes",
                "GTK Themes",
                "preferences-desktop-theme-symbolic",
                "GTK theme selection",
            ),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_gtk_themes")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_gtk_themes()
