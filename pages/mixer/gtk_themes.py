"""GTK Themes page - migrated from main.py."""

from pages.base import BasePage


class GtkThemesPage(BasePage):
    id = "gtk_themes"
    title = "GTK Themes"
    icon = "preferences-desktop-theme-symbolic"

    @staticmethod
    def get_sidebar_items():
        return []

    def build(self, app, builder):
        widget = builder.get_object("page_gtk_themes")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_gtk_themes()
