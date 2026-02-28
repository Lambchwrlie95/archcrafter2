"""Menu section page (moved from pages/mixer)."""

from pages.base import BasePage
from pages import register_page


@register_page
class MenuPage(BasePage):
    id = "menu"
    title = "Menu"
    icon = "ac-jgmenu-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            ("menu", "Menu", "ac-jgmenu-symbolic", "jgmenu configuration"),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_menu")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_menu_presets()
        app._ensure_bar_preview_refresh(False)
