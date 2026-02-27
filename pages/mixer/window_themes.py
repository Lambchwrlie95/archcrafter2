"""Window Themes page - migrated from main.py."""

from pages.base import BasePage


class WindowThemesPage(BasePage):
    id = "window_themes"
    title = "Window Themes"
    icon = "window-new-symbolic"

    @staticmethod
    def get_sidebar_items():
        return []

    def build(self, app, builder):
        widget = builder.get_object("page_window_themes")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_window_themes()
