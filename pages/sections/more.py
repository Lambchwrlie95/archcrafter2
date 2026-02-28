"""More section page (moved from pages/mixer)."""

from pages.base import BasePage
from pages import register_page


@register_page
class MorePage(BasePage):
    id = "more"
    title = "More"
    icon = "view-more-symbolic"

    @staticmethod
    def get_sidebar_items():
        return [
            ("more", "More", "view-more-symbolic", "Additional tools"),
        ]

    def build(self, app, builder):
        widget = builder.get_object("page_more")
        self.widget = widget
        return widget
