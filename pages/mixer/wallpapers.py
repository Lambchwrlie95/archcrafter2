"""Compatibility shim for wallpapers section.

This module keeps the original import path while delegating the real
implementation to `pages.sections.wallpapers` to allow an incremental
migration without breaking existing code.
"""

from pages.sections.wallpapers import WallpaperPage  # noqa: F401

