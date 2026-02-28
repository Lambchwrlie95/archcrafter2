"""Tests for GtkThemeService theming and preview rendering."""

from pathlib import Path
import pytest

from backend.services import ServiceContainer
from backend.gtk_themes import GtkThemeService


def _build_service(base: Path) -> GtkThemeService:
    container = ServiceContainer(base, base / "settings.json")
    return container.gtk_themes


def test_gtk_theme_service_basics(tmp_path: Path) -> None:
    """Test basic GTK theme service construction and metadata."""
    base = tmp_path / "app"
    svc = _build_service(base)
    
    # should initialize without errors
    assert svc.base_dir == base
    assert svc.settings is not None
    
    # metadata cache should exist but be empty initially
    assert isinstance(svc._metadata_cache, dict)


def test_theme_signature_generation(tmp_path: Path) -> None:
    """Test signature generation for cache invalidation."""
    base = tmp_path / "app"
    svc = _build_service(base)
    
    # create a fake theme object
    class FakeTheme:
        name = "TestTheme"
        path = tmp_path / "themes" / "TestTheme"
    
    theme = FakeTheme()
    sig = svc._theme_signature(theme)
    
    # signature should be a string with theme name in it
    assert isinstance(sig, str)
    assert "TestTheme" in sig


def test_preview_cache_slug(tmp_path: Path) -> None:
    """Test cache slug sanitization."""
    base = tmp_path / "app"
    svc = _build_service(base)
    
    # normal name
    slug = svc._preview_cache_slug("My-Theme_123")
    assert slug == "My-Theme_123"
    
    # name with bad characters
    slug2 = svc._preview_cache_slug("My Theme! @#$%")
    assert "_" in slug2
    assert all(c.isalnum() or c in "-_" for c in slug2)
    
    # long name should be truncated
    slug3 = svc._preview_cache_slug("x" * 100)
    assert len(slug3) <= 48


def test_preview_cache_path(tmp_path: Path) -> None:
    """Test preview cache path generation."""
    base = tmp_path / "app"
    svc = _build_service(base)
    
    class FakeTheme:
        name = "TestTheme"
        path = tmp_path / "themes" / "TestTheme"
    
    theme = FakeTheme()
    path_card = svc.preview_cache_path(theme, "card", (320, 150))
    path_panel = svc.preview_cache_path(theme, "panel", (640, 420))
    
    # paths should be different
    assert path_card != path_panel
    
    # both should be in cache dir
    assert "gtk_previews" in str(path_card)
    assert "gtk_previews" in str(path_panel)
    
    # both should exist (created by method)
    assert path_card.parent.exists()
