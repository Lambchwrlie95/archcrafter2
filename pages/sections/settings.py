"""Settings section page (moved from pages/mixer)."""

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

from backend.deps import detect_external_tools
from pages import register_page
from pages.base import BasePage

BASE_DIR = Path(__file__).resolve().parent.parent.parent


@register_page
class SettingsPage(BasePage):
    id = "settings"
    title = "Settings"
    icon = "applications-system-symbolic"

    def __init__(self):
        super().__init__()
        self.list_diagnostics = None
        self.list_paths = None
        self.btn_clear_cache = None
        self.btn_reset_settings = None

    @staticmethod
    def get_sidebar_items():
        # Settings typically does not show in the standard sidebar, but is triggered by the gear icon.
        # We can leave this empty or provide a placeholder.
        return []

    def build(self, app, builder):
        self.app = app
        widget = builder.get_object("page_settings")
        self.widget = widget

        self.list_diagnostics = builder.get_object("list_diagnostics")
        self.list_paths = builder.get_object("list_paths")
        self.btn_clear_cache = builder.get_object("btn_clear_cache")
        self.btn_reset_settings = builder.get_object("btn_reset_settings")

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
                str(self.app.settings.settings_file),
            )
            self._add_settings_row(
                self.list_paths,
                "Cache Directory",
                "Folder",
                str(self.app.services.wallpapers.cache_dir),
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

        return widget

    def on_activate(self, app):
        pass

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
            for p in self.app.services.wallpapers.cache_dir.rglob("*"):
                if p.is_file() and p.name != "palette_cache.json":
                    try:
                        p.unlink()
                        count += 1
                    except Exception:
                        pass
            GLib.idle_add(self.app._show_message, f"Cleared {count} cached files")

        threading.Thread(target=clear_task, daemon=True).start()

    def on_reset_settings_clicked(self, _button):
        dialog = Gtk.MessageDialog(
            transient_for=self.app.window,
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
            self.app.settings.data = {}
            self.app.settings.save()
            self.app._show_message("Settings reset. Please restart the application.")
