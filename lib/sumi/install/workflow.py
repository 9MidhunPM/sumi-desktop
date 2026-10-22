"""Interactive setup: review, explicit collision consent, packages, then files."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import tempfile

from . import ownership, packages, prerequisites
from .paths import InstallError, Layout

RUNTIME_ENTRIES = ("bin", "lib", "shell", "assets", "systemd", "templates", "packaging", "LICENSE")


def render_artifacts(source: Path, layout: Layout, *, update: bool = False) -> dict[Path, tuple[bytes, int]]:
    """All generated files are rendered in memory before the first write."""
    from .. import session, themes
    files = session.build_artifacts(layout.runtime, layout.config, layout.data,
                                    layout.state, layout.bin, home=layout.home)
    # Theme resolution reads the public catalog and any existing user preference.
    theme_id = ownership.load(layout.state / "theme.json", {}).get("id", themes.DEFAULT_THEME_ID)
    try:
        theme = themes.get_theme(theme_id, home=layout.home, state_dir=layout.state, data_dir=layout.data)
    except (KeyError, ValueError):
        theme = themes.get_theme(themes.DEFAULT_THEME_ID, home=layout.home, state_dir=layout.state, data_dir=layout.data)
    rendered, _warnings = themes.render_theme(theme, home=layout.home, state_dir=layout.state)
    for path, content in rendered.items():
        # Bundled images must survive deletion or movement of the source checkout.
        content = content.replace(str(source / "assets"), str(layout.runtime / "assets"))
        files[path] = (content.encode(), 0o600)
    wrapper = "#!/bin/sh\nexport PYTHONDONTWRITEBYTECODE=1\nexec " + shlex.quote(str(layout.runtime / "bin/desktopctl")) + ' "$@"\n'
    files[layout.bin / "desktopctl"] = (wrapper.encode(), 0o755)
    profile = ownership.load(layout.state / "profile.json", {}) if update else {}
    profile.update(profile="sumi", installed=True, install_root=str(layout.runtime), standalone=True)
    files[layout.state / "profile.json"] = ((json.dumps(profile, indent=2) + "\n").encode(), 0o600)
    return files


def artifact_paths(layout: Layout, files: dict) -> list[Path]:
    hypr = layout.config / "hypr"
    return [layout.runtime, hypr, *[path for path in files if not path.is_relative_to(hypr)]]


def stage(source: Path, layout: Layout, files: dict, destination: Path, *, update: bool = False) -> dict[Path, Path]:
    runtime = destination / "runtime"
    runtime.mkdir()
    def ignore(_directory, names):
        return [name for name in names if name in {"__pycache__", ".git", ".DS_Store"} or name.endswith(".pyc")]
    for name in RUNTIME_ENTRIES:
        item = source / name
        if not item.exists():
            raise InstallError(f"Incomplete source release: {item} is missing")
        inventory = ownership.inventory(item)
        if any(entry["type"] == "link" for entry in inventory.values()):
            raise InstallError(f"Public runtime contains a symlink: {item}; use a clean release archive")
        if item.is_dir():
            shutil.copytree(item, runtime / name, ignore=ignore)
        else:
            shutil.copy2(item, runtime / name)
    artifacts = {layout.runtime: runtime}
    hypr = destination / "hypr"
    existing_hypr = layout.config / "hypr"
    if update and existing_hypr.is_dir() and not existing_hypr.is_symlink():
        shutil.copytree(existing_hypr, hypr, symlinks=True)
    else:
        hypr.mkdir()
    artifacts[layout.config / "hypr"] = hypr
    for index, (path, (content, mode)) in enumerate(files.items()):
        if path.is_relative_to(layout.config / "hypr"):
            temporary = hypr / path.relative_to(layout.config / "hypr")
            if update and path.name == "local.lua" and os.path.lexists(temporary):
                continue
            # A previously configured symlink must not redirect staging writes.
            relative = temporary.relative_to(hypr)
            parent = hypr
            for part in relative.parts[:-1]:
                parent = parent / part
                if parent.is_symlink():
                    parent.unlink()
                    parent.mkdir()
        else:
            temporary = destination / "files" / str(index)
            artifacts[path] = temporary
        ownership.write(temporary, content, mode)
    return artifacts


def summary(source: Path, layout: Layout, paths: list[Path], *, update: bool, no_packages: bool) -> None:
    print("Sumi desktop " + ("update" if update else "installation"))
    print("Runtime: " + str(layout.runtime))
    print("Configuration: " + str(layout.config))
    print("Private state and recovery backups: " + str(layout.state))
    print("Files/directories managed by this operation:")
    for path in paths:
        print("  " + str(path) + (" [existing: will be backed up]" if os.path.lexists(path) else " [new]"))
    if no_packages:
        print("Packages: skipped by request; installed runtime dependencies will be checked.")
    else:
        print("Official Arch package operation (includes a full system upgrade):")
        print("  " + shlex.join(packages.package_command(source)))
        print("Services: enable/start NetworkManager unless another network manager is active;")
        print("          enable/start Bluetooth only when an adapter is detected.")
    print("Your running graphical session is left active. Log out and select Hyprland after setup.")
    print("Packages, drivers, login managers, disks, and user data are never removed by uninstall.")


def run(source: Path, *, dry_run: bool = False, update: bool = False, no_packages: bool = False,
        home: Path | None = None) -> dict:
    source = source.resolve()
    layout = Layout.from_environment(home)
    existing = ownership.load(layout.manifest)
    if update and not existing:
        raise InstallError("Sumi is not installed here. Run ./install.sh without --update first.")
    if existing and not update:
        raise InstallError("Sumi is already installed. Run ./install.sh --update to create a rollback snapshot.")
    files = render_artifacts(source, layout, update=update)
    paths = artifact_paths(layout, files)
    layout.validate(paths)
    summary(source, layout, paths, update=update, no_packages=no_packages)
    errors = prerequisites.check_host()
    if no_packages:
        errors += prerequisites.check_versions() + packages.check_dependencies(source)
    if dry_run:
        print("DRY RUN: no files, directories, packages, services, or private state were changed.")
        if layout.journal.exists():
            print("An interrupted operation is pending. A real installation will recover it before continuing.")
        for error in errors:
            print("Prerequisite: " + error)
        return {"dry_run": True, "prerequisites_ok": not errors, "destinations": [str(p) for p in paths]}
    if errors:
        raise InstallError("\n".join(errors))
    collisions = any(os.path.lexists(path) for path in paths)
    required = "Back up and use Sumi" if collisions else "Install Sumi"
    print("\nType " + required + " to continue, or press Enter to exit without changes.")
    try:
        choice = input("> ").strip()
    except EOFError:
        choice = ""
    if choice != required:
        return {"cancelled": True, "changed": False}
    if not no_packages:
        packages.install_packages(source)
    errors = prerequisites.check_versions() + packages.check_dependencies(source)
    if errors:
        raise InstallError("\n".join(errors) + "\nDesktop files have not been changed.")
    previous_handler = signal.getsignal(signal.SIGTERM)
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt("Installation interrupted")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with ownership.locked(layout):
            recovered = ownership.recover_pending(layout)
            # A recovered partial operation may have altered the files that theme
            # adapters merge; render again after restoring the known state.
            if recovered:
                files = render_artifacts(source, layout, update=update)
            with tempfile.TemporaryDirectory(prefix="stage-", dir=layout.records) as directory:
                artifacts = stage(source, layout, files, Path(directory), update=update)
                installed = ownership.transact(layout, artifacts, kind="update" if update else "install")
        notes = packages.configure_system_services() if not no_packages else []
        if os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
            result = subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
            if result.returncode:
                notes.append("User service reload failed. Log in again, then run desktopctl doctor --check.")
        print("Sumi is installed. Log out and select Hyprland; from a TTY run Hyprland.")
        print("Controller: " + str(layout.bin / "desktopctl"))
        for note in notes:
            print(note)
        return {"installed": True, "update": update, "runtime": installed["runtime"],
                "backup": installed["original"], "rollback": installed["rollback"], "notes": notes}
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the Sumi desktop on an installed Arch x86_64 system")
    parser.add_argument("--dry-run", action="store_true", help="Print the full plan without changing any state")
    parser.add_argument("--update", action="store_true", help="Update the installed runtime and retain rollback")
    parser.add_argument("--no-packages", action="store_true", help="Use already installed dependencies (advanced)")
    args = parser.parse_args(argv)
    try:
        result = run(Path(__file__).resolve().parents[3], dry_run=args.dry_run,
                     update=args.update, no_packages=args.no_packages)
        return 0 if result.get("prerequisites_ok", True) else 1
    except (InstallError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print("Sumi setup: " + str(exc))
        return 1
    except KeyboardInterrupt:
        print("Sumi setup interrupted. Completed file changes were rolled back; packages may remain installed.")
        return 130
