# Page Modularization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the monolithic main.py (5292 lines) into pluggable page modules under pages/ directory, enabling independent development of each page.

**Architecture:** Each page is a class inheriting from BasePage, auto-discovered and registered. Main.py becomes a thin router. Backend services remain unchanged.

**Tech Stack:** Python 3, GTK3 (gi.repository), existing backend services

---

## Prerequisites

- Create a worktree for this refactoring (see using-git-worktrees skill)
- Ensure tests pass before starting

---

## Phase 1: Infrastructure (Tasks 1-4)

### Task 1: Create pages directory structure

**Files:**
- Create: `pages/__init__.py`
- Create: `pages/base.py`
- Create: `pages/mixer/__init__.py`
- Create: `pages/builder/__init__.py`
- Create: `pages/presets/__init__.py`

**Step 1: Create pages/base.py**

```python
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from gi.repository import Gtk

class BasePage(ABC):
    """Abstract base class for all pages."""
    
    id: str = ""
    title: str = ""
    icon: str = ""
    
    _widget: Optional["Gtk.Widget"] = None
    
    @staticmethod
    def get_sidebar_items():
        """Returns list of sidebar items: [(row_id, title, icon, description), ...]"""
        return []
    
    def build(self, app, builder) -> "Gtk.Widget":
        """Build and return the page widget."""
        raise NotImplementedError
    
    def on_activate(self, app):
        """Called when page becomes visible."""
        pass
    
    def on_deactivate(self, app):
        """Called when page is hidden."""
        pass
    
    @property
    def widget(self) -> Optional["Gtk.Widget"]:
        return self._widget
    
    @widget.setter
    def widget(self, value: "Gtk.Widget"):
        self._widget = value
```

**Step 2: Create pages/__init__.py**

```python
"""Page registry and auto-discovery."""
from pathlib import Path
from typing import Type, TYPE_CHECKING

from pages.base import BasePage

MODES = ["mixer", "builder", "presets"]

_PAGE_CACHE: dict[str, Type["BasePage"]] = {}

def get_all_pages() -> dict[str, Type["BasePage"]]:
    """Auto-discover all page classes."""
    if _PAGE_CACHE:
        return _PAGE_CACHE
    
    for mode in MODES:
        mode_dir = Path(__file__).parent / mode
        if not mode_dir.exists():
            continue
        
        for py_file in mode_dir.glob("*.py"):
            if py_file.stem in ("__init__",) or py_file.stem.startswith("_"):
                continue
            
            module_name = f"pages.{mode}.{py_file.stem}"
            module = __import__(module_name, fromlist=[""])
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) 
                    and issubclass(attr, BasePage) 
                    and attr is not BasePage):
                    _PAGE_CACHE[attr.id] = attr
    
    return _PAGE_CACHE

def get_mode_pages(mode: str) -> list[Type["BasePage"]]:
    """Get all pages for a specific mode."""
    all_pages = get_all_pages()
    return [p for p in all_pages.values() if p.__module__.startswith(f"pages.{mode}")]

def get_sidebar_items_for_mode(mode: str) -> list:
    """Gather all sidebar items for a mode from its pages."""
    items = []
    for page_cls in get_mode_pages(mode):
        items.extend(page_cls.get_sidebar_items())
    return items

def create_page_instance(page_id: str, app) -> Optional[BasePage]:
    """Create an instance of a page by ID."""
    pages = get_all_pages()
    page_cls = pages.get(page_id)
    if page_cls:
        return page_cls()
    return None
```

**Step 3: Create empty mode init files**

```python
# pages/mixer/__init__.py
# pages/builder/__init__.py
# pages/presets/__init__.py
# Empty - auto-discovery handles loading
```

**Step 4: Commit**

```bash
git add pages/
git commit -m "feat: add page module infrastructure"
```

---

### Task 2: Extract WallpaperPage from main.py

**Files:**
- Create: `pages/mixer/wallpapers.py`
- Modify: `main.py`

**Step 1: Create pages/mixer/wallpapers.py**

```python
"""Wallpaper page - migrated from main.py."""
from pages.base import BasePage

class WallpaperPage(BasePage):
    id = "wallpapers"
    title = "Wallpapers"
    icon = "image-x-generic-symbolic"
    
    @staticmethod
    def get_sidebar_items():
        return [
            ("wallpapers", "Wallpapers", "image-x-generic-symbolic", "Manage wallpapers"),
            ("gtk_themes", "GTK Themes", "preferences-desktop-theme-symbolic", "GTK theme selection"),
            ("window_themes", "Window Themes", "window-new-symbolic", "Openbox themes"),
            ("icons", "Icons", "preferences-desktop-icons-symbolic", "Icon theme selection"),
            ("cursors", "Cursors", "input-mouse-symbolic", "Cursor theme selection"),
            ("panels", "Panels", "transform-scale-symbolic", "Polybar/Tint2 panels"),
            ("menu", "Menu", "ac-jgmenu-symbolic", "jgmenu configuration"),
            ("terminals", "Terminals", "utilities-terminal-symbolic", "Terminal presets"),
            ("fetch", "Fetch", "system-information-symbolic", "System fetch tools"),
            ("more", "More", "view-more-symbolic", "Additional tools"),
        ]
    
    def build(self, app, builder):
        # Get existing widget from Glade
        widget = builder.get_object("page_wallpapers")
        self.widget = widget
        return widget
    
    def on_activate(self, app):
        # Called when page becomes visible
        app.reload_wallpapers()
        app.sync_wallpaper_controls_from_settings()
```

**Step 2: Verify import works**

```bash
cd /home/lamb/.config/loom
python3 -c "from pages import get_all_pages; print(get_all_pages())"
```

