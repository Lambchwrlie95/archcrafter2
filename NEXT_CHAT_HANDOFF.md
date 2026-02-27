# ArchCrafter2 - Full Handoff + Workflow Notes

Updated: 2026-02-27
Project root: `/home/lamb/.config/loom`

## 1) Project Intent
ArchCrafter2 is the GTK3 + Glade recreation of an older GTK4 ArchCrafter UI.
Main goals right now:
- Keep the UI Glade-driven and GTK3-safe.
- Preserve completed Wallpaper workflow (highest priority stability).
- Incrementally build other tabs (GTK Themes, Window Themes, etc.) without regressions.

## 2) Non-Negotiable Rules
- GTK3 only. No GTK4 APIs/properties.
- Glade-first: keep structure in `Archcrafter2.glade`; Python should wire behavior, not replace layout.
- Use existing widget IDs; do not invent random runtime IDs and forget Glade alignment.
- Keep CSS compatible with GTK3.
- Safe, narrow patches only. Avoid broad refactors unless explicitly requested.
- If removing a Glade widget/page/row, remove matching Python references (mapping/signals).

## 3) Current Sidebar + Pages (Authoritative)
Current sidebar rows:
- `row_wallpapers`
- `row_gtk_themes`
- `row_window_themes`
- `row_panels` (label displayed as `Bar`)
- `row_jgmenu` (label displayed as `Menu`)
- `row_terminals`
- `row_fetch`
- `row_icons`
- `row_cursors`
- `row_more`
- `row_settings`

Current stack pages:
- `page_wallpapers`
- `page_gtk_themes`
- `page_window_themes`
- `page_panels`
- `page_menu`
- `page_terminals`
- `page_fetch`
- `page_icons`
- `page_cursors`
- `page_more`
- `page_settings`

Removed intentionally:
- `Rofi` row/page
- `Openbox Config` row/page

## 4) Current Top Mode Behavior
Top mode bar buttons:
- mixer
- builder
- presets

Important:
- Bottom `Settings` top-mode button was fully removed from Glade and Python references.
- Settings is accessed via sidebar `row_settings` and top-right settings button in wallpaper header.

Mode logic:
- `mixer` uses the normal app sidebar + real content stack.
- `builder` and `presets` each have their own independent sidebars and selection states.
- `builder/presets` currently show placeholder workspace content (not full feature pages yet).

## 5) Current Icon Decisions
All are symbolic icon names.

Sidebar icons now:
- Wallpapers: `ac-wallpapers-symbolic` (22)
- GTK Themes: `ac-gtk-themes-symbolic` (22)
- Window Themes: `ac-window-themes-symbolic` (22)
- Bar: `multimedia-volume-control-symbolic` (26)
- Menu: `ac-jgmenu-symbolic` (22)
- Terminals: `ac-terminal-symbolic` (22)
- Fetch: `document-print-symbolic` (26)
- Icons: `face-monkey-symbolic` (22)
- Cursors: `ac-cursors-symbolic` (22)
- Settings: `ac-settings-symbolic` (22)
- More: `ac-hub-symbolic` (22)

Top-right settings icon:
- `icon_top_settings`: `ac-settings-symbolic` (18)

Why Bar/Fetch are 26:
- Their glyphs have more internal padding and looked visually smaller at 22/24.

## 6) Main File Architecture
Main entry:
- `main.py`
- App ID: `org.archcrafter2.app`

Core constants in `main.py`:
- `PRIMARY_GLADE`
- `ROW_TO_PAGE`
- `MODE_SIDEBAR_ITEMS`
- wallpaper fill/sort constants

Critical sections:
- Top mode and sidebar swap logic: mode sidebars, paned resize persistence, top mode apply.
- Wallpaper feature block:
  - thumbnail generation
  - palette extraction
  - colorize pipeline
  - inline actions (preview/colorize/apply/delete)
  - rename/edit display names
- GTK Themes tab:
  - search/filter/type badge/color chips
  - preview mockup panel
  - apply + preview css path loading
