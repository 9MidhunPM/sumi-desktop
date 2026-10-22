#!/usr/bin/env python3
"""Check every Git tree, not only HEAD, for public-release boundary violations."""
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def git(*args): return subprocess.check_output(['git','-C',str(root),*args])
seen=set(); count=0
for commit in git('rev-list','--all').decode().splitlines():
    count+=1
    for record in git('ls-tree','-rz',commit).split(b'\0'):
        if not record: continue
        meta,path=record.split(b'\t',1);mode,kind,oid=meta.split();name=path.decode()
        assert mode!=b'120000',f'Symlink in history: {name}'
        assert not any(part in {'.env','.codex','.agents','.aws','__pycache__'} for part in Path(name).parts),name
        if oid in seen: continue
        seen.add(oid)
        content=git('cat-file','blob',oid.decode())
        if b'\0' not in content:
            # Personal machine locations are never releasable. Synthetic fixtures
            # such as /home/test remain valid documentation/test data.
            assert (b'/home/' + b'midhun/') not in content, f'Private path in {name}'
        if name.startswith('assets/wallpapers/'):
            assert Path(name).name in {'ember.svg','ember.png','tide.svg','tide.png','ink.svg','ink.png'},name
        if name.startswith('assets/thumbnails/'):
            assert Path(name).name in {'ember.jpg','tide.jpg','ink.jpg'},name
print(f'PASS: {count} Git trees, {len(seen)} unique blobs; no private paths, state folders, external symlinks or undocumented wallpapers')
