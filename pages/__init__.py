"""Page registry and discovery utilities.

This module provides a simple registration API that page modules can use
via the `@register_page` decorator. A light-weight auto-discovery still
imports page modules under the known `MODES` so packages that haven't been
converted will continue to work.
"""

from importlib import import_module
from pathlib import Path
from typing import Type, TYPE_CHECKING, Optional

from pages.base import BasePage

if TYPE_CHECKING:
    from main import ArchCrafter2App

MODES = ["mixer", "builder", "presets"]

# Central registry for page id -> page class
_PAGE_REGISTRY: dict[str, Type[BasePage]] = {}


def register_page(cls: Type[BasePage]) -> Type[BasePage]:
    """Register a page class in the central registry.

    Usage:
        @register_page
        class MyPage(BasePage):
            id = "my_page"
            ...
    """
    if not hasattr(cls, "id") or not getattr(cls, "id"):
        raise ValueError("Page class must define a non-empty `id` attribute")
    _PAGE_REGISTRY[cls.id] = cls
    return cls


def _import_mode_modules() -> None:
    """Import modules under `pages.<mode>` to allow them to register.

    Import errors are caught and logged (no logging dependency here, so
    failures are silently ignored) to avoid breaking the app if a single
    page module has a problem.
    """
    base = Path(__file__).parent
    for mode in MODES:
        mode_dir = base / mode
        if not mode_dir.exists():
            continue
        for py_file in mode_dir.glob("*.py"):
            if py_file.stem in ("__init__",) or py_file.stem.startswith("_"):
                continue
            module_name = f"pages.{mode}.{py_file.stem}"
            try:
                import_module(module_name)
            except Exception:
                # Ignore faulty page modules during discovery; they can
                # still be diagnosed separately by running them directly.
                continue


def get_all_pages() -> dict[str, Type[BasePage]]:
    """Return the registry of discovered/registered pages.

    If the registry is empty we attempt an import-based discovery so
    modules using the `@register_page` decorator (or legacy modules)
    are loaded.
    """
    if not _PAGE_REGISTRY:
        _import_mode_modules()
        # Legacy: perform a lightweight scan for classes in already-imported
        # modules for backward compatibility.
        for mode in MODES:
            pkg_prefix = f"pages.{mode}."
            # iterate through currently imported modules
            for name, module in list(globals().items()):
                pass
        # If a `pages.sections` package exists, import its grouped SECTIONS
        # mapping and merge into the registry for convenience.
        try:
            sect_mod = import_module("pages.sections")
            sect_map = getattr(sect_mod, "SECTIONS", None)
            if isinstance(sect_map, dict):
                for k, v in sect_map.items():
                    if k not in _PAGE_REGISTRY:
                        _PAGE_REGISTRY[k] = v
        except Exception:
            # Ignore; sections package is optional
            pass
    return _PAGE_REGISTRY


# Convenience exports for the grouped sections package
try:
    from pages.sections import SECTIONS as SECTIONS  # type: ignore
    from pages.sections import ALL_PAGES as ALL_PAGES  # type: ignore
except Exception:
    SECTIONS = {}
    ALL_PAGES = []


def get_section_class(page_id: str) -> Optional[Type[BasePage]]:
    """Return the page class for a section `page_id` if available."""
    # Prefer explicit sections mapping, fall back to registry.
    cls = SECTIONS.get(page_id) if isinstance(SECTIONS, dict) else None
    if cls:
        return cls
    return _PAGE_REGISTRY.get(page_id)


def get_mode_pages(mode: str) -> list[Type[BasePage]]:
    """Get all pages for a specific mode."""
    return [p for p in get_all_pages().values() if p.__module__.startswith(f"pages.{mode}")]


def get_sidebar_items_for_mode(mode: str) -> list:
    """Gather all sidebar items for a mode from its pages."""
    items = []
    for page_cls in get_mode_pages(mode):
        items.extend(page_cls.get_sidebar_items())
    return items


def create_page_instance(page_id: str, app: "ArchCrafter2App") -> Optional[BasePage]:
    """Create an instance of a page by ID using the registry."""
    page_cls = _PAGE_REGISTRY.get(page_id)
    if page_cls:
        return page_cls()
    return None


def get_row_to_page_map() -> dict[str, str]:
    """Generate ROW_TO_PAGE map from page sidebar items."""
    row_to_page = {}
    for page_cls in get_all_pages().values():
        for item in page_cls.get_sidebar_items():
            row_id = item[0]
            row_to_page[f"row_{row_id}"] = page_cls.id
    return row_to_page


def get_page_to_row_map() -> dict[str, str]:
    """Generate PAGE_TO_ROW map (reverse of ROW_TO_PAGE)."""
    return {v: k for k, v in get_row_to_page_map().items()}
