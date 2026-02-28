#!/usr/bin/env python3
import colorsys
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import gi

from backend import (
    GtkThemeService,
    InterfaceThemeService,
    ServiceContainer,
    SettingsStore,
    WallpaperService,
    WindowThemeService,
    detect_external_tools,
)
from pages import create_page_instance, get_all_pages, get_row_to_page_map

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")
gi.require_version("Gdk", "3.0")
from gi.repository import (  # noqa: E402  # pyright: ignore[reportAttributeAccessIssue]
    Gdk,
    GdkPixbuf,
    GLib,
    Gtk,
    Pango,
)

BASE_DIR = Path(__file__).resolve().parent
PRIMARY_GLADE = BASE_DIR / "Archcrafter2.glade"
APP_CSS_PATH = BASE_DIR / "assets" / "app.css"
GTK_PREVIEW_RENDERER = BASE_DIR / "backend" / "gtk_preview_renderer.py"
GTK_PREVIEW_CARD_SIZE = (320, 150)
GTK_PREVIEW_PANEL_SIZE = (640, 420)

FILL_MODES = ["zoom-fill", "centered", "scaled", "tiled", "auto"]
SORT_KEYS = ["name_asc", "name_desc", "newest", "oldest"]
SORT_LABEL_TO_KEY = {
    "Name A-Z": "name_asc",
    "Name Z-A": "name_desc",
    "Newest": "newest",
    "Oldest": "oldest",
}

# Sidebar should stay compact; do not allow expanding beyond this width.
# Keep right-side cap, but allow collapsing left for more content space.
SIDEBAR_WIDTH_MIN = 0
SIDEBAR_WIDTH_MAX = 280
SIDEBAR_COLLAPSED_WIDTH = 52

ROW_TO_PAGE = {}  # Generated from pages


