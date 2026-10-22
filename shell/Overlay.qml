pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Wayland
import "config"

PanelWindow {
    id: overlay
    required property var modelData
    required property var app
    screen: modelData
    color: "transparent"
    // A panel belongs to one output. Other outputs retain their normal input.
    readonly property bool shown: app.panel !== "" && app.activeScreen === modelData
    readonly property bool popupShown: shown
    property string dashboardKind: "calendar"
    readonly property string panelKind: ["launcher", "files", "clipboard"].indexOf(app.panel) >= 0 ? "launcher"
        : app.panel === "appearance" ? "appearance" : app.panel === "widgets" ? "widgets" : app.panel === "settings" ? "settings" : "dashboard"
    property real reveal: shown ? 1 : 0
    visible: app.activeScreen === modelData && (shown || reveal > 0.001)
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "sumi-overlay"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: popupShown && !app.nativeDialogOpen ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    // A native file picker needs a mapped parent, without an overlay stealing
    // its focus or intercepting pointer input above its ordinary window.
    mask: Region { width: overlay.popupShown && !overlay.app.nativeDialogOpen ? overlay.width : 0; height: overlay.popupShown && !overlay.app.nativeDialogOpen ? overlay.height : 0 }
    Behavior on reveal {
        id: scrimMotion
        NumberAnimation { duration: scrimMotion.targetValue > 0 ? Theme.motionEnter : Theme.motionExit; easing.type: scrimMotion.targetValue > 0 ? Easing.OutQuint : Easing.InCubic }
    }
    function rememberPanel() {
        if (popupShown && ["calendar", "media", "notifications", "pomodoro", "power", "help"].indexOf(app.panel) >= 0)
            dashboardKind = app.panel;
    }
    function focusCurrent() {
        if (!popupShown || !page.item) return;
        content.forceActiveFocus(Qt.OtherFocusReason);
        if (typeof page.item.focusDefault === "function") page.item.focusDefault();
        else {
            // Use the native focus chain so Tab/Shift+Tab remain consistent with controls.
            const candidate = page.item.nextItemInFocusChain(true);
            if (candidate && candidate !== page.item) candidate.forceActiveFocus(Qt.OtherFocusReason);
        }
    }
    function prepareCurrent() {
        rememberPanel();
        if (!popupShown || !page.item) return;
        if (typeof page.item.activatePanel === "function") page.item.activatePanel(app.panel);
        else if (typeof page.item.activate === "function") page.item.activate();
        Qt.callLater(focusCurrent);
    }
    onPopupShownChanged: if (popupShown) { rememberPanel(); Qt.callLater(prepareCurrent); }
    Connections {
        target: overlay.app
        function onActivationSerialChanged() { overlay.rememberPanel(); Qt.callLater(overlay.prepareCurrent); }
        function onPanelChanged() { overlay.rememberPanel(); }
    }
    Rectangle {
        id: scrim
        anchors.fill: parent
        // The active output, including its bar, dims behind every panel family.
        color: Theme.scrim
        opacity: overlay.app.nativeDialogOpen ? 0 : overlay.reveal
        MouseArea { anchors.fill: parent; onClicked: overlay.app.close() }
    }
    FocusScope {
        id: content
        anchors.fill: parent
        visible: overlay.popupShown || overlay.reveal > 0.001
        opacity: overlay.app.nativeDialogOpen ? 0 : 1
        focus: overlay.popupShown
        Keys.onEscapePressed: overlay.app.close()
        // Load each family once, then reuse its model, icons, and controls on reopen.
        Repeater {
            id: panelRepeater
            model: ["launcher", "appearance", "widgets", "settings", "dashboard"]
            delegate: Loader {
                id: panelLoader
                required property string modelData
                readonly property bool selected: overlay.popupShown && overlay.panelKind === modelData
                property real motionProgress: selected && status === Loader.Ready ? 1 : 0
                property bool initialized: modelData === "launcher"
                active: initialized
                asynchronous: true
                visible: selected || opacity > 0.001
                enabled: selected
                readonly property string placement: modelData === "settings" || (modelData === "dashboard" && overlay.dashboardKind === "notifications") ? "right"
                    : modelData === "dashboard" && ["calendar", "media"].indexOf(overlay.dashboardKind) >= 0 ? "top" : "center"
                readonly property real topInset: placement === "center" ? 24 : Math.min(Theme.panelTop, Math.max(24, overlay.height - height - 24))
                x: placement === "right" ? Math.max(24, overlay.width - width - 24) : Math.max(24, (overlay.width - width) / 2)
                y: placement === "center" ? Math.max(24, (overlay.height - height) / 2) : topInset
                opacity: motionProgress
                scale: Theme.effectiveReducedMotion ? 1 : 0.95 + motionProgress * 0.05
                transform: Translate {
                    x: Theme.effectiveReducedMotion || panelLoader.placement !== "right" ? 0 : (1 - panelLoader.motionProgress) * (Theme.batteryMotion ? 14 : 24)
                    y: Theme.effectiveReducedMotion || panelLoader.placement === "right" ? 0 : (1 - panelLoader.motionProgress) * (panelLoader.placement === "top" ? -1 : 1) * (Theme.batteryMotion ? 12 : 20)
                }
                Behavior on motionProgress {
                    id: panelMotion
                    NumberAnimation { duration: panelMotion.targetValue > 0 ? Theme.motionEnter : Theme.motionExit; easing.type: panelMotion.targetValue > 0 ? Easing.OutQuint : Easing.InCubic }
                }
                sourceComponent: modelData === "launcher" ? launcherComponent : modelData === "appearance" ? appearanceComponent
                    : modelData === "widgets" ? widgetsComponent : modelData === "settings" ? settingsComponent : dashboardComponent
                onSelectedChanged: if (selected) initialized = true
                Component.onCompleted: if (selected) initialized = true
                onLoaded: if (selected) overlay.prepareCurrent()
                MouseArea { anchors.fill: parent; z: -1; onClicked: {} }
            }
        }
    }
    QtObject {
        id: page
        readonly property var item: {
            for (let index = 0; index < panelRepeater.count; index++) {
                const candidate = panelRepeater.itemAt(index);
                if (candidate.selected && candidate.item) return candidate.item;
            }
            return null;
        }
    }
    Component { id: launcherComponent; Launcher { app: overlay.app } }
    Component { id: appearanceComponent; Appearance { app: overlay.app } }
    Component { id: widgetsComponent; WidgetsEditor { app: overlay.app } }
    Component { id: settingsComponent; QuickSettings { app: overlay.app } }
    Component { id: dashboardComponent; Dashboard { app: overlay.app; kind: overlay.dashboardKind } }
}
