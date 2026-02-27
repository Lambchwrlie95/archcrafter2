"""Terminals page - migrated from main.py."""

from pages.base import BasePage


class TerminalsPage(BasePage):
    id = "terminals"
    title = "Terminals"
    icon = "utilities-terminal-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            (
                "terminals",
                "Terminals",
                "utilities-terminal-symbolic",
                "Terminal presets",
            ),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_terminals")
        self.widget = widget
        return widget
