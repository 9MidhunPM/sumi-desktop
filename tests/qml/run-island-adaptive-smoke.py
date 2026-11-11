#!/usr/bin/env python3
"""Real contour must follow measured task content and survive interrupted morphs."""
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parents[2]
base = runpy.run_path(str(repo/'tests/qml/run-island-smoke.py'))
HARNESS = base['HARNESS'].split('        function test_island() {')[0] + '''        function settled() {
            wait(60);
            ready(() => island.visual.dashboardReady && !island.morphing && island.visual.shapeDistance < 1
                && Math.abs(island.visual.preferredWidth-Math.min(island.visual.requestedWidth,island.visual.maximumWidth))<.5
                && Math.abs(island.visual.preferredHeight-Math.min(island.visual.requestedHeight,island.visual.maximumHeight))<.5,
                "Measured contour settles");
            center();
            check(Math.abs(island.visual.headerWidth-island.bodyWidth)<.5 && island.visual.surface.y===0, "Header and body are one contour");
            check(Math.abs(island.inputWidth-island.bodyWidth)<.5 && Math.abs(island.inputHeight-island.bodyHeight)<.5, "Input mask follows contour");
            const headerLeft=child("islandDashboardLeftLane"), headerRight=child("islandDashboardRightLane"), clock=child("barClockTime"), period=child("barClockPeriod");
            check(headerLeft && headerRight && headerLeft.visible && headerRight.visible, "Dashboard controls are visible beside the fixed clock");
            check(headerLeft.x + headerLeft.width <= clock.x && headerRight.x >= period.x + period.width, "Header controls do not overlap the clock");
            check(island.bodyWidth<=island.width-24+.5 && island.bodyHeight<=island.height+.5, "Measured contour stays on screen");
        }
        function test_adaptive() {
            ready(() => !Settings.loading,"Settings initialized");
            Settings.reducedMotion=true; Settings.islandNotch=true;
            island.idle=false; island.monitor={activeWorkspace:{hasFullscreen:false}};
            S.Media.players=[];
            island.pin("controls"); settled();
            const controlsWidth=island.bodyWidth;
            island.selectSection("pomodoro"); settled();
            const focusWidth=island.bodyWidth, focusHeight=island.bodyHeight;
            check(focusWidth<controlsWidth-100,"Small focus task uses a smaller island");
            island.selectSection("media"); settled();
            const emptyMediaHeight = island.bodyHeight;
            check(island.bodyWidth <= 440, "Empty playback stays compact");
            player.isPlaying = true; S.Media.players = [player]; settled();
            check(island.bodyWidth>focusWidth+80 && island.bodyWidth<controlsWidth,"Playing media gets room for artwork and transport");
            check(island.bodyHeight > emptyMediaHeight, "Playback expands the actual contour from its empty state: " + emptyMediaHeight + " -> " + island.bodyHeight);
            S.Media.players = []; settled();
            island.selectSection("launcher"); settled();
            const desk=child("islandDashboardLoader").item;
            const launcher=findChild(desk,"islandDesktopLauncherLoader").item;
            const search=findChild(launcher,"launcherSearch");
            launcher.tab="Actions"; search.text=""; wait(120); settled();
            const fullHeight=island.bodyHeight;
            search.text="there-is-no-action-for-this-synthetic-query"; wait(120); settled();
            check(island.bodyHeight<fullHeight-150,"Empty result shrinks actual contour, not only page contents: "+fullHeight+" -> "+island.bodyHeight);
            check(!island.morphing,"Reduced motion commits the measured target immediately");
            Settings.reducedMotion=false;
            island.selectSection("appearance"); wait(90);
            const before=island.bodyWidth;
            island.selectSection("pomodoro");
            check(Math.abs(island.bodyWidth-before)<1,"Interrupted resize starts at its current shape");
            let intermediate=false;
            for(let frame=0;frame<24;frame++) { wait(16); center(); if(island.morphing && island.bodyWidth>focusWidth+1 && island.bodyWidth<680) intermediate=true; }
            settled();
            check(intermediate,"Task transition renders intermediate contour frames");
            check(Math.abs(island.bodyWidth-focusWidth)<.5 && Math.abs(island.bodyHeight-focusHeight)<1,"Interrupted morph reaches correct small task target");
            island.dismiss(true); wait(220);
            island.visual.headerClicked();
            settled();
            check(island.section==="controls" && !island.previewPinned,"Header opens full controls dashboard");
            island.selectSection("appearance"); settled();
            keyClick(Qt.Key_Escape);wait(220);
            check(!island.pinned && !island.expanded,"Escape exits instead of navigating back");
            screenInfo.width=344; screenInfo.height=440; wait(40);
            Settings.reducedMotion=true; island.pin("appearance"); settled();
            check(island.bodyWidth<=320 && island.bodyHeight<=392,"Narrow short display bounds rich tools");
            console.info("ISLAND_ADAPTIVE_OK"); Qt.quit();
        }
    }
}
'''

def main():
    with tempfile.TemporaryDirectory(prefix='sumi-adaptive-') as temporary:
        work=Path(temporary); config=work/'shell'
        shutil.copytree(repo/'shell',config)
        path=config/'DynamicIsland.qml'; path.write_text(base['adapt'](path.read_text()))
        visual=config/'components/IslandContent.qml'; visual.write_text(visual.read_text().replace('HoverHandler {','HoverHandler { enabled: false;'))
        media=config/'services/Media.qml'; media.write_text(media.read_text().replace('readonly property var players: Mp.Mpris.players.values','property var players: []').replace(' && !Desktop.preview',''))
        media=config/'services/IslandMedia.qml'; media.write_text(media.read_text().replace(' && !Desktop.preview',''))
        (config/'shell.qml').write_text(HARNESS); (work/'runtime').mkdir(mode=0o700)
        env=dict(os.environ,SUMI_PREVIEW='1',SUMI_STATE_DIR=str(work/'state'),QT_QPA_PLATFORM='offscreen',XDG_RUNTIME_DIR=str(work/'runtime'))
        result=subprocess.run(['qs','-p',str(config)],env=env,capture_output=True,text=True,timeout=30)
        output=result.stdout+result.stderr
        if result.returncode or 'ISLAND_ADAPTIVE_OK' not in output or any(token in output for token in ('TypeError:','ReferenceError:','Binding loop','Unable to assign [undefined]')):
            raise SystemExit(output)
        print('PASS: measured task contours, empty-search shrink, united header/mask, interruption, reduced motion, main opening/Escape and narrow screen bounds')

if __name__=='__main__': main()
