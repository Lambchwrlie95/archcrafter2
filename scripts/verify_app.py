#!/usr/bin/env python3
"""
Verify the Loom app: imports, Glade IDs, backend, page registry.
Run from repo root: python3 scripts/verify_app.py
No display required for structure checks.
"""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def check_imports():
    print("1. Imports...")
    from main import ArchCrafter2App
    from pages import get_all_pages, get_row_to_page_map
    from backend import (
        WallpaperService,
        SettingsStore,
        GtkThemeService,
        WindowThemeService,
    )
    print("   main, pages, backend OK")
    return True


def check_pages():
    print("2. Page registry...")
    from pages import get_all_pages, get_row_to_page_map
    pages = get_all_pages()
    m = get_row_to_page_map()
    assert len(pages) >= 10, "Expected at least 10 pages"
    assert "wallpapers" in pages, "Missing wallpapers page"
    assert "row_wallpapers" in m, "Missing row_wallpapers mapping"
    assert "row_menu" in m, "Missing row_menu mapping"
    print(f"   Pages: {list(pages.keys())}")
    print(f"   Row->page entries: {len(m)}")
    return True


def check_glade():
    print("3. Glade file...")
    glade_path = REPO_ROOT / "Archcrafter2.glade"
    if not glade_path.exists():
        print("   FAIL: Archcrafter2.glade not found")
        return False
    tree = ET.parse(glade_path)
    root = tree.getroot()
    ids = {e.get("id") for e in root.iter() if e.get("id")}
    required = [
        "sidebar_box", "sidebar_list", "content_stack", "root_hbox", "top_mode_bar",
        "content_box", "page_wallpapers", "page_settings", "button_top_settings",
        "global_actions_bar", "page_gtk_themes", "page_window_themes",
        "wallpaper_flowbox", "flowbox_gtk_themes", "flowbox_window_themes",
        "row_menu",
    ]
    missing = [r for r in required if r not in ids]
    if missing:
        print(f"   FAIL: Missing IDs: {missing}")
        return False
    print(f"   Required IDs present ({len(ids)} objects in Glade)")
    return True


def check_backend():
    print("4. Backend services...")
    from backend import WallpaperService, SettingsStore, GtkThemeService, WindowThemeService
    settings = SettingsStore(REPO_ROOT / "settings.json")
    WallpaperService(REPO_ROOT, settings)
    GtkThemeService(REPO_ROOT, settings)
    WindowThemeService(REPO_ROOT, settings)
    print("   All services instantiate OK")
    return True


def check_css():
    print("5. Assets...")
    css = REPO_ROOT / "assets" / "app.css"
    if not css.exists():
        print("   WARN: assets/app.css not found")
    else:
        print("   assets/app.css present")
    return True


def main():
    print("Loom app verification (no display)\n")
    steps = [check_imports, check_pages, check_glade, check_backend, check_css]
    failed = []
    for step in steps:
        try:
            step()
        except Exception as e:
            print(f"   FAIL: {e}")
            failed.append(step.__name__)
    print()
    if failed:
        print("Verification FAILED:", failed)
        return 1
    print("Verification PASSED. Run 'python3 main.py' with a display for full UI test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
