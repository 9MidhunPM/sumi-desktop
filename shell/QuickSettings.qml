pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
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
    readonly property int panelInset: app.activeScreen && app.activeScreen.height <= 600 ? Metrics.space4 : Metrics.space5
    readonly property real contentHeight: bodyContent.implicitHeight + (embedded ? 0 : header.implicitHeight + footer.implicitHeight + panelInset * 2 + 32)
    property bool pageActive: true
    color: embedded ? "transparent" : Theme.glassFill
    border.width: embedded ? 0 : Theme.borderWidth
    property string section: app.settingsSection || ""
    readonly property bool panelActive: visible && pageActive && (embedded || app.panel === "settings")
    readonly property real brightness: S.Brightness.percent
    readonly property bool brightnessReady: S.Brightness.ready
    readonly property bool brightnessLoading: S.Brightness.loading
    readonly property bool brightnessWriting: S.Brightness.writing
    readonly property bool brightnessWritePending: S.Brightness.writePending
    readonly property bool nightLight: S.NightLight.active
    readonly property bool nightLightAvailable: S.NightLight.available
    readonly property bool nightLightBusy: S.NightLight.busy
    readonly property bool recording: S.Recording.recording
    readonly property bool recordingReady: S.Recording.ready
    readonly property bool recordingBusy: S.Recording.busy
    readonly property string recordingFile: S.Recording.file
    property var sectionState: ({})
    property string previousSection: ""
    function belongsToPage(item) {
        while (item) { if (item === root) return true; item = item.parent; }
        return false;
    }
    function focusableControl(item) {
        return item && (item.activeFocusOnTab || typeof item.clicked === "function" || item === password || item === audioHeading);
    }
    function rememberPage(name) {
        const saved = root.sectionState[name] || {};
        const focused = root.Window.window ? root.Window.window.activeFocusItem : null;
        const values = Object.assign({}, root.sectionState);
        values[name] = {scroll: body.contentItem.contentY, focus: focused && belongsToPage(focused) && focusableControl(focused) ? focused : saved.focus || null};
        root.sectionState = values;
    }
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() {
            if (!root.panelActive) return;
            const focused = root.Window.window.activeFocusItem;
            if (!focused || !root.belongsToPage(focused) || !root.focusableControl(focused)) return;
            const saved = Object.assign({}, root.sectionState[root.section] || {}, {focus: focused});
            const values = Object.assign({}, root.sectionState);
            values[root.section] = saved;
            root.sectionState = values;
        }
    }
    property string controlError: ""
    property var selectedNetwork: null
    readonly property string pageTitle: ({wifi: "Wi-Fi", bluetooth: "Bluetooth", audio: "Sound devices", capture: "Capture & record"})[section] || "Control center"
    width: Math.min(440, Math.max(1, app.activeScreen ? app.activeScreen.width - 48 : 440))
    // Small subpages fit their contents; only long device lists scroll.
    height: Math.min(header.implicitHeight + bodyContent.implicitHeight + footer.implicitHeight + panelInset * 2 + 32,
        Math.max(1, app.activeScreen ? app.activeScreen.height - Theme.panelTop - 24 : 780))

    function updateScanning(): void {
        // Root owns discovery; cached per-monitor panels only publish navigation.
        if (!root.embedded && root.panelActive && typeof root.app.settingsSection !== "undefined") root.app.settingsSection = root.section;
    }
    function focusFirst(): void {
        Qt.callLater(() => {
            if (!root.panelActive) return;
            let target = wifiTile;
            if (root.section === "wifi") target = wifiToggle.enabled ? wifiToggle : body;
            else if (root.section === "bluetooth") target = bluetoothToggle.enabled ? bluetoothToggle : pairButton;
            else if (root.section === "audio") target = !root.embedded ? audioManagerButton : outputDevices.count ? outputDevices.itemAt(0) : audioHeading;
            else if (root.section === "capture") target = captureRegion;
            const saved = root.embedded ? root.sectionState[root.section] : null;
            if (saved && saved.focus && saved.focus.visible && saved.focus.enabled && root.focusableControl(saved.focus)) target = saved.focus;
            target.forceActiveFocus(Qt.OtherFocusReason);
            if (saved && typeof saved.scroll === "number") {
                const selectedSection = root.section;
                Qt.callLater(() => {
                    if (root.panelActive && root.section === selectedSection)
                        body.contentItem.contentY = Math.max(0, Math.min(saved.scroll, body.contentItem.contentHeight - body.contentItem.height));
                });
            } else { body.contentItem.contentY = 0; body.revealItem(target); }
        });
    }
    function focusDefault(): void { focusFirst(); }
    function back(): bool { if (selectedNetwork) { selectedNetwork = null; password.clear(); return true; } if (section === "bluetooth" && S.Bluetooth.pairing) { S.Bluetooth.cancelPairing(); return true; } return false; }
    function openAudioManager(): void { if (!embedded) { root.app.close(); S.Audio.openManager(); } }
    function openBluetoothManager(): void { if (!embedded) { root.app.close(); S.Bluetooth.openManager(); } }
    function readBrightness(): void { S.Brightness.refresh(); }
    function queueBrightness(value): void { S.Brightness.setPercent(value); }
    function commitBrightness(): void { S.Brightness.commit(); }
    function readNightLight(): void { S.NightLight.refresh(); }
    function toggleNightLight(): void { S.NightLight.toggle(); }
    function refreshRecording(): void { S.Recording.refresh(); }
    function stopRecording(): void { S.Recording.stop(); }
    function activate(): void {
        root.controlError = "";
        if (!embedded) section = root.app.settingsSection || "";
        if (!S.Desktop.preview) {
            root.readBrightness();
            if (!root.nightLightBusy) root.readNightLight();
            if (root.section === "capture") root.refreshRecording();
        }
        focusFirst();
    }
    function connectSelected(): void {
        if (!root.selectedNetwork || S.Network.connecting) return;
        S.Network.connect(root.selectedNetwork, password.text);
        password.clear();
    }
    onSectionChanged: {
        rememberPage(previousSection);
        previousSection = section;
        updateScanning();
        root.selectedNetwork = null;
        password.clear();
        root.controlError = "";
        if (root.section === "capture" && root.panelActive) root.refreshRecording();
        focusFirst();
    }
    onPanelActiveChanged: {
        if (!panelActive) { rememberPage(section); root.selectedNetwork = null; password.clear(); if (root.section === "bluetooth" && S.Bluetooth.pairing) S.Bluetooth.cancelPairing(); }
        else focusFirst();
    }
    Component.onCompleted: activate()
    Connections {
        target: S.Network
        function onConnectingChanged() {
            if (!S.Network.connecting && !S.Network.connectionError) root.selectedNetwork = null;
        }
    }

    Connections { target: S.Brightness; function onErrorChanged() { if (S.Brightness.error) root.controlError = S.Brightness.error; } }
    Connections { target: S.NightLight; function onErrorChanged() { if (S.NightLight.error) root.controlError = S.NightLight.error; } }
    Connections { target: S.Recording; function onErrorChanged() { if (S.Recording.error) root.controlError = S.Recording.error; } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.embedded ? 0 : root.panelInset
        spacing: Metrics.space4

        RowLayout {
            id: header
            visible: !root.embedded
            Layout.fillWidth: true
            spacing: 10
            C.QuickButton { island: root.embedded; id: backButton; objectName: "settingsBack"; visible: root.section.length > 0; glyph: "󰁍"; quiet: true; compact: true; tooltip: "Back to controls"; onClicked: root.section = "" }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                C.Label { color: root.foreground; text: root.pageTitle; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
                C.Label { text: root.section.length > 0 ? "Your devices, in one place" : Qt.formatDateTime(S.Clock.date, "dddd, d MMMM"); color: root.secondary; font.pixelSize: 12; Layout.fillWidth: true }
            }
            C.QuickButton { island: root.embedded; objectName: "settingsClose"; glyph: "󰅖"; quiet: true; compact: true; tooltip: "Close controls · Esc"; onClicked: root.app.close() }
        }

        C.PanelScrollView {
            id: body
            objectName: "settingsBody"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0

            ColumnLayout {
                id: bodyContent
                width: body.availableWidth
                spacing: Metrics.space4
                C.Label { visible: root.controlError.length > 0; text: root.controlError; color: Theme.accentWarn; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }

                ColumnLayout {
                    visible: root.section === ""
                    Layout.fillWidth: true
                    spacing: Metrics.space4

                    GridLayout {
                        columns: 2
                        columnSpacing: Metrics.space3
                        rowSpacing: Metrics.space3
                        Layout.fillWidth: true
                        C.QuickTile { island: root.embedded;
                            id: wifiTile
                            objectName: "settingsWifi"
                            Layout.fillWidth: true
                            text: "Wi-Fi"
                            glyph: S.Network.wifiEnabled ? "󰤨" : "󰤭"
                            subtitle: !S.Network.wifiAvailable ? "Unavailable" : S.Network.connected ? S.Network.name : S.Network.wifiEnabled ? "Not connected" : "Off"
                            selected: S.Network.wifiEnabled
                            disclosure: true
                            secondaryText: S.Network.wifiEnabled ? "On" : "Off"
                            secondaryLabel: S.Network.wifiEnabled ? "Turn Wi-Fi off" : "Turn Wi-Fi on"
                            secondaryEnabled: S.Network.wifiAvailable
                            onSecondaryClicked: S.Network.toggleWifi()
                            onClicked: root.section = "wifi"
                        }
                        C.QuickTile { island: root.embedded;
                            objectName: "settingsBluetooth"
                            Layout.fillWidth: true
                            text: "Bluetooth"
                            glyph: S.Bluetooth.enabled ? "󰂯" : "󰂲"
                            subtitle: !S.Bluetooth.available ? "Unavailable" : !S.Bluetooth.enabled ? "Off" : S.Bluetooth.connectedCount > 0 ? S.Bluetooth.connectedCount + " connected" : "Ready to connect"
                            selected: S.Bluetooth.enabled
                            disclosure: true
                            secondaryText: S.Bluetooth.enabled ? "On" : "Off"
                            secondaryLabel: S.Bluetooth.enabled ? "Turn Bluetooth off" : "Turn Bluetooth on"
                            secondaryEnabled: S.Bluetooth.available
                            onSecondaryClicked: S.Bluetooth.toggle()
                            onClicked: root.section = "bluetooth"
                            TapHandler { acceptedButtons: Qt.RightButton; onTapped: root.openBluetoothManager() }
                        }
                        C.QuickTile { island: root.embedded;
                            Layout.fillWidth: true
                            text: "Do not disturb"
                            glyph: Settings.dnd ? "󰂛" : "󰂚"
                            subtitle: Settings.dnd ? "Notifications silenced" : "Notifications allowed"
                            selected: Settings.dnd
                            onClicked: S.Notifications.toggleDnd()
                        }
                        C.QuickTile { island: root.embedded;
                            objectName: "settingsNightLight"
                            Layout.fillWidth: true
                            text: "Night light"
                            glyph: "󰖔"
                            subtitle: root.nightLightBusy ? "Applying…" : !root.nightLightAvailable ? "Unavailable" : root.nightLight ? "Warm display" : "Natural display"
                            selected: root.nightLight
                            enabled: root.nightLightAvailable && !root.nightLightBusy
                            onClicked: root.toggleNightLight()
                        }
                    }

                    ColumnLayout {
                        objectName: "settingsSound"
                        Layout.fillWidth: true
                        spacing: 5
                        TapHandler { acceptedButtons: Qt.RightButton; onTapped: root.openAudioManager() }
                        RowLayout {
                            Layout.fillWidth: true
                            C.QuickButton { island: root.embedded; objectName: "settingsMute"; glyph: S.Audio.muted ? "󰖁" : "󰕾"; enabled: S.Audio.hasOutput; compact: true; quiet: true; tooltip: S.Audio.muted ? "Unmute sound" : "Mute sound"; onClicked: S.Audio.toggleMute() }
                            C.Label { color: root.foreground; text: S.Audio.muted ? "Sound muted" : "Volume"; font.weight: Font.Medium; Layout.fillWidth: true }
                            C.Label { text: Math.round(S.Audio.volume * 100) + "%"; color: root.secondary; font.pixelSize: 12 }
                            C.QuickButton { island: root.embedded; glyph: "󰁔"; compact: true; quiet: true; tooltip: "Choose sound devices"; onClicked: root.section = "audio" }
                        }
                        C.Label { objectName: "settingsOutputName"; text: S.Audio.outputName; color: root.secondary; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                        C.QuickSlider { island: root.embedded; objectName: "settingsOutputVolume"; label: "Output volume"; Layout.fillWidth: true; enabled: S.Audio.hasOutput; value: S.Audio.volume; onMoved: S.Audio.setVolume(value) }
                        RowLayout {
                            Layout.fillWidth: true
                            C.QuickButton { island: root.embedded; text: S.Audio.hasInput ? S.Audio.sourceMuted ? "Microphone muted" : "Microphone on" : "No microphone"; glyph: S.Audio.sourceMuted ? "󰍭" : "󰍬"; enabled: S.Audio.hasInput; compact: true; quiet: true; selected: S.Audio.sourceMuted; onClicked: S.Audio.toggleSourceMute() }
                            Item { Layout.fillWidth: true }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        RowLayout {
                            Layout.fillWidth: true
                            C.Label { color: root.foreground; text: "󰃠"; font.pixelSize: 20; Layout.preferredWidth: 40; horizontalAlignment: Text.AlignHCenter }
                            C.Label { color: root.foreground; text: "Brightness"; font.weight: Font.Medium; Layout.fillWidth: true }
                            C.Label { text: root.brightnessReady ? Math.round(root.brightness) + "%" : root.brightnessLoading ? "Loading…" : "Unavailable"; color: root.secondary; font.pixelSize: 12 }
                        }
                        C.QuickSlider { island: root.embedded; objectName: "settingsBrightness"; label: "Display brightness"; Layout.fillWidth: true; from: 0.01; enabled: root.brightnessReady; value: root.brightness / 100; onMoved: root.queueBrightness(value * 100) }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            C.Label { color: root.foreground; text: S.Battery.charging ? "󰂄" : "󰁹"; font.pixelSize: 20 }
                            C.Label { color: root.foreground; text: S.Battery.available ? Math.round(S.Battery.percent) + "%" : "Power"; font.weight: Font.Medium }
                            C.Label { text: S.Battery.timeLabel; font.pixelSize: 11; color: root.secondary; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: width < 350 ? 1 : 3
                            columnSpacing: 5
                            rowSpacing: 5
                            Repeater {
                                model: [{id: "power-saver", label: "Saver", glyph: "󰌪"}, {id: "balanced", label: "Balanced", glyph: "󰾅"}, {id: "performance", label: "Performance", glyph: "󰓅"}]
                                C.QuickButton { island: root.embedded;
                                    required property var modelData
                                    text: modelData.label
                                    glyph: modelData.glyph
                                    compact: true
                                    Layout.fillWidth: true
                                    enabled: modelData.id !== "performance" || S.Battery.performanceAvailable
                                    selected: S.Battery.profile === modelData.id
                                    onClicked: S.Battery.setProfile(modelData.id)
                                }
                            }
                        }
                    }

                    RowLayout {
                        visible: S.Media.available
                        Layout.fillWidth: true
                        spacing: Metrics.space3
                        Rectangle {
                            Layout.preferredWidth: 46
                            Layout.preferredHeight: 46
                            radius: Metrics.controlRadius
                            color: Theme.bgPlaying
                            clip: true
                            C.Label { anchors.centerIn: parent; text: "󰎆"; color: root.accent; font.pixelSize: 23 }
                            Image { anchors.fill: parent; visible: status === Image.Ready; source: S.Media.artUrl; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(92, 92); asynchronous: true }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            C.Label { color: root.foreground; text: S.Media.title; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight }
                            C.Label { text: S.Media.artist; color: root.secondary; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
                        }
                        C.QuickButton { island: root.embedded; glyph: S.Media.playing ? "󰏤" : "󰐊"; quiet: true; tooltip: S.Media.playing ? "Pause playback" : "Play"; onClicked: S.Media.toggle() }
                    }
                }

                ColumnLayout {
                    visible: root.section === "wifi"
                    Layout.fillWidth: true
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        C.Label { color: root.foreground; text: S.Network.wifiEnabled ? "Available networks" : "Wi-Fi is off"; font.weight: Font.Medium; Layout.fillWidth: true }
                        C.QuickButton { island: root.embedded; id: wifiToggle; text: S.Network.wifiEnabled ? "Turn off" : "Turn on"; selected: S.Network.wifiEnabled; compact: true; enabled: S.Network.wifiAvailable; onClicked: S.Network.toggleWifi() }
                    }
                    C.Label { visible: !S.Network.wifiAvailable || (S.Network.wifiEnabled && S.Network.networks.length === 0); text: !S.Network.wifiAvailable ? "No wireless adapter is available." : "Looking for nearby networks…"; color: root.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    C.Label { visible: S.Network.captivePortal; text: "This network needs a browser sign-in."; color: Theme.accentWarn; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    C.Label { visible: S.Network.connecting || S.Network.connectionError.length > 0; text: S.Network.connecting ? "Connecting to " + (S.Network.pendingNetwork ? S.Network.pendingNetwork.name : "network") + "…" : S.Network.connectionError; color: S.Network.connectionError ? Theme.accentPink : root.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Repeater {
                        model: S.Network.wifiEnabled ? S.Network.networks : []
                        C.QuickDeviceRow { island: root.embedded;
                            required property var modelData
                            Layout.fillWidth: true
                            text: modelData.name
                            glyph: "󰤨"
                            subtitle: modelData.connected ? "Connected · select to disconnect" : "Select to connect"
                            selected: modelData.connected
                            onClicked: {
                                if (modelData.connected) S.Network.disconnect(modelData);
                                else if (!S.Network.connecting) { root.selectedNetwork = modelData; S.Network.connectionError = ""; Qt.callLater(() => password.forceActiveFocus()); }
                            }
                        }
                    }
                    ColumnLayout {
                        visible: root.selectedNetwork !== null
                        Layout.fillWidth: true
                        spacing: Metrics.space3
                        C.Label { color: root.foreground; text: root.selectedNetwork ? "Connect to " + root.selectedNetwork.name : ""; font.weight: Font.Medium; Layout.fillWidth: true }
                        TextField {
                            id: password
                            Layout.fillWidth: true
                            implicitHeight: 44
                            padding: 12
                            placeholderText: "Password · leave blank for a saved network"
                            echoMode: TextInput.Password
                            color: root.foreground
                            placeholderTextColor: root.secondary
                            font.family: Theme.font
                            font.pixelSize: 12
                            selectByMouse: true
                            Accessible.name: "Wi-Fi password"
                            onAccepted: root.connectSelected()
                            background: Rectangle { radius: Metrics.controlRadius; color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.06); border.width: password.activeFocus ? 2 : 1; border.color: password.activeFocus ? root.accent : root.separator }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            C.QuickButton { island: root.embedded; text: "Cancel"; quiet: true; onClicked: { root.selectedNetwork = null; password.clear(); } }
                            Item { Layout.fillWidth: true }
                            C.QuickButton { island: root.embedded; text: S.Network.connecting ? "Connecting…" : "Connect"; enabled: !S.Network.connecting; selected: true; onClicked: root.connectSelected() }
                        }
                    }
                }

                ColumnLayout {
                    visible: root.section === "bluetooth"
                    Layout.fillWidth: true
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        C.Label { color: root.foreground; text: S.Bluetooth.enabled ? "Your devices" : "Bluetooth is off"; font.weight: Font.Medium; Layout.fillWidth: true }
                        C.QuickButton { island: root.embedded; id: bluetoothToggle; text: S.Bluetooth.enabled ? "Turn off" : "Turn on"; selected: S.Bluetooth.enabled; compact: true; enabled: S.Bluetooth.available; onClicked: S.Bluetooth.toggle() }
                    }
                    C.Label { visible: !S.Bluetooth.available || (S.Bluetooth.enabled && S.Bluetooth.devices.length === 0); text: !S.Bluetooth.available ? "No Bluetooth adapter is available." : "Looking for nearby devices…"; color: root.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Repeater {
                        model: S.Bluetooth.enabled ? S.Bluetooth.sortedDevices : []
                        C.QuickDeviceRow { island: root.embedded;
                            required property var modelData
                            Layout.fillWidth: true
                            text: modelData.name || modelData.address
                            glyph: "󰂯"
                            subtitle: modelData.connected ? "Connected · select to disconnect" : modelData.paired ? "Paired · select to connect" : "Select to pair"
                            selected: modelData.connected
                            onClicked: { if (modelData.connected) S.Bluetooth.disconnectDevice(modelData); else if (modelData.paired) S.Bluetooth.connectDevice(modelData); else S.Bluetooth.pairDevice(modelData); }
                        }
                    }
                    ColumnLayout {
                        visible: S.Bluetooth.pairing || S.Bluetooth.pairingError.length > 0
                        Layout.fillWidth: true
                        C.Label { color: root.foreground; Layout.fillWidth: true; text: S.Bluetooth.pairing ? "Pairing with " + S.Bluetooth.pairingName : "Pairing ended"; font.weight: Font.DemiBold }
                        C.Label { color: root.foreground; Layout.fillWidth: true; wrapMode: Text.Wrap; text: S.Bluetooth.promptKind === "DisplayPinCode" || S.Bluetooth.promptKind === "DisplayPasskey" ? "Enter " + S.Bluetooth.promptValue + " on your device" : S.Bluetooth.promptKind === "RequestConfirmation" ? "Does " + S.Bluetooth.promptValue + " match the code on your device?" : S.Bluetooth.promptKind === "RequestPinCode" || S.Bluetooth.promptKind === "RequestPasskey" ? "Enter the code for your device" : S.Bluetooth.promptKind ? "Allow this device to pair?" : "Waiting for device…"; visible: S.Bluetooth.pairing }
                        TextField { id: pairingCode; Layout.fillWidth: true; visible: S.Bluetooth.promptKind === "RequestPinCode" || S.Bluetooth.promptKind === "RequestPasskey"; placeholderText: "Pairing code"; Accessible.name: "Bluetooth pairing code"; color: root.foreground; onAccepted: { S.Bluetooth.answerPairing(text); clear(); } }
                        RowLayout {
                            visible: S.Bluetooth.pairing
                            C.QuickButton { island: root.embedded; text: "Cancel"; onClicked: { S.Bluetooth.cancelPairing(); pairingCode.clear(); } }
                            C.QuickButton { island: root.embedded; text: "Confirm"; selected: true; visible: S.Bluetooth.promptKind.length > 0 && S.Bluetooth.promptKind.indexOf("Display") !== 0; onClicked: { S.Bluetooth.answerPairing(pairingCode.visible ? pairingCode.text : true); pairingCode.clear(); } }
                        }
                        C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; visible: S.Bluetooth.pairingError.length > 0; text: S.Bluetooth.pairingError; color: Theme.accentWarn }
                    }
                    C.QuickButton { island: root.embedded; id: pairButton; visible: !root.embedded; objectName: "settingsBluetoothManager"; text: "Open Bluetooth manager"; tooltip: "Pair devices and manage Bluetooth"; glyph: "󰂯"; Layout.fillWidth: true; onClicked: root.openBluetoothManager() }
                }

                ColumnLayout {
                    visible: root.section === "audio"
                    Layout.fillWidth: true
                    spacing: Metrics.space2
                    TapHandler { acceptedButtons: Qt.RightButton; onTapped: root.openAudioManager() }
                    C.QuickButton { island: root.embedded; id: audioManagerButton; visible: !root.embedded; objectName: "settingsAudioManager"; text: "Open sound mixer"; glyph: "󰕾"; Layout.fillWidth: true; onClicked: root.openAudioManager() }
                    C.Label { color: root.foreground; id: audioHeading; text: "Output"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    C.Label { text: S.Audio.outputName; color: root.secondary; font.pixelSize: 11; Layout.fillWidth: true }
                    C.QuickSlider { island: root.embedded; label: "Output volume"; Layout.fillWidth: true; enabled: S.Audio.hasOutput; value: S.Audio.volume; onMoved: S.Audio.setVolume(value) }
                    C.Label { visible: S.Audio.sinks.length === 0; text: "No output devices are available."; color: root.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Repeater { id: outputDevices; model: S.Audio.sinks; C.QuickDeviceRow { island: root.embedded; required property var modelData; text: modelData.description || modelData.name; glyph: "󰓃"; Layout.fillWidth: true; selected: modelData === S.Audio.sink; onClicked: S.Audio.selectSink(modelData) } }
                    Item { Layout.preferredHeight: 8 }
                    C.Label { color: root.foreground; text: "Input"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    RowLayout {
                        Layout.fillWidth: true
                        C.QuickButton { island: root.embedded; text: S.Audio.sourceMuted ? "Unmute microphone" : "Mute microphone"; glyph: S.Audio.sourceMuted ? "󰍭" : "󰍬"; enabled: S.Audio.hasInput; compact: true; quiet: true; selected: S.Audio.sourceMuted; onClicked: S.Audio.toggleSourceMute() }
                        Item { Layout.fillWidth: true }
                        C.Label { text: Math.round(S.Audio.sourceVolume * 100) + "%"; color: root.secondary; font.pixelSize: 12 }
                    }
                    C.Label { objectName: "settingsInputName"; text: S.Audio.inputName; color: root.secondary; font.pixelSize: 11; Layout.fillWidth: true }
                    C.QuickSlider { island: root.embedded; objectName: "settingsInputVolume"; label: "Microphone level"; Layout.fillWidth: true; enabled: S.Audio.hasInput; value: S.Audio.sourceVolume; onMoved: S.Audio.setSourceVolume(value) }
                    C.Label { visible: S.Audio.sources.length === 0; text: "No input devices are available."; color: root.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Repeater { id: inputDevices; model: S.Audio.sources; C.QuickDeviceRow { island: root.embedded; required property var modelData; text: modelData.description || modelData.name; glyph: "󰍬"; Layout.fillWidth: true; selected: modelData === S.Audio.source; onClicked: S.Audio.selectSource(modelData) } }
                }

                ColumnLayout {
                    visible: root.section === "capture"
                    Layout.fillWidth: true
                    spacing: Metrics.space2
                    C.Label { color: root.foreground; text: "Screenshots"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    C.QuickDeviceRow { island: root.embedded; id: captureRegion; text: "Capture a region"; subtitle: "Select an area of your screen"; glyph: "󰄀"; Layout.fillWidth: true; onClicked: { if (typeof root.app.selectCapture === "function") root.app.selectCapture(false, false); else { root.app.close(); S.Desktop.action("capture", ["region"]); } } }
                    C.QuickDeviceRow { island: root.embedded; text: "Capture & annotate"; subtitle: "Draw, highlight and crop in Satty"; glyph: "󰏫"; Layout.fillWidth: true; onClicked: { if (typeof root.app.selectCapture === "function") root.app.selectCapture(true, false); else { root.app.close(); S.Desktop.action("capture", ["region", "annotate"]); } } }
                    Item { Layout.preferredHeight: 4 }
                    RowLayout {
                        Layout.fillWidth: true
                        C.Label { color: root.foreground; text: "Screen recording"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        C.QuickButton { island: root.embedded; text: "Refresh"; compact: true; quiet: true; enabled: !root.recordingBusy; onClicked: root.refreshRecording() }
                    }
                    C.Label { text: root.recordingBusy ? "Checking recording…" : !root.recordingReady ? "Recording status unavailable" : root.recording ? "Recording in progress" : "Ready to record"; color: root.recording ? Theme.accentWarn : root.secondary; Layout.fillWidth: true }
                    C.QuickDeviceRow { island: root.embedded; objectName: "settingsRecordStart"; visible: !root.recording; enabled: root.recordingReady && !root.recordingBusy; text: "Record a region"; subtitle: "Select an area to start recording"; glyph: "󰑋"; Layout.fillWidth: true; onClicked: { if (typeof root.app.selectCapture === "function") root.app.selectCapture(false, true); else { root.app.close(); Qt.callLater(() => S.Recording.start()); } } }
                    C.QuickDeviceRow { island: root.embedded; objectName: "settingsRecordStop"; visible: root.recording; enabled: root.recordingReady && !root.recordingBusy; text: "Stop recording"; subtitle: "Save the current recording"; glyph: "󰓛"; Layout.fillWidth: true; onClicked: root.stopRecording() }
                }
            }
        }

        ColumnLayout {
            id: footer
            visible: !root.embedded
            Layout.fillWidth: true
            spacing: 10
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: root.separator; opacity: 0.5 }
            RowLayout {
                Layout.fillWidth: true
                spacing: 5
                C.QuickButton { island: root.embedded; text: "Appearance"; glyph: "󰏘"; quiet: true; compact: true; onClicked: root.app.open("appearance", null) }
                C.QuickButton { island: root.embedded; glyph: "󰄀"; quiet: true; compact: true; tooltip: "Capture & record"; onClicked: root.section = root.section === "capture" ? "" : "capture" }
                Item { Layout.fillWidth: true }
                C.QuickButton { island: root.embedded; glyph: "󰌾"; quiet: true; compact: true; tooltip: "Lock session"; onClicked: { root.app.close(); S.Desktop.action("lock", []); } }
                C.QuickButton { island: root.embedded; glyph: "󰐥"; quiet: true; compact: true; tooltip: "Session & power"; onClicked: root.app.open("power", null) }
            }
        }
    }
}