def _build_row_to_page():
    global ROW_TO_PAGE
    ROW_TO_PAGE = get_row_to_page_map()


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
        (
            "builder_menus",
            "Menus",
            "ac-jgmenu-symbolic",
            "Build and customize launcher/menu presets",
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
        (
            "presets_menus",
            "Menu Presets",
            "ac-jgmenu-symbolic",
            "Saved launcher and menu preset packs",
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
        super().__init__(application_id="org.loom.app")
        self.window: Optional[Gtk.Window] = None
        self.builder: Optional[Gtk.Builder] = None
        self.sidebar_list: Optional[Gtk.ListBox] = None
        self.content_stack: Optional[Gtk.Stack] = None
        self.status_infobar: Optional[Gtk.InfoBar] = None
        self.status_message_label: Optional[Gtk.Label] = None
        self._status_hide_source: Optional[int] = None

        # initialize services via centralized container for easier testing and
        # future dependency management.  individual attributes are kept for
        # backward compatibility with legacy method calls spread throughout
        # this monolithic application.
        self.services = ServiceContainer(BASE_DIR, BASE_DIR / "settings.json")
        # expose common service shortcuts on the app object
        self.settings = self.services.settings
        self.wallpaper_service = self.services.wallpapers
        self.window_theme_service = self.services.window_themes
        self.gtk_theme_service = self.services.gtk_themes
        self.interface_theme_service = self.services.interface_themes

        _build_row_to_page()
        self.pages: dict[str, object] = {}
        self._init_page_registry()

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
        self.global_actions_bar = None
        self.top_mode_right_actions = None
        self.sidebar_header_box = None
        self.sidebar_scroller = None
        self.button_sidebar_toggle = None
        self._sidebar_toggle_handler_id = 0
        self._sidebar_toggle_syncing = False
        self._sidebar_restore_width = 260
        self._suppress_sidebar_width_save = False
        self.root_hbox = None
        self.main_paned = None
        self.builder_sidebar_list: Optional[Gtk.ListBox] = None
        self.presets_sidebar_list: Optional[Gtk.ListBox] = None
        self.active_top_mode = "mixer"
        self._mode_sidebar_selection = {
            "builder": "builder_home",
            "presets": "presets_home",
        }
        self._last_sidebar_row_name = "row_wallpapers"
        self._last_sidebar_page_name = "wallpapers"
        self._last_non_settings_sidebar_row_name = "row_wallpapers"
        self._last_non_settings_sidebar_page_name = "wallpapers"
        self._sidebar_width_save_source = None
        self._pending_sidebar_width = None
        self._sidebar_width_cap = None
        self._gtk_theme_meta_by_name = {}
        self._icon_search_paths_registered = False

        self.thumb_width = self.wallpaper_service.get_thumb_size()
        self._thumb_size_reload_source = None

        # keep flags used by UI logic
        self._loading_wallpaper_state = False
        self._dependency_warning_shown = False
        self._preview_window = None
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
            self._last_sidebar_row_name = row_id
            self._last_sidebar_page_name = page_name
            if page_name != "settings":
                self._last_non_settings_sidebar_row_name = row_id
                self._last_non_settings_sidebar_page_name = page_name
            self.content_stack.set_visible_child_name(page_name)

            page = self.pages.get(page_name)
            if page and hasattr(page, "on_activate"):
                page.on_activate(self)

            if page_name == "panels":
                self.refresh_bar_page_state()
                self._ensure_bar_preview_refresh(True)
            elif page_name == "menu":
                self.reload_menu_presets()
                self._ensure_bar_preview_refresh(False)
            else:
                self._ensure_bar_preview_refresh(False)

    def _select_sidebar_row_by_name(self, row_name: str) -> None:
        if self.sidebar_list is None:
            return
        for row in self.sidebar_list.get_children():
            if Gtk.Buildable.get_name(row) == row_name:
                self.sidebar_list.select_row(row)
                break

    def _init_page_registry(self) -> None:
        """Initialize all page instances."""
        for page_id in get_all_pages():
            self.pages[page_id] = create_page_instance(page_id, self)

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

            row.mode_item_id = item_id
            row.mode_item_title = title
            row.mode_item_subtitle = subtitle

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
            if str(getattr(row, "mode_item_id", "") or "") == item_id:
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
        title = str(getattr(row, "mode_item_title", "") or mode.title())
        subtitle = str(getattr(row, "mode_item_subtitle", "") or "")
        return (title, subtitle)

    def on_mode_sidebar_row_selected(self, _listbox, row, mode: str):
        if row is None:
            return
        item_id = str(getattr(row, "mode_item_id", "") or "").strip()
        if item_id:
            self._mode_sidebar_selection[mode] = item_id
        if self.active_top_mode != mode:
            return
        if self.mode_placeholder_title is not None:
            self.mode_placeholder_title.set_text(
                str(getattr(row, "mode_item_title", "") or mode.title())
            )
        if self.mode_placeholder_subtitle is not None:
            self.mode_placeholder_subtitle.set_text(
                str(getattr(row, "mode_item_subtitle", "") or "")
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
        self.button_sidebar_toggle = self.builder.get_object("button_sidebar_toggle")
        self.button_top_settings = self.builder.get_object("button_top_settings")
        icon_top_settings = self.builder.get_object("icon_top_settings")
        self.global_actions_bar = self.builder.get_object("global_actions_bar")
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
        self._install_sidebar_header_toggle()
        self._ensure_resizable_layout()
        self._arrange_top_mode_actions()
        self._bind_sidebar_toggle()

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

        if icon_top_settings is not None:
            icon_top_settings.set_pixel_size(21)
        if self.button_top_settings is not None:
            self.button_top_settings.set_margin_start(2)
            self.button_top_settings.set_margin_end(0)
            self.button_top_settings.set_size_request(34, 30)

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

    def _install_sidebar_header_toggle(self):
        if self.sidebar_box is None or self.button_sidebar_toggle is None:
            return

        if self.sidebar_header_box is None:
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            header.get_style_context().add_class("sidebar-header")
            header.set_margin_top(6)
            header.set_margin_bottom(6)
            header.set_margin_start(6)
            header.set_margin_end(6)
            header.set_hexpand(True)

            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            header.pack_end(spacer, True, True, 0)
            self.sidebar_header_box = header

        parent = self.button_sidebar_toggle.get_parent()
        if parent is not None:
            parent.remove(self.button_sidebar_toggle)
        if self.sidebar_header_box is not None:
            self.sidebar_header_box.pack_start(
                self.button_sidebar_toggle, False, False, 0
            )

        if (
            self.sidebar_header_box is not None
            and self.sidebar_header_box.get_parent() is None
        ):
            self.sidebar_box.pack_start(self.sidebar_header_box, False, False, 0)

        if (
            self.sidebar_scroller is not None
            and self.sidebar_scroller.get_parent() is not self.sidebar_box
        ):
            current_parent = self.sidebar_scroller.get_parent()
            if current_parent is not None:
                current_parent.remove(self.sidebar_scroller)
            self.sidebar_box.pack_start(self.sidebar_scroller, True, True, 0)

        if self.sidebar_header_box is not None:
            try:
                self.sidebar_box.reorder_child(self.sidebar_header_box, 0)
            except Exception:
                pass
        if self.sidebar_scroller is not None:
            try:
                self.sidebar_box.reorder_child(self.sidebar_scroller, 1)
            except Exception:
                pass

    def _arrange_top_mode_actions(self):
        if self.top_mode_bar is None:
            return

        if self.top_mode_right_actions is None:
            self.top_mode_right_actions = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=4
            )
            self.top_mode_right_actions.set_halign(Gtk.Align.END)
            self.top_mode_right_actions.set_valign(Gtk.Align.CENTER)
            self.top_mode_right_actions.set_margin_start(12)
            self.top_mode_right_actions.set_margin_end(2)

        if self.button_top_settings is not None:
            parent = self.button_top_settings.get_parent()
            if parent is not None:
                parent.remove(self.button_top_settings)
            self.top_mode_right_actions.pack_start(
                self.button_top_settings, False, False, 0
            )

        if self.top_mode_right_actions.get_parent() is None:
            self.top_mode_bar.pack_end(self.top_mode_right_actions, False, False, 0)

        if self.global_actions_bar is not None:
            self.global_actions_bar.hide()

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
            if self.sidebar_box.get_parent() is not None:
                self.sidebar_box.get_parent().remove(self.sidebar_box)
            paned.add1(self.sidebar_box)
            paned.add2(self.content_box)
            # Sidebar can shrink left; content should keep priority.
            paned.child_set_property(self.sidebar_box, "shrink", True)
            paned.child_set_property(self.sidebar_box, "resize", False)
            paned.child_set_property(self.content_box, "shrink", True)
            paned.child_set_property(self.content_box, "resize", True)
            self.root_hbox.pack_start(paned, True, True, 0)
            self.main_paned = paned

        self.sidebar_box.set_size_request(SIDEBAR_COLLAPSED_WIDTH, -1)

        ui = self.settings.get_section("ui", default={})
        try:
            sidebar_width = int(ui.get("sidebar_width", 260))
        except (TypeError, ValueError):
            sidebar_width = 260
        sidebar_width = max(
            SIDEBAR_COLLAPSED_WIDTH, min(SIDEBAR_WIDTH_MAX, sidebar_width)
        )
        if self._sidebar_width_cap is None:
            # Keep a fixed right-side drag cap; do not lock to last saved width.
            self._sidebar_width_cap = SIDEBAR_WIDTH_MAX
        self._sidebar_restore_width = sidebar_width
        sidebar_width = min(sidebar_width, int(self._sidebar_width_cap))

        self.main_paned.set_position(sidebar_width)
        if self._main_paned_notify_id is not None:
            try:
                self.main_paned.disconnect(self._main_paned_notify_id)
            except Exception:
                self._main_paned_notify_id = None
        if self._main_paned_notify_id is None:
            self._main_paned_notify_id = self.main_paned.connect(
                "notify::position", self.on_main_paned_position_changed
            )
        self.main_paned.show_all()

    def _bind_sidebar_toggle(self):
        if self.button_sidebar_toggle is None:
            return
        if self._sidebar_toggle_handler_id:
            return

        self._sidebar_toggle_handler_id = self.button_sidebar_toggle.connect(
            "toggled", self.on_sidebar_toggle_toggled
        )
        start_open = self._sidebar_restore_width > SIDEBAR_COLLAPSED_WIDTH + 24
        self._sidebar_toggle_syncing = True
        self.button_sidebar_toggle.set_active(start_open)
        self._sidebar_toggle_syncing = False
        self._apply_sidebar_toggle_state(start_open)

    def on_sidebar_toggle_toggled(self, button):
        if self._sidebar_toggle_syncing:
            return
        self._apply_sidebar_toggle_state(bool(button.get_active()))

    def _apply_sidebar_toggle_state(self, is_open: bool):
        if self.main_paned is None or self.sidebar_scroller is None:
            return

        if is_open:
            self.sidebar_scroller.show()
            restore = max(
                SIDEBAR_COLLAPSED_WIDTH + 24,
                min(SIDEBAR_WIDTH_MAX, int(self._sidebar_restore_width)),
            )
            self._suppress_sidebar_width_save = True
            self.main_paned.set_position(restore)
            return

        current_pos = int(self.main_paned.get_position())
        if current_pos > SIDEBAR_COLLAPSED_WIDTH:
            self._sidebar_restore_width = current_pos
        self.sidebar_scroller.hide()
        self._suppress_sidebar_width_save = True
        self.main_paned.set_position(SIDEBAR_COLLAPSED_WIDTH)

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

        self._sidebar_width_cap = max(
            SIDEBAR_WIDTH_MIN, min(SIDEBAR_WIDTH_MAX, measured)
        )
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
        clamped = max(SIDEBAR_COLLAPSED_WIDTH, min(max_width, raw_pos))
        if clamped != raw_pos:
            paned.set_position(clamped)

        sidebar_open = (
            self.button_sidebar_toggle is not None
            and self.button_sidebar_toggle.get_active()
        )
        if not sidebar_open:
            if clamped != SIDEBAR_COLLAPSED_WIDTH:
                self._suppress_sidebar_width_save = True
                paned.set_position(SIDEBAR_COLLAPSED_WIDTH)
                return
            if self._suppress_sidebar_width_save:
                self._suppress_sidebar_width_save = False
            return

        if clamped <= SIDEBAR_COLLAPSED_WIDTH + 2:
            # Near-collapsed drag snaps to collapsed toggle state.
            if (
                self.button_sidebar_toggle is not None
                and self.button_sidebar_toggle.get_active()
            ):
                self._sidebar_toggle_syncing = True
                self.button_sidebar_toggle.set_active(False)
                self._sidebar_toggle_syncing = False
                self._apply_sidebar_toggle_state(False)
            return

        if clamped > SIDEBAR_COLLAPSED_WIDTH:
            self._sidebar_restore_width = clamped
        if self._suppress_sidebar_width_save:
            self._suppress_sidebar_width_save = False
            return
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
            sidebar_open = (
                self.button_sidebar_toggle is not None
                and self.button_sidebar_toggle.get_active()
            )
            self.sidebar_scroller.set_visible(sidebar_open)

        if mode == "builder":
            self._swap_sidebar_widget(self._get_mode_sidebar_widget("builder"))
            self._restore_mode_sidebar_selection("builder")
        elif mode == "presets":
            self._swap_sidebar_widget(self._get_mode_sidebar_widget("presets"))
            self._restore_mode_sidebar_selection("presets")
        else:
            self._swap_sidebar_widget(self.sidebar_list)
            # Ensure mixer sidebar always has a live selection after mode swaps.
            if (
                self.sidebar_list is not None
                and self.sidebar_list.get_selected_row() is None
            ):
                self._select_sidebar_row_by_name(
                    self._last_sidebar_row_name or "row_wallpapers"
                )

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

        if mode != "mixer":
            self._ensure_bar_preview_refresh(False)
        elif self.content_stack is not None:
            self._ensure_bar_preview_refresh(
                self.content_stack.get_visible_child_name() == "panels"
            )

        ui = self.settings.get_section("ui", default={})
        if ui.get("top_mode") != mode:
            ui["top_mode"] = mode
            self.settings.save()

    def on_top_mode_toggled(self, button, mode: str):
        if not button.get_active():
            return
        self.apply_top_mode(mode)

    def on_top_settings_clicked(self, _button):
        if self.content_stack is None:
            return

        current_page = self.content_stack.get_visible_child_name() or ""
        if current_page == "settings":
            # Toggle back to the previously selected sidebar page.
            target = self._last_non_settings_sidebar_page_name or "wallpapers"
            self.content_stack.set_visible_child_name(target)
            self._select_sidebar_row_by_name(
                self._last_non_settings_sidebar_row_name or "row_wallpapers"
            )
            return

        # Settings lives in mixer content; force mixer mode first, keep sidebar state.
        if self.mode_mixer_btn is not None:
            self.mode_mixer_btn.set_active(True)
        self.content_stack.set_visible_child_name("settings")

    def init_status_infobar(self):
        assert self.builder is not None
        self.status_infobar = self.builder.get_object("status_infobar")
        self.status_message_label = self.builder.get_object("label_status_message")
        if self.status_infobar is None:
            return
        self.status_infobar.set_no_show_all(True)
        self.status_infobar.hide()
        self.status_infobar.connect("response", self.on_status_infobar_response)

    def on_status_infobar_response(self, _bar, _response_id):
        self._hide_status_infobar()

    def _hide_status_infobar(self):
        if self._status_hide_source is not None:
            try:
                GLib.source_remove(self._status_hide_source)
            except Exception:
                pass
            self._status_hide_source = None
        if self.status_infobar is not None:
            self.status_infobar.hide()
        return False

    def _show_message(self, message: str):
        print(message)
        if self.status_infobar is None or self.status_message_label is None:
            return

        self.status_message_label.set_text(str(message))
        lower = str(message).lower()
        if "failed" in lower or "error" in lower:
            self.status_infobar.set_message_type(Gtk.MessageType.ERROR)
        elif "warning" in lower:
            self.status_infobar.set_message_type(Gtk.MessageType.WARNING)
        else:
            self.status_infobar.set_message_type(Gtk.MessageType.INFO)

        self.status_infobar.show_all()
        if self._status_hide_source is not None:
            try:
                GLib.source_remove(self._status_hide_source)
            except Exception:
                pass
        self._status_hide_source = GLib.timeout_add(3500, self._hide_status_infobar)

    # file signature helper now lives inside WallpaperService; keep a delegate
    def do_activate(self):
        if self.window is not None:
            self.window.present()
            return

        self.builder = Gtk.Builder()
        assert self.builder is not None
        if not PRIMARY_GLADE.exists():
            raise RuntimeError(f"Missing Glade file: {PRIMARY_GLADE}")
        self.builder.add_from_file(str(PRIMARY_GLADE))
        self.window = find_glade_window(self.builder)
        if self.window is None:
            raise RuntimeError(
                f"No GtkWindow/GtkApplicationWindow found in: {PRIMARY_GLADE}"
            )

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
        self.init_status_infobar()

        # Build all registered pages
        for page_id, page in self.pages.items():
            if hasattr(page, "build"):
                page.build(self, self.builder)

        self.window.present()
        GLib.idle_add(self._show_dependency_warning_once)

    def do_shutdown(self):
        self._ensure_bar_preview_refresh(False)
        self._hide_status_infobar()
        self._save_palette_cache_to_disk()
        Gtk.Application.do_shutdown(self)


def main():
    app = ArchCrafter2App()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
