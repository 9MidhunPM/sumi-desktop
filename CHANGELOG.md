# Changelog

## Unreleased

- Add an outlined black dynamic island with adaptive Home, Inbox, Music, Controls, and optional Thursday pages.
- Route desktop notifications, backlight changes, audio, connectivity, and battery thresholds through a prioritized preview stream.
- Support short horizontal touchpad gestures across the entire island, keyboard tab switching, compact power profiles, and reduced/battery motion.
- Show shared, visibility-driven CPU, RAM, and root-storage usage; remove the extra bottom action grid while retaining the full original right-side Quick Settings.
- Add an independently implemented optional Thursday adapter with explicit environment configuration, streamed response text and sender labels, one measured speech waveform, and queued-audio lifecycle fixes. External companion code and credentials remain unbundled.
- Keep pinned controls stationary during transient feedback and center the clock accurately during animated width changes.
- Bound and reap region selectors, handle Escape as cancellation, keep compact island status visible during selection, and recover lost callbacks.
- Preserve the public installer, XDG paths, recovery behavior, original three MIT landscape assets, and source-history privacy checks.

## 0.1.0 — 2026-10-22

Initial standalone public release of Sumi Desktop.

- Import the existing glass shell, bar, launcher learning, quick settings, notification server, media/motion, widgets, and capture tools.
- Remove personal assistant integrations and machine-specific paths/application choices.
- Add original MIT-licensed Ember, Tide, and Ink landscapes; retain 25 reusable color presets.
- Add a complete portable Hyprland Lua session, authentication agent, wallpaper startup, clipboard services, idle locking, and suspend integration.
- Add an interactive official-Arch installer with a no-write preview, verified collision backups, copied runtime, update rollback, and edit-preserving uninstall.
- Add beginner guides, actionable diagnostics, Python/QML/Arch CI, asset/history scans, and reproducible synthetic native captures.

The initial history contains 40 subsystem and release commits with current dates. Imported features are identified as imports rather than claimed as new work.

Known boundaries: Arch x86_64 only; an installed system, networking, sudo and working GPU drivers are prerequisites. Disk setup, drivers, display-manager replacement, physical device certification, and package rollback are outside this release. The optional desktop media widget targets Spotify; general MPRIS controls remain in the bar and media panel.
