#!/usr/bin/env python3
"""Real file installation against installed Arch packages, as a normal user.

CI installs the declared packages into a fresh Arch container before this test.
External services and the compositor are not started in the container lane.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    if os.getuid() == 0:
        raise SystemExit('Run the Arch integration smoke as a normal user')
    with tempfile.TemporaryDirectory(prefix='sumi Arch install ') as directory:
        base=Path(directory); source=base/'source with spaces'; home=base/'fresh home'; home.mkdir()
        shutil.copytree(ROOT,source,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc','artifacts'))
        runtime=base/'runtime'; runtime.mkdir(mode=0o700)
        env={'HOME':str(home),'SUMI_HOME':str(home),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8',
             'XDG_CONFIG_HOME':str(base/'config'),'XDG_DATA_HOME':str(base/'data'),
             'XDG_STATE_HOME':str(base/'state'),'XDG_CACHE_HOME':str(base/'cache'),
             'XDG_RUNTIME_DIR':str(runtime),'PYTHONDONTWRITEBYTECODE':'1'}
        def call(argv,answer=None):
            result=subprocess.run([str(a) for a in argv],input=answer,env=env,cwd=base,text=True,capture_output=True,timeout=120)
            if result.returncode: raise AssertionError(result.stdout+'\n'+result.stderr)
            return result.stdout
        call([source/'install.sh','--dry-run'])
        call([source/'install.sh','--no-packages'],'Install Sumi\n')
        controller=home/'.local/bin/desktopctl'
        moved=base/'source moved away';source.rename(moved)
        assert json.loads(call([controller,'profile','status']))['standalone']
        assert len(json.loads(call([controller,'theme','list']))) == 25
        assert not list((base/'data/sumi/runtime').rglob('__pycache__'))
        call(['Hyprland','--verify-config','-c',base/'config/hypr/hyprland.lua'])
        units=sorted((base/'config/systemd/user').glob('sumi-*'))
        call(['systemd-analyze','--user','verify',*units])
        call([controller,'doctor','--check'])
        local=base/'config/hypr/local.lua';local.write_text('-- retained personal settings\n')
        call([moved/'install.sh','--update','--no-packages'],'Back up and use Sumi\n')
        assert local.read_text()=='-- retained personal settings\n'
        call([controller,'rollback','--dry-run']);call([controller,'rollback'])
        call([controller,'uninstall','--dry-run']);call([controller,'uninstall'])
        assert local.is_file()
        assert not (base/'data/sumi/runtime').exists()
        assert (base/'state/sumi/installer/backups').is_dir()
    print('PASS: fresh Arch install, source relocation, Lua parser, doctor, update, rollback, edited-file preservation, uninstall')

if __name__=='__main__': main()
