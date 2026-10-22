#!/usr/bin/env python3
"""Validate distributable image catalog without accessing user state."""
import hashlib
import json
from pathlib import Path
from PIL import Image
root = Path(__file__).resolve().parents[1]
catalog = json.loads((root/'assets/themes/catalog.json').read_text())
for theme in catalog['themes']:
    wallpaper = root/theme['wallpaper']
    assert wallpaper.resolve().is_relative_to(root/'assets/wallpapers')
    assert not wallpaper.is_symlink()
    assert theme['assetLicense'] == 'MIT'
    assert hashlib.sha256(wallpaper.read_bytes()).hexdigest() == theme['sha256']
    with Image.open(wallpaper) as image:
        assert list(image.size) == theme['sourceSize']
    assert (root/theme['thumbnail']).is_file()
assert len({t['wallpaper'] for t in catalog['themes']}) == 3
print(f"Verified {len(catalog['themes'])} palettes and 3 original MIT landscapes")
