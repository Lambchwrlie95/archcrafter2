"""Cursor Themes section page (moved from pages/mixer)."""

import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from pages import register_page
from pages.base import BasePage


@register_page
class CursorThemesPage(BasePage):
    id = "cursors"
    title = "Cursors"
    icon = "input-mouse-symbolic"

    def __init__(self):
        super().__init__()
        self.flowbox_cursor_themes = None
        self.entry_cursors_search = None
        self._cursor_theme_reload_id = 0

    @staticmethod
    def get_sidebar_items():
        return [
            ("cursors", "Cursors", "input-mouse-symbolic", "Cursor theme selection"),
        ]

    def build(self, app, builder):
        self.app = app
        widget = builder.get_object("page_cursor_themes")
        self.widget = widget

        self.flowbox_cursor_themes = builder.get_object("flowbox_cursor_themes")
        self.entry_cursors_search = builder.get_object("entry_cursors_search")

        if self.entry_cursors_search is not None:
            self.entry_cursors_search.connect(
                "changed", lambda _w: self.reload_cursor_themes()
            )

        self.reload_cursor_themes()
        return widget

    def on_activate(self, app):
        self.reload_cursor_themes()

    def reload_cursor_themes(self):
        if self.flowbox_cursor_themes is None:
            return

        self.app._clear_widget_children(self.flowbox_cursor_themes)
        self._cursor_theme_reload_id += 1
        reload_id = self._cursor_theme_reload_id

        query = ""
        if self.entry_cursors_search is not None:
            query = self.entry_cursors_search.get_text().strip().lower()

        thread = threading.Thread(
            target=self._reload_cursor_themes_thread,
            args=(query, reload_id),
            daemon=True,
        )
        thread.start()

    def _reload_cursor_themes_thread(self, query: str, reload_id: int):
        themes = self.app.interface_theme_service.list_cursor_themes()
        current = self.app.interface_theme_service.get_current_cursor_theme()
        if query:
            themes = [
                t
                for t in themes
                if query in t.name.lower()
                or query in str(t.display_name or "").lower()
                or query in str(t.comment or "").lower()
            ]

        def add_theme_card(theme, is_current: bool):
            if (
                self.flowbox_cursor_themes is None
                or reload_id != self._cursor_theme_reload_id
            ):
                return False

            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.get_style_context().add_class("theme-card")
            if is_current:
                card.get_style_context().add_class("theme-card-active")

            theme_title = str(theme.display_name or theme.name)
            top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            title = Gtk.Label(label=theme_title)
            title.get_style_context().add_class("theme-title")
            title.set_xalign(0.0)
            title.set_ellipsize(Pango.EllipsizeMode.END)
            title.set_tooltip_text(theme.name)
            top_row.pack_start(title, True, True, 0)
            if is_current:
                badge = Gtk.Label(label="CURRENT")
                badge.get_style_context().add_class("theme-type-badge")
                top_row.pack_start(badge, False, False, 0)
            card.pack_start(top_row, False, False, 0)

            preview = self.app._make_theme_preview_strip(
                [
                    "input-mouse-symbolic",
                    "transform-move-symbolic",
                    "crosshair-symbolic",
                    "object-rotate-right-symbolic",
                ]
            )
            card.pack_start(preview, False, False, 0)

            subtitle_parts = [theme.name]
            if theme.inherits:
                inherit_text = ", ".join(theme.inherits[:2])
                if len(theme.inherits) > 2:
                    inherit_text += ", ..."
                subtitle_parts.append(f"inherits {inherit_text}")
            subtitle = Gtk.Label(label="  |  ".join(subtitle_parts))
            subtitle.get_style_context().add_class("theme-subtitle")
            subtitle.set_xalign(0.0)
            subtitle.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            subtitle.set_max_width_chars(28)
            subtitle.set_tooltip_text(
                f"{theme.path}\n{theme.comment}" if theme.comment else str(theme.path)
            )
            card.pack_start(subtitle, False, False, 0)

            apply_btn = Gtk.Button(label="Apply")
            apply_btn.get_style_context().add_class("suggested-action")
            apply_btn.get_style_context().add_class("theme-apply-button")
            apply_btn.connect("clicked", self.on_cursor_theme_apply_clicked, theme.name)
            card.pack_start(apply_btn, False, False, 0)

            child = Gtk.FlowBoxChild()
            child.add(card)
            self.flowbox_cursor_themes.add(child)
            child.show_all()
            return False

        for theme in themes:
            GLib.idle_add(add_theme_card, theme, theme.name == current)

    def on_cursor_theme_apply_clicked(self, _button, theme_name):
        ok, message = self.app.interface_theme_service.apply_cursor_theme(theme_name)
        self.app._show_message(message)
        if ok:
            self.reload_cursor_themes()
            return

        dialog = Gtk.MessageDialog(
            transient_for=self.app.window,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()
