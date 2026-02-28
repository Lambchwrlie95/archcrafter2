"""Fetch section page (moved from pages/mixer)."""

from pages.base import BasePage
from pages import register_page


@register_page
class FetchPage(BasePage):
    id = "fetch"
    title = "Fetch"
    icon = "system-information-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            ("fetch", "Fetch", "system-information-symbolic", "System fetch tools"),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_fetch")
        self.widget = widget
        return widget
