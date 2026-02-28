from pathlib import Path

import pytest

from backend.services import ServiceContainer
from backend.wallpapers import THUMB_SIZE_MAX, THUMB_SIZE_MIN, THUMB_SIZE_DEFAULT


def _build_service(base: Path):
    container = ServiceContainer(base, base / "settings.json")
    return container.wallpapers


def test_wallpaper_service_defaults_and_setters(tmp_path: Path):
    base = tmp_path / "app"
    svc = _build_service(base)

    # default source and setter validation
    assert svc.get_source() == "custom"
    svc.set_source("system")
    assert svc.get_source() == "system"
    svc.set_source("bogus")
    assert svc.get_source() == "custom"

    # fill mode
    assert svc.get_fill_mode() in ("zoom-fill", "centered", "scaled", "tiled", "auto")
    svc.set_fill_mode("centered")
    assert svc.get_fill_mode() == "centered"
    svc.set_fill_mode("invalid")
    assert svc.get_fill_mode() == "zoom-fill"

    # view mode
    assert svc.get_view_mode() in ("grid", "list")
    svc.set_view_mode("list")
    assert svc.get_view_mode() == "list"
    svc.set_view_mode("oops")
    assert svc.get_view_mode() == "grid"

    # sort mode
    assert svc.get_sort_mode() in ("name_asc", "name_desc", "newest", "oldest")
    svc.set_sort_mode("name_desc")
    assert svc.get_sort_mode() == "name_desc"
    svc.set_sort_mode("x")
    assert svc.get_sort_mode() == "name_asc"

    # thumb size boundaries
    assert svc.get_thumb_size() == THUMB_SIZE_DEFAULT
    svc.set_thumb_size(THUMB_SIZE_MAX + 100)
    assert svc.get_thumb_size() == THUMB_SIZE_MAX
    # test with invalid value; method converts to int(value) which raises and defaults
    svc.set_thumb_size(int(200))
    assert svc.get_thumb_size() == 200


def test_custom_dirs_and_search(tmp_path: Path):
    base = tmp_path / "app"
    svc = _build_service(base)

    folder = base / "foo"
    folder.mkdir(parents=True)
    svc.set_custom_dir(folder)
    assert folder in svc.get_custom_dirs()

    # search dirs should contain either system or custom and colorized
    svc.set_source("custom")
    dirs = svc.get_search_dirs()
    assert folder in dirs
    assert svc.colorized_dir in dirs

    # switching to system removes custom, but retains colorized
    svc.set_source("system")
    dirs2 = svc.get_search_dirs()
    assert folder not in dirs2
    assert svc.colorized_dir in dirs2


@pytest.mark.parametrize("value", ["xyz", 1.23, None])
def test_get_custom_dirs_filters_non_paths(tmp_path: Path, value):
    base = tmp_path / "app"
    svc = _build_service(base)
    # manually poke corrupt entries
    state = svc.get_state()
    state["custom_dirs"] = [value]
    svc.settings.save()
    # should never raise and should return list with at least library_dir
    result = svc.get_custom_dirs()
    assert isinstance(result, list)
    assert svc.library_dir in result


def test_get_colorized_badge_css(tmp_path: Path) -> None:
    """Test badge CSS generation for colorized wallpapers."""
    base = tmp_path / "app"
    svc = _build_service(base)

    # default color should be used if not configured
    bg, text = svc.get_colorized_badge_css()
    assert isinstance(bg, str)
    assert isinstance(text, str)
    # should be rgba and hex color
    assert "rgba" in bg
    assert text.startswith("#")

    # set a custom badge color
    section = svc.settings.get_section("wallpapers", default={})
    section["colorized_badge_color"] = "#FF0000"  # bright red
    svc.settings.save()

    bg2, text2 = svc.get_colorized_badge_css()
    # bright red should produce dark text
    assert text2 == "#111111"
    assert "255" in bg2  # red channel is 255

    # set a dark color
    section["colorized_badge_color"] = "#000000"  # black
    svc.settings.save()

    bg3, text3 = svc.get_colorized_badge_css()
    # black should produce light text
    assert text3 == "#ffffff"
