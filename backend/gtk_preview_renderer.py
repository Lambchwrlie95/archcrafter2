#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render GTK theme preview to PNG")
    parser.add_argument("--theme", required=True, help="GTK theme name")
    parser.add_argument("--output", required=True, help="PNG output path")
    parser.add_argument("--width", type=int, default=900, help="Preview width")
    parser.add_argument("--height", type=int, default=560, help="Preview height")
    return parser.parse_args()


def build_preview_widget(Gtk):
    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    root.set_border_width(10)

    menubar = Gtk.MenuBar()
    for label in ("File", "Edit", "View", "Help"):
        menubar.append(Gtk.MenuItem(label=label))
    root.pack_start(menubar, False, False, 0)

    toolbar = Gtk.Toolbar()
    toolbar.set_icon_size(Gtk.IconSize.SMALL_TOOLBAR)
    toolbar.set_style(Gtk.ToolbarStyle.ICONS)
    for icon_name in ("go-previous-symbolic", "go-next-symbolic", "view-refresh-symbolic"):
        item = Gtk.ToolButton()
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.SMALL_TOOLBAR)
        item.set_icon_widget(icon)
        icon.show()
        toolbar.insert(item, -1)

    entry_item = Gtk.ToolItem()
    entry_item.set_expand(True)
    entry = Gtk.Entry()
    entry.set_text("Search demo content")
    entry_item.add(entry)
    toolbar.insert(entry_item, -1)
    root.pack_start(toolbar, False, False, 0)

    notebook = Gtk.Notebook()

    controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    controls.set_border_width(10)
    top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    top_row.pack_start(Gtk.CheckButton(label="Enable shadows"), False, False, 0)
    top_row.pack_start(Gtk.RadioButton(label="Compact mode"), False, False, 0)
    controls.pack_start(top_row, False, False, 0)

    row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    row2.pack_start(Gtk.Entry(text="Primary input"), True, True, 0)
    combo = Gtk.ComboBoxText()
    combo.append_text("Default")
    combo.append_text("Alternate")
    combo.set_active(0)
    row2.pack_start(combo, False, False, 0)
    controls.pack_start(row2, False, False, 0)

    progress = Gtk.ProgressBar()
    progress.set_fraction(0.63)
    progress.set_text("Sync progress")
    progress.set_show_text(True)
    controls.pack_start(progress, False, False, 0)

    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
    scale.set_value(42)
    controls.pack_start(scale, False, False, 0)

    actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    actions.set_halign(Gtk.Align.END)
    actions.pack_start(Gtk.Button(label="Cancel"), False, False, 0)
    actions.pack_start(Gtk.Button(label="Apply"), False, False, 0)
    controls.pack_start(actions, False, False, 0)

    notebook.append_page(controls, Gtk.Label(label="Controls"))

    list_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    list_page.set_border_width(10)
    store = Gtk.ListStore(str, str)
    store.append(["Window border", "Enabled"])
    store.append(["Button radius", "6px"])
    store.append(["Selection style", "Accent fill"])
    store.append(["Scrollbar width", "Auto"])
    tree = Gtk.TreeView(model=store)
    tree.set_headers_visible(True)
    tree.append_column(Gtk.TreeViewColumn("Setting", Gtk.CellRendererText(), text=0))
    tree.append_column(Gtk.TreeViewColumn("Value", Gtk.CellRendererText(), text=1))
    tree.get_selection().select_path(1)
    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroller.set_min_content_height(150)
    scroller.add(tree)
    list_page.pack_start(scroller, True, True, 0)
    notebook.append_page(list_page, Gtk.Label(label="List"))

    root.pack_start(notebook, True, True, 0)
    return root


def main() -> int:
    args = parse_args()
    out_path = Path(args.output).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    os.environ["GTK_THEME"] = str(args.theme)

    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    window = Gtk.OffscreenWindow()
    window.set_default_size(max(220, int(args.width)), max(180, int(args.height)))
    window.set_size_request(max(220, int(args.width)), max(180, int(args.height)))
    window.add(build_preview_widget(Gtk))
    window.show_all()

    state = {"attempt": 0, "saved": False}

    def capture() -> bool:
        state["attempt"] += 1
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        pixbuf = window.get_pixbuf()
        if pixbuf is None:
            if state["attempt"] < 25:
                return True
            Gtk.main_quit()
            return False
        try:
            pixbuf.savev(str(out_path), "png", ["compression"], ["3"])
            state["saved"] = True
        except Exception:
            state["saved"] = False
        Gtk.main_quit()
        return False

    GLib.timeout_add(70, capture)
    Gtk.main()
    return 0 if state["saved"] and out_path.exists() else 2


if __name__ == "__main__":
    raise SystemExit(main())
