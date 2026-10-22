"""Resolve and validate installation destinations without creating them."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


class InstallError(RuntimeError):
    """A safe, actionable installation failure."""


def absolute_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise InstallError(f"An absolute XDG path is required: {path}")
    if any(character in str(path) for character in "\n\r\x00"):
        raise InstallError("Installation paths cannot contain newlines or NUL bytes")
    return path.resolve()


@dataclass(frozen=True)
class Layout:
    home: Path
    config: Path
    data: Path
    state: Path
    bin: Path

    @classmethod
    def from_environment(cls, home: Path | None = None) -> "Layout":
        home = absolute_path(home or os.environ.get("SUMI_HOME", Path.home()))
        return cls(home, absolute_path(os.environ.get("XDG_CONFIG_HOME", home / ".config")),
                   absolute_path(os.environ.get("SUMI_DATA_DIR", Path(os.environ.get("XDG_DATA_HOME", home / ".local/share")) / "sumi")),
                   absolute_path(os.environ.get("SUMI_STATE_DIR", Path(os.environ.get("XDG_STATE_HOME", home / ".local/state")) / "sumi")),
                   absolute_path(home / ".local/bin"))

    @property
    def runtime(self) -> Path:
        return self.data / "runtime"

    @property
    def records(self) -> Path:
        return self.state / "installer"

    @property
    def shared_data(self) -> Path:
        return absolute_path(os.environ.get("XDG_DATA_HOME", self.home / ".local/share"))

    @property
    def manifest(self) -> Path:
        return self.records / "installed.json"

    @property
    def journal(self) -> Path:
        return self.records / "pending.json"

    def validate(self, paths: list[Path]) -> None:
        """Reject nested destinations and symlinked parents, including stale manifests."""
        for internal in (self.records, self.records / "backups", self.records / "lock"):
            if internal.is_symlink():
                raise InstallError(f"Installer storage cannot be a symlink: {internal}")
        allowed = (self.runtime, self.bin / "desktopctl", self.state / "profile.json",
                   self.state / "theme.json", self.shared_data / "color-schemes/Sumi.colors")
        for path in paths:
            if not path.is_absolute() or ".." in path.parts:
                raise InstallError(f"Unsafe installation destination: {path}")
            if not (path in allowed or (path.is_relative_to(self.config) and path != self.config)):
                raise InstallError(f"Destination is outside Sumi's ownership: {path}")
            parent = path.parent
            while parent != parent.parent:
                if parent.is_symlink():
                    raise InstallError(f"A destination parent is a symlink: {parent}; use a resolved XDG directory")
                parent = parent.parent
        for first in paths:
            for second in paths:
                if first != second and first.is_relative_to(second):
                    raise InstallError(f"Installation destinations overlap: {first} and {second}")
        if any(self.records == path or self.records.is_relative_to(path) for path in paths):
            raise InstallError("Installer records cannot be inside a replaced directory")
