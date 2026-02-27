"""Wallpaper page - migrated from main.py."""

from pages.base import BasePage


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
            (
                "gtk_themes",
                "GTK Themes",
                "preferences-desktop-theme-symbolic",
                "GTK theme selection",
            ),
            ("window_themes", "Window Themes", "window-new-symbolic", "Openbox themes"),
            (
                "icons",
                "Icons",
                "preferences-desktop-icons-symbolic",
                "Icon theme selection",
            ),
            ("cursors", "Cursors", "input-mouse-symbolic", "Cursor theme selection"),
            ("panels", "Panels", "transform-scale-symbolic", "Polybar/Tint2 panels"),
            ("menu", "Menu", "ac-jgmenu-symbolic", "jgmenu configuration"),
            (
                "terminals",
                "Terminals",
                "utilities-terminal-symbolic",
                "Terminal presets",
            ),
            ("fetch", "Fetch", "system-information-symbolic", "System fetch tools"),
            ("more", "More", "view-more-symbolic", "Additional tools"),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_wallpapers")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.reload_wallpapers()
        app.sync_wallpaper_controls_from_settings()
