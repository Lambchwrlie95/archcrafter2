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
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402  # pyright: ignore[reportAttributeAccessIssue]

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
SIDEBAR_WIDTH_MAX = 347
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

BAR_PRESET_TARGETS = {
    "polybar": {
        "title": "Polybar",
        "binary": "polybar",
        "config_dir": Path.home() / ".config" / "polybar",
        "target_file": "config.ini",
        "preset_file": BASE_DIR / "library" / "bars" / "polybar" / "config.ini",
    },
    "tint2": {
        "title": "Tint2",
        "binary": "tint2",
        "config_dir": Path.home() / ".config" / "tint2",
        "target_file": "tint2rc",
        "preset_file": BASE_DIR / "library" / "bars" / "tint2" / "tint2rc",
    },
}

MENU_ENGINE_BINARIES = {
    "rofi": ("rofi",),
    "dmenu": ("dmenu",),
    "jgmenu": ("jgmenu",),
    "fuzzel": ("fuzzel",),
    "wofi": ("wofi",),
    "bemenu": ("bemenu-run", "bemenu"),
}

MENU_ENGINE_COLORS = {
    "rofi": {
        "bg": "#12151a",
        "panel": "#1b212b",
        "surface": "#232b37",
        "accent": "#4da3ff",
        "text": "#dce3ef",
    },
    "dmenu": {
        "bg": "#0f1117",
        "panel": "#20252f",
        "surface": "#1c222b",
        "accent": "#61c49a",
        "text": "#d8dfeb",
    },
    "jgmenu": {
        "bg": "#131419",
        "panel": "#242831",
        "surface": "#2d323d",
        "accent": "#f2b45d",
        "text": "#e9ecf3",
    },
    "fuzzel": {
        "bg": "#0f1418",
        "panel": "#172027",
        "surface": "#1f2b33",
        "accent": "#62b6f1",
        "text": "#d5e7f3",
    },
    "wofi": {
        "bg": "#11141a",
        "panel": "#212631",
        "surface": "#2a313f",
        "accent": "#bf8fff",
        "text": "#dfe4f0",
    },
    "bemenu": {
        "bg": "#121313",
        "panel": "#232525",
        "surface": "#2b2f2f",
        "accent": "#7fd67c",
        "text": "#e4ece6",
    },
}

