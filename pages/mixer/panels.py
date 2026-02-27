"""Panels page (polybar/tint2) - migrated from main.py."""

from pages.base import BasePage


class PanelsPage(BasePage):
    id = "panels"
    title = "Panels"
    icon = "transform-scale-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            ("panels", "Panels", "transform-scale-symbolic", "Polybar/Tint2 panels"),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_bar")
        self.widget = widget
        return widget

    def on_activate(self, app):
        app.refresh_bar_page_state()
        app._ensure_bar_preview_refresh(True)
