from __future__ import annotations

import colorsys
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

from .settings import SettingsStore
from .wallpaper_names import WallpaperNameStore

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
FILL_MODES = ["zoom-fill", "centered", "scaled", "tiled", "auto"]
SORT_MODES = ["name_asc", "name_desc", "newest", "oldest"]
THUMB_SIZE_MIN = 160
THUMB_SIZE_MAX = 320
THUMB_SIZE_DEFAULT = 220
ASKPASS_CANDIDATES = [
    "/usr/bin/ssh-askpass",
    "/usr/lib/ssh/ssh-askpass",
    "/usr/bin/ksshaskpass",
    "/usr/bin/lxqt-openssh-askpass",
    "/usr/bin/gnome-ssh-askpass",
]


@dataclass(frozen=True)
class WallpaperEntry:
    name: str
    path: Path


class WallpaperService:
    def __init__(self, base_dir: Path, settings: SettingsStore):
        self.base_dir = Path(base_dir)
        self.settings = settings
        self.library_dir = self.base_dir / "library" / "wallpapers"
        self.colorized_dir = self.library_dir / "colorized"
        self.legacy_colorized_dir = self.base_dir / "cache" / "wallpaper_variants"
        self.system_dirs = [
            Path("/usr/share/backgrounds"),
            Path("/usr/share/wallpapers"),
        ]
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self.colorized_dir.mkdir(parents=True, exist_ok=True)
        self.variant_dir = self.colorized_dir

        # palette caching state (moved from application)
        self.cache_dir = self.base_dir / "cache"
        self.thumb_cache_dir = self.cache_dir / "thumbnails"
        self.palette_cache_file = self.cache_dir / "palette_cache.json"
        self._palette_cache: dict[str, list[str]] = {}
        self._palette_disk_cache: dict[str, list[str]] = {}
        self._palette_cache_dirty = False
        self._palette_cache_dirty_count = 0
        self._palette_cache_lock = threading.Lock()

        self._import_legacy_colorized_variants()
        self.name_store = WallpaperNameStore(settings)
        self._ensure_defaults()

        # initialize directories that used to be created by the app
        self.thumb_cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_palette_cache_from_disk()
        self._prune_thumbnail_cache(max_files=5000)

    def _prune_thumbnail_cache(self, max_files: int = 5000):
        try:
            files = sorted(
                self.thumb_cache_dir.glob("*.png"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            return
        if len(files) <= max_files:
            return
        for old in files[max_files:]:
            try:
                old.unlink()
            except Exception:
                continue

    def _import_legacy_colorized_variants(self) -> None:
        legacy = self.legacy_colorized_dir
        if not legacy.exists() or not legacy.is_dir():
            return

        for src in legacy.glob("*"):
            try:
                if not src.is_file() or src.suffix.lower() not in SUPPORTED_EXTS:
                    continue
                dst = self.colorized_dir / src.name
                if not dst.exists():
                    shutil.copy2(src, dst)
            except Exception:
                continue

    def _ensure_defaults(self) -> None:
        section = self.settings.get_section("wallpapers", default={})
        section.setdefault("source", "custom")
        section.setdefault("fill_mode", "zoom-fill")
        section.setdefault("view_mode", "grid")
        section.setdefault(
            "custom_dirs", [str(self.library_dir), str(self.colorized_dir)]
        )
        section.setdefault("sort_mode", "name_asc")
        section.setdefault("thumb_size", THUMB_SIZE_DEFAULT)
        section.setdefault("colorize_strength", 65)
        section.setdefault("colorized_tag_color", "#1482C8")
        section.setdefault("colorized_badge_color", "#1482C8")
        section.setdefault("name_overrides", {})

        dirs = section.get("custom_dirs", [])
        if not isinstance(dirs, list):
            dirs = []
        colorized = str(self.colorized_dir)
        if colorized not in dirs:
            dirs.append(colorized)
        section["custom_dirs"] = dirs

        self.settings.save()

    def get_state(self) -> dict:
        return self.settings.get_section("wallpapers", default={})

    def get_source(self) -> str:
        source = str(self.get_state().get("source", "custom"))
        return source if source in {"custom", "system"} else "custom"

    def set_source(self, source: str) -> None:
        section = self.get_state()
        section["source"] = "system" if source == "system" else "custom"
        self.settings.save()

    def get_fill_mode(self) -> str:
        mode = str(self.get_state().get("fill_mode", "zoom-fill"))
        return mode if mode in FILL_MODES else "zoom-fill"

    def set_fill_mode(self, mode: str) -> None:
        section = self.get_state()
        section["fill_mode"] = mode if mode in FILL_MODES else "zoom-fill"
        self.settings.save()

    def get_view_mode(self) -> str:
        mode = str(self.get_state().get("view_mode", "grid"))
        return mode if mode in {"grid", "list"} else "grid"

    def set_view_mode(self, mode: str) -> None:
        section = self.get_state()
        section["view_mode"] = "list" if mode == "list" else "grid"
        self.settings.save()

    def get_sort_mode(self) -> str:
        mode = str(self.get_state().get("sort_mode", "name_asc"))
        return mode if mode in SORT_MODES else "name_asc"

    def set_sort_mode(self, mode: str) -> None:
        section = self.get_state()
        section["sort_mode"] = mode if mode in SORT_MODES else "name_asc"
        self.settings.save()

    def get_thumb_size(self) -> int:
        value = self.get_state().get("thumb_size", THUMB_SIZE_DEFAULT)
        try:
            size = int(value)
        except Exception:
            size = THUMB_SIZE_DEFAULT
        return max(THUMB_SIZE_MIN, min(THUMB_SIZE_MAX, size))

    def set_thumb_size(self, size: int) -> None:
        try:
            parsed = int(size)
        except Exception:
            parsed = THUMB_SIZE_DEFAULT
        section = self.get_state()
        section["thumb_size"] = max(THUMB_SIZE_MIN, min(THUMB_SIZE_MAX, parsed))
        self.settings.save()

    def get_custom_dirs(self) -> list[Path]:
        section = self.get_state()
        dirs = section.get("custom_dirs", [str(self.library_dir)])
        result = []
        for value in dirs:
            try:
                p = Path(value).expanduser()
            except Exception:
                continue
            if p not in result:
                result.append(p)
        if not result:
            result = [self.library_dir]
        return result

    def set_custom_dir(self, folder: Path) -> None:
        p = Path(folder).expanduser()
        section = self.get_state()

        dirs = [str(p)]
        try:
            if p.resolve() != self.colorized_dir.resolve():
                dirs.append(str(self.colorized_dir))
        except Exception:
            dirs.append(str(self.colorized_dir))

        section["custom_dirs"] = dirs
        section["source"] = "custom"
        self.settings.save()

    def get_search_dirs(self) -> list[Path]:
        dirs: list[Path] = []

        if self.get_source() == "system":
            dirs.extend(self.system_dirs)
        else:
            dirs.extend(self.get_custom_dirs())

        if self.colorized_dir not in dirs:
            dirs.append(self.colorized_dir)

        unique: list[Path] = []
        for d in dirs:
            if d.exists() and d not in unique:
                unique.append(d)
        return unique

    # -----------------------------------------------------------
    # palette / color utilities (originally in main.py)
    # -----------------------------------------------------------

    def _file_signature(self, path: Path):
        try:
            st = path.stat()
            return (int(st.st_mtime_ns), int(st.st_size))
        except Exception:
            return (0, 0)

    def _palette_cache_key(self, path: Path, count: int):
        sig_mtime, sig_size = self._file_signature(path)
        try:
            resolved = str(path.resolve())
        except Exception:
            resolved = str(path)
        src = f"{resolved}|{sig_mtime}:{sig_size}|{int(count)}"
        return hashlib.sha1(src.encode("utf-8")).hexdigest()

    def _load_palette_cache_from_disk(self):
        with self._palette_cache_lock:
            self._palette_disk_cache = {}
        if not self.palette_cache_file.exists():
            return
        try:
            payload = json.loads(self.palette_cache_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            entries = payload.get("entries", {})
            if not isinstance(entries, dict):
                return
            for key, value in entries.items():
                if not isinstance(key, str) or not isinstance(value, list):
                    continue
                colors = [str(c).lower() for c in value if isinstance(c, str)]
                if colors:
                    with self._palette_cache_lock:
                        self._palette_disk_cache[key] = colors
        except Exception:
            with self._palette_cache_lock:
                self._palette_disk_cache = {}

    def _save_palette_cache_to_disk(self):
        if not self._palette_cache_dirty:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with self._palette_cache_lock:
                entries = dict(self._palette_disk_cache)
            data = {
                "version": 1,
                "entries": entries,
            }
            tmp = self.palette_cache_file.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(data, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            tmp.replace(self.palette_cache_file)
            self._palette_cache_dirty = False
            self._palette_cache_dirty_count = 0
        except Exception:
            pass

    def _maybe_flush_palette_cache(self):
        if self._palette_cache_dirty_count >= 24:
            self._save_palette_cache_to_disk()

    def extract_palette(self, path: Path, count: int = 5):
        """Return a cached palette for the given image file."""
        key = self._palette_cache_key(path, count)
        with self._palette_cache_lock:
            cached = self._palette_cache.get(key)
        if cached:
            return cached

        with self._palette_cache_lock:
            disk_cached = self._palette_disk_cache.get(key)
        if disk_cached:
            with self._palette_cache_lock:
                self._palette_cache[key] = disk_cached[:count]
                return self._palette_cache[key]

        colors = []
        try:
            pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 80, 80, True)
            width, height = pix.get_width(), pix.get_height()
            n = pix.get_n_channels()
            rowstride = pix.get_rowstride()
            data = pix.get_pixels()

            freq = {}
            step = max(1, int((width * height) / 1800))
            for y in range(0, height, step):
                base = y * rowstride
                for x in range(0, width, step):
                    i = base + x * n
                    r = data[i]
                    g = data[i + 1]
                    b = data[i + 2]
                    if n == 4 and data[i + 3] < 20:
                        continue
                    rq = (r // 24) * 24
                    gq = (g // 24) * 24
                    bq = (b // 24) * 24
                    freq[(rq, gq, bq)] = freq.get((rq, gq, bq), 0) + 1

            ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
            picked = []
            for (r, g, b), _ in ranked:
                if all(self._color_distance((r, g, b), p) >= 30 for p in picked):
                    picked.append((r, g, b))
                if len(picked) >= count:
                    break

            for r, g, b in picked:
                colors.append(f"#{r:02x}{g:02x}{b:02x}")
        except Exception:
            colors = []

        if not colors:
            colors = ["#4c566a", "#5e81ac", "#88c0d0", "#a3be8c", "#ebcb8b"]

        with self._palette_cache_lock:
            self._palette_cache[key] = colors[:count]
            self._palette_disk_cache[key] = colors[:count]
        self._palette_cache_dirty = True
        self._palette_cache_dirty_count += 1
        self._maybe_flush_palette_cache()
        with self._palette_cache_lock:
            return self._palette_cache[key]

    def _hex_to_rgb(self, color_hex: str):
        value = color_hex.lstrip("#")
        if len(value) != 6:
            return 0.5, 0.5, 0.5
        r = int(value[0:2], 16) / 255.0
        g = int(value[2:4], 16) / 255.0
        b = int(value[4:6], 16) / 255.0
        return r, g, b

    def _rgb_to_hex(self, r: float, g: float, b: float):
        r = max(0, min(255, int(round(r * 255))))
        g = max(0, min(255, int(round(g * 255))))
        b = max(0, min(255, int(round(b * 255))))
        return f"#{r:02x}{g:02x}{b:02x}"

    def mix_hex(self, base_hex: str, target_hex: str, ratio: float):
        ratio = max(0.0, min(1.0, float(ratio)))
        br, bg, bb = self._hex_to_rgb(base_hex)
        tr, tg, tb = self._hex_to_rgb(target_hex)
        rr = br + (tr - br) * ratio
        gg = bg + (tg - bg) * ratio
        bb2 = bb + (tb - bb) * ratio
        return self._rgb_to_hex(rr, gg, bb2)

    def _is_light_hex(self, color_hex: str) -> bool:
        r, g, b = self._hex_to_rgb(color_hex)
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return lum >= 0.56

    def _color_distance(self, a, b):
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)

    def get_similar_colors(self, base_colors):
        result = []
        seeds = base_colors[:5] if base_colors else ["#5e81ac"]
        for color_hex in seeds:
            r, g, b = self._hex_to_rgb(color_hex)
            h, s, v = colorsys.rgb_to_hsv(r, g, b)
            for dh in (0.0, 0.03, -0.03, 0.07, -0.07, 0.12, -0.12):
                nh = (h + dh) % 1.0
                for sat_mul, val_mul in (
                    (1.0, 1.0),
                    (1.1, 1.0),
                    (0.9, 1.1),
                    (1.2, 0.95),
                ):
                    ns = max(0.18, min(1.0, s * sat_mul))
                    nv = max(0.2, min(1.0, v * val_mul))
                    rr, gg, bb = colorsys.hsv_to_rgb(nh, ns, nv)
                    result.append(self._rgb_to_hex(rr, gg, bb))

        return self._unique_colors(result, limit=30)

    def get_color_theory_colors(self, base_colors):
        seeds = self._unique_colors(base_colors, limit=3) or ["#5E81AC"]
        result = []

        for color_hex in seeds:
            r, g, b = self._hex_to_rgb(color_hex)
            h, s, v = colorsys.rgb_to_hsv(r, g, b)

            # Analogous / complement / split-complement / triadic / square
            for deg in (0, 30, -30, 180, 150, -150, 120, -120, 90, -90):
                nh = (h + deg / 360.0) % 1.0
                for sat_mul, val_mul in ((1.0, 1.0), (0.85, 1.08), (1.15, 0.92)):
                    ns = max(0.18, min(1.0, s * sat_mul))
                    nv = max(0.16, min(1.0, v * val_mul))
                    rr, gg, bb = colorsys.hsv_to_rgb(nh, ns, nv)
                    result.append(self._rgb_to_hex(rr, gg, bb))

            # Monochromatic tints/shades
            for vv in (0.28, 0.42, 0.56, 0.70, 0.84, 0.95):
                rr, gg, bb = colorsys.hsv_to_rgb(h, max(0.12, s * 0.75), vv)
                result.append(self._rgb_to_hex(rr, gg, bb))

        return self._unique_colors(result, limit=36)

    def get_recent_colorize_swatches(self):
        section = self.settings.get_section("wallpapers", default={})
        values = section.get("colorize_recent", [])
        if not isinstance(values, list):
            return []
        return self._unique_colors(values, limit=24)

    def record_colorize_swatch(self, color_hex: str):
        normalized = self._unique_colors([color_hex], limit=1)
        if not normalized:
            return
        color = normalized[0]

        section = self.settings.get_section("wallpapers", default={})
        current = section.get("colorize_recent", [])
        if not isinstance(current, list):
            current = []

        merged = [color] + [
            c for c in self._unique_colors(current, limit=64) if c != color
        ]
        section["colorize_recent"] = merged[:36]
        self.settings.save()

    def _random_color(self):
        return f"#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}"

    def get_colorize_strength(self) -> int:
        section = self.settings.get_section("wallpapers", default={})
        raw = section.get("colorize_strength", 65)
        try:
            value = int(raw)
        except Exception:
            value = 65
        return max(10, min(100, value))

    # helper for determining if a path belongs to the colorized variant folder
    def is_colorized_path(self, path: Path) -> bool:
        try:
            return Path(path).resolve().is_relative_to(self.variant_dir.resolve())
        except Exception:
            return "colorized" in str(path).lower()

    def compose_display_name(self, entry, is_colorized: bool | None = None):
        if is_colorized is None:
            is_colorized = self.is_colorized_path(entry.path) or str(
                entry.name
            ).lower().startswith("colorized/")

        base = self.get_display_name(entry.path, Path(entry.name).name)
        if is_colorized and "(colorized)" not in base.lower():
            return f"{base} (Colorized)"
        return base

    def set_colorize_strength(self, value: int):
        section = self.settings.get_section("wallpapers", default={})
        section["colorize_strength"] = max(10, min(100, int(value)))
        self.settings.save()

    def create_colorized_variant(
        self, source_path: Path, color_hex: str, strength: int = 55
    ) -> tuple[Path | None, str | None]:
        src = Path(source_path)
        if not src.exists():
            return None, "Source image not found"

        safe_stem = "".join(ch if ch.isalnum() else "_" for ch in src.stem)[:48]
        digest = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:10]
        color_tag = color_hex.lstrip("#").lower()
        out = self.variant_dir / f"{safe_stem}_{digest}_{color_tag}_{strength}.png"
        if out.exists():
            return out, None

        magick = shutil.which("magick")
        convert = shutil.which("convert")
        cmd = None
        if magick:
            cmd = [
                magick,
                str(src),
                "-fill",
                color_hex,
                "-colorize",
                str(strength),
                str(out),
            ]
        elif convert:
            cmd = [
                convert,
                str(src),
                "-fill",
                color_hex,
                "-colorize",
                str(strength),
                str(out),
            ]
        else:
            return (
                None,
                "ImageMagick is required for colorize (magick/convert not found)",
            )

        try:
            subprocess.run(
                cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return out, None
        except Exception as exc:
            return None, f"Colorize failed: {exc}"

    def list_wallpapers(self) -> list[WallpaperEntry]:
        found: dict[str, WallpaperEntry] = {}
        for folder in self.get_search_dirs():
            for p in folder.rglob("*"):
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                    key = str(p.resolve())
                    rel_name = str(p.relative_to(folder))
                    try:
                        if folder.resolve() == self.colorized_dir.resolve():
                            rel_name = f"colorized/{p.name}"
                    except Exception:
                        pass
                    found[key] = WallpaperEntry(name=rel_name, path=p)
        return sorted(found.values(), key=lambda x: x.name.lower())

    def get_display_name(self, path: Path, fallback: str) -> str:
        return self.name_store.get(path, fallback)

    def set_display_name(self, path: Path, name: str | None) -> str:
        return self.name_store.set(path, name)

    def clear_display_name(self, path: Path) -> None:
        self.name_store.remove(path)

    def _is_system_wallpaper(self, path: Path) -> bool:
        try:
            target = path.resolve()
        except Exception:
            target = path
        for base in self.system_dirs:
            try:
                if target.is_relative_to(base.resolve()):
                    return True
            except Exception:
                continue
        return False

    def _resolve_askpass_binary(self) -> str | None:
        configured = os.environ.get("SUDO_ASKPASS", "").strip()
        if configured:
            p = Path(configured)
            if p.exists() and os.access(str(p), os.X_OK):
                return str(p)

        for candidate in ASKPASS_CANDIDATES:
            p = Path(candidate)
            if p.exists() and os.access(str(p), os.X_OK):
                return str(p)
        return None

    def delete_wallpaper(self, path: Path | str) -> tuple[bool, str]:
        wp = Path(path).expanduser()
        if not wp.exists():
            return False, "Delete failed: file missing."
        if not wp.is_file():
            return False, "Delete failed: target is not a file."

        try:
            wp.unlink()
            return True, f"Deleted: {wp.name}"
        except PermissionError:
            # Fall through to sudo askpass path below.
            pass
        except Exception as exc:
            # For system wallpaper paths we still try sudo fallback.
            if not self._is_system_wallpaper(wp):
                return False, f"Delete failed: {exc}"

        sudo = shutil.which("sudo")
        if not sudo:
            return False, "Delete failed: sudo is not installed."

        askpass = self._resolve_askpass_binary()
        if not askpass:
            return False, "Delete failed: askpass helper not found. Set SUDO_ASKPASS."

        env = dict(os.environ)
        env["SUDO_ASKPASS"] = askpass
        res = subprocess.run(
            [sudo, "-A", "-k", "rm", "-f", "--", str(wp)],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if res.returncode != 0:
            detail = (res.stderr or res.stdout or "").strip()
            if not detail:
                detail = "sudo rm failed."
            return False, f"Delete failed: {detail}"

        if wp.exists():
            return False, "Delete failed: file still exists after sudo rm."
        return True, f"Deleted: {wp.name}"

    def apply_wallpaper(self, path: Path | str) -> tuple[bool, str]:
        wp = Path(path)
        if not wp.exists():
            return False, "Wallpaper file not found."

        nitrogen = shutil.which("nitrogen")
        if not nitrogen:
            return False, "Nitrogen is not installed."

        mode = self.get_fill_mode()
        flag_map = {
            "zoom-fill": "--set-zoom-fill",
            "centered": "--set-centered",
            "scaled": "--set-scaled",
            "tiled": "--set-tiled",
            "auto": "--set-auto",
        }
        flag = flag_map.get(mode, "--set-zoom-fill")

        try:
            subprocess.run([nitrogen, flag, str(wp), "--save"], check=False)
        except Exception as exc:
            return False, f"Failed to run nitrogen: {exc}"

        section = self.get_state()
        section["last_applied"] = str(wp)
        self.settings.save()
        return True, f"Applied: {wp.name}"

    # -------------------------------------------------------
    # Badge CSS generation (originally in main.py)
    # -------------------------------------------------------

    def get_colorized_badge_css(self) -> tuple[str, str]:
        """Return (bg_color, text_color) for colorized badge display.

        Uses the wallpaper section's colorized_badge_color setting and
        calculates appropriate text color based on luminance.
        """
        section = self.settings.get_section("wallpapers", default={})
        raw = str(
            section.get(
                "colorized_tag_color", section.get("colorized_badge_color", "#1482C8")
            )
        ).strip()

        if raw.startswith("#"):
            raw = raw[1:]
        if len(raw) != 6:
            raw = "1482C8"
        try:
            r = int(raw[0:2], 16)
            g = int(raw[2:4], 16)
            b = int(raw[4:6], 16)
        except Exception:
            r, g, b = 20, 130, 200

        # Basic contrast text color based on relative luminance.
        lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        text = "#111111" if lum > 0.62 else "#ffffff"
        bg = f"rgba({r}, {g}, {b}, 0.88)"
        return bg, text
