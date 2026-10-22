#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
version=${1:-v0.1.0}
if [[ ! "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf '%s\n' 'Expected a release version such as v0.1.0' >&2
    exit 1
fi
mkdir -p dist
git archive --format=tar --prefix="sumi-desktop-${version}/" "$version" | gzip -n > "dist/sumi-desktop-${version}.tar.gz"
(cd dist && sha256sum "sumi-desktop-${version}.tar.gz" > "sumi-desktop-${version}.tar.gz.sha256")
printf '%s\n' "Created dist/sumi-desktop-${version}.tar.gz and SHA256 checksum"
