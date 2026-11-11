pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"
import "../services" as S

// Cached core destinations: navigation never destroys list position or month state.
FocusScope {
    id: root
    required property var app
    property string route: "home"
    property bool active: false
    property double now: Date.now()
    property real mediaPosition: 0
    property var spectrumSamples: []
    readonly property real preferredWidthHint: route === "media" && !S.IslandMedia.available ? 420 : 0
    // Natural content is measured at the destination width, never the animated clip.
    readonly property real contentHeight: route === "calendar" ? calendar.implicitHeight
        : route === "media" ? media.implicitHeight
        : route === "inbox" ? inboxToolbar.implicitHeight + 12 + (S.Notifications.count ? inbox.contentHeight : 64)
        : route === "notification" ? detailContent.implicitHeight : homeContent.implicitHeight
    property int statsConsumer: 0
    function syncStatsDemand() { if (statsConsumer) S.SystemStats.setDemand(statsConsumer, active && route === "home"); }
    Component.onCompleted: { statsConsumer = S.SystemStats.createConsumer(); syncStatsDemand(); }
    Component.onDestruction: if (statsConsumer) S.SystemStats.releaseConsumer(statsConsumer)
    readonly property var selectedEntry: S.Notifications.history.find(entry => app.islandSession && String(entry.id) === String(app.islandSession.entityId)) || null
    readonly property var priorities: S.Widgets.document.priorities.filter(item => item.text.trim().length)
    signal routeRequested(string route)
    signal captureRequested(bool annotate)
    signal recordingRequested()

    function openNotification(entry) {
        if (!entry || !app.islandSession) return;
        app.islandSession.entityId = entry.id;
        routeRequested("notification");
    }
    function focusDefault() {
        const target = route === "inbox" ? inbox : route === "notification" ? detailScroll : route === "calendar" ? calendar : route === "media" ? mediaScroll : homeScroll;
        target.forceActiveFocus(Qt.OtherFocusReason);
    }
    function back() {
        if (route === "media" && media.sourcesExpanded) { media.sourcesExpanded = false; return true; }
        return false;
    }
    function markVisible() {
        if (!active) return;
        if (route === "notification") {
            if (selectedEntry && selectedEntry.unread) S.Notifications.markEntriesRead([selectedEntry.id]);
            return;
        }
        if (route !== "inbox") return;
        const ids = [];
        for (const child of inbox.contentItem.children) {
            if (child.entry && child.entry.unread && child.y + child.height > inbox.contentY && child.y < inbox.contentY + inbox.height)
                ids.push(child.entry.id);
        }
        if (ids.length) S.Notifications.markEntriesRead(ids);
    }
    onActiveChanged: { syncStatsDemand(); if (active) readVisible.restart(); }
    onRouteChanged: { syncStatsDemand(); readVisible.restart(); }
    onSelectedEntryChanged: if (active && route === "notification") readVisible.restart()
    Connections { target: S.Notifications; function onHistoryChanged() { readVisible.restart(); } }
    Timer { id: readVisible; interval: 160; onTriggered: root.markVisible() }

    component Caption: Label { color: IslandStyle.secondary; font.pixelSize: 13; wrapMode: Text.Wrap; textFormat: Text.PlainText }
    component Heading: Label { color: IslandStyle.text; font.pixelSize: 18; font.weight: Font.DemiBold; wrapMode: Text.Wrap; textFormat: Text.PlainText }
    component Rule: Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: IslandStyle.line }
    component RowAction: IslandPreviewButton {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        implicitHeight: 44
        quiet: true
    }

    StackLayout {
        anchors.fill: parent
        currentIndex: root.route === "calendar" ? 1 : root.route === "inbox" ? 2 : root.route === "notification" ? 3 : root.route === "media" ? 4 : 0
        ScrollView {
            id: homeScroll
            objectName: "islandDeskHome"
            clip: true
            contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                id: homeContent
                width: homeScroll.availableWidth
                spacing: Metrics.space4
                Heading { Layout.fillWidth: true; text: Qt.formatDateTime(new Date(root.now), "dddd, d MMMM") }
                IslandHomeSummary {
                    objectName: "islandDeskHomeSummary"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: implicitHeight
                    app: root.app
                    now: root.now
                    onCalendarRequested: root.routeRequested("calendar")
                    onControlsRequested: root.routeRequested("controls")
                    onCaptureRequested: root.captureRequested(false)
                    onRecordingRequested: root.recordingRequested()
                }
                RowAction { objectName: "islandDeskFocusShortcut"; text: "Focus timer"; iconName: "timer"; onClicked: root.routeRequested("pomodoro") }
                Rule {}
                RowLayout {
                    Layout.fillWidth: true
                    Heading { text: "Priorities"; font.pixelSize: 15; Layout.fillWidth: true }
                    IslandPreviewButton { text: "Edit"; quiet: true; onClicked: root.routeRequested("widgets") }
                }
                Caption { Layout.fillWidth: true; visible: !root.priorities.length; text: "Make room for what matters. Add up to three priorities." }
                Repeater {
                    model: root.priorities
                    RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Icon { name: "more-horizontal"; color: modelData.done ? IslandStyle.text : "#bbc1c5"; size: 16 }
                        Caption { text: modelData.text; font.strikeout: modelData.done; Layout.fillWidth: true }
                    }
                }
                RowLayout {
                    visible: !!S.Widgets.document.deadline.title
                    Layout.fillWidth: true
                    Icon { name: "calendar"; size: 18; color: IslandStyle.text }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Caption { text: S.Widgets.document.deadline.title; Layout.fillWidth: true }
                        Caption { text: S.Widgets.deadlineText; font.pixelSize: 12; Layout.fillWidth: true }
                    }
                }
                Rule {}
                RowLayout {
                    Layout.fillWidth: true
                    Heading { text: "Recent notifications"; font.pixelSize: 15; Layout.fillWidth: true }
                    IslandPreviewButton { text: "Inbox ›"; quiet: true; onClicked: root.routeRequested("inbox") }
                }
                Caption { visible: !S.Notifications.count; text: "You’re all caught up."; Layout.fillWidth: true }
                Repeater {
                    model: S.Notifications.history.slice(0, 3)
                    RowAction {
                        required property var modelData
                        text: modelData.summary || modelData.appName
                        tooltip: modelData.appName + ": " + modelData.summary
                        iconName: "bell"
                        onClicked: root.openNotification(modelData)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    IslandPreviewButton { Layout.fillWidth: true; iconName: "camera"; text: "Screenshot"; onClicked: root.captureRequested(false) }
                    IslandPreviewButton { Layout.fillWidth: true; iconName: "record"; text: S.Recording.recording ? "Stop recording" : "Record"; onClicked: root.recordingRequested() }
                }
            }
        }
        ScrollView {
            id: calendarScroll
            objectName: "islandDeskCalendar"
            clip: true
            contentWidth: availableWidth
            IslandCalendar { id: calendar; objectName: "islandDeskMonthView"; width: calendarScroll.availableWidth; today: new Date(root.now) }
        }
        ColumnLayout {
            spacing: Metrics.space3
            RowLayout {
                Layout.fillWidth: true
                id: inboxToolbar
                Caption { Layout.fillWidth: true; text: S.Notifications.unread ? S.Notifications.unread + " unread" : "All caught up" }
                IslandPreviewButton { text: S.Notifications.dnd ? "DND on" : "DND off"; selected: S.Notifications.dnd; onClicked: Settings.setValue("dnd", !S.Notifications.dnd) }
                IslandPreviewButton { text: "Clear"; enabled: S.Notifications.count > 0; quiet: true; onClicked: S.Notifications.clear() }
            }
            Caption { visible: !S.Notifications.count; text: "No notifications yet. Enjoy the quiet."; Layout.fillWidth: true }
            ListView {
                id: inbox
                objectName: "islandDeskInbox"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 4
                model: S.Notifications.history
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                onContentYChanged: readVisible.restart()
                delegate: Item {
                    id: entryRow
                    required property var modelData
                    readonly property var entry: modelData
                    width: inbox.width
                    height: Math.max(76, rowContent.implicitHeight + 24)
                    RowLayout {
                        id: rowContent
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 8 }
                        spacing: Metrics.space3
                        Rectangle { width: 5; height: 5; radius: 3; color: entryRow.entry.unread ? IslandStyle.text : "transparent" }
                        ColumnLayout {
                            Layout.fillWidth: true; Layout.minimumWidth: 0
                            spacing: 4
                            Caption { text: entryRow.entry.appName; font.pixelSize: 11; Layout.fillWidth: true }
                            Label { text: entryRow.entry.summary; textFormat: Text.PlainText; color: IslandStyle.text; font.pixelSize: 13; font.weight: Font.DemiBold; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                        IslandPreviewButton { text: "›"; tooltip: "Read notification"; implicitWidth: 40; implicitHeight: 40; quiet: true; onClicked: root.openNotification(entryRow.entry) }
                        IslandPreviewButton { text: "×"; tooltip: "Dismiss notification"; implicitWidth: 40; implicitHeight: 40; quiet: true; onClicked: S.Notifications.dismiss(entryRow.entry.id) }
                    }
                    Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 1; color: IslandStyle.line }
                }
            }
        }
        ScrollView {
            id: detailScroll
            objectName: "islandDeskNotificationDetail"
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                id: detailContent
                width: detailScroll.availableWidth
                spacing: Metrics.space4
                Caption { text: root.selectedEntry ? root.selectedEntry.appName : "Notification unavailable"; Layout.fillWidth: true }
                Heading { text: root.selectedEntry ? root.selectedEntry.summary : "This notification was dismissed."; Layout.fillWidth: true }
                Caption { text: root.selectedEntry ? root.selectedEntry.body || "" : "Return to Inbox to see your other notifications."; Layout.fillWidth: true }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Repeater {
                        model: root.selectedEntry ? root.selectedEntry.actions || [] : []
                        IslandPreviewButton {
                            required property string modelData
                            required property int index
                            width: Math.min(implicitWidth, detailScroll.availableWidth)
                            implicitHeight: 40
                            text: modelData
                            onClicked: { if (root.selectedEntry) S.Notifications.invoke(root.selectedEntry.id, index); }
                        }
                    }
                }
                IslandPreviewButton { visible: !!root.selectedEntry; text: "Dismiss"; quiet: true; onClicked: { S.Notifications.dismiss(root.selectedEntry.id); root.routeRequested("inbox"); } }
            }
        }
        ScrollView {
            id: mediaScroll
            objectName: "islandDeskMedia"
            clip: true
            contentWidth: availableWidth
            IslandMediaPage { id: media; width: mediaScroll.availableWidth; active: root.active && root.route === "media"; mediaPosition: root.mediaPosition; samples: root.spectrumSamples; onDetailsRequested: root.routeRequested("audio") }
        }
    }
}
