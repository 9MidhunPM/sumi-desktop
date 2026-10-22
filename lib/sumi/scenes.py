"""Small, data-only wallpaper scenes for the desktop widgets.

Anchors are top-left points in the original image, normalized to [0, 1]. The
shell maps them through the wallpaper's centered cover crop, then fits cards to
the available screen. Curated art is never analyzed at runtime.
"""
from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
import re


WIDGETS = ("clock", "spotify", "priorities", "deadline")
MAX_IMAGE_DIMENSION = 100_000
DEFAULT_LAYOUT = {
    "mode": "left", "compact": True,
    "anchors": {
        "clock": [0.06, 0.20], "spotify": [0.06, 0.39],
        "priorities": [0.06, 0.59], "deadline": [0.06, 0.79],
    },
}


def valid_layout(value: object) -> bool:
    if (not isinstance(value, dict) or not isinstance(value.get("mode"), str)
            or value["mode"] not in {"left", "right", "split"}):
        return False
    if not isinstance(value.get("compact"), bool) or not isinstance(value.get("anchors"), dict):
        return False
    for name in WIDGETS:
        point = value["anchors"].get(name)
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return False
        if not all(isinstance(coordinate, (int, float)) and not isinstance(coordinate, bool)
                   and 0 <= coordinate <= 1 and math.isfinite(coordinate) for coordinate in point):
            return False
    return True


def _valid_size(value: object) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(side, int) and not isinstance(side, bool)
                    and 0 < side <= MAX_IMAGE_DIMENSION for side in value))


def scene_for_theme(theme: dict, *, curated: list[dict] | None = None) -> dict:
    """Build a scene without writes, commands, or image-content analysis.

    Resolved themes normally already contain every field. Older custom variants
    inherit curated geometry by image hash. Unknown images receive a conservative
    compact left layout; reading an image header for its dimensions is sufficient.
    """
    wallpaper = Path(theme["wallpaper"]).expanduser().resolve()
    image_key = theme.get("sha256") or theme.get("imageKey")
    if not isinstance(image_key, str) or not re.fullmatch(r"[0-9a-f]{64}", image_key):
        digest = hashlib.sha256()
        with wallpaper.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        image_key = digest.hexdigest()
    inherited = next((item for item in curated or [] if item.get("sha256") == image_key), {})
    layout = theme.get("desktopLayout")
    if not valid_layout(layout):
        layout = inherited.get("desktopLayout")
    if not valid_layout(layout):
        layout = DEFAULT_LAYOUT
    size = theme.get("sourceSize")
    if not _valid_size(size):
        size = inherited.get("sourceSize")
    if not _valid_size(size):
        from PIL import Image
        with Image.open(wallpaper) as image:
            size = list(image.size)
            if image.getexif().get(274) in {5, 6, 7, 8}:
                size.reverse()
        if not _valid_size(size):
            raise ValueError("Wallpaper dimensions exceed the supported desktop scene size")
    return {
        "version": 1, "imageKey": image_key, "wallpaper": str(wallpaper),
        "sourceSize": list(size), "layout": copy.deepcopy(layout),
    }
