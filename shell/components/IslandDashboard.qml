pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts
import "../services" as S
import "../config"

FocusScope {
    id: root
    required property var app
    property var screenInfo: null
    property string section: "home"
    property bool selectionAnimation: false
    property bool completed: false
    // Opening/resizing relayout must not sweep the selection across other tabs.
    onWidthChanged: selectionAnimation = false
    property bool active: false
    property double now: Date.now()
    property real mediaPosition: 0
    property var samples: []
    property int statsConsumer: 0
    function syncStatsDemand() { if (statsConsumer) S.SystemStats.setDemand(statsConsumer, active && (section === "home" || section === "controls")); }
    Component.onCompleted: { completed = true; statsConsumer = S.SystemStats.createConsumer(); syncStatsDemand(); }
    Component.onDestruction: if (statsConsumer) S.SystemStats.releaseConsumer(statsConsumer)
    readonly property var tabDeck: section === "calendar" ? null : pagesDeck
    readonly property var thursdayBackend: typeof app.thursdayBackend === "undefined" ? null : app.thursdayBackend
    readonly property real preferredWidth: section === "media" ? 520 : section === "inbox" ? 560 : section === "home" || section === "calendar" ? 600 : 640
    readonly property real preferredHeight: section === "controls" ? 52 + controlsScroll.contentHeight : section === "thursday" ? 500 : Math.max(220, 52 + (
        section === "calendar" ? calendarScroll.contentHeight : section === "home" ? homeScroll.contentHeight : section === "media" ? mediaScroll.contentHeight
        : 54 + (S.Notifications.count ? Math.max(100, inbox.contentHeight) : 88)))
    readonly property var inboxEntries: {
        const entries = S.Notifications.history.slice().sort((a, b) => String(a.appName).localeCompare(String(b.appName)) || new Date(b.time).getTime() - new Date(a.time).getTime());
        return entries.map((entry, index) => Object.assign({}, entry, {groupStart: index === 0 || entries[index - 1].appName !== entry.appName}));
    }
    readonly property string controlError: S.Brightness.error || S.Recording.error || S.NightLight.error
    signal sectionRequested(string section)
    signal dismissRequested()
    signal openPanelRequested(string panel)
    signal settingsRequested(string section)
    signal captureRequested(bool annotate)
    signal recordingRequested()
    signal thursdayFullChatRequested()

    function duration(milliseconds) {
        const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
        return Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2, "0");
    }
    function belongsTo(item, ancestor) {
        while (item) { if (item === ancestor) return true; item = item.parent; }
        return false;
    }
    function revealFocused() {
        if (!active || section === "thursday" || !root.Window.window) return;
        const item = root.Window.window.activeFocusItem;
        if (!item) return;
        const viewport = section === "inbox" ? inbox : (section === "calendar" ? calendarScroll : section === "home" ? homeScroll : section === "media" ? mediaScroll : section === "thursday" ? thursdayPage : controlsScroll).contentItem;
        if (!viewport || !belongsTo(item, viewport.contentItem)) return;
        const point = item.mapToItem(viewport.contentItem, 0, 0);
        if (point.y < viewport.contentY + 8) viewport.contentY = Math.max(0, point.y - 8);
        else if (point.y + item.height > viewport.contentY + viewport.height - 8)
            viewport.contentY = Math.min(Math.max(0, viewport.contentHeight - viewport.height), point.y + item.height - viewport.height + 8);
    }
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() { Qt.callLater(root.revealFocused); }
    }
    function focusDefault() {
        if (section === "calendar") { calendarBack.forceActiveFocus(Qt.OtherFocusReason); return; }
        const tab = section === "thursday" ? thursdayTab : section === "controls" ? controlsTab : section === "media" ? mediaTab : section === "inbox" ? inboxTab : homeTab;
        tab.forceActiveFocus(Qt.OtherFocusReason);
    }
    function refresh() { S.Brightness.refresh(); S.Recording.refresh(); S.NightLight.refresh(); }
    function markVisibleEntries() {
        if (!active || section !== "inbox" || pagesDeck.moving) return;
        const ids = [];
        for (const child of inbox.contentItem.children) {
            if (child.entry && child.entry.unread && child.y + child.height > inbox.contentY && child.y < inbox.contentY + inbox.height)
                ids.push(child.entry.id);
        }
        if (ids.length) S.Notifications.markEntriesRead(ids);
    }
    onActiveChanged: { if (active) refresh(); readVisible.restart(); syncStatsDemand(); }
    onSectionChanged: { selectionAnimation = completed && active; readVisible.restart(); syncStatsDemand(); if (active) Qt.callLater(root.focusDefault); }
    onInboxEntriesChanged: readVisible.restart()
    Timer { id: readVisible; interval: 120; onTriggered: root.markVisibleEntries() }
    Connections {
        target: pagesDeck
        function onMovingChanged() { if (!pagesDeck.moving) readVisible.restart(); }
    }
    Keys.onPressed: event => {
        if ((event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) && (event.modifiers & Qt.ControlModifier)) {
            if (root.section === "calendar") root.sectionRequested(event.modifiers & Qt.ShiftModifier ? "thursday" : "inbox");
            else pagesDeck.navigate(event.modifiers & Qt.ShiftModifier ? -1 : 1);
            event.accepted = true;
        }
    }
    Keys.onEscapePressed: event => { root.dismissRequested(); event.accepted = true; }

    component IslandButton: ActionButton {
        width: Math.min(implicitWidth, Math.max(1, root.width - 8))
        textColor: selected ? "#202027" : "#f3f3f7"
        implicitHeight: 34
        background: Rectangle {
            radius: 16
            color: parent.selected ? "#f6f6f8" : parent.down ? "#494a53" : parent.quiet ? parent.hovered ? "#303138" : "transparent" : "#292a30"
            border.width: parent.visualFocus ? 2 : 0
            border.color: "#ffffff"
        }
    }
    component TabButton: IslandButton {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        leftPadding: root.width < 380 ? 6 : 12
        rightPadding: leftPadding
        font.pixelSize: root.width < 380 ? 11 : 13
        quiet: true
        background: Rectangle {
            radius: 17
            color: parent.selected ? "transparent" : parent.down ? "#494a53" : parent.hovered ? "#303138" : "transparent"
            border.width: parent.visualFocus ? 2 : 0
            border.color: "#ffffff"
        }
    }
    component Caption: Label { color: "#bdbdc5"; font.pixelSize: 12 }
    component Rule: Rectangle { Layout.fillWidth: true; Layout.minimumWidth: 0; implicitHeight: 1; color: "#303034" }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Rectangle {
            id: tabTrack
            objectName: "islandTabTrack"
            readonly property var selectedTab: root.section === "thursday" ? thursdayTab : root.section === "controls" ? controlsTab : root.section === "media" ? mediaTab : root.section === "inbox" ? inboxTab : homeTab
            Layout.fillWidth: true
            implicitHeight: 40
            radius: 20
            color: "#222328"
            Rectangle {
                objectName: "islandTabSelection"
                x: tabTrack.selectedTab.x + 3; y: 3
                width: tabTrack.selectedTab.width; height: 34; radius: 17
                color: "#f6f6f8"
                Behavior on x { enabled: root.selectionAnimation; NumberAnimation { duration: Motion.music; easing.type: Easing.OutCubic } }
                Behavior on width { enabled: root.selectionAnimation; NumberAnimation { duration: Motion.music; easing.type: Easing.OutCubic } }
            }
            RowLayout {
                anchors.fill: parent
                anchors.margins: 3
                spacing: 2
            TabButton { id: homeTab; objectName: "islandTabHome"; text: root.width < 420 ? "" : "Home"; iconName: root.width < 420 ? "grid" : ""; tooltip: "Home"; quiet: true; selected: root.section === "home" || root.section === "calendar"; onClicked: root.sectionRequested("home") }
            TabButton { id: inboxTab; objectName: "islandTabInbox"; text: root.width < 420 ? "" : "Inbox" + (S.Notifications.unread ? " · " + S.Notifications.unread : ""); iconName: root.width < 420 ? "bell" : ""; tooltip: "Inbox"; quiet: true; selected: root.section === "inbox"; onClicked: root.sectionRequested("inbox") }
            TabButton { id: mediaTab; objectName: "islandTabMedia"; text: root.width < 420 ? "" : "Music"; iconName: root.width < 420 ? "music" : ""; tooltip: "Music"; quiet: true; selected: root.section === "media"; onClicked: root.sectionRequested("media") }
            TabButton { id: controlsTab; objectName: "islandTabControls"; text: root.width < 420 ? "" : "Controls"; iconName: root.width < 420 ? "settings" : ""; tooltip: "Controls"; quiet: true; selected: root.section === "controls"; onClicked: root.sectionRequested("controls") }
            TabButton { id: thursdayTab; objectName: "islandTabThursday"; text: root.width < 420 ? "" : "Thursday"; iconName: root.width < 420 ? "sparkles" : ""; tooltip: "Thursday"; selected: root.section === "thursday"; onClicked: root.sectionRequested("thursday") }
            IslandButton { text: "×"; tooltip: "Close dashboard"; quiet: true; implicitWidth: 30; onClicked: root.dismissRequested() }
            }
        }
        IslandTabDeck {
            id: pagesDeck
            objectName: "islandTabDeck"
            active: root.active && root.section !== "calendar"
            visible: root.section !== "calendar"
            enabled: visible
            gestureEnabled: false
            onIndexRequested: index => root.sectionRequested(["home", "inbox", "media", "controls", "thursday"][index])
            Layout.fillWidth: true; Layout.minimumWidth: 0
            Layout.fillHeight: true
            currentIndex: Math.max(0, ["home", "inbox", "media", "controls", "thursday"].indexOf(root.section))

            ScrollView {
                id: homeScroll
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: homeScroll.availableWidth
                    spacing: 10
                    IslandHomeSummary {
                        objectName: "islandHomeSummary"
                        Layout.fillWidth: true; Layout.minimumWidth: 0
                        Layout.preferredHeight: implicitHeight
                        app: root.app
                        now: root.now
                        onCalendarRequested: root.sectionRequested("calendar")
                        onControlsRequested: root.sectionRequested("controls")
                        onCaptureRequested: root.captureRequested(false)
                        onRecordingRequested: root.recordingRequested()
                    }
                    RowLayout {
                        Layout.fillWidth: true; Layout.minimumWidth: 0
                        Label { text: "Recent notifications"; color: "#ffffff"; font.weight: Font.DemiBold; Layout.fillWidth: true; Layout.minimumWidth: 0 }
                        IslandButton { text: "Inbox ›"; quiet: true; onClicked: root.sectionRequested("inbox") }
                    }
                    Caption { visible: S.Notifications.count === 0; text: "You’re all caught up." }
                    Repeater {
                        model: S.Notifications.history.slice(0, 3)
                        IslandNotificationPreview {
                            required property var modelData
                            Layout.fillWidth: true; Layout.minimumWidth: 0
                            entry: modelData
                            active: root.active && root.section === "home"
                            onOpenRequested: root.sectionRequested("inbox")
                            onDismissRequested: S.Notifications.dismiss(modelData.id)
                        }
                    }
                }
            }

            ColumnLayout {
                spacing: 8
                Rectangle {
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    implicitHeight: inboxTools.implicitHeight + 16
                    radius: 21
                    color: "#202126"
                    Flow {
                        id: inboxTools
                        x: 8; y: 8; width: parent.width - 16
                        spacing: 5
                        Caption { text: S.Notifications.unread + " unread"; width: 62; height: 30; verticalAlignment: Text.AlignVCenter }
                        IslandPreviewButton { objectName: "islandInboxDnd"; text: S.Notifications.dnd ? "DND on" : "DND off"; quiet: true; selected: S.Notifications.dnd; implicitHeight: 30; font.pixelSize: 11; onClicked: S.Notifications.toggleDnd() }
                        IslandPreviewButton { objectName: "islandInboxRead"; text: "Mark read"; tooltip: "Mark all notifications read"; enabled: S.Notifications.unread > 0; quiet: true; implicitHeight: 30; font.pixelSize: 11; leftPadding: 7; rightPadding: 7; onClicked: S.Notifications.markRead() }
                        IslandPreviewButton { objectName: "islandInboxClear"; text: "Clear all"; tooltip: "Dismiss all notifications"; enabled: S.Notifications.count > 0; quiet: true; implicitHeight: 30; font.pixelSize: 11; leftPadding: 7; rightPadding: 7; onClicked: S.Notifications.clear() }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    implicitHeight: 88
                    visible: S.Notifications.count === 0
                    radius: 23
                    color: "#24252b"
                    Icon { x: 18; anchors.verticalCenter: parent.verticalCenter; name: "bell"; size: 27; color: "#b9bdca" }
                    Caption { x: 60; width: parent.width - 78; anchors.verticalCenter: parent.verticalCenter; text: "No notifications yet. Enjoy the quiet."; wrapMode: Text.Wrap }
                }
                ListView {
                    id: inbox
                    objectName: "islandInboxList"
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    Layout.fillHeight: true
                    clip: true
                    spacing: 8
                    model: root.inboxEntries
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}
                    onContentYChanged: readVisible.restart()
                    delegate: Column {
                        id: notificationRow
                        required property var modelData
                        readonly property var entry: modelData
                        width: inbox.width
                        spacing: 6
                        Label { visible: notificationRow.entry.groupStart; width: parent.width; height: visible ? 25 : 0; text: notificationRow.entry.appName; color: "#ffffff"; font.weight: Font.DemiBold }
                        IslandNotificationPreview {
                            width: parent.width
                            height: implicitHeight
                            entry: notificationRow.entry
                            active: root.active && root.section === "inbox"
                            onOpenRequested: root.openPanelRequested("notifications")
                            onDismissRequested: S.Notifications.dismiss(notificationRow.entry.id)
                        }
                    }
                }
            }

            ScrollView {
                id: mediaScroll
                clip: true
                contentWidth: availableWidth
                IslandMediaPage {
                    objectName: "islandMediaPage"
                    width: mediaScroll.availableWidth
                    active: root.active && root.section === "media"
                    mediaPosition: root.mediaPosition
                    samples: root.samples
                    onDetailsRequested: root.openPanelRequested("media")
                }
            }

            ScrollView {
                id: controlsScroll
                objectName: "islandControlsScroll"
                clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    objectName: "islandControlsContent"
                    width: controlsScroll.availableWidth
                    spacing: 10
                    IslandControlCenter {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: implicitHeight
                        app: root.app
                        active: root.active && root.section === "controls"
                        now: root.now
                        onSettingsRequested: section => root.settingsRequested(section)
                        onCaptureRequested: annotate => root.captureRequested(annotate)
                        onRecordingRequested: root.recordingRequested()
                    }
                    Caption { Layout.fillWidth: true; Layout.minimumWidth: 0; visible: root.controlError.length > 0; text: root.controlError; color: "#ffc88a"; wrapMode: Text.Wrap }
                }
            }
            IslandThursdayPage {
                id: thursdayPage
                backend: root.thursdayBackend
                active: root.active && root.section === "thursday"
                onFullChatRequested: root.thursdayFullChatRequested()
            }
        }
        ScrollView {
            id: calendarScroll
            objectName: "islandCalendarArea"
            Layout.fillWidth: true; Layout.minimumWidth: 0
            Layout.fillHeight: true
            visible: root.section === "calendar"
            enabled: visible
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: calendarScroll.availableWidth
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    IslandButton {
                        id: calendarBack
                        objectName: "islandCalendarBack"
                        text: "‹ Home"; tooltip: "Back to Home"; quiet: true
                        onClicked: root.sectionRequested("home")
                    }
                    Label { text: "Calendar"; color: "#ffffff"; font.pixelSize: 15; font.weight: Font.DemiBold; Layout.fillWidth: true }
                }
                IslandCalendar {
                    objectName: "islandMonthView"
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    Layout.preferredHeight: implicitHeight
                    today: new Date(root.now)
                }
            }
        }
    }
    IslandTabGesture {
        anchors.fill: parent
        z: 1000
        deck: root.tabDeck
        active: root.active
    }
}
