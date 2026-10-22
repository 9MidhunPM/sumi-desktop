# Updates, recovery, and removal

Keep the installation's backup directory. By default it is `~/.local/state/sumi/installer/backups`; custom XDG state settings move it with the rest of Sumi's private state. Backups contain copies of previous configuration and should be treated as private files.

The installer records ownership and checksums in `installer/installed.json`. Do not edit these records or remove backups while an operation is in progress.

## Update and rollback

From your source checkout, fetch the release you want to install, then review the preview:

```sh
git pull --ff-only
./install.sh --update --dry-run
./install.sh --update
```

Use the same XDG environment as the original installation. Updates replace the installed runtime, so the desktop does not depend on the checkout's location. An update saves the previous installation as a rollback snapshot. The original pre-Sumi backup remains available.

Managed defaults can be replaced during an update. `hypr/local.lua` and unmanaged Hyprland files are retained; keep personal compositor settings there. Review the printed file list and retain your own copy of important configuration. Log out and back into Hyprland after updating.

To return to the snapshot saved immediately before the latest update:

```sh
desktopctl rollback --dry-run
desktopctl rollback
```

Rollback captures the current state in a safety snapshot before restoring the update snapshot. It changes installed files and configuration; log out and back in afterward. It does not roll back Arch package upgrades.

## If the desktop does not start

Press **Ctrl+Alt+F3**, log in as your normal user, and run:

```sh
"$HOME/.local/bin/desktopctl" doctor --check
journalctl --user -b -u sumi-shell.service -u sumi-session.target --no-pager
```

The doctor command reports missing dependencies, installation ownership problems, and session readiness with suggested next steps. It returns a failing status when required checks fail. A text console is not a running graphical session, so session checks can be unavailable there.

If the controller launcher is unavailable but your checkout is intact, run `./bin/desktopctl` from that checkout instead. Use the same XDG environment so it finds the installed state.

| Symptom | Next step |
| --- | --- |
| Package installation fails | Read the pacman error, repair networking or the package problem, then rerun setup. Desktop files are not replaced before package installation succeeds. Packages already installed by pacman may remain. |
| Hyprland rejects configuration | In a running Hyprland session use `hyprctl configerrors`; inspect `hypr/local.lua` and recent edits. From a console inspect the error printed by `Hyprland`. |
| Shell is absent inside Hyprland | Run `desktopctl doctor --check`, then inspect `journalctl --user -b -u sumi-shell.service`. Use `desktopctl session-start` only from the affected Hyprland session to refresh environment and services. |
| Network controls are unavailable | Check `systemctl status NetworkManager.service`. Setup retains a detected competing network manager; migrate deliberately before enabling NetworkManager. |
| Bluetooth, audio, battery, or brightness is unavailable | Confirm that the device exists and its system service/driver works. A desktop without a battery or an output without a controllable backlight is supported. |
| Suspend is refused because the idle service is inactive | Inside Hyprland run `desktopctl session-start`, then inspect `systemctl --user status sumi-idle.service`. Secure suspend waits for the lock service through Hypridle's inhibitor. |
| Screen sharing is unavailable | Inspect `systemctl --user status xdg-desktop-portal.service xdg-desktop-portal-hyprland.service` and their journal. Log out and back in after installing or changing portal settings. |
| A panel reports a failed desktop change | Read its error and inspect `desktopctl operation status latest`. A queued operation is not evidence that it completed. |

The installer journals configuration replacement before touching destinations. If a setup or update was interrupted, the next real installation attempt recovers the pending file transaction before proceeding. A dry run reports the pending transaction without modifying it. For an interrupted desktop profile operation, `desktopctl restore pending` handles that separate recovery record. Preserve the original error output if recovery cannot complete.

## Restore the previous desktop

When a usable previous Hyprland backup exists, Appearance exposes **Restore previous desktop**. For recovery, log out to a text console first and run:

```sh
desktopctl restore original
```

This restores the original backed-up configuration and can replace later edits to managed files. It saves the current state in a safety snapshot before restoring, and reports both snapshot paths. Choose uninstall instead if you want edited artifacts preserved in place. Start your previous session afterward; if you triggered recovery from Appearance, log out to complete the change. On a fresh installation with no usable previous desktop configuration, this recovery action is unavailable; removal remains available.

## Uninstall

Preview what Sumi owns, then remove it:

```sh
desktopctl uninstall --dry-run
desktopctl uninstall
```

Uninstall restores backed-up originals or removes newly installed artifacts only when they still match Sumi's recorded ownership. Subsequently edited files are preserved. A changed owned directory is preserved as a whole artifact, so the output may list a directory requiring your review. Inspect those paths manually before making any further changes.

Uninstall retains user data, private wallpaper imports, state, backup snapshots, and installed system packages. It does not remove drivers, a display manager, or other applications. It also leaves system-service choices for you to review, since those services may be used by another desktop.

Log out after restoring or uninstalling. Do not delete Sumi's backups until you have checked that your previous desktop and important configuration are intact.
