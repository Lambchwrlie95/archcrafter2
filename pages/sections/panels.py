"""Panels section page (moved from pages/mixer)."""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from pages import register_page
from pages.base import BasePage

# Local constants
BASE_DIR = Path(__file__).resolve().parent.parent.parent
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


@register_page
class PanelsPage(BasePage):
    id = "panels"
    title = "Panels"
    icon = "transform-scale-symbolic"

    def __init__(self):
        super().__init__()
        self.label_bar_runtime_hint = None
        self.label_bar_polybar_status = None
        self.label_bar_tint2_status = None
        self.image_bar_polybar_preview = None
        self.image_bar_tint2_preview = None
        self.preview_polybar_strip = None
        self.preview_tint2_strip = None
        self.label_bar_polybar_preview_meta = None
        self.label_bar_tint2_preview_meta = None
        self.button_bar_polybar_apply = None
        self.button_bar_tint2_apply = None
        self.button_bar_polybar_open = None
        self.button_bar_tint2_open = None
        self._bar_preview_refresh_source = None

    @staticmethod
    def get_sidebar_items():
        return [
            ("panels", "Panels", "transform-scale-symbolic", "Polybar/Tint2 panels"),
        ]

    def build(self, app, builder):
        self.app = app
        widget = builder.get_object("page_panels")
        self.widget = widget

        self.label_bar_runtime_hint = builder.get_object("label_bar_runtime_hint")
        self.label_bar_polybar_status = builder.get_object("label_bar_polybar_status")
        self.label_bar_tint2_status = builder.get_object("label_bar_tint2_status")
        self.image_bar_polybar_preview = builder.get_object("image_bar_polybar_preview")
        self.image_bar_tint2_preview = builder.get_object("image_bar_tint2_preview")
        self.preview_polybar_strip = builder.get_object("preview_polybar_strip")
        self.preview_tint2_strip = builder.get_object("preview_tint2_strip")
        self.label_bar_polybar_preview_meta = builder.get_object(
            "label_bar_polybar_preview_meta"
        )
        self.label_bar_tint2_preview_meta = builder.get_object(
            "label_bar_tint2_preview_meta"
        )
        self.button_bar_polybar_apply = builder.get_object("button_bar_polybar_apply")
        self.button_bar_tint2_apply = builder.get_object("button_bar_tint2_apply")
        self.button_bar_polybar_open = builder.get_object("button_bar_polybar_open")
        self.button_bar_tint2_open = builder.get_object("button_bar_tint2_open")
        button_polybar_copy = builder.get_object("button_bar_polybar_copy")
        button_tint2_copy = builder.get_object("button_bar_tint2_copy")
        button_open_builder = builder.get_object("button_bar_open_builder")

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
        return widget

    def on_activate(self, app):
        self.refresh_bar_page_state(refresh_preview=True)
        self._ensure_bar_preview_refresh(True)

    def on_deactivate(self, app):
        self._ensure_bar_preview_refresh(False)

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
            self.app.active_top_mode != "mixer"
            or self.app.content_stack is None
            or self.app.content_stack.get_visible_child_name() != "panels"
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
            self.app._show_message("Unknown bar target")
            return

        title = str(spec["title"])
        preset = self._preferred_bar_preset(target)
        source = self._bar_preset_source_file(target)
        dest = self._bar_target_config_file(target)
        if source is None or dest is None:
            self.app._show_message(f"Cannot install {title} preset")
            return
        if not source.exists():
            self.app._show_message(f"{title} preset file missing: {source}")
            return

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            backup = self._backup_file(dest)
            shutil.copy2(source, dest)
        except Exception as exc:
            self.app._show_message(f"Failed to install {title} preset: {exc}")
            return

        preset_name = "default"
        if preset is not None:
            preset_name = str(preset.get("name", "default"))

        if backup is None:
            self.app._show_message(
                f"Installed {title} preset '{preset_name}' to {dest}"
            )
        else:
            self.app._show_message(
                f"Installed {title} preset '{preset_name}' to {dest} (backup: {backup.name})"
            )
        self.refresh_bar_page_state(refresh_preview=True)

    def _open_bar_config_dir(self, target: str):
        spec = BAR_PRESET_TARGETS.get(target)
        if spec is None:
            self.app._show_message("Unknown bar target")
            return

        title = str(spec["title"])
        config_dir = Path(spec["config_dir"])
        if not config_dir.exists():
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
                self.app._show_message(f"Created {title} config folder")
            except Exception as exc:
                self.app._show_message(
                    f"{title} config folder not found: {config_dir} ({exc})"
                )
                return

        opener = shutil.which("xdg-open")
        if opener is None:
            self.app._show_message("Cannot open folder: xdg-open is not installed")
            return

        try:
            subprocess.Popen([opener, str(config_dir)])
            self.app._show_message(f"Opened {title} config folder")
            self.refresh_bar_page_state()
        except Exception as exc:
            self.app._show_message(f"Failed to open {title} folder: {exc}")

    def _copy_bar_config_path(self, target: str):
        spec = BAR_PRESET_TARGETS.get(target)
        if spec is None:
            self.app._show_message("Unknown bar target")
            return

        display = Gdk.Display.get_default()
        if display is None:
            self.app._show_message("Cannot copy path: no display available")
            return

        clipboard = Gtk.Clipboard.get_default(display)
        if clipboard is None:
            self.app._show_message("Cannot copy path: clipboard unavailable")
            return

        config_dir = str(spec["config_dir"])
        clipboard.set_text(config_dir, -1)
        clipboard.store()
        self.app._show_message(f"Copied {spec['title']} config path")

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
        if self.app.mode_builder_btn is not None:
            self.app.mode_builder_btn.set_active(True)
