"""One shell shortcut registry and a conservative Lua binding migration."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import shlex

START = "-- >>> SUMI SHORTCUTS START"
END = "-- <<< SUMI SHORTCUTS END"

# chord, label, controller argv, recognised Classic command, category
_ACTIONS = (
    ("SUPER + SPACE", "Open command hub", ("ipc", "sumi", "toggle", "launcher"), "theme.menu", "Shell"),
    ("SUPER + SHIFT + SPACE", "Find files", ("ipc", "sumi", "toggle", "files"), ".config/wofi/file-search.sh", "Shell"),
    ("SUPER + N", "Notification history", ("ipc", "sumi", "toggle", "notifications"), "swaync-client", "Shell"),
    ("SUPER + SHIFT + T", "Appearance", ("ipc", "sumi", "toggle", "appearance"), ".config/hypr/scripts/theme-switcher.sh", "Shell"),
    ("SUPER + CTRL + V", "Clipboard history", ("ipc", "sumi", "toggle", "clipboard"), "ipc sumi toggle clipboard", "Shell"),
    ("SUPER + RETURN", "Terminal", ("action", "terminal"), "theme.terminal", "Applications"),
    ("SUPER + E", "Files", ("action", "files"), "theme.fileManager", "Applications"),
    ("SUPER + SHIFT + S", "Capture a region", ("action", "capture", "region"), "hyprshot", "System"),
    ("SUPER + CTRL + SHIFT + S", "Capture and annotate", ("action", "capture", "region", "annotate"), "action capture region annotate", "System"),
    ("SUPER + T", "Restart selected shell", ("restart",), "pkill qs", "System"),
    ("SUPER + SLASH", "Shortcut reference", ("ipc", "sumi", "toggle", "help"), "ipc sumi toggle help", "Shell"),
)


def registry() -> dict:
    items = [{"id": chord.lower().replace(" + ", "-"),
              "keys": " + ".join({"SUPER": "Super", "CTRL": "Ctrl", "SHIFT": "Shift", "ALT": "Alt", "SPACE": "Space", "RETURN": "Enter", "SLASH": "/"}.get(part.strip(), part.strip()) for part in chord.split("+")),
              "label": label, "category": category} for chord, label, argv, _, category in _ACTIONS]
    items.extend([
        {"id": "bar-peek", "keys": "Hold Right Shift", "label": "Peek at the bar in hidden mode", "category": "Shell"},
        {"id": "workspaces", "keys": "Super + 1–9 / 0", "label": "Workspace 1–10", "category": "Workspaces"},
        {"id": "move-workspace", "keys": "Super + Shift + 1–9 / 0", "label": "Move window to workspace", "category": "Workspaces"},
        {"id": "focus", "keys": "Super + Arrow", "label": "Focus a window", "category": "Workspaces"},
        {"id": "move-window", "keys": "Super + Shift + Arrow", "label": "Move a window", "category": "Workspaces"},
        {"id": "lock", "keys": "Super + L", "label": "Lock session", "category": "System"},
    ])
    return {"version": 1, "shortcuts": items}


def code_mask(text: str) -> str:
    """Blank Lua strings/comments while preserving delimiter positions."""
    mask = list(text)
    i = 0
    while i < len(text):
        begin = i
        comment = text.startswith("--", i)
        if comment:
            i += 2
        long = re.match(r"\[(=*)\[", text[i:])
        if long:
            close = "]" + long[1] + "]"
            end = text.find(close, i + len(long[0]))
            i = len(text) if end < 0 else end + len(close)
        elif comment:
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
        elif text[i] in "\"'":
            quote = text[i]
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
        else:
            i += 1
            continue
        mask[begin:i] = ["\n" if c == "\n" else " " for c in text[begin:i]]
    return "".join(mask)


def _calls(text: str):
    mask = code_mask(text)
    for match in re.finditer(r"\bhl\s*\.\s*bind\s*\(", mask):
        stack, commas, end = ["("], [], match.end()
        while end < len(mask) and stack:
            char = mask[end]
            if char in "({[":
                stack.append(char)
            elif char in ")}]":
                stack.pop()
            elif char == "," and len(stack) == 1:
                commas.append(end)
            end += 1
        if stack or not commas:
            raise ValueError("Cannot safely parse a Hyprland shortcut")
        yield match.start(), end, text[match.end():commas[0]], text[commas[0]+1:end-1]


def _key(expression: str, aliases: dict) -> str | None:
    parts = []
    for term in re.split(r"\s*\.\.\s*", expression.strip()):
        try:
            value = ast.literal_eval(term) if term[:1] in {"'", '"'} else aliases.get(term)
        except (ValueError, SyntaxError):
            return None
        if not isinstance(value, str):
            return None
        parts.append(value)
    tokens = [token.strip().upper() for token in "".join(parts).split("+")]
    modifiers, key = tokens[:-1], tokens[-1]
    order = {"SUPER": 0, "CTRL": 1, "ALT": 2, "SHIFT": 3}
    return " + ".join(sorted(modifiers, key=lambda value: order.get(value, 9)) + [key])


def render_bindings(original: str, executable: str, *, config_dir: Path | None = None) -> tuple[str, str]:
    if original.count(START) != original.count(END) or original.count(START) > 1:
        raise ValueError("Sumi shortcut markers are incomplete or duplicated")
    original = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", "", original, flags=re.S)
    aliases = {}
    for name, literal in re.findall(r"\blocal\s+(\w+)\s*=\s*(\"[^\"\n]*\"|'[^'\n]*')", original):
        aliases[name] = ast.literal_eval(literal)
    managed = {_key(json.dumps(chord), {}): (argv, legacy) for chord, _, argv, legacy, _ in _ACTIONS}
    seen, removals = set(), []
    for begin, end, expression, body in _calls(original):
        chord = _key(expression, aliases)
        released = bool(re.search(r"\brelease\s*=\s*true", body))
        if chord is not None:
            signature = (chord, released)
            if signature in seen:
                raise ValueError("Duplicate Hyprland shortcut: " + chord + (" (release)" if released else ""))
            seen.add(signature)
        if chord not in managed and chord != "SHIFT_R":
            continue
        compact = re.sub(r"\s+", "", body)
        if chord == "SHIFT_R":
            recognised = "quickshellBar" in body or "ipcbar" in compact
        else:
            argv, legacy = managed[chord]
            recognised = re.sub(r"\s+", "", legacy) in compact or re.sub(r"\s+", "", " ".join(argv)) in compact
        if not recognised or (released and chord != "SHIFT_R"):
            raise ValueError("Sumi shortcut conflicts with a custom binding: " + chord)
        removals.append((begin, end))
    for begin, end in reversed(removals):
        original = original[:begin] + original[end:]
    # Callers may supply the installation config root. XDG remains authoritative
    # when the executable is outside the traditional ~/.local/bin location.
    config_dir = config_dir or Path(os.environ.get("XDG_CONFIG_HOME", str(Path(executable).parent.parent.parent / ".config")))
    helper = config_dir / "sumi/generated/shortcuts.lua"
    include = f'{START}\ndofile({json.dumps(str(helper))})\n{END}\n'
    lines = ["-- Generated from desktopctl shortcuts. Edit the registry, not this file."]
    for chord, _, argv, _, _ in _ACTIONS:
        command = shlex.join([executable, *argv])
        lines.append(f"hl.bind({json.dumps(chord)}, hl.dsp.exec_cmd({json.dumps(command)}))")
    bar = shlex.join([executable, "ipc", "bar"])
    lines += [f"local sumiBar = {json.dumps(bar)}",
              'hl.bind("SHIFT_R", hl.dsp.exec_cmd(sumiBar .. " peek"), { non_consuming = true })',
              'hl.bind("SHIFT_R", hl.dsp.exec_cmd(sumiBar .. " release"), { release = true, non_consuming = true })']
    return original.rstrip() + "\n\n" + include, "\n".join(lines) + "\n"
