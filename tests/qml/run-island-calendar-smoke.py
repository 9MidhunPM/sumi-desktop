#!/usr/bin/env python3
"""Exercise the separate island calendar area with deterministic fixtures."""
import os
from pathlib import Path
import shutil
import runpy
import subprocess
import tempfile

HARNESS = '''import QtQuick
import QtTest
import Quickshell
import "components"
ShellRoot {
    QtObject {
        id: fakeApp
        property bool focusRunning: false
        property double focusDeadline: 0
        property double focusRemaining: 1500000
    }
    FloatingWindow {
        visible: true; implicitWidth: 600; implicitHeight: 700; color: "black"
        IslandDashboard { id: home; anchors.fill: parent; app: fakeApp; active: true; now: new Date(2024, 1, 29, 12).getTime(); onSectionRequested: section => home.section = section }
        TestCase {
            name: "IslandCalendar"
            when: true
            function check(value, message) { if (!value) { console.error("ISLAND_CALENDAR_FAILED", message); Qt.exit(1); throw new Error(message); } }
            function test_calendar() {
                wait(200);
                const button = findChild(home, "islandHomeCalendar");
                const calendar = findChild(home, "islandMonthView");
                const deck = findChild(home, "islandTabDeck");
                const area = findChild(home, "islandCalendarArea");
                check(!area.visible && deck.count === 5, "Calendar is outside the five-tab deck");
                mouseClick(button);
                wait(100);
                check(findChild(home, "islandCalendarBack").activeFocus, "Calendar entry focuses visible Back control");
                check(home.section === "calendar" && area.visible && !deck.visible && !deck.active, "Home button opens separate calendar area");
                check(home.tabDeck === null && findChild(home, "islandTabHome").selected, "Calendar stays under Home and disables outer slide gestures");
                check(findChild(home, "islandTabCalendar") === null && deck.count === 5, "No calendar tab or sixth slide destination");
                check(calendar.daysInMonth === 29 && calendar.firstWeekday === 3, "Leap February uses Monday-first alignment");
                check(findChild(calendar, "islandCalendarDay31").isToday, "Only current date is highlighted");
                findChild(calendar, "islandCalendarNext").clicked();
                check(calendar.month.getMonth() === 2 && calendar.daysInMonth === 31, "Next month navigates to March");
                findChild(calendar, "islandCalendarPrevious").clicked();
                check(calendar.month.getMonth() === 1, "Previous month returns to February");
                calendar.monthOffset = 10;
                findChild(calendar, "islandCalendarNext").clicked();
                check(calendar.month.getFullYear() === 2025 && calendar.month.getMonth() === 0, "Month navigation crosses year boundary");
                findChild(calendar, "islandCalendarToday").clicked();
                check(calendar.monthOffset === 0 && calendar.month.getMonth() === 1, "Today restores current month");
                home.anchors.fill = null; home.width = 280; home.height = 300;
                wait(100);
                check(calendar.width <= 280 && area.contentHeight > area.height, "Calendar fits compact width and scrolls in short island");
                for (const name of ["islandCalendarMonth", "islandCalendarToday", "islandCalendarPrevious", "islandCalendarNext", "islandCalendarDay0", "islandCalendarDay41"]) {
                    const item = findChild(calendar, name);
                    const point = item.mapToItem(calendar, 0, 0);
                    check(point.x >= 0 && point.x + item.width <= calendar.width + 1, "Calendar controls fit compact width: " + name);
                }
                findChild(home, "islandCalendarBack").clicked();
                check(home.section === "home" && deck.visible && deck.active && home.tabDeck === deck, "Back returns Home and restores five-page gestures");
                wait(100);
                check(findChild(home, "islandTabHome").activeFocus, "Back restores focus to Home");
                button.clicked();
                wait(100);
                keyClick(Qt.Key_Tab, Qt.ControlModifier);
                wait(100);
                check(home.section === "inbox", "Ctrl Tab exits calendar to next main tab");
                home.section = "calendar";
                wait(100);
                keyClick(Qt.Key_Tab, Qt.ControlModifier | Qt.ShiftModifier);
                wait(100);
                check(home.section === "thursday", "Ctrl Shift Tab exits calendar to previous main tab");
                console.info("ISLAND_CALENDAR_OK"); Qt.quit();
            }
        }
    }
}
'''


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='sumi-island-calendar-') as temporary:
        work = Path(temporary)
        for folder in ('components', 'config', 'assets'):
            shutil.copytree(repo / 'shell' / folder, work / folder)
        shutil.copytree(repo / 'shell/integrations', work / 'integrations')
        services = work / 'services'
        services.mkdir()
        stubs = runpy.run_path(str(repo / 'tests/qml/run-island-dashboard-smoke.py'))['STUBS']
        (services / 'qmldir').write_text(''.join(f'singleton {name} {name}.qml\n' for name in stubs))
        for name, body in stubs.items():
            (services / f'{name}.qml').write_text('pragma Singleton\nimport QtQuick\nimport Quickshell\nSingleton {\n' + body + '}\n')
        (work / 'shell.qml').write_text(HARNESS)
        runtime = work / 'runtime'
        runtime.mkdir(mode=0o700)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_RUNTIME_DIR=str(runtime), SUMI_PREVIEW='1')
        result = subprocess.run(['qs', '-p', str(work)], env=env, text=True, capture_output=True, timeout=15)
        output = result.stdout + result.stderr
        if result.returncode or 'ISLAND_CALENDAR_OK' not in output or any(message in output for message in ('TypeError:', 'ReferenceError:', 'Unable to assign [undefined]', 'Failed to load configuration', 'FAIL!')):
            raise SystemExit(output)
        print('PASS: Home calendar subpage; five tabs only; gesture suspension; Back and keyboard navigation; leap day; month/year navigation; Today; compact scrollable layout')


if __name__ == '__main__':
    main()
