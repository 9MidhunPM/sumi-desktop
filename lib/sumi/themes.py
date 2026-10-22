"""Sumi's data-only theme library and reversible application adapters.

No shell files are executed, and no processes are signalled by this module.
The controller decides when to execute the returned reload commands.
"""
from __future__ import annotations

from .paths import config_path, data_root, managed_path, allowed_path, canonical_path

import colorsys
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import tempfile
from typing import Any

from .statefiles import data_path, file_lock, state_path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "assets/themes/catalog.json"
DEFAULT_THEME_ID = "sunset-shrine"
COLOR_KEYS = (
    "bgPanel", "bgPanelStrong", "bgPlaying", "desktopBackground", "borderSoft",
    "borderStrong", "borderAccent1", "borderAccent2", "textMain", "textSoft",
    "accentBlue", "accentCyan", "accentPink", "accentWarn",
)
BEGIN = "# >>> SUMI THEME START"
END = "# <<< SUMI THEME END"


def parse_assignments(text: str) -> dict[str, str]:
    """Parse literal NAME=value lines without evaluating shell expansions.

    Legacy manifests contain only string assignments. Reject commands rather
    than trying to interpret a subset of executable shell syntax.
    """
    result = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"\s*([A-Z][A-Z0-9_]*)=(.*)", line)
        if not match:
            raise ValueError(f"Expected literal assignment on line {number}")
        key, raw = match.groups()
        if any(token in raw for token in ("$", "`", ";", "\\\n")):
            raise ValueError(f"Shell expansion or command on line {number}")
        values = shlex.split(raw, comments=True, posix=True)
        if len(values) > 1:
            raise ValueError(f"Multiple values on line {number}")
        result[key] = values[0] if values else ""
    return result


def rgba(value: str) -> tuple[int, int, int, int]:
    """Read legacy CSS/Hypr colors; return red, green, blue, alpha bytes."""
    value = value.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}", value):
        return tuple(int(c * 2, 16) for c in value[1:]) + (255,)
    if re.fullmatch(r"#[0-9a-f]{6}", value):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
    if re.fullmatch(r"#[0-9a-f]{8}", value):
        return tuple(int(value[i:i + 2], 16) for i in (3, 5, 7)) + (int(value[1:3], 16),)
    match = re.fullmatch(r"(rgb|rgba)\(([^)]+)\)", value)
    if match:
        kind, inner = match.groups()
        if re.fullmatch(r"[0-9a-f]{6}([0-9a-f]{2})?", inner):
            channels = tuple(int(inner[i:i + 2], 16) for i in (0, 2, 4))
            return channels + (int(inner[6:8], 16) if len(inner) == 8 else 255,)
        parts = [v.strip() for v in inner.split(",")]
        # A few existing generated manifests contain rgba(243,223,183ee).
        if len(parts) == 3 and re.fullmatch(r"\d{1,3}[a-f0-9]{2}", parts[2]) and kind == "rgba":
            parts[2], alpha = parts[2][:-2], int(parts[2][-2:], 16)
        else:
            alpha = round(float(parts[3]) * 255) if len(parts) == 4 else 255
        if len(parts) in (3, 4):
            channels = tuple(int(v) for v in parts[:3])
            if all(0 <= v <= 255 for v in (*channels, alpha)):
                return channels + (alpha,)
    raise ValueError(f"Unsupported color: {value!r}")


def color(value: str) -> str:
    r, g, b, a = rgba(value)
    return f"#{r:02x}{g:02x}{b:02x}" if a == 255 else f"#{a:02x}{r:02x}{g:02x}{b:02x}"


def opaque(value: str) -> str:
    return "#" + "".join(f"{v:02x}" for v in rgba(value)[:3])


def hypr_color(value: str) -> str:
    r, g, b, a = rgba(value)
    return f"rgba({r:02x}{g:02x}{b:02x}{a:02x})"


def contrast(foreground: str, background: str) -> float:
    def luminance(value: str) -> float:
        components = [x / 255 for x in rgba(value)[:3]]
        components = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in components]
        return sum(a * b for a, b in zip(components, (0.2126, 0.7152, 0.0722)))
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _legible(value: str, background: str, minimum: float) -> str:
    if contrast(value, background) >= minimum:
        return value
    rgb = rgba(value)[:3]
    for amount in range(1, 21):
        adjusted = "#" + "".join(f"{round(v + (255 - v) * amount / 20):02x}" for v in rgb)
        if contrast(adjusted, background) >= minimum:
            return adjusted
    return "#ffffff"


def _defaults(identifier: str, name: str, wallpaper: str, thumbnail: str, colors: dict) -> dict:
    return {
        "id": identifier, "name": name, "wallpaper": wallpaper, "thumbnail": thumbnail,
        "colors": colors, "font": "Adwaita Sans", "fontMono": "JetBrainsMono Nerd Font",
        "fontSize": 14, "windowRounding": 16, "borderWidth": 1,
    }


