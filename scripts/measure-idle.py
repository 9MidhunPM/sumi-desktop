#!/usr/bin/env python3
"""Record CPU and battery telemetry without changing hardware settings."""
import argparse
import json
import os
from pathlib import Path
import time


def cpu(pid):
    try:
        # Everything after the final ')' starts at field 3 (state).
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")",1)[1].split()
        return int(fields[11]) + int(fields[12])
    except (FileNotFoundError, ProcessLookupError):
        return None


def batteries():
    result = {}
    for path in Path('/sys/class/power_supply').glob('*'):
        try:
            if path.joinpath('type').read_text().strip() != 'Battery':
                continue
            values = {}
            for key in ('status','capacity','energy_now','power_now','charge_now','current_now','voltage_now'):
                try:
                    values[key] = path.joinpath(key).read_text().strip()
                except FileNotFoundError:
                    pass
            result[path.name] = values
        except FileNotFoundError:
            pass
    return result


parser = argparse.ArgumentParser()
parser.add_argument('--pid', action='append',type=int,required=True)
parser.add_argument('--seconds',type=int,default=20)
args = parser.parse_args()
duration = max(1,min(args.seconds,60))
before = {pid:cpu(pid) for pid in args.pid}
energy_before = batteries()
started = time.monotonic()
time.sleep(duration)
elapsed = time.monotonic()-started
result = {'elapsed_seconds':round(elapsed,3),'processes':{},'battery_before':energy_before,'battery_after':batteries()}
for pid in args.pid:
    after = cpu(pid)
    result['processes'][str(pid)] = {'cpu_percent_one_core':round((after-before[pid])/os.sysconf('SC_CLK_TCK')/elapsed*100,3) if after is not None and before[pid] is not None else None}
result['interpretation'] = 'Charging samples cannot establish battery-drain equivalence. Keep display settings, radios, workload and power mode matched for comparisons.'
print(json.dumps(result,indent=2))
