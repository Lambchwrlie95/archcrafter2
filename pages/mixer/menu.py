"""Menu page (jgmenu) - migrated from main.py."""

from pages.base import BasePage


class MenuPage(BasePage):
    id = "menu"
    title = "Menu"
    icon = "ac-jgmenu-symbolic"

    @staticmethod
    def get_sidebar_items():
        return []

    def build(self, app, builder):
        widget = builder.get_object("page_menu")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_menu_presets()
        app._ensure_bar_preview_refresh(False)