- Window Themes tab:
  - list + apply Openbox window themes

Activate flow order:
1. Load Glade
2. Set app window
3. Register custom icon search paths
4. Connect sidebar row-selection
5. Load CSS provider
6. `init_top_mode_bar()`
7. `init_wallpaper_page()`
8. `init_window_themes_page()`
9. `init_gtk_themes_page()`

## 7) Backend Modules
`backend/settings.py`
- JSON settings store (section-based dicts).

`backend/wallpapers.py`
- Source dirs, custom dirs, sorting, view mode, thumb size persistence.
- Applies wallpaper via `nitrogen`.
- Ensures colorized folder is always part of custom dirs.
- Imports legacy variants from `cache/wallpaper_variants` into `library/wallpapers/colorized`.

`backend/wallpaper_names.py`
- Persistent rename overrides (`name_overrides`) keyed by resolved absolute path.

`backend/gtk_themes.py`
- Scans GTK themes with `gtk-3.0/gtk.css`.
- Extracts metadata:
  - colors (`bg`, `fg`, `accent`)
  - type (`light/dark`) using name heuristic + luminance fallback.
- Reads/applies current GTK theme using `gsettings`.

`backend/themes.py`
- Scans Openbox window themes (`openbox-3` folder required).
- Reads/writes current theme in `~/.config/openbox/rc.xml`.
- Applies with `openbox --reconfigure`.

## 8) External Runtime Dependencies
Used by code:
- `nitrogen` for wallpaper apply.
- ImageMagick (`magick` or `convert`) for colorize.
- `gsettings` for GTK theme get/set.
- `openbox --reconfigure` for window theme apply.

If these are missing, app reports errors in status/message flows.

## 9) Current Settings Schema (from settings.json)
Top-level sections:
- `wallpapers`
- `ui`

Important `wallpapers` keys:
- `source`: custom/system
- `fill_mode`
- `view_mode`
- `custom_dirs`
- `last_applied`
- `sort_mode`
- `thumb_size`
- `colorize_recent`
- `colorize_strength`
- `colorized_tag_color`
- `colorized_badge_color`
- `name_overrides`

Important `ui` keys:
- `sidebar_width`
- `top_mode`

## 10) What Is Already Accomplished
- GTK3 + Glade baseline is functional.
- Wallpaper section is significantly developed and user-tuned:
  - grid/list behavior
  - palette swatches and copy-on-click
  - colorize popover/dialog workflows
  - colorized variants + tags
  - rename/edit names
  - deletion and apply flow
- GTK Themes tab implemented with metadata and preview support.
- Window Themes tab implemented with Openbox apply.
- Sidebar + icon set heavily curated to current style.
- Top-mode builder/presets sidebars separated from mixer sidebar.

## 11) Known Sensitive Areas (Avoid Regressions)
- Wallpaper card rendering and interaction code in `main.py` is dense and easy to break.
- Glade hierarchy must remain valid; malformed tree can leak labels/widgets into wrong containers.
- If editing row/page structure, update `ROW_TO_PAGE` immediately.
- Avoid introducing hidden duplicate controls; remove dead widgets cleanly.

## 12) Safe Workflow for Next Chat
1. Clarify exact requested UI/behavior change.
2. Locate related Glade IDs and mapping in `main.py`.
3. Patch minimal scope.
4. Validate:
   - `xmllint --noout Archcrafter2.glade`
   - `python3 -m py_compile main.py`
5. Launch and verify visually.
6. Report only what changed.

## 13) Launch / Troubleshooting Commands
Run app foreground:
- `cd /home/lamb/.config/loom && python3 main.py`

Run app background:
- `nohup python3 /home/lamb/.config/loom/main.py >/tmp/loom.log 2>&1 &`

Stop app:
- `pkill -f "/home/lamb/.config/loom/main.py"`

Check running:
- `pgrep -af "python3 /home/lamb/.config/loom/main.py|python3 main.py"`

If window exists but not focused:
- `xdotool search --name ArchCrafter2`
- `xdotool windowactivate <WIN_ID>`

