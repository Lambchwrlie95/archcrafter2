"""Page registry and auto-discovery."""

from pathlib import Path
from typing import Type, TYPE_CHECKING, Optional

from pages.base import BasePage

if TYPE_CHECKING:
    from main import ArchCrafter2App

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
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BasePage)
                    and attr is not BasePage
                ):
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


def create_page_instance(page_id: str, app: "ArchCrafter2App") -> Optional[BasePage]:
    """Create an instance of a page by ID."""
    pages = get_all_pages()
    page_cls = pages.get(page_id)
    if page_cls:
        return page_cls()
    return None


def get_row_to_page_map() -> dict[str, str]:
    """Generate ROW_TO_PAGE map from page sidebar items."""
    row_to_page = {}
    for page_cls in get_all_pages().values():
        for item in page_cls.get_sidebar_items():
            row_id = item[0]  # First element is row_id
            row_to_page[f"row_{row_id}"] = page_cls.id
    return row_to_page


def get_page_to_row_map() -> dict[str, str]:
    """Generate PAGE_TO_ROW map (reverse of ROW_TO_PAGE)."""
    return {v: k for k, v in get_row_to_page_map().items()}
