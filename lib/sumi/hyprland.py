"""Generated Hyprland Lua integration; no compositor access during rendering."""
from __future__ import annotations

from .paths import config_path, data_root, managed_path, allowed_path, canonical_path

import ast
import json
from pathlib import Path
import re
import shlex


def migrate_shell_commands(text: str) -> str:
    """Migrate the active legacy commands, retaining surrounding shell sequencing."""
    text = re.sub(r"\bhyprctl\s+dispatch\s+dpms\s+(on|off)\b",
                  lambda m: "hyprctl dispatch 'hl.dsp.dpms({ action = \"" + m[1] + "\" })'", text)
    return re.sub(r"\bhyprctl\s+dispatch\s+exit\b", "hyprctl dispatch 'hl.dsp.exit()'", text)


def migrate_lua_commands(text: str) -> str:
    # Native dispatch tables avoid a shell and another IPC round trip for resize.
    pattern = r'''hl\s*\.\s*dsp\s*\.\s*exec_cmd\s*\(\s*(["'])(hyprctl\s+dispatch\s+resizeactive\s+(-?\d+)\s+(-?\d+))\1\s*\)'''
    return re.sub(pattern, lambda m: f"hl.dsp.window.resize({{ x = {int(m[3])}, y = {int(m[4])}, relative = true }})", text)


def classic_bindings(text: str, executable: str) -> str:
    text = migrate_lua_commands(text)
    literal = r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')'''
    pattern = r"hl\s*\.\s*dsp\s*\.\s*exec_cmd\s*\(\s*" + literal + r"\s*\)"
    def command(match):
        value = ast.literal_eval(match[1])
        if re.fullmatch(r"\s*pkill\s+qs\s*;\s*qs\s*&?\s*", value):
            replacement = shlex.join([executable, "restart"])
        else:
            return match[0]
        return "hl.dsp.exec_cmd(" + json.dumps(replacement) + ")"
    text = re.sub(pattern, command, text)
    return re.sub(r"\blocal\s+quickshellBar\s*=\s*" + literal,
                  lambda m: "local quickshellBar = " + json.dumps(shlex.join([executable, "ipc", "bar"])), text)


def classic_workspace_qml(text: str) -> str:
    pattern = r'''Hyprland\s*\.\s*dispatch\s*\(\s*(["'])workspace \1\s*\+\s*([A-Za-z_]\w*(?:\.\w+)*)\s*\)'''
    return re.sub(pattern, lambda m: 'Hyprland.dispatch("hl.dsp.focus({ workspace = " + ' + m[2] + ' + " })")', text)


def classic_power_qml(text: str, executable: str) -> str:
    pattern = r'''\[\s*(["'])hyprctl\1\s*,\s*(["'])dispatch\2\s*,\s*(["'])exit\3\s*\]'''
    return re.sub(pattern, lambda _: json.dumps([executable, "action", "power", "logout"]), text)


def environment(original: str) -> str:
    marker = "-- >>> SUMI QT PROVIDER START"
    end = "-- <<< SUMI QT PROVIDER END"
    original = re.sub(re.escape(marker) + r".*?" + re.escape(end) + r"\s*", "", original, flags=re.S)
    return original.rstrip() + f'\n\n{marker}\nhl.env("QT_QPA_PLATFORMTHEME", "qt6ct")\n{end}\n'


def motion_include(original: str, home: Path) -> str:
    start, end = "-- >>> SUMI MOTION START", "-- <<< SUMI MOTION END"
    original = re.sub(re.escape(start) + r".*?" + re.escape(end) + r"\s*", "", original, flags=re.S)
    return original.rstrip() + f'\n\n{start}\ndofile({json.dumps(str(config_path(home) / "sumi/generated/motion.lua"))})\n{end}\n'


