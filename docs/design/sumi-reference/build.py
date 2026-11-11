#!/usr/bin/env python3
"""Build a portable offline HTML reference from its reviewable source files."""
import base64
import mimetypes
from pathlib import Path
import re

SOURCE = Path(__file__).resolve().parent
OUTPUT = SOURCE.parent / 'sumi-desktop-reference.html'

def inline_asset(match):
    target = (SOURCE / match.group(1)).resolve()
    media = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
    encoded = base64.b64encode(target.read_bytes()).decode('ascii')
    return f'url("data:{media};base64,{encoded}")'

html = (SOURCE / 'index.html').read_text()
css = (SOURCE / 'shell.css').read_text()
css = re.sub(r"url\(['\"]?([^'\")]+)['\"]?\)", inline_asset, css)
html = html.replace('<link rel="stylesheet" href="shell.css">', f'<style>\n{css}\n</style>')
for name in ('ui', 'device-pages', 'desktop-pages', 'conversation-pages', 'app'):
    script = (SOURCE / (name + '.js')).read_text()
    html = html.replace(f'<script src="{name}.js"></script>', '<script>\n' + script + '\n</script>')
OUTPUT.write_text(html)
print(f'{OUTPUT} ({OUTPUT.stat().st_size:,} bytes)')
