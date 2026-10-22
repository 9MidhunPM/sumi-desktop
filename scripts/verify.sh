#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export PYTHONPATH="$PWD/lib${PYTHONPATH:+:$PYTHONPATH}"
python3 -m unittest discover -s tests -v
python3 tests/qml/run-services-smoke.py
python3 tests/qml/run-widget-services-smoke.py
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
