"""Window Themes section page (moved from pages/mixer)."""

from pages.base import BasePage
from pages import register_page


@register_page
class WindowThemesPage(BasePage):
    id = "window_themes"
    title = "Window Themes"
    icon = "window-new-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            ("window_themes", "Window Themes", "window-new-symbolic", "Openbox themes"),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_window_themes")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_window_themes()
