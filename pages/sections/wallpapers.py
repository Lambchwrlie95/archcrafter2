"""Wallpapers section page (moved from pages/mixer)."""

from pages.base import BasePage
from pages import register_page


@register_page
class WallpaperPage(BasePage):
    id = "wallpapers"
    title = "Wallpapers"
    icon = "image-x-generic-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            (
                "wallpapers",
                "Wallpapers",
                "image-x-generic-symbolic",
                "Manage wallpapers",
            ),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_wallpapers")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_wallpapers()
        app.sync_wallpaper_controls_from_settings()
