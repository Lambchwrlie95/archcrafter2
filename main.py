#!/usr/bin/env python3
import colorsys
import hashlib
import math
import random
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("Gdk", "3.0")
from typing import Any, Optional

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

from backend import GtkThemeService, SettingsStore, WallpaperService, WindowThemeService

BASE_DIR = Path(__file__).resolve().parent
PRIMARY_GLADE = BASE_DIR / "Archcrafter2.glade"
BACKUP_GLADE = BASE_DIR / "#Archcrafter2.glade#"

FILL_MODES = ["zoom-fill", "centered", "scaled", "tiled", "auto"]
SORT_KEYS = ["name_asc", "name_desc", "newest", "oldest"]
SORT_LABEL_TO_KEY = {
    "Name A-Z": "name_asc",
    "Name Z-A": "name_desc",
    "Newest": "newest",
    "Oldest": "oldest",
}

# Sidebar should stay compact; do not allow expanding beyond this width.
SIDEBAR_WIDTH_MIN = 220
SIDEBAR_WIDTH_MAX = 347

ROW_TO_PAGE = {
    "row_wallpapers": "wallpapers",
    "row_gtk_themes": "gtk_themes",
    "row_window_themes": "window_themes",
    "row_panels": "panels",
    "row_jgmenu": "menu",
    "row_terminals": "terminals",
    "row_fetch": "fetch",
    "row_icons": "icons",
    "row_cursors": "cursors",
    "row_more": "more",
    "row_settings": "settings",
}

MODE_SIDEBAR_ITEMS = {
    "builder": [
        (
            "builder_home",
            "Builder Home",
            "applications-development-symbolic",
            "Build and organize module structure",
        ),
        (
            "builder_layout",
            "Layout",
            "view-list-symbolic",
            "Arrange containers and spacing",
        ),
        (
            "builder_widgets",
            "Widgets",
            "insert-object-symbolic",
            "Manage widget templates and IDs",
        ),
        (
            "builder_signals",
            "Signals",
            "network-transmit-receive-symbolic",
            "Wire and review signal handlers",
        ),
        (
            "builder_assets",
            "Assets",
            "folder-symbolic",
            "Review assets and integration points",
        ),
    ],
    "presets": [
        (
            "presets_home",
            "Presets Home",
            "view-grid-symbolic",
            "Browse and organize preset packs",
        ),
        (
            "presets_wallpapers",
            "Wallpaper Presets",
            "image-x-generic-symbolic",
            "Saved wallpaper combinations",
        ),
        (
            "presets_gtk",
            "GTK Presets",
            "preferences-desktop-theme-symbolic",
            "Saved GTK theme sets",
        ),
        (
            "presets_window",
            "Window Presets",
            "window-new-symbolic",
            "Saved Openbox window theme sets",
        ),
        (
            "presets_icons",
            "Icon Presets",
            "folder-pictures-symbolic",
            "Saved icon and cursor sets",
        ),
    ],
}


def find_glade_window(builder: Gtk.Builder) -> Optional[Gtk.Window]:
    for obj in builder.get_objects():
        if isinstance(obj, Gtk.ApplicationWindow):
            return obj
    for obj in builder.get_objects():
        if isinstance(obj, Gtk.Window):
            return obj
    return None


