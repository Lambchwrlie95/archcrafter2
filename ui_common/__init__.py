"""Shared UI components for pages."""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")

from typing import Optional

from gi.repository import Gtk, GdkPixbuf, Pango


def make_action_icon_button(icon_name: str, tooltip: str) -> Gtk.Button:
    """Create a standard action button with icon."""
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


def make_sidebar_row(
    item_id: str, title: str, icon_name: str, subtitle: str
) -> Gtk.ListBoxRow:
    """Create a standard sidebar row."""
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
    return row


def make_card_label(
    text: str, css_class: Optional[str] = None, xalign: float = 0.0
) -> Gtk.Label:
    """Create a standard card label."""
    label = Gtk.Label(label=text)
    label.set_xalign(xalign)
    label.set_ellipsize(Pango.EllipsizeMode.END)
    if css_class:
        label.get_style_context().add_class(css_class)
    return label


def make_event_box() -> Gtk.EventBox:
    """Create a standard event box for click handling."""
    event_box = Gtk.EventBox()
    event_box.set_visible_window(False)
    event_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
    return event_box
