from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .settings import SettingsStore


@dataclass(frozen=True)
class GtkThemeEntry:
    name: str
    path: Path
    css_path: Path
    colors: dict[str, str] = field(
        default_factory=lambda: {
            "bg": "#2f343f",
            "fg": "#e6eaf0",
            "accent": "#5ba1ea",
        }
    )
    type: str = "unknown"  # "light", "dark", "unknown"


class GtkThemeService:
    def __init__(self, base_dir: Path, settings: SettingsStore):
        self.base_dir = Path(base_dir)
        self.settings = settings
        self.system_dirs = [Path("/usr/share/themes")]
        self.user_dirs = [
            Path("~/.themes").expanduser(),
            Path("~/.local/share/themes").expanduser(),
        ]
        # cache key: absolute css path -> (mtime, metadata)
        self._metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._metadata_cache_dirty = False
        self.cache_dir = self.base_dir / "cache"
        self.metadata_cache_file = self.cache_dir / "gtk_theme_metadata.json"
        self._load_metadata_cache_from_disk()

    def _load_metadata_cache_from_disk(self) -> None:
        self._metadata_cache = {}
        if not self.metadata_cache_file.exists():
            return
        try:
            payload = json.loads(self.metadata_cache_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            entries = payload.get("entries", {})
            if not isinstance(entries, dict):
                return
            for key, value in entries.items():
                if not isinstance(key, str) or not isinstance(value, dict):
                    continue
                mtime = float(value.get("mtime", 0.0))
                meta = value.get("meta", {})
                if not isinstance(meta, dict):
                    continue
                colors = meta.get("colors", {})
                theme_type = str(meta.get("type", "unknown"))
                if not isinstance(colors, dict):
                    continue
                self._metadata_cache[key] = (
                    mtime,
                    {"colors": dict(colors), "type": theme_type},
                )
        except Exception:
            self._metadata_cache = {}

    def _save_metadata_cache_to_disk(self) -> None:
        if not self._metadata_cache_dirty:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            entries: dict[str, dict[str, Any]] = {}
            for key, (mtime, meta) in self._metadata_cache.items():
                entries[key] = {"mtime": float(mtime), "meta": dict(meta)}

            payload = {"version": 1, "entries": entries}
            tmp = self.metadata_cache_file.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            tmp.replace(self.metadata_cache_file)
            self._metadata_cache_dirty = False
        except Exception:
            pass

    def _theme_search_paths(self) -> list[Path]:
        return [p for p in self.system_dirs + self.user_dirs if p.exists()]

    def _resolve_theme_css_path(self, theme_dir: Path) -> Path | None:
        gtk3_dir = theme_dir / "gtk-3.0"
        if not gtk3_dir.is_dir():
            return None

        preferred = ("gtk.css", "gtk-dark.css", "gtk-contained.css")
        for name in preferred:
            candidate = gtk3_dir / name
            if candidate.is_file():
                return candidate

        try:
            extra = sorted(p for p in gtk3_dir.glob("*.css") if p.is_file())
        except Exception:
            extra = []
        if extra:
            return extra[0]
        return None

    def list_themes(self) -> list[GtkThemeEntry]:
        found: dict[str, GtkThemeEntry] = {}

        # System first, user second. Same-name entries are overwritten by user themes.
        for folder in self._theme_search_paths():
            try:
                entries = list(folder.iterdir())
            except Exception:
                continue

            for p in entries:
                if not p.is_dir():
                    continue

                css_path = self._resolve_theme_css_path(p)
                if css_path is None:
                    continue

                metadata = self.get_theme_metadata(p.name, css_path)
                found[p.name] = GtkThemeEntry(
                    name=p.name,
                    path=p,
                    css_path=css_path,
                    colors=metadata["colors"],
                    type=metadata["type"],
                )

        self._save_metadata_cache_to_disk()
        return sorted(found.values(), key=lambda x: x.name.lower())

    def _looks_dark_name(self, name: str) -> bool:
        n = name.lower()
        tokens = ("dark", "black", "night", "nokto", "dracula", "noir")
        return any(t in n for t in tokens)

    def _looks_light_name(self, name: str) -> bool:
        n = name.lower()
        tokens = ("light", "white", "day")
        return any(t in n for t in tokens)

    def _extract_color_from_css(
        self, content: str, names: tuple[str, ...]
    ) -> str | None:
        for key in names:
            # @define-color theme_bg_color #2f343f;
            m_define = re.search(
                rf"@define-color\s+{re.escape(key)}\s+([^;\n]+)",
                content,
                flags=re.IGNORECASE,
            )
            if m_define:
                color = self._normalize_color(m_define.group(1))
                if color:
                    return color

            # CSS custom property fallback: theme_bg_color: #2f343f;
            m_prop = re.search(
                rf"\b{re.escape(key)}\b\s*:\s*([^;\n]+)",
                content,
                flags=re.IGNORECASE,
            )
            if m_prop:
                color = self._normalize_color(m_prop.group(1))
                if color:
                    return color

        return None

    def get_theme_metadata(self, name: str, css_path: Path) -> dict[str, Any]:
        default_colors = {
            "bg": "#2f343f",
            "fg": "#e6eaf0",
            "accent": "#5ba1ea",
        }

        cache_key = str(css_path.resolve())
        mtime = 0.0
        try:
            mtime = css_path.stat().st_mtime
        except Exception:
            pass

        cached = self._metadata_cache.get(cache_key)
        if cached is not None and cached[0] == mtime:
            return dict(cached[1])

        colors = dict(default_colors)

        try:
            content = css_path.read_text(errors="ignore")
            bg = self._extract_color_from_css(
                content, ("theme_bg_color", "theme_base_color", "bg_color")
            )
            fg = self._extract_color_from_css(content, ("theme_fg_color", "fg_color"))
            accent = self._extract_color_from_css(
                content,
                (
                    "theme_selected_bg_color",
                    "accent_color",
                    "selected_bg_color",
                    "theme_selected_fg_color",
                ),
            )
            if bg:
                colors["bg"] = bg
            if fg:
                colors["fg"] = fg
            if accent:
                colors["accent"] = accent
        except Exception:
            # Keep defaults and use name heuristic.
            pass

        has_dark_name = self._looks_dark_name(name)
        has_light_name = self._looks_light_name(name)

        # Prefer explicit naming when present.
        if has_dark_name and not has_light_name:
            theme_type = "dark"
        elif has_light_name and not has_dark_name:
            theme_type = "light"
        else:
            # Fall back to luminance of background color.
            lum = self._get_luminance(colors["bg"])
            theme_type = "dark" if lum < 0.46 else "light"

        meta: dict[str, Any] = {"colors": colors, "type": theme_type}
        self._metadata_cache[cache_key] = (mtime, dict(meta))
        self._metadata_cache_dirty = True
        return meta

    def _normalize_color(self, value: str) -> str | None:
        value = str(value).strip()

        # hex forms: #rgb, #rrggbb, #rrggbbaa
        m_hex = re.search(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", value)
        if m_hex:
            raw = m_hex.group(1)
            if len(raw) == 3:
                raw = "".join(ch * 2 for ch in raw)
            elif len(raw) == 8:
                raw = raw[:6]
            return f"#{raw.lower()}"

        # rgb()/rgba()
        m_rgb = re.search(
            r"rgba?\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})",
            value,
            flags=re.IGNORECASE,
        )
        if m_rgb:
            r = max(0, min(255, int(m_rgb.group(1))))
            g = max(0, min(255, int(m_rgb.group(2))))
            b = max(0, min(255, int(m_rgb.group(3))))
            return f"#{r:02x}{g:02x}{b:02x}"

        return None

    def _get_luminance(self, hex_color: str) -> float:
        try:
            value = str(hex_color).lstrip("#")
            if len(value) == 3:
                value = "".join([c * 2 for c in value])
            if len(value) < 6:
                return 0.5
            r = int(value[0:2], 16)
            g = int(value[2:4], 16)
            b = int(value[4:6], 16)
            return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        except Exception:
            return 0.5

    def get_current_theme(self) -> str | None:
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                value = res.stdout.strip().strip("'")
                return value or None
        except Exception:
            pass
        return None

    def apply_theme(self, theme_name: str) -> tuple[bool, str]:
        available = {t.name for t in self.list_themes()}
        if theme_name not in available:
            return False, f"Theme not found: {theme_name}"

        try:
            res = subprocess.run(
                [
                    "gsettings",
                    "set",
                    "org.gnome.desktop.interface",
                    "gtk-theme",
                    theme_name,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return True, f"Applied GTK theme: {theme_name}"

            error_text = (res.stderr or "").strip() or "gsettings set failed"
            return False, f"Failed to apply GTK theme: {error_text}"
        except Exception as exc:
            return False, f"Failed to apply GTK theme: {exc}"

    def get_theme_css_path(self, theme_name: str) -> Path | None:
        entry = next((t for t in self.list_themes() if t.name == theme_name), None)
        if entry is None:
            return None

        if entry.css_path.exists():
            return entry.css_path
        return None

    # -------------------------------------------------------
    # preview rendering and caching (originally in main.py)
    # -------------------------------------------------------

    def _theme_signature(self, theme) -> str:
        """Generate a cache-invalidation signature for a theme based on mtime/size."""
        css_path = getattr(theme, "css_path", theme.path / "gtk-3.0" / "gtk.css")
        try:
            st = css_path.stat()
            resolved = str(css_path.resolve())
            return f"{resolved}:{int(st.st_mtime_ns)}:{int(st.st_size)}"
        except Exception:
            return f"{str(css_path)}:{theme.name}"

    def _preview_cache_slug(self, name: str) -> str:
        """Sanitize theme name for use in filesystem paths."""
        return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name[:48])

    def preview_cache_path(self, theme, variant: str, preview_size: tuple[int, int]) -> Path:
        """Generate path for cached preview image."""
        width, height = preview_size
        key = (
            f"gtk-preview-v1|{theme.name}|{variant}|{width}x{height}|"
            f"{self._theme_signature(theme)}"
        )
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
        slug = self._preview_cache_slug(theme.name)
        cache_dir = self.cache_dir / "gtk_previews"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{slug}-{variant}-{digest}.png"

    def render_preview_to_cache(
        self, theme, variant: str, out_path: Path, preview_renderer_path: Path
    ) -> bool:
        """Render GTK theme preview via subprocess and cache the result."""
        if not preview_renderer_path.exists():
            return False

        # Get dimensions from variant (card vs panel)
        width = 640 if variant == "panel" else 320
        height = 420 if variant == "panel" else 150

        tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
        cmd = [
            sys.executable,
            str(preview_renderer_path),
            "--theme",
            str(theme.name),
            "--output",
            str(tmp_path),
            "--width",
            str(width),
            "--height",
            str(height),
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=22,
            )
            if res.returncode != 0 or not tmp_path.exists():
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass
                return False
            tmp_path.replace(out_path)
            return True
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            return False
