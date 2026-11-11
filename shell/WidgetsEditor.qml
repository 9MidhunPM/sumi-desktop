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
    property bool embedded: false
    island: embedded
    readonly property color foreground: embedded ? IslandStyle.text : Theme.textMain
    readonly property color secondary: embedded ? IslandStyle.secondary : Theme.textSoft
    readonly property color accent: embedded ? IslandStyle.accent : Theme.accentBlue
    readonly property color accentForeground: embedded ? IslandStyle.accentText : Theme.desktopBackground
    readonly property color separator: embedded ? IslandStyle.line : Theme.borderSoft
    readonly property real contentHeight: formContent.implicitHeight + formFooter.implicitHeight + 16
        + (embedded ? 0 : formHeader.implicitHeight + 52)
    property bool pageActive: visible
    inset: embedded
    color: embedded ? "transparent" : Theme.glassFill
    border.width: embedded ? 0 : Theme.borderWidth
    enabled: !embedded || pageActive
    width: Math.min(620, Math.max(1, app.activeScreen ? app.activeScreen.width - 48 : 620))
    height: Math.min(680, Math.max(1, app.activeScreen ? app.activeScreen.height - 48 : 680))
    property var priorityTexts: ["", "", ""]
    property var priorityDone: [false, false, false]
    property var enabledDraft: ({clock: true, spotify: true, priorities: true, deadline: true})
    property string message: ""
    property bool saveRequested: false
    property bool dirty: false
    readonly property bool compact: width < 500
    property bool draftReady: false
    property bool restoringSessionDraft: false
    readonly property var session: embedded && typeof app.islandSession !== "undefined" ? app.islandSession : null
    function persistSessionDraft() {
        if (!draftReady || restoringSessionDraft || !session || !pageActive) return;
        session.save("widgetsDraft", {
            priorityTexts: priorityTexts.slice(), priorityDone: priorityDone.slice(),
            enabled: Object.assign({}, enabledDraft), title: deadlineTitle.text,
            date: deadlineDate.text, time: deadlineTime.text, dirty: dirty
        });
    }
    function resumeSessionDraft() {
        const value = session && session.savedPages ? session.savedPages.widgetsDraft : null;
        if (!value) return false;
        restoringSessionDraft = true;
        priorityTexts = value.priorityTexts.slice(); priorityDone = value.priorityDone.slice();
        enabledDraft = Object.assign({}, value.enabled);
        deadlineTitle.text = value.title; deadlineDate.text = value.date; deadlineTime.text = value.time;
        dirty = value.dirty === true;
        restoringSessionDraft = false;
        return true;
    }
    onPriorityTextsChanged: persistSessionDraft()
    onPriorityDoneChanged: persistSessionDraft()
    onEnabledDraftChanged: persistSessionDraft()
    onDirtyChanged: persistSessionDraft()
    onPageActiveChanged: if (draftReady && pageActive) resumeSessionDraft()

    function activatePanel() { if (!resumeSessionDraft() && !dirty) restoreDraft(); }
    function focusDefault() { const row = priorityRows.itemAt(0); if (row) row.field.forceActiveFocus(Qt.OtherFocusReason); }
    function restoreDraft() {
        restoringSessionDraft = true;
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
        restoringSessionDraft = false;
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
    Component.onCompleted: { restoreDraft(); resumeSessionDraft(); draftReady = true; }
    Connections { target: S.Widgets; function onLoadedChanged() { if (S.Widgets.loaded && !root.dirty) root.restoreDraft(); } function onSaved(ok) { if (root.saveRequested) { root.saveRequested = false; root.message = ok ? "Saved" : S.Widgets.error; if (ok) root.dirty = false; } } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.embedded ? 0 : root.compact ? 18 : 24
        spacing: Metrics.space4
        RowLayout {
            id: formHeader
            visible: !root.embedded
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                C.Label { color: root.foreground; text: "Your desktop"; font.pixelSize: 25; font.weight: Font.DemiBold; Layout.fillWidth: true }
                C.Label { text: "A few things worth keeping in sight."; color: root.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
            C.ActionButton { island: root.embedded; text: "×"; tooltip: "Close widgets"; objectName: "widgetsClose"; quiet: true; font.pixelSize: 20; onClicked: root.app.close() }
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
                id: formContent
                width: body.availableWidth
                spacing: Metrics.space3
                C.Label { color: root.foreground; text: "Daily priorities"; font.pixelSize: 16; font.weight: Font.DemiBold }
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
                            indicator: Rectangle { implicitWidth: 22; implicitHeight: 22; x: done.leftPadding; y: (done.height - height) / 2; radius: 6; color: done.checked ? root.accent : "transparent"; border.width: done.visualFocus ? 2 : 1; border.color: root.accent; C.Label { anchors.centerIn: parent; text: done.checked ? "✓" : ""; color: root.accentForeground } }
                        }
                        TextField {
                            id: priorityInput
                            objectName: "widgetsPriority" + priorityRow.index
                            Layout.fillWidth: true
                            implicitHeight: 42
                            maximumLength: 180
                            text: root.priorityTexts[priorityRow.index]
                            placeholderText: "Priority " + (priorityRow.index + 1)
                            color: root.foreground
                            placeholderTextColor: root.secondary
                            selectionColor: root.accent
                            selectedTextColor: root.accentForeground
                            font.family: Theme.font
                            padding: 10
                            Accessible.name: placeholderText
                            onActiveFocusChanged: if (activeFocus) root.reveal(priorityInput)
                            onTextEdited: { const next = root.priorityTexts.slice(); next[priorityRow.index] = text; root.priorityTexts = next; root.dirty = true; }
                            background: C.Surface { island: root.embedded; inset: true; radius: IslandStyle.controlRadius; border.width: priorityInput.activeFocus ? 2 : 1; border.color: priorityInput.activeFocus ? root.accent : root.separator }
                        }
                    }
                }
                C.ActionButton { island: root.embedded;
                    text: "Clear completed"; quiet: true; enabled: root.priorityDone.some(value => value)
                    onActiveFocusChanged: if (activeFocus) root.reveal(this)
                    onClicked: { root.priorityTexts = root.priorityTexts.map((text, index) => root.priorityDone[index] ? "" : text); root.priorityDone = [false, false, false]; root.dirty = true; }
                }
                C.Label { color: root.foreground; text: "Next deadline"; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.topMargin: 8 }
                TextField {
                    id: deadlineTitle
                    onTextChanged: root.persistSessionDraft()
                    objectName: "widgetsDeadlineTitle"
                    Layout.fillWidth: true
                    implicitHeight: 42
                    maximumLength: 160
                    placeholderText: "What are you working towards?"
                    color: root.foreground; placeholderTextColor: root.secondary; font.family: Theme.font; padding: 10
                    Accessible.name: "Deadline title"
                    onTextEdited: root.dirty = true
                    onActiveFocusChanged: if (activeFocus) root.reveal(deadlineTitle)
                    background: C.Surface { island: root.embedded; inset: true; radius: IslandStyle.controlRadius; border.width: deadlineTitle.activeFocus ? 2 : 1; border.color: deadlineTitle.activeFocus ? root.accent : root.separator }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    TextField {
                        id: deadlineDate
                        onTextChanged: root.persistSessionDraft()
                        objectName: "widgetsDeadlineDate"
                        Layout.fillWidth: true
                        implicitHeight: 42
                        maximumLength: 10
                        placeholderText: "YYYY-MM-DD"
                        color: root.foreground; placeholderTextColor: root.secondary; font.family: Theme.fontMono; padding: 10
                        Accessible.name: "Deadline date, year month day"
                        onTextEdited: root.dirty = true
                        onActiveFocusChanged: if (activeFocus) root.reveal(deadlineDate)
                        background: C.Surface { island: root.embedded; inset: true; radius: IslandStyle.controlRadius; border.width: deadlineDate.activeFocus ? 2 : 1; border.color: deadlineDate.activeFocus ? root.accent : root.separator }
                    }
                    TextField {
                        id: deadlineTime
                        onTextChanged: root.persistSessionDraft()
                        objectName: "widgetsDeadlineTime"
                        Layout.preferredWidth: 92
                        implicitHeight: 42
                        maximumLength: 5
                        placeholderText: "17:00"
                        color: root.foreground; placeholderTextColor: root.secondary; font.family: Theme.fontMono; padding: 10
                        Accessible.name: "Deadline time, 24 hour"
                        onTextEdited: root.dirty = true
                        onActiveFocusChanged: if (activeFocus) root.reveal(deadlineTime)
                        background: C.Surface { island: root.embedded; inset: true; radius: IslandStyle.controlRadius; border.width: deadlineTime.activeFocus ? 2 : 1; border.color: deadlineTime.activeFocus ? root.accent : root.separator }
                    }
                }
                C.ActionButton { island: root.embedded; text: "Clear deadline"; quiet: true; onActiveFocusChanged: if (activeFocus) root.reveal(this); onClicked: { deadlineTitle.clear(); deadlineDate.clear(); root.dirty = true; } }
                C.Label { color: root.foreground; text: "Visible widgets"; font.pixelSize: 16; font.weight: Font.DemiBold; Layout.topMargin: 8 }
                Flow {
                    Layout.fillWidth: true
                    spacing: Metrics.space2
                    Repeater {
                        model: [{key: "clock", title: "Clock"}, {key: "spotify", title: "Spotify"}, {key: "priorities", title: "Priorities"}, {key: "deadline", title: "Deadline"}]
                        C.ActionButton { island: root.embedded;
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
                C.Label { text: "Placement follows your wallpaper. Change its layout in Appearance."; color: root.secondary; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
        }
        RowLayout {
            id: formFooter
            Layout.fillWidth: true
            spacing: Metrics.space3
            C.Label { objectName: "widgetsMessage"; text: root.message || S.Widgets.error || "Saved privately on this computer"; color: root.message === "Saved" ? Theme.accentCyan : root.secondary; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
            C.ActionButton { island: root.embedded; objectName: "widgetsSave"; text: S.Widgets.saving ? "Saving…" : "Save"; selected: true; enabled: S.Widgets.loaded && !S.Widgets.saving; onClicked: root.save() }
        }
    }
}
