pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell.Io
import "config"
import "services" as S
import "components" as C

C.Surface {
    id: root
    required property var app
    property string kind: "calendar"
    property string pendingPower: ""
    property double now: Date.now()
    readonly property bool compactCalendar: app.activeScreen && app.activeScreen.height < 700
    function activatePanel() {
        pendingPower = "";
        now = Date.now();
        if (kind === "help" && !shortcutReader.running) shortcutReader.running = true;
    }
    function focusDefault() {
        let target = body;
        if (kind === "media" && S.Media.available) target = playButton;
        else if (kind === "pomodoro") target = focusStartButton;
        else if (kind === "power") target = powerActions.itemAt(0) || body;
        else if (kind === "notifications") target = dndButton;
        body.contentItem.contentY = 0;
        target.forceActiveFocus(Qt.OtherFocusReason);
        body.revealItem(target);
    }
    readonly property string heading: ({calendar:"Today",media:"Now playing",notifications:"Notifications",pomodoro:"A focused moment",power:"Session",help:"Keyboard shortcuts"})[kind] || "Sumi"
    property var shortcuts: []
    property string shortcutsError: ""
    width: Math.min(kind === "help" ? 640 : 480, Math.max(1, app.activeScreen ? app.activeScreen.width - 48 : 640))
    height: Math.min(header.implicitHeight + bodyContent.implicitHeight + 56, kind === "help" ? 650 : 610,
        Math.max(1, app.activeScreen ? app.activeScreen.height - (["calendar", "media", "notifications"].indexOf(kind) >= 0 ? Theme.panelTop + 24 : 48) : 650))
    Process {
        id: shortcutReader
        command: [S.Desktop.controller, "shortcuts", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const data = JSON.parse(text);
                    if (!Array.isArray(data.shortcuts)) throw new Error("Invalid shortcut list");
                    root.shortcuts = data.shortcuts;
                    root.shortcutsError = "";
                } catch (error) { root.shortcutsError = "Keyboard shortcuts could not be loaded."; }
            }
        }
        onExited: code => { if (code !== 0) root.shortcutsError = "Keyboard shortcuts could not be loaded."; }
    }
    Timer { interval: 1000; repeat: true; running: root.visible && root.kind === "pomodoro" && root.app.focusRunning; onTriggered: root.now = Date.now() }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 16
        RowLayout {
            id: header
            Layout.fillWidth: true
            C.Label { text: root.heading; Layout.fillWidth: true; font.pixelSize: 22; font.weight: Font.DemiBold }
            C.ActionButton { id: closeButton; objectName: "dashboardClose"; text: "×"; font.pixelSize: 20; tooltip: "Close panel · Esc"; quiet: true; onClicked: root.app.close() }
        }
        C.PanelScrollView {
            id: body
            objectName: "dashboardBody"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            ColumnLayout {
                id: bodyContent
                width: body.availableWidth
                spacing: 16
                ColumnLayout {
                    visible: root.kind === "calendar"
                    Layout.fillWidth: true
                    spacing: root.compactCalendar ? 10 : 14
                    C.Label { text: Qt.formatDateTime(S.Clock.date,"dddd, d MMMM yyyy"); color: Theme.textSoft }
                    C.Label { text: S.Clock.accessibleTime; font.pixelSize: root.compactCalendar ? 44 : 52; font.weight: Font.Light }
                    GridLayout {
                        columns: 7
                        Layout.fillWidth: true
                        rowSpacing: root.compactCalendar ? 4 : 6
                        columnSpacing: 6
                        Repeater { model: ["M","T","W","T","F","S","S"]; C.Label { required property string modelData; text: modelData; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; color: Theme.textSoft; font.pixelSize: 12 } }
                        Repeater {
                            model: 42
                            Rectangle {
                                required property int index
                                readonly property int offset: (new Date(S.Clock.date.getFullYear(),S.Clock.date.getMonth(),1).getDay() + 6) % 7
                                readonly property int day: index - offset + 1
                                readonly property int days: new Date(S.Clock.date.getFullYear(),S.Clock.date.getMonth()+1,0).getDate()
                                readonly property bool today: day === S.Clock.date.getDate()
                                Layout.fillWidth: true
                                implicitHeight: root.compactCalendar ? 26 : 30
                                radius: 8
                                color: today ? Theme.accentBlue : "transparent"
                                C.Label { anchors.centerIn: parent; text: parent.day > 0 && parent.day <= parent.days ? parent.day : ""; color: parent.today ? Theme.desktopBackground : Theme.textMain }
                            }
                        }
                    }
                    C.ActionButton { id: focusSessionButton; objectName: "calendarFocusSession"; text: "󰔟  Start a focus session"; Layout.fillWidth: true; onClicked: root.app.open("pomodoro",null) }
                }
                ColumnLayout {
                    visible: root.kind === "media"
                    Layout.fillWidth: true
                    spacing: 18
                    Image { visible: status === Image.Ready; Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: 160; Layout.preferredHeight: 160; source: S.Media.artUrl; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(360,360) }
                    C.Label { text: S.Media.title || "Nothing playing"; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 20 }
                    C.Label { visible: text.length > 0; text: S.Media.artist; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; color: Theme.textSoft }
                    RowLayout { Layout.alignment: Qt.AlignHCenter; spacing: 18
                        C.ActionButton { text: "󰒮"; font.pixelSize: 20; tooltip: "Previous track"; enabled: S.Media.available; onClicked: S.Media.previous() }
                        C.ActionButton { id: playButton; objectName: "mediaPlay"; tooltip: S.Media.playing ? "Pause playback" : "Play"; enabled: S.Media.available; iconName: S.Media.playing ? "pause" : "play"; selected: true; onClicked: S.Media.toggle() }
                        C.ActionButton { text: "󰒭"; font.pixelSize: 20; tooltip: "Next track"; enabled: S.Media.available; onClicked: S.Media.next() }
                    }
                }
                ColumnLayout {
                    visible: root.kind === "pomodoro"
                    Layout.fillWidth: true
                    spacing: 18
                    C.Label { text: "One thing at a time."; color: Theme.textSoft; Layout.alignment: Qt.AlignHCenter }
                    C.Label {
                        readonly property int remaining: root.app.focusRunning ? Math.max(0,Math.ceil((root.app.focusDeadline-root.now)/1000)) : Math.ceil(root.app.focusRemaining/1000)
                        text: Math.floor(remaining/60).toString().padStart(2,"0") + ":" + (remaining%60).toString().padStart(2,"0")
                        font.family: Theme.fontMono
                        font.pixelSize: 64
                        Layout.alignment: Qt.AlignHCenter
                    }
                    RowLayout { Layout.alignment: Qt.AlignHCenter
                        C.ActionButton { text: "25 min"; onClicked: root.app.focusReset(25) }
                        C.ActionButton { text: "50 min"; onClicked: root.app.focusReset(50) }
                        C.ActionButton { text: "5 min break"; onClicked: root.app.focusReset(5) }
                    }
                    C.ActionButton { id: focusStartButton; objectName: "pomodoroStart"; text: root.app.focusRunning ? "Pause" : "Begin"; selected: true; Layout.fillWidth: true; onClicked: { if (root.app.focusRunning) root.app.focusPause(); else root.app.focusStart(); root.now = Date.now(); } }
                    C.Label { text: "You can close this panel. We’ll let you know when it’s time."; wrapMode: Text.Wrap; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; color: Theme.textSoft; font.pixelSize: 12 }
                }
                ColumnLayout {
                    visible: root.kind === "power"
                    Layout.fillWidth: true
                    spacing: 12
                    Repeater {
                        id: powerActions
                        model: [{id:"suspend",name:"󰤄  Suspend"},{id:"logout",name:"󰍃  Log out"},{id:"reboot",name:"󰜉  Restart"},{id:"shutdown",name:"󰐥  Shut down"}]
                        C.ActionButton { required property var modelData; text: modelData.name; Layout.fillWidth: true; selected: root.pendingPower === modelData.id; onClicked: root.pendingPower = modelData.id }
                    }
                    C.ActionButton { visible: root.pendingPower.length > 0; text: "Confirm " + root.pendingPower; Layout.fillWidth: true; onClicked: { const action = root.pendingPower; root.app.close(); S.Desktop.action("power",[action]); } }
                    C.Label { text: "Applications close gracefully before logout, restart or shutdown."; color: Theme.textSoft; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true }
                }
                ColumnLayout {
                    visible: root.kind === "help"
                    Layout.fillWidth: true
                    spacing: 12
                    C.Label { visible: root.shortcutsError.length > 0; text: root.shortcutsError; color: Theme.accentWarn; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Repeater {
                        model: root.shortcuts
                        ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 3
                            C.Label { text: Array.isArray(parent.modelData.keys) ? parent.modelData.keys.join(" / ") : parent.modelData.keys; font.family: Theme.fontMono; font.pixelSize: 12; color: Theme.accentBlue; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            C.Label { text: parent.modelData.label; Layout.fillWidth: true; font.pixelSize: 13; wrapMode: Text.Wrap }
                        }
                    }
                    C.Label { text: "Esc · Close the current panel"; color: Theme.textSoft; Layout.fillWidth: true }
                }
                ColumnLayout {
                    visible: root.kind === "notifications"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    RowLayout { Layout.fillWidth: true
                        C.ActionButton { id: dndButton; objectName: "notificationsDnd"; text: Settings.dnd ? "Do Not Disturb on" : "Do Not Disturb off"; selected: Settings.dnd; onClicked: S.Notifications.toggleDnd() }
                        Item { Layout.fillWidth: true }
                        C.ActionButton { text: "Clear all"; quiet: true; onClicked: S.Notifications.clear() }
                    }
                    C.Label { visible: S.Notifications.storageError.length > 0; text: S.Notifications.storageError; color: Theme.accentWarn; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
                    ListView {
                        id: notificationList
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.min(420, Math.max(120, contentHeight))
                        spacing: 12
                        clip: true
                        model: S.Notifications.history
                        ScrollBar.vertical: ScrollBar {}
                        delegate: C.Surface {
                            id: note
                            required property var modelData
                            width: notificationList.width
                            implicitHeight: noteBody.implicitHeight + 24
                            ColumnLayout {
                                id: noteBody
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 7
                                RowLayout { Layout.fillWidth: true
                                    C.Label { text: note.modelData.appName; Layout.fillWidth: true; color: Theme.textSoft; font.pixelSize: 11 }
                                    C.ActionButton { text: "×"; font.pixelSize: 18; tooltip: "Dismiss notification"; quiet: true; implicitHeight: 24; onClicked: S.Notifications.dismiss(note.modelData.id) }
                                }
                                C.Label { text: note.modelData.summary; font.weight: Font.DemiBold; wrapMode: Text.Wrap; Layout.fillWidth: true }
                                C.Label { text: note.modelData.body; color: Theme.textSoft; wrapMode: Text.Wrap; maximumLineCount: 5; Layout.fillWidth: true; font.pixelSize: 13 }
                                Flow { Layout.fillWidth: true; spacing: 5; Repeater { model: note.modelData.actions; C.ActionButton { required property string modelData; required property int index; text: modelData; onClicked: S.Notifications.invoke(note.modelData.id,index) } } }
                            }
                        }
                        C.Label { visible: S.Notifications.count === 0; anchors.centerIn: parent; text: "All caught up"; color: Theme.textSoft }
                    }
                }
            }
        }
    }
}
