#!/usr/bin/env python3
"""Core desk journeys against real preview services; no desktop mutations."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "components"
import "services" as S
ShellRoot {
    S.IslandSession { id: session }
    QtObject { id: app; property var islandSession: session }
    FloatingWindow {
        visible: true
        implicitWidth: 570; implicitHeight: 500
        IslandCorePage {
            id: page
            anchors.fill: parent
            app: app
            active: true
            onRouteRequested: route => page.route = route
        }
        TestCase {
            name: "IslandCoreJourneys"
            when: true
            function check(value, message) { if (!value) { console.error(message); Qt.exit(1); throw new Error(message); } }
            function test_journeys() {
                wait(100);
                check(S.SystemStats.consumers[page.statsConsumer] === true, "Home requests shared statistics");
                page.route = "calendar";
                check(S.SystemStats.consumers[page.statsConsumer] === false, "Inactive Home suspends statistics");
                page.route = "home";
                page.active = false;
                check(S.SystemStats.consumers[page.statsConsumer] === false, "Dismissed Home suspends statistics");
                page.active = true;
                const entries = [];
                for (let i = 1; i <= 14; i++) entries.push({id:i, appName:"Fixture", summary:"Notification " + i, body:"Plain <b>body</b>", time:new Date(), unread:true, actions:[]});
                S.Notifications.history = entries;
                page.openNotification(entries[13]);
                wait(240);
                check(page.route === "notification" && session.entityId === "14", "Notification opens internally with entity");
                check(S.Notifications.history.find(e => e.id === 14).unread === false, "Only selected detail marked seen");
                check(S.Notifications.history.filter(e => e.unread).length === 13, "Opening detail never marks all read");
                page.route = "inbox";
                wait(240);
                check(S.Notifications.history.find(e => e.id === 12).unread, "Offscreen rows remain unread");
                const inbox = findChild(page, "islandDeskInbox");
                inbox.contentY = 250;
                page.route = "calendar";
                const month = findChild(page, "islandDeskMonthView");
                month.monthOffset = 3;
                page.active = false;
                page.active = true;
                page.route = "home";
                page.route = "calendar";
                check(month.monthOffset === 3, "Calendar month survives navigation and dismissal");
                page.route = "inbox";
                check(inbox.contentY === 250, "Inbox retains scroll across destinations");
                page.active = false;
                S.Notifications.history = S.Notifications.history.concat([{id:99,appName:"Fixture",summary:"Hidden arrival",body:"",time:new Date(),unread:true,actions:[]}]);
                wait(240);
                check(S.Notifications.history.find(e => e.id === 99).unread, "Inactive inbox cannot mark arrivals read");
                Qt.quit();
            }
        }
    }
}
'''

def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-core-pages-') as tmp:
        work = Path(tmp)
        for name in ('components', 'config', 'services', 'assets'):
            shutil.copytree(repo / 'shell' / name, work / name)
        (work / 'shell.qml').write_text(HARNESS)
        runtime = work / 'runtime'
        runtime.mkdir(mode=0o700)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QSG_RHI_BACKEND='software', SUMI_PREVIEW='1', XDG_RUNTIME_DIR=str(runtime), SUMI_STATE_DIR=str(work/'state'))
        run = subprocess.run(['qs', '-p', str(work/'shell.qml')], env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=25)
        if run.returncode:
            print(run.stdout)
            raise SystemExit(run.returncode)
        print('PASS: notification entity/read-visible semantics, inactive arrivals, calendar and inbox state retained')

if __name__ == '__main__':
    main()
