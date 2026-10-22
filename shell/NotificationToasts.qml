pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import "config"
import "services" as S
import "components" as C

PanelWindow {
    id: root
    required property var app
    readonly property var requestedEntries: {
        const entries = S.Notifications.active.slice(0, 3).map(entry => ({key: String(entry.id), entry: entry}));
        if (S.Desktop.lastError) entries.unshift({key: "action-error", entry: {appName: "Sumi", summary: "Action could not complete", body: S.Desktop.lastError, actions: [], error: true}});
        return entries;
    }
    readonly property bool shown: toastModel.count > 0 && app.panel === ""
    property real reveal: shown ? 1 : 0
    property real stackHeight: 0
    visible: shown || reveal > 0.001
    screen: app.notificationScreen
    anchors { top: true; right: true }
    margins { top: Theme.panelTop; right: 24 }
    implicitWidth: Math.min(380, Math.max(1, app.notificationScreen ? app.notificationScreen.width - 48 : 380))
    implicitHeight: Math.min(Math.max(1, stackHeight), Math.max(1, app.notificationScreen ? app.notificationScreen.height - Theme.panelTop - 24 : 700))
    color: "transparent"
    exclusiveZone: 0
    WlrLayershell.namespace: "sumi-notifications"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    Behavior on reveal {
        id: stackMotion
        NumberAnimation { duration: stackMotion.targetValue > 0 ? Theme.motionEnter : Theme.motionExit; easing.type: stackMotion.targetValue > 0 ? Easing.OutQuint : Easing.InCubic }
    }
    Behavior on stackHeight {
        id: heightMotion
        // New cards need a full viewport before their own slide starts.
        enabled: root.shown && heightMotion.targetValue > 0 && heightMotion.targetValue < root.stackHeight
        NumberAnimation { duration: Theme.motionEnter; easing.type: Easing.OutQuint }
    }

    function updateStackHeight() {
        // Map the first card at its full height; retain the final card's surface
        // until its exit finishes instead of clipping it as the model empties.
        if (toastList.contentHeight > 0 || !root.visible) stackHeight = toastList.contentHeight;
    }
    onVisibleChanged: if (!visible) updateStackHeight()

    function syncEntries() {
        const next = requestedEntries;
        for (let index = toastModel.count - 1; index >= 0; index--)
            if (!next.some(entry => entry.key === toastModel.get(index).key)) toastModel.remove(index);
        for (let index = 0; index < next.length; index++) {
            let existing = -1;
            for (let candidate = 0; candidate < toastModel.count; candidate++)
                if (toastModel.get(candidate).key === next[index].key) { existing = candidate; break; }
            if (existing < 0) toastModel.insert(index, next[index]);
            else {
                if (existing !== index) toastModel.move(existing, index, 1);
                toastModel.setProperty(index, "entry", next[index].entry);
            }
        }
    }
    onRequestedEntriesChanged: syncEntries()
    Component.onCompleted: { syncEntries(); updateStackHeight(); }
    ListModel { id: toastModel; dynamicRoles: true }
    ListView {
        id: toastList
        anchors.fill: parent
        opacity: root.reveal
        scale: Theme.effectiveReducedMotion ? 1 : 0.96 + root.reveal * 0.04
        transformOrigin: Item.TopRight
        transform: Translate { x: Theme.effectiveReducedMotion ? 0 : (1 - root.reveal) * (Theme.batteryMotion ? 14 : 28) }
        enabled: root.shown
        clip: true
        spacing: 10
        model: toastModel
        boundsBehavior: Flickable.StopAtBounds
        onContentHeightChanged: root.updateStackHeight()
        displaced: Transition { NumberAnimation { properties: "x,y"; duration: Theme.motionEnter; easing.type: Easing.OutQuint } }
        delegate: C.Surface {
            id: toast
            required property var entry
            property real entrance: 0
            // ListView can skip add transitions just outside its old viewport.
            // Each new card owns its entry so the second/third card still glides.
            Component.onCompleted: entrance = 1
            ListView.onRemove: removal.start()
            enabled: !removal.running
            opacity: entrance
            scale: Theme.effectiveReducedMotion ? 1 : 0.96 + entrance * 0.04
            transformOrigin: Item.TopRight
            transform: Translate { x: Theme.effectiveReducedMotion ? 0 : (1 - toast.entrance) * (Theme.batteryMotion ? 18 : 32) }
            Behavior on entrance {
                enabled: !removal.running
                NumberAnimation { duration: Theme.motionEnter; easing.type: Easing.OutQuint }
            }
            SequentialAnimation {
                id: removal
                // Keep both the card and its layout space until its exit ends.
                PropertyAction { target: toast; property: "ListView.delayRemove"; value: true }
                NumberAnimation { target: toast; property: "entrance"; to: 0; duration: Theme.motionExit; easing.type: Easing.InCubic }
                PropertyAction { target: toast; property: "ListView.delayRemove"; value: false }
            }
            width: toastList.width
            height: content.implicitHeight + 28
            border.color: entry.error ? Theme.accentWarn : Theme.borderSoft
            ColumnLayout {
                id: content
                anchors.fill: parent
                anchors.margins: 14
                spacing: 7
                RowLayout {
                    Layout.fillWidth: true
                    C.Label { text: toast.entry.appName; Layout.fillWidth: true; color: toast.entry.error ? Theme.accentWarn : Theme.accentBlue; font.pixelSize: 11 }
                    C.ActionButton { text: "×"; tooltip: "Dismiss notification"; quiet: true; implicitHeight: 24; onClicked: { if (toast.entry.error) S.Desktop.lastError = ""; else S.Notifications.dismiss(toast.entry.id); } }
                }
                C.Label { text: toast.entry.summary; font.weight: Font.DemiBold; wrapMode: Text.Wrap; maximumLineCount: 2; Layout.fillWidth: true }
                C.Label { visible: text.length > 0; text: toast.entry.body; color: Theme.textSoft; wrapMode: Text.Wrap; maximumLineCount: 3; Layout.fillWidth: true; font.pixelSize: 13 }
                Flow { Layout.fillWidth: true; spacing: 5; Repeater { model: toast.entry.actions; C.ActionButton { required property string modelData; required property int index; text: modelData; onClicked: S.Notifications.invoke(toast.entry.id,index) } } }
            }
        }
    }
}
