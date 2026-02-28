# Loom Application Analysis - 2026-02-28

## Current State Summary

### What's Working
- **Backend Services**: Well-factored service architecture using `ServiceContainer`
  - `WallpaperService`: Color/palette operations, colorization
  - `GtkThemeService`: GTK theme management
  - `WindowThemeService`: Openbox theme management
  - `InterfaceThemeService`: Interface customization
  - `SettingsStore`: Persistent configuration
  - `FetchService`: System information
  
- **Page Structure**: Refactored UI pages moved to `pages/sections/`
  - WallpaperPage, FetchPage, GtkThemesPage, WindowThemesPage
  - IconThemesPage, CursorThemesPage, PanelsPage, MenuPage
  - TerminalsPage, MorePage
  - Each page properly implements `BasePage` and uses `@register_page` decorator

- **Glade UI**: Complete UI definition with 11 page containers (wallpapers, gtk_themes, window_themes, panels, menu, terminals, fetch, icons, cursors, settings, more)

### Current Issues

#### CRITICAL: Missing Page Exports (Prevents Launch)
1. **`BuilderHomePage` (builder_home.py)**: 
   - Exists and is decorated with `@register_page`
   - NOT exported in `pages/sections/__init__.py`
   - Referenced in `MODE_SIDEBAR_ITEMS` but no corresponding page instance created
   - Same issue for builder_layout, builder_widgets, builder_signals, builder_assets, builder_menus

2. **`SettingsPage` (settings.py)**:
   - Exists and is decorated with `@register_page`
   - NOT exported in `pages/sections/__init__.py`
   - Glade file has `page_settings` defined
   - Will fail when app tries to instantiate it

3. **`PresetPages`**: Not yet implemented - referenced in MODE_SIDEBAR_ITEMS but no classes exist
   - presets_home, presets_wallpaper, presets_gtk, presets_window, presets_icons, presets_menus

#### Consequence
When `main.py` calls `_init_page_registry()`:
```python
for page_id in get_all_pages():
    self.pages[page_id] = create_page_instance(page_id, self)
```

The `create_page_instance()` function only looks in `_PAGE_REGISTRY`, which was populated from the `SECTIONS` dict. Missing exports = missing registrations = `None` page instances, which break UI callbacks.

#### Secondary Issues
- `MODE_SIDEBAR_ITEMS` references pages and sidebar rows that don't have corresponding UI pages
- Builder mode and Presets mode functionality not implemented yet
- Page registry discovery could be more robust

## Architecture Overview

### Page Registration Flow
```
pages/sections/*.py (e.g., wallpapers.py)
  ↓ @register_page decorator
  ↓
pages/sections/__init__.py (SECTIONS dict, ALL_PAGES list)
  ↓
pages/__init__.py (get_all_pages() merges SECTIONS into _PAGE_REGISTRY)
  ↓
main.py (_init_page_registry() creates instances via create_page_instance())
  ↓
main.py (do_activate() calls page.build() for each)
```

### Key Dependencies
- GTK 3 + PyGObject
- Glade UI builder (Archcrafter2.glade)
- Backend services (no external dependencies beyond system packages)

## Recommended Fixes (Priority Order)

### 1. IMMEDIATE: Export Missing Pages (Fix Launch)
- Add BuilderHomePage and SettingsPage to `pages/sections/__init__.py`
- Update SECTIONS dict to include all defined pages
- Verify all Glade `page_*` objects have corresponding page classes

### 2. SHORT-TERM: Stub Undefined Pages
- Create minimal preset page classes (PresetWallpaperPage, etc.)
- Implement `get_sidebar_items()` and basic `build()` methods
- Prevents crashes when user tries to access builder/presets modes

### 3. MID-TERM: Clean Up Mode Architecture
- Decide: Keep MODE_SIDEBAR_ITEMS or migrate to page-based sidebar generation
- Either implement builder/presets UI fully, or remove/disable them
- Consolidate sidebar item definitions

### 4. LONG-TERM: Improve Robustness
- Add validation that all sidebar rows have corresponding pages
- Add logging to page discovery process
- Consider type hints for page ID strings (TypedDict or Enum)

## Test Coverage Needed
- [ ] All pages instantiate without errors
- [ ] All Glade objects exist for all pages
- [ ] All sidebar rows map to valid pages
- [ ] Page lifecycle (on_activate, on_deactivate) works
- [ ] Service container initializes correctly
