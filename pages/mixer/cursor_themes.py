"""Cursor Themes page - migrated from main.py."""

from pages.base import BasePage


class CursorThemesPage(BasePage):
    id = "cursors"
    title = "Cursors"
    icon = "input-mouse-symbolic"

    @staticmethod
    def get_sidebar_items():
        return []

    def build(self, app, builder):
        widget = builder.get_object("page_cursor_themes")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_cursor_themes()
