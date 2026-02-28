"""Icon Themes section page (moved from pages/mixer)."""

import threading
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

from pages import register_page
from pages.base import BasePage

ICON_CARD_PREVIEW_ROWS = (
    ("user-home", "folder", "user-desktop", "folder-remote", "user-trash"),
    (
        "text-x-generic",
        "image-x-generic",
        "video-x-generic",
        "audio-x-generic",
        "package-x-generic",
    ),
    (
        "utilities-terminal",
        "application-x-executable",
        "firefox",
        "chromium",
        "gimp",
    ),
)
ICON_CARD_SYMBOLIC_ROW = (
    "network-wireless-symbolic",
    "network-wired-symbolic",
    "bluetooth-active-symbolic",
    "audio-volume-high-symbolic",
    "battery-good-symbolic",
    "display-brightness-medium-symbolic",
)
ICON_DIALOG_SECTION_ICONS = (
    (
        "Folders & Places",
        ("user-home", "user-desktop", "folder", "folder-remote", "user-trash"),
    ),
    (
        "Files",
        (
            "text-x-generic",
            "image-x-generic",
            "video-x-generic",
            "audio-x-generic",
            "x-office-document",
            "package-x-generic",
        ),
    ),
    (
        "Applications",
        (
            "utilities-terminal",
            "application-x-executable",
            "firefox",
            "chromium",
            "gimp",
            "emblem-mail",
        ),
    ),
)