Expected: `{'wallpapers': <class 'pages.mixer.wallpapers.WallpaperPage'>}`

**Step 3: Test app still runs**

```bash
python3 main.py --help  # or just launch and verify
```

**Step 4: Commit**

```bash
git add pages/mixer/wallpapers.py
git commit -m "feat: extract WallpaperPage from main.py"
```

---

### Task 3: Integrate page registry into main.py

**Files:**
- Modify: `main.py:404-600`

**Step 1: Add page registry to __init__**

In `main.py`, add after service initialization:

```python
# Page registry
from pages import get_all_pages, create_page_instance

self.pages = {}  # page_id -> instance

def _init_page_registry(self):
    """Initialize page registry."""
    for page_id in get_all_pages():
        self.pages[page_id] = create_page_instance(page_id, self)

self._init_page_registry()
```

**Step 2: Test pages accessible**

```bash
python3 -c "from main import ArchCrafter2App; print('OK')"
```

**Step 3: Commit**

```bash
git commit -m "feat: integrate page registry into main app"
```

---

### Task 4: Verify Phase 1 works

**Step 1: Run app in mixer mode**

```bash
python3 main.py
```

Navigate to Wallpapers page - should work as before.

**Step 2: Check for any errors**

Look for import errors or missing attributes.

---

## Phase 2: Migrate All Mixer Pages (Tasks 5-14)

### Task 5: Migrate GTK Themes Page

**Files:**
- Create: `pages/mixer/gtk_themes.py`
- Copy methods from main.py:
  - `init_gtk_themes_page()` (line 3583)
  - `reload_gtk_themes()` (line 3937)
  - All `_gtk_*` helper methods

**Step 1: Create pages/mixer/gtk_themes.py**

```python
"""GTK Themes page - migrated from main.py."""
from pages.base import BasePage

class GtkThemesPage(BasePage):
    id = "gtk_themes"
    title = "GTK Themes"
    icon = "preferences-desktop-theme-symbolic"
    
    # Methods migrated from main.py
    def build(self, app, builder):
        # Get widget and setup
        self.widget = builder.get_object("page_gtk_themes")
        return self.widget
    
    def on_activate(self, app):
        app.reload_gtk_themes()
```

**Step 2: Copy all related methods**

Extract each method from main.py to the page class.

**Step 3: Test**

Run app, navigate to GTK Themes.

**Step 4: Commit**

---

### Task 6: Migrate Window Themes Page

**Files:**
- Create: `pages/mixer/window_themes.py`
- Migrate from main.py:
  - `init_window_themes_page()` (line 4163)
  - `reload_window_themes()` (line 4189)

---

### Task 7: Migrate Icon Themes Page

**Files:**
- Create: `pages/mixer/icon_themes.py`
- Migrate from main.py:
  - `init_icon_themes_page()` (line 4278)
  - `reload_icon_themes()` (line 4291)

---

### Task 8: Migrate Cursor Themes Page

**Files:**
- Create: `pages/mixer/cursor_themes.py`
- Migrate from main.py:
  - `init_cursor_themes_page()` (line 4470)
  - `reload_cursor_themes()` (line 4482)

---

### Task 9: Migrate Panels Page

**Files:**
- Create: `pages/mixer/panels.py`
- Migrate from main.py:
  - `init_bar_page()` (line 2843)

---

### Task 10: Migrate Menu Page

**Files:**
- Create: `pages/mixer/menu.py`
- Migrate from main.py:
  - `init_menu_page()` (line 3520)
  - `reload_menu_presets()` (line 3397)

---

### Task 11: Migrate Terminals Page

**Files:**
- Create: `pages/mixer/terminals.py`
- Find and migrate related methods

---

### Task 12: Migrate Fetch Page

**Files:**
- Create: `pages/mixer/fetch.py`
- Find and migrate related methods

---

### Task 13: Migrate More Page

**Files:**
- Create: `pages/mixer/more.py`
- Find and migrate related methods

---

### Task 14: Verify all mixer pages work

**Step 1: Navigate each mixer page**

Test each page loads correctly.

---

## Phase 3: Migrate Builder Pages (Tasks 15-21)

### Task 15: Migrate Builder Home

**Files:**
- Create: `pages/builder/home.py`

---

### Task 16: Migrate Builder Layout

**Files:**
- Create: `pages/builder/layout.py`

---

### Task 17: Migrate Builder Widgets

**Files:**
- Create: `pages/builder/widgets.py`

---

### Task 18: Migrate Builder Signals

**Files:**
- Create: `pages/builder/signals.py`

---

### Task 19: Migrate Builder Assets

**Files:**
- Create: `pages/builder/assets.py`

---

### Task 20: Migrate Builder Menus

**Files:**
- Create: `pages/builder/menus.py`

---

### Task 21: Verify builder mode

**Step 1: Test builder mode navigation**

---

## Phase 4: Migrate Presets Pages (Tasks 22-28)

### Task 22: Migrate Presets Home

**Files:**
- Create: `pages/presets/home.py`

---

### Task 23-28: Migrate remaining preset pages

- Presets Wallpapers, GTK, Window, Icons, Menus

---

## Phase 5: Cleanup (Tasks 29-32)

### Task 29: Remove migrated methods from main.py

Delete methods that have been moved to page classes.

### Task 30: Reduce main.py size

Target: ~400 lines

### Task 31: Final testing

- Test all modes
- Test all pages

### Task 32: Commit final state

```bash
git add -A
git commit -m "refactor: complete page modularization"
```

---

## Verification Commands

```bash
# Test page discovery
python3 -c "from pages import get_all_pages; print(list(get_all_pages().keys()))"

# Test app launches
python3 main.py &

# Test each mode
# Navigate: mixer > builder > presets
```

---

## Plan Complete

Two execution options:

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
