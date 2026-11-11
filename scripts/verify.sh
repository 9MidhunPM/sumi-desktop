#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export PYTHONPATH="$PWD/lib${PYTHONPATH:+:$PYTHONPATH}"
python3 -m unittest discover -s tests -v
python3 tests/qml/run-services-smoke.py
python3 tests/qml/run-widget-services-smoke.py
python3 tests/qml/run-artwork-smoke.py
python3 tests/qml/run-island-events-smoke.py
python3 tests/qml/run-island-media-smoke.py
python3 tests/qml/run-island-smoke.py
python3 tests/qml/run-controls-smoke.py
python3 tests/qml/run-capture-handoff-smoke.py
python3 tests/qml/run-capture-controller-smoke.py
python3 tests/qml/run-system-stats-smoke.py
python3 tests/qml/run-island-dashboard-smoke.py
python3 tests/qml/run-island-session-smoke.py
python3 tests/qml/run-island-workspace-smoke.py
python3 tests/qml/run-island-open-target-smoke.py
python3 tests/qml/run-island-adaptive-smoke.py
python3 tests/qml/run-island-natural-size-smoke.py
python3 tests/qml/run-island-core-pages-smoke.py
python3 tests/qml/run-island-controls-inline-smoke.py
python3 tests/qml/run-island-desktop-smoke.py
python3 tests/qml/run-thursday-adapter-smoke.py
python3 tests/qml/run-thursday-adapter-history-smoke.py
python3 tests/qml/run-island-calendar-smoke.py
python3 tests/qml/run-island-tabs-smoke.py
python3 tests/qml/run-island-thursday-smoke.py
python3 tests/qml/run-island-thursday-bridge-smoke.py
python3 tests/qml/run-island-assistant-output-smoke.py
python3 tests/qml/run-island-now-playing-smoke.py
python3 tests/qml/run-ui-smoke.py
python3 tests/qml/run-launcher-smoke.py
python3 tests/qml/run-launcher-history-smoke.py
python3 tests/qml/run-quick-settings-smoke.py
python3 tests/qml/run-interactions-smoke.py
python3 tests/qml/run-overlay-smoke.py
python3 tests/qml/run-surfaces-smoke.py
python3 tests/qml/run-icons-smoke.py
python3 tests/qml/run-marquee-smoke.py
python3 tests/qml/run-motion-policy-smoke.py
python3 tests/qml/run-popup-motion-smoke.py
python3 tests/qml/run-widgets-smoke.py
python3 tests/qml/run-controller-smoke.py
python3 tests/qml/run-appearance-smoke.py
python3 tests/qml/run-widget-editor-smoke.py
python3 -m compileall -q lib
bash -n install.sh
python3 scripts/check-assets.py
printf '%s\n' 'All isolated checks passed. Native compositor validation is separate.'
