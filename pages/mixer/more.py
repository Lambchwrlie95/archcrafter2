"""More page - migrated from main.py."""

from pages.base import BasePage


class MorePage(BasePage):
    id = "more"
    title = "More"
    icon = "view-more-symbolic"

    @staticmethod
    def get_sidebar_items():
        return []

    def build(self, app, builder):
        widget = builder.get_object("page_more")
        self.widget = widget
        return widget
