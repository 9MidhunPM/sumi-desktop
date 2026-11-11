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
    property bool embedded: false
    island: embedded
    readonly property color foreground: embedded ? IslandStyle.text : Theme.textMain
    readonly property color secondary: embedded ? IslandStyle.secondary : Theme.textSoft
    readonly property color accent: embedded ? IslandStyle.accent : Theme.accentBlue
    readonly property color accentForeground: embedded ? IslandStyle.accentText : Theme.desktopBackground
    readonly property color separator: embedded ? IslandStyle.line : Theme.borderSoft
    // Gallery budget comes from rows, not the current viewport: no size loop.
    readonly property real galleryNaturalHeight: Math.min(2, Math.max(1, Math.ceil(themes.length / Math.max(1, Math.floor(gallery.width / 180))))) * 134
    readonly property real contentHeight: header.implicitHeight + (compact ? galleryNaturalHeight + details.implicitHeight + 16
        : Math.max(galleryNaturalHeight, details.implicitHeight)) + options.implicitHeight + footerMessage.implicitHeight + 64
        + (embedded ? 0 : 40)
    property bool pageActive: visible
    inset: embedded
    color: embedded ? "transparent" : Theme.glassFill
    border.width: embedded ? 0 : Theme.borderWidth
    enabled: !embedded || pageActive
    property var themes: []
    property var selected: null
    property string message: ""
    property bool success: true
    property bool changing: false
    property var importScreen: null
    property bool importing: false
    readonly property bool compact: width < 720
    readonly property bool shortLayout: height < 520
    readonly property int themeCount: gallery.count
    readonly property real galleryWidth: gallery.width
    readonly property real previewWidth: preview.width
    width: Math.min(980, Math.max(1, app.activeScreen ? app.activeScreen.width - 48 : 980))
    height: Math.min(760, Math.max(1, app.activeScreen ? app.activeScreen.height - 48 : 760))

    function focusDefault() { gallery.forceActiveFocus(Qt.OtherFocusReason); }
    function activatePanel() { catalog.running = true; }
    function addWallpaper() {
        if (root.app.nativeDialogOpen) return;
        importScreen = root.app.activeScreen;
        importing = true;
        // Keep the dialog's layer-shell parent mapped, but hand all input and
        // visible content to the normal native window until it is dismissed.
        root.app.nativeDialogOpen = true;
        Qt.callLater(() => { if (root.importing) { importer.open(); importStartup.restart(); } });
    }
    function finishImport(restorePage = true) {
        if (!importing) return;
        importing = false;
        importStartup.stop();
        root.app.nativeDialogOpen = false;
        if (restorePage) root.app.open("appearance", root.importScreen);
    }
    Component.onDestruction: if (importing) root.app.nativeDialogOpen = false
    Timer {
        id: importStartup
        interval: 2000
        onTriggered: if (root.importing && !importer.visible) {
            root.message = "The file picker could not open. Try Add wallpaper again.";
            root.success = false;
            root.finishImport();
        }
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
    Component.onCompleted: catalog.running = true
    Shortcut { sequence: "Ctrl+O"; enabled: root.visible && root.pageActive && !root.app.nativeDialogOpen; context: Qt.WindowShortcut; onActivated: root.addWallpaper() }
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
    FileDialog {
        id: importer
        title: "Add a wallpaper"
        nameFilters: ["Images (*.jpg *.jpeg *.png *.webp)"]
        onVisibleChanged: if (!visible && root.importing) Qt.callLater(() => { if (!importer.visible && root.importing) root.finishImport(); })
        onAccepted: {
            root.finishImport();
            root.command(["theme", "import", decodeURIComponent(selectedFile.toString().replace(/^file:\/\//, ""))]);
        }
        onRejected: root.finishImport()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.embedded ? 0 : root.compact ? 16 : 20
        spacing: root.shortLayout ? 12 : 18
        GridLayout {
            id: header
            Layout.fillWidth: true
            columns: root.compact ? 2 : 3
            columnSpacing: 10
            rowSpacing: 8
            ColumnLayout {
                visible: !root.embedded
                Layout.row: 0
                Layout.column: 0
                Layout.fillWidth: true
                spacing: 4
                C.Label { color: root.foreground; text: "Appearance"; font.pixelSize: root.compact ? 23 : 26; font.weight: Font.DemiBold; Layout.fillWidth: true }
                C.Label { visible: !root.shortLayout; text: "A different atmosphere. One coherent desktop."; color: root.secondary; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
            C.ActionButton { island: root.embedded;
                id: addWallpaper
                objectName: "appearanceAddWallpaper"
                Layout.row: root.compact ? 1 : 0
                Layout.column: root.compact ? 0 : 1
                Layout.columnSpan: root.compact ? 2 : 1
                Layout.fillWidth: root.compact
                KeyNavigation.tab: root.embedded ? gallery : closeButton
                                KeyNavigation.backtab: resetWidgets
                text: "+ Add wallpaper"
                tooltip: "Import a wallpaper · Ctrl+O"
                onClicked: root.addWallpaper()
            }
            C.ActionButton { island: root.embedded; id: closeButton; visible: !root.embedded; objectName: "appearanceClose"; KeyNavigation.tab: gallery; KeyNavigation.backtab: addWallpaper; Layout.row: 0; Layout.column: root.compact ? 1 : 2; text: "×"; font.pixelSize: 20; tooltip: "Close appearance · Esc"; quiet: true; onClicked: root.app.close() }
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
                spacing: Metrics.space4
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
                        KeyNavigation.backtab: root.embedded ? addWallpaper : closeButton
                        keyNavigationWraps: true
                        highlightMoveDuration: Theme.motionControl
                        onCurrentIndexChanged: if (currentIndex >= 0 && currentIndex < root.themes.length) root.selected = root.themes[currentIndex]
                        onActiveFocusChanged: if (activeFocus) root.revealControl(gallery)
                        Keys.onReturnPressed: if (root.selected && !root.changing) root.command(["theme", "use", root.selected.id])
                        Keys.onEnterPressed: if (root.selected && !root.changing) root.command(["theme", "use", root.selected.id])
                        Keys.onSpacePressed: if (currentIndex >= 0) root.selected = root.themes[currentIndex]
                        highlight: Rectangle { color: "transparent"; border.color: root.accent; border.width: 2; radius: Metrics.controlRadius; visible: gallery.activeFocus }
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Item {
                            id: tile
                            required property var modelData
                            required property int index
                            width: gallery.cellWidth - 10
                            height: gallery.cellHeight - 10
                            Rectangle {
                                anchors.fill: parent
                                color: root.embedded ? IslandStyle.raised : Theme.bgPanel
                                radius: IslandStyle.controlRadius
                                border.width: root.selected && root.selected.id === tile.modelData.id ? 2 : 1
                                border.color: root.selected && root.selected.id === tile.modelData.id ? root.accent : root.separator
                                Image { anchors.fill: parent; anchors.margins: 4; anchors.bottomMargin: 29; source: tile.modelData.thumbnail || tile.modelData.wallpaper; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(300,180); asynchronous: true }
                                C.Label { color: root.foreground; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 10; text: tile.modelData.name; font.pixelSize: 12 }
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
                            spacing: Metrics.space3
                            Image { id: preview; visible: !root.compact; Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 250; Layout.maximumWidth: 250; Layout.preferredHeight: root.shortLayout ? 112 : 155; source: root.selected ? root.selected.thumbnail || root.selected.wallpaper : ""; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(600,360) }
                            C.Label { color: root.foreground; text: root.selected ? root.selected.name : "Choose a theme"; font.pixelSize: 20; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Row { spacing: 10; Repeater { model: root.selected ? [root.selected.colors.accentBlue,root.selected.colors.accentCyan,root.selected.colors.accentPink,root.selected.colors.accentWarn] : []; Rectangle { required property string modelData; width: 24; height: 24; radius: 12; color: modelData } } }
                            C.Label { text: "Primary accent"; color: root.secondary; font.pixelSize: 12 }
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
                                color: root.foreground
                                font.family: Theme.fontMono
                                Accessible.name: "Primary accent color"
                                onActiveFocusChanged: if (activeFocus) root.revealControl(accent)
                                background: C.Surface { island: root.embedded; inset: true; border.width: accent.activeFocus ? 2 : Theme.borderWidth; border.color: accent.activeFocus ? root.accent : root.separator }
                            }
                            C.ActionButton { island: root.embedded; id: applyAccent; KeyNavigation.tab: applyTheme; KeyNavigation.backtab: accent; objectName: "appearanceApplyAccent"; text: "Apply accent"; Layout.fillWidth: true; enabled: root.selected !== null && !root.changing && /^#[0-9a-fA-F]{6}$/.test(accent.text); onActiveFocusChanged: if (activeFocus) root.revealControl(applyAccent); onClicked: root.command(["theme", "accent", root.selected.id, accent.text]) }
                            C.ActionButton { island: root.embedded; id: applyTheme; KeyNavigation.tab: classic; KeyNavigation.backtab: applyAccent; objectName: "appearanceApplyTheme"; text: "Apply theme  →"; selected: true; Layout.fillWidth: true; enabled: root.selected !== null && !root.changing; onActiveFocusChanged: if (activeFocus) root.revealControl(applyTheme); onClicked: root.command(["theme", "use", root.selected.id]) }
                        }
                    }
                }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.separator }
                Flow {
                    id: options
                    Layout.fillWidth: true
                    spacing: Metrics.space2
                    C.Label { text: "Desktop · Sumi"; color: root.secondary; height: 36 }
                    C.ActionButton { island: root.embedded; id: classic; KeyNavigation.tab: barMode; KeyNavigation.backtab: applyTheme; objectName: "appearanceClassic"; text: "Switch to Classic"; enabled: !root.changing; onActiveFocusChanged: if (activeFocus) root.revealControl(classic); onClicked: root.command(["profile", "use", "classic"]) }
                    C.ActionButton { island: root.embedded; id: barMode; KeyNavigation.tab: islandStyle; KeyNavigation.backtab: classic; objectName: "appearanceBarMode"; text: Settings.barHiddenMode ? "Bar: hold Shift" : "Bar: visible"; quiet: true; onActiveFocusChanged: if (activeFocus) root.revealControl(barMode); onClicked: Settings.toggle("barHiddenMode") }
                    C.ActionButton { island: root.embedded; id: islandStyle; objectName: "appearanceIslandStyle"; KeyNavigation.tab: motionMode; KeyNavigation.backtab: barMode; text: Settings.islandNotch ? "Center: Notch" : "Center: Island"; quiet: true; tooltip: "Switch the black center island between floating and top-edge notch"; onActiveFocusChanged: if (activeFocus) root.revealControl(islandStyle); onClicked: Settings.toggle("islandNotch") }
                    C.ActionButton { island: root.embedded; id: motionMode; KeyNavigation.tab: editWidgets; KeyNavigation.backtab: islandStyle; objectName: "appearanceMotion"; text: Settings.reducedMotion ? "Motion: reduced" : Settings.fullMotion ? "Motion: expressive" : "Motion: adaptive"; tooltip: "Cycle motion: adaptive, expressive, reduced"; quiet: true; onActiveFocusChanged: if (activeFocus) root.revealControl(motionMode); onClicked: Settings.cycleMotion() }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: Metrics.space2
                    C.ActionButton { island: root.embedded; id: editWidgets; objectName: "appearanceWidgets"; KeyNavigation.tab: widgetLayout; KeyNavigation.backtab: motionMode; text: "Edit widgets"; onActiveFocusChanged: if (activeFocus) root.revealControl(editWidgets); onClicked: root.app.open("widgets", root.app.activeScreen) }
                    C.ActionButton { island: root.embedded;
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
                    C.ActionButton { island: root.embedded; id: resetWidgets; objectName: "appearanceWidgetReset"; KeyNavigation.tab: addWallpaper; KeyNavigation.backtab: widgetLayout; text: "Reset layout"; quiet: true; enabled: S.Widgets.layoutMode !== "curated"; onActiveFocusChanged: if (activeFocus) root.revealControl(resetWidgets); onClicked: S.Widgets.setLayout("curated") }
                }
                C.Label { text: "Widget layout applies to your current wallpaper."; color: root.secondary; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
                C.Label { id: footerMessage; text: root.message || Motion.error || ("Current theme · " + Theme.name); color: root.success && !Motion.error ? root.secondary : Theme.accentPink; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
            }
        }
    }
}