def legacy_theme(identifier: str, text: str, wallpaper: str, thumbnail: str) -> dict:
    values = parse_assignments(text)
    mapping = {
        "bgPanel": "BG_PANEL", "bgPanelStrong": "BG_PANEL_STRONG", "bgPlaying": "BG_PLAYING",
        "borderSoft": "BORDER_SOFT", "borderStrong": "BORDER_STRONG", "textMain": "TEXT_MAIN",
        "textSoft": "TEXT_SOFT", "accentBlue": "ACCENT_BLUE", "accentCyan": "ACCENT_CYAN",
        "accentPink": "ACCENT_PINK", "accentWarn": "ACCENT_WARN",
    }
    colors = {key: color(values[source]) for key, source in mapping.items()}
    for target, fallback in (("borderAccent1", "accentBlue"), ("borderAccent2", "accentPink")):
        source = "HYPR_ACCENT_PRIMARY" if target == "borderAccent1" else "HYPR_ACCENT_SECONDARY"
        try:
            colors[target] = color(values[source])
        except (ValueError, KeyError):
            colors[target] = colors[fallback]
    colors["desktopBackground"] = opaque(colors["bgPanel"])
    colors["textMain"] = _legible(colors["textMain"], colors["bgPanelStrong"], 7)
    colors["textSoft"] = _legible(colors["textSoft"], colors["bgPanelStrong"], 4.5)
    theme = _defaults(identifier, values.get("NAME", identifier), wallpaper, thumbnail, colors)
    theme["legacy"] = {"wallpaper": values.get("WALLPAPER", ""), "manifest": f"assets/themes/legacy/{identifier}.theme"}
    theme["terminal"] = {key.removeprefix("KITTY_").lower(): value for key, value in values.items() if key.startswith("KITTY_")}
    return theme


def _catalog() -> dict:
    data = json.loads(CATALOG.read_text())
    if data.get("version") != 1 or not isinstance(data.get("themes"), list):
        raise ValueError("Unsupported theme catalog")
    return data


def _resolved(theme: dict, *, curated: list[dict] | None = None) -> dict:
    if not isinstance(theme, dict):
        raise ValueError("Theme manifest must be an object")
    theme = copy.deepcopy(theme)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", theme.get("id", "")):
        raise ValueError("Invalid theme ID")
    if not all(key in theme.get("colors", {}) for key in COLOR_KEYS):
        raise ValueError(f"Incomplete palette: {theme['id']}")
    theme["colors"] = {key: color(theme["colors"][key]) for key in COLOR_KEYS}
    for key in ("wallpaper", "thumbnail"):
        path = Path(theme[key])
        theme[key] = str((ROOT / path).resolve() if not path.is_absolute() else path.resolve())
    from .scenes import scene_for_theme
    scene = scene_for_theme(theme, curated=curated)
    theme.update(imageKey=scene["imageKey"], sourceSize=scene["sourceSize"], desktopLayout=scene["layout"])
    return theme


def list_themes(*, state_dir: Path | None = None, data_dir: Path | None = None, home: Path | None = None) -> list[dict]:
    """Merge immutable bundled themes, private imports, and saved user variants."""
    curated = _catalog()["themes"]
    entries = [_resolved(theme, curated=curated) for theme in curated]
    known = {entry["id"] for entry in entries}
    manifests = [(item, item.parent.name) for item in sorted((data_path(data_dir, home=home) / "themes/imported").glob("*/theme.json"))]
    manifests += [(item, item.stem) for item in sorted((state_path(state_dir, home=home) / "themes").glob("*-custom.json"))]
    for manifest, identifier in manifests:
        try:
            entry = _resolved(json.loads(manifest.read_text()), curated=curated)
            if entry["id"] != identifier or entry["id"] in known:
                continue
        except (OSError, ValueError, KeyError, TypeError):
            continue
        entries.append(entry)
        known.add(entry["id"])
    return entries


def get_theme(identifier: str, *, state_dir: Path | None = None, data_dir: Path | None = None, home: Path | None = None) -> dict:
    for theme in list_themes(state_dir=state_dir, data_dir=data_dir, home=home):
        if theme["id"] == identifier:
            return theme
    raise ValueError(f"Unknown theme: {identifier}")


