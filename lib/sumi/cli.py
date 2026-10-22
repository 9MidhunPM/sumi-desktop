"""Command line interface shared by keybindings, shell actions, and TTY recovery."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import subprocess

from . import profiles
from .operations import NoOperationsError


def _json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON (the default)")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="desktopctl", description="Sumi desktop profiles, themes, and recovery")
    commands = command.add_subparsers(dest="command", required=True)
    profile = commands.add_parser("profile", help="Switch or inspect desktop profiles")
    sub = profile.add_subparsers(dest="profile_command", required=True)
    use = sub.add_parser("use")
    use.add_argument("name", choices=("sumi", "classic"))
    _json_flag(use)
    _json_flag(sub.add_parser("status"))
    _json_flag(sub.add_parser("toggle", help="Switch between Classic and Sumi"))
    theme = commands.add_parser("theme", help="Browse, apply, and import wallpapers")
    themes = theme.add_subparsers(dest="theme_command", required=True)
    _json_flag(themes.add_parser("list"))
    theme_use = themes.add_parser("use")
    theme_use.add_argument("id")
    _json_flag(theme_use)
    theme_accent = themes.add_parser("accent")
    theme_accent.add_argument("id")
    theme_accent.add_argument("color", help="Primary accent, e.g. #d9a66a")
    _json_flag(theme_accent)
    theme_import = themes.add_parser("import")
    theme_import.add_argument("path", type=Path)
    _json_flag(theme_import)
    restore = commands.add_parser("restore", help="Recover from TTY or restore original configuration")
    restore.add_argument("snapshot", choices=("original", "pending"))
    _json_flag(restore)
    doctor = commands.add_parser("doctor", help="Check dependencies, backups, and session health")
    doctor.add_argument("--check", action="store_true", help="Exit nonzero when a required check fails")
    _json_flag(doctor)
    for name in ("uninstall", "rollback"):
        lifecycle = commands.add_parser(name, help="Safely " + name + " the installed desktop")
        lifecycle.add_argument("--dry-run", action="store_true")
        _json_flag(lifecycle)
    install = commands.add_parser("install", help="Back up configuration and install CLI/service units")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--update", action="store_true")
    install.add_argument("--no-packages", action="store_true")
    _json_flag(install)
    start = commands.add_parser("start", help="Start the selected profile")
    start.add_argument("--foreground", action="store_true", help=argparse.SUPPRESS)
    _json_flag(start)
    _json_flag(commands.add_parser("restart", help="Restart only the selected shell instance"))
    _json_flag(commands.add_parser("shortcuts", help="List the generated desktop shortcut registry"))
    notifications = commands.add_parser("notifications", help="Read or persist private notification history")
    notifications.add_argument("notification_command", choices=("load", "save"))
    widgets = commands.add_parser("widgets", help="Read or persist private desktop widget settings")
    widgets.add_argument("widget_command", choices=("load", "save"))
    _json_flag(widgets)
    history = commands.add_parser("launcher-history", help="Read or reset local launcher learning")
    history.add_argument("history_command", choices=("load", "record", "reset"))
    _json_flag(history)
    operation = commands.add_parser("operation", help="Inspect a desktop operation")
    operations = operation.add_subparsers(dest="operation_command", required=True)
    operation_status = operations.add_parser("status")
    operation_status.add_argument("id")
    _json_flag(operation_status)
    operation_run = operations.add_parser("run", help=argparse.SUPPRESS)
    operation_run.add_argument("id")
    motion = commands.add_parser("motion", help="Apply the managed compositor motion policy")
    motion_commands = motion.add_subparsers(dest="motion_command", required=True)
    motion_apply = motion_commands.add_parser("apply")
    motion_apply.add_argument("mode", choices=("normal", "battery", "reduced"))
    _json_flag(motion_apply)
    _json_flag(commands.add_parser("session-start", help=argparse.SUPPRESS))
    _json_flag(commands.add_parser("session-stop", help=argparse.SUPPRESS))
    commands.add_parser("session-watch", help=argparse.SUPPRESS)
    ipc = commands.add_parser("ipc", help="Call the selected profile's explicit Quickshell instance")
    ipc.add_argument("target")
    ipc.add_argument("method")
    ipc.add_argument("args", nargs=argparse.REMAINDER)
    action = commands.add_parser("action", help="Run a desktop action")
    action.add_argument("args", nargs=argparse.REMAINDER)
    return command


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(raw_args)
    home = profiles.home_path()
    state_dir = profiles.state_path(home)
    try:
        stops_shell = (args.command in {"restore", "restart"}
                       or (args.command == "theme" and args.theme_command in {"use", "accent"})
                       or (args.command == "action" and args.args[:1] == ["wallpaper"])
                       or (args.command == "profile" and args.profile_command in {"use", "toggle"})
                       or (args.command == "action" and args.args[:1] == ["profile"])
                       or args.command in {"uninstall", "rollback"})
        if stops_shell and profiles.in_shell_cgroup():
            print(json.dumps(profiles.delegate_controller(raw_args, home=home, state_dir=state_dir)))
            return 0
        if args.command == "operation":
            from . import operations
            if args.operation_command == "status":
                result = operations.status(args.id, state_dir)
            else:
                previous = os.environ.get("SUMI_CONTROLLER")
                os.environ["SUMI_CONTROLLER"] = "1"
                try:
                    result, code = operations.run(args.id, state_dir, main)
                finally:
                    if previous is None:
                        os.environ.pop("SUMI_CONTROLLER", None)
                    else:
                        os.environ["SUMI_CONTROLLER"] = previous
                print(json.dumps(result, indent=2, default=str))
                return code
        elif args.command == "shortcuts":
            from .shortcuts import registry
            result = registry()
        elif args.command == "notifications":
            from . import notifications
            if args.notification_command == "load":
                result = notifications.load(state_dir)
            else:
                # Keep notification contents off process argument lists.
                payload = sys.stdin.read(2_000_001)
                if len(payload) > 2_000_000:
                    raise ValueError("Notification history exceeds the storage limit")
                result = notifications.save(json.loads(payload), state_dir)
        elif args.command == "widgets":
            from . import widgets
            if args.widget_command == "load":
                result = widgets.load(state_dir)
            else:
                # Notes and deadline text must not appear in process arguments.
                payload = sys.stdin.read(widgets.MAX_STORAGE_BYTES + 1)
                result = widgets.save(widgets.decode(payload), state_dir)
        elif args.command == "launcher-history":
            from . import launcher_history
            if args.history_command == "record":
                payload = sys.stdin.read(launcher_history.MAX_REQUEST_BYTES + 1)
                result = launcher_history.record(launcher_history.decode_request(payload), state_dir)
            elif args.history_command == "reset":
                result = launcher_history.reset(state_dir)
            else:
                result = launcher_history.load(state_dir)
        elif args.command == "motion":
            result = profiles.apply_motion(args.mode, home=home, state_dir=state_dir)
        elif args.command == "profile":
            if args.profile_command == "status":
                result = profiles.profile_status(home=home, state_dir=state_dir)
            elif args.profile_command == "toggle":
                result = profiles.use_profile("toggle", home=home, state_dir=state_dir)
            else:
                result = profiles.use_profile(args.name, home=home, state_dir=state_dir)
        elif args.command == "theme":
            from . import themes
            if args.theme_command == "list":
                result = themes.list_themes(state_dir=state_dir)
            elif args.theme_command == "use":
                result = profiles.apply_theme_live(args.id, home=home, state_dir=state_dir)
            elif args.theme_command == "accent":
                result = profiles.apply_theme_live(args.id, accent=args.color, home=home, state_dir=state_dir)
            else:
                result = themes.import_wallpaper(args.path.expanduser(), home=home, state_dir=state_dir, data_dir=profiles.data_path(home))
        elif args.command == "restore":
            restore = profiles.restore_original if args.snapshot == "original" else profiles.restore_pending
            result = restore(home=home, state_dir=state_dir)
        elif args.command == "doctor":
            from . import installer
            result = installer.diagnostics(home=home)
            print(json.dumps(result, indent=2, default=str))
            return 1 if args.check and not result["ok"] else 0
        elif args.command in {"uninstall", "rollback"}:
            from . import installer
            result = getattr(installer, args.command)(home=home, dry_run=args.dry_run)
        elif args.command == "install":
            from . import installer
            return installer.main([flag for flag, enabled in (("--dry-run", args.dry_run), ("--update", args.update), ("--no-packages", args.no_packages)) if enabled])
        elif args.command == "start":
            result = profiles.start(home=home, state_dir=state_dir, foreground=args.foreground)
        elif args.command == "restart":
            result = profiles.restart(home=home, state_dir=state_dir)
        elif args.command == "session-start":
            result = profiles.session_start(home=home, state_dir=state_dir)
        elif args.command in {"session-stop", "session-watch"}:
            from . import session
            result = session.stop() if args.command == "session-stop" else session.watch()
        elif args.command == "ipc":
            output = profiles.ipc(args.target, args.method, args.args, home=home, state_dir=state_dir)
            if output:
                print(output)
            return 0
        elif args.command == "action":
            # Keep IPC behind this CLI as well for action callers using one entrypoint.
            if args.args and args.args[0] == "ipc":
                return main(args.args)
            from . import actions
            return actions.main(args.args) or 0
        else:
            raise profiles.ProfileError("Unknown command")
        print(json.dumps(result, indent=2, default=str))
        return 0
    except NoOperationsError as exc:
        print(f"desktopctl: {exc}", file=sys.stderr)
        return 3
    except (RuntimeError, ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(f"desktopctl: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
