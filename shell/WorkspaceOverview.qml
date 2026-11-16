import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import "config"
import "services" as S

PanelWindow {
    id: root
    required property var modelData
    required property var app
    property bool opened: false
    signal dismissRequested()
    signal workspaceRequested(var target)
    signal windowRequested(var target, string address)
    signal overviewHidden()
    screen: modelData
    color: "transparent"
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "sumi-overview"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: opened ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    visible: opened || reveal > 0.001
    property real reveal: opened ? 1 : 0
    property int selection: 0
    property int dropIndex: -1
    property string dragTitle: ""
    property point dragPoint: Qt.point(0, 0)
    property real horizontalScroll: 0
    property real verticalScroll: 0
    Timer { id: scrollReset; interval: 350; onTriggered: { root.horizontalScroll = 0; root.verticalScroll = 0; } }
    function navigateScroll(event, horizontal) {
        const pixel = horizontal ? event.pixelDelta.x : event.pixelDelta.y;
        const angle = horizontal ? event.angleDelta.x : event.angleDelta.y;
        const delta = pixel || angle;
        let accumulator = horizontal ? horizontalScroll : verticalScroll;
        if (delta && accumulator && Math.sign(delta) !== Math.sign(accumulator)) accumulator = 0;
        accumulator += delta;
        scrollReset.restart();
        const threshold = pixel ? 90 : 200;
        while (Math.abs(accumulator) >= threshold) {
            const row = Math.floor(selection / columns);
            const col = selection % columns;
            const previous = selection;
            if (horizontal) {
                const nextCol = Math.max(0, Math.min(columns - 1, col + (accumulator > 0 ? 1 : -1)));
                const next = row * columns + nextCol;
                if (next < entries.length) selection = next;
            } else {
                const nextRow = row + (accumulator > 0 ? 1 : -1);
                const next = nextRow * columns + col;
                if (nextRow >= 0 && next < entries.length) selection = next;
            }
            if (selection === previous) { accumulator = 0; break; }
            accumulator -= Math.sign(accumulator) * threshold;
        }
        if (horizontal) horizontalScroll = accumulator; else verticalScroll = accumulator;
        event.accepted = true;
    }
    Timer {
        interval: 50; repeat: true; running: root.opened && root.dragTitle.length > 0
        onTriggered: {
            const edge = 60;
            const top = scroller.y, bottom = scroller.y + scroller.height;
            let movement = root.dragPoint.y < top + edge ? -18 : root.dragPoint.y > bottom - edge ? 18 : 0;
            const maxY = Math.max(0, scroller.contentHeight - scroller.height);
            const next = Math.max(0, Math.min(maxY, scroller.contentY + movement));
            if (next !== scroller.contentY) { scroller.contentY = next; root.updateDrop(keyTarget, root.dragPoint.x, root.dragPoint.y); }
        }
    }
    function updateDrop(source, px, py) {
        dropIndex = -1;
        for (let i = 0; i < workspaceRepeater.count; ++i) {
            const target = workspaceRepeater.itemAt(i);
            if (!target) continue;
            const p = target.mapFromItem(source, px, py);
            if (p.x >= 0 && p.y >= 0 && p.x < target.width && p.y < target.height - 37) { dropIndex = i; break; }
        }
    }
    function finishDrop(address, from) {
        const target = entries[dropIndex];
        dropIndex = -1;
        if (target && String(target.target) !== String(from)) S.HyprlandActions.moveWindowToWorkspace(address, target.target);
    }
    function openWorkspace(index) {
        if (!opened || !entries[index]) return;
        selection = index;
        workspaceRequested(entries[index].target);
    }
    onSelectionChanged: Qt.callLater(() => {
        const item = workspaceRepeater.itemAt(selection);
        if (!item) return;
        let target = scroller.contentY;
        if (item.y < target) target = item.y;
        else if (item.y + item.height > target + scroller.height) target = Math.max(0, item.y + item.height - scroller.height);
        if (target !== scroller.contentY) { selectionScroll.stop(); selectionScroll.to = target; selectionScroll.start(); }
    })
    NumberAnimation { id: selectionScroll; target: scroller; property: "contentY"; duration: Motion.reduced ? 0 : 180; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.standardCurve }
    readonly property real previewAspect: modelData ? modelData.height / modelData.width : 0.625
    function tileWidthFor(count, viewWidth, viewHeight) {
        const rows = Math.ceil(Math.max(1, entries.length) / count);
        const byWidth = (viewWidth - 22 * (count - 1)) / count;
        const byHeight = ((viewHeight - 22 * (rows - 1)) / rows - 37) / previewAspect;
        return Math.max(0, Math.min(byWidth, byHeight));
    }
    // Mission Control keeps every space on screen: pick the column count that
    // gives the largest tiles while all rows fit, instead of scrolling them away.
    readonly property int columns: {
        const viewWidth = Math.max(1, width - 2 * Math.max(36, width * 0.055)), viewHeight = Math.max(1, height - 150);
        const base = width >= 1100 ? 3 : width >= 700 ? 2 : 1;
        let best = base, bestWidth = 0;
        for (let count = base; count <= 6; count++) {
            const size = tileWidthFor(count, viewWidth, viewHeight);
            if (size > bestWidth + 0.5) { best = count; bestWidth = size; }
        }
        return width < 700 ? 1 : best;
    }
    property var entries: []
    readonly property int durationIn: Motion.reduced ? 0 : Motion.battery ? 140 : 280
    readonly property int durationOut: Motion.reduced ? 0 : Motion.battery ? 100 : 200
    Behavior on reveal { NumberAnimation { duration: root.opened ? root.durationIn : root.durationOut; easing.type: Easing.BezierSpline; easing.bezierCurve: root.opened ? Motion.bounceCurve : Motion.exitCurve } }
    Timer { id: closeTimer; onTriggered: if (!root.opened) root.overviewHidden() }
    onOpenedChanged: {
        if (opened) {
            closeTimer.stop();
            Hyprland.refreshToplevels();
            refreshEntries();
            const active = Hyprland.focusedMonitor && Hyprland.focusedMonitor.activeWorkspace;
            selection = Math.max(0, entries.findIndex(e => active && e.id === active.id));
            Qt.callLater(() => keyTarget.forceActiveFocus());
        } else {
            dropIndex = -1; dragTitle = ""; horizontalScroll = 0; verticalScroll = 0; scrollReset.stop();
            selectionScroll.stop();
            closeTimer.interval = Math.max(1, durationOut + 10);
            closeTimer.restart();
        }
    }
    function refreshEntries() {
        const selectedTarget = entries[selection] ? String(entries[selection].target) : "";
        let all = Hyprland.workspaces.values.filter(w => !!w);
        let normal = all.filter(w => !String(w.name).startsWith("special:")).sort((a,b) => a.id - b.id);
        let special = all.filter(w => String(w.name).startsWith("special:"));
        let used = new Set(normal.map(w => w.id));
        let empty = 1; while (used.has(empty)) empty++;
        let items = normal.map(w => makeEntry(w));
        items.push({id: empty, name: String(empty), target: String(empty), windows: [], monitor: "", empty: true});
        items.sort((a,b) => a.id - b.id);
        items = items.concat(special.map(w => makeEntry(w)));
        // Preserve delegates and capture sessions when only window geometry or
        // title changes. Those properties update on the toplevel objects.
        const unchanged = entries.length === items.length && items.every((item, index) => {
            const old = entries[index];
            return old && old.id === item.id && old.name === item.name && old.monitor === item.monitor && old.empty === item.empty
                && old.windows.length === item.windows.length
                && item.windows.every((window, i) => old.windows[i] === window);
        });
        if (!unchanged) entries = items;
        const selectedIndex = entries.findIndex(item => String(item.target) === selectedTarget);
        selection = selectedIndex >= 0 ? selectedIndex : Math.min(selection, Math.max(0, entries.length - 1));
    }
    function makeEntry(w) {
        return {id: w.id, name: w.name || String(w.id), target: w.name || String(w.id),
            monitor: w.monitor ? w.monitor.name : "", windows: w.toplevels ? w.toplevels.values.filter(x => !!x) : [], empty: false};
    }
    Timer {
        id: updateDebounce
        interval: 80
        onTriggered: {
            if (!root.opened) return;
            Hyprland.refreshToplevels();
            // IPC refresh completes asynchronously; coalesce its replies.
            modelUpdate.restart();
        }
    }
    Timer { id: modelUpdate; interval: 120; onTriggered: if (root.opened) root.refreshEntries() }
    Connections {
        target: Hyprland
        ignoreUnknownSignals: true
        function onRawEvent(event) {
            if (!root.opened || !event) return;
            const name = String(event.name || "");
            if (/^(openwindow|closewindow|movewindow|resizewindow|changefloatingmode|fullscreen|createworkspace|destroyworkspace|moveworkspace|renameworkspace|monitoradded|monitorremoved)/.test(name))
                updateDebounce.restart();
        }
    }
    Rectangle { anchors.fill: parent; color: Theme.desktopBackground; opacity: root.reveal }
    Image {
        anchors.fill: parent
        source: Theme.wallpaper ? (Theme.wallpaper.startsWith("/") ? "file://" + Theme.wallpaper : Theme.wallpaper) : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        opacity: root.reveal * 0.22
    }
    Rectangle { anchors.fill: parent; color: "#cc101016"; opacity: root.reveal }
    Item {
        id: keyTarget
        anchors.fill: parent
        focus: root.opened
        Keys.onPressed: event => {
            if (event.key === Qt.Key_Escape) { root.dismissRequested(); event.accepted = true; return; }
            let next = root.selection;
            if (event.key === Qt.Key_Left) next--;
            else if (event.key === Qt.Key_Right) next++;
            else if (event.key === Qt.Key_Up) next -= root.columns;
            else if (event.key === Qt.Key_Down) next += root.columns;
            else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                if (root.entries[root.selection]) root.workspaceRequested(root.entries[root.selection].target);
                event.accepted = true; return;
            } else return;
            root.selection = Math.max(0, Math.min(root.entries.length - 1, next));
            event.accepted = true;
        }
        opacity: root.reveal
        transform: Scale { origin.x: keyTarget.width / 2; origin.y: keyTarget.height / 2; xScale: 1.06 - root.reveal * 0.06; yScale: xScale }
        Text { id: heading; x: Math.max(36, root.width * 0.055); y: 38; text: "Workspaces"; color: Theme.textMain; font.family: Theme.font; font.pixelSize: 28; font.weight: Font.DemiBold }
        Row {
            anchors.right: parent.right; anchors.rightMargin: Math.max(36, root.width * 0.055); anchors.verticalCenter: heading.verticalCenter
            visible: root.width >= 700
            spacing: 8
            Repeater {
                model: [["←→↑↓", "Navigate"], ["↵", "Open"], ["Esc", "Close"], ["Two-finger click", "Open selected"]]
                Row {
                    required property var modelData
                    spacing: 6
                    Rectangle {
                        width: Math.max(22, keyLabel.implicitWidth + 12); height: 22; radius: 6
                        color: Qt.rgba(1, 1, 1, 0.08); border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.14)
                        Text { id: keyLabel; anchors.centerIn: parent; text: parent.parent.modelData[0]; color: Theme.textSoft; font.family: Theme.font; font.pixelSize: 12; font.weight: Font.Medium }
                    }
                    Text { anchors.verticalCenter: parent.verticalCenter; text: parent.modelData[1]; color: Theme.textSoft; font.family: Theme.font; font.pixelSize: 13; rightPadding: 6 }
                }
            }
        }
        Flickable {
            id: scroller
            anchors { top: heading.bottom; topMargin: 28; bottom: parent.bottom; bottomMargin: 36; left: parent.left; right: parent.right; leftMargin: Math.max(36, root.width * 0.055); rightMargin: Math.max(36, root.width * 0.055) }
            contentHeight: grid.height; clip: root.reveal > 0.995; boundsBehavior: Flickable.StopAtBounds
            WheelHandler {
                target: null
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                orientation: Qt.Vertical
                onWheel: event => root.navigateScroll(event, false)
            }
            WheelHandler {
                target: null
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                orientation: Qt.Horizontal
                onWheel: event => root.navigateScroll(event, true)
            }
            Grid {
                id: grid
                columns: root.columns; spacing: 22
                readonly property real tileWidth: root.width < 700 ? scroller.width : Math.min((scroller.width - spacing * (columns - 1)) / columns, root.tileWidthFor(columns, scroller.width, scroller.height))
                width: columns * tileWidth + spacing * (columns - 1)
                x: Math.max(0, (scroller.width - width) / 2)
                Repeater {
                    id: workspaceRepeater
                    model: root.entries
                    delegate: Item {
                        id: tile
                        required property var modelData
                        required property int index
                        readonly property bool scratchpad: String(modelData.name).startsWith("special:")
                        property real selectionEmphasis: root.selection === index ? 1 : 0
                        Behavior on selectionEmphasis { NumberAnimation { duration: Theme.motionBounce * 0.7; easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.bounceCurve } }
                        z: root.selection === index ? 10 : 0
                        readonly property point screenPoint: Qt.point(scroller.x + tile.x + tile.width / 2, scroller.y + tile.y - scroller.contentY + preview.height / 2)
                        transform: [
                            Scale { origin.x: tile.width / 2; origin.y: preview.height / 2; xScale: root.selection === tile.index ? 1 + (1 - root.reveal) * (root.width / tile.width - 1) : 1; yScale: root.selection === tile.index ? 1 + (1 - root.reveal) * (root.height / preview.height - 1) : 1 },
                            Translate { x: root.selection === tile.index ? (1 - root.reveal) * (root.width / 2 - tile.screenPoint.x) : 0; y: root.selection === tile.index ? (1 - root.reveal) * (root.height / 2 - tile.screenPoint.y) : 0 },
                            Scale { origin.x: tile.width / 2; origin.y: preview.height / 2; xScale: 1 + 0.025 * tile.selectionEmphasis; yScale: xScale }
                        ]
                        width: grid.tileWidth
                        height: preview.height + 37
                        Rectangle {
                            id: preview
                            width: parent.width; height: width * (root.modelData ? root.modelData.height / root.modelData.width : 0.625)
                            radius: 16; color: Theme.desktopBackground; clip: true
                            Image { anchors.fill: parent; source: Theme.wallpaper ? (Theme.wallpaper.startsWith("/") ? "file://" + Theme.wallpaper : Theme.wallpaper) : ""; fillMode: Image.PreserveAspectCrop; asynchronous: true }
                            Rectangle { anchors.fill: parent; color: "#22000000" }
                            Rectangle { anchors.fill: parent; color: "#282d1d4e"; visible: tile.scratchpad }
                            Repeater {
                                model: tile.modelData.windows
                                delegate: Item {
                                    id: windowTile
                                    z: 1
                                    required property var modelData
                                    readonly property var info: modelData.lastIpcObject || ({})
                                    readonly property var mon: modelData.monitor
                                    readonly property real mw: mon && mon.width ? mon.width / (mon.scale || 1) : 1920
                                    readonly property real mh: mon && mon.height ? mon.height / (mon.scale || 1) : 1080
                                    readonly property real mx: mon ? mon.x : 0
                                    readonly property real my: mon ? mon.y : 0
                                    x: Math.max(0, ((info.at || [0,0])[0] - mx) / mw * preview.width)
                                    y: Math.max(0, ((info.at || [0,0])[1] - my) / mh * preview.height)
                                    width: Math.max(48, Math.min(preview.width - x, ((info.size || [mw,mh])[0] / mw) * preview.width))
                                    height: Math.max(32, Math.min(preview.height - y, ((info.size || [mw,mh])[1] / mh) * preview.height))
                                    Rectangle { anchors.fill: parent; radius: 6; color: "#e52b2932" }
                                    Rectangle { anchors.fill: parent; radius: 6; color: "transparent"; border.width: windowPointer.containsMouse ? 2 : 1; border.color: windowPointer.containsMouse ? "#ffffff" : "#88ffffff"; z: 2 }
                                    // Freeze the last frame while the selected tile expands on exit.
                                    // Release the source once the transition finishes, or immediately
                                    // when its monitor disappears.
                                    ScreencopyView { id: capture; anchors.fill: parent; anchors.margins: 2; captureSource: root.visible && windowTile.mon && Quickshell.screens.some(s => s && s.name === windowTile.mon.name) ? windowTile.modelData.wayland : null; live: root.opened; paintCursor: false }
                                    Image { id: fallbackIcon; anchors.horizontalCenter: parent.horizontalCenter; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: -10; width: 24; height: 24; visible: !capture.hasContent && source.toString().length > 0; source: Quickshell.iconPath(windowTile.info.class || "", true) || ""; fillMode: Image.PreserveAspectFit }
                                    Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.verticalCenter: parent.verticalCenter; anchors.verticalCenterOffset: fallbackIcon.visible ? 12 : 0; width: parent.width - 12; visible: !capture.hasContent; text: windowTile.modelData.title || windowTile.info.class || "Window"; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; color: "white"; font.family: Theme.font; font.pixelSize: 12 }
                                    Rectangle {
                                        z: 5
                                        visible: windowPointer.containsMouse && !windowPointer.draggingWindow
                                        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 6
                                        width: Math.min(parent.width - 8, hoverTitle.implicitWidth + 16); height: 22; radius: 11
                                        color: "#e6141418"
                                        Text { id: hoverTitle; anchors.centerIn: parent; width: parent.width - 16; text: windowTile.modelData.title || windowTile.info.class || "Window"; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; color: "white"; font.family: Theme.font; font.pixelSize: 11; font.weight: Font.Medium }
                                    }
                                    MouseArea {
                                        id: windowPointer
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                                        preventStealing: true
                                        property real startX: 0
                                        property real startY: 0
                                        property bool draggingWindow: false
                                        onPressed: mouse => { startX = mouse.x; startY = mouse.y; draggingWindow = false; }
                                        onPositionChanged: mouse => {
                                            if (!pressed || !(pressedButtons & Qt.LeftButton)) return;
                                            if (!draggingWindow && Math.hypot(mouse.x - startX, mouse.y - startY) > 10) { draggingWindow = true; selectionScroll.stop(); }
                                            if (draggingWindow) {
                                                root.updateDrop(windowTile, mouse.x, mouse.y);
                                                root.dragPoint = keyTarget.mapFromItem(windowTile, mouse.x, mouse.y);
                                                root.dragTitle = windowTile.modelData.title || windowTile.info.class || "Window";
                                            }
                                        }
                                        onReleased: mouse => {
                                            const address = windowTile.modelData.address || "";
                                            // A two-finger click opens the workspace chosen by two-finger scrolling,
                                            // not the one under the pointer.
                                            if (mouse.button === Qt.RightButton) { if (containsMouse) root.openWorkspace(root.selection); }
                                            else if (draggingWindow) root.finishDrop(address, tile.modelData.target);
                                            else if (containsMouse) { root.selection = tile.index; root.windowRequested(tile.modelData.target, address); }
                                            draggingWindow = false; root.dragTitle = "";
                                        }
                                        onCanceled: { draggingWindow = false; root.dropIndex = -1; root.dragTitle = ""; }
                                    }
                                }
                            }
                            MouseArea { anchors.fill: parent; z: 0; acceptedButtons: Qt.LeftButton | Qt.RightButton; onClicked: mouse => root.openWorkspace(mouse.button === Qt.RightButton ? root.selection : tile.index) }
                        }
                        Rectangle {
                            anchors.fill: preview
                            radius: preview.radius
                            color: "transparent"
                            border.width: root.dropIndex === tile.index ? 5 : 1 + 4 * tile.selectionEmphasis
                            border.color: root.dropIndex === tile.index ? "#ffffff" : root.selection === tile.index ? "#ffffff" : tile.scratchpad ? "#c4a8e8" : Theme.borderSoft
                            z: 3
                        }
                        Rectangle {
                            anchors.right: preview.right; anchors.top: preview.top; anchors.margins: 10
                            width: scratchText.implicitWidth + 22; height: 26; radius: 8
                            color: "#e635284b"; visible: tile.scratchpad; z: 4
                            Text { id: scratchText; anchors.centerIn: parent; text: "SCRATCHPAD"; color: "#f0dcff"; font.family: Theme.font; font.pixelSize: 11; font.bold: true; font.letterSpacing: 0.7 }
                        }
                        Text { anchors.left: parent.left; anchors.top: preview.bottom; anchors.topMargin: 10; text: tile.modelData.name.startsWith("special:") ? tile.modelData.name.slice(8) + " · Scratchpad" : "Workspace " + tile.modelData.name; color: root.selection === tile.index ? Theme.textMain : Theme.textSoft; font.family: Theme.font; font.pixelSize: 14; font.weight: root.selection === tile.index ? Font.DemiBold : Font.Normal }
                        Row {
                            anchors.right: parent.right; anchors.top: preview.bottom; anchors.topMargin: 8
                            spacing: 4
                            Repeater {
                                model: (tile.modelData.windows || []).slice(0, 5)
                                Image {
                                    required property var modelData
                                    width: 20; height: 20; sourceSize: Qt.size(40, 40); asynchronous: true
                                    source: Quickshell.iconPath(String((modelData.lastIpcObject || {}).class || ""), true) || ""
                                    visible: status === Image.Ready
                                }
                            }
                            Text { visible: Quickshell.screens.length > 1; text: tile.modelData.monitor; color: Theme.textSoft; font.family: Theme.font; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        }
                    }
                }
            }
        }
        Rectangle {
            z: 100; visible: root.dragTitle.length > 0
            x: Math.max(0, Math.min(keyTarget.width - width, root.dragPoint.x + 14))
            y: Math.max(0, Math.min(keyTarget.height - height, root.dragPoint.y + 14))
            width: 220; height: 40; radius: 10; color: Theme.glassFill
            border.width: 1; border.color: Theme.accentBlue
            Text { anchors.fill: parent; anchors.margins: 10; text: root.dragTitle; color: Theme.textMain; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter; font.family: Theme.font }
        }
    }
}
