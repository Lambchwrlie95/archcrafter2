# Fetch Tab Design (Fastfetch-First)

Date: 2026-02-27
Project: Loom (`/home/lamb/.config/loom`)

## 1) Goal
Build a real Fetch experience in the Mixer mode that lets users browse, preview, and apply fetch presets, starting with Fastfetch and leaving an explicit extension path for Neofetch and future Builder-driven authoring.

## 2) Context Snapshot
- Existing state:
  - Sidebar row `row_fetch` is wired to stack page `fetch`.
  - `page_fetch` is currently a placeholder label only.
  - Bar/GTK/Icon/Cursor tabs already use card-style GTK3 layouts and runtime status chips.
- Existing architecture:
  - Glade-first GTK3 layout (`Archcrafter2.glade`), runtime behavior in `main.py`, settings persisted in `settings.json` via `SettingsStore`.
  - Service modules live under `backend/` and are imported in `backend/__init__.py`.

## 3) Selected Direction
Fastfetch-first, engine-ready architecture.

Why:
- Fastfetch is installed (`2.59.0`) and supports JSON/JSONC presets well.
- Delivers value quickly for Arch ricing workflows.
- Keeps a clean abstraction so Neofetch support can be added without UI rewrites.

## 4) UX Layout (GTK3 / Glade)
## Header Controls
- `GtkComboBoxText` for engine selection (`Fastfetch`, `Neofetch`).
- `GtkFileChooserButton` for preset folder root.
- `GtkSearchEntry` for preset name/tag filtering.
- `GtkButton` refresh action.

## Main Content
- Left side: preset browser (`GtkFlowBox`) with cards.
  - Card fields: preset title, engine badge, short description/tags.
  - Primary action: select card (single selection).
- Right side: preset preview panel.
  - Non-editable `GtkTextView` in monospace style for command output or JSON summary.
  - Metadata labels: source path, last modified, engine compatibility.

## Footer Actions
- `Run Preview`: execute fetch command safely and show output.
- `Set Default`: persist selected preset in `settings.json`.
- `Open File`: open selected preset in system editor.
- `Reveal Folder`: open preset directory with `xdg-open`.
- `Open Builder`: switch to Builder mode for future Fetch Builder page.

## 5) Data Model & Storage
## Preset Sources
- Default folder roots:
  - `library/fetch/fastfetch/`
  - `library/fetch/neofetch/`
- Fastfetch accepted extensions: `.json`, `.jsonc`.
- Neofetch accepted extension: `.conf` (future parsing; initially list/run-only).

## Metadata Catalog
- Optional index file: `library/fetch/presets/index.json`.
  - Purpose: user-friendly title, tags, and grouping without mutating raw preset files.

## Settings Schema Additions
New `fetch` section in `settings.json`:
- `engine` (`fastfetch` by default)
- `preset_dirs` (list)
- `default_preset` (path or logical id)
- `search_text`
- `auto_refresh`

## 6) Behavior Rules
- If selected engine binary is missing, disable run/apply actions and show warning chip.
- Preserve selection if a refresh occurs and preset still exists.
- Running preview uses subprocess without shell interpolation.
- Truncate excessively long output in preview (with a "show more" path in later phase).

## 7) Error Handling
- Missing folder: show info message and offer to create folder.
- Invalid Fastfetch JSON/JSONC: mark card as invalid, keep it visible, show parse reason.
- Command failure: show stderr in preview panel and app status infobar.

## 8) Visual Language
- Reuse existing CSS classes (`theme-card`, `theme-subtitle`, `theme-type-badge`, `theme-apply-button`) for consistency.
- Add only fetch-specific helper classes for preview pane and engine status chips.

## 9) Builder Integration (Phase 2)
- Builder sidebar adds `builder_fetch` item.
- Builder page for composing Fastfetch modules and exporting JSON into `library/fetch/fastfetch/`.
- Fetch tab auto-detects new exported presets.

## 10) Milestones
- M1: Fetch tab UI + Fastfetch preset discovery + preview output + default selection persistence.
- M2: Neofetch listing/run integration.
- M3: Builder Fetch composer and export pipeline.

## 11) Verification Strategy
- Static checks:
  - `xmllint --noout Archcrafter2.glade`
  - `python3 -m py_compile main.py backend/*.py`
- Functional checks:
  - Select engine, search presets, run preview, set default, restart app and confirm persistence.
  - Validate missing-binary behavior by temporarily masking command path.

## 12) Official References
- GTK3 API: https://docs.gtk.org/gtk3/
- GtkBuilder: https://docs.gtk.org/gtk3/class.Builder.html
- GtkFlowBox: https://docs.gtk.org/gtk3/class.FlowBox.html
- GtkTextView: https://docs.gtk.org/gtk3/class.TextView.html
- GtkCssProvider: https://docs.gtk.org/gtk3/class.CssProvider.html
- Python 3.14 docs: https://docs.python.org/3.14/
- Fastfetch 2.59.0 release: https://github.com/fastfetch-cli/fastfetch/releases/tag/2.59.0
- Fastfetch config docs (not release-pinned): https://github.com/fastfetch-cli/fastfetch/wiki/Configuration
- Neofetch 7.1.0 release: https://github.com/dylanaraps/neofetch/releases/tag/7.1.0
