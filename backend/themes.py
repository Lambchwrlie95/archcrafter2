from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from .settings import SettingsStore


@dataclass(frozen=True)
class WindowThemeEntry:
    name: str
    path: Path


class WindowThemeService:
    def __init__(self, base_dir: Path, settings: SettingsStore):
        self.base_dir = Path(base_dir)
        self.settings = settings
        self.system_dirs = [Path("/usr/share/themes")]
        self.user_dirs = [
            Path("~/.themes").expanduser(),
            Path("~/.local/share/themes").expanduser(),
        ]
        self.rc_xml_path = Path("~/.config/openbox/rc.xml").expanduser()

    def list_themes(self) -> list[WindowThemeEntry]:
        found: dict[str, WindowThemeEntry] = {}
        search_paths = [p for p in self.system_dirs + self.user_dirs if p.exists()]

        for folder in search_paths:
            try:
                entries = list(folder.iterdir())
            except Exception:
                continue

            for p in entries:
                if not p.is_dir():
                    continue
                ob_dir = p / "openbox-3"
                if ob_dir.exists() and ob_dir.is_dir():
                    theme_name = p.name
                    # User themes are scanned later and override system themes.
                    found[theme_name] = WindowThemeEntry(name=theme_name, path=p)

        return sorted(found.values(), key=lambda x: x.name.lower())

    def _find_theme_name_node(self, root):
        for node in root.iter():
            if not isinstance(node.tag, str) or not node.tag.endswith("theme"):
                continue
            for child in list(node):
                if isinstance(child.tag, str) and child.tag.endswith("name"):
                    return child
        return None

    def get_current_theme(self) -> str | None:
        if not self.rc_xml_path.exists():
            return None
        try:
            tree = ET.parse(self.rc_xml_path)
            root = tree.getroot()
            name_node = self._find_theme_name_node(root)
            if name_node is not None:
                value = (name_node.text or "").strip()
                return value or None
        except Exception:
            pass
        return None

    def apply_theme(self, theme_name: str) -> tuple[bool, str]:
        if not self.rc_xml_path.exists():
            return False, "Openbox configuration file not found."

        available = {t.name for t in self.list_themes()}
        if theme_name not in available:
            return False, f"Theme not found: {theme_name}"

        try:
            tree = ET.parse(self.rc_xml_path)
            root = tree.getroot()
            name_node = self._find_theme_name_node(root)
            if name_node is None:
                return False, "Could not find <theme><name> in rc.xml"

            name_node.text = theme_name
            tree.write(self.rc_xml_path, encoding="utf-8", xml_declaration=True)

            subprocess.run(["openbox", "--reconfigure"], check=False)
            return True, f"Applied window theme: {theme_name}"
        except Exception as exc:
            return False, f"Failed to apply theme: {exc}"
