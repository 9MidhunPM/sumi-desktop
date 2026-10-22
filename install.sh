#!/bin/sh
# No bootstrap downloads, privilege escalation, or writes occur before review.
set -eu
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python is required. On Arch run: sudo pacman -Syu --needed python git sudo'
    exit 1
fi
sumi_source=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$sumi_source/lib"
exec python3 -B -m sumi.installer "$@"
