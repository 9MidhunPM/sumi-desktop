"""Private screenshot handoff to an independently managed annotation editor."""
from __future__ import annotations

import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import uuid


def _directory(*, create: bool) -> tuple[Path, int]:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    directory = runtime / "sumi/annotations"
    if create:
        directory.parent.mkdir(mode=0o700, exist_ok=True)
        directory.mkdir(mode=0o700, exist_ok=True)
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(descriptor)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        os.close(descriptor)
        raise ValueError("Annotation input directory must be private to this user")
    return directory, descriptor


def _cleanup(root_fd: int, session_fd: int, identifier: str) -> None:
    # Unlink relative to the held directory, never an arbitrary supplied path
    # or a recursively traversed tree. The user's saved output is separate.
    try:
        os.unlink("capture.png", dir_fd=session_fd)
    except FileNotFoundError:
        pass
    try:
        os.rmdir(identifier, dir_fd=root_fd)
    except FileNotFoundError:
        pass


def launch(image: bytes, output: Path, launcher) -> dict:
    """Stage private input and return after the transient worker is registered."""
    directory, root_fd = _directory(create=True)
    identifier = uuid.uuid4().hex
    session_fd = None
    try:
        os.mkdir(identifier, mode=0o700, dir_fd=root_fd)
        session_fd = os.open(identifier, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        descriptor = os.open("capture.png", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=session_fd)
        with os.fdopen(descriptor, "wb") as captured:
            captured.write(image)
            captured.flush()
            os.fsync(captured.fileno())
        os.fsync(session_fd)
        controller = Path(__file__).resolve().parents[2] / "bin/desktopctl"
        launcher([str(controller), "action", "annotation-session", identifier, str(output)])
        return {"annotation_id": identifier, "output": str(output), "launched": True}
    except BaseException:
        if session_fd is not None:
            _cleanup(root_fd, session_fd, identifier)
        raise
    finally:
        if session_fd is not None:
            os.close(session_fd)
        os.close(root_fd)


def session(identifier: str, output: str) -> None:
    """Run the editor for one owned input, cleaning it when that editor exits."""
    if not re.fullmatch(r"[a-f0-9]{32}", identifier):
        raise ValueError("Invalid annotation session")
    directory, root_fd = _directory(create=False)
    session_fd = None
    owned = False
    process = None
    interrupted = None
    cleaning = False
    previous_handlers = {}

    def interrupt(signum, _frame):
        nonlocal interrupted
        interrupted = signum
        if process is not None and not cleaning:
            raise SystemExit(128 + signum)

    try:
        session_fd = os.open(identifier, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        info = os.fstat(session_fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("Annotation session is not private to this user")
        descriptor = os.open("capture.png", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=session_fd)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise ValueError("Annotation input is not an owned private file")
        finally:
            os.close(descriptor)
        owned = True
        captured = directory / identifier / "capture.png"
        destination = Path(output)
        if not destination.is_absolute() or destination.resolve() == captured.resolve():
            raise ValueError("Annotation output must be separate from its private input")
        command = ["satty", "--filename", str(captured), "--output-filename", str(destination)]
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.signal(signum, interrupt)
        if interrupted is not None:
            raise SystemExit(128 + interrupted)
        process = subprocess.Popen(command)
        if interrupted is not None:
            raise SystemExit(128 + interrupted)
        code = process.wait()
        if code:
            raise subprocess.CalledProcessError(code, command)
    finally:
        cleaning = True
        try:
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except ProcessLookupError:
                    pass
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if owned:
                _cleanup(root_fd, session_fd, identifier)
        finally:
            for signum, previous in previous_handlers.items():
                signal.signal(signum, previous)
            if session_fd is not None:
                os.close(session_fd)
            os.close(root_fd)
