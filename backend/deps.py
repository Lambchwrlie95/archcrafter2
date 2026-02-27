from __future__ import annotations

import shutil


def detect_external_tools() -> dict[str, str | None]:
    magick = shutil.which("magick")
    if not magick:
        magick = shutil.which("convert")

    return {
        "nitrogen": shutil.which("nitrogen"),
        "magick_or_convert": magick,
        "gsettings": shutil.which("gsettings"),
        "openbox": shutil.which("openbox"),
    }
