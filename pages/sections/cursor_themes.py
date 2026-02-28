"""Cursor Themes section page (moved from pages/mixer)."""

from pages.base import BasePage
from pages import register_page


@register_page
class CursorThemesPage(BasePage):
    id = "cursors"
    title = "Cursors"
    icon = "input-mouse-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            ("cursors", "Cursors", "input-mouse-symbolic", "Cursor theme selection"),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_cursor_themes")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_cursor_themes()
