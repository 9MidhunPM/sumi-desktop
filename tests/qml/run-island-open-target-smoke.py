#!/usr/bin/env python3
"""Preview promotion must measure controls before the first visible dashboard frame."""
from pathlib import Path
import runpy,shutil,tempfile,subprocess,os,json,re
repo=Path(__file__).resolve().parents[2]
m=runpy.run_path(str(repo/'tests/qml/run-island-smoke.py'))
h=m['HARNESS'].split('        function test_island() {')[0]+'''        function test_open_target() {
            ready(() => !Settings.loading, "Settings initialized");
            Settings.reducedMotion=false;Settings.islandNotch=false;island.idle=false;
            island.monitor={activeWorkspace:{hasFullscreen:false}};S.Media.players=[];wait(100);
            for(const previous of ["media","inbox"]) {
                island.pin(previous);wait(250);island.dismiss();wait(250);
                island.visual.headerClicked();
                check(island.pinned && !island.previewPinned && island.section === "controls", "Header opens the full controls dashboard");
                let lastHeight = island.bodyHeight, lastWidth = island.bodyWidth;
                const header=child("islandUtilityHeader");
                check(header !== null, "Contextual utility header is retained");
                for(let frame=0;frame<24;frame++) {
                    wait(1);
                    console.info("OPEN_GEOMETRY", previous, frame, island.bodyWidth, island.bodyHeight);
                    check(island.bodyHeight >= lastHeight - .5 && island.bodyWidth >= lastWidth - .5, "Opening geometry must not overshoot then shrink");
                    lastHeight = island.bodyHeight; lastWidth = island.bodyWidth;
                    const workspace=child("islandDashboardLoader").item;
                    check(island.section==="controls" && workspace.resolvedRoute==="controls","Explicit promotion opens controls from its first visible frame");
                    check(workspace.currentPage && workspace.currentPage.route==="controls","Retained page content identifies the intended utility during expansion");
                    wait(15);
                }
                island.dismiss();wait(200);
            }
            console.info("OPEN_TARGET_OK");Qt.quit();
        }
    }
}
'''
with tempfile.TemporaryDirectory(prefix='island-motion-') as temp:
 p=Path(temp);config=p/'shell';shutil.copytree(repo/'shell',config)
 path=config/'DynamicIsland.qml';path.write_text(m['adapt'](path.read_text()))
 v=config/'components/IslandContent.qml';v.write_text(v.read_text().replace('HoverHandler {','HoverHandler { enabled: false;'))
 media=config/'services/Media.qml';media.write_text(media.read_text().replace('readonly property var players: Mp.Mpris.players.values','property var players: []').replace(' && !Desktop.preview',''))
 island_media=config/'services/IslandMedia.qml';island_media.write_text(island_media.read_text().replace(' && !Desktop.preview',''))

 (config/'shell.qml').write_text(h);rt=p/'runtime';rt.mkdir(mode=0o700)
 env=dict(os.environ,SUMI_PREVIEW='1',SUMI_STATE_DIR=str(p/'state'),QT_QPA_PLATFORM='offscreen',XDG_RUNTIME_DIR=str(rt))
 r=subprocess.run(['qs','-p',str(config)],env=env,capture_output=True,text=True,timeout=20)
 out=r.stdout+r.stderr
 print(out)
 if r.returncode or 'OPEN_TARGET_OK' not in out:raise SystemExit(1)
