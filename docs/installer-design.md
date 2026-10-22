# Installer transaction model

The installer targets a normal user on an installed Arch Linux x86_64 machine.
It uses Python's standard library, official `core` and `extra` packages, and the
system package manager. It never formats disks, installs a display manager,
chooses GPU drivers, or removes packages.

## Preview and consent

`install.sh` disables Python bytecode writes before loading any modules.
Rendering, path resolution, collision detection, prerequisite checks, and the
setup summary are read-only. `--dry-run` ends at this boundary; it does not create
the home, XDG directories, a lock, an installation marker, or a backup. Version
checks query `pacman -Q` instead of launching a compositor before first login.

On a fresh destination, installation requires the typed choice `Install Sumi`.
Any existing artifact requires the exact choice `Back up and use Sumi`.
Pressing Enter, EOF, or any other answer cancels without changing files, packages,
services, or private state. There is deliberately no unattended `--yes` bypass.

The reviewed package operation uses `sudo pacman -Syu --needed` with explicit
`core/name` and `extra/name` package names. Pacman retains its own confirmation
prompt. A package failure stops before any desktop artifact is changed. Package
transactions are managed by pacman and are not undone by file rollback.

## Owned files and collision backups

Runtime code, QML, templates, and public assets are copied beneath
`$XDG_DATA_HOME/sumi/runtime`. No installed file depends on the clone or an
external runtime symlink. User configuration uses `$XDG_CONFIG_HOME`, private
records use `$XDG_STATE_HOME/sumi`, and the controller wrapper is installed at
`~/.local/bin/desktopctl`. Default XDG paths are used when variables are unset.
Absolute XDG locations and paths containing spaces are supported.

Every replaced artifact is inventoried with file hashes, modes, and symlink
targets. Sumi treats the Hyprland configuration directory and installed runtime
as complete artifacts, and theme adapters and systemd units as individual files.
Collision snapshots include every artifact, including absent destinations, the
controller wrapper, generated state, GTK/Qt settings, and existing edited files.
Backup contents are verified before installation and before recovery.

Snapshots and ownership metadata live in `sumi/installer` inside the state
directory. Snapshots are never reused as mutable working directories. Symlink
objects are copied without dereferencing their targets; symlinked destination
parents and special files are rejected. The source runtime cannot contain any
symlinks. A nonblocking installation lock prevents concurrent transactions.

## Failure recovery and updates

The installer stages all new files, copies and verifies the previous artifacts,
flushes the backup bytes, and publishes a durable `pending.json` journal before
replacing the first destination. Each destination is staged alongside its final
location. Replacing a nonempty directory has a short rename gap; the journal
covers that gap. Exceptions and Ctrl-C restore the snapshot immediately. SIGKILL
leaves the same journal for `desktopctl restore pending` or the next installation.

`./install.sh --update` requires an existing installation and retains the
previous runtime and generated files as a rollback snapshot. Update snapshots
include local edits before managed defaults are refreshed. Additional Hyprland
files, including `local.lua`, are carried into the updated configuration. An
artifact modified before update remains protected from automatic uninstall;
copying retained user files does not make them installer-owned.

`desktopctl rollback` restores the pre-update snapshot and first saves the
current files in a safety snapshot. It restores files and ownership metadata;
it does not downgrade packages. `desktopctl restore original` is available only
when a verified original backup contains a usable Hyprland entry configuration.
That command restores the original snapshot, including overwritten files, after
saving the current files. Review local changes in the safety snapshot afterward.

## Removal and diagnostics

`desktopctl uninstall` restores original collisions or removes newly installed
artifacts only when their current fingerprints match the installed ownership
record. Modified artifacts are preserved as whole files or directories. Data,
backups, installed packages, and networking services remain. An uninstall safety
snapshot and journal cover failures during removal. Log out to end the current
graphical session after removal or restoration.

`desktopctl doctor --check` reports required commands, package versions, backup
integrity, pending recovery, and session services with actionable instructions.
Missing optional battery, Bluetooth, and backlight devices are informational.
Changed owned files are informational because customization is expected.

## Verification scope

The installer suite uses temporary homes and custom XDG paths containing spaces.
It exercises the real file transaction implementation while mocking package and
service mutations. A real subprocess runs `install.sh --dry-run` from a copied
public source and proves that neither source bytecode nor destination state is
created. Tests also cover package failure, interrupted activation, backup
tampering, symlink collisions, update rollback, source-independent execution,
repeated installation, and preservation of user edits across update/uninstall.
These tests do not establish graphical startup or package compatibility in a
fresh virtual machine; those are separate native acceptance checks.
