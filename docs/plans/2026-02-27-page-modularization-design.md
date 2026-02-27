# Page Modularization Design

**Date:** 2026-02-27  
**Status:** Approved  
**Goal:** Split monolithic `main.py` into pluggable page modules

---

## 1. Overview

Transform the monolithic `ArchCrafter2App` class (5292 lines) into a modular architecture where each page is an independent module. Pages are auto-discovered and registered, making the app extensible without modifying core routing code.

---

## 2. Architecture

### 2.1 Directory Structure

```
/
├── main.py                      # App shell, router, mode switching (~400 lines)
├── backend/                    # Keep as-is (already modular)
├── pages/
│   ├── __init__.py              # Page registry, auto-discovery
│   ├── base.py                  # BasePage abstract class
│   ├── mixer/                   # Theme mixer mode
│   │   ├── wallpapers.py
│   │   ├── gtk_themes.py
│   │   ├── window_themes.py
│   │   ├── icon_themes.py
│   │   ├── cursor_themes.py
│   │   ├── panels.py            # polybar/tint2
│   │   ├── menu.py              # jgmenu
│   │   ├── terminals.py
│   │   ├── fetch.py
│   │   └── more.py
│   ├── builder/                 # Builder mode
│   │   ├── home.py
│   │   ├── layout.py
│   │   ├── widgets.py
│   │   ├── signals.py
│   │   ├── assets.py
│   │   └── menus.py
│   └── presets/                 # Presets mode
│       ├── home.py
│       ├── wallpapers.py
│       ├── gtk.py
│       ├── window.py
│       ├── icons.py
│       └── menus.py
└── ui_common/                   # Shared widgets (future)
```

### 2.2 Mode Structure

| Mode | Default Page | Description |
|------|--------------|-------------|
| `mixer` | `wallpapers` | Theme customization (wallpapers, GTK, icons, etc.) |
| `builder` | `home` | GLade project builder |
| `presets` | `home` | Preset pack management |

---

## 3. Page Interface

### 3.1 Base Class

```python
# pages/base.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import ArchCrafter2App

class BasePage(ABC):
    """Abstract base class for all pages."""
    
    # Page identification
    id: str                      # Unique page ID (e.g., "wallpapers")
    title: str                   # Display title
    icon: str                    # GTK icon name
    
    @staticmethod
    def get_sidebar_items():
        """
        Returns list of sidebar items for this page's mode.
        Format: [(row_id, title, icon, description), ...]
        """
        return []
    
    def build(self, app: "ArchCrafter2App", builder: Gtk.Builder) -> Gtk.Widget:
        """Build and return the page widget."""
        pass
    
    def on_activate(self, app: "ArchCrafter2App"):
        """Called when page becomes visible."""
        pass
    
    def on_deactivate(self, app: "ArchCrafter2App"):
        """Called when page is hidden."""
        pass
```

### 3.3 Mode-Specific Page

```python
# pages/mixer/wallpapers.py
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
        # Migrated from main.py: init_wallpaper_page()
        widget = builder.get_object("page_wallpapers")
        self._setup_ui(app, builder)
        return widget
    
    def on_activate(self, app):
        # Migrated from main.py sidebar handler
        app.reload_wallpapers()
```

---

## 4. Page Registry (Auto-Discovery)

```python
# pages/__init__.py
from pathlib import Path
from typing import Type

MODES = ["mixer", "builder", "presets"]

def get_all_pages() -> dict[str, Type["BasePage"]]:
    """Auto-discover all page classes from pages/ subdirectories."""
    pages = {}
    
    for mode in MODES:
        mode_dir = Path(__file__).parent / mode
        if not mode_dir.exists():
            continue
            
        for py_file in mode_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
                
            module_name = f"pages.{mode}.{py_file.stem}"
            module = __import__(module_name, fromlist=[""])
            
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) 
                    and issubclass(attr, BasePage) 
                    and attr is not BasePage):
                    pages[attr.id] = attr
    
    return pages

def get_mode_pages(mode: str) -> list[Type["BasePage"]]:
    """Get all pages belonging to a specific mode."""
    all_pages = get_all_pages()
    return [p for p in all_pages.values() if p.__module__.startswith(f"pages.{mode}")]
```

