# Loom (refactor notes)

This repo is a GTK3-based desktop configuration tool. I performed a
refactor to separate UI pages into discrete "sections" so you can work on
features independently (e.g. Wallpapers, GTK themes, Window themes, Icons,
Cursors, Panels, Menu, Terminals, Fetch, More).

Key structural notes
- UI pages are now implemented under `pages/sections/` as individual
  modules (e.g. `pages/sections/wallpapers.py`).
- `pages/mixer/*` modules are compatibility shims that import the real
  implementation from `pages.sections` so existing imports continue to work
  during the migration.
- `pages/__init__.py` exposes a `register_page` decorator for explicit
  page registration and merges `pages.sections.SECTIONS` into the page
  registry for convenience.

How to run tests

Install the test dependency and run pytest:

```bash
python -m pip install -U pip
python -m pip install -r requirements.txt
pytest -q
```

Notes about running the app
- The application depends on system GTK/PyGObject libraries. To run the
  GUI you will likely need to install system packages such as `python3-gi`
  and GTK3 on your distribution.

Developer helpers
- A `ServiceContainer` (see `backend/services.py`) centralizes backend
  service creation and is intended to make tests easier and later allow
  swapping/mocking components. Application code still exposes shortcuts
  like `app.wallpaper_service` for backwards compatibility.

If you'd like, I can:
- Move builder/presets pages into `pages/sections/` and add shims,
- Add a GitHub Actions workflow to run tests on push/PR (I will add one),
- Add developer docs or type hints for services.
