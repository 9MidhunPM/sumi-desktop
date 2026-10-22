pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import Quickshell.Io
import "config"
import "services" as S
import "components" as C

C.Surface {
    id: root
    required property var app
    property var themes: []
    property var selected: null
    property string message: ""
    property bool success: true
    property bool changing: false
    property bool recoveryAvailable: false
    property var importScreen: null
    readonly property bool compact: width < 720
    readonly property bool shortLayout: height < 520
    readonly property int themeCount: gallery.count
    readonly property real galleryWidth: gallery.width
    readonly property real previewWidth: preview.width
    width: Math.min(980, Math.max(1, app.activeScreen ? app.activeScreen.width - 48 : 980))
    height: Math.min(760, Math.max(1, app.activeScreen ? app.activeScreen.height - 48 : 760))

    function focusDefault() { gallery.forceActiveFocus(Qt.OtherFocusReason); }
    function activatePanel() { catalog.running = true; recoveryStatus.running = true; }
    function addWallpaper() {
        importScreen = root.app.activeScreen;
        // Keep the dialog's layer-shell parent mapped, but hand all input and
        // visible content to the normal native window until it is dismissed.
        root.app.nativeDialogOpen = true;
        Qt.callLater(() => importer.open());
    }
    function revealControl(item) {
        Qt.callLater(function() {
            if (!item.activeFocus) return;
            // Reveal in the inner detail viewport first, then the complete body.
            for (const viewport of [detailsScroll, body]) {
                const flick = viewport.contentItem;
                if (!flick || typeof flick.contentY !== "number") continue;
                let ancestor = item;
                while (ancestor && ancestor !== flick.contentItem) ancestor = ancestor.parent;
                if (!ancestor) continue;
                const point = item.mapToItem(flick.contentItem, 0, 0);
                let target = flick.contentY;
                if (point.y < target + 8) target = point.y - 8;
                else if (point.y + item.height > target + flick.height - 8) target = point.y + item.height - flick.height + 8;
                flick.contentY = Math.max(0, Math.min(Math.max(0, flick.contentHeight - flick.height), target));
            }
        });
    }
    function command(args) {
        if (S.Desktop.preview) { message = "Preview · desktop changes are disabled"; return; }
        if (changing) return;
        changing = true;
        message = "Applying…";
        S.Desktop.run(args, "appearance", function(ok, value, error) {
            root.changing = false;
            root.success = ok;
            root.message = ok ? "Applied" : error;
            if (ok) catalog.running = true;
        });
    }
    Component.onCompleted: { catalog.running = true; recoveryStatus.running = true; }
    Shortcut { sequence: "Ctrl+O"; enabled: root.visible && !root.app.nativeDialogOpen; context: Qt.WindowShortcut; onActivated: root.addWallpaper() }
    Process {
        id: catalog
        command: [S.Desktop.controller, "theme", "list", "--json"]
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const data = JSON.parse(text);
                    root.themes = Array.isArray(data) ? data : data.themes;
                    gallery.currentIndex = Math.max(0, root.themes.findIndex(theme => theme.id === Theme.id));
                    root.selected = root.themes[gallery.currentIndex] || null;
                } catch (error) { root.message = "Could not read wallpaper library"; root.success = false; }
            }
        }
    }
    Process {
        id: recoveryStatus
        command: [S.Desktop.controller, "profile", "status", "--json"]
        stdout: StdioCollector { id: recoveryOutput }
        onExited: (code, status) => {
            root.recoveryAvailable = false;
            if (code !== 0) return;
            try { root.recoveryAvailable = JSON.parse(recoveryOutput.text).recovery_available === true; }
            catch (error) { console.warn("Sumi: previous desktop recovery is unavailable"); }
        }
    }
    FileDialog {
        id: importer
        title: "Add a wallpaper"
        nameFilters: ["Images (*.jpg *.jpeg *.png *.webp)"]
        onAccepted: {
            root.app.nativeDialogOpen = false;
            root.app.open("appearance", root.importScreen);
            root.command(["theme", "import", decodeURIComponent(selectedFile.toString().replace(/^file:\/\//, ""))]);
        }
        onRejected: {
            root.app.nativeDialogOpen = false;
            root.app.open("appearance", root.importScreen);
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.compact ? 16 : 20
        spacing: root.shortLayout ? 12 : 18
        GridLayout {
            id: header
            Layout.fillWidth: true
            columns: root.compact ? 2 : 3
            columnSpacing: 10
            rowSpacing: 8
            ColumnLayout {
                Layout.row: 0
                Layout.column: 0
                Layout.fillWidth: true
                spacing: 4
                C.Label { text: "Appearance"; font.pixelSize: root.compact ? 23 : 26; font.weight: Font.DemiBold; Layout.fillWidth: true }
                C.Label { visible: !root.shortLayout; text: "A different atmosphere. One coherent desktop."; color: Theme.textSoft; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
            C.ActionButton {
                id: addWallpaper
                objectName: "appearanceAddWallpaper"
                Layout.row: root.compact ? 1 : 0
                Layout.column: root.compact ? 0 : 1
                Layout.columnSpan: root.compact ? 2 : 1
                Layout.fillWidth: root.compact
                KeyNavigation.tab: closeButton
                                KeyNavigation.backtab: resetWidgets
                text: "+ Add wallpaper"
                tooltip: "Import a wallpaper · Ctrl+O"
                onClicked: root.addWallpaper()
            }
            C.ActionButton { id: closeButton; objectName: "appearanceClose"; KeyNavigation.tab: gallery; KeyNavigation.backtab: addWallpaper; Layout.row: 0; Layout.column: root.compact ? 1 : 2; text: "×"; font.pixelSize: 20; tooltip: "Close appearance · Esc"; quiet: true; onClicked: root.app.close() }
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
                spacing: 16
                GridLayout {
                    id: contentRow
                    columns: root.compact ? 1 : 2
                    Layout.fillWidth: true
                    columnSpacing: 24
                    rowSpacing: 16
                    readonly property real paneHeight: root.compact ? Math.max(134, Math.min(268, body.availableHeight * 0.65))
                        : Math.max(134, body.availableHeight - options.implicitHeight - footerMessage.implicitHeight - 49)
                    GridView {
                        id: gallery
                        objectName: "appearanceGallery"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: root.compact ? contentRow.width : contentRow.width - 274
                        Layout.preferredHeight: contentRow.paneHeight
                        Layout.minimumHeight: 134
                        cellWidth: width / Math.max(1, Math.floor(width / 180))
                        cellHeight: 134
                        clip: true
                        model: root.themes
                        activeFocusOnTab: true
                        KeyNavigation.priority: KeyNavigation.BeforeItem
                        KeyNavigation.tab: accent
                        KeyNavigation.backtab: closeButton
                        keyNavigationWraps: true
                        highlightMoveDuration: Theme.motionControl
                        onCurrentIndexChanged: if (currentIndex >= 0 && currentIndex < root.themes.length) root.selected = root.themes[currentIndex]
                        onActiveFocusChanged: if (activeFocus) root.revealControl(gallery)
                        Keys.onReturnPressed: if (root.selected && !root.changing) root.command(["theme", "use", root.selected.id])
                        Keys.onEnterPressed: if (root.selected && !root.changing) root.command(["theme", "use", root.selected.id])
                        Keys.onSpacePressed: if (currentIndex >= 0) root.selected = root.themes[currentIndex]
                        highlight: Rectangle { color: "transparent"; border.color: Theme.accentBlue; border.width: 2; radius: 12; visible: gallery.activeFocus }
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Item {
                            id: tile
                            required property var modelData
                            required property int index
                            width: gallery.cellWidth - 10
                            height: gallery.cellHeight - 10
                            Rectangle {
                                anchors.fill: parent
                                color: Theme.bgPanel
                                radius: 10
                                border.width: root.selected && root.selected.id === tile.modelData.id ? 2 : 1
                                border.color: root.selected && root.selected.id === tile.modelData.id ? Theme.accentBlue : Theme.borderSoft
                                Image { anchors.fill: parent; anchors.margins: 4; anchors.bottomMargin: 29; source: tile.modelData.thumbnail || tile.modelData.wallpaper; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(300,180); asynchronous: true }
                                C.Label { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 10; text: tile.modelData.name; font.pixelSize: 11 }
                            }
                            MouseArea { anchors.fill: parent; onClicked: { gallery.currentIndex = tile.index; root.selected = tile.modelData; gallery.forceActiveFocus(Qt.MouseFocusReason); } }
                        }
                    }
                    ScrollView {
                        id: detailsScroll
                        Layout.preferredWidth: root.compact ? contentRow.width : 250
                        Layout.minimumWidth: 0
                        Layout.maximumWidth: root.compact ? contentRow.width : 250
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.compact ? details.implicitHeight : contentRow.paneHeight
                        Layout.minimumHeight: root.compact ? details.implicitHeight : 134
                        contentWidth: availableWidth
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        ColumnLayout {
                            id: details
                            width: detailsScroll.availableWidth
                            spacing: 12
                            Image { id: preview; visible: !root.compact; Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 250; Layout.maximumWidth: 250; Layout.preferredHeight: root.shortLayout ? 112 : 155; source: root.selected ? root.selected.thumbnail || root.selected.wallpaper : ""; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(600,360) }
                            C.Label { text: root.selected ? root.selected.name : "Choose a theme"; font.pixelSize: 20; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Row { spacing: 10; Repeater { model: root.selected ? [root.selected.colors.accentBlue,root.selected.colors.accentCyan,root.selected.colors.accentPink,root.selected.colors.accentWarn] : []; Rectangle { required property string modelData; width: 24; height: 24; radius: 12; color: modelData } } }
                            C.Label { text: "Primary accent"; color: Theme.textSoft; font.pixelSize: 12 }
                            TextField {
                                id: accent
                                objectName: "appearanceAccent"
                                KeyNavigation.tab: applyAccent
                                KeyNavigation.backtab: gallery
                                Layout.fillWidth: true
                                implicitHeight: 40
                                padding: 10
                                text: root.selected ? root.selected.colors.accentBlue : ""
                                placeholderText: "#RRGGBB"
                                color: Theme.textMain
                                font.family: Theme.fontMono
                                Accessible.name: "Primary accent color"
                                onActiveFocusChanged: if (activeFocus) root.revealControl(accent)
                                background: C.Surface { border.width: accent.activeFocus ? 2 : Theme.borderWidth; border.color: accent.activeFocus ? Theme.accentBlue : Theme.borderSoft }
                            }
                            C.ActionButton { id: applyAccent; KeyNavigation.tab: applyTheme; KeyNavigation.backtab: accent; objectName: "appearanceApplyAccent"; text: "Apply accent"; Layout.fillWidth: true; enabled: root.selected !== null && !root.changing && /^#[0-9a-fA-F]{6}$/.test(accent.text); onActiveFocusChanged: if (activeFocus) root.revealControl(applyAccent); onClicked: root.command(["theme", "accent", root.selected.id, accent.text]) }
                            C.ActionButton { id: applyTheme; KeyNavigation.tab: root.recoveryAvailable ? classic : barMode; KeyNavigation.backtab: applyAccent; objectName: "appearanceApplyTheme"; text: "Apply theme  →"; selected: true; Layout.fillWidth: true; enabled: root.selected !== null && !root.changing; onActiveFocusChanged: if (activeFocus) root.revealControl(applyTheme); onClicked: root.command(["theme", "use", root.selected.id]) }
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.borderSoft }
                Flow {
                    id: options
                    Layout.fillWidth: true
                    spacing: 8
                    C.Label { text: "Desktop · Sumi"; color: Theme.textSoft; height: 36 }
                    C.ActionButton { id: classic; KeyNavigation.tab: barMode; KeyNavigation.backtab: applyTheme; objectName: "appearanceClassic"; text: "Restore previous desktop"; tooltip: "Restore the original desktop configuration, replacing later edits after saving a recovery snapshot. Log out afterward"; visible: root.recoveryAvailable; enabled: !root.changing; onActiveFocusChanged: if (activeFocus) root.revealControl(classic); onClicked: root.command(["restore", "original"]) }
                    C.ActionButton { id: barMode; KeyNavigation.tab: motionMode; KeyNavigation.backtab: root.recoveryAvailable ? classic : applyTheme; objectName: "appearanceBarMode"; text: Settings.barHiddenMode ? "Bar: hold Shift" : "Bar: visible"; quiet: true; onActiveFocusChanged: if (activeFocus) root.revealControl(barMode); onClicked: Settings.toggle("barHiddenMode") }
                    C.ActionButton { id: motionMode; KeyNavigation.tab: editWidgets; KeyNavigation.backtab: barMode; objectName: "appearanceMotion"; text: Settings.reducedMotion ? "Motion: reduced" : Settings.fullMotion ? "Motion: expressive" : "Motion: adaptive"; tooltip: "Cycle motion: adaptive, expressive, reduced"; quiet: true; onActiveFocusChanged: if (activeFocus) root.revealControl(motionMode); onClicked: Settings.cycleMotion() }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    C.ActionButton { id: editWidgets; objectName: "appearanceWidgets"; KeyNavigation.tab: widgetLayout; KeyNavigation.backtab: motionMode; text: "Edit widgets"; onActiveFocusChanged: if (activeFocus) root.revealControl(editWidgets); onClicked: root.app.open("widgets", root.app.activeScreen) }
                    C.ActionButton {
                        id: widgetLayout
                        objectName: "appearanceWidgetLayout"
                        KeyNavigation.tab: resetWidgets
                        KeyNavigation.backtab: editWidgets
                        text: "Layout: " + S.Widgets.layoutMode
                        tooltip: "Cycle the current wallpaper’s widget layout"
                        quiet: true
                        onActiveFocusChanged: if (activeFocus) root.revealControl(widgetLayout)
                        onClicked: { const modes = ["curated", "left", "right", "split"]; S.Widgets.setLayout(modes[(modes.indexOf(S.Widgets.layoutMode) + 1) % modes.length]); }
                    }
                    C.ActionButton { id: resetWidgets; objectName: "appearanceWidgetReset"; KeyNavigation.tab: addWallpaper; KeyNavigation.backtab: widgetLayout; text: "Reset layout"; quiet: true; enabled: S.Widgets.layoutMode !== "curated"; onActiveFocusChanged: if (activeFocus) root.revealControl(resetWidgets); onClicked: S.Widgets.setLayout("curated") }
                }
                C.Label { text: "Widget layout applies to your current wallpaper."; color: Theme.textSoft; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                C.Label { id: footerMessage; text: root.message || Motion.error || ("Current theme · " + Theme.name); color: root.success && !Motion.error ? Theme.textSoft : Theme.accentPink; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
            }
        }
    }
}
