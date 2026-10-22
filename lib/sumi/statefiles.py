"""Private state files shared by desktop actions and the user theme library."""
from __future__ import annotations

import contextlib
import fcntl
import os
from pathlib import Path
import tempfile


def home_path(home: Path | None = None) -> Path:
    return Path(home or os.environ.get("SUMI_HOME", Path.home())).expanduser()


def state_path(path: Path | None = None, *, home: Path | None = None) -> Path:
    default = Path(os.environ.get("XDG_STATE_HOME", home_path(home) / ".local/state")) / "sumi"
    return Path(path or os.environ.get("SUMI_STATE_DIR", default)).expanduser().resolve()


def data_path(path: Path | None = None, *, home: Path | None = None) -> Path:
    default = Path(os.environ.get("XDG_DATA_HOME", home_path(home) / ".local/share")) / "sumi"
    return Path(path or os.environ.get("SUMI_DATA_DIR", default)).expanduser().resolve()


@contextlib.contextmanager
def file_lock(path: Path, *, wait: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a+") as handle:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError as error:
            raise RuntimeError("Another operation is already running; try again when it finishes") from error
        yield


def atomic_write(path: Path, content: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)