@register_page
class IconThemesPage(BasePage):
    id = "icons"
    title = "Icons"
    icon = "preferences-desktop-icons-symbolic"

    def __init__(self):
        super().__init__()
        self.flowbox_icon_themes = None
        self.entry_icons_search = None
        self._icon_theme_reload_id = 0

    @staticmethod
    def get_sidebar_items():
        return [
            (
                "icons",
                "Icons",
                "preferences-desktop-icons-symbolic",
                "Icon theme selection",
            ),
        ]

    def build(self, app, builder):
        self.app = app
        widget = builder.get_object("page_icon_themes")
        self.widget = widget

        self.flowbox_icon_themes = builder.get_object("flowbox_icon_themes")
        self.entry_icons_search = builder.get_object("entry_icons_search")
        if self.flowbox_icon_themes is not None:
            self.flowbox_icon_themes.set_min_children_per_line(1)
            self.flowbox_icon_themes.set_max_children_per_line(4)

        if self.entry_icons_search is not None:
            self.entry_icons_search.connect(
                "changed", lambda _w: self.reload_icon_themes()
            )

        self.reload_icon_themes()
        return widget

    def on_activate(self, app):
        self.reload_icon_themes()

    def reload_icon_themes(self):
        if self.flowbox_icon_themes is None:
            return

        self.app._clear_widget_children(self.flowbox_icon_themes)
        self._icon_theme_reload_id += 1
        reload_id = self._icon_theme_reload_id

        query = ""
        if self.entry_icons_search is not None:
            query = self.entry_icons_search.get_text().strip().lower()

        thread = threading.Thread(
            target=self._reload_icon_themes_thread,
            args=(query, reload_id),
            daemon=True,
        )
        thread.start()

    def _reload_icon_themes_thread(self, query: str, reload_id: int):
        themes = self.app.interface_theme_service.list_icon_themes()
        current = self.app.interface_theme_service.get_current_icon_theme()
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
                self.flowbox_icon_themes is None
                or reload_id != self._icon_theme_reload_id
            ):
                return False

            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.get_style_context().add_class("theme-card")
            card.get_style_context().add_class("icon-theme-card")
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

            preview_surface = self._build_icon_theme_preview_surface(theme.name)
            preview_click = Gtk.EventBox()
            preview_click.set_visible_window(False)
            preview_click.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            preview_click.set_tooltip_text("Click to preview this icon theme")
            preview_click.connect(
                "button-press-event",
                self.on_icon_theme_card_preview_pressed,
                theme.name,
                theme_title,
            )
            preview_click.add(preview_surface)
            card.pack_start(preview_click, False, False, 0)

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

            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            actions.get_style_context().add_class("icon-theme-actions-row")
            actions.set_halign(Gtk.Align.END)

            preview_btn = Gtk.Button(label="Preview")
            preview_btn.get_style_context().add_class("theme-secondary-button")
            preview_btn.get_style_context().add_class("icon-theme-action-button")
            preview_btn.set_always_show_image(True)
            preview_btn.set_image(
                Gtk.Image.new_from_icon_name("view-preview-symbolic", Gtk.IconSize.MENU)
            )
            preview_btn.connect(
                "clicked",
                self.on_icon_theme_preview_clicked,
                theme.name,
                theme_title,
            )
            actions.pack_start(preview_btn, False, False, 0)

            apply_btn = Gtk.Button(label="Apply")
            apply_btn.get_style_context().add_class("suggested-action")
            apply_btn.get_style_context().add_class("icon-theme-action-button")
            apply_btn.set_always_show_image(True)
            apply_btn.set_image(
                Gtk.Image.new_from_icon_name(
                    "object-select-symbolic", Gtk.IconSize.MENU
                )
            )
            apply_btn.connect("clicked", self.on_icon_theme_apply_clicked, theme.name)
            actions.pack_start(apply_btn, False, False, 0)
            card.pack_start(actions, False, False, 0)

            child = Gtk.FlowBoxChild()
            child.add(card)
            self.flowbox_icon_themes.add(child)
            child.show_all()
            return False

        for theme in themes:
            GLib.idle_add(add_theme_card, theme, theme.name == current)

    def on_icon_theme_card_preview_pressed(
        self, _widget, event, theme_name: str, display_name: str
    ):
        if event is not None and getattr(event, "button", 1) != 1:
            return False
        self.on_icon_theme_preview_clicked(None, theme_name, display_name)
        return True

    def _load_icon_pixbuf_for_theme(
        self, icon_theme: Gtk.IconTheme, icon_name: str, size: int
    ) -> Optional[GdkPixbuf.Pixbuf]:
        candidates = [icon_name]
        if icon_name.endswith("-symbolic"):
            candidates.append(icon_name[: -len("-symbolic")])
        candidates.append("image-missing")

        for candidate in candidates:
            try:
                return icon_theme.load_icon(
                    candidate, size, Gtk.IconLookupFlags.FORCE_SIZE
                )
            except GLib.Error:
                continue
            except Exception:
                continue
        return None

    def _build_icon_theme_preview_tile(
        self,
        icon_theme: Gtk.IconTheme,
        icon_name: str,
        size: int,
        compact: bool = False,
    ) -> Gtk.Box:
        slot = Gtk.Box()
        slot.set_halign(Gtk.Align.FILL)
        slot.set_valign(Gtk.Align.FILL)
        slot.get_style_context().add_class("icon-theme-preview-slot")
        if compact:
            slot.get_style_context().add_class("icon-theme-preview-slot-compact")
        slot.set_size_request(max(22, size + 8), max(22, size + 8))

        pixbuf = self._load_icon_pixbuf_for_theme(icon_theme, icon_name, size)
        if pixbuf is not None:
            img = Gtk.Image.new_from_pixbuf(pixbuf)
        else:
            img = Gtk.Image.new_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
            img.set_pixel_size(size)

        img.set_halign(Gtk.Align.CENTER)
        img.set_valign(Gtk.Align.CENTER)
        img.set_tooltip_text(icon_name)
        slot.pack_start(img, True, True, 0)
        return slot

    def _build_icon_theme_preview_row(
        self,
        icon_theme: Gtk.IconTheme,
        icon_names: tuple[str, ...],
        size: int,
        compact: bool = False,
        dialog_row: bool = False,
    ) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.get_style_context().add_class("icon-theme-preview-row")
        if dialog_row:
            row.get_style_context().add_class("icon-theme-preview-row-dialog")
        row.set_halign(Gtk.Align.FILL)
        for icon_name in icon_names:
            tile = self._build_icon_theme_preview_tile(
                icon_theme, icon_name, size, compact=compact
            )
            row.pack_start(tile, True, True, 0)
        return row

    def _build_icon_theme_preview_surface(self, theme_name: str, large: bool = False):
        icon_theme = Gtk.IconTheme.new()
        icon_theme.set_custom_theme(theme_name)

        surface = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        surface.get_style_context().add_class("icon-theme-preview-surface")
        if large:
            surface.get_style_context().add_class("icon-theme-preview-surface-large")

        if large:
            for section_title, section_icons in ICON_DIALOG_SECTION_ICONS:
                title = Gtk.Label(label=section_title)
                title.set_xalign(0.0)
                title.get_style_context().add_class("icon-theme-preview-section-title")
                section_row = self._build_icon_theme_preview_row(
                    icon_theme,
                    section_icons,
                    size=26,
                    dialog_row=True,
                )
                surface.pack_start(title, False, False, 0)
                surface.pack_start(section_row, False, False, 0)
            symbolic_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            symbolic_wrap.get_style_context().add_class("icon-theme-symbolic-divider")
            symbolic_row = self._build_icon_theme_preview_row(
                icon_theme,
                ICON_CARD_SYMBOLIC_ROW,
                size=18,
                compact=True,
                dialog_row=True,
            )
            symbolic_wrap.pack_start(symbolic_row, False, False, 0)
            surface.pack_start(symbolic_wrap, False, False, 0)
        else:
            for row_icons in ICON_CARD_PREVIEW_ROWS:
                row = self._build_icon_theme_preview_row(
                    icon_theme, row_icons, size=32, dialog_row=False
                )
                surface.pack_start(row, False, False, 0)
            symbolic_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            symbolic_wrap.get_style_context().add_class("icon-theme-symbolic-divider")
            symbolic_row = self._build_icon_theme_preview_row(
                icon_theme,
                ICON_CARD_SYMBOLIC_ROW,
                size=16,
                compact=True,
                dialog_row=False,
            )
            symbolic_wrap.pack_start(symbolic_row, False, False, 0)
            surface.pack_start(symbolic_wrap, False, False, 0)

        return surface

    def on_icon_theme_preview_clicked(self, _button, theme_name, display_name=None):
        title_name = str(display_name or theme_name)
        dialog = Gtk.Dialog(
            title=f"Icon Preview - {title_name}",
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(560, 460)
        dialog.set_resizable(True)

        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(10)
        content.set_margin_end(10)

        title = Gtk.Label(label=title_name)
        title.get_style_context().add_class("theme-title")
        title.set_xalign(0.0)
        content.pack_start(title, False, False, 0)

        preview = self._build_icon_theme_preview_surface(theme_name, large=True)
        content.pack_start(preview, True, True, 0)

        subtitle = Gtk.Label(label=f"Theme ID: {theme_name}")
        subtitle.get_style_context().add_class("theme-subtitle")
        subtitle.set_xalign(0.0)
        content.pack_start(subtitle, False, False, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def on_icon_theme_apply_clicked(self, _button, theme_name):
        ok, message = self.app.interface_theme_service.apply_icon_theme(theme_name)
        self.app._show_message(message)
        if ok:
            self.reload_icon_themes()
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
