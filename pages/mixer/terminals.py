"""Terminals page - migrated from main.py."""

from pages.base import BasePage


class TerminalsPage(BasePage):
    id = "terminals"
    title = "Terminals"
    icon = "utilities-terminal-symbolic"

    @staticmethod
    def get_sidebar_items():
        return []

    def build(self, app, builder):
        widget = builder.get_object("page_terminals")
        self.widget = widget
        return widget
