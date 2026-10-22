"""XDG locations and canonical names used by recoverable snapshots."""
import os
from pathlib import Path


def config_path(home):
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path(home) / ".config").expanduser().absolute()


def data_root(home):
    return Path(os.environ.get("XDG_DATA_HOME") or Path(home) / ".local/share").expanduser().absolute()


def managed_path(home, relative):
    name = str(relative)
    for prefix, base in ((".config", config_path(home)), (".local/share", data_root(home))):
        if name == prefix or name.startswith(prefix + "/"):
            return base / name[len(prefix):].lstrip("/")
    return Path(home) / relative


def allowed_path(home, path):
    return any(path.is_relative_to(base.resolve()) for base in (Path(home), config_path(home), data_root(home)))


def canonical_path(home, path):
    for prefix, base in ((".config", config_path(home)), (".local/share", data_root(home))):
        if path.is_relative_to(base.resolve()):
            return prefix + "/" + str(path.relative_to(base.resolve()))
    return str(path.relative_to(Path(home).resolve()))
