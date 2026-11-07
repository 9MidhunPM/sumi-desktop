"""Read-only, dependency-free CPU, memory and root filesystem observations."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import time
from typing import NamedTuple


class CpuCounters(NamedTuple):
    # Guest/guest_nice are already included in user/nice and are not summed.
    fields: tuple[int, ...]

    @property
    def total(self) -> int:
        return sum(self.fields)

    @property
    def idle(self) -> int:
        return self.fields[3] + self.fields[4]


def parse_cpu(text: str) -> CpuCounters:
    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0] != "cpu":
            continue
        if len(parts) < 5:
            raise ValueError("Incomplete aggregate CPU counters")
        values = tuple(int(value) for value in parts[1:9])
        if any(value < 0 for value in values):
            raise ValueError("Negative CPU counters")
        return CpuCounters(values + (0,) * (8 - len(values)))
    raise ValueError("Aggregate CPU counters are missing")


def cpu_percent(previous: CpuCounters | None, current: CpuCounters) -> float | None:
    if previous is None or any(new < old for old, new in zip(previous.fields, current.fields)):
        return None
    elapsed = current.total - previous.total
    idle = current.idle - previous.idle
    if elapsed <= 0 or idle < 0 or idle > elapsed:
        return None
    return round(100 * (elapsed - idle) / elapsed, 1)


def parse_memory(text: str) -> tuple[int, int]:
    values = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if not separator or key not in {"MemTotal", "MemAvailable"}:
            continue
        parts = value.split()
        if len(parts) != 2 or parts[1] != "kB":
            raise ValueError("Invalid memory units")
        values[key] = int(parts[0]) * 1024
    total, available = values["MemTotal"], values["MemAvailable"]
    if total <= 0 or available < 0 or available > total:
        raise ValueError("Invalid memory counters")
    return total - available, total


class Sampler:
    def __init__(self, proc: Path = Path("/proc"), storage_path: str = "/"):
        self.proc = proc
        self.storage_path = storage_path
        self.previous_cpu: CpuCounters | None = None

    def prime(self) -> None:
        try:
            self.previous_cpu = parse_cpu((self.proc / "stat").read_text())
        except (OSError, ValueError):
            self.previous_cpu = None

    def sample(self) -> dict:
        errors = []
        cpu = None
        try:
            current = parse_cpu((self.proc / "stat").read_text())
            cpu = cpu_percent(self.previous_cpu, current)
            self.previous_cpu = current
            if cpu is None:
                errors.append("CPU needs a fresh sample.")
        except (OSError, ValueError):
            self.previous_cpu = None
            errors.append("CPU statistics are unavailable.")
        memory_used = memory_total = None
        try:
            memory_used, memory_total = parse_memory((self.proc / "meminfo").read_text())
        except (OSError, ValueError, KeyError):
            errors.append("Memory statistics are unavailable.")
        storage_used = storage_total = storage_free = None
        try:
            disk = shutil.disk_usage(self.storage_path)
            if disk.total <= 0 or not 0 <= disk.used <= disk.total or not 0 <= disk.free <= disk.total:
                raise ValueError("Invalid disk counters")
            storage_used, storage_total, storage_free = disk.used, disk.total, disk.free
        except (OSError, ValueError):
            errors.append("Root storage statistics are unavailable.")
        return {"cpuAvailable": cpu is not None, "cpuPercent": cpu,
                "memoryAvailable": memory_total is not None, "memoryUsed": memory_used, "memoryTotal": memory_total,
                "storageAvailable": storage_total is not None, "storageUsed": storage_used,
                "storageTotal": storage_total, "storageFree": storage_free, "error": " ".join(errors)}


def watch() -> None:
    """Write one JSON observation after a short baseline, then every two seconds."""
    sampler = Sampler()
    sampler.prime()
    try:
        time.sleep(.2)
        while True:
            print(json.dumps(sampler.sample(), allow_nan=False), flush=True)
            time.sleep(2)
    except (BrokenPipeError, KeyboardInterrupt):
        return
