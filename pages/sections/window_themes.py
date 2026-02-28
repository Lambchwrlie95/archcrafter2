"""Window Themes section page (moved from pages/mixer)."""

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from pages import register_page
from pages.base import BasePage


@register_page
class WindowThemesPage(BasePage):
    id = "window_themes"
    title = "Window Themes"
    icon = "window-new-symbolic"

    def __init__(self):
        super().__init__()
        self.flowbox_window_themes = None
        self.entry_window_themes_search = None
        self.current_theme_name = None

    @staticmethod
    def get_sidebar_items():
        return [
            (
                "window_themes",
                "Window Themes",
                "window-new-symbolic",
                "Openbox themes",
            ),
        ]

    def build(self, app, builder):
        self.app = app
        widget = builder.get_object("page_window_themes")
        self.widget = widget

        self.flowbox_window_themes = builder.get_object("flowbox_window_themes")
        self.entry_window_themes_search = builder.get_object(
            "entry_window_themes_search"
        )
        if self.entry_window_themes_search is None:
            if widget is not None:
                entry = Gtk.SearchEntry()
                entry.set_name("entry_window_themes_search")
                entry.set_placeholder_text("Search window themes...")
                entry.set_width_chars(28)
                widget.pack_start(entry, False, False, 0)
                try:
                    widget.reorder_child(entry, 1)
                except Exception:
                    pass
                entry.show()
                self.entry_window_themes_search = entry

        if self.entry_window_themes_search is not None:
            self.entry_window_themes_search.connect(
                "changed", lambda _w: self.reload_window_themes()
            )

        self.current_theme_name = self.app.window_theme_service.get_current_theme()
        self.reload_window_themes()
        return widget

    def on_activate(self, app):
        self.reload_window_themes()

    def reload_window_themes(self):
        if self.flowbox_window_themes is None:
            return
        self.app._clear_widget_children(self.flowbox_window_themes)
        query = ""
        if self.entry_window_themes_search is not None:
            query = self.entry_window_themes_search.get_text().strip().lower()
        thread = threading.Thread(
            target=self._reload_window_themes_thread, args=(query,), daemon=True
        )
        thread.start()

    def _reload_window_themes_thread(self, query: str):
        flowbox = self.flowbox_window_themes
        if flowbox is None:
            return

        themes = self.app.window_theme_service.list_themes()
        if query:
            themes = [t for t in themes if query in t.name.lower()]
        current = self.app.window_theme_service.get_current_theme()

        def add_theme_card(theme, is_current):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.get_style_context().add_class("theme-card")
            if is_current:
                card.get_style_context().add_class("theme-card-active")

            top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            title = Gtk.Label(label=theme.name)
            title.get_style_context().add_class("theme-title")
            title.set_xalign(0.0)
            title.set_ellipsize(Pango.EllipsizeMode.END)
            top_row.pack_start(title, True, True, 0)
            if is_current:
                badge = Gtk.Label(label="CURRENT")
                badge.get_style_context().add_class("theme-type-badge")
                top_row.pack_start(badge, False, False, 0)
            card.pack_start(top_row, False, False, 0)

            preview = self.app._make_theme_preview_strip(
                [
                    "preferences-system-windows-symbolic",
                    "window-new-symbolic",
                    "view-restore-symbolic",
                    "window-close-symbolic",
                ]
            )
            card.pack_start(preview, False, False, 0)

            subtitle = Gtk.Label(label=str(theme.path))
            subtitle.get_style_context().add_class("theme-subtitle")
            subtitle.set_xalign(0.0)
            subtitle.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            subtitle.set_max_width_chars(28)
            card.pack_start(subtitle, False, False, 0)

            apply_btn = Gtk.Button(label="Apply")
            apply_btn.get_style_context().add_class("suggested-action")
            apply_btn.get_style_context().add_class("theme-apply-button")
            apply_btn.connect("clicked", self.on_window_theme_apply_clicked, theme.name)
            card.pack_start(apply_btn, False, False, 0)

            child = Gtk.FlowBoxChild()
            child.add(card)
            flowbox.add(child)
            child.show_all()
            return False

        for theme in themes:
            GLib.idle_add(add_theme_card, theme, theme.name == current)

    def on_window_theme_apply_clicked(self, _button, theme_name):
        ok, message = self.app.window_theme_service.apply_theme(theme_name)
        self.app._show_message(message)
        if ok:
            self.current_theme_name = theme_name
            self.reload_window_themes()
        else:
            dialog = Gtk.MessageDialog(
                transient_for=self.app.window,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=message,
            )
            dialog.run()
            dialog.destroy()
