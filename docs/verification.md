# Release verification

The v0.1.0 release separates automated behavior, fresh Arch installation, and
native graphical checks. Test data and screenshots are synthetic. The original
desktop configuration and private wallpapers were not installed into the public
checkout or replaced during validation.

## Standalone Python and QML

`bash scripts/verify.sh` passed from a separate temporary copy of the public
project, with no sibling project dependency:

- **244 Python tests passed**, with no skips in the full private-D-Bus run.
- **All 17 QML smoke runners passed**, covering services, notifications,
  launcher learning, keyboard navigation, quick settings, modal focus,
  appearance, widgets, persistence, icons, media, and animation policy.
- Widget checks exercised **25 presets × 6 sizes × 4 modes = 600 combinations**.
- Python compilation, installer shell syntax, and the asset catalog passed.

Installer tests cover fresh homes, custom XDG roots, paths containing spaces,
source relocation, repeated installation, refusal and explicit replacement of
existing configuration, package failure, collision races, interrupted activation,
pending-journal recovery, update rollback, and preservation of edited files.
The dry-run test inventories both source and home before and after a subprocess
invocation, including bytecode files, and asserts no package or service calls.

Offscreen tests replace native window wrappers only in temporary test copies.
They prove layout and interaction behavior, not compositor layer placement.

## Fresh Arch integration

The [Arch CI workflow](../.github/workflows/verify.yml) starts with `archlinux:base`,
installs the complete dependency manifest from official repositories, and runs
the suites as an unprivileged user in a separate checkout. The
[initial release-candidate run passed](https://github.com/9MidhunPM/sumi-desktop/actions/runs/39826859264).
Every subsequent push repeats the pipeline; check the
[current run](https://github.com/9MidhunPM/sumi-desktop/actions/workflows/verify.yml)
for the exact revision being installed.

`scripts/arch-install-smoke.py` performs a real file installation with installed
Arch dependencies, custom XDG paths containing spaces, and an isolated home.
It moves the source checkout, invokes the installed controller, validates the
complete Lua configuration with `Hyprland --verify-config`, checks diagnostics,
then updates, rolls back, and uninstalls while preserving a user's `local.lua`.
The release pipeline also validates every generated service with
`systemd-analyze --user verify`. This caught and corrected a working-directory
quoting error during release validation.

Container validation does not start a graphical login or physical services.
Session environment ordering, optional-service failures, and shutdown behavior
have separate unit coverage.

## Native compositor checks

The following command passed all **seven checks** on Hyprland 0.56.2 and
Quickshell 0.3.2, from an existing Wayland session:

```sh
python3 scripts/native-smoke.py \
  --parent-wayland "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" \
  --output /tmp/sumi-native-check
```

1. Complete generated Lua configuration parses.
2. The actual Sumi shell starts under a private compositor.
3. Keyboard launch of a synthetic application records launcher learning.
4. Quick settings opens and closes through keyboard navigation.
5. Notifications arrive over a private D-Bus session.
6. Wallpaper and palette changes refresh the actual rendered desktop.
7. Native layer placement matches the bar, panels, and desktop widgets.

The harness initializes a nested renderer and creates a 1600 × 1000 headless
output. It starts child processes directly, bypassing the real user's systemd
session, and cleans them up afterward. Its private D-Bus configuration disables
service autoactivation. Physical devices and the system bus are isolated;
brightness and night-light availability are explicit fixtures. See the
[capture provenance](screenshots/README.md) and the actual README screenshots.

## Publication checks

`scripts/check-public.py` scans every committed tree for private paths, local
state, unexpected symlinks, and undocumented wallpaper assets. Gitleaks scans
the complete history. `scripts/check-assets.py` verifies all 25 palettes and the
three original MIT landscapes. These checks must pass before the release tag.

The release archive is produced from the tag by `scripts/package-release.sh`;
its SHA256 file is published alongside it. Dates and authorship in the initial
40-commit history are current and authentic. Imported features are labeled as
imports in commit subjects and the changelog.

## Known validation limits

A fresh display-manager login, physical Wi-Fi/Bluetooth/audio/brightness
operations, locking and suspend on real hardware, multi-GPU behavior, and
battery impact were not exercised end to end. Missing-device behavior is
covered by isolated tests; this is not a hardware compatibility certification.
The installer leaves disk setup, GPU drivers, and display-manager replacement
to the installed Arch system. Package changes are not rolled back by Sumi.