def motion_lua(mode: str) -> str:
    if mode not in {"normal", "battery", "reduced"}:
        raise ValueError("Unknown motion mode")
    enabled = "false" if mode == "reduced" else "true"
    lines = [f"-- Sumi motion: {mode}. Values are durations in deciseconds.",
             f"hl.config({{ animations = {{ enabled = {enabled} }} }})"]
    # macOS Tahoe-like curves without changing user-owned curve names: a soft
    # settling spring for arrivals, a plain deceleration for glides and fades,
    # and a brisk exit. The original Sumi curves remain defined for user rules.
    for name, points in (("sumiEaseOutQuint", "{ 0.23, 1 }, { 0.32, 1 }"),
                         ("sumiEaseInOutCubic", "{ 0.65, 0.05 }, { 0.36, 1 }"),
                         ("sumiLinear", "{ 0, 0 }, { 1, 1 }"),
                         ("sumiAlmostLinear", "{ 0.5, 0.5 }, { 0.75, 1 }"),
                         ("sumiQuick", "{ 0.15, 0 }, { 0.1, 1 }"),
                         ("sumiTahoe", "{ 0.32, 1.24 }, { 0.58, 1 }"),
                         ("sumiTahoeSmooth", "{ 0.2, 0 }, { 0, 1 }"),
                         ("sumiTahoeExit", "{ 0.3, 0 }, { 0.6, 1 }")):
        lines.append(f'hl.curve("{name}", {{ type = "bezier", points = {{ {points} }} }})')
    # Windows open with a small spring from 90%, close briskly, and Spaces glide
    # without bounce. Battery keeps the same tree, shorter and without overshoot.
    animations = (
        ("global", 8, 5, "default", None, None),
        ("border", 3, 2, "sumiTahoeSmooth", None, None),
        ("windows", 4.2, 2.6, "sumiTahoe", None, None),
        ("windowsIn", 3.8, 2.2, "sumiTahoe", "popin 90%", "popin 94%"),
        ("windowsOut", 1.8, 1.1, "sumiTahoeExit", "popin 92%", "popin 96%"),
        ("fadeIn", 2, 1.2, "sumiTahoeSmooth", None, None),
        ("fadeOut", 1.6, 1, "sumiTahoeExit", None, None),
        ("fade", 2.4, 1.5, "sumiTahoeSmooth", None, None),
        ("layers", 3.2, 2, "sumiTahoe", None, None),
        ("layersIn", 3.2, 2, "sumiTahoe", "fade", "fade"),
        ("layersOut", 1.5, 1, "sumiTahoeExit", "fade", "fade"),
        ("fadeLayersIn", 1.8, 1, "sumiTahoeSmooth", None, None),
        ("fadeLayersOut", 1.4, 0.9, "sumiTahoeExit", None, None),
        ("workspaces", 4.6, 2.8, "sumiTahoeSmooth", "slide", "slide"),
        ("workspacesIn", 4.6, 2.8, "sumiTahoeSmooth", "slide", "slide"),
        ("workspacesOut", 4.6, 2.8, "sumiTahoeSmooth", "slide", "slide"),
        ("specialWorkspace", 4.2, 2.6, "sumiTahoe", "slidevert bottom", "slidevert bottom"),
        ("zoomFactor", 5, 3, "sumiTahoeSmooth", None, None),
    )
    for leaf, normal_duration, battery_duration, curve, normal_style, battery_style in animations:
        duration = normal_duration if mode == "normal" else battery_duration
        style = normal_style if mode == "normal" else battery_style
        if mode != "normal" and curve == "sumiTahoe": curve = "sumiTahoeSmooth"
        suffix = ", style = " + json.dumps(style) if style else ""
        lines.append(f'hl.animation({{ leaf = "{leaf}", enabled = {enabled}, speed = {duration}, bezier = "{curve}"{suffix} }})')
    # These layer surfaces animate content themselves. Avoid compositor scaling
    # full-screen transparent surfaces in addition to their QML motion.
    lines.append('hl.layer_rule({ match = { namespace = "^sumi-(bar|overlay|notifications)$" }, no_anim = true })')
    return "\n".join(lines) + "\n"