def _atomic_write(path: Path, content: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.sumi-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def import_wallpaper(path: str | Path, *, home: Path | None = None,
                     state_dir: Path | None = None, data_dir: Path | None = None) -> dict:
    """Publish one complete private import; the bundled catalog is never changed."""
    from PIL import Image, ImageOps
    source = Path(path).expanduser().resolve(strict=True)
    if source.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Wallpaper exceeds 100 MiB")
    original = source.read_bytes()
    if len(original) > 100 * 1024 * 1024:
        raise ValueError("Wallpaper exceeds 100 MiB")
    with Image.open(io.BytesIO(original)) as image:
        image.verify()
    digest = hashlib.sha256(original).hexdigest()
    with Image.open(io.BytesIO(original)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        source_size = list(image.size)
        image.thumbnail((256, 256))
        quantized = image.quantize(colors=8)
        palette = quantized.getpalette()
        candidates = []
        for count, index in quantized.getcolors():
            rgb = palette[index * 3:index * 3 + 3]
            hue, lightness, saturation = colorsys.rgb_to_hls(*(v / 255 for v in rgb))
            candidates.append((count * (saturation + .2), hue, saturation))
        _, hue, saturation = max(candidates)
        def derived(lightness: float, shift: float = 0) -> str:
            return "#" + "".join(f"{round(v * 255):02x}" for v in colorsys.hls_to_rgb((hue + shift) % 1, lightness, min(.55, max(.18, saturation))))
        colors = {
            "bgPanel": "#e6" + derived(.07)[1:], "bgPanelStrong": "#f5" + derived(.105)[1:],
            "bgPlaying": derived(.16), "desktopBackground": derived(.045),
            "borderSoft": "#33" + derived(.68)[1:], "borderStrong": "#80" + derived(.72)[1:],
            "borderAccent1": derived(.74), "borderAccent2": derived(.72, .12),
            "textMain": "#f1eee8", "textSoft": "#c8c5c3", "accentBlue": derived(.74),
            "accentCyan": derived(.78, .12), "accentPink": derived(.76, -.12), "accentWarn": "#e7c58d",
        }
    with Image.open(io.BytesIO(original)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((640, 400))
        preview = io.BytesIO()
        image.save(preview, format="JPEG", quality=85)
    data_dir = data_path(data_dir, home=home)
    library = data_dir / "themes/imported"
    with file_lock(data_dir / "themes/import.lock"):
        entries = list_themes(home=home, state_dir=state_dir, data_dir=data_dir)
        for entry in entries:
            if entry.get("sha256") == digest:
                return entry
        slug = re.sub(r"[^a-z0-9]+", "-", source.stem.lower()).strip("-")[:55] or "wallpaper"
        identifiers = {entry["id"] for entry in entries}
        identifier = slug
        suffix_number = 0
        while identifier in identifiers or (library / identifier).exists():
            identifier = f"{slug}-{digest[:12]}" + (f"-{suffix_number}" if suffix_number else "")
            suffix_number += 1
        suffix = source.suffix.lower() if source.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") else ".img"
        published = library / identifier
        wallpaper_name = "wallpaper" + suffix
        theme = _defaults(identifier, source.stem.replace("-", " ").replace("_", " ").title(),
                          str(published / wallpaper_name), str(published / "thumbnail.jpg"), colors)
        from .scenes import DEFAULT_LAYOUT
        theme.update(sha256=digest, imageKey=digest, sourceName=source.name, generated=True,
                     sourceSize=source_size, desktopLayout=copy.deepcopy(DEFAULT_LAYOUT))
        library.mkdir(parents=True, exist_ok=True, mode=0o700)
        staged = Path(tempfile.mkdtemp(prefix=".import-", dir=library))
        did_publish = False
        try:
            _atomic_write(staged / wallpaper_name, original)
            _atomic_write(staged / "thumbnail.jpg", preview.getvalue())
            _atomic_write(staged / "theme.json", (json.dumps(theme, indent=2) + "\n").encode())
            os.replace(staged, published)
            did_publish = True
            directory = os.open(library, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except BaseException:
            if did_publish:
                shutil.rmtree(published)
            raise
        finally:
            shutil.rmtree(staged, ignore_errors=True)
        return _resolved(theme)


def _managed(text: str, body: str, begin: str = BEGIN, end: str = END, *, prepend: bool = False) -> str:
    block = f"{begin}\n{body.rstrip()}\n{end}"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
    if begin in text or end in text:
        if text.count(begin) != 1 or text.count(end) != 1 or not pattern.search(text):
            raise ValueError("Unbalanced Sumi managed markers")
        if prepend:
            remainder = pattern.sub("", text).lstrip()
            return block + "\n\n" + remainder.rstrip() + ("\n" if remainder else "")
        return pattern.sub(lambda _: block, text).rstrip() + "\n"
    if prepend:
        return block + "\n\n" + text.rstrip() + ("\n" if text else "")
    return text.rstrip() + ("\n\n" if text.strip() else "") + block + "\n"


def _ini_keys(text: str, section: str, updates: dict[str, str]) -> str:
    """Update selected keys without reserializing comments or unrelated sections."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == f"[{section}]"), None)
    if start is None:
        if lines and lines[-1]:
            lines.append("")
        lines.extend([f"[{section}]"] + [f"{key}={value}" for key, value in updates.items()])
        return "\n".join(lines) + "\n"
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
    pending = dict(updates)
    for i in range(start + 1, end):
        match = re.match(r"\s*([^#;=]+?)\s*=", lines[i])
        if match and match.group(1) in updates:
            key = match.group(1)
            lines[i] = f"{key}={updates[key]}"
            pending.pop(key, None)
    lines[end:end] = [f"{key}={value}" for key, value in pending.items()]
    return "\n".join(lines) + "\n"


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _jsonc_clean(text: str) -> str:
    """Replace JSONC comments/trailing commas with spaces, preserving offsets."""
    chars = list(text)
    if chars and chars[0] == "\ufeff":
        chars[0] = " "
    index = 0
    while index < len(chars):
        if chars[index] == '"':
            index += 1
            while index < len(chars):
                if chars[index] == "\\":
                    index += 2
                elif chars[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
        elif chars[index:index + 2] == ["/", "/"]:
            while index < len(chars) and chars[index] not in "\r\n":
                chars[index] = " "
                index += 1
        elif chars[index:index + 2] == ["/", "*"]:
            end = text.find("*/", index + 2)
            if end < 0:
                raise ValueError("Unterminated JSONC comment")
            for position in range(index, end + 2):
                if chars[position] not in "\r\n":
                    chars[position] = " "
            index = end + 2
        else:
            index += 1
    index = 0
    while index < len(chars):
        if chars[index] == '"':
            index += 1
            while index < len(chars):
                if chars[index] == "\\":
                    index += 2
                elif chars[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
        elif chars[index] == ",":
            following = index + 1
            while following < len(chars) and chars[following].isspace():
                following += 1
            if following < len(chars) and chars[following] in "}]":
                chars[index] = " "
            index += 1
        else:
            index += 1
    return "".join(chars)


def _jsonc_properties(text: str) -> tuple[int, dict[str, tuple[int, int]]]:
    cleaned = _jsonc_clean(text)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSONC object")
    decoder = json.JSONDecoder()
    opening = cleaned.index("{")
    index = opening + 1
    properties = {}
    while index < len(cleaned):
        while index < len(cleaned) and (cleaned[index].isspace() or cleaned[index] == ","):
            index += 1
        if cleaned[index] == "}":
            break
        key, index = decoder.raw_decode(cleaned, index)
        while cleaned[index].isspace():
            index += 1
        if cleaned[index] != ":":
            raise ValueError("Expected JSONC property colon")
        index += 1
        while cleaned[index].isspace():
            index += 1
        start = index
        _, index = decoder.raw_decode(cleaned, index)
        properties[key] = (start, index)
    return opening, properties


def merge_jsonc(text: str, updates: dict) -> str:
    """Merge selected object keys by source offsets, preserving all other text."""
    opening, properties = _jsonc_properties(text)
    edits = []
    missing = {}
    for key, value in updates.items():
        if key not in properties:
            missing[key] = value
            continue
        start, end = properties[key]
        if isinstance(value, dict):
            replacement = merge_jsonc(text[start:end], value)
        else:
            replacement = json.dumps(value, ensure_ascii=False)
        edits.append((start, end, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    if missing:
        added = ",\n".join("  " + json.dumps(key) + ": " + json.dumps(value, ensure_ascii=False, indent=2).replace("\n", "\n  ") for key, value in missing.items())
        text = text[:opening + 1] + "\n" + added + ("," if properties else "") + "\n" + text[opening + 1:]
    # Validate the result before it becomes a transaction candidate.
    json.loads(_jsonc_clean(text))
    return text


def _gtk_css(colors: dict) -> str:
    background = opaque(colors["bgPanelStrong"])
    base = opaque(colors["bgPanel"])
    foreground = opaque(colors["textMain"])
    muted = opaque(colors["textSoft"])
    accent = opaque(colors["accentBlue"])
    # User accent overrides may be dark or bright. Selected text must remain
    # readable on either without restricting the user's chosen accent.
    selected_text = max((base, foreground, "#000000", "#ffffff"),
                        key=lambda candidate: contrast(candidate, accent))
    border_red, border_green, border_blue, border_alpha = rgba(colors["borderSoft"])
    border = f"rgba({border_red}, {border_green}, {border_blue}, {border_alpha / 255:.3f})"
    aliases = {
        "accent_color": accent, "accent_bg_color": accent, "accent_fg_color": selected_text,
        "window_bg_color": background, "window_fg_color": foreground,
        "headerbar_bg_color": base, "headerbar_fg_color": foreground,
        "popover_bg_color": background, "popover_fg_color": foreground,
        "view_bg_color": base, "view_fg_color": foreground,
        "card_bg_color": opaque(colors["bgPlaying"]), "card_fg_color": foreground,
        "sidebar_bg_color": base, "sidebar_fg_color": muted,
        "sidebar_border_color": border, "sidebar_backdrop_color": base,
        "theme_bg_color": background, "theme_fg_color": foreground,
        "theme_base_color": base, "theme_text_color": foreground,
        "theme_selected_bg_color": accent, "theme_selected_fg_color": selected_text,
        "theme_unfocused_bg_color": background, "theme_unfocused_fg_color": muted,
        "theme_unfocused_base_color": base, "theme_unfocused_text_color": muted,
        "theme_unfocused_selected_bg_color": accent, "theme_unfocused_selected_fg_color": selected_text,
        "insensitive_bg_color": background, "insensitive_fg_color": muted,
        "insensitive_base_color": base, "borders": border, "unfocused_borders": border,
    }
    definitions = "\n".join(f"@define-color {name} {value};" for name, value in aliases.items())
    return "/* Sumi generated GTK3 palette. Classic styles are kept in the profile snapshot. */\n" + definitions + "\n\n" + """
window, .background { background-color: @window_bg_color; color: @window_fg_color; }
headerbar, headerbar:backdrop { background-image: none; background-color: @headerbar_bg_color; color: @headerbar_fg_color; box-shadow: none; }
popover, popover.background, menu, .menu { background-color: @popover_bg_color; color: @popover_fg_color; }
.view, textview text, treeview.view, iconview.view { background-color: @view_bg_color; color: @view_fg_color; }
entry { background-color: @view_bg_color; color: @view_fg_color; border-color: @borders; }
entry:focus, button:focus { border-color: @accent_color; }
selection, *:selected, .view:selected, .view:selected:focus, treeview.view:selected, iconview.view:selected {
    background-color: @theme_selected_bg_color;
    color: @theme_selected_fg_color;
}
button.suggested-action { background-image: none; background-color: @accent_bg_color; color: @accent_fg_color; }
.sidebar, .sidebar .view { background-color: @sidebar_bg_color; color: @sidebar_fg_color; }
.sidebar .view:selected { background-color: @accent_bg_color; color: @accent_fg_color; }
scrollbar slider { background-color: alpha(@window_fg_color, 0.24); }

/* Thunar keeps its native Adwaita layout, with Sumi surfaces and clear selection. */
.thunar.background { background-color: @window_bg_color; color: @window_fg_color; }
.thunar toolbar, .thunar headerbar, .thunar .location-bar {
    background-image: none;
    background-color: @headerbar_bg_color;
    color: @headerbar_fg_color;
    border-color: @borders;
}
.thunar .standard-view, .thunar .standard-view .view {
    background-color: @view_bg_color;
    color: @view_fg_color;
}
.thunar .sidebar .view { background-color: @sidebar_bg_color; color: @sidebar_fg_color; }
.thunar .view:selected, .thunar .view:selected:focus, .thunar .sidebar .view:selected {
    background-color: @accent_bg_color;
    color: @accent_fg_color;
}
.thunar .rubberband { background-color: alpha(@accent_bg_color, 0.20); border: 1px solid @accent_color; }
.thunar .path-bar-button:checked { background-image: none; background-color: @accent_bg_color; color: @accent_fg_color; }
.thunar statusbar { background-color: @window_bg_color; color: @sidebar_fg_color; }
"""


def _ghostty(theme: dict) -> str:
    c = theme["colors"]
    terminal = theme.get("terminal", {})
    lines = ["# Sumi generated palette", f"font-family = {theme['fontMono']}", "font-size = 12",
             "window-padding-x = 16", "window-padding-y = 14", "background-opacity = 0.96",
             "quit-after-last-window-closed = true", "quit-after-last-window-closed-delay = 0s"]
    base = {"background": opaque(c["bgPanel"]), "foreground": c["textMain"],
            "cursor-color": c["accentCyan"], "cursor-text": opaque(c["bgPanel"]),
            "selection-background": c["accentBlue"], "selection-foreground": opaque(c["bgPanel"])}
    for key, value in base.items():
        lines.append(f"{key} = {value}")
    palette = [opaque(c["bgPanel"]), "#e59a9a", "#a6c8ad", c["accentWarn"], c["accentBlue"],
               c["accentPink"], c["accentCyan"], c["textSoft"], "#606575", "#efb0b0", "#c2debd",
               "#eed7a8", c["accentBlue"], c["accentPink"], c["accentCyan"], c["textMain"]]
    for index, fallback in enumerate(palette):
        lines.append(f"palette = {index}={terminal.get(f'color{index}', fallback)}")
    return "\n".join(lines) + "\n"


def _kitty(theme: dict) -> str:
    """Use the same palette while leaving Kitty's user-tuned behavior intact."""
    colors = theme["colors"]
    lines = ["# Sumi generated palette",
             f"background {opaque(colors['bgPanel'])}", f"foreground {colors['textMain']}",
             f"cursor {colors['accentCyan']}", f"cursor_text_color {opaque(colors['bgPanel'])}",
             f"selection_background {colors['accentBlue']}", f"selection_foreground {opaque(colors['bgPanel'])}",
             f"active_tab_background {colors['accentBlue']}", f"active_tab_foreground {opaque(colors['bgPanel'])}",
             f"inactive_tab_background {opaque(colors['bgPanelStrong'])}", f"inactive_tab_foreground {colors['textSoft']}",
             f"tab_bar_background {opaque(colors['bgPanel'])}", f"active_border_color {colors['accentBlue']}"]
    for line in _ghostty(theme).splitlines():
        if line.startswith("palette = "):
            index, value = line.removeprefix("palette = ").split("=", 1)
            lines.append(f"color{index} {value}")
    return "\n".join(lines) + "\n"


def _normalize_hyprlock_auth(original: str) -> str:
    """Migrate only the known obsolete general:auth:pam_module block.

    Hyprlock 0.9.6 reads auth:pam:module. The legacy spelling is ignored by
    Hyprlock, so keep the intended service name while using its supported
    location. Unrelated general settings and modern auth sections stay intact.
    """
    stack = []
    migrations = []
    has_modern_auth = False
    offset = 0
    for line in original.splitlines(keepends=True):
        structural = line.split("#", 1)[0].strip()
        category = re.fullmatch(r"([a-zA-Z_-]+)\s*\{", structural)
        if category:
            name = category.group(1)
            if not stack and name == "auth":
                has_modern_auth = True
            stack.append((name, offset, offset + len(line)))
        elif structural == "}" and stack:
            name, start, body_start = stack.pop()
            if name == "auth" and [item[0] for item in stack] == ["general"]:
                body = original[body_start:offset]
                settings = [entry for entry in body.splitlines() if entry.strip() and not entry.lstrip().startswith("#")]
                if len(settings) == 1:
                    match = re.fullmatch(r"\s*pam_module\s*=\s*([^#\r\n]+?)(?:\s*#[^\r\n]*)?\s*", settings[0])
                    if match:
                        migrations.append((start, offset + len(line), match.group(1).strip()))
        offset += len(line)
    if not migrations:
        return original
    modules = {value for _, _, value in migrations}
    if len(modules) != 1:
        raise ValueError("Hyprlock has conflicting legacy PAM module settings")
    for start, end, _ in reversed(migrations):
        original = original[:start] + original[end:]
    if not has_modern_auth:
        module = migrations[0][2]
        original = original.rstrip() + f"\n\nauth {{\n    pam {{\n        module = {module}\n    }}\n}}\n"
    return original


def _hyprlock(original: str, theme: dict, generated: Path) -> tuple[str, str]:
    """Restyle visuals and preserve the PAM policy in supported config syntax."""
    c = theme["colors"]
    variables = "\n".join([
        "# Sumi generated visual variables; authentication remains in hyprlock.conf",
        f"$sumi_wallpaper = {theme['wallpaper']}", f"$sumi_main = {hypr_color(c['textMain'])}",
        f"$sumi_soft = {hypr_color(c['textSoft'])}", f"$sumi_accent = {hypr_color(c['accentBlue'])}",
        f"$sumi_panel = {hypr_color(c['bgPanelStrong'])}", f"$sumi_font = {theme['font']}", "",
    ])
    if not original:
        original = (ROOT / "templates/hyprlock.conf").read_text()
    original = _normalize_hyprlock_auth(original)
    # Prepend variables so every subsequent section can reference them.
    original = re.sub(r"# >>> SUMI LOCK START.*?# <<< SUMI LOCK END\s*", "", original, flags=re.S)
    header = f"# >>> SUMI LOCK START\nsource = {generated}\n# <<< SUMI LOCK END\n\n"
    lines, block, depth = [], None, 0
    for line in original.splitlines():
        stripped = line.strip()
        match = re.match(r"(background|label|input-field|shape)\s*\{", stripped)
        if depth == 0 and match:
            block = match.group(1)
        if block and re.match(r"\s*[a-z_]+\s*=", line):
            key = line.split("=", 1)[0].strip()
            replacement = None
            if key == "path" and block == "background":
                replacement = "$sumi_wallpaper"
            elif key in ("font_family",):
                replacement = "$sumi_font"
            elif key in ("font_color",) or (key == "color" and block == "label"):
                replacement = "$sumi_main" if block == "input-field" else "$sumi_soft"
            elif key in ("outer_color", "border_color", "check_color"):
                replacement = "$sumi_accent"
            elif key in ("inner_color",) or (key == "color" and block in ("shape", "background")):
                replacement = "$sumi_panel"
            if replacement:
                line = line.split("=", 1)[0] + "= " + replacement
            # Clock needs minute cadence; the old 500 ms face animation is static text.
            line = line.replace("cmd[update:1000]", "cmd[update:60000]")
            if ("echo" in line and "scanning face" in line) or "Face unlock · type your password to continue" in line:
                line = "    text = Unlock your session · enter your password"
            if key == "placeholder_text" and "face id · type to use pin" in line.lower():
                line = "    placeholder_text = Enter your password"
        lines.append(line)
        # Only count structural braces, never shell snippets embedded in text.
        if stripped.endswith("{"):
            depth += 1
        elif stripped == "}":
            depth -= 1
            if depth == 0:
                block = None
    return header + "\n".join(lines).strip() + "\n", variables


def _qt_scheme(colors: dict) -> str:
    rgb = lambda value: ",".join(str(v) for v in rgba(value)[:3])
    blocks = []
    for group in ("View", "Window", "Button", "Tooltip", "Complementary", "Selection"):
        selected = group == "Selection"
        blocks.append(f"[Colors:{group}]\nBackgroundNormal={rgb(colors['accentBlue'] if selected else colors['bgPanelStrong'])}\n"
                      f"BackgroundAlternate={rgb(colors['bgPlaying'])}\nForegroundNormal={rgb(colors['bgPanel'] if selected else colors['textMain'])}\n"
                      f"ForegroundInactive={rgb(colors['textSoft'])}\nDecorationFocus={rgb(colors['accentBlue'])}\n"
                      f"DecorationHover={rgb(colors['accentCyan'])}\n")
    return "\n".join(blocks) + "\n[General]\nName=Sumi\nColorScheme=Sumi\n"


def _qt6ct_scheme(colors: dict) -> str:
    # QPalette::ColorRole order, 21 entries; disabled text remains distinguishable.
    c = {key: opaque(value) for key, value in colors.items()}
    roles = [c['textMain'], c['bgPanelStrong'], c['borderStrong'], c['borderSoft'], c['bgPanel'],
             c['bgPlaying'], c['textMain'], c['textMain'], c['bgPanel'], c['bgPanelStrong'],
             c['bgPanelStrong'], '#000000', c['accentBlue'], c['bgPanel'], c['accentCyan'],
             c['accentPink'], c['bgPlaying'], c['textSoft'], c['bgPanelStrong'], c['textMain'], c['textSoft']]
    normal = ', '.join(roles)
    disabled = list(roles)
    for index in (0, 6, 7, 19):
        disabled[index] = c['textSoft']
    return f"[ColorScheme]\nactive_colors={normal}\ninactive_colors={normal}\ndisabled_colors={', '.join(disabled)}\n"


def render_theme(theme: dict, *, home: Path, state_dir: Path) -> tuple[dict[Path, str], list[str]]:
    """Prepare all text files in memory; caller can review or transact the result."""
    home, state_dir = Path(home).resolve(), Path(state_dir).resolve()
    generated = config_path(home) / "sumi/generated"
    c = theme["colors"]
    files: dict[Path, str] = {}
    warnings = ["GTK4 applications follow their supported dark/accent preferences; reopening some applications may be required."]
    ghostty = config_path(home) / "ghostty/config.ghostty"
    if not ghostty.exists() and (config_path(home) / "ghostty/config").exists():
        ghostty = config_path(home) / "ghostty/config"
    files[generated / "ghostty.conf"] = _ghostty(theme)
    files[ghostty] = _managed(_read(ghostty), f"config-file = {generated / 'ghostty.conf'}")
    files[generated / "kitty.conf"] = _kitty(theme)
    kitty = config_path(home) / "kitty/kitty.conf"
    files[kitty] = _managed(_read(kitty), f"include {generated / 'kitty.conf'}\nauto_reload_config 0.1")
    files[generated / "gtk3.css"] = _gtk_css(c)
    gtk = config_path(home) / "gtk-3.0/gtk.css"
    # Sumi owns the stylesheet for its profile. Appending legacy definitions or
    # importing the old Thunar rules would override the selected palette. The
    # profile controller retains that original CSS in the Classic snapshot.
    files[gtk] = _managed("", f'@import url("{generated / "gtk3.css"}");', "/* >>> SUMI THEME START */", "/* <<< SUMI THEME END */")
    for version in ("3.0", "4.0"):
        settings = config_path(home) / f"gtk-{version}/settings.ini"
        files[settings] = _ini_keys(_read(settings), "Settings", {
            "gtk-application-prefer-dark-theme": "1", "gtk-font-name": "Adwaita Sans 10",
            **({"gtk-theme-name": "Adwaita-dark"} if version == "3.0" else {}),
        })
    lua = "return {\n" + "".join(f'  {key} = {json.dumps(value)},\n' for key, value in {
        "font_ui": theme['font'], "accent_primary": hypr_color(c['borderAccent1']),
        "accent_secondary": hypr_color(c['borderAccent2']), "accent_warn": hypr_color(c['accentWarn']),
        "bg_shadow": hypr_color(c['desktopBackground']),
    }.items()) + f"  window_rounding = {theme['windowRounding']},\n}}\n"
    files[generated / "hyprland.lua"] = lua
    hypr_theme = config_path(home) / "hypr/config/theme.lua"
    if hypr_theme.exists():
        text = _read(hypr_theme)
        text = re.sub(r"-- >>> SUMI THEME START.*?-- <<< SUMI THEME END\s*", "", text, flags=re.S)
        override = f'-- >>> SUMI THEME START\nfor key, value in pairs(dofile({json.dumps(str(generated / "hyprland.lua"))})) do M[key] = value end\n-- <<< SUMI THEME END\n'
        if re.search(r"\breturn\s+M\s*$", text):
            files[hypr_theme] = re.sub(r"\breturn\s+M\s*$", lambda _: override + "\nreturn M\n", text)
        else:
            warnings.append("Hyprland theme.lua has an unfamiliar layout; generated palette is available but was not included.")
    lock = config_path(home) / "hypr/hyprlock.conf"
    files[lock], files[generated / "hyprlock.conf"] = _hyprlock(_read(lock), theme, generated / "hyprlock.conf")
    files[data_root(home) / "color-schemes/Sumi.colors"] = _qt_scheme(c)
    kde = config_path(home) / "kdeglobals"
    files[kde] = _ini_keys(_read(kde), "General", {"ColorScheme": "Sumi"})
    # KDE uses inline Colors groups when present; update those managed keys too.
    for group in ("View", "Window", "Button", "Tooltip", "Complementary", "Selection"):
        values = {
            "BackgroundNormal": ",".join(str(v) for v in rgba(c['accentBlue'] if group == 'Selection' else c['bgPanelStrong'])[:3]),
            "ForegroundNormal": ",".join(str(v) for v in rgba(c['bgPanel'] if group == 'Selection' else c['textMain'])[:3]),
            "DecorationFocus": ",".join(str(v) for v in rgba(c['accentBlue'])[:3]),
        }
        files[kde] = _ini_keys(files[kde], f"Colors:{group}", values)
    files[config_path(home) / "qt6ct/colors/Sumi.conf"] = _qt6ct_scheme(c)
    qt = config_path(home) / "qt6ct/qt6ct.conf"
    files[qt] = _ini_keys(_read(qt), "Appearance", {"custom_palette": "true", "color_scheme_path": str(config_path(home) / "qt6ct/colors/Sumi.conf")})
    editor_colors = {"workbench.colorCustomizations": {
        "editor.background": opaque(c['bgPanel']), "editor.foreground": c['textMain'],
        "sideBar.background": opaque(c['bgPanelStrong']), "sideBar.foreground": c['textSoft'],
        "statusBar.background": opaque(c['bgPlaying']), "statusBar.foreground": c['textMain'],
        "focusBorder": opaque(c['accentBlue']), "editorCursor.foreground": opaque(c['accentCyan']),
    }}
    files[generated / "editor-colors.json"] = json.dumps(editor_colors, indent=2) + "\n"
    for app in ("Antigravity IDE", "Antigravity", "Code"):
        settings = config_path(home) / app / "User/settings.json"
        if settings.exists():
            try:
                files[settings] = merge_jsonc(_read(settings), editor_colors)
            except (ValueError, TypeError):
                warnings.append(f"{app} settings contain unsupported JSONC; use generated/editor-colors.json to import the palette.")
    files[generated / "nvim-colors.lua"] = "\n".join([
        '-- Load with :luafile ~/.config/sumi/generated/nvim-colors.lua',
        f'vim.api.nvim_set_hl(0, "Normal", {{ fg = "{c["textMain"]}", bg = "{opaque(c["bgPanel"])}" }})',
        f'vim.api.nvim_set_hl(0, "NormalFloat", {{ fg = "{c["textMain"]}", bg = "{opaque(c["bgPanelStrong"])}" }})',
        f'vim.api.nvim_set_hl(0, "FloatBorder", {{ fg = "{opaque(c["accentBlue"])}", bg = "{opaque(c["bgPanelStrong"])}" }})', '',
    ])
    init_lua = config_path(home) / "nvim/init.lua"
    init_vim = config_path(home) / "nvim/init.vim"
    if init_lua.exists():
        text = _read(init_lua)
        if re.search(r"^\s*return\b", text, re.M):
            warnings.append("Neovim init.lua contains a return statement; import generated/nvim-colors.lua manually.")
        else:
            body = f'local sumi_colors = {json.dumps(str(generated / "nvim-colors.lua"))}\npcall(dofile, sumi_colors)\nvim.api.nvim_create_autocmd("ColorScheme", {{ group = vim.api.nvim_create_augroup("SumiColors", {{ clear = true }}), callback = function() pcall(dofile, sumi_colors) end }})'
            files[init_lua] = _managed(text, body, "-- >>> SUMI THEME START", "-- <<< SUMI THEME END")
    elif init_vim.exists():
        body = f'luafile {generated / "nvim-colors.lua"}'
        files[init_vim] = _managed(_read(init_vim), body, '" >>> SUMI THEME START', '" <<< SUMI THEME END')
    runtime = {key: theme[key] for key in ("id", "name", "wallpaper", "thumbnail", "colors", "font", "fontMono", "fontSize", "windowRounding", "borderWidth")}
    from .scenes import scene_for_theme
    scene = scene_for_theme(theme)
    runtime.update(imageKey=scene["imageKey"], sourceSize=scene["sourceSize"], desktopLayout=scene["layout"])
    files[state_dir / "theme.json"] = json.dumps(runtime, indent=2) + "\n"
    return files, warnings


def _apply_resolved(theme: dict, *, home: Path, state_dir: Path, dry_run: bool, extra_files: dict[Path, str] | None = None) -> dict:
    if not Path(theme["wallpaper"]).is_file():
        raise FileNotFoundError(theme["wallpaper"])
    home, state_dir = Path(home).resolve(), Path(state_dir).resolve()
    files, warnings = render_theme(theme, home=home, state_dir=state_dir)
    files = {**(extra_files or {}), **files}
    changes, snapshots = [], []
    for logical, content in files.items():
        actual = logical.resolve()
        if not (allowed_path(home, actual) or actual.is_relative_to(state_dir)):
            raise ValueError(f"Config symlink points outside the requested home: {logical}")
        old = actual.read_bytes() if actual.exists() else None
        encoded = content.encode()
        changes.append({"path": str(logical), "target": str(actual), "status": "unchanged" if old == encoded else "planned" if dry_run else "written"})
        if old != encoded:
            mode = stat.S_IMODE(actual.stat().st_mode) if actual.exists() else 0o600
            snapshots.append((actual, old, mode, encoded))
    report = {
        "theme": theme, "dry_run": dry_run, "changed": changes, "warnings": warnings,
        "reload_commands": [["hyprctl", "reload"], ["systemctl", "--user", "reload", "app-com.mitchellh.ghostty.service"]],
        "wallpaper": theme["wallpaper"],
    }
    if dry_run:
        return report
    completed = []
    try:
        for path, old, mode, encoded in snapshots:
            _atomic_write(path, encoded, mode)
            completed.append((path, old, mode))
    except Exception:
        failures = []
        for path, old, mode in reversed(completed):
            try:
                if old is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_write(path, old, mode)
            except Exception as error:
                failures.append(f"{path}: {error}")
        if failures:
            raise RuntimeError("Theme transaction failed; rollback needs attention: " + "; ".join(failures))
        raise
    return report


def apply_theme(theme_id: str, *, home: Path, state_dir: Path, dry_run: bool = False) -> dict:
    """Render a theme with byte-preserving rollback on any write failure.

    Files are fully prepared before the first write. The runtime theme is written
    last so shell watchers see only complete transactions. Reloads are returned,
    never executed here, and should run after the controller snapshots profiles.
    """
    theme = get_theme(theme_id, state_dir=state_dir, home=home)
    return _apply_resolved(theme, home=home, state_dir=state_dir, dry_run=dry_run)


def apply_custom_accent(theme_id: str, accent_hex: str, *, home: Path, state_dir: Path, dry_run: bool = False) -> dict:
    """Persist and apply a personal primary-accent variant in one transaction.

    Base catalog themes are immutable. Re-editing a custom variant replaces that
    variant, and it remains selectable after restarting the shell.
    """
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent_hex):
        raise ValueError("Accent must be a color in #RRGGBB form")
    theme = get_theme(theme_id, state_dir=state_dir, home=home)
    base_id = theme.get("custom", {}).get("baseThemeId", theme["id"])
    base = get_theme(base_id, state_dir=state_dir, home=home)
    variant = copy.deepcopy(theme)
    variant.update(id=f"{base_id}-custom", name=f"{base['name']} · Custom")
    variant["colors"]["accentBlue"] = accent_hex.lower()
    variant["colors"]["borderAccent1"] = accent_hex.lower()
    variant["custom"] = {"baseThemeId": base_id, "accent": accent_hex.lower()}
    manifest = Path(state_dir).resolve() / "themes" / f"{variant['id']}.json"
    return _apply_resolved(variant, home=home, state_dir=state_dir, dry_run=dry_run,
                           extra_files={manifest: json.dumps(variant, indent=2) + "\n"})


customize_theme = apply_custom_accent
