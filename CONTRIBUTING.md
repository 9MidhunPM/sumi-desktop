# Contributing

Sumi Desktop is a Python controller and Quickshell/QML shell for Arch Linux and current Hyprland Lua configuration. Read [the quickstart](docs/quickstart.md) and [customization guide](docs/customization.md) before proposing changes.

Open an issue describing the problem and the behavior you want. For a fix, keep the change focused and include a way to reproduce the failure. For visual changes, include screenshots with synthetic content and redistributable wallpapers. Do not publish notification bodies, clipboard content, personal filenames, imported wallpapers, credentials, or private logs.

## Work without changing your desktop

Clone the repository into a separate directory. The source tree can be edited and tested without installing it. Keep personal configuration and state out of Git. Use temporary homes, XDG directories, and private D-Bus sessions for tests. Do not point a test at the running desktop's configuration or state.

For a full isolated check on Arch with the project's dependencies and test tools installed:

```sh
./scripts/verify.sh
```

Python-only checks can be run with:

```sh
PYTHONPATH=lib python3 -m unittest discover -s tests -v
```

Some tests start offscreen Quickshell and private D-Bus processes. They need a functioning local IPC environment even though they do not test a live compositor. `scripts/check-assets.py` validates the published wallpaper catalog. Installer tests must cover dry-run immutability and failure recovery with controlled package/service doubles, not real host package operations.

Report validation accurately: Python checks, QML/offscreen tests, fresh Arch installation tests, and native graphical checks are separate kinds of evidence. A green unit test or an HTTP response does not prove that a desktop session works. Note skipped tests, missing hardware, and environment restrictions.

## Change guidelines

- Preserve the glass styling, keyboard access, focus visibility, and adaptive/reduced motion modes.
- Pass commands as argument arrays. Do not interpolate launcher text, filenames, or widget content into shell commands.
- Honor XDG paths and test spaces in paths. Runtime files must work without the source checkout or sibling repositories.
- Back up every overwritten artifact and keep dry runs free of writes and service/package actions.
- Keep personal integration modules and their external symlinks outside the public runtime.
- Add a focused regression test for behavior with a meaningful failure mode; avoid tests that merely repeat an implementation.
- Add attribution and provenance before introducing any asset. Original project assets are MIT; bundled third-party marks retain the licenses named beside them.

For a pull request, describe the user-visible problem, the resulting behavior, and exactly how you tested it. Call out changes to packages, service startup, lock/suspend behavior, configuration ownership, or recovery. Do not include generated private state or machine-specific validation output.

Contributions are supplied under this repository's MIT license unless an asset has an explicitly documented compatible license. The initial release imports existing Sumi features; commit messages should distinguish imports from new behavior and use truthful commit dates.
