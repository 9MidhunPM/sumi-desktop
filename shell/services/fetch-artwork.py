#!/usr/bin/env python3
"""Fetch one remote cover, normalize its decoder format, and print its cache URI."""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

from PIL import Image, ImageOps

MAX_BYTES = 8 * 1024 * 1024


def fetch(url: str, cache: Path) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Unsupported artwork URL')
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = cache / (hashlib.sha256(url.encode()).hexdigest() + '.png')
    if target.is_file():
        try:
            with Image.open(target) as existing:
                existing.verify()
            target.touch()
            return target.as_uri()
        except (OSError, ValueError):
            target.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cover-', dir=cache) as directory:
        download = Path(directory) / 'download'
        result = subprocess.run([
            'curl', '--silent', '--fail', '--location', '--max-redirs', '3',
            '--proto', '=http,https', '--proto-redir', '=http,https',
            '--connect-timeout', '3', '--max-time', '8', '--retry', '1',
            '--retry-all-errors', '--retry-delay', '0', '--max-filesize', str(MAX_BYTES),
            '--output', str(download), '--', url,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        if result.returncode or not download.is_file() or download.stat().st_size > MAX_BYTES:
            raise ValueError('Artwork download failed')
        with Image.open(download) as image:
            if image.width * image.height > 16_777_216:
                raise ValueError('Artwork dimensions exceed the limit')
            image = ImageOps.exif_transpose(image).convert('RGBA')
            image.thumbnail((768, 768))
            normalized = Path(directory) / 'cover.png'
            image.save(normalized, 'PNG')
        normalized.chmod(0o600)
        os.replace(normalized, target)
    # Keep the cache bounded; only normalized covers belong to this directory.
    entries = []
    for item in cache.glob('*.png'):
        try:
            entries.append((item.stat().st_mtime, item))
        except FileNotFoundError:
            pass
    for _, old in sorted(entries, reverse=True)[64:]:
        try:
            old.unlink()
        except FileNotFoundError:
            pass
    return target.as_uri()


if __name__ == '__main__':
    try:
        base = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'sumi' / 'artwork'
        print(fetch(sys.argv[1], base.resolve()))
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        # Do not put URLs or response contents in desktop logs.
        print('Artwork could not be loaded', file=sys.stderr)
        raise SystemExit(1)
