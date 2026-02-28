# Backend Workflow Refactoring

## Summary

This document outlines the progressive refactoring of `ArchCrafter2App` to extract backend logic into service classes. The goal is to make the application code cleaner, testable, and maintainable.

## Phase 1: Wallpaper Logic Extraction (Completed)

### What Moved

Core wallpaper color/palette operations have been relocated from `main.py` into `backend/wallpapers.py`:

**Palette Management:**
- `_load_palette_cache_from_disk()` → `WallpaperService.load_palette_cache_from_disk()`
- `_save_palette_cache_to_disk()` → `WallpaperService.save_palette_cache_to_disk()`
- `_palette_cache_key()` → `WallpaperService._palette_cache_key()`
- `_extract_palette()` → `WallpaperService.extract_palette()`
- Associated cache state: `_palette_cache`, `_palette_disk_cache`, `_palette_cache_lock`

**Color Utilities:**
- `_hex_to_rgb()` → `WallpaperService._hex_to_rgb()`
- `_rgb_to_hex()` → `WallpaperService._rgb_to_hex()`
- `mix_hex()` → `WallpaperService.mix_hex()`
- `_is_light_hex()` → `WallpaperService._is_light_hex()`
- `_color_distance()` → `WallpaperService._color_distance()`

**Color Generation:**
- `_build_similar_colors()` → `WallpaperService.get_similar_colors()`
- `_build_color_theory_colors()` → `WallpaperService.get_color_theory_colors()`
- `_get_recent_colorize_swatches()` → `WallpaperService.get_recent_colorize_swatches()`
- `_record_colorize_swatch()` → `WallpaperService.record_colorize_swatch()`
- `_random_color()` → `WallpaperService._random_color()`

**Colorization:**
- `_get_colorize_strength()` → `WallpaperService.get_colorize_strength()`
- `_set_colorize_strength()` → `WallpaperService.set_colorize_strength()`
- `_create_colorized_variant()` → `WallpaperService.create_colorized_variant()`

**Display Logic:**
- `_is_colorized_path()` → `WallpaperService.is_colorized_path()`
- `_compose_wallpaper_display_name()` → `WallpaperService.compose_display_name()`

### What Changed in `main.py`

The application class keeps thin wrapper methods that delegate to the service:

```python
def _extract_palette(self, path: Path, count: int = 5):
    return self.wallpaper_service.extract_palette(path, count)

def _build_similar_colors(self, base_colors):
    return self.wallpaper_service.get_similar_colors(base_colors)
```

This preserves the existing calling interface while moving implementation to a testable service.

### State Cleanup

Removed from `ArchCrafter2App.__init__()`:
- `self.palette_cache_file`
- `self.cache_dir` (still needed for other uses, now only managed by service)
- `self.thumb_cache_dir` (now only managed by service)
- `self._palette_cache`, `_palette_disk_cache`, `_palette_cache_lock`
- `self.variant_dir` (use `wallpaper_service.variant_dir`)

### Backwards Compatibility

All application code continues to work unchanged. UI handlers call methods on the app object (`self.on_colorize...()`) which delegate through thin wrappers to the service.

## Testing

New tests added in `tests/backend/test_wallpaper_service.py` cover:
- Service construction via `ServiceContainer`
- Default palette management
- Color utilities (hex ↔ rgb conversion, color distance)
- Colorization helpers (strength, variant creation)
- Display name composition

Run tests via: `pytest tests/backend/ -v`

##  Future Phases

### Phase 2: Theme Logic Extraction (Completed)

### What Moved

**GTK Theme Preview Rendering:**
- `_gtk_theme_signature()` → `GtkThemeService._theme_signature()`
- `_gtk_preview_cache_path()` → `GtkThemeService.preview_cache_path()`
- `_render_gtk_preview_to_cache()` → `GtkThemeService.render_preview_to_cache()`
- Associated cache logic and slug sanitization

**Wallpaper Badge CSS:**
- `_get_colorized_badge_css()` → `WallpaperService.get_colorized_badge_css()`
- Color luminance calculation and badge styling

### Implementation Pattern

Similar to Phase 1, main.py keeps thin delegating wrappers:
```python
def _gtk_theme_signature(self, theme) -> str:
    return self.gtk_theme_service._theme_signature(theme)
```

This preserves the existing calling interface while moving implementation to a testable service.

### Tests Added

New tests in:
- [test_gtk_theme_service.py](tests/backend/test_gtk_theme_service.py) – signature generation, cache paths, slug sanitization
- [test_wallpaper_service.py](tests/backend/test_wallpaper_service.py) – badge CSS generation with color contrast checks


### Phase 3: Icon/Cursor Theme Services
Create backend services for icon and cursor theme listing and application (currently handled by GTK/XDG directly in main.py).

### Phase 4: Fetch Service Enhancements
Move fetch-related state and helpers to centralize preset discovery and rendering.

### Phase 5: Settings UI Controller
Create a dedicated settings controller that doesn't live inside the main app class.

### Phase 6: Menu/Panel Logic
Extract bar (polybar/tint2) preview rendering and apply logic into dedicated service layer.

## Design Principles

1. **Services own their data** – each service manages its own state and caching.
2. **Thin wrapper methods preserve compatibility** – old code paths still work.
3. **Testable in isolation** – services can be instantiated without GTK or the full app.
4. **Centralized container** – `ServiceContainer` builds and wires all services on startup.

## Notes

- Color math is CPU-bound and domain-specific; it made sense to keep it in the wallpaper service.
- Palette caching is tightly coupled to image analysis; appropriate to live alongside that logic.
- UI handlers still live in `main.py`; the dividing line is between "business logic" (service) and "presentation" (handler).
- No database or RPC; services are in-process and tightly coupled for simplicity.