class ArchCrafter2App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.archcrafter2.app")
        self.window: Optional[Gtk.Window] = None
        self.builder: Optional[Gtk.Builder] = None
        self.sidebar_list: Optional[Gtk.ListBox] = None
        self.content_stack: Optional[Gtk.Stack] = None

        self.settings = SettingsStore(BASE_DIR / "settings.json")
        self.wallpaper_service = WallpaperService(BASE_DIR, self.settings)
        self.window_theme_service = WindowThemeService(BASE_DIR, self.settings)
        self.gtk_theme_service = GtkThemeService(BASE_DIR, self.settings)

        self.switch_wallpaper_system_source = None
        self.combo_wallpaper_fill_mode = None
        self.combo_wallpaper_sort = None
        self.entry_wallpaper_search = None
        self.chooser_wallpaper_folder = None
        self.button_top_settings = None
        self.wallpaper_view_stack = None
        self.wallpaper_view_switcher = None
        self.wallpaper_grid_scroller = None
        self.wallpaper_flowbox = None
        self.label_wallpaper_count = None
        self.scale_wallpaper_thumb_size = None
        self.flowbox_window_themes = None
        self.flowbox_gtk_themes = None
        self.entry_gtk_themes_search: Optional[Gtk.Entry] = None
        self.combo_gtk_themes_filter: Optional[Gtk.ComboBoxText] = None
        self.gtk_theme_preview_container: Optional[Gtk.Frame] = None
        self.gtk_theme_preview_provider = Gtk.CssProvider()
        self._gtk_theme_preview_provider_attached = False
        self._gtk_theme_reload_id = 0

        self.sidebar_box = None
        self.content_box = None
        self.mode_mixer_btn = None
        self.mode_builder_btn = None
        self.mode_presets_btn = None
        self.mode_placeholder = None
        self.mode_placeholder_title = None
        self.mode_placeholder_subtitle = None
        self.top_mode_bar = None
        self.top_mode_links = None
        self.sidebar_scroller = None
        self.root_hbox = None
        self.main_paned = None
        self.builder_sidebar_list: Optional[Gtk.ListBox] = None
        self.presets_sidebar_list: Optional[Gtk.ListBox] = None
        self.active_top_mode = "mixer"
        self._mode_sidebar_selection = {
            "builder": "builder_home",
            "presets": "presets_home",
        }
        self._sidebar_width_save_source = None
        self._pending_sidebar_width = None
        self._sidebar_width_cap = None
        self._gtk_theme_meta_by_name = {}
        self._icon_search_paths_registered = False

        self.thumb_width = self.wallpaper_service.get_thumb_size()
        self._thumb_size_reload_source = None

        self._loading_wallpaper_state = False
        self._wallpaper_bottom_bar_ready = False
        self._palette_cache = {}
        self._preview_window = None
        self.variant_dir = BASE_DIR / "library" / "wallpapers" / "colorized"
        self.variant_dir.mkdir(parents=True, exist_ok=True)
        self.current_reload_id = 0
        self.current_theme_name = self.window_theme_service.get_current_theme()
        self._reload_lock = threading.Lock()
        self._last_name_edit_us = 0

    def on_sidebar_row_selected(self, _listbox, row):
        if row is None or self.content_stack is None:
            return
        row_id = Gtk.Buildable.get_name(row)
        page_name = ROW_TO_PAGE.get(row_id)
        if page_name:
            self.content_stack.set_visible_child_name(page_name)

    def _build_mode_sidebar_list(self, mode: str) -> Gtk.ListBox:
        listbox = Gtk.ListBox()
        listbox.set_name("sidebar_list")
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        listbox.set_activate_on_single_click(True)
        listbox.set_hexpand(True)
        listbox.set_vexpand(True)
        listbox.set_visible(True)

        for item_id, title, icon_name, subtitle in MODE_SIDEBAR_ITEMS.get(mode, []):
            row = Gtk.ListBoxRow()
            row.set_name(f"row_{item_id}")
            row.set_visible(True)
            row.set_can_focus(True)

            row.set_data("mode_item_id", item_id)
            row.set_data("mode_item_title", title)
            row.set_data("mode_item_subtitle", subtitle)

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            box.set_visible(True)
            box.set_margin_top(10)
            box.set_margin_bottom(10)
            box.set_margin_start(14)
            box.set_margin_end(14)

            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            icon.set_pixel_size(22)
            icon.set_visible(True)

            label = Gtk.Label(label=title)
            label.set_visible(True)
            label.set_xalign(0.0)

            box.pack_start(icon, False, False, 0)
            box.pack_start(label, True, True, 0)
            row.add(box)
            listbox.add(row)

        listbox.connect("row-selected", self.on_mode_sidebar_row_selected, mode)
        listbox.show_all()
        return listbox

    def _ensure_mode_sidebars(self):
        if self.builder_sidebar_list is None:
            self.builder_sidebar_list = self._build_mode_sidebar_list("builder")
        if self.presets_sidebar_list is None:
            self.presets_sidebar_list = self._build_mode_sidebar_list("presets")

    def _get_mode_sidebar_widget(self, mode: str):
        self._ensure_mode_sidebars()
        if mode == "builder":
            return self.builder_sidebar_list
        if mode == "presets":
            return self.presets_sidebar_list
        return self.sidebar_list

    def _swap_sidebar_widget(self, target):
        if self.sidebar_scroller is None or target is None:
            return
        current = self.sidebar_scroller.get_child()
        if current is target:
            return
        if current is not None:
            self.sidebar_scroller.remove(current)
        self.sidebar_scroller.add(target)
        target.show_all()

    def _find_row_by_item_id(self, listbox: Gtk.ListBox, item_id: str):
        for row in listbox.get_children():
            if not isinstance(row, Gtk.ListBoxRow):
                continue
            if str(row.get_data("mode_item_id") or "") == item_id:
                return row
        return None

    def _restore_mode_sidebar_selection(self, mode: str):
        widget = self._get_mode_sidebar_widget(mode)
        if widget is None:
            return
        if mode not in {"builder", "presets"}:
            return
        wanted = str(self._mode_sidebar_selection.get(mode, "")).strip()
        row = self._find_row_by_item_id(widget, wanted)
        if row is None:
            row = widget.get_row_at_index(0)
        if row is not None:
            widget.select_row(row)

    def _current_mode_sidebar_title_subtitle(self, mode: str):
        widget = self._get_mode_sidebar_widget(mode)
        if widget is None:
            if mode == "builder":
                return ("Builder", "Builder workspace")
            if mode == "presets":
                return ("Presets", "Presets workspace")
            return ("", "")
        row = widget.get_selected_row()
        if row is None:
            row = widget.get_row_at_index(0)
        if row is None:
            if mode == "builder":
                return ("Builder", "Builder workspace")
            if mode == "presets":
                return ("Presets", "Presets workspace")
            return ("", "")
        title = str(row.get_data("mode_item_title") or mode.title())
        subtitle = str(row.get_data("mode_item_subtitle") or "")
        return (title, subtitle)

    def on_mode_sidebar_row_selected(self, _listbox, row, mode: str):
        if row is None:
            return
        item_id = str(row.get_data("mode_item_id") or "").strip()
        if item_id:
            self._mode_sidebar_selection[mode] = item_id
        if self.active_top_mode != mode:
            return
        if self.mode_placeholder_title is not None:
            self.mode_placeholder_title.set_text(
                str(row.get_data("mode_item_title") or mode.title())
            )
        if self.mode_placeholder_subtitle is not None:
            self.mode_placeholder_subtitle.set_text(
                str(row.get_data("mode_item_subtitle") or "")
            )

    def _register_icon_search_paths(self):
        if self._icon_search_paths_registered:
            return

        icon_theme = Gtk.IconTheme.get_default()
        if icon_theme is None:
            return

        for d in (
            BASE_DIR / "assets" / "icons",
            BASE_DIR.parent / "archcrafter" / "ui" / "assets" / "icons",
        ):
            try:
                if d.exists():
                    icon_theme.append_search_path(str(d))
            except Exception:
                pass

        self._icon_search_paths_registered = True

    def init_top_mode_bar(self):
        assert self.builder is not None
        self.sidebar_box = self.builder.get_object("sidebar_box")
        self.sidebar_scroller = self.builder.get_object("sidebar_scroller")
        self.content_box = self.builder.get_object("content_box")
        self.root_hbox = self.builder.get_object("root_hbox")
        self.top_mode_bar = self.builder.get_object("top_mode_bar")
        self.top_mode_links = self.builder.get_object("top_mode_links")
        self.mode_mixer_btn = self.builder.get_object("mode_mixer_btn")
        self.mode_builder_btn = self.builder.get_object("mode_builder_btn")
        self.mode_presets_btn = self.builder.get_object("mode_presets_btn")

        self._configure_mode_button(
            self.mode_mixer_btn,
            "mixer",
            "media-eq-symbolic",
            "mixer",
            "mode-left",
        )
        self._configure_mode_button(
            self.mode_builder_btn,
            "builder",
            "applications-development-symbolic",
            "builder",
            "mode-mid",
        )
        self._configure_mode_button(
            self.mode_presets_btn,
            "presets",
            "view-grid-symbolic",
            "presets",
            "mode-right",
        )
        self._ensure_resizable_layout()

        if self.sidebar_box is not None and self.top_mode_bar is not None:
            try:
                parent = self.top_mode_bar.get_parent()
                if parent is not None and parent is not self.sidebar_box:
                    parent.remove(self.top_mode_bar)
                if self.top_mode_bar.get_parent() is not self.sidebar_box:
                    self.sidebar_box.pack_end(self.top_mode_bar, False, True, 0)
            except Exception:
                pass

        if self.top_mode_links is not None:
            ctx = self.top_mode_links.get_style_context()
            ctx.remove_class("linked")
            self.top_mode_links.set_halign(Gtk.Align.FILL)
            self.top_mode_links.set_hexpand(True)
            self.top_mode_links.set_homogeneous(True)
            self.top_mode_links.set_spacing(0)

        if self.top_mode_bar is not None:
            self.top_mode_bar.set_halign(Gtk.Align.FILL)
            self.top_mode_bar.set_hexpand(True)
            self.top_mode_bar.set_margin_top(8)
            self.top_mode_bar.set_margin_bottom(10)
            self.top_mode_bar.set_margin_start(8)
            self.top_mode_bar.set_margin_end(8)
            self.top_mode_bar.show_all()

        if self.content_box is not None and self.mode_placeholder is None:
            placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            placeholder.set_halign(Gtk.Align.CENTER)
            placeholder.set_valign(Gtk.Align.CENTER)
            placeholder.set_hexpand(True)
            placeholder.set_vexpand(True)

            title = Gtk.Label(label="")
            title.get_style_context().add_class("mode-placeholder-title")
            title.set_xalign(0.5)

            subtitle = Gtk.Label(label="")
            subtitle.get_style_context().add_class("mode-placeholder-subtitle")
            subtitle.set_xalign(0.5)

            placeholder.pack_start(title, False, False, 0)
            placeholder.pack_start(subtitle, False, False, 0)

            self.content_box.pack_start(placeholder, True, True, 0)
            placeholder.hide()

            self.mode_placeholder = placeholder
            self.mode_placeholder_title = title
            self.mode_placeholder_subtitle = subtitle

        ui = self.settings.get_section("ui", default={})
        start_mode = str(ui.get("top_mode", "mixer")).strip().lower()

        if start_mode == "builder" and self.mode_builder_btn is not None:
            self.mode_builder_btn.set_active(True)
            self.apply_top_mode("builder")
        elif start_mode == "presets" and self.mode_presets_btn is not None:
            self.mode_presets_btn.set_active(True)
            self.apply_top_mode("presets")
        else:
            if self.mode_mixer_btn is not None:
                self.mode_mixer_btn.set_active(True)
            self.apply_top_mode("mixer")

    def _configure_mode_button(
        self, button, label: str, icon_name: str, mode: str, edge_class: str
    ):
        if button is None:
            return
        button.set_label(label)
        button.set_halign(Gtk.Align.FILL)
        button.set_hexpand(True)
        button.set_mode(False)
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.set_always_show_image(True)
        button.set_image_position(Gtk.PositionType.LEFT)
        img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        img.set_pixel_size(14)
        button.set_image(img)
        ctx = button.get_style_context()
        ctx.add_class("mode-link-btn")
        ctx.add_class(edge_class)
        button.connect("toggled", self.on_top_mode_toggled, mode)

    def _ensure_resizable_layout(self):
        if (
            self.root_hbox is None
            or self.sidebar_box is None
            or self.content_box is None
        ):
            return

        if self.main_paned is None:
            for child in self.root_hbox.get_children():
                if isinstance(child, Gtk.Paned):
                    self.main_paned = child
                    break

        if self.main_paned is None:
            try:
                if self.sidebar_box.get_parent() is self.root_hbox:
                    self.root_hbox.remove(self.sidebar_box)
                if self.content_box.get_parent() is self.root_hbox:
                    self.root_hbox.remove(self.content_box)
            except Exception:
                return

            paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
            paned.set_wide_handle(True)
            paned.set_hexpand(True)
            paned.set_vexpand(True)
            paned.add1(self.sidebar_box)
            paned.add2(self.content_box)
            self.root_hbox.pack_start(paned, True, True, 0)
            self.main_paned = paned

        ui = self.settings.get_section("ui", default={})
        try:
            sidebar_width = int(ui.get("sidebar_width", 260))
        except Exception:
            sidebar_width = 260
        sidebar_width = max(SIDEBAR_WIDTH_MIN, min(SIDEBAR_WIDTH_MAX, sidebar_width))
        if self._sidebar_width_cap is None:
            self._sidebar_width_cap = sidebar_width
        sidebar_width = min(sidebar_width, int(self._sidebar_width_cap))

        self.main_paned.set_position(sidebar_width)
        self.main_paned.connect("notify::position", self.on_main_paned_position_changed)
        self.main_paned.show_all()

    def _lock_sidebar_width_cap_from_current(self):
        if self.main_paned is None:
            return False

        measured = 0
        if self.sidebar_box is not None:
            try:
                measured = int(self.sidebar_box.get_allocated_width())
            except Exception:
                measured = 0
        if measured <= 0:
            try:
                measured = int(self.main_paned.get_position())
            except Exception:
                measured = 0
        if measured <= 0:
            return False

        self._sidebar_width_cap = max(SIDEBAR_WIDTH_MIN, measured)
        if self.main_paned.get_position() > self._sidebar_width_cap:
            self.main_paned.set_position(self._sidebar_width_cap)
        return False

    def on_main_paned_position_changed(self, paned, _pspec):
        raw_pos = int(paned.get_position())
        max_width = (
            int(self._sidebar_width_cap)
            if self._sidebar_width_cap is not None
            else SIDEBAR_WIDTH_MAX
        )
        clamped = max(SIDEBAR_WIDTH_MIN, min(max_width, raw_pos))
        if clamped != raw_pos:
            paned.set_position(clamped)
        self._pending_sidebar_width = clamped
        if self._sidebar_width_save_source is None:
            self._sidebar_width_save_source = GLib.timeout_add(
                250, self._flush_sidebar_width_save
            )

    def _flush_sidebar_width_save(self):
        self._sidebar_width_save_source = None
        if self._pending_sidebar_width is None:
            return False

        ui = self.settings.get_section("ui", default={})
        current = ui.get("sidebar_width")
        if current != self._pending_sidebar_width:
            ui["sidebar_width"] = self._pending_sidebar_width
            self.settings.save()
        return False

    def apply_top_mode(self, mode: str):
        mode = str(mode or "mixer").strip().lower()
        if mode not in {"mixer", "builder", "presets"}:
            mode = "mixer"
        self.active_top_mode = mode

        if self.sidebar_scroller is not None:
            self.sidebar_scroller.set_visible(True)

        if mode == "builder":
            self._swap_sidebar_widget(self._get_mode_sidebar_widget("builder"))
            self._restore_mode_sidebar_selection("builder")
        elif mode == "presets":
            self._swap_sidebar_widget(self._get_mode_sidebar_widget("presets"))
            self._restore_mode_sidebar_selection("presets")
        else:
            self._swap_sidebar_widget(self.sidebar_list)

        show_placeholder = mode in {"builder", "presets"}

        if self.content_stack is not None:
            self.content_stack.set_visible(not show_placeholder)

        if self.mode_placeholder is not None:
            if show_placeholder:
                title, subtitle = self._current_mode_sidebar_title_subtitle(mode)
                if self.mode_placeholder_title is not None:
                    self.mode_placeholder_title.set_text(title)
                if self.mode_placeholder_subtitle is not None:
                    self.mode_placeholder_subtitle.set_text(subtitle)
                self.mode_placeholder.show()
            else:
                self.mode_placeholder.hide()

        ui = self.settings.get_section("ui", default={})
        if ui.get("top_mode") != mode:
            ui["top_mode"] = mode
            self.settings.save()

    def on_top_mode_toggled(self, button, mode: str):
        if not button.get_active():
            return
        self.apply_top_mode(mode)

    def on_top_settings_clicked(self, _button):
        # Settings lives in the mixer content stack; force mixer mode first.
        if self.mode_mixer_btn is not None:
            self.mode_mixer_btn.set_active(True)
        if self.sidebar_list is not None:
            for row in self.sidebar_list.get_children():
                if Gtk.Buildable.get_name(row) == "row_settings":
                    self.sidebar_list.select_row(row)
                    break
        if self.content_stack is not None:
            self.content_stack.set_visible_child_name("settings")

    def _reparent_box_child(
        self,
        widget,
        target_box: Gtk.Box,
        expand: bool = False,
        fill: bool = False,
        padding: int = 0,
        pack_end: bool = False,
    ):
        if widget is None or target_box is None:
            return

        current_parent = widget.get_parent()
        if current_parent is target_box:
            return

        if current_parent is not None:
            current_parent.remove(widget)

        if pack_end:
            target_box.pack_end(widget, expand, fill, padding)
        else:
            target_box.pack_start(widget, expand, fill, padding)

    def _ensure_wallpaper_bottom_bar(self):
        if self.builder is None:
            return
        if self._wallpaper_bottom_bar_ready:
            return

        page = self.builder.get_object("page_wallpapers")
        header_box = self.builder.get_object("wallpaper_header_box")
        controls_box = self.builder.get_object("wallpaper_controls_box")
        title = self.builder.get_object("title_wallpapers")
        count = self.builder.get_object("label_wallpaper_count")
        size_label = self.builder.get_object("label_wallpaper_thumb_size")
        size_sep = self.builder.get_object("sep_wallpaper_ctrl_size")
        settings_icon = self.builder.get_object("icon_top_settings")

        if page is None:
            return

        # Compact the top controls row and keep settings action near controls.
        page.set_spacing(4)
        if controls_box is not None:
            controls_box.set_spacing(7)
            controls_box.set_hexpand(False)
            controls_box.set_halign(Gtk.Align.START)
        if settings_icon is not None:
            settings_icon.set_from_icon_name(
                "preferences-system-symbolic", Gtk.IconSize.MENU
            )
            settings_icon.set_pixel_size(18)
        if self.button_top_settings is not None and controls_box is not None:
            self.button_top_settings.set_margin_start(6)
            self._reparent_box_child(
                self.button_top_settings, controls_box, False, False, 0
            )
        if header_box is not None:
            header_box.set_no_show_all(True)
            header_box.hide()

        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        Gtk.Buildable.set_name(bottom_bar, "wallpaper_bottom_bar")
        bottom_bar.set_hexpand(True)
        bottom_bar.set_margin_start(10)
        bottom_bar.set_margin_end(10)
        bottom_bar.set_margin_top(0)
        bottom_bar.set_margin_bottom(0)

        info_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        info_box.set_hexpand(True)
        info_box.set_halign(Gtk.Align.START)

        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        size_box.set_halign(Gtk.Align.END)

        bottom_bar.pack_start(info_box, True, True, 0)
        bottom_bar.pack_end(size_box, False, False, 0)

        self._reparent_box_child(title, info_box, False, False, 0)
        self._reparent_box_child(count, info_box, False, False, 0)
        self._reparent_box_child(size_label, size_box, False, False, 0)
        self._reparent_box_child(
            self.scale_wallpaper_thumb_size, size_box, False, False, 0
        )

        if size_sep is not None:
            size_sep.hide()

        page.pack_end(bottom_bar, False, True, 0)
        bottom_bar.show_all()
        self._wallpaper_bottom_bar_ready = True

    def _show_message(self, message: str):
        print(message)
        if self.window is not None:
            self.window.set_title(f"ArchCrafter2 - {message}")

    def _get_colorized_badge_css(self):
        section = self.settings.get_section("wallpapers", default={})
        raw = str(
            section.get(
                "colorized_tag_color", section.get("colorized_badge_color", "#1482C8")
            )
        ).strip()

        if raw.startswith("#"):
            raw = raw[1:]
        if len(raw) != 6:
            raw = "1482C8"
        try:
            r = int(raw[0:2], 16)
            g = int(raw[2:4], 16)
            b = int(raw[4:6], 16)
        except Exception:
            r, g, b = 20, 130, 200

        # Basic contrast text color based on relative luminance.
        lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        text = "#111111" if lum > 0.62 else "#ffffff"
        bg = f"rgba({r}, {g}, {b}, 0.88)"
        return bg, text

    def _ensure_css(self):
        badge_bg, badge_text = self._get_colorized_badge_css()
        css = """
        .preview-shell {
            background-color: transparent;
            border: none;
            border-radius: 8px;
        }
        .wallpaper-title {
            font-size: 11px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.70);
        }
        .overlay-action-button {
            background-color: transparent;
            color: rgba(225, 233, 245, 0.82);
            border-radius: 6px;
            border: none;
            min-height: 28px;
            min-width: 28px;
            padding: 0;
        }
        .overlay-action-button:hover {
            background-color: rgba(255, 255, 255, 0.10);
            color: #ffffff;
        }
        .overlay-action-button:active {
            background-color: rgba(255, 255, 255, 0.16);
            color: #ffffff;
        }
        .colorize-swatch {
            border: 1px solid rgba(255, 255, 255, 0.24);
            border-radius: 10px;
        }
        .colorize-chip-button {
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 10px;
            padding: 0;
        }
        .colorize-chip-button:hover {
            background-color: transparent;
            border-color: rgba(255, 255, 255, 0.34);
        }
        .colorized-badge {
            background-color: __BADGE_BG__;
            color: __BADGE_TEXT__;
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 10px;
            font-weight: 700;
        }
        .theme-card {
            background-color: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 10px;
            min-width: 170px;
        }
        .theme-card:hover {
            background-color: rgba(255, 255, 255, 0.07);
            border-color: rgba(255, 255, 255, 0.16);
        }
        .theme-card-active {
            border-color: rgba(91, 161, 234, 0.85);
            background-color: rgba(91, 161, 234, 0.12);
        }
        .theme-title {
            font-size: 12px;
            font-weight: 600;
        }
        .theme-chip {
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            min-height: 12px;
            min-width: 12px;
        }
        .theme-type-badge {
            font-size: 9px;
            font-weight: 700;
            color: rgba(235, 240, 248, 0.92);
            padding: 2px 6px;
            border-radius: 4px;
            background-color: rgba(91, 161, 234, 0.18);
            border: 1px solid rgba(91, 161, 234, 0.42);
        }
        .theme-apply-button {
            border-radius: 6px;
            padding: 4px 10px;
        }
        #sidebar_list row {
            margin: 1px 6px;
            border-radius: 8px;
        }
        #sidebar_list row:selected {
            background-color: rgba(91, 161, 234, 0.18);
        }
        #top_mode_bar {
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            padding-top: 6px;
        }
        #top_mode_links {
            background-color: rgba(255, 255, 255, 0.01);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 10px;
        }
        .mode-link-btn {
            background-image: none;
            background-color: transparent;
            color: rgba(237, 240, 246, 0.90);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 0;
            padding: 4px 8px;
            min-height: 28px;
            font-size: 11px;
            font-weight: 500;
        }
        .mode-link-btn:hover {
            background-color: rgba(255, 255, 255, 0.05);
            color: #ffffff;
        }
        .mode-link-btn:checked {
            background-color: rgba(91, 161, 234, 0.18);
            border-color: rgba(91, 161, 234, 0.74);
            color: #ffffff;
        }
        .mode-link-btn.mode-left {
            border-top-left-radius: 10px;
            border-bottom-left-radius: 10px;
        }
        .mode-link-btn.mode-mid {
            border-left-width: 0;
        }
        .mode-link-btn.mode-right {
            border-left-width: 0;
            border-top-right-radius: 10px;
            border-bottom-right-radius: 10px;
        }
        .mode-placeholder-title {
            font-size: 19px;
            font-weight: 700;
        }
        .mode-placeholder-subtitle {
            color: rgba(255, 255, 255, 0.72);
        }
        """
        css = css.replace("__BADGE_BG__", badge_bg).replace(
            "__BADGE_TEXT__", badge_text
        )
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode("utf-8"))
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _build_preview_pixbuf(
        self, image_path: Path, max_w: int = 1500, max_h: int = 950
    ):
        pix = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
        w, h = pix.get_width(), pix.get_height()
        if w <= 0 or h <= 0:
            return pix
        scale = min(max_w / w, max_h / h, 1.0)
        if scale < 1.0:
            tw, th = max(1, int(w * scale)), max(1, int(h * scale))
            pix = pix.scale_simple(tw, th, GdkPixbuf.InterpType.BILINEAR)
        return pix

    def on_preview_window_destroy(self, _win):
        self._preview_window = None

    def on_wallpaper_preview_clicked(self, _button, path_str: str):
        path = Path(path_str)
        if not path.exists():
            self._show_message("Preview failed: file missing")
            return

        if self._preview_window is not None:
            try:
                self._preview_window.destroy()
            except Exception:
                pass
            self._preview_window = None

        try:
            pix = self._build_preview_pixbuf(path)
            img = Gtk.Image.new_from_pixbuf(pix)
        except Exception:
            img = Gtk.Image.new_from_icon_name("image-missing", Gtk.IconSize.DIALOG)

        win = Gtk.Window(title=f"Preview - {path.name}")
        if self.window is not None:
            win.set_transient_for(self.window)
        win.set_default_size(1000, 700)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(img)
        win.add(scroll)

        win.connect("destroy", self.on_preview_window_destroy)
        self._preview_window = win
        win.show_all()

    def on_colorizer_preview_original_clicked(
        self, _button, path_str: str, parent_dialog
    ):
        path = Path(path_str)
        if not path.exists():
            self._show_message("Preview failed: file missing")
            return

        try:
            pix = self._build_preview_pixbuf(path)
            img = Gtk.Image.new_from_pixbuf(pix)
        except Exception:
            img = Gtk.Image.new_from_icon_name("image-missing", Gtk.IconSize.DIALOG)

        parent = parent_dialog if isinstance(parent_dialog, Gtk.Window) else self.window
        dialog = Gtk.Dialog(
            title=f"Preview - {path.name}", transient_for=parent, modal=True
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(1000, 700)

        area = dialog.get_content_area()
        area.set_margin_top(8)
        area.set_margin_bottom(8)
        area.set_margin_start(8)
        area.set_margin_end(8)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        scroll.add(img)
        area.pack_start(scroll, True, True, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _clear_widget_children(self, widget):
        for child in widget.get_children():
            widget.remove(child)

    def _get_thumbnail_pixbuf(self, image_path: Path, width: int, height: int):
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(image_path), width, height, True
            )
        except Exception:
            return None

    def _build_thumbnail(self, image_path: Path, width: int, height: int):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(image_path), width, height, True
            )
            return Gtk.Image.new_from_pixbuf(pixbuf)
        except Exception:
            fallback = Gtk.Image.new_from_icon_name(
                "image-missing", Gtk.IconSize.DIALOG
            )
            fallback.set_size_request(width, height)
            return fallback

    def _draw_rounded_thumbnail(self, widget, cr, pixbuf, radius: float = 8.0):
        alloc = widget.get_allocation()
        w = float(max(1, alloc.width))
        h = float(max(1, alloc.height))

        self._rounded_rect(cr, 0.5, 0.5, max(1.0, w - 1.0), max(1.0, h - 1.0), radius)
        cr.clip()

        # Fill letterbox area so non-16:9 images still look intentional.
        cr.set_source_rgb(0.08, 0.09, 0.10)
        cr.paint()

        if pixbuf is not None:
            pw = pixbuf.get_width()
            ph = pixbuf.get_height()
            ox = (w - pw) / 2.0
            oy = (h - ph) / 2.0
            Gdk.cairo_set_source_pixbuf(cr, pixbuf, ox, oy)
            cr.paint()

        return False

    def _build_rounded_thumbnail_widget(
        self, pixbuf, width: int, height: int, radius: float = 8.0
    ):
        area = Gtk.DrawingArea()
        area.set_size_request(width, height)
        area.connect("draw", self._draw_rounded_thumbnail, pixbuf, radius)
        return area

    def _is_colorized_path(self, path: Path) -> bool:
        try:
            return Path(path).resolve().is_relative_to(self.variant_dir.resolve())
        except Exception:
            return "colorized" in str(path).lower()

    def _base_wallpaper_display_name(self, entry):
        clean_name = Path(entry.name).name
        return self.wallpaper_service.get_display_name(entry.path, clean_name)

    def _compose_wallpaper_display_name(self, entry, is_colorized: bool | None = None):
        if is_colorized is None:
            is_colorized = self._is_colorized_path(entry.path) or str(
                entry.name
            ).lower().startswith("colorized/")

        base = self._base_wallpaper_display_name(entry)
        if is_colorized and "(colorized)" not in base.lower():
            return f"{base} (Colorized)"
        return base

    def _hex_to_rgb(self, color_hex: str):
        value = color_hex.lstrip("#")
        if len(value) != 6:
            return 0.5, 0.5, 0.5
        r = int(value[0:2], 16) / 255.0
        g = int(value[2:4], 16) / 255.0
        b = int(value[4:6], 16) / 255.0
        return r, g, b

    def _rgb_to_hex(self, r: float, g: float, b: float):
        r = max(0, min(255, int(round(r * 255))))
        g = max(0, min(255, int(round(g * 255))))
        b = max(0, min(255, int(round(b * 255))))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _mix_hex(self, base_hex: str, target_hex: str, ratio: float):
        ratio = max(0.0, min(1.0, float(ratio)))
        br, bg, bb = self._hex_to_rgb(base_hex)
        tr, tg, tb = self._hex_to_rgb(target_hex)
        rr = br + (tr - br) * ratio
        gg = bg + (tg - bg) * ratio
        bb2 = bb + (tb - bb) * ratio
        return self._rgb_to_hex(rr, gg, bb2)

    def _is_light_hex(self, color_hex: str) -> bool:
        r, g, b = self._hex_to_rgb(color_hex)
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return lum >= 0.56

    def _rounded_rect(self, cr, x: float, y: float, w: float, h: float, radius: float):
        r = max(0.0, min(radius, w / 2.0, h / 2.0))
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def _draw_swatch(self, widget, cr, color_hex: str):
        r, g, b = self._hex_to_rgb(color_hex)
        alloc = widget.get_allocation()
        x, y = 0.5, 0.5
        w = max(1.0, alloc.width - 1.0)
        h = max(1.0, alloc.height - 1.0)
        radius = max(4.0, min(w, h) * 0.30)

        self._rounded_rect(cr, x, y, w, h, radius)
        cr.set_source_rgb(r, g, b)
        cr.fill_preserve()
        cr.set_source_rgba(0, 0, 0, 0.32)
        cr.set_line_width(1.0)
        cr.stroke()
        return False

    def on_swatch_pressed(self, _widget, _event, color_hex: str):
        color = color_hex.upper()
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(color, -1)
        self._show_message(f"Copied {color}")
        return True

    def _build_swatch_row(self, colors, swatch_size: int = 20, spacing: int = 3):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
        row.set_halign(Gtk.Align.START)
        for color_hex in colors:
            sw = Gtk.DrawingArea()
            sw.set_size_request(swatch_size, swatch_size)
            sw.connect("draw", self._draw_swatch, color_hex)

            click_box = Gtk.EventBox()
            click_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            click_box.set_tooltip_text(f"Click to copy {color_hex.upper()}")
            click_box.connect("button-press-event", self.on_swatch_pressed, color_hex)
            click_box.add(sw)

            row.pack_start(click_box, False, False, 0)
        return row

    def _color_distance(self, a, b):
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    def _extract_palette(self, path: Path, count: int = 5):
        key = str(path)
        cached = self._palette_cache.get(key)
        if cached:
            return cached

        colors = []
        try:
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 80, 80, True)
            width, height = pix.get_width(), pix.get_height()
            n = pix.get_n_channels()
            rowstride = pix.get_rowstride()
            data = pix.get_pixels()

            freq = {}
            step = max(1, int((width * height) / 1800))
            for y in range(0, height, step):
                base = y * rowstride
                for x in range(0, width, step):
                    i = base + x * n
                    r = data[i]
                    g = data[i + 1]
                    b = data[i + 2]
                    if n == 4 and data[i + 3] < 20:
                        continue
                    rq = (r // 24) * 24
                    gq = (g // 24) * 24
                    bq = (b // 24) * 24
                    freq[(rq, gq, bq)] = freq.get((rq, gq, bq), 0) + 1

            ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
            picked = []
            for (r, g, b), _ in ranked:
                if all(self._color_distance((r, g, b), p) >= 30 for p in picked):
                    picked.append((r, g, b))
                if len(picked) >= count:
                    break

            for r, g, b in picked:
                colors.append(f"#{r:02x}{g:02x}{b:02x}")
        except Exception:
            colors = []

        if not colors:
            colors = ["#4c566a", "#5e81ac", "#88c0d0", "#a3be8c", "#ebcb8b"]

        self._palette_cache[key] = colors[:count]
        return self._palette_cache[key]

    def _build_similar_colors(self, base_colors):
        result = []
        seeds = base_colors[:5] if base_colors else ["#5e81ac"]
        for color_hex in seeds:
            r, g, b = self._hex_to_rgb(color_hex)
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            for dh in (0.0, 0.03, -0.03, 0.07, -0.07, 0.12, -0.12):
                nh = (h + dh) % 1.0
                for sat_mul, val_mul in (
                    (1.0, 1.0),
                    (1.1, 1.0),
                    (0.9, 1.1),
                    (1.2, 0.95),
                ):
                    ns = max(0.18, min(1.0, s * sat_mul))
                    nv = max(0.2, min(1.0, v * val_mul))
                    rr, gg, bb = colorsys.hsv_to_rgb(nh, ns, nv)
                    result.append(self._rgb_to_hex(rr, gg, bb))

        return self._unique_colors(result, limit=30)

    def _unique_colors(self, colors, limit: int | None = None):
        unique = []
        seen = set()
        for c in colors:
            cu = str(c).strip().upper()
            if not cu.startswith("#"):
                cu = f"#{cu}"
            if len(cu) != 7:
                continue
            if cu in seen:
                continue
            seen.add(cu)
            unique.append(cu)
            if limit is not None and len(unique) >= limit:
                break
        return unique

    def _build_color_theory_colors(self, base_colors):
        seeds = self._unique_colors(base_colors, limit=3) or ["#5E81AC"]
        result = []

        for color_hex in seeds:
            r, g, b = self._hex_to_rgb(color_hex)
            h, s, v = colorsys.rgb_to_hsv(r, g, b)

            # Analogous / complement / split-complement / triadic / square
            for deg in (0, 30, -30, 180, 150, -150, 120, -120, 90, -90):
                nh = (h + deg / 360.0) % 1.0
                for sat_mul, val_mul in ((1.0, 1.0), (0.85, 1.08), (1.15, 0.92)):
                    ns = max(0.18, min(1.0, s * sat_mul))
                    nv = max(0.16, min(1.0, v * val_mul))
                    rr, gg, bb = colorsys.hsv_to_rgb(nh, ns, nv)
                    result.append(self._rgb_to_hex(rr, gg, bb))

            # Monochromatic tints/shades
            for vv in (0.28, 0.42, 0.56, 0.70, 0.84, 0.95):
                rr, gg, bb = colorsys.hsv_to_rgb(h, max(0.12, s * 0.75), vv)
                result.append(self._rgb_to_hex(rr, gg, bb))

        return self._unique_colors(result, limit=36)

    def _get_recent_colorize_swatches(self):
        section = self.settings.get_section("wallpapers", default={})
        values = section.get("colorize_recent", [])
        if not isinstance(values, list):
            return []
        return self._unique_colors(values, limit=24)

    def _record_colorize_swatch(self, color_hex: str):
        normalized = self._unique_colors([color_hex], limit=1)
        if not normalized:
            return
        color = normalized[0]

        section = self.settings.get_section("wallpapers", default={})
        current = section.get("colorize_recent", [])
        if not isinstance(current, list):
            current = []

        merged = [color] + [
            c for c in self._unique_colors(current, limit=64) if c != color
        ]
        section["colorize_recent"] = merged[:36]
        self.settings.save()

    def _random_color(self):
        return f"#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}"

    def _get_colorize_strength(self) -> int:
        section = self.settings.get_section("wallpapers", default={})
        raw = section.get("colorize_strength", 65)
        try:
            value = int(raw)
        except Exception:
            value = 65
        return max(10, min(100, value))

    def _set_colorize_strength(self, value: int):
        section = self.settings.get_section("wallpapers", default={})
        section["colorize_strength"] = max(10, min(100, int(value)))
        self.settings.save()

    def on_colorize_strength_changed(self, scale):
        self._set_colorize_strength(int(round(scale.get_value())))

    def _create_colorized_variant(
        self, source_path: Path, color_hex: str, strength: int = 55
    ) -> tuple[Optional[Path], Optional[str]]:
        src = Path(source_path)
        if not src.exists():
            return None, "Source image not found"

        safe_stem = "".join(ch if ch.isalnum() else "_" for ch in src.stem)[:48]
        digest = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:10]
        color_tag = color_hex.lstrip("#").lower()
        out = self.variant_dir / f"{safe_stem}_{digest}_{color_tag}_{strength}.png"
        if out.exists():
            return out, None

        magick = shutil.which("magick")
        convert = shutil.which("convert")
        cmd = None
        if magick:
            cmd = [
                magick,
                str(src),
                "-fill",
                color_hex,
                "-colorize",
                str(strength),
                str(out),
            ]
        elif convert:
            cmd = [
                convert,
                str(src),
                "-fill",
                color_hex,
                "-colorize",
                str(strength),
                str(out),
            ]
        else:
            return (
                None,
                "ImageMagick is required for colorize (magick/convert not found)",
            )

        try:
            subprocess.run(
                cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return out, None
        except Exception as exc:
            return None, f"Colorize failed: {exc}"

    def _apply_colorized_and_report(
        self,
        source_path: Path,
        color_hex: str,
        dialog=None,
        message_prefix: str = "Applied colorized wallpaper",
        close_on_success: bool = False,
        strength: int | None = None,
    ):
        use_strength = (
            self._get_colorize_strength()
            if strength is None
            else max(10, min(100, int(strength)))
        )
        variant, err = self._create_colorized_variant(
            Path(source_path), color_hex, use_strength
        )
        if err or variant is None:
            self._show_message(err or "Colorize failed")
            return False

        ok, message = self.wallpaper_service.apply_wallpaper(variant)
        if ok:
            pretty = str(color_hex).strip().upper()
            self._record_colorize_swatch(pretty)
            self._show_message(f"{message_prefix} {pretty}")
            if close_on_success and dialog is not None:
                dialog.destroy()
            return True

        self._show_message(message)
        return False

    def _rgba_to_hex(self, rgba: Gdk.RGBA):
        r = max(0, min(255, int(round(rgba.red * 255))))
        g = max(0, min(255, int(round(rgba.green * 255))))
        b = max(0, min(255, int(round(rgba.blue * 255))))
        return f"#{r:02x}{g:02x}{b:02x}"

    def on_colorize_pick(
        self,
        _widget,
        _event,
        source_path: str,
        color_hex: str,
        dialog,
        strength_scale=None,
    ):
        strength = None
        if strength_scale is not None:
            strength = int(round(strength_scale.get_value()))
        self._apply_colorized_and_report(
            Path(source_path),
            color_hex,
            dialog,
            "Applied colorized wallpaper",
            strength=strength,
        )
        return True

    def on_colorize_chip_clicked(
        self, _button, source_path: str, color_hex: str, dialog, strength_scale=None
    ):
        strength = None
        if strength_scale is not None:
            strength = int(round(strength_scale.get_value()))
        self._apply_colorized_and_report(
            Path(source_path),
            color_hex,
            dialog,
            "Applied colorized wallpaper",
            strength=strength,
        )

    def _build_colorize_chip_flow(
        self, colors, source_path: str, dialog, strength_scale=None
    ):
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(10)
        flow.set_column_spacing(4)
        flow.set_row_spacing(4)

        for color_hex in self._unique_colors(colors, limit=None):
            child = Gtk.FlowBoxChild()

            sw = Gtk.DrawingArea()
            sw.set_size_request(58, 34)
            sw.connect("draw", self._draw_swatch, color_hex)
            sw.get_style_context().add_class("colorize-swatch")

            swatch_btn = Gtk.Button()
            swatch_btn.set_relief(Gtk.ReliefStyle.NONE)
            swatch_btn.get_style_context().add_class("colorize-chip-button")
            swatch_btn.set_tooltip_text(f"Apply {color_hex}")
            swatch_btn.connect(
                "clicked",
                self.on_colorize_chip_clicked,
                source_path,
                color_hex,
                dialog,
                strength_scale,
            )
            swatch_btn.add(sw)

            child.add(swatch_btn)
            flow.add(child)

        return flow

    def on_random_colorize_clicked(
        self, _button, source_path: str, dialog, strength_scale=None
    ):
        color_hex = self._random_color()
        strength = None
        if strength_scale is not None:
            strength = int(round(strength_scale.get_value()))
        self._apply_colorized_and_report(
            Path(source_path),
            color_hex,
            dialog,
            "Applied random colorized wallpaper",
            strength=strength,
        )

    def on_custom_color_changed(self, color_button, hex_entry):
        color_hex = self._rgba_to_hex(color_button.get_rgba()).upper()
        hex_entry.set_text(color_hex)

    def on_copy_custom_hex_clicked(self, _button, hex_entry):
        color = hex_entry.get_text().strip().upper()
        if not color:
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(color, -1)
        self._show_message(f"Copied {color}")

    def on_apply_custom_color_clicked(
        self,
        _button,
        source_path: str,
        color_button,
        hex_entry,
        dialog,
        strength_scale=None,
    ):
        color_hex = self._rgba_to_hex(color_button.get_rgba())
        hex_entry.set_text(color_hex.upper())
        strength = None
        if strength_scale is not None:
            strength = int(round(strength_scale.get_value()))
        self._apply_colorized_and_report(
            Path(source_path),
            color_hex,
            dialog,
            "Applied custom colorized wallpaper",
            strength=strength,
        )

    def on_wallpaper_colorize_clicked(self, _button, path_str: str):
        src = Path(path_str)
        if not src.exists():
            self._show_message("Cannot colorize: file missing")
            return

        palette = self._extract_palette(src)
        choices = self._build_similar_colors(palette)

        dialog = Gtk.Dialog(
            title=f"Colorize - {src.name}", transient_for=self.window, modal=True
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(760, 460)

        area = dialog.get_content_area()
        area.set_spacing(12)
        area.set_margin_top(12)
        area.set_margin_bottom(12)
        area.set_margin_start(12)
        area.set_margin_end(12)

        info = Gtk.Label(
            label="Pick a swatch or use Custom Color wheel to colorize and apply"
        )
        info.set_xalign(0.0)
        area.pack_start(info, False, False, 0)

        strength_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        strength_label = Gtk.Label(label="Strength")
        strength_label.set_xalign(0.0)
        strength_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 10, 100, 1
        )
        strength_scale.set_hexpand(True)
        strength_scale.set_digits(0)
        strength_scale.set_draw_value(True)
        strength_scale.set_value(float(self._get_colorize_strength()))
        strength_scale.connect("value-changed", self.on_colorize_strength_changed)
        strength_row.pack_start(strength_label, False, False, 0)
        strength_row.pack_start(strength_scale, True, True, 0)
        area.pack_start(strength_row, False, False, 0)
        recent_colors = self._get_recent_colorize_swatches()

        notebook = Gtk.Notebook()
        notebook.set_scrollable(True)
        notebook.set_hexpand(True)
        notebook.set_vexpand(True)

        def add_color_tab(title: str, colors):
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            page.set_margin_top(6)
            page.set_margin_bottom(6)
            page.set_margin_start(6)
            page.set_margin_end(6)

            if colors:
                scroller = Gtk.ScrolledWindow()
                scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
                scroller.set_min_content_height(210)
                scroller.set_shadow_type(Gtk.ShadowType.NONE)
                scroller.add(
                    self._build_colorize_chip_flow(
                        colors, str(src), dialog, strength_scale
                    )
                )
                page.pack_start(scroller, True, True, 0)
            else:
                empty = Gtk.Label(label="No swatches yet")
                empty.set_xalign(0.0)
                page.pack_start(empty, True, True, 0)

            notebook.append_page(page, Gtk.Label(label=title))

        add_color_tab("Palette", choices)
        add_color_tab("Recent", recent_colors)

        area.pack_start(notebook, True, True, 0)

        custom_frame = Gtk.Frame(label="Custom Color")
        custom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        custom_box.set_margin_top(8)
        custom_box.set_margin_bottom(8)
        custom_box.set_margin_start(8)
        custom_box.set_margin_end(8)

        color_button = Gtk.ColorButton()
        color_button.set_use_alpha(False)
        color_button.set_title("Pick custom color")
        if palette:
            rgba = Gdk.RGBA()
            if rgba.parse(palette[0]):
                color_button.set_rgba(rgba)

        custom_hex = Gtk.Entry()
        custom_hex.set_editable(False)
        custom_hex.set_width_chars(9)
        custom_hex.set_text(self._rgba_to_hex(color_button.get_rgba()).upper())

        color_button.connect("color-set", self.on_custom_color_changed, custom_hex)

        apply_custom_btn = Gtk.Button(label="Apply Custom")
        apply_custom_btn.set_image(
            Gtk.Image.new_from_icon_name(
                "format-fill-color-symbolic", Gtk.IconSize.BUTTON
            )
        )
        apply_custom_btn.set_always_show_image(True)
        apply_custom_btn.connect(
            "clicked",
            self.on_apply_custom_color_clicked,
            str(src),
            color_button,
            custom_hex,
            dialog,
            strength_scale,
        )

        copy_hex_btn = Gtk.Button(label="Copy Hex")
        copy_hex_btn.set_image(
            Gtk.Image.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.BUTTON)
        )
        copy_hex_btn.set_always_show_image(True)
        copy_hex_btn.connect("clicked", self.on_copy_custom_hex_clicked, custom_hex)

        custom_box.pack_start(color_button, False, False, 0)
        custom_box.pack_start(custom_hex, False, False, 0)
        custom_box.pack_start(copy_hex_btn, False, False, 0)
        custom_box.pack_start(apply_custom_btn, False, False, 0)
        custom_frame.add(custom_box)
        area.pack_start(custom_frame, False, False, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        random_btn = Gtk.Button(label="Randomize")
        random_btn.set_image(
            Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        )
        random_btn.set_always_show_image(True)
        random_btn.connect(
            "clicked", self.on_random_colorize_clicked, str(src), dialog, strength_scale
        )
        preview_btn = Gtk.Button(label="Preview Original")
        preview_btn.connect(
            "clicked", self.on_colorizer_preview_original_clicked, str(src), dialog
        )
        actions.pack_start(random_btn, False, False, 0)
        actions.pack_start(preview_btn, False, False, 0)
        area.pack_start(actions, False, False, 0)

        dialog.connect("response", lambda d, _r: d.destroy())
        dialog.show_all()

    def on_wallpaper_source_toggled(self, switch, _pspec):
        if self._loading_wallpaper_state:
            return
        source = "system" if switch.get_active() else "custom"
        self.wallpaper_service.set_source(source)
        if self.chooser_wallpaper_folder is not None:
            self.chooser_wallpaper_folder.set_sensitive(True)
        if self.label_wallpaper_folder is not None:
            self.label_wallpaper_folder.set_sensitive(True)
        self.reload_wallpapers()

    def on_wallpaper_fill_mode_changed(self, combo):
        if self._loading_wallpaper_state:
            return
        value = combo.get_active_text()
        if value:
            self.wallpaper_service.set_fill_mode(value)

    def on_wallpaper_sort_changed(self, combo):
        if self._loading_wallpaper_state:
            return
        value = combo.get_active_text() or "Name A-Z"
        self.wallpaper_service.set_sort_mode(SORT_LABEL_TO_KEY.get(value, "name_asc"))
        self.reload_wallpapers()

    def on_wallpaper_search_changed(self, _entry):
        if self._loading_wallpaper_state:
            return
        self.reload_wallpapers()

    def _queue_thumb_reload(self):
        if self._thumb_size_reload_source is not None:
            GLib.source_remove(self._thumb_size_reload_source)
        self._thumb_size_reload_source = GLib.timeout_add(150, self._run_thumb_reload)

    def _run_thumb_reload(self):
        self._thumb_size_reload_source = None
        self.reload_wallpapers()
        return False

    def on_wallpaper_thumb_size_changed(self, scale):
        if self._loading_wallpaper_state:
            return
        size = int(round(scale.get_value()))
        size = max(180, min(420, size))
        if size == self.thumb_width:
            return
        self.thumb_width = size
        self._update_wallpaper_grid_columns()
        self.wallpaper_service.set_thumb_size(size)
        self._queue_thumb_reload()

    def on_wallpaper_folder_selected(self, chooser):
        if self._loading_wallpaper_state:
            return
        folder = chooser.get_filename()
        if not folder:
            return

        self.wallpaper_service.set_custom_dir(Path(folder))
        if self.switch_wallpaper_system_source is not None:
            if self.switch_wallpaper_system_source.get_active():
                self.switch_wallpaper_system_source.set_active(False)
            else:
                self.reload_wallpapers()

    def on_wallpaper_apply_clicked(self, _button, path_str: str):
        ok, message = self.wallpaper_service.apply_wallpaper(Path(path_str))
        self._show_message(message)
        if not ok:
            dialog = Gtk.MessageDialog(
                transient_for=self.window,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=message,
            )
            dialog.run()
            dialog.destroy()

    def on_wallpaper_name_activate(
        self,
        _widget,
        event,
        path_str: str,
        label_widget=None,
        is_colorized: bool = False,
        fallback_name: str | None = None,
    ):
        if event is None:
            return False
        if getattr(event, "button", 0) != 1:
            return False

        event_type = getattr(event, "type", None)
        double_press = getattr(Gdk.EventType, "_2BUTTON_PRESS", None)
        if event_type not in (Gdk.EventType.BUTTON_PRESS, double_press):
            return False

        now_us = GLib.get_monotonic_time()
        if now_us - self._last_name_edit_us < 300_000:
            return True
        self._last_name_edit_us = now_us

        self.on_wallpaper_edit_name_clicked(
            None, path_str, label_widget, is_colorized, fallback_name
        )
        return True

    def on_wallpaper_edit_name_clicked(
        self,
        _button,
        path_str: str,
        label_widget=None,
        is_colorized: bool = False,
        fallback_name: str | None = None,
    ):
        path = Path(path_str)
        if fallback_name is None or not str(fallback_name).strip():
            fallback_name = path.name

        current = self.wallpaper_service.get_display_name(path, fallback_name)

        dialog = Gtk.Dialog(
            title=f"Edit Name - {path.name}", transient_for=self.window, modal=True
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Reset", 1)
        save_btn = dialog.add_button("Save", Gtk.ResponseType.OK)
        save_btn.get_style_context().add_class("suggested-action")
        dialog.set_default_size(420, 140)

        area = dialog.get_content_area()
        area.set_spacing(8)
        area.set_margin_top(10)
        area.set_margin_bottom(10)
        area.set_margin_start(10)
        area.set_margin_end(10)

        hint = Gtk.Label(
            label="Edit display name only (original filename stays unchanged)."
        )
        hint.set_xalign(0.0)
        area.pack_start(hint, False, False, 0)

        entry = Gtk.Entry()
        entry.set_text(current)
        entry.set_activates_default(True)
        dialog.set_default_response(Gtk.ResponseType.OK)
        area.pack_start(entry, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        new_name = entry.get_text()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            saved = self.wallpaper_service.set_display_name(path, new_name)
            if not saved:
                saved = fallback_name
            message = f"Name updated: {saved}"
        elif response == 1:
            self.wallpaper_service.clear_display_name(path)
            saved = fallback_name
            message = f"Name reset: {saved}"
        else:
            return

        if is_colorized and "(colorized)" not in saved.lower():
            shown = f"{saved} (Colorized)"
        else:
            shown = saved

        if label_widget is not None:
            label_widget.set_text(shown)

        self._show_message(message)

    def on_wallpaper_delete_clicked(self, _button, path_str: str, flow_child=None):
        path = Path(path_str)
        if not path.exists():
            self._show_message("Delete failed: file missing")
            return

        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=f"Delete wallpaper '{path.name}'?",
        )
        dialog.format_secondary_text("This permanently removes the file from disk.")
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        delete_btn = dialog.add_button("Delete", Gtk.ResponseType.OK)
        delete_btn.get_style_context().add_class("destructive-action")

        response = dialog.run()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return

        ok, message = self.wallpaper_service.delete_wallpaper(path)
        if not ok:
            self._show_message(message)
            err = Gtk.MessageDialog(
                transient_for=self.window,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=message,
            )
            err.run()
            err.destroy()
            return

        self.wallpaper_service.clear_display_name(path)
        self._show_message(message)

        if flow_child is not None and self.wallpaper_flowbox is not None:
            try:
                self.wallpaper_flowbox.remove(flow_child)
                if self.label_wallpaper_count is not None:
                    count = len(self.wallpaper_flowbox.get_children())
                    self.label_wallpaper_count.set_text(f"{count} wallpapers")
                return
            except Exception:
                pass

        self.reload_wallpapers()

    def on_wallpaper_card_hover(self, _widget, _event, target_widget, show: bool):
        if show:
            target_widget.show()
        else:
            target_widget.hide()
        return False

    def init_gtk_themes_page(self):
        assert self.builder is not None
        self.flowbox_gtk_themes = self.builder.get_object("flowbox_gtk_themes")
        self.entry_gtk_themes_search = self.builder.get_object(
            "entry_gtk_themes_search"
        )
        self.combo_gtk_themes_filter = self.builder.get_object(
            "combo_gtk_themes_filter"
        )
        self.gtk_theme_preview_container = self.builder.get_object(
            "gtk_theme_preview_container"
        )

        if self.entry_gtk_themes_search:
            self.entry_gtk_themes_search.connect(
                "changed", lambda w: self.reload_gtk_themes()
            )
        if self.combo_gtk_themes_filter:
            self.combo_gtk_themes_filter.connect(
                "changed", lambda w: self.reload_gtk_themes()
            )

        if self.gtk_theme_preview_container:
            self._build_gtk_preview_mockup()
            # Initial preview of current theme
            current = self.gtk_theme_service.get_current_theme()
            if current:
                self._update_gtk_theme_preview(current)

        self.reload_gtk_themes()

    def reload_gtk_themes(self):
        if self.flowbox_gtk_themes is None:
            return
        self._clear_widget_children(self.flowbox_gtk_themes)
        self._gtk_theme_reload_id += 1
        reload_id = self._gtk_theme_reload_id

        query = ""
        if self.entry_gtk_themes_search:
            query = self.entry_gtk_themes_search.get_text().lower().strip()

        filter_type = "all"
        if self.combo_gtk_themes_filter:
            idx = self.combo_gtk_themes_filter.get_active()
            if idx == 1:
                filter_type = "light"
            elif idx == 2:
                filter_type = "dark"

        thread = threading.Thread(
            target=self._reload_gtk_themes_thread,
            args=(query, filter_type, reload_id),
            daemon=True,
        )
        thread.start()

    def _reload_gtk_themes_thread(self, query, filter_type, reload_id):
        themes = self.gtk_theme_service.list_themes()
        current = self.gtk_theme_service.get_current_theme()
        if reload_id != self._gtk_theme_reload_id:
            return
        self._gtk_theme_meta_by_name = {t.name: t for t in themes}

        # Filtering
        if query:
            themes = [t for t in themes if query in t.name.lower()]
        if filter_type != "all":
            themes = [t for t in themes if t.type == filter_type]

        def add_theme_card(theme, is_current):
            if (
                reload_id != self._gtk_theme_reload_id
                or self.flowbox_gtk_themes is None
            ):
                return False
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.get_style_context().add_class("theme-card")
            if is_current:
                card.get_style_context().add_class("theme-card-active")

            # Top row: title + badge
            top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            title = Gtk.Label(label=theme.name)
            title.get_style_context().add_class("theme-title")
            title.set_xalign(0.0)
            title.set_ellipsize(Pango.EllipsizeMode.END)
            top_row.pack_start(title, True, True, 0)

            badge = Gtk.Label(label=theme.type.upper())
            badge.get_style_context().add_class("theme-type-badge")
            top_row.pack_start(badge, False, False, 0)
            card.pack_start(top_row, False, False, 0)

            # Color row: 3 chips
            color_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            for ckey in ["bg", "fg", "accent"]:
                chip = Gtk.DrawingArea()
                chip.set_size_request(14, 14)
                chip.get_style_context().add_class("theme-chip")
                chip.connect(
                    "draw", self._draw_swatch, theme.colors.get(ckey, "#5ba1ea")
                )
                color_row.pack_start(chip, False, False, 0)

            card.pack_start(color_row, False, False, 0)

            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            preview_btn = Gtk.Button(label="Preview")
            preview_btn.get_style_context().add_class("theme-apply-button")
            preview_btn.connect(
                "clicked", self.on_gtk_theme_preview_clicked, theme.name
            )
            actions.pack_start(preview_btn, True, True, 0)

            apply_btn = Gtk.Button(label="Apply")
            apply_btn.get_style_context().add_class("suggested-action")
            apply_btn.get_style_context().add_class("theme-apply-button")
            apply_btn.connect("clicked", self.on_gtk_theme_apply_clicked, theme.name)
            actions.pack_start(apply_btn, True, True, 0)

            card.pack_start(actions, False, False, 0)

            event_box = Gtk.EventBox()
            event_box.add(card)
            event_box.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK)

            def _on_enter(_w, _e, theme_name):
                self._update_gtk_theme_preview(theme_name)
                return False

            event_box.connect("enter-notify-event", _on_enter, theme.name)

            child = Gtk.FlowBoxChild()
            child.add(event_box)
            self.flowbox_gtk_themes.add(child)
            child.show_all()
            return False

        for theme in themes:
            GLib.idle_add(add_theme_card, theme, theme.name == current)

    def _build_gtk_preview_mockup(self):
        container = self.gtk_theme_preview_container
        if container is None:
            return

        mockup = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        mockup.set_margin_top(15)
        mockup.set_margin_bottom(15)
        mockup.set_margin_start(15)
        mockup.set_margin_end(15)

        # Tabs
        notebook = Gtk.Notebook()
        page1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page1.set_margin_top(10)
        page1.set_margin_bottom(10)
        page1.set_margin_start(10)
        page1.set_margin_end(10)

        # Inner widgets
        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row1.pack_start(Gtk.CheckButton(label="Check Button"), False, False, 0)
        row1.pack_start(Gtk.RadioButton(label="Radio Button"), False, False, 0)
        page1.add(row1)

        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row2.pack_start(Gtk.Entry(text="Text entry..."), True, True, 0)
        page1.add(row2)

        progress = Gtk.ProgressBar()
        progress.set_fraction(0.65)
        page1.add(progress)

        notebook.append_page(page1, Gtk.Label(label="Demo Widgets"))
        notebook.append_page(
            Gtk.Label(label="Tab 2 Content"), Gtk.Label(label="Page 2")
        )

        mockup.pack_start(notebook, True, True, 0)

        # Buttons at bottom
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_row.set_halign(Gtk.Align.END)
        btn_row.pack_start(Gtk.Button(label="Cancel"), False, False, 0)
        btn_row.pack_start(Gtk.Button(label="OK"), False, False, 0)
        mockup.pack_start(btn_row, False, False, 0)

        container.add(mockup)
        mockup.show_all()

    def _update_gtk_theme_preview(self, theme_name):
        container = self.gtk_theme_preview_container
        if container is None:
            return

        theme = self._gtk_theme_meta_by_name.get(theme_name)
        if theme is None:
            themes = self.gtk_theme_service.list_themes()
            self._gtk_theme_meta_by_name = {t.name: t for t in themes}
            theme = self._gtk_theme_meta_by_name.get(theme_name)
        if theme is None:
            return

        colors = theme.colors if isinstance(theme.colors, dict) else {}
        bg = str(colors.get("bg", "#2f343f"))
        fg = str(colors.get("fg", "#e6eaf0"))
        accent = str(colors.get("accent", "#5ba1ea"))

        light_theme = self._is_light_hex(bg)
        surface = self._mix_hex(bg, "#000000", 0.06 if light_theme else 0.18)
        border = (
            self._mix_hex(bg, "#000000", 0.20)
            if light_theme
            else self._mix_hex(bg, "#ffffff", 0.20)
        )
        tab_active = self._mix_hex(accent, "#ffffff", 0.18 if light_theme else 0.10)
        button_text = "#111111" if self._is_light_hex(accent) else "#ffffff"

        css = f"""
        #gtk_theme_preview_container {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: 8px;
        }}
        #gtk_theme_preview_container * {{
            color: {fg};
        }}
        #gtk_theme_preview_container entry {{
            background-color: {surface};
            border: 1px solid {border};
            color: {fg};
        }}
        #gtk_theme_preview_container notebook {{
            background-color: {surface};
            border: 1px solid {border};
        }}
        #gtk_theme_preview_container notebook header tab:checked {{
            background-color: {tab_active};
        }}
        #gtk_theme_preview_container button {{
            background-image: none;
            background-color: {accent};
            color: {button_text};
            border: 1px solid {border};
        }}
        #gtk_theme_preview_container progressbar trough {{
            background-color: {surface};
        }}
        #gtk_theme_preview_container progressbar progress {{
            background-color: {accent};
        }}
        """

        try:
            self.gtk_theme_preview_provider.load_from_data(css.encode("utf-8"))
            ctx = container.get_style_context()
            if self._gtk_theme_preview_provider_attached:
                ctx.remove_provider(self.gtk_theme_preview_provider)
            ctx.add_provider(
                self.gtk_theme_preview_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            self._gtk_theme_preview_provider_attached = True
        except Exception as e:
            print(f"Failed to build theme preview CSS: {e}")

    def on_gtk_theme_preview_clicked(self, _button, theme_name):
        self._update_gtk_theme_preview(theme_name)
        self._show_message(f"Previewing GTK theme: {theme_name}")

    def on_gtk_theme_apply_clicked(self, _button, theme_name):
        ok, message = self.gtk_theme_service.apply_theme(theme_name)
        self._show_message(message)
        if ok:
            self.reload_gtk_themes()
            self._update_gtk_theme_preview(theme_name)
        else:
            dialog = Gtk.MessageDialog(
                transient_for=self.window,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=message,
            )
            dialog.run()
            dialog.destroy()

    def init_window_themes_page(self):
        assert self.builder is not None
        self.flowbox_window_themes = self.builder.get_object("flowbox_window_themes")
        self.reload_window_themes()

    def reload_window_themes(self):
        if self.flowbox_window_themes is None:
            return
        self._clear_widget_children(self.flowbox_window_themes)
        thread = threading.Thread(target=self._reload_window_themes_thread, daemon=True)
        thread.start()

    def _reload_window_themes_thread(self):
        themes = self.window_theme_service.list_themes()
        current = self.window_theme_service.get_current_theme()

        def add_theme_card(theme, is_current):
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.get_style_context().add_class("theme-card")
            if is_current:
                card.get_style_context().add_class("theme-card-active")

            title = Gtk.Label(label=theme.name)
            title.get_style_context().add_class("theme-title")
            title.set_xalign(0.5)
            card.pack_start(title, True, True, 0)

            apply_btn = Gtk.Button(label="Apply")
            apply_btn.get_style_context().add_class("suggested-action")
            apply_btn.get_style_context().add_class("theme-apply-button")
            apply_btn.connect("clicked", self.on_window_theme_apply_clicked, theme.name)
            card.pack_start(apply_btn, False, False, 0)

            child = Gtk.FlowBoxChild()
            child.add(card)
            self.flowbox_window_themes.add(child)
            child.show_all()
            return False

        for theme in themes:
            GLib.idle_add(add_theme_card, theme, theme.name == current)

    def on_window_theme_apply_clicked(self, _button, theme_name):
        ok, message = self.window_theme_service.apply_theme(theme_name)
        self._show_message(message)
        if ok:
            self.current_theme_name = theme_name
            self.reload_window_themes()
        else:
            dialog = Gtk.MessageDialog(
                transient_for=self.window,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=message,
            )
            dialog.run()
            dialog.destroy()

    def init_wallpaper_page(self):
        assert self.builder is not None
        self.switch_wallpaper_system_source = self.builder.get_object(
            "switch_wallpaper_system_source"
        )
        self.combo_wallpaper_fill_mode = self.builder.get_object(
            "combo_wallpaper_fill_mode"
        )
        self.combo_wallpaper_sort = self.builder.get_object("combo_wallpaper_sort")
        self.entry_wallpaper_search = self.builder.get_object("entry_wallpaper_search")
        self.chooser_wallpaper_folder = self.builder.get_object(
            "chooser_wallpaper_folder"
        )
        self.button_top_settings = self.builder.get_object("button_top_settings")
        self.label_wallpaper_folder = self.builder.get_object("label_wallpaper_folder")
        self.wallpaper_view_stack = self.builder.get_object("wallpaper_view_stack")
        self.wallpaper_view_switcher = self.builder.get_object(
            "wallpaper_view_switcher"
        )
        self.wallpaper_grid_scroller = self.builder.get_object(
            "wallpaper_grid_scroller"
        )
        self.wallpaper_flowbox = self.builder.get_object("wallpaper_flowbox")
        self.label_wallpaper_count = self.builder.get_object("label_wallpaper_count")
        self.scale_wallpaper_thumb_size = self.builder.get_object(
            "scale_wallpaper_thumb_size"
        )

        if self.switch_wallpaper_system_source is not None:
            self.switch_wallpaper_system_source.connect(
                "notify::active", self.on_wallpaper_source_toggled
            )
        if self.combo_wallpaper_fill_mode is not None:
            self.combo_wallpaper_fill_mode.connect(
                "changed", self.on_wallpaper_fill_mode_changed
            )
        if self.combo_wallpaper_sort is not None:
            self.combo_wallpaper_sort.connect("changed", self.on_wallpaper_sort_changed)
        if self.entry_wallpaper_search is not None:
            self.entry_wallpaper_search.connect(
                "changed", self.on_wallpaper_search_changed
            )
        if self.chooser_wallpaper_folder is not None:
            self.chooser_wallpaper_folder.connect(
                "file-set", self.on_wallpaper_folder_selected
            )
        if self.button_top_settings is not None:
            self.button_top_settings.connect("clicked", self.on_top_settings_clicked)
        if self.scale_wallpaper_thumb_size is not None:
            self.scale_wallpaper_thumb_size.connect(
                "value-changed", self.on_wallpaper_thumb_size_changed
            )
        if self.wallpaper_grid_scroller is not None:
            self.wallpaper_grid_scroller.set_policy(
                Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
            )
            if hasattr(self.wallpaper_grid_scroller, "set_propagate_natural_width"):
                self.wallpaper_grid_scroller.set_propagate_natural_width(False)
            self.wallpaper_grid_scroller.connect(
                "size-allocate", self.on_wallpaper_grid_scroller_size_allocate
            )

        if self.wallpaper_flowbox is not None:
            self.wallpaper_flowbox.set_column_spacing(10)
            self.wallpaper_flowbox.set_row_spacing(12)
            self.wallpaper_flowbox.set_margin_top(10)
            self.wallpaper_flowbox.set_margin_bottom(10)
            self.wallpaper_flowbox.set_margin_start(10)
            self.wallpaper_flowbox.set_margin_end(10)
            self.wallpaper_flowbox.set_min_children_per_line(1)
            self.wallpaper_flowbox.set_max_children_per_line(3)
            self._update_wallpaper_grid_columns()

        # Grid-only mode: hide switcher and pin stack to grid.
        if self.wallpaper_view_switcher is not None:
            self.wallpaper_view_switcher.hide()
        if self.wallpaper_view_stack is not None:
            self.wallpaper_view_stack.set_visible_child_name("grid")

        self.sync_wallpaper_controls_from_settings()
        self.reload_wallpapers()

    def sync_wallpaper_controls_from_settings(self):
        self._loading_wallpaper_state = True
        try:
            source = self.wallpaper_service.get_source()
            fill_mode = self.wallpaper_service.get_fill_mode()
            sort_mode = self.wallpaper_service.get_sort_mode()
            custom_dirs = self.wallpaper_service.get_custom_dirs()

            is_custom = source == "custom"
            if self.switch_wallpaper_system_source is not None:
                self.switch_wallpaper_system_source.set_active(source == "system")

            if self.chooser_wallpaper_folder is not None:
                self.chooser_wallpaper_folder.set_sensitive(True)
                if custom_dirs:
                    custom_path = custom_dirs[0]
                    if custom_path.exists():
                        self.chooser_wallpaper_folder.set_filename(str(custom_path))

            if self.label_wallpaper_folder is not None:
                self.label_wallpaper_folder.set_sensitive(True)

            if self.combo_wallpaper_fill_mode is not None:
                idx = FILL_MODES.index(fill_mode) if fill_mode in FILL_MODES else 0
                self.combo_wallpaper_fill_mode.set_active(idx)
            self.thumb_width = self.wallpaper_service.get_thumb_size()
            if self.scale_wallpaper_thumb_size is not None:
                self.scale_wallpaper_thumb_size.set_value(float(self.thumb_width))
        finally:
            self._loading_wallpaper_state = False

    def on_wallpaper_grid_scroller_size_allocate(self, _widget, allocation):
        self._update_wallpaper_grid_columns(int(allocation.width))

    def _update_wallpaper_grid_columns(self, viewport_width: int | None = None):
        if self.wallpaper_flowbox is None:
            return

        if viewport_width is None and self.wallpaper_grid_scroller is not None:
            viewport_width = int(self.wallpaper_grid_scroller.get_allocated_width())

        if viewport_width is None or viewport_width <= 0:
            return

        col_spacing = int(self.wallpaper_flowbox.get_column_spacing())
        side_margins = int(
            self.wallpaper_flowbox.get_margin_start()
            + self.wallpaper_flowbox.get_margin_end()
        )
        available = max(1, viewport_width - side_margins)

        # Keep card footers fully visible in narrower layouts.
        card_width = max(230, min(420, int(self.thumb_width)))
        columns = int((available + col_spacing) // max(1, card_width + col_spacing))
        columns = max(1, min(3, columns))
        self.wallpaper_flowbox.set_max_children_per_line(columns)

    def _sorted_filtered_wallpapers(self):
        entries = self.wallpaper_service.list_wallpapers()
        query = ""
        if self.entry_wallpaper_search is not None:
            query = self.entry_wallpaper_search.get_text().strip().lower()

        if query:
            entries = [
                e
                for e in entries
                if query in e.name.lower()
                or query in str(e.path).lower()
                or query in self._compose_wallpaper_display_name(e).lower()
            ]

        mode = self.wallpaper_service.get_sort_mode()

        def mtime(entry):
            try:
                return entry.path.stat().st_mtime
            except Exception:
                return 0

        if mode == "name_desc":
            entries.sort(key=lambda e: e.name.lower(), reverse=True)
        elif mode == "newest":
            entries.sort(key=mtime, reverse=True)
        elif mode == "oldest":
            entries.sort(key=mtime)
        else:
            entries.sort(key=lambda e: e.name.lower())

        return entries

    def reload_wallpapers(self):
        if self.wallpaper_flowbox is None:
            return

        with self._reload_lock:
            self.current_reload_id += 1
            reload_id = self.current_reload_id

        self._clear_widget_children(self.wallpaper_flowbox)
        if self.label_wallpaper_count is not None:
            self.label_wallpaper_count.set_text("Loading...")

        thread = threading.Thread(
            target=self._reload_wallpapers_thread, args=(reload_id,), daemon=True
        )
        thread.start()

    def _reload_wallpapers_thread(self, reload_id):
        entries = self._sorted_filtered_wallpapers()

        def update_count():
            if self.current_reload_id == reload_id and self.label_wallpaper_count:
                self.label_wallpaper_count.set_text(f"{len(entries)} wallpapers")
            return False

        GLib.idle_add(update_count)

        thumb_w = max(180, min(420, int(self.thumb_width)))
        thumb_h = max(100, int(thumb_w * 9 / 16))

        for entry in entries:
            if self.current_reload_id != reload_id:
                return

            # Heavy lifting in worker thread
            palette = self._extract_palette(entry.path)
            pixbuf = self._get_thumbnail_pixbuf(entry.path, thumb_w, thumb_h)

            def add_wallpaper_card(e, p, pb):
                if self.current_reload_id != reload_id:
                    return False

                flow_child = Gtk.FlowBoxChild()

                card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

                card_img = self._build_rounded_thumbnail_widget(
                    pb, thumb_w, thumb_h, 9.0
                )
                is_colorized = self._is_colorized_path(e.path) or str(
                    e.name
                ).lower().startswith("colorized/")

                media_widget = card_img
                if is_colorized:
                    overlay = Gtk.Overlay()
                    overlay.add(card_img)

                    badge = Gtk.Label(label="COLORIZED")
                    badge.get_style_context().add_class("colorized-badge")
                    badge.set_halign(Gtk.Align.START)
                    badge.set_valign(Gtk.Align.START)
                    badge.set_margin_top(8)
                    badge.set_margin_start(8)
                    overlay.add_overlay(badge)
                    media_widget = overlay

                # Clean filename + optional custom display name
                clean_name = Path(e.name).name
                display_name = self._compose_wallpaper_display_name(e, is_colorized)
                card_name = Gtk.Label(label=display_name)
                card_name.get_style_context().add_class("wallpaper-title")
                card_name.set_xalign(0.0)
                card_name.set_ellipsize(Pango.EllipsizeMode.END)
                card_name.set_max_width_chars(max(18, int(thumb_w / 12)))

                media_click = Gtk.EventBox()
                media_click.set_visible_window(False)
                media_click.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
                media_click.set_tooltip_text("Click or double-click to edit name")
                media_click.connect(
                    "button-press-event",
                    self.on_wallpaper_name_activate,
                    str(e.path),
                    card_name,
                    is_colorized,
                    clean_name,
                )
                media_click.add(media_widget)

                name_click = Gtk.EventBox()
                name_click.set_visible_window(False)
                name_click.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
                name_click.set_tooltip_text("Click or double-click to edit name")
                name_click.connect(
                    "button-press-event",
                    self.on_wallpaper_name_activate,
                    str(e.path),
                    card_name,
                    is_colorized,
                    clean_name,
                )
                name_click.add(card_name)

                swatch_size = 20 if thumb_w >= 240 else 18 if thumb_w >= 210 else 16
                actions_row_min = (4 * 28) + (3 * 4)
                swatch_slot = swatch_size + 3
                swatch_budget = max(0, thumb_w - actions_row_min - 8)
                max_swatches = max(2, swatch_budget // max(1, swatch_slot))
                swatches = self._build_swatch_row(
                    p[:max_swatches], swatch_size=swatch_size, spacing=3
                )

                def make_action_icon_button(icon_name: str, tooltip: str):
                    btn = Gtk.Button()
                    img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
                    img.set_pixel_size(15)
                    img.set_halign(Gtk.Align.CENTER)
                    img.set_valign(Gtk.Align.CENTER)
                    btn.set_image(img)
                    btn.set_always_show_image(True)
                    btn.set_tooltip_text(tooltip)
                    btn.set_relief(Gtk.ReliefStyle.NONE)
                    btn.get_style_context().add_class("overlay-action-button")
                    return btn

                preview_button = make_action_icon_button(
                    "view-preview-symbolic", "Preview"
                )
                preview_button.connect(
                    "clicked", self.on_wallpaper_preview_clicked, str(e.path)
                )

                colorize_button = make_action_icon_button(
                    "format-fill-color-symbolic", "Colorize"
                )
                colorize_button.connect(
                    "clicked", self.on_wallpaper_colorize_clicked, str(e.path)
                )
                apply_button = make_action_icon_button(
                    "object-select-symbolic", "Apply wallpaper"
                )
                apply_button.connect(
                    "clicked", self.on_wallpaper_apply_clicked, str(e.path)
                )

                delete_button = make_action_icon_button(
                    "edit-delete-symbolic", "Delete wallpaper"
                )
                delete_button.connect(
                    "clicked", self.on_wallpaper_delete_clicked, str(e.path), flow_child
                )

                actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                actions_row.pack_start(preview_button, False, False, 0)
                actions_row.pack_start(colorize_button, False, False, 0)
                actions_row.pack_start(apply_button, False, False, 0)
                actions_row.pack_start(delete_button, False, False, 0)

                footer_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                footer_row.set_hexpand(True)
                spacer = Gtk.Box()
                spacer.set_hexpand(True)
                footer_row.pack_start(swatches, False, False, 0)
                footer_row.pack_start(spacer, True, True, 0)
                footer_row.pack_start(actions_row, False, False, 0)

                card.pack_start(media_click, False, False, 0)
                card.pack_start(name_click, False, False, 0)
                card.pack_start(footer_row, False, False, 0)

                flow_child.add(card)
                self.wallpaper_flowbox.add(flow_child)
                flow_child.show_all()
                return False

            GLib.idle_add(add_wallpaper_card, entry, palette, pixbuf)

    def do_activate(self):
        if self.window is not None:
            self.window.present()
            return

        self.builder = Gtk.Builder()
        assert self.builder is not None
        loaded_files = []

        for candidate in (PRIMARY_GLADE, BACKUP_GLADE):
            if not candidate.exists():
                continue
            self.builder.add_from_file(str(candidate))
            loaded_files.append(candidate)
            self.window = find_glade_window(self.builder)
            if self.window is not None:
                break

        if self.window is None:
            files = ", ".join(str(p) for p in loaded_files) or "no files"
            raise RuntimeError(f"No GtkWindow/GtkApplicationWindow found in: {files}")

        if isinstance(self.window, Gtk.ApplicationWindow):
            self.window.set_application(self)
        self.window.set_resizable(True)
        self._register_icon_search_paths()

        assert self.builder is not None
        self.sidebar_list = self.builder.get_object("sidebar_list")
        self.content_stack = self.builder.get_object("content_stack")

        if self.sidebar_list and self.content_stack:
            self.sidebar_list.connect("row-selected", self.on_sidebar_row_selected)
            first_row = self.sidebar_list.get_row_at_index(0)
            if first_row is not None:
                self.sidebar_list.select_row(first_row)

        self._ensure_css()
        self.init_top_mode_bar()
        self.init_wallpaper_page()
        self.init_window_themes_page()
        self.init_gtk_themes_page()
        self.window.present()
        GLib.timeout_add(120, self._lock_sidebar_width_cap_from_current)


def main():
    app = ArchCrafter2App()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