## 14) Current Git Working Tree Note
Repo is intentionally dirty and includes runtime state edits.
Do NOT reset broadly.
Notable changed/untracked items currently include:
- `Archcrafter2.glade`
- `main.py`
- `backend/gtk_themes.py`
- `backend/wallpapers.py`
- `settings.json`
- `NEXT_CHAT_HANDOFF.md`
- pycache files and some deleted colorized images

If making commits later, prefer excluding `__pycache__` and avoid deleting user wallpaper assets unless requested.

## 15) Backlog / Suggested Next Safe Steps
- Build real content for `Bar`, `Menu`, `Terminals`, `Fetch`, `Icons`, `Cursors`, `Settings`, `More` pages.
- Keep each section modular (separate init/reload handlers like wallpaper/themes).
- Move inline CSS string into external CSS file when user asks (currently functional but less ideal).
- Add small integration checks per tab before adding major UI complexity.

## 16) Quick Rule Reminder for Any New Chat
- GTK3 + Glade only.
- Minimal, reversible patches.
- Validate every change.
- Preserve Wallpaper behavior first.
- Keep icon style and spacing consistent.

## 17) Page Modularization Architecture (2026-02-27)

### Overview
The app now has a pluggable page architecture. Pages are auto-discovered from the `pages/` directory.

### Directory Structure
```
pages/
├── __init__.py      # Auto-discovery registry, get_all_pages(), get_row_to_page_map()
├── base.py          # BasePage abstract class
├── mixer/          # Theme mixer pages
│   ├── wallpapers.py
│   ├── gtk_themes.py
│   ├── window_themes.py
│   ├── icon_themes.py
│   ├── cursor_themes.py
│   ├── panels.py
│   ├── menu.py
│   ├── terminals.py
│   ├── fetch.py
│   └── more.py
└── builder/
    └── home.py

ui_common/
└── __init__.py     # Shared widget helpers
```

### How It Works
1. `pages/__init__.py` auto-discovers all `BasePage` subclasses
2. `ROW_TO_PAGE` is now auto-generated from page sidebar items
3. Each page class provides:
   - `id`: unique page identifier
   - `get_sidebar_items()`: list of sidebar entries for that mode
   - `build(app, builder)`: returns the GTK widget
   - `on_activate(app)`: called when page becomes visible

### Adding a New Page
1. Create `pages/mixer/your_page.py`:
```python
from pages.base import BasePage

class YourPage(BasePage):
    id = "your_page"
    title = "Your Title"
    icon = "icon-name"
    
    @staticmethod
    def get_sidebar_items():
        return [("your_page", "Your Title", "icon-name", "Description")]
    
    def build(self, app, builder):
        return builder.get_object("page_your_glade_id")
    
    def on_activate(self, app):
        app.reload_your_feature()
```
2. It auto-appears in sidebar on next run - no main.py changes needed!

### Current Status
- Page infrastructure: DONE
- Auto-discovery: DONE
- ROW_TO_PAGE auto-generation: DONE
- ui_common helpers: DONE
- **FULL METHOD MIGRATION**: PENDING - page classes currently delegate to `app.reload_*()` methods in main.py

### Full Migration (Optional Future Work)
To fully isolate pages, migrate the actual logic from `main.py` methods into page classes. Example:
- Move `reload_wallpapers()`, `_reload_wallpapers_thread()`, `_sorted_filtered_wallpapers()` from main.py into `pages/mixer/wallpapers.py`
- This can be done incrementally, one page at a time

### Testing
```bash
# Test page discovery
python3 -c "from pages import get_all_pages; print(get_all_pages().keys())"

# Test ROW_TO_PAGE mapping
python3 -c "from pages import get_row_to_page_map; print(get_row_to_page_map())"

# Run app
python3 main.py
```

### Key Files
- `pages/__init__.py` - Registry and auto-discovery
- `pages/base.py` - BasePage class
- `main.py` - Still contains most page logic (delegated via `app.reload_*()`)
