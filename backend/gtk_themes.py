from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess
from typing import Any

from .settings import SettingsStore


@dataclass(frozen=True)
class GtkThemeEntry:
    name: str
    path: Path
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

    def _theme_search_paths(self) -> list[Path]:
        return [p for p in self.system_dirs + self.user_dirs if p.exists()]

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

                css_path = p / "gtk-3.0" / "gtk.css"
                if not css_path.exists():
                    continue

                metadata = self.get_theme_metadata(p.name, css_path)
                found[p.name] = GtkThemeEntry(
                    name=p.name,
                    path=p,
                    colors=metadata["colors"],
                    type=metadata["type"],
                )

        return sorted(found.values(), key=lambda x: x.name.lower())

    def _looks_dark_name(self, name: str) -> bool:
        n = name.lower()
        tokens = ("dark", "black", "night", "nokto", "dracula", "noir")
        return any(t in n for t in tokens)

    def _looks_light_name(self, name: str) -> bool:
        n = name.lower()
        tokens = ("light", "white", "day")
        return any(t in n for t in tokens)

    def _extract_color_from_css(self, content: str, names: tuple[str, ...]) -> str | None:
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
            bg = self._extract_color_from_css(content, ("theme_bg_color", "theme_base_color", "bg_color"))
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
                ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", theme_name],
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

        css_file = entry.path / "gtk-3.0" / "gtk.css"
        if css_file.exists():
            return css_file
        return None
