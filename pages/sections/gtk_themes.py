"""GTK Themes section page (moved from pages/mixer)."""

import threading
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk, Pango

from pages import register_page
from pages.base import BasePage

# Local constants
GTK_PREVIEW_RENDERER = (
    Path(__file__).resolve().parent.parent.parent
    / "backend"
    / "gtk_preview_renderer.py"
)
GTK_PREVIEW_CARD_SIZE = (320, 150)
GTK_PREVIEW_PANEL_SIZE = (640, 420)


@register_page
class GtkThemesPage(BasePage):
    id = "gtk_themes"
    title = "GTK Themes"
    icon = "preferences-desktop-theme-symbolic"

    def __init__(self):
        super().__init__()
        self.flowbox_gtk_themes = None
        self.entry_gtk_themes_search = None
        self.combo_gtk_themes_filter = None
        self.gtk_theme_preview_container = None
        self.gtk_theme_preview_surface = None
        self.gtk_theme_preview_image = None
        self._gtk_preview_selected_label = None
        self._gtk_preview_theme_name = None
        self._gtk_preview_card_images = {}
        self._gtk_preview_render_jobs = set()
        self._gtk_theme_reload_id = 0
        self._gtk_theme_meta_by_name = {}

    @staticmethod
    def get_sidebar_items():
        return [
            (
                "gtk_themes",
                "GTK Themes",
                "preferences-desktop-theme-symbolic",
                "GTK theme selection",
            ),
        ]

    def build(self, app, builder):
        self.app = app
        widget = builder.get_object("page_gtk_themes")
        self.widget = widget

        self.flowbox_gtk_themes = builder.get_object("flowbox_gtk_themes")
        self.entry_gtk_themes_search = builder.get_object("entry_gtk_themes_search")
        self.combo_gtk_themes_filter = builder.get_object("combo_gtk_themes_filter")
        self.gtk_theme_preview_container = builder.get_object(
            "gtk_theme_preview_container"
        )

        gtk_filter_bar = builder.get_object("gtk_themes_filter_bar")
        if widget is not None and gtk_filter_bar is not None:
            try:
                widget.reorder_child(gtk_filter_bar, 1)
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
            current = self.app.gtk_theme_service.get_current_theme()
            if current:
                self._gtk_preview_theme_name = current

        self.reload_gtk_themes()
        return widget

    def on_activate(self, app):
        self.reload_gtk_themes()

    def _sanitize_cache_slug(self, value: str) -> str:
        slug = "".join(ch if ch.isalnum() else "_" for ch in str(value))
        slug = slug.strip("_")
        return (slug or "theme")[:56]

    def _gtk_theme_signature(self, theme) -> str:
        return self.app.gtk_theme_service._theme_signature(theme)

    def _gtk_preview_dimensions(self, variant: str) -> tuple[int, int]:
        if variant == "panel":
            return GTK_PREVIEW_PANEL_SIZE
        return GTK_PREVIEW_CARD_SIZE

    def _gtk_preview_cache_path(self, theme, variant: str) -> Path:
        return self.app.gtk_theme_service.preview_cache_path(
            theme,
            variant,
            GTK_PREVIEW_CARD_SIZE if variant != "panel" else GTK_PREVIEW_PANEL_SIZE,
        )

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
        return self.app.gtk_theme_service.render_preview_to_cache(
            theme, variant, out_path, GTK_PREVIEW_RENDERER
        )

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
        self.app._clear_widget_children(self.flowbox_gtk_themes)
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
        themes = self.app.gtk_theme_service.list_themes()
        current = self.app.gtk_theme_service.get_current_theme()
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
        self.app._clear_widget_children(container)

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
            themes = self.app.gtk_theme_service.list_themes()
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
        ok, message = self.app.gtk_theme_service.apply_theme(theme_name)
        self.app._show_message(message)
        if ok:
            self.reload_gtk_themes()
            self._update_gtk_theme_preview(theme_name)
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