---

## 5. Main App Integration

### 5.1 Router Responsibilities

`main.py` becomes a thin shell:

```python
# main.py (simplified)
class ArchCrafter2App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.loom.app")
        
        # Services (keep existing)
        self.settings = SettingsStore(...)
        self.wallpaper_service = WallpaperService(...)
        # ... other services
        
        # Page registry
        from pages import get_all_pages
        self.pages = {}  # page_id -> instance
        self._init_page_registry()
        
        # UI shell
        self.window = None
        self.sidebar_list = None
        self.content_stack = None
    
    def _init_page_registry(self):
        """Instantiate all pages and register."""
        page_classes = get_all_pages()
        for page_id, page_cls in page_classes.items():
            self.pages[page_id] = page_cls()
    
    def get_mode_sidebar_items(self, mode: str) -> list:
        """Gather sidebar items from all pages in a mode."""
        items = []
        for page in self.pages.values():
            if page.__module__.startswith(f"pages.{mode}"):
                items.extend(page.get_sidebar_items())
        return items
    
    def on_sidebar_row_selected(self, listbox, row):
        """Route to appropriate page."""
        row_id = Gtk.Buildable.get_name(row)
        page_id = ROW_TO_PAGE.get(row_id)
        
        if page_id and page_id in self.pages:
            page = self.pages[page_id]
            self.content_stack.set_visible_child_name(page_id)
            page.on_activate(self)
```

### 5.2 Shared Services

Pages receive services via `__init__` or property access:

```python
class WallpaperPage(BasePage):
    def on_activate(self, app):
        # Access shared services
        app.wallpaper_service.reload()
        app.settings.get("wallpaper", {})
```

---

## 6. Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ App Shell    │  │ Page Registry│  │ Service      │ │
│  │ (Gtk.App)    │  │ (auto-disc.) │  │ Container    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
          │                  │                    │
          ▼                  ▼                    ▼
    ┌──────────┐     ┌──────────┐         ┌──────────┐
    │ Sidebar  │     │ Page     │         │ Backend  │
    │ (mode    │────▶│ Instance │────────▶│ Services │
    │ routing) │     │          │         │          │
    └──────────┘     └──────────┘         └──────────┘
```

---

## 7. Migration Strategy

### Phase 1: Create Base Infrastructure
1. Create `pages/base.py` with `BasePage` class
2. Create `pages/__init__.py` with registry
3. Create `pages/mixer/wallpapers.py` (extract from main.py)
4. Update main.py to use page registry for mixer mode

### Phase 2: Migrate One Page at a Time
1. Migrate each page module in any order
2. Each migration: copy methods from main.py → page class
3. Verify page still works before moving on

### Phase 3: Clean Up
1. Remove migrated methods from main.py
2. Move page files to proper directories
3. Add ui_common/ for shared widgets if needed

---

## 8. Extension Examples

### Adding a New Page
```python
# pages/mixer/conky.py (new file)
from pages.base import BasePage

class ConkyPage(BasePage):
    id = "conky"
    title = "Conky"
    icon = "utilities-system-monitor-symbolic"
    
    @staticmethod
    def get_sidebar_items():
        return [("conky", "Conky", "utilities-system-monitor-symbolic", "Conky widgets")]
    
    def build(self, app, builder):
        # Build page
        pass
```
→ Auto-appears in mixer sidebar on next launch

### Adding a New Mode
```python
# In pages/__init__.py, add to MODES:
MODES = ["mixer", "builder", "presets", "newmode"]

# Create pages/newmode/ directory with pages
```

---

## 9. Success Criteria

- [ ] main.py reduced to ~400 lines
- [ ] Each page in separate file under pages/
- [ ] Adding new page requires only creating new file
- [ ] All existing functionality preserved
- [ ] No breaking changes to backend services
- [ ] Tests pass for migrated pages

---

## 10. Open Questions

| Question | Decision Needed |
|----------|-----------------|
| Shared widgets | Extract to ui_common/ now or later? |
| Page state | Keep in app or page instance? |
| Glade handling | Pages access builder directly or receive widgets? |
| Import order | Avoid circular imports between main/pages? |
