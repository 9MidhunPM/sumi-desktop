#!/usr/bin/env python3
"""Exercise cover request visibility and stale-result handling in real QML."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "components" as C
ShellRoot {
 Window { visible: true; width: 100; height: 100
  C.ArtworkImage { id: art; anchors.fill: parent; active: false; artworkUrl: "https://fixture.test/blue" }
  TestCase { name: "ArtworkRequests"; when: true
   function test_covers() {
    wait(100); verify(!art.loading && !art.cachedSource, "Hidden covers create no network demand");
    art.active = true; tryCompare(art, "status", Image.Ready, 4000);
    verify(String(art.source).endsWith("blue.png"), "Remote result loads through native PNG decoder");
    art.artworkUrl = "https://fixture.test/slow"; wait(50);
    art.artworkUrl = "https://fixture.test/red";
    tryCompare(art, "status", Image.Ready, 4000);
    verify(String(art.source).endsWith("red.png"), "Latest track wins after cancellation");
    art.artworkUrl = "https://fixture.test/slow"; wait(30); art.active = false;
    wait(150); verify(!art.loading && !art.cachedSource, "Hidden track cancels download demand");
    art.artworkUrl = "https://fixture.test/blue"; art.active = true;
    tryCompare(art, "status", Image.Ready, 4000);
    verify(String(art.source).endsWith("blue.png"), "Returning to desktop resumes current cover");
    art.artworkUrl = "https://fixture.test/slow"; wait(30);
    art.artworkUrl = "https://fixture.test/red";
    art.artworkUrl = "https://fixture.test/slow";
    art.active = false; art.active = true;
    tryCompare(art, "status", Image.Ready, 4000);
    verify(String(art.source).endsWith("blue.png"), "A-B-A and immediate visibility resume settle current cover");
    art.artworkUrl = Qt.resolvedUrl("red.png"); tryCompare(art, "status", Image.Ready, 4000);
    verify(!art.remote, "Local artwork bypasses remote fetches");
    console.info("SUMI_ARTWORK_OK"); Qt.quit();
   }
  }
 }
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix='sumi-artwork-') as temporary:
        work = Path(temporary)
        (work / 'components').mkdir()
        (work / 'services').mkdir()
        (work / 'runtime').mkdir(mode=0o700)
        shutil.copy2(ROOT / 'shell/components/ArtworkImage.qml', work / 'components')
        for name, color in [('red', '#b84e69'), ('blue', '#6a95bc')]:
            Image.new('RGB', (100, 100), color).save(work / (name + '.png'))
        (work / 'services/fetch-artwork.py').write_text('''import sys,time
from pathlib import Path
name=sys.argv[1].rsplit('/',1)[-1]
if name=='slow':time.sleep(1)
print((Path(__file__).resolve().parents[1]/(('red' if name=='red' else 'blue')+'.png')).as_uri())
''')
        (work / 'shell.qml').write_text(HARNESS)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(work / 'runtime'))
        result = subprocess.run(['qs', '-p', str(work)], env=env, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        if result.returncode or 'SUMI_ARTWORK_OK' not in output or any(error in output for error in ['TypeError:', 'ReferenceError:', 'FAIL!', 'Binding loop']):
            raise SystemExit(output)
    print('PASS: remote cover decodes, latest track wins, hidden download cancellation, visibility resume, local bypass')


if __name__ == '__main__':
    main()
