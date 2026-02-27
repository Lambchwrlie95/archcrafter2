from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .settings import SettingsStore
from .wallpaper_names import WallpaperNameStore

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
FILL_MODES = ["zoom-fill", "centered", "scaled", "tiled", "auto"]
SORT_MODES = ["name_asc", "name_desc", "newest", "oldest"]
THUMB_SIZE_MIN = 180
THUMB_SIZE_MAX = 420
THUMB_SIZE_DEFAULT = 280
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
        self._import_legacy_colorized_variants()
        self.name_store = WallpaperNameStore(settings)
        self._ensure_defaults()

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