MENU_PRESET_LIBRARY = (
    {
        "id": "rofi-drun-grid",
        "name": "Rofi - DRUN Grid",
        "engine": "rofi",
        "purpose": "launcher",
        "session": "both",
        "style": "grid",
        "tags": ("applications", "icons", "quick-launch"),
        "summary": "Application launcher with icon-first grid browsing.",
        "command": "rofi -show drun -show-icons",
        "paths": (
            str(Path.home() / ".config" / "rofi" / "config.rasi"),
            str(Path.home() / ".config" / "rofi" / "themes"),
        ),
    },
    {
        "id": "rofi-power-compact",
        "name": "Rofi - Power Compact",
        "engine": "rofi",
        "purpose": "power",
        "session": "both",
        "style": "compact",
        "tags": ("shutdown", "logout", "lock"),
        "summary": "Compact power menu for quick session actions.",
        "command": "rofi -show power-menu -modi power-menu:~/.config/rofi/powermenu.sh",
        "paths": (
            str(Path.home() / ".config" / "rofi" / "powermenu.sh"),
            str(Path.home() / ".config" / "rofi" / "power.rasi"),
        ),
    },
    {
        "id": "jgmenu-categories",
        "name": "jgmenu - Category Launcher",
        "engine": "jgmenu",
        "purpose": "launcher",
        "session": "x11",
        "style": "menu",
        "tags": ("categories", "panel-button", "desktop-menu"),
        "summary": "Traditional category menu suitable for panel integration.",
        "command": "jgmenu_run",
        "paths": (
            str(Path.home() / ".config" / "jgmenu" / "jgmenurc"),
            str(Path.home() / ".config" / "jgmenu" / "prepend.csv"),
        ),
    },
    {
        "id": "dmenu-script-runner",
        "name": "dmenu - Script Runner",
        "engine": "dmenu",
        "purpose": "scripts",
        "session": "x11",
        "style": "minimal",
        "tags": ("shell", "runner", "keyboard"),
        "summary": "Minimal text launcher focused on scripts and custom commands.",
        "command": "dmenu_run",
        "paths": (
            str(Path.home() / ".config" / "dmenu"),
            str(Path.home() / ".local" / "bin"),
        ),
    },
    {
        "id": "fuzzel-wayland-apps",
        "name": "Fuzzel - Wayland Apps",
        "engine": "fuzzel",
        "purpose": "launcher",
        "session": "wayland",
        "style": "minimal",
        "tags": ("wayland", "compact", "apps"),
        "summary": "Lightweight Wayland launcher preset with clean list layout.",
        "command": "fuzzel",
        "paths": (str(Path.home() / ".config" / "fuzzel" / "fuzzel.ini"),),
    },
    {
        "id": "wofi-dashboard",
        "name": "Wofi - Dashboard",
        "engine": "wofi",
        "purpose": "launcher",
        "session": "wayland",
        "style": "dashboard",
        "tags": ("wayland", "search", "show drun"),
        "summary": "Wayland launcher dashboard with larger layout and search.",
        "command": "wofi --show drun",
        "paths": (
            str(Path.home() / ".config" / "wofi" / "config"),
            str(Path.home() / ".config" / "wofi" / "style.css"),
        ),
    },
    {
        "id": "bemenu-clipboard",
        "name": "Bemenu - Clipboard Picker",
        "engine": "bemenu",
        "purpose": "clipboard",
        "session": "both",
        "style": "dense",
        "tags": ("picker", "history", "copy"),
        "summary": "Dense single-row picker for clipboard history workflows.",
        "command": "cliphist list | bemenu | cliphist decode | wl-copy",
        "paths": (
            str(Path.home() / ".config" / "bemenu"),
            str(Path.home() / ".config" / "cliphist"),
        ),
    },
    {
        "id": "rofi-window-switcher",
        "name": "Rofi - Window Switcher",
        "engine": "rofi",
        "purpose": "windows",
        "session": "both",
        "style": "list",
        "tags": ("alt-tab", "workspace", "window"),
        "summary": "Window and workspace switcher with a searchable list.",
        "command": "rofi -show window",
        "paths": (str(Path.home() / ".config" / "rofi" / "window.rasi"),),
    },
)

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

        self.settings = SettingsStore(BASE_DIR / "settings.json")
        self.wallpaper_service = WallpaperService(BASE_DIR, self.settings)
        self.window_theme_service = WindowThemeService(BASE_DIR, self.settings)
        self.gtk_theme_service = GtkThemeService(BASE_DIR, self.settings)
        self.interface_theme_service = InterfaceThemeService(BASE_DIR, self.settings)

        _build_row_to_page()
        self.pages: dict[str, object] = {}
        self._init_page_registry()

        self.switch_wallpaper_system_source = None
        self.combo_wallpaper_fill_mode = None
        self.combo_wallpaper_sort = None
        self.entry_wallpaper_search = None
        self.chooser_wallpaper_folder = None
        self.button_top_settings = None
        self.wallpaper_view_stack = None
        self.wallpaper_view_switcher = None
        self.wallpaper_grid_scroller = None
        self.wallpaper_list_scroller = None
        self.wallpaper_flowbox = None
        self.wallpaper_listbox = None
        self.label_wallpaper_count = None
        self.scale_wallpaper_thumb_size = None
        self.wallpaper_controls_box = None
        self.wallpaper_footer_bar = None
        self.wallpaper_footer_zoom_scale = None
        self.wallpaper_source_picker = None
        self.wallpaper_source_system_btn = None
        self.wallpaper_source_custom_btn = None
        self.flowbox_window_themes = None
        self.flowbox_gtk_themes = None
        self.flowbox_icon_themes = None
        self.flowbox_cursor_themes = None
        self.label_bar_runtime_hint: Optional[Gtk.Label] = None
        self.label_bar_polybar_status: Optional[Gtk.Label] = None
        self.label_bar_tint2_status: Optional[Gtk.Label] = None
        self.image_bar_polybar_preview: Optional[Gtk.Image] = None
        self.image_bar_tint2_preview: Optional[Gtk.Image] = None
        self.preview_polybar_strip: Optional[Gtk.Box] = None
        self.preview_tint2_strip: Optional[Gtk.Box] = None
        self.label_bar_polybar_preview_meta: Optional[Gtk.Label] = None
        self.label_bar_tint2_preview_meta: Optional[Gtk.Label] = None
        self.button_bar_polybar_apply: Optional[Gtk.Button] = None
        self.button_bar_tint2_apply: Optional[Gtk.Button] = None
        self.button_bar_polybar_open: Optional[Gtk.Button] = None
        self.button_bar_tint2_open: Optional[Gtk.Button] = None
        self._bar_preview_refresh_source: Optional[int] = None
        self.entry_menu_search: Optional[Gtk.Entry] = None
        self.combo_menu_engine_filter: Optional[Gtk.ComboBoxText] = None
        self.combo_menu_purpose_filter: Optional[Gtk.ComboBoxText] = None
        self.combo_menu_sort: Optional[Gtk.ComboBoxText] = None
        self.check_menu_installed_only: Optional[Gtk.CheckButton] = None
        self.flowbox_menu_presets: Optional[Gtk.FlowBox] = None
        self.label_menu_count: Optional[Gtk.Label] = None
        self.label_menu_preview_title: Optional[Gtk.Label] = None
        self.label_menu_preview_meta: Optional[Gtk.Label] = None
        self.label_menu_preview_tags: Optional[Gtk.Label] = None
        self.label_menu_preview_command: Optional[Gtk.Label] = None
        self.menu_preview_area: Optional[Gtk.DrawingArea] = None
        self.button_menu_copy_command: Optional[Gtk.Button] = None
        self.button_menu_clone_builder: Optional[Gtk.Button] = None
        self._menu_selected_preset_id: Optional[str] = None
        self.entry_window_themes_search: Optional[Gtk.Entry] = None
        self.entry_gtk_themes_search: Optional[Gtk.Entry] = None
        self.entry_icons_search: Optional[Gtk.Entry] = None
        self.entry_cursors_search: Optional[Gtk.Entry] = None
        self.combo_gtk_themes_filter: Optional[Gtk.ComboBoxText] = None
        self.gtk_theme_preview_container: Optional[Gtk.Box] = None
        self.gtk_theme_preview_surface: Optional[Gtk.Box] = None
        self.gtk_theme_preview_image: Optional[Gtk.Image] = None
        self.gtk_theme_preview_provider = Gtk.CssProvider()
        self._gtk_theme_preview_provider_attached = False
        self._gtk_preview_selected_label: Optional[Gtk.Label] = None
        self._gtk_preview_theme_name: Optional[str] = None
        self._gtk_preview_card_images: dict[str, list[Gtk.Image]] = {}
        self._gtk_preview_render_jobs: set[str] = set()
        self._main_paned_notify_id: Optional[int] = None
        self._gtk_theme_reload_id = 0
        self._icon_theme_reload_id = 0
        self._cursor_theme_reload_id = 0

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

        self._loading_wallpaper_state = False
        self._palette_cache = {}
        self.cache_dir = BASE_DIR / "cache"
        self.thumb_cache_dir = self.cache_dir / "thumbnails"
        self.gtk_preview_cache_dir = self.cache_dir / "gtk_previews"
        self.palette_cache_file = self.cache_dir / "palette_cache.json"
        self._palette_disk_cache = {}
        self._palette_cache_dirty = False
        self._palette_cache_dirty_count = 0
        self._palette_cache_lock = threading.Lock()
        self._dependency_warning_shown = False
        self._preview_window = None
        self.variant_dir = BASE_DIR / "library" / "wallpapers" / "colorized"
        self.variant_dir.mkdir(parents=True, exist_ok=True)
        self.thumb_cache_dir.mkdir(parents=True, exist_ok=True)
        self.gtk_preview_cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_palette_cache_from_disk()
        self._prune_thumbnail_cache(max_files=5000)
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

    def _file_signature(self, path: Path):
        try:
            st = path.stat()
            return (int(st.st_mtime_ns), int(st.st_size))
        except Exception:
            return (0, 0)

    def _thumbnail_cache_path(self, image_path: Path, width: int, height: int):
        sig_mtime, sig_size = self._file_signature(image_path)
        try:
            resolved = str(image_path.resolve())
        except Exception:
            resolved = str(image_path)
        key = f"{resolved}|{width}x{height}|{sig_mtime}:{sig_size}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self.thumb_cache_dir / f"{digest}.png"

    def _prune_thumbnail_cache(self, max_files: int = 5000):
        try:
            files = sorted(
                self.thumb_cache_dir.glob("*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            return
        if len(files) <= max_files:
            return
        for old in files[max_files:]:
            try:
                old.unlink()
            except Exception:
                continue

    def _palette_cache_key(self, path: Path, count: int):
        sig_mtime, sig_size = self._file_signature(path)
        try:
            resolved = str(path.resolve())
        except Exception:
            resolved = str(path)
        src = f"{resolved}|{sig_mtime}:{sig_size}|{int(count)}"
        return hashlib.sha1(src.encode("utf-8")).hexdigest()

    def _load_palette_cache_from_disk(self):
        with self._palette_cache_lock:
            self._palette_disk_cache = {}
        if not self.palette_cache_file.exists():
            return
        try:
            payload = json.loads(self.palette_cache_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            entries = payload.get("entries", {})
            if not isinstance(entries, dict):
                return
            for key, value in entries.items():
                if not isinstance(key, str) or not isinstance(value, list):
                    continue
                colors = [str(c).lower() for c in value if isinstance(c, str)]
                if colors:
                    with self._palette_cache_lock:
                        self._palette_disk_cache[key] = colors
        except Exception:
            with self._palette_cache_lock:
                self._palette_disk_cache = {}

    def _save_palette_cache_to_disk(self):
        if not self._palette_cache_dirty:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with self._palette_cache_lock:
                entries = dict(self._palette_disk_cache)
            data = {
                "version": 1,
                "entries": entries,
            }
            tmp = self.palette_cache_file.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(data, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            tmp.replace(self.palette_cache_file)
            self._palette_cache_dirty = False
            self._palette_cache_dirty_count = 0
        except Exception:
            pass

    def _maybe_flush_palette_cache(self):
        if self._palette_cache_dirty_count >= 24:
            self._save_palette_cache_to_disk()

    def _show_dependency_warning_once(self):
        if self._dependency_warning_shown:
            return False
        self._dependency_warning_shown = True

        tools = detect_external_tools()
        missing = []
        if not tools.get("nitrogen"):
            missing.append("nitrogen (wallpaper apply)")
        if not tools.get("magick_or_convert"):
            missing.append("magick/convert (colorize)")
        if not tools.get("gsettings"):
            missing.append("gsettings (GTK theme apply)")
        if not tools.get("openbox"):
            missing.append("openbox (window theme apply)")

        if not missing or self.window is None:
            return False

        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="Some external tools are missing",
        )
        dialog.format_secondary_text(
            "ArchCrafter2 will still run, but some actions are unavailable:\n\n- "
            + "\n- ".join(missing)
        )
        dialog.run()
        dialog.destroy()
        return False

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
        provider = Gtk.CssProvider()
        if APP_CSS_PATH.exists():
            provider.load_from_path(str(APP_CSS_PATH))
        else:
            provider.load_from_data(b"")

        badge_provider = Gtk.CssProvider()
        badge_provider.load_from_data(
            (
                ".colorized-badge {"
                f"background-color: {badge_bg};"
                f"color: {badge_text};"
                "}"
            ).encode("utf-8")
        )
        screen = Gdk.Screen.get_default()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                badge_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
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
        cache_path = self._thumbnail_cache_path(image_path, width, height)
        if cache_path.exists():
            try:
                return GdkPixbuf.Pixbuf.new_from_file(str(cache_path))
            except Exception:
                try:
                    cache_path.unlink()
                except Exception:
                    pass

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                str(image_path), width, height, True
            )
            try:
                pixbuf.savev(str(cache_path), "png", ["compression"], ["6"])
            except Exception:
                pass
            return pixbuf
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
        key = self._palette_cache_key(path, count)
        with self._palette_cache_lock:
            cached = self._palette_cache.get(key)
        if cached:
            return cached

        with self._palette_cache_lock:
            disk_cached = self._palette_disk_cache.get(key)
        if disk_cached:
            with self._palette_cache_lock:
                self._palette_cache[key] = disk_cached[:count]
                return self._palette_cache[key]

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

        with self._palette_cache_lock:
            self._palette_cache[key] = colors[:count]
            self._palette_disk_cache[key] = colors[:count]
        self._palette_cache_dirty = True
        self._palette_cache_dirty_count += 1
        self._maybe_flush_palette_cache()
        with self._palette_cache_lock:
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
        guard_prev = self._loading_wallpaper_state
        self._loading_wallpaper_state = True
        try:
            if self.wallpaper_source_system_btn is not None:
                self.wallpaper_source_system_btn.set_active(source == "system")
            if self.wallpaper_source_custom_btn is not None:
                self.wallpaper_source_custom_btn.set_active(source == "custom")
        finally:
            self._loading_wallpaper_state = guard_prev
        is_custom = source == "custom"
        if self.chooser_wallpaper_folder is not None:
            self.chooser_wallpaper_folder.set_sensitive(is_custom)
        if self.label_wallpaper_folder is not None:
            self.label_wallpaper_folder.set_sensitive(is_custom)
        self.reload_wallpapers()

    def on_wallpaper_source_choice_toggled(self, button, source_name: str):
        if self._loading_wallpaper_state:
            return
        if not button.get_active():
            return
        target_system = source_name == "system"
        if self.switch_wallpaper_system_source is not None:
            if self.switch_wallpaper_system_source.get_active() != target_system:
                self.switch_wallpaper_system_source.set_active(target_system)
            else:
                # Keep behavior consistent even if state is unchanged.
                self.on_wallpaper_source_toggled(
                    self.switch_wallpaper_system_source, None
                )

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
        self._set_wallpaper_thumb_size(size)

    def _set_wallpaper_thumb_size(self, size: int):
        size = max(180, min(420, int(size)))
        if size == self.thumb_width:
            return
        self.thumb_width = size
        self._update_wallpaper_grid_columns()
        self.wallpaper_service.set_thumb_size(size)
        self._queue_thumb_reload()

    def on_wallpaper_zoom_scroll(self, _widget, event):
        if event is None:
            return False

        state = getattr(event, "state", 0)
        if not (state & Gdk.ModifierType.CONTROL_MASK):
            return False

        step = 20
        delta = 0
        direction = getattr(event, "direction", Gdk.ScrollDirection.SMOOTH)
        if direction == Gdk.ScrollDirection.UP:
            delta = step
        elif direction == Gdk.ScrollDirection.DOWN:
            delta = -step
        elif direction == Gdk.ScrollDirection.SMOOTH:
            try:
                _dx, dy = event.get_scroll_deltas()
            except Exception:
                dy = 0.0
            if dy < -0.01:
                delta = step
            elif dy > 0.01:
                delta = -step

        if delta != 0:
            self._set_wallpaper_thumb_size(self.thumb_width + delta)
        return True

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

    def on_icon_theme_card_preview_pressed(
        self, _widget, event, theme_name: str, display_name: str
    ):
        if event is not None and getattr(event, "button", 1) != 1:
            return False
        self.on_icon_theme_preview_clicked(None, theme_name, display_name)
        return True

    def _build_bar_session_hint(self) -> str:
        if os.environ.get("WAYLAND_DISPLAY"):
            return (
                "Session hint: Wayland detected (Tint2/Polybar shown for compatibility)"
            )
        if os.environ.get("DISPLAY"):
            return "Session hint: X11 detected (Polybar and Tint2 are native fits)"
        return "Session hint: display session not detected, showing generic bar presets"

    def _is_bar_process_running(self, binary: str) -> bool:
        try:
            result = subprocess.run(
                ["pgrep", "-x", str(binary)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _find_bar_preview_file(self, preset_dir: Path) -> Optional[Path]:
        for name in (
            "preview.png",
            "preview.jpg",
            "preview.jpeg",
            "preview.webp",
            "screenshot.png",
            "screenshot.jpg",
            "thumb.png",
        ):
            candidate = preset_dir / name
            if candidate.exists():
                return candidate
        return None

    def _discover_bar_presets(self, target: str) -> list[dict[str, object]]:
        spec = BAR_PRESET_TARGETS.get(target)
        if spec is None:
            return []

        root = Path(spec["preset_file"]).parent
        target_file = str(spec["target_file"])
        presets: list[dict[str, object]] = []
        if not root.exists():
            return presets

        root_config = root / target_file
        if root_config.exists():
            presets.append(
                {
                    "name": "default",
                    "dir": root,
                    "config_path": root_config,
                    "preview_path": self._find_bar_preview_file(root),
                }
            )

        try:
            children = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            children = []

        for child in children:
            if not child.is_dir():
                continue
            cfg = child / target_file
            if not cfg.exists():
                continue
            presets.append(
                {
                    "name": child.name,
                    "dir": child,
                    "config_path": cfg,
                    "preview_path": self._find_bar_preview_file(child),
                }
            )

        return presets

    def _preferred_bar_preset(self, target: str) -> Optional[dict[str, object]]:
        presets = self._discover_bar_presets(target)
        if not presets:
            return None
        return presets[0]

    def _build_bar_target_status(self, target: str) -> str:
        spec = BAR_PRESET_TARGETS.get(target)
        if spec is None:
            return "Unknown target"

        binary_ok = shutil.which(str(spec["binary"])) is not None
        running = self._is_bar_process_running(str(spec["binary"]))
        config_ok = Path(spec["config_dir"]).exists()
        preset_count = len(self._discover_bar_presets(target))
        binary_status = "binary found" if binary_ok else "binary missing"
        run_status = "running" if running else "not running"
        config_status = "config found" if config_ok else "config missing"
        preset_status = f"{preset_count} preset(s)"
        return f"{binary_status} • {run_status} • {config_status} • {preset_status}"

    def _set_bar_status_label(self, label: Optional[Gtk.Label], target: str):
        if label is None:
            return
        spec = BAR_PRESET_TARGETS.get(target)
        if spec is None:
            label.set_text("Unknown target")
            return

        binary_ok = shutil.which(str(spec["binary"])) is not None
        running = self._is_bar_process_running(str(spec["binary"]))
        config_ok = Path(spec["config_dir"]).exists()
        preset_ok = bool(self._discover_bar_presets(target))
        label.set_text(self._build_bar_target_status(target))
        ctx = label.get_style_context()
        ctx.remove_class("bar-status-ok")
        ctx.remove_class("bar-status-warn")
        ctx.add_class(
            "bar-status-ok"
            if binary_ok and running and config_ok and preset_ok
            else "bar-status-warn"
        )

    def _capture_live_bar_preview_pixbuf(self) -> Optional[GdkPixbuf.Pixbuf]:
        if os.environ.get("WAYLAND_DISPLAY"):
            return None
        screen = Gdk.Screen.get_default()
        if screen is None:
            return None
        root = screen.get_root_window()
        if root is None:
            return None

        src_x = 0
        src_y = 0
        src_w = int(root.get_width())
        monitor_h = int(root.get_height())

        display = Gdk.Display.get_default()
        if display is not None:
            try:
                monitor = display.get_primary_monitor()
                if monitor is None and display.get_n_monitors() > 0:
                    monitor = display.get_monitor(0)
                if monitor is not None:
                    geo = monitor.get_geometry()
                    src_x = int(geo.x)
                    src_y = int(geo.y)
                    src_w = int(geo.width)
                    monitor_h = int(geo.height)
            except Exception:
                pass

        if src_w <= 0:
            return None
        src_h = max(24, min(64, int(monitor_h * 0.07)))
        try:
            pixbuf = Gdk.pixbuf_get_from_window(root, src_x, src_y, src_w, src_h)
        except Exception:
            return None
        if pixbuf is None:
            return None

        target_h = 42
        target_w = max(320, min(1440, int(src_w)))
        if pixbuf.get_width() != target_w or pixbuf.get_height() != target_h:
            scaled = pixbuf.scale_simple(
                target_w, target_h, GdkPixbuf.InterpType.BILINEAR
            )
            if scaled is not None:
                pixbuf = scaled
        return pixbuf

    def _load_bar_preview_file_pixbuf(self, path: Path) -> Optional[GdkPixbuf.Pixbuf]:
        if not path.exists():
            return None
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 1440, 42, True)
        except Exception:
            return None

    def _set_bar_preview_widget(
        self,
        image: Optional[Gtk.Image],
        fallback_strip: Optional[Gtk.Widget],
        meta_label: Optional[Gtk.Label],
        pixbuf: Optional[GdkPixbuf.Pixbuf],
        meta_text: str,
    ):
        if meta_label is not None:
            meta_label.set_text(meta_text)
        if image is None:
            return
        if pixbuf is None:
            image.clear()
            image.hide()
            if fallback_strip is not None:
                fallback_strip.show()
            return
        image.set_from_pixbuf(pixbuf)
        image.show()
        if fallback_strip is not None:
            fallback_strip.hide()

    def _refresh_single_bar_preview(
        self,
        target: str,
        image: Optional[Gtk.Image],
        fallback_strip: Optional[Gtk.Widget],
        meta_label: Optional[Gtk.Label],
        live_pixbuf: Optional[GdkPixbuf.Pixbuf],
    ):
        if live_pixbuf is not None:
            self._set_bar_preview_widget(
                image,
                fallback_strip,
                meta_label,
                live_pixbuf,
                "Preview source: live top-bar capture",
            )
            return

        preset = self._preferred_bar_preset(target)
        if preset is None:
            self._set_bar_preview_widget(
                image,
                fallback_strip,
                meta_label,
                None,
                "Preview source: schematic (no preset found)",
            )
            return

        preview_path = preset.get("preview_path")
        preview_pixbuf = None
        if isinstance(preview_path, Path):
            preview_pixbuf = self._load_bar_preview_file_pixbuf(preview_path)
        if preview_pixbuf is not None:
            self._set_bar_preview_widget(
                image,
                fallback_strip,
                meta_label,
                preview_pixbuf,
                f"Preview source: preset screenshot ({preset['name']})",
            )
            return

        self._set_bar_preview_widget(
            image,
            fallback_strip,
            meta_label,
            None,
            f"Preview source: schematic ({preset['name']})",
        )

    def _on_bar_preview_refresh_timer(self):
        if (
            self.active_top_mode != "mixer"
            or self.content_stack is None
            or self.content_stack.get_visible_child_name() != "panels"
        ):
            self._bar_preview_refresh_source = None
            return False
        self.refresh_bar_page_state(refresh_preview=True)
        return True

    def _ensure_bar_preview_refresh(self, active: bool):
        if active:
            if self._bar_preview_refresh_source is None:
                self._bar_preview_refresh_source = GLib.timeout_add_seconds(
                    6, self._on_bar_preview_refresh_timer
                )
            return
        if self._bar_preview_refresh_source is not None:
            GLib.source_remove(self._bar_preview_refresh_source)
            self._bar_preview_refresh_source = None

    def refresh_bar_page_state(self, refresh_preview: bool = True):
        if self.label_bar_runtime_hint is not None:
            self.label_bar_runtime_hint.set_text(self._build_bar_session_hint())

        self._set_bar_status_label(self.label_bar_polybar_status, "polybar")
        self._set_bar_status_label(self.label_bar_tint2_status, "tint2")

        polybar_path = Path(BAR_PRESET_TARGETS["polybar"]["config_dir"])
        tint2_path = Path(BAR_PRESET_TARGETS["tint2"]["config_dir"])
        polybar_preset = self._preferred_bar_preset("polybar")
        tint2_preset = self._preferred_bar_preset("tint2")
        if self.button_bar_polybar_open is not None:
            self.button_bar_polybar_open.set_sensitive(polybar_path.exists())
            self.button_bar_polybar_open.set_tooltip_text(str(polybar_path))
        if self.button_bar_tint2_open is not None:
            self.button_bar_tint2_open.set_sensitive(tint2_path.exists())
            self.button_bar_tint2_open.set_tooltip_text(str(tint2_path))
        if self.button_bar_polybar_apply is not None:
            self.button_bar_polybar_apply.set_sensitive(polybar_preset is not None)
            if polybar_preset is not None:
                self.button_bar_polybar_apply.set_tooltip_text(
                    str(polybar_preset.get("config_path", ""))
                )
            else:
                self.button_bar_polybar_apply.set_tooltip_text(
                    "No Polybar preset found in library/bars/polybar"
                )
        if self.button_bar_tint2_apply is not None:
            self.button_bar_tint2_apply.set_sensitive(tint2_preset is not None)
            if tint2_preset is not None:
                self.button_bar_tint2_apply.set_tooltip_text(
                    str(tint2_preset.get("config_path", ""))
                )
            else:
                self.button_bar_tint2_apply.set_tooltip_text(
                    "No Tint2 preset found in library/bars/tint2"
                )

        if refresh_preview:
            live_preview = self._capture_live_bar_preview_pixbuf()
            self._refresh_single_bar_preview(
                "polybar",
                self.image_bar_polybar_preview,
                self.preview_polybar_strip,
                self.label_bar_polybar_preview_meta,
                live_preview,
            )
            self._refresh_single_bar_preview(
                "tint2",
                self.image_bar_tint2_preview,
                self.preview_tint2_strip,
                self.label_bar_tint2_preview_meta,
                live_preview,
            )

    def init_bar_page(self):
        assert self.builder is not None
        self.label_bar_runtime_hint = self.builder.get_object("label_bar_runtime_hint")
        self.label_bar_polybar_status = self.builder.get_object(
            "label_bar_polybar_status"
        )
        self.label_bar_tint2_status = self.builder.get_object("label_bar_tint2_status")
        self.image_bar_polybar_preview = self.builder.get_object(
            "image_bar_polybar_preview"
        )
        self.image_bar_tint2_preview = self.builder.get_object(
            "image_bar_tint2_preview"
        )
        self.preview_polybar_strip = self.builder.get_object("preview_polybar_strip")
        self.preview_tint2_strip = self.builder.get_object("preview_tint2_strip")
        self.label_bar_polybar_preview_meta = self.builder.get_object(
            "label_bar_polybar_preview_meta"
        )
        self.label_bar_tint2_preview_meta = self.builder.get_object(
            "label_bar_tint2_preview_meta"
        )
        self.button_bar_polybar_apply = self.builder.get_object(
            "button_bar_polybar_apply"
        )
        self.button_bar_tint2_apply = self.builder.get_object("button_bar_tint2_apply")
        self.button_bar_polybar_open = self.builder.get_object(
            "button_bar_polybar_open"
        )
        self.button_bar_tint2_open = self.builder.get_object("button_bar_tint2_open")
        button_polybar_copy = self.builder.get_object("button_bar_polybar_copy")
        button_tint2_copy = self.builder.get_object("button_bar_tint2_copy")
        button_open_builder = self.builder.get_object("button_bar_open_builder")

        polybar_path = Path(BAR_PRESET_TARGETS["polybar"]["config_dir"])
        tint2_path = Path(BAR_PRESET_TARGETS["tint2"]["config_dir"])

        if self.button_bar_polybar_apply is not None:
            self.button_bar_polybar_apply.connect(
                "clicked", self.on_bar_polybar_apply_clicked
            )
        if self.button_bar_tint2_apply is not None:
            self.button_bar_tint2_apply.connect(
                "clicked", self.on_bar_tint2_apply_clicked
            )
        if self.button_bar_polybar_open is not None:
            self.button_bar_polybar_open.connect(
                "clicked", self.on_bar_polybar_open_clicked
            )
        if self.button_bar_tint2_open is not None:
            self.button_bar_tint2_open.connect(
                "clicked", self.on_bar_tint2_open_clicked
            )
        if button_polybar_copy is not None:
            button_polybar_copy.connect("clicked", self.on_bar_polybar_copy_clicked)
            button_polybar_copy.set_tooltip_text(str(polybar_path))
        if button_tint2_copy is not None:
            button_tint2_copy.connect("clicked", self.on_bar_tint2_copy_clicked)
            button_tint2_copy.set_tooltip_text(str(tint2_path))
        if button_open_builder is not None:
            button_open_builder.connect("clicked", self.on_bar_open_builder_clicked)

        self.refresh_bar_page_state(refresh_preview=True)

    def _bar_target_config_file(self, target: str) -> Optional[Path]:
        spec = BAR_PRESET_TARGETS.get(target)
        if spec is None:
            return None
        return Path(spec["config_dir"]) / str(spec["target_file"])

    def _bar_preset_source_file(self, target: str) -> Optional[Path]:
        preset = self._preferred_bar_preset(target)
        if preset is None:
            return None
        source = preset.get("config_path")
        if not isinstance(source, Path):
            return None
        return source

    def _backup_file(self, path: Path) -> Optional[Path]:
        if not path.exists():
            return None
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.name}.bak-{stamp}")
        shutil.copy2(path, backup)
        return backup

    def _install_bar_preset(self, target: str):
        spec = BAR_PRESET_TARGETS.get(target)
        if spec is None:
            self._show_message("Unknown bar target")
            return

        title = str(spec["title"])
        preset = self._preferred_bar_preset(target)
        source = self._bar_preset_source_file(target)
        dest = self._bar_target_config_file(target)
        if source is None or dest is None:
            self._show_message(f"Cannot install {title} preset")
            return
        if not source.exists():
            self._show_message(f"{title} preset file missing: {source}")
            return

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            backup = self._backup_file(dest)
            shutil.copy2(source, dest)
        except Exception as exc:
            self._show_message(f"Failed to install {title} preset: {exc}")
            return

        preset_name = "default"
        if preset is not None:
            preset_name = str(preset.get("name", "default"))

        if backup is None:
            self._show_message(f"Installed {title} preset '{preset_name}' to {dest}")
        else:
            self._show_message(
                f"Installed {title} preset '{preset_name}' to {dest} (backup: {backup.name})"
            )
        self.refresh_bar_page_state(refresh_preview=True)

    def _open_bar_config_dir(self, target: str):
        spec = BAR_PRESET_TARGETS.get(target)
        if spec is None:
            self._show_message("Unknown bar target")
            return

        title = str(spec["title"])
        config_dir = Path(spec["config_dir"])
        if not config_dir.exists():
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
                self._show_message(f"Created {title} config folder")
            except Exception as exc:
                self._show_message(
                    f"{title} config folder not found: {config_dir} ({exc})"
                )
                return

        opener = shutil.which("xdg-open")
        if opener is None:
            self._show_message("Cannot open folder: xdg-open is not installed")
            return

        try:
            subprocess.Popen([opener, str(config_dir)])
            self._show_message(f"Opened {title} config folder")
            self.refresh_bar_page_state()
        except Exception as exc:
            self._show_message(f"Failed to open {title} folder: {exc}")

    def _copy_bar_config_path(self, target: str):
        spec = BAR_PRESET_TARGETS.get(target)
        if spec is None:
            self._show_message("Unknown bar target")
            return

        display = Gdk.Display.get_default()
        if display is None:
            self._show_message("Cannot copy path: no display available")
            return

        clipboard = Gtk.Clipboard.get_default(display)
        if clipboard is None:
            self._show_message("Cannot copy path: clipboard unavailable")
            return

        config_dir = str(spec["config_dir"])
        clipboard.set_text(config_dir, -1)
        clipboard.store()
        self._show_message(f"Copied {spec['title']} config path")

    def on_bar_polybar_open_clicked(self, _button):
        self._open_bar_config_dir("polybar")

    def on_bar_tint2_open_clicked(self, _button):
        self._open_bar_config_dir("tint2")

    def on_bar_polybar_apply_clicked(self, _button):
        self._install_bar_preset("polybar")

    def on_bar_tint2_apply_clicked(self, _button):
        self._install_bar_preset("tint2")

    def on_bar_polybar_copy_clicked(self, _button):
        self._copy_bar_config_path("polybar")

    def on_bar_tint2_copy_clicked(self, _button):
        self._copy_bar_config_path("tint2")

    def on_bar_open_builder_clicked(self, _button):
        if self.mode_builder_btn is not None:
            self.mode_builder_btn.set_active(True)

    def _menu_engine_palette(self, engine: str):
        return MENU_ENGINE_COLORS.get(str(engine), MENU_ENGINE_COLORS["rofi"])

    def _menu_engine_available(self, engine: str) -> bool:
        binaries = MENU_ENGINE_BINARIES.get(str(engine), (str(engine),))
        for binary in binaries:
            if shutil.which(str(binary)) is not None:
                return True
        return False

    def _menu_runtime_compatible(self, session: str) -> bool:
        session = str(session or "both").strip().lower()
        if session == "x11":
            return bool(os.environ.get("DISPLAY"))
        if session == "wayland":
            return bool(os.environ.get("WAYLAND_DISPLAY"))
        return True

    def _menu_runtime_note(self, session: str) -> str:
        session = str(session or "both").strip().lower()
        if session == "x11":
            return "X11-focused"
        if session == "wayland":
            return "Wayland-focused"
        return "X11 + Wayland"

    def _menu_collect_tags(self, preset: dict) -> list[str]:
        tags: list[str] = []
        for value in (
            preset.get("engine"),
            preset.get("purpose"),
            preset.get("session"),
            preset.get("style"),
        ):
            raw = str(value or "").strip().lower()
            if raw and raw not in tags:
                tags.append(raw)
        for tag in preset.get("tags", ()):
            raw = str(tag or "").strip().lower()
            if raw and raw not in tags:
                tags.append(raw)
        return tags

    def _menu_preset_by_id(self, preset_id: str | None) -> Optional[dict]:
        target = str(preset_id or "").strip()
        if not target:
            return None
        for preset in MENU_PRESET_LIBRARY:
            if str(preset.get("id", "")) == target:
                return dict(preset)
        return None

    def _copy_text_to_clipboard(self, text: str, ok_message: str):
        display = Gdk.Display.get_default()
        if display is None:
            self._show_message("Cannot copy: no display available")
            return
        clipboard = Gtk.Clipboard.get_default(display)
        if clipboard is None:
            self._show_message("Cannot copy: clipboard unavailable")
            return
        clipboard.set_text(str(text), -1)
        clipboard.store()
        self._show_message(ok_message)

    def _draw_menu_mock_preview(self, widget, cr, preset: dict, compact: bool = True):
        alloc = widget.get_allocation()
        w = max(1.0, float(alloc.width) - 1.0)
        h = max(1.0, float(alloc.height) - 1.0)
        palette = self._menu_engine_palette(str(preset.get("engine", "rofi")))
        bg = str(palette.get("bg", "#12151a"))
        panel = str(palette.get("panel", "#1b212b"))
        surface = str(palette.get("surface", "#232b37"))
        accent = str(palette.get("accent", "#4da3ff"))
        text = str(palette.get("text", "#dce3ef"))

        self._rounded_rect(cr, 0.5, 0.5, w, h, 10.0)
        r, g, b = self._hex_to_rgb(bg)
        cr.set_source_rgb(r, g, b)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.0)
        cr.stroke()

        top_h = max(16.0, h * 0.22)
        self._rounded_rect(cr, 6.0, 6.0, max(1.0, w - 12.0), top_h, 6.0)
        r, g, b = self._hex_to_rgb(panel)
        cr.set_source_rgb(r, g, b)
        cr.fill()

        entry_y = 8.0 + (top_h - 12.0) / 2.0
        self._rounded_rect(cr, 12.0, entry_y, max(24.0, w * 0.58), 12.0, 5.0)
        r, g, b = self._hex_to_rgb(surface)
        cr.set_source_rgb(r, g, b)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.0)
        cr.stroke()

        self._rounded_rect(cr, max(18.0, w - 68.0), entry_y, 56.0, 12.0, 5.0)
        r, g, b = self._hex_to_rgb(accent)
        cr.set_source_rgb(r, g, b)
        cr.fill()

        rows = 3 if compact else 6
        start_y = top_h + 15.0
        row_h = max(8.0, (h - start_y - 10.0) / max(1, rows))
        tr, tg, tb = self._hex_to_rgb(text)
        for idx in range(rows):
            y = start_y + (idx * row_h)
            self._rounded_rect(cr, 10.0, y, max(20.0, w - 20.0), row_h - 4.0, 4.0)
            alpha = 0.18 if idx == 1 else 0.10
            cr.set_source_rgba(tr, tg, tb, alpha)
            cr.fill()

            if idx == 1:
                self._rounded_rect(
                    cr,
                    10.0,
                    y,
                    max(18.0, min(8.0 + w * 0.06, w - 20.0)),
                    row_h - 4.0,
                    4.0,
                )
                r, g, b = self._hex_to_rgb(accent)
                cr.set_source_rgba(r, g, b, 0.85)
                cr.fill()
        return False

    def _draw_menu_card_preview(self, widget, cr, preset: dict):
        return self._draw_menu_mock_preview(widget, cr, preset, compact=True)

    def _draw_menu_preview_area(self, widget, cr):
        preset = self._menu_preset_by_id(self._menu_selected_preset_id)
        if preset is None:
            preset = dict(MENU_PRESET_LIBRARY[0])
        return self._draw_menu_mock_preview(widget, cr, preset, compact=False)

    def _set_menu_preview_preset(self, preset_id: str):
        preset = self._menu_preset_by_id(preset_id)
        if preset is None:
            return

        self._menu_selected_preset_id = str(preset.get("id", ""))
        installed = self._menu_engine_available(str(preset.get("engine", "")))
        runtime_ok = self._menu_runtime_compatible(str(preset.get("session", "both")))
        state_text = "installed" if installed else "not installed"
        runtime_text = (
            "runtime ok"
            if runtime_ok
            else self._menu_runtime_note(str(preset.get("session", "both")))
        )
        tags = self._menu_collect_tags(preset)

        if self.label_menu_preview_title is not None:
            self.label_menu_preview_title.set_text(
                str(preset.get("name", "Menu Preset"))
            )
        if self.label_menu_preview_meta is not None:
            self.label_menu_preview_meta.set_text(
                "Engine: "
                + str(preset.get("engine", "")).upper()
                + "  •  Purpose: "
                + str(preset.get("purpose", "")).title()
                + "  •  "
                + state_text
                + "  •  "
                + runtime_text
            )
        if self.label_menu_preview_tags is not None:
            self.label_menu_preview_tags.set_text("Tags: " + ", ".join(tags))
        if self.label_menu_preview_command is not None:
            self.label_menu_preview_command.set_text(
                "Command: " + str(preset.get("command", ""))
            )
        if self.menu_preview_area is not None:
            self.menu_preview_area.queue_draw()
        if self.button_menu_copy_command is not None:
            self.button_menu_copy_command.set_sensitive(True)
        if self.button_menu_clone_builder is not None:
            self.button_menu_clone_builder.set_sensitive(True)

    def _menu_filtered_presets(self) -> list[dict]:
        query = ""
        if self.entry_menu_search is not None:
            query = str(self.entry_menu_search.get_text() or "").strip().lower()

        engine_filter = "all"
        if self.combo_menu_engine_filter is not None:
            engine_filter = str(self.combo_menu_engine_filter.get_active_id() or "all")

        purpose_filter = "all"
        if self.combo_menu_purpose_filter is not None:
            purpose_filter = str(
                self.combo_menu_purpose_filter.get_active_id() or "all"
            )

        installed_only = (
            self.check_menu_installed_only is not None
            and self.check_menu_installed_only.get_active()
        )

        sort_mode = "name_asc"
        if self.combo_menu_sort is not None:
            sort_mode = str(self.combo_menu_sort.get_active_id() or "name_asc")

        items: list[dict] = []
        for raw in MENU_PRESET_LIBRARY:
            preset = dict(raw)
            engine = str(preset.get("engine", "")).strip().lower()
            purpose = str(preset.get("purpose", "")).strip().lower()
            installed = self._menu_engine_available(engine)
            runtime_ok = self._menu_runtime_compatible(
                str(preset.get("session", "both"))
            )
            preset["installed"] = installed
            preset["runtime_ok"] = runtime_ok

            if engine_filter != "all" and engine != engine_filter:
                continue
            if purpose_filter != "all" and purpose != purpose_filter:
                continue
            if installed_only and not installed:
                continue

            if query:
                searchable = " ".join(
                    [
                        str(preset.get("name", "")),
                        engine,
                        purpose,
                        str(preset.get("style", "")),
                        str(preset.get("summary", "")),
                        " ".join(self._menu_collect_tags(preset)),
                    ]
                ).lower()
                if query not in searchable:
                    continue

            items.append(preset)

        if sort_mode == "name_desc":
            items.sort(key=lambda p: str(p.get("name", "")).lower(), reverse=True)
        elif sort_mode == "engine":
            items.sort(
                key=lambda p: (
                    str(p.get("engine", "")).lower(),
                    str(p.get("name", "")).lower(),
                )
            )
        elif sort_mode == "installed":
            items.sort(
                key=lambda p: (
                    not bool(p.get("installed", False)),
                    str(p.get("name", "")).lower(),
                )
            )
        else:
            items.sort(key=lambda p: str(p.get("name", "")).lower())
        return items

    def on_menu_card_pressed(self, _widget, _event, preset_id: str):
        self._set_menu_preview_preset(preset_id)
        return False

    def on_menu_card_preview_clicked(self, _button, preset_id: str):
        preset = self._menu_preset_by_id(preset_id)
        if preset is None:
            return
        self._set_menu_preview_preset(preset_id)

        dialog = Gtk.Dialog(
            title=f"Menu Preview - {preset.get('name', 'Preset')}",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(820, 520)

        area = dialog.get_content_area()
        area.set_margin_top(10)
        area.set_margin_bottom(10)
        area.set_margin_start(10)
        area.set_margin_end(10)
        area.set_spacing(10)

        surface = Gtk.DrawingArea()
        surface.set_size_request(-1, 260)
        surface.get_style_context().add_class("menu-preview-surface")
        surface.connect("draw", self._draw_menu_card_preview, preset)
        area.pack_start(surface, False, False, 0)

        summary = Gtk.Label(label=str(preset.get("summary", "")))
        summary.set_xalign(0.0)
        summary.set_line_wrap(True)
        summary.get_style_context().add_class("theme-subtitle")
        area.pack_start(summary, False, False, 0)

        details = Gtk.Label(
            label=(
                "Engine: "
                + str(preset.get("engine", "")).upper()
                + "  •  Purpose: "
                + str(preset.get("purpose", "")).title()
                + "  •  Session: "
                + str(preset.get("session", "both")).upper()
            )
        )
        details.set_xalign(0.0)
        details.get_style_context().add_class("theme-subtitle")
        area.pack_start(details, False, False, 0)

        command = Gtk.Label(label="Command: " + str(preset.get("command", "")))
        command.set_xalign(0.0)
        command.set_line_wrap(True)
        command.set_selectable(True)
        command.get_style_context().add_class("menu-command-label")
        area.pack_start(command, False, False, 0)

        paths = preset.get("paths", ())
        if paths:
            path_label = Gtk.Label(
                label="Files: " + "  |  ".join([str(p) for p in paths])
            )
            path_label.set_xalign(0.0)
            path_label.set_line_wrap(True)
            path_label.set_selectable(True)
            path_label.get_style_context().add_class("theme-subtitle")
            area.pack_start(path_label, False, False, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def on_menu_card_copy_clicked(self, _button, preset_id: str):
        preset = self._menu_preset_by_id(preset_id)
        if preset is None:
            return
        self._set_menu_preview_preset(preset_id)
        self._copy_text_to_clipboard(
            str(preset.get("command", "")),
            f"Copied command for {preset.get('name', 'preset')}",
        )

    def _open_builder_menu_workspace(self, preset_name: Optional[str] = None):
        self._mode_sidebar_selection["builder"] = "builder_menus"
        if self.mode_builder_btn is not None:
            self.mode_builder_btn.set_active(True)
        builder_sidebar = self._get_mode_sidebar_widget("builder")
        if builder_sidebar is not None:
            row = self._find_row_by_item_id(builder_sidebar, "builder_menus")
            if row is not None:
                builder_sidebar.select_row(row)
        if preset_name:
            self._show_message(f"Builder Menus opened for '{preset_name}'")
        else:
            self._show_message("Builder Menus workspace opened")

    def on_menu_card_builder_clicked(self, _button, preset_id: str):
        preset = self._menu_preset_by_id(preset_id)
        if preset is None:
            return
        self._set_menu_preview_preset(preset_id)
        self._open_builder_menu_workspace(str(preset.get("name", "Menu preset")))

    def on_menu_filters_changed(self, _widget):
        self.reload_menu_presets()

    def on_menu_import_clicked(self, _button):
        self._show_message(
            "Menu importer scaffold ready. Next: file picker + preset manifest."
        )

    def on_menu_open_builder_clicked(self, _button):
        self._open_builder_menu_workspace()

    def on_menu_copy_command_clicked(self, _button):
        preset = self._menu_preset_by_id(self._menu_selected_preset_id)
        if preset is None:
            self._show_message("Select a menu preset first")
            return
        self._copy_text_to_clipboard(
            str(preset.get("command", "")),
            f"Copied command for {preset.get('name', 'preset')}",
        )

    def on_menu_clone_builder_clicked(self, _button):
        preset = self._menu_preset_by_id(self._menu_selected_preset_id)
        if preset is None:
            self._show_message("Select a menu preset first")
            return
        self._open_builder_menu_workspace(str(preset.get("name", "Menu preset")))

    def reload_menu_presets(self):
        if self.flowbox_menu_presets is None:
            return

        visible_presets = self._menu_filtered_presets()
        self._clear_widget_children(self.flowbox_menu_presets)

        for preset in visible_presets:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.get_style_context().add_class("theme-card")
            card.get_style_context().add_class("menu-preset-card")

            top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            title = Gtk.Label(label=str(preset.get("name", "Menu Preset")))
            title.get_style_context().add_class("theme-title")
            title.set_xalign(0.0)
            title.set_ellipsize(Pango.EllipsizeMode.END)
            top_row.pack_start(title, True, True, 0)

            engine_badge = Gtk.Label(label=str(preset.get("engine", "")).upper())
            engine_badge.get_style_context().add_class("theme-type-badge")
            engine_badge.get_style_context().add_class("menu-engine-badge")
            top_row.pack_start(engine_badge, False, False, 0)
            card.pack_start(top_row, False, False, 0)

            preview = Gtk.DrawingArea()
            preview.set_size_request(-1, 92)
            preview.get_style_context().add_class("menu-preview-surface")
            preview.connect("draw", self._draw_menu_card_preview, preset)
            card.pack_start(preview, False, False, 0)

            summary = Gtk.Label(label=str(preset.get("summary", "")))
            summary.set_xalign(0.0)
            summary.set_line_wrap(True)
            summary.get_style_context().add_class("theme-subtitle")
            card.pack_start(summary, False, False, 0)

            tags_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            tags_row.set_halign(Gtk.Align.START)
            for tag in self._menu_collect_tags(preset)[:4]:
                chip = Gtk.Label(label=str(tag).upper())
                chip.get_style_context().add_class("menu-tag-chip")
                tags_row.pack_start(chip, False, False, 0)
            card.pack_start(tags_row, False, False, 0)

            status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            status_text = (
                "Installed" if bool(preset.get("installed", False)) else "Missing"
            )
            status_badge = Gtk.Label(label=status_text.upper())
            status_badge.get_style_context().add_class("theme-type-badge")
            if bool(preset.get("installed", False)):
                status_badge.get_style_context().add_class("menu-status-ok")
            else:
                status_badge.get_style_context().add_class("menu-status-warn")
            status_row.pack_start(status_badge, False, False, 0)

            runtime_note = Gtk.Label(
                label=self._menu_runtime_note(str(preset.get("session", "both")))
            )
            runtime_note.get_style_context().add_class("theme-subtitle")
            runtime_note.set_xalign(0.0)
            status_row.pack_start(runtime_note, False, False, 0)
            card.pack_start(status_row, False, False, 0)

            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            preview_btn = Gtk.Button(label="Preview")
            preview_btn.get_style_context().add_class("theme-apply-button")
            preview_btn.get_style_context().add_class("theme-secondary-button")
            preview_btn.connect(
                "clicked", self.on_menu_card_preview_clicked, str(preset.get("id", ""))
            )
            actions.pack_start(preview_btn, True, True, 0)

            copy_btn = Gtk.Button(label="Copy Cmd")
            copy_btn.get_style_context().add_class("theme-apply-button")
            copy_btn.get_style_context().add_class("theme-secondary-button")
            copy_btn.connect(
                "clicked", self.on_menu_card_copy_clicked, str(preset.get("id", ""))
            )
            actions.pack_start(copy_btn, True, True, 0)

            builder_btn = Gtk.Button(label="Builder")
            builder_btn.get_style_context().add_class("theme-apply-button")
            builder_btn.connect(
                "clicked", self.on_menu_card_builder_clicked, str(preset.get("id", ""))
            )
            actions.pack_start(builder_btn, True, True, 0)
            card.pack_start(actions, False, False, 0)

            event_box = Gtk.EventBox()
            event_box.add(card)
            event_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            event_box.connect(
                "button-press-event",
                self.on_menu_card_pressed,
                str(preset.get("id", "")),
            )

            child = Gtk.FlowBoxChild()
            child.add(event_box)
            self.flowbox_menu_presets.add(child)
            child.show_all()

        if self.label_menu_count is not None:
            self.label_menu_count.set_text(f"{len(visible_presets)} presets")

        selected_exists = False
        if self._menu_selected_preset_id:
            for preset in visible_presets:
                if str(preset.get("id", "")) == self._menu_selected_preset_id:
                    selected_exists = True
                    break

        if visible_presets and not selected_exists:
            self._set_menu_preview_preset(str(visible_presets[0].get("id", "")))
        elif not visible_presets:
            self._menu_selected_preset_id = None
            if self.label_menu_preview_title is not None:
                self.label_menu_preview_title.set_text("No presets match this filter")
            if self.label_menu_preview_meta is not None:
                self.label_menu_preview_meta.set_text(
                    "Try a wider search or disable Installed-only mode."
                )
            if self.label_menu_preview_tags is not None:
                self.label_menu_preview_tags.set_text("Tags: -")
            if self.label_menu_preview_command is not None:
                self.label_menu_preview_command.set_text("Command: -")
            if self.button_menu_copy_command is not None:
                self.button_menu_copy_command.set_sensitive(False)
            if self.button_menu_clone_builder is not None:
                self.button_menu_clone_builder.set_sensitive(False)
            if self.menu_preview_area is not None:
                self.menu_preview_area.queue_draw()

    def init_menu_page(self):
        assert self.builder is not None
        self.entry_menu_search = self.builder.get_object("entry_menu_search")
        self.combo_menu_engine_filter = self.builder.get_object(
            "combo_menu_engine_filter"
        )
        self.combo_menu_purpose_filter = self.builder.get_object(
            "combo_menu_purpose_filter"
        )
        self.combo_menu_sort = self.builder.get_object("combo_menu_sort")
        self.check_menu_installed_only = self.builder.get_object(
            "check_menu_installed_only"
        )
        self.flowbox_menu_presets = self.builder.get_object("flowbox_menu_presets")
        self.label_menu_count = self.builder.get_object("label_menu_count")
        self.label_menu_preview_title = self.builder.get_object(
            "label_menu_preview_title"
        )
        self.label_menu_preview_meta = self.builder.get_object(
            "label_menu_preview_meta"
        )
        self.label_menu_preview_tags = self.builder.get_object(
            "label_menu_preview_tags"
        )
        self.label_menu_preview_command = self.builder.get_object(
            "label_menu_preview_command"
        )
        self.menu_preview_area = self.builder.get_object("menu_preview_area")
        button_menu_import = self.builder.get_object("button_menu_import")
        button_menu_open_builder = self.builder.get_object("button_menu_open_builder")
        self.button_menu_copy_command = self.builder.get_object(
            "button_menu_copy_command"
        )
        self.button_menu_clone_builder = self.builder.get_object(
            "button_menu_clone_builder"
        )

        if self.combo_menu_engine_filter is not None:
            self.combo_menu_engine_filter.remove_all()
            self.combo_menu_engine_filter.append("all", "All Engines")
            for engine in MENU_ENGINE_BINARIES.keys():
                self.combo_menu_engine_filter.append(engine, engine.upper())
            self.combo_menu_engine_filter.set_active_id("all")
            self.combo_menu_engine_filter.connect(
                "changed", self.on_menu_filters_changed
            )

        if self.combo_menu_purpose_filter is not None:
            self.combo_menu_purpose_filter.remove_all()
            self.combo_menu_purpose_filter.append("all", "All Purposes")
            for purpose in ("launcher", "power", "scripts", "windows", "clipboard"):
                self.combo_menu_purpose_filter.append(purpose, purpose.title())
            self.combo_menu_purpose_filter.set_active_id("all")
            self.combo_menu_purpose_filter.connect(
                "changed", self.on_menu_filters_changed
            )

        if self.combo_menu_sort is not None:
            self.combo_menu_sort.remove_all()
            self.combo_menu_sort.append("name_asc", "Sort: Name A-Z")
            self.combo_menu_sort.append("name_desc", "Sort: Name Z-A")
            self.combo_menu_sort.append("engine", "Sort: Engine")
            self.combo_menu_sort.append("installed", "Sort: Installed First")
            self.combo_menu_sort.set_active_id("name_asc")
            self.combo_menu_sort.connect("changed", self.on_menu_filters_changed)

        if self.entry_menu_search is not None:
            self.entry_menu_search.connect("changed", self.on_menu_filters_changed)
        if self.check_menu_installed_only is not None:
            self.check_menu_installed_only.connect(
                "toggled", self.on_menu_filters_changed
            )
        if button_menu_import is not None:
            button_menu_import.connect("clicked", self.on_menu_import_clicked)
        if button_menu_open_builder is not None:
            button_menu_open_builder.connect(
                "clicked", self.on_menu_open_builder_clicked
            )
        if self.button_menu_copy_command is not None:
            self.button_menu_copy_command.connect(
                "clicked", self.on_menu_copy_command_clicked
            )
            self.button_menu_copy_command.set_sensitive(False)
        if self.button_menu_clone_builder is not None:
            self.button_menu_clone_builder.connect(
                "clicked", self.on_menu_clone_builder_clicked
            )
            self.button_menu_clone_builder.set_sensitive(False)
        if self.menu_preview_area is not None:
            self.menu_preview_area.connect("draw", self._draw_menu_preview_area)

        self.reload_menu_presets()

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
        page_gtk_themes = self.builder.get_object("page_gtk_themes")
        gtk_filter_bar = self.builder.get_object("gtk_themes_filter_bar")
        if page_gtk_themes is not None and gtk_filter_bar is not None:
            try:
                page_gtk_themes.reorder_child(gtk_filter_bar, 1)
            except Exception:
                pass

        if self.flowbox_gtk_themes is not None:
            self.flowbox_gtk_themes.set_min_children_per_line(1)
            self.flowbox_gtk_themes.set_max_children_per_line(2)

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
            current = self.gtk_theme_service.get_current_theme()
            if current:
                self._gtk_preview_theme_name = current

        self.reload_gtk_themes()

    def _make_theme_preview_strip(self, icon_names: list[str]):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.get_style_context().add_class("theme-preview-row")
        for icon_name in icon_names:
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            icon.set_pixel_size(16)
            row.pack_start(icon, False, False, 0)
        return row

    def _sanitize_cache_slug(self, value: str) -> str:
        slug = "".join(ch if ch.isalnum() else "_" for ch in str(value))
        slug = slug.strip("_")
        return (slug or "theme")[:56]

    def _gtk_theme_signature(self, theme) -> str:
        css_path = getattr(theme, "css_path", theme.path / "gtk-3.0" / "gtk.css")
        try:
            st = css_path.stat()
            resolved = str(css_path.resolve())
            return f"{resolved}:{int(st.st_mtime_ns)}:{int(st.st_size)}"
        except Exception:
            return f"{str(css_path)}:{theme.name}"

    def _gtk_preview_dimensions(self, variant: str) -> tuple[int, int]:
        if variant == "panel":
            return GTK_PREVIEW_PANEL_SIZE
        return GTK_PREVIEW_CARD_SIZE

    def _gtk_preview_cache_path(self, theme, variant: str) -> Path:
        width, height = self._gtk_preview_dimensions(variant)
        key = (
            f"gtk-preview-v1|{theme.name}|{variant}|{width}x{height}|"
            f"{self._gtk_theme_signature(theme)}"
        )
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
        slug = self._sanitize_cache_slug(theme.name)
        return self.gtk_preview_cache_dir / f"{slug}-{variant}-{digest}.png"

    def _load_preview_pixbuf(
        self, image_path: Path, width: int | None = None, height: int | None = None
    ):
        if not image_path.exists():
            return None
        try:
            if width is not None and height is not None:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(image_path), width, height, True
                )
            return GdkPixbuf.Pixbuf.new_from_file(str(image_path))
        except Exception:
            return None

    def _render_gtk_preview_to_cache(self, theme, variant: str, out_path: Path) -> bool:
        if not GTK_PREVIEW_RENDERER.exists():
            return False
        width, height = self._gtk_preview_dimensions(variant)
        tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
        cmd = [
            sys.executable,
            str(GTK_PREVIEW_RENDERER),
            "--theme",
            str(theme.name),
            "--output",
            str(tmp_path),
            "--width",
            str(width),
            "--height",
            str(height),
        ]
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=22,
                cwd=str(BASE_DIR),
            )
            if res.returncode != 0 or not tmp_path.exists():
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass
                return False
            tmp_path.replace(out_path)
            return True
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            return False

    def _schedule_gtk_preview_render(self, theme, variant: str):
        out_path = self._gtk_preview_cache_path(theme, variant)
        job_key = f"{variant}:{out_path.name}"
        if job_key in self._gtk_preview_render_jobs:
            return
        self._gtk_preview_render_jobs.add(job_key)

        def worker():
            ok = self._render_gtk_preview_to_cache(theme, variant, out_path)

            def finalize():
                self._gtk_preview_render_jobs.discard(job_key)
                if not ok:
                    if (
                        variant == "panel"
                        and self._gtk_preview_theme_name == theme.name
                        and self._gtk_preview_selected_label is not None
                    ):
                        self._gtk_preview_selected_label.set_text(
                            f"Preview render failed for: {theme.name}"
                        )
                    return False
                if variant == "card":
                    self._refresh_gtk_theme_card_images(theme.name)
                else:
                    if self._gtk_preview_theme_name == theme.name:
                        if self._set_gtk_theme_panel_preview_from_cache(theme):
                            if self._gtk_preview_selected_label is not None:
                                self._gtk_preview_selected_label.set_text(
                                    f"Previewing: {theme.name}"
                                )
                return False

            GLib.idle_add(finalize)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _refresh_gtk_theme_card_images(self, theme_name: str) -> None:
        theme = self._gtk_theme_meta_by_name.get(theme_name)
        if theme is None:
            return
        cache_path = self._gtk_preview_cache_path(theme, "card")
        width, height = self._gtk_preview_dimensions("card")
        pixbuf = self._load_preview_pixbuf(cache_path, width=width, height=height)
        if pixbuf is None:
            return
        alive: list[Gtk.Image] = []
        for image in self._gtk_preview_card_images.get(theme_name, []):
            if image.get_parent() is None:
                continue
            image.set_from_pixbuf(pixbuf)
            alive.append(image)
        self._gtk_preview_card_images[theme_name] = alive

    def _set_gtk_theme_card_preview_from_cache(
        self, theme, image: Gtk.Image, allow_render: bool
    ) -> None:
        cache_path = self._gtk_preview_cache_path(theme, "card")
        width, height = self._gtk_preview_dimensions("card")
        pixbuf = self._load_preview_pixbuf(cache_path, width=width, height=height)
        if pixbuf is not None:
            image.set_from_pixbuf(pixbuf)
            return

        image.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
        image.set_pixel_size(24)
        if allow_render:
            self._schedule_gtk_preview_render(theme, "card")

    def _set_gtk_theme_panel_preview_from_cache(self, theme) -> bool:
        if self.gtk_theme_preview_image is None:
            return False
        cache_path = self._gtk_preview_cache_path(theme, "panel")
        pixbuf = self._load_preview_pixbuf(cache_path)
        if pixbuf is None:
            return False
        self.gtk_theme_preview_image.set_from_pixbuf(pixbuf)
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

    def _build_gtk_theme_card_mockup(
        self, theme, allow_render: bool = False
    ) -> Gtk.Box:
        mini = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        mini.get_style_context().add_class("gtk-theme-mini-preview")
        mini.set_margin_top(2)
        mini.set_margin_bottom(2)
        mini.set_margin_start(2)
        mini.set_margin_end(2)

        image = Gtk.Image()
        image.set_halign(Gtk.Align.FILL)
        image.set_valign(Gtk.Align.FILL)
        image.set_hexpand(True)
        image.set_vexpand(False)
        image.set_size_request(-1, 116)
        mini.pack_start(image, True, True, 0)

        self._gtk_preview_card_images.setdefault(theme.name, []).append(image)
        self._set_gtk_theme_card_preview_from_cache(
            theme, image, allow_render=allow_render
        )
        return mini

    def reload_gtk_themes(self):
        if self.flowbox_gtk_themes is None:
            return
        self._clear_widget_children(self.flowbox_gtk_themes)
        self._gtk_preview_card_images = {}
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

        def add_theme_card(theme, is_current, index):
            if (
                reload_id != self._gtk_theme_reload_id
                or self.flowbox_gtk_themes is None
            ):
                return False
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            card.get_style_context().add_class("theme-card")
            card.get_style_context().add_class("gtk-theme-card")
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

            # Mini preview mirrors the right-side concept with real widgets.
            mini = self._build_gtk_theme_card_mockup(
                theme, allow_render=bool(is_current or index < 6)
            )
            card.pack_start(mini, False, False, 0)

            info = Gtk.Label(label="Press Preview for full panel")
            info.get_style_context().add_class("theme-subtitle")
            info.set_xalign(0.0)
            info.set_ellipsize(Pango.EllipsizeMode.END)
            card.pack_start(info, False, False, 0)

            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            preview_btn = Gtk.Button(label="Preview")
            preview_btn.get_style_context().add_class("theme-apply-button")
            preview_btn.get_style_context().add_class("theme-secondary-button")
            preview_btn.set_always_show_image(True)
            preview_btn.set_image_position(Gtk.PositionType.LEFT)
            preview_img = Gtk.Image.new_from_icon_name(
                "view-preview-symbolic", Gtk.IconSize.MENU
            )
            preview_img.set_pixel_size(14)
            preview_btn.set_image(preview_img)
            preview_btn.connect(
                "clicked", self.on_gtk_theme_preview_clicked, theme.name
            )
            actions.pack_start(preview_btn, True, True, 0)

            apply_btn = Gtk.Button(label="Apply Theme")
            apply_btn.get_style_context().add_class("suggested-action")
            apply_btn.get_style_context().add_class("theme-apply-button")
            apply_btn.get_style_context().add_class("theme-primary-button")
            apply_btn.set_always_show_image(True)
            apply_btn.set_image_position(Gtk.PositionType.LEFT)
            apply_img = Gtk.Image.new_from_icon_name(
                "object-select-symbolic", Gtk.IconSize.MENU
            )
            apply_img.set_pixel_size(14)
            apply_btn.set_image(apply_img)
            if is_current:
                apply_btn.set_label("Applied")
                apply_btn.set_sensitive(False)
            apply_btn.connect("clicked", self.on_gtk_theme_apply_clicked, theme.name)
            actions.pack_start(apply_btn, True, True, 0)

            card.pack_start(actions, False, False, 0)

            child = Gtk.FlowBoxChild()
            child.add(card)
            self.flowbox_gtk_themes.add(child)
            child.show_all()
            return False

        for idx, theme in enumerate(themes):
            GLib.idle_add(add_theme_card, theme, theme.name == current, idx)

    def _build_gtk_preview_mockup(self):
        container = self.gtk_theme_preview_container
        if container is None:
            return
        self._clear_widget_children(container)

        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        panel.set_margin_top(10)
        panel.set_margin_bottom(10)
        panel.set_margin_start(10)
        panel.set_margin_end(10)

        selected_label = Gtk.Label(label="Click Preview on a theme card")
        selected_label.get_style_context().add_class("theme-subtitle")
        selected_label.set_xalign(0.0)
        selected_label.set_ellipsize(Pango.EllipsizeMode.END)
        panel.pack_start(selected_label, False, False, 0)
        self._gtk_preview_selected_label = selected_label

        surface = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        surface.set_name("gtk_theme_preview_surface")
        surface.get_style_context().add_class("gtk-theme-preview-surface")
        surface.set_margin_top(4)
        surface.set_margin_bottom(4)
        surface.set_margin_start(4)
        surface.set_margin_end(4)
        self.gtk_theme_preview_surface = surface

        note = Gtk.Label(label="Rendered using the real GTK theme engine")
        note.get_style_context().add_class("theme-subtitle")
        note.set_xalign(0.0)
        surface.pack_start(note, False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_width(1)
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)
        image = Gtk.Image()
        image.set_halign(Gtk.Align.CENTER)
        image.set_valign(Gtk.Align.START)
        image.set_margin_top(6)
        image.set_margin_bottom(6)
        image.set_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG)
        image.set_pixel_size(46)
        image.set_hexpand(True)
        image.set_vexpand(True)
        scroll.add(image)
        surface.pack_start(scroll, True, True, 0)
        panel.pack_start(surface, True, True, 0)
        self.gtk_theme_preview_image = image

        container.add(panel)
        panel.show_all()

    def _update_gtk_theme_preview(self, theme_name):
        if self.gtk_theme_preview_image is None:
            return

        theme = self._gtk_theme_meta_by_name.get(theme_name)
        if theme is None:
            themes = self.gtk_theme_service.list_themes()
            self._gtk_theme_meta_by_name = {t.name: t for t in themes}
            theme = self._gtk_theme_meta_by_name.get(theme_name)
        if theme is None:
            return

        self._gtk_preview_theme_name = theme_name
        if self._set_gtk_theme_panel_preview_from_cache(theme):
            if self._gtk_preview_selected_label is not None:
                self._gtk_preview_selected_label.set_text(f"Previewing: {theme_name}")
        else:
            self.gtk_theme_preview_image.set_from_icon_name(
                "view-refresh-symbolic", Gtk.IconSize.DIALOG
            )
            self.gtk_theme_preview_image.set_pixel_size(38)
            if self._gtk_preview_selected_label is not None:
                self._gtk_preview_selected_label.set_text(
                    f"Rendering preview: {theme_name}..."
                )
        self._schedule_gtk_preview_render(theme, "panel")

        self._schedule_gtk_preview_render(theme, "card")

    def on_gtk_theme_preview_clicked(self, _button, theme_name):
        self._update_gtk_theme_preview(theme_name)

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
        self.entry_window_themes_search = self.builder.get_object(
            "entry_window_themes_search"
        )
        if self.entry_window_themes_search is None:
            page_window_themes = self.builder.get_object("page_window_themes")
            if page_window_themes is not None:
                entry = Gtk.SearchEntry()
                entry.set_name("entry_window_themes_search")
                entry.set_placeholder_text("Search window themes...")
                entry.set_width_chars(28)
                page_window_themes.pack_start(entry, False, False, 0)
                try:
                    page_window_themes.reorder_child(entry, 1)
                except Exception:
                    pass
                entry.show()
                self.entry_window_themes_search = entry
        if self.entry_window_themes_search is not None:
            self.entry_window_themes_search.connect(
                "changed", lambda _w: self.reload_window_themes()
            )
        self.reload_window_themes()

    def reload_window_themes(self):
        if self.flowbox_window_themes is None:
            return
        self._clear_widget_children(self.flowbox_window_themes)
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

        themes = self.window_theme_service.list_themes()
        if query:
            themes = [t for t in themes if query in t.name.lower()]
        current = self.window_theme_service.get_current_theme()

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

            preview = self._make_theme_preview_strip(
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

    def init_icon_themes_page(self):
        assert self.builder is not None
        self.flowbox_icon_themes = self.builder.get_object("flowbox_icon_themes")
        self.entry_icons_search = self.builder.get_object("entry_icons_search")
        if self.flowbox_icon_themes is not None:
            self.flowbox_icon_themes.set_min_children_per_line(1)
            self.flowbox_icon_themes.set_max_children_per_line(4)

        if self.entry_icons_search is not None:
            self.entry_icons_search.connect(
                "changed", lambda _w: self.reload_icon_themes()
            )

        self.reload_icon_themes()

    def reload_icon_themes(self):
        if self.flowbox_icon_themes is None:
            return

        self._clear_widget_children(self.flowbox_icon_themes)
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
        themes = self.interface_theme_service.list_icon_themes()
        current = self.interface_theme_service.get_current_icon_theme()
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

    def on_icon_theme_preview_clicked(self, _button, theme_name, display_name=None):
        title_name = str(display_name or theme_name)
        dialog = Gtk.Dialog(
            title=f"Icon Preview - {title_name}",
            transient_for=self.window,
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
        ok, message = self.interface_theme_service.apply_icon_theme(theme_name)
        self._show_message(message)
        if ok:
            self.reload_icon_themes()
            return

        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()

    def init_cursor_themes_page(self):
        assert self.builder is not None
        self.flowbox_cursor_themes = self.builder.get_object("flowbox_cursor_themes")
        self.entry_cursors_search = self.builder.get_object("entry_cursors_search")

        if self.entry_cursors_search is not None:
            self.entry_cursors_search.connect(
                "changed", lambda _w: self.reload_cursor_themes()
            )

        self.reload_cursor_themes()

    def reload_cursor_themes(self):
        if self.flowbox_cursor_themes is None:
            return

        self._clear_widget_children(self.flowbox_cursor_themes)
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
        themes = self.interface_theme_service.list_cursor_themes()
        current = self.interface_theme_service.get_current_cursor_theme()
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

            preview = self._make_theme_preview_strip(
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
        ok, message = self.interface_theme_service.apply_cursor_theme(theme_name)
        self._show_message(message)
        if ok:
            self.reload_cursor_themes()
            return

        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()

    def init_settings_page(self):
        assert self.builder is not None
        self.list_diagnostics = self.builder.get_object("list_diagnostics")
        self.list_paths = self.builder.get_object("list_paths")
        self.btn_clear_cache = self.builder.get_object("btn_clear_cache")
        self.btn_reset_settings = self.builder.get_object("btn_reset_settings")

        if self.list_diagnostics:
            tools = detect_external_tools()
            for name, path in tools.items():
                status = "Installed" if path else "Missing"
                self._add_settings_row(
                    self.list_diagnostics,
                    name.replace("_", " ").title(),
                    status,
                    path or "N/A",
                )

        if self.list_paths:
            self._add_settings_row(
                self.list_paths,
                "Settings File",
                "JSON",
                str(self.settings.settings_file),
            )
            self._add_settings_row(
                self.list_paths, "Cache Directory", "Folder", str(self.cache_dir)
            )
            self._add_settings_row(
                self.list_paths,
                "Library Directory",
                "Folder",
                str(BASE_DIR / "library"),
            )

        if self.btn_clear_cache:
            self.btn_clear_cache.connect("clicked", self.on_clear_cache_clicked)

        if self.btn_reset_settings:
            self.btn_reset_settings.connect("clicked", self.on_reset_settings_clicked)

    def _add_settings_row(self, listbox, title, status, details):
        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_title = Gtk.Label(label=title)
        lbl_title.set_xalign(0)
        lbl_title.get_style_context().add_class("theme-title")

        lbl_details = Gtk.Label(label=details)
        lbl_details.set_xalign(0)
        lbl_details.get_style_context().add_class("theme-subtitle")
        lbl_details.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_details.set_max_width_chars(60)

        vbox.pack_start(lbl_title, False, False, 0)
        vbox.pack_start(lbl_details, False, False, 0)

        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        status_box.set_valign(Gtk.Align.CENTER)
        lbl_status = Gtk.Label(label=status)
        lbl_status.get_style_context().add_class("theme-type-badge")
        if status.lower() == "missing":
            lbl_status.get_style_context().add_class("bar-status-warn")
        elif status.lower() == "installed":
            lbl_status.get_style_context().add_class("bar-status-ok")

        status_box.pack_end(lbl_status, False, False, 0)

        box.pack_start(vbox, True, True, 0)
        box.pack_end(status_box, False, False, 0)

        row.add(box)
        listbox.add(row)
        row.show_all()

    def on_clear_cache_clicked(self, _button):
        def clear_task():
            count = 0
            for p in self.cache_dir.rglob("*"):
                if p.is_file() and p.name != "palette_cache.json":
                    try:
                        p.unlink()
                        count += 1
                    except Exception:
                        pass
            GLib.idle_add(self._show_message, f"Cleared {count} cached files")

        threading.Thread(target=clear_task, daemon=True).start()

    def on_reset_settings_clicked(self, _button):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Reset all settings?",
        )
        dialog.format_secondary_text(
            "This will revert all app preferences to defaults. This action cannot be undone."
        )
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            self.settings.data = {}
            self.settings.save()
            self._show_message("Settings reset. Please restart the application.")

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
        self.wallpaper_list_scroller = self.builder.get_object(
            "wallpaper_list_scroller"
        )
        self.wallpaper_flowbox = self.builder.get_object("wallpaper_flowbox")
        self.wallpaper_listbox = self.builder.get_object("wallpaper_listbox")
        self.label_wallpaper_count = self.builder.get_object("label_wallpaper_count")
        self.wallpaper_controls_box = self.builder.get_object("wallpaper_controls_box")
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
                "scroll-event", self.on_wallpaper_zoom_scroll
            )
            self.wallpaper_grid_scroller.connect(
                "size-allocate", self.on_wallpaper_grid_scroller_size_allocate
            )
        if self.wallpaper_list_scroller is not None:
            self.wallpaper_list_scroller.connect(
                "scroll-event", self.on_wallpaper_zoom_scroll
            )
        if self.wallpaper_flowbox is not None:
            self.wallpaper_flowbox.connect(
                "scroll-event", self.on_wallpaper_zoom_scroll
            )
        if self.wallpaper_listbox is not None:
            self.wallpaper_listbox.connect(
                "scroll-event", self.on_wallpaper_zoom_scroll
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

        self._ensure_wallpaper_source_picker()
        self._refine_wallpaper_controls_layout()
        self._dock_wallpaper_count_footer()
        self.sync_wallpaper_controls_from_settings()
        self.reload_wallpapers()

    def _ensure_wallpaper_source_picker(self):
        if self.wallpaper_source_picker is not None:
            return

        picker = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        picker.get_style_context().add_class("source-segmented")

        system_btn = Gtk.RadioButton.new_with_label_from_widget(None, "System")
        custom_btn = Gtk.RadioButton.new_with_label_from_widget(system_btn, "Custom")

        for btn, edge in (
            (system_btn, "mode-left"),
            (custom_btn, "mode-right"),
        ):
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.set_mode(False)
            btn.set_can_focus(True)
            ctx = btn.get_style_context()
            ctx.add_class("mode-link-btn")
            ctx.add_class("source-choice-btn")
            ctx.add_class(edge)
            picker.pack_start(btn, False, False, 0)

        system_btn.connect("toggled", self.on_wallpaper_source_choice_toggled, "system")
        custom_btn.connect("toggled", self.on_wallpaper_source_choice_toggled, "custom")

        picker.show_all()
        self.wallpaper_source_picker = picker
        self.wallpaper_source_system_btn = system_btn
        self.wallpaper_source_custom_btn = custom_btn

    def _refine_wallpaper_controls_layout(self):
        box = self.wallpaper_controls_box
        if box is None:
            return
        if bool(getattr(box, "_loom_refined_layout", False)):
            return

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_hexpand(True)
        row.get_style_context().add_class("wallpaper-controls-row")

        if self.entry_wallpaper_search is not None:
            self.entry_wallpaper_search.set_hexpand(False)
            self.entry_wallpaper_search.set_width_chars(14)
            self.entry_wallpaper_search.set_size_request(170, -1)
        if self.chooser_wallpaper_folder is not None:
            self.chooser_wallpaper_folder.set_hexpand(False)
            self.chooser_wallpaper_folder.set_size_request(220, -1)
        if self.combo_wallpaper_fill_mode is not None:
            self.combo_wallpaper_fill_mode.set_size_request(120, -1)
        if self.combo_wallpaper_sort is not None:
            self.combo_wallpaper_sort.set_size_request(120, -1)
        if self.label_wallpaper_folder is not None:
            self.label_wallpaper_folder.set_text("Folder")
        fill_label = self.builder.get_object("label_wallpaper_fill_mode")
        if fill_label is not None:
            fill_label.set_text("Fill")
        source_label = self.builder.get_object("label_wallpaper_source")
        if source_label is not None:
            source_label.hide()
        if self.switch_wallpaper_system_source is not None:
            self.switch_wallpaper_system_source.hide()

        for child in list(box.get_children()):
            box.remove(child)

        widgets = [
            self.wallpaper_source_picker,
            fill_label,
            self.combo_wallpaper_fill_mode,
            self.combo_wallpaper_sort,
            self.label_wallpaper_folder,
            self.chooser_wallpaper_folder,
            self.entry_wallpaper_search,
        ]
        for w in widgets:
            if w is None:
                continue
            row.pack_start(w, False, False, 0)

        if self.entry_wallpaper_search is not None:
            row.set_child_packing(
                self.entry_wallpaper_search, False, False, 0, Gtk.PackType.START
            )

        box.set_orientation(Gtk.Orientation.VERTICAL)
        box.set_spacing(0)
        box.pack_start(row, False, False, 0)
        box._loom_refined_layout = True
        box.show_all()

    def _dock_wallpaper_count_footer(self):
        if self.label_wallpaper_count is None:
            return
        if self.wallpaper_footer_bar is not None:
            return
        if self.builder is None:
            return

        page = self.builder.get_object("page_wallpapers")
        if page is None:
            return

        parent = self.label_wallpaper_count.get_parent()
        if parent is not None:
            parent.remove(self.label_wallpaper_count)

        self.label_wallpaper_count.set_xalign(0.0)
        self.label_wallpaper_count.get_style_context().add_class(
            "wallpaper-count-footer"
        )

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        footer.get_style_context().add_class("wallpaper-footer")
        footer.set_margin_start(2)
        footer.set_margin_end(2)
        footer.set_margin_bottom(1)
        footer.pack_start(self.label_wallpaper_count, False, False, 0)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        footer.pack_start(spacer, True, True, 0)

        if self.scale_wallpaper_thumb_size is None:
            scale = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 180.0, 420.0, 10.0
            )
            scale.connect("value-changed", self.on_wallpaper_thumb_size_changed)
            self.scale_wallpaper_thumb_size = scale

        if self.scale_wallpaper_thumb_size is not None:
            zoom_scale = self.scale_wallpaper_thumb_size
            zoom_scale.set_draw_value(False)
            zoom_scale.set_size_request(92, 12)
            zoom_scale.set_digits(0)
            zoom_scale.set_value_pos(Gtk.PositionType.RIGHT)
            zoom_scale.set_tooltip_text("Wallpaper zoom")
            zoom_scale.get_style_context().add_class("wallpaper-zoom-compact")
            parent = zoom_scale.get_parent()
            if parent is not None:
                parent.remove(zoom_scale)
            footer.pack_end(zoom_scale, False, False, 0)
            self.wallpaper_footer_zoom_scale = zoom_scale

        page.pack_end(footer, False, False, 0)
        self.wallpaper_footer_bar = footer
        footer.show_all()

    def sync_wallpaper_controls_from_settings(self):
        self._loading_wallpaper_state = True
        try:
            source = self.wallpaper_service.get_source()
            fill_mode = self.wallpaper_service.get_fill_mode()
            sort_mode = self.wallpaper_service.get_sort_mode()
            custom_dirs = self.wallpaper_service.get_custom_dirs()
            is_system = source == "system"

            if self.switch_wallpaper_system_source is not None:
                self.switch_wallpaper_system_source.set_active(is_system)
            if self.wallpaper_source_system_btn is not None:
                self.wallpaper_source_system_btn.set_active(is_system)
            if self.wallpaper_source_custom_btn is not None:
                self.wallpaper_source_custom_btn.set_active(not is_system)

            if self.chooser_wallpaper_folder is not None:
                self.chooser_wallpaper_folder.set_sensitive(not is_system)
                if custom_dirs:
                    custom_path = custom_dirs[0]
                    if custom_path.exists():
                        self.chooser_wallpaper_folder.set_filename(str(custom_path))

            if self.label_wallpaper_folder is not None:
                self.label_wallpaper_folder.set_sensitive(not is_system)

            if self.combo_wallpaper_fill_mode is not None:
                idx = FILL_MODES.index(fill_mode) if fill_mode in FILL_MODES else 0
                self.combo_wallpaper_fill_mode.set_active(idx)
            if self.combo_wallpaper_sort is not None:
                sort_index = {
                    "name_asc": 0,
                    "name_desc": 1,
                    "newest": 2,
                    "oldest": 3,
                }
                self.combo_wallpaper_sort.set_active(sort_index.get(sort_mode, 0))
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
        flowbox = self.wallpaper_flowbox
        if flowbox is None:
            return

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
                break

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
                flowbox.add(flow_child)
                flow_child.show_all()
                return False

            GLib.idle_add(add_wallpaper_card, entry, palette, pixbuf)

        self._save_palette_cache_to_disk()

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
        self.init_settings_page()
        self.init_wallpaper_page()
        self.init_bar_page()
        self.init_menu_page()
        self.init_window_themes_page()
        self.init_gtk_themes_page()
        self.init_icon_themes_page()
        self.init_cursor_themes_page()
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
