"""Menu section page (moved from pages/mixer)."""

import os
import shutil
from pathlib import Path
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

from pages.base import BasePage
from pages import register_page

# Globals
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




@register_page
class MenuPage(BasePage):
    id = "menu"
    title = "Menu"
    icon = "ac-jgmenu-symbolic"

    def __init__(self):
        super().__init__()
        self.entry_menu_search = None
        self.combo_menu_engine_filter = None
        self.combo_menu_purpose_filter = None
        self.combo_menu_sort = None
        self.check_menu_installed_only = None
        self.flowbox_menu_presets = None
        self.label_menu_count = None
        self.label_menu_preview_title = None
        self.label_menu_preview_meta = None
        self.label_menu_preview_tags = None
        self.label_menu_preview_command = None
        self.menu_preview_area = None
        self.button_menu_copy_command = None
        self.button_menu_clone_builder = None
        self._menu_selected_preset_id = None

    @staticmethod
    def get_sidebar_items():
        return [
            ("menu", "Menu", "ac-jgmenu-symbolic", "jgmenu configuration"),
        ]

    def build(self, app, builder):
        self.app = app
        widget = builder.get_object("page_menu")
        self.widget = widget
        
        # Method: init_menu_page inline
        self.entry_menu_search = builder.get_object("entry_menu_search")
        self.combo_menu_engine_filter = builder.get_object("combo_menu_engine_filter")
        self.combo_menu_purpose_filter = builder.get_object("combo_menu_purpose_filter")
        self.combo_menu_sort = builder.get_object("combo_menu_sort")
        self.check_menu_installed_only = builder.get_object("check_menu_installed_only")
        self.flowbox_menu_presets = builder.get_object("flowbox_menu_presets")
        self.label_menu_count = builder.get_object("label_menu_count")
        self.label_menu_preview_title = builder.get_object("label_menu_preview_title")
        self.label_menu_preview_meta = builder.get_object("label_menu_preview_meta")
        self.label_menu_preview_tags = builder.get_object("label_menu_preview_tags")
        self.label_menu_preview_command = builder.get_object("label_menu_preview_command")
        self.menu_preview_area = builder.get_object("menu_preview_area")
        
        button_menu_import = builder.get_object("button_menu_import")
        button_menu_open_builder = builder.get_object("button_menu_open_builder")
        self.button_menu_copy_command = builder.get_object("button_menu_copy_command")
        self.button_menu_clone_builder = builder.get_object("button_menu_clone_builder")

        if self.combo_menu_engine_filter is not None:
            self.combo_menu_engine_filter.remove_all()
            self.combo_menu_engine_filter.append("all", "All Engines")
            for engine in MENU_ENGINE_BINARIES.keys():
                self.combo_menu_engine_filter.append(engine, engine.upper())
            self.combo_menu_engine_filter.set_active_id("all")
            self.combo_menu_engine_filter.connect("changed", self.on_menu_filters_changed)

        if self.combo_menu_purpose_filter is not None:
            self.combo_menu_purpose_filter.remove_all()
            self.combo_menu_purpose_filter.append("all", "All Purposes")
            for purpose in ("launcher", "power", "scripts", "windows", "clipboard"):
                self.combo_menu_purpose_filter.append(purpose, purpose.title())
            self.combo_menu_purpose_filter.set_active_id("all")
            self.combo_menu_purpose_filter.connect("changed", self.on_menu_filters_changed)

        if self.combo_menu_sort is not None:
            self.combo_menu_sort.connect("changed", self.on_menu_filters_changed)
        if self.entry_menu_search is not None:
            self.entry_menu_search.connect("changed", self.on_menu_filters_changed)
        if self.check_menu_installed_only is not None:
            self.check_menu_installed_only.connect("toggled", self.on_menu_filters_changed)

        if button_menu_import is not None:
            button_menu_import.connect("clicked", self.on_menu_import_clicked)
        if button_menu_open_builder is not None:
            button_menu_open_builder.connect("clicked", self.on_menu_open_builder_clicked)

        if self.button_menu_copy_command is not None:
            self.button_menu_copy_command.connect("clicked", self.on_menu_copy_command_clicked)
        if self.button_menu_clone_builder is not None:
            self.button_menu_clone_builder.connect("clicked", self.on_menu_clone_builder_clicked)

        if self.menu_preview_area is not None:
            self.menu_preview_area.connect("draw", self._draw_menu_preview_area)

        self.reload_menu_presets()
        
        return widget

    def on_activate(self, app):
        self.reload_menu_presets()
        app._ensure_bar_preview_refresh(False)

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
            self.app._show_message("Cannot copy: no display available")
            return
        clipboard = Gtk.Clipboard.get_default(display)
        if clipboard is None:
            self.app._show_message("Cannot copy: clipboard unavailable")
            return
        clipboard.set_text(str(text), -1)
        clipboard.store()
        self.app._show_message(ok_message)

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

        self.app._rounded_rect(cr, 0.5, 0.5, w, h, 10.0)
        r, g, b = self.app._hex_to_rgb(bg)
        cr.set_source_rgb(r, g, b)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.0)
        cr.stroke()

        top_h = max(16.0, h * 0.22)
        self.app._rounded_rect(cr, 6.0, 6.0, max(1.0, w - 12.0), top_h, 6.0)
        r, g, b = self.app._hex_to_rgb(panel)
        cr.set_source_rgb(r, g, b)
        cr.fill()

        entry_y = 8.0 + (top_h - 12.0) / 2.0
        self.app._rounded_rect(cr, 12.0, entry_y, max(24.0, w * 0.58), 12.0, 5.0)
        r, g, b = self.app._hex_to_rgb(surface)
        cr.set_source_rgb(r, g, b)
        cr.fill_preserve()
        cr.set_source_rgba(1.0, 1.0, 1.0, 0.08)
        cr.set_line_width(1.0)
        cr.stroke()

        self.app._rounded_rect(cr, max(18.0, w - 68.0), entry_y, 56.0, 12.0, 5.0)
        r, g, b = self.app._hex_to_rgb(accent)
        cr.set_source_rgb(r, g, b)
        cr.fill()

        rows = 3 if compact else 6
        start_y = top_h + 15.0
        row_h = max(8.0, (h - start_y - 10.0) / max(1, rows))
        tr, tg, tb = self.app._hex_to_rgb(text)
        for idx in range(rows):
            y = start_y + (idx * row_h)
            self.app._rounded_rect(cr, 10.0, y, max(20.0, w - 20.0), row_h - 4.0, 4.0)
            alpha = 0.18 if idx == 1 else 0.10
            cr.set_source_rgba(tr, tg, tb, alpha)
            cr.fill()

            if idx == 1:
                self.app._rounded_rect(
                    cr,
                    10.0,
                    y,
                    max(18.0, min(8.0 + w * 0.06, w - 20.0)),
                    row_h - 4.0,
                    4.0,
                )
                r, g, b = self.app._hex_to_rgb(accent)
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
            transient_for=self.app.window,
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
        if self.app.mode_builder_btn is not None:
            self.app.mode_builder_btn.set_active(True)
        builder_sidebar = self._get_mode_sidebar_widget("builder")
        if builder_sidebar is not None:
            row = self._find_row_by_item_id(builder_sidebar, "builder_menus")
            if row is not None:
                builder_sidebar.select_row(row)
        if preset_name:
            self.app._show_message(f"Builder Menus opened for '{preset_name}'")
        else:
            self.app._show_message("Builder Menus workspace opened")

    def on_menu_card_builder_clicked(self, _button, preset_id: str):
        preset = self._menu_preset_by_id(preset_id)
        if preset is None:
            return
        self._set_menu_preview_preset(preset_id)
        self._open_builder_menu_workspace(str(preset.get("name", "Menu preset")))

    def on_menu_filters_changed(self, _widget):
        self.reload_menu_presets()

    def on_menu_import_clicked(self, _button):
        self.app._show_message(
            "Menu importer scaffold ready. Next: file picker + preset manifest."
        )

    def on_menu_open_builder_clicked(self, _button):
        self._open_builder_menu_workspace()

    def on_menu_copy_command_clicked(self, _button):
        preset = self._menu_preset_by_id(self._menu_selected_preset_id)
        if preset is None:
            self.app._show_message("Select a menu preset first")
            return
        self._copy_text_to_clipboard(
            str(preset.get("command", "")),
            f"Copied command for {preset.get('name', 'preset')}",
        )

    def on_menu_clone_builder_clicked(self, _button):
        preset = self._menu_preset_by_id(self._menu_selected_preset_id)
        if preset is None:
            self.app._show_message("Select a menu preset first")
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


