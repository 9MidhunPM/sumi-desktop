pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "config"
import "services" as S
import "components" as C

C.Surface {
    id: root
    required property var app
    width: Math.min(620, Math.max(1, app.activeScreen ? app.activeScreen.width - 48 : 620))
    height: Math.min(680, Math.max(1, app.activeScreen ? app.activeScreen.height - 48 : 680))
    property var priorityTexts: ["", "", ""]
    property var priorityDone: [false, false, false]
    property var enabledDraft: ({clock: true, spotify: true, priorities: true, deadline: true})
    property string message: ""
    property bool saveRequested: false
    property bool dirty: false
    readonly property bool compact: width < 500

    function activatePanel() { restoreDraft(); }
    function focusDefault() { const row = priorityRows.itemAt(0); if (row) row.field.forceActiveFocus(Qt.OtherFocusReason); }
    function restoreDraft() {
        const value = S.Widgets.document;
        priorityTexts = value.priorities.map(item => item.text);
        priorityDone = value.priorities.map(item => item.done);
        enabledDraft = Object.assign({}, value.enabled);
        deadlineTitle.text = value.deadline.title;
        const date = value.deadline.at === null ? null : new Date(value.deadline.at);
        deadlineDate.text = date ? Qt.formatDateTime(date, "yyyy-MM-dd") : "";
        deadlineTime.text = date ? Qt.formatDateTime(date, "HH:mm") : "17:00";
        dirty = false;
        message = "";
    }
    function reveal(item) {
        if (!item.activeFocus) return;
        Qt.callLater(function() {
            const flick = body.contentItem;
            const point = item.mapToItem(flick.contentItem, 0, 0);
            let target = flick.contentY;
            if (point.y < target + 8) target = point.y - 8;
            else if (point.y + item.height > target + flick.height - 8) target = point.y + item.height - flick.height + 8;
            flick.contentY = Math.max(0, Math.min(Math.max(0, flick.contentHeight - flick.height), target));
        });
    }
    function parseDeadline(dateText, timeText) {
        if (!dateText.trim()) return {ok: true, at: null};
        const date = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateText.trim());
        const time = /^(\d{2}):(\d{2})$/.exec(timeText.trim());
        if (!date || !time) return {ok: false, message: "Use YYYY-MM-DD and a 24-hour time such as 17:00."};
        const y = Number(date[1]), m = Number(date[2]) - 1, d = Number(date[3]), h = Number(time[1]), n = Number(time[2]);
        const result = new Date(y, m, d, h, n, 0, 0);
        if (result.getFullYear() !== y || result.getMonth() !== m || result.getDate() !== d
            || result.getHours() !== h || result.getMinutes() !== n || result.getTime() < 0)
            return {ok: false, message: "Choose a valid local date and time."};
        return {ok: true, at: result.getTime()};
    }
    function save() {
        const deadline = parseDeadline(deadlineDate.text, deadlineTime.text);
        if (!deadline.ok) { message = deadline.message; deadlineDate.forceActiveFocus(); return; }
        const value = JSON.parse(JSON.stringify(S.Widgets.document));
        value.enabled = Object.assign({}, enabledDraft);
        value.priorities = priorityTexts.map((text, index) => ({text: text.trim(), done: text.trim() ? priorityDone[index] : false}));
        value.deadline = {title: deadlineTitle.text.trim(), at: deadline.at};
        saveRequested = true;
        if (!S.Widgets.saveDocument(value)) { saveRequested = false; message = S.Widgets.error; }
    }
    Component.onCompleted: restoreDraft()
    Connections { target: S.Widgets; function onLoadedChanged() { if (S.Widgets.loaded && !root.dirty) root.restoreDraft(); } function onSaved(ok) { if (root.saveRequested) { root.saveRequested = false; root.message = ok ? "Saved" : S.Widgets.error; if (ok) root.dirty = false; } } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compact ? 18 : 24
        spacing: 16
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                C.Label { text: "Your desktop"; font.pixelSize: 25; font.weight: Font.DemiBold; Layout.fillWidth: true }
                C.Label { text: "A few things worth keeping in sight."; color: Theme.textSoft; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
            C.ActionButton { text: "×"; tooltip: "Close widgets"; objectName: "widgetsClose"; quiet: true; font.pixelSize: 20; onClicked: root.app.close() }
        }
        ScrollView {
            id: body
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            contentWidth: availableWidth
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                width: body.availableWidth
                spacing: 12
                C.Label { text: "Daily priorities"; font.pixelSize: 16; font.weight: Font.DemiBold }
                Repeater {
                    id: priorityRows
                    model: 3
                    RowLayout {
                        id: priorityRow
                        required property int index
                        readonly property var field: priorityInput
                        Layout.fillWidth: true
                        spacing: 10
                        CheckBox {
                            id: done
                            objectName: "widgetsDone" + priorityRow.index
                            checked: root.priorityDone[priorityRow.index]
                            Accessible.name: "Priority " + (priorityRow.index + 1) + " completed"
                            activeFocusOnTab: true
                            onActiveFocusChanged: if (activeFocus) root.reveal(done)
                            onClicked: { const next = root.priorityDone.slice(); next[priorityRow.index] = checked; root.priorityDone = next; root.dirty = true; }
                            indicator: Rectangle { implicitWidth: 22; implicitHeight: 22; x: done.leftPadding; y: (done.height - height) / 2; radius: 6; color: done.checked ? Theme.accentBlue : "transparent"; border.width: done.visualFocus ? 2 : 1; border.color: Theme.accentBlue; C.Label { anchors.centerIn: parent; text: done.checked ? "✓" : ""; color: Theme.desktopBackground } }
                        }
                        TextField {
                            id: priorityInput
                            objectName: "widgetsPriority" + priorityRow.index
                            Layout.fillWidth: true
                            implicitHeight: 42
                            maximumLength: 180
                            text: root.priorityTexts[priorityRow.index]
                            placeholderText: "Priority " + (priorityRow.index + 1)
                            color: Theme.textMain
                            placeholderTextColor: Theme.textSoft
                            selectionColor: Theme.accentBlue
                            selectedTextColor: Theme.desktopBackground
                            font.family: Theme.font
                            padding: 10
                            Accessible.name: placeholderText
                            onActiveFocusChanged: if (activeFocus) root.reveal(priorityInput)
                            onTextEdited: { const next = root.priorityTexts.slice(); next[priorityRow.index] = text; root.priorityTexts = next; root.dirty = true; }
                            background: C.Surface { radius: 10; color: Theme.bgPanel; border.width: priorityInput.activeFocus ? 2 : 1; border.color: priorityInput.activeFocus ? Theme.accentBlue : Theme.borderSoft }
                        }
                    }
                }
                C.ActionButton {
                    text: "Clear completed"; quiet: true; enabled: root.priorityDone.some(value => value)
                    onActiveFocusChanged: if (activeFocus) root.reveal(this)
                    onClicked: { root.priorityTexts = root.priorityTexts.map((text, index) => root.priorityDone[index] ? "" : text); root.priorityDone = [false, false, false]; root.dirty = true; }
                }
                C.Label { text: "Next deadline"; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.topMargin: 8 }
                TextField {
                    id: deadlineTitle
                    objectName: "widgetsDeadlineTitle"
                    Layout.fillWidth: true
                    implicitHeight: 42
                    maximumLength: 160
                    placeholderText: "What are you working towards?"
                    color: Theme.textMain; placeholderTextColor: Theme.textSoft; font.family: Theme.font; padding: 10
                    Accessible.name: "Deadline title"
                    onTextEdited: root.dirty = true
                    onActiveFocusChanged: if (activeFocus) root.reveal(deadlineTitle)
                    background: C.Surface { radius: 10; color: Theme.bgPanel; border.width: deadlineTitle.activeFocus ? 2 : 1; border.color: deadlineTitle.activeFocus ? Theme.accentBlue : Theme.borderSoft }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    TextField {
                        id: deadlineDate
                        objectName: "widgetsDeadlineDate"
                        Layout.fillWidth: true
                        implicitHeight: 42
                        maximumLength: 10
                        placeholderText: "YYYY-MM-DD"
                        color: Theme.textMain; placeholderTextColor: Theme.textSoft; font.family: Theme.fontMono; padding: 10
                        Accessible.name: "Deadline date, year month day"
                        onTextEdited: root.dirty = true
                        onActiveFocusChanged: if (activeFocus) root.reveal(deadlineDate)
                        background: C.Surface { radius: 10; color: Theme.bgPanel; border.width: deadlineDate.activeFocus ? 2 : 1; border.color: deadlineDate.activeFocus ? Theme.accentBlue : Theme.borderSoft }
                    }
                    TextField {
                        id: deadlineTime
                        objectName: "widgetsDeadlineTime"
                        Layout.preferredWidth: 92
                        implicitHeight: 42
                        maximumLength: 5
                        placeholderText: "17:00"
                        color: Theme.textMain; placeholderTextColor: Theme.textSoft; font.family: Theme.fontMono; padding: 10
                        Accessible.name: "Deadline time, 24 hour"
                        onTextEdited: root.dirty = true
                        onActiveFocusChanged: if (activeFocus) root.reveal(deadlineTime)
                        background: C.Surface { radius: 10; color: Theme.bgPanel; border.width: deadlineTime.activeFocus ? 2 : 1; border.color: deadlineTime.activeFocus ? Theme.accentBlue : Theme.borderSoft }
                    }
                }
                C.ActionButton { text: "Clear deadline"; quiet: true; onActiveFocusChanged: if (activeFocus) root.reveal(this); onClicked: { deadlineTitle.clear(); deadlineDate.clear(); root.dirty = true; } }
                C.Label { text: "Visible widgets"; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.topMargin: 8 }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Repeater {
                        model: [{key: "clock", title: "Clock"}, {key: "spotify", title: "Spotify"}, {key: "priorities", title: "Priorities"}, {key: "deadline", title: "Deadline"}]
                        C.ActionButton {
                            required property var modelData
                            objectName: "widgetsEnabled" + modelData.key
                            text: modelData.title
                            selected: root.enabledDraft[modelData.key]
                            Accessible.checkable: true
                            Accessible.checked: selected
                            onActiveFocusChanged: if (activeFocus) root.reveal(this)
                            onClicked: { const next = Object.assign({}, root.enabledDraft); next[modelData.key] = !next[modelData.key]; root.enabledDraft = next; root.dirty = true; }
                        }
                    }
                }
                C.Label { text: "Placement follows your wallpaper. Change its layout in Appearance."; color: Theme.textSoft; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            C.Label { objectName: "widgetsMessage"; text: root.message || S.Widgets.error || "Saved privately on this computer"; color: root.message === "Saved" ? Theme.accentCyan : Theme.textSoft; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
            C.ActionButton { objectName: "widgetsSave"; text: S.Widgets.saving ? "Saving…" : "Save"; selected: true; enabled: S.Widgets.loaded && !S.Widgets.saving; onClicked: root.save() }
        }
    }
}
