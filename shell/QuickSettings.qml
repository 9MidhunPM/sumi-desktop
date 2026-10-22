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
    property string section: app.settingsSection || ""
    readonly property bool panelActive: visible && app.panel === "settings"
    property real brightness: 0
    property bool brightnessReady: false
    property bool brightnessLoading: false
    property int brightnessReadSerial: 0
    property bool nightLight: false
    property bool nightLightAvailable: false
    property bool nightLightBusy: false
    property int nightLightSerial: 0
    property bool recording: false
    property bool recordingReady: false
    property bool recordingBusy: false
    property string recordingFile: ""
    property string controlError: ""
    property var selectedNetwork: null
    readonly property string pageTitle: ({wifi: "Wi-Fi", bluetooth: "Bluetooth", audio: "Sound devices", capture: "Capture & record"})[section] || "Control center"
    width: Math.min(440, Math.max(1, app.activeScreen ? app.activeScreen.width - 48 : 440))
    // Small subpages fit their contents; only long device lists scroll.
    height: Math.min(header.implicitHeight + bodyContent.implicitHeight + footer.implicitHeight + 72,
        Math.max(1, app.activeScreen ? app.activeScreen.height - Theme.panelTop - 24 : 780))

    function updateScanning(): void {
        // Root owns discovery; cached per-monitor panels only publish navigation.
        if (root.panelActive && typeof root.app.settingsSection !== "undefined") root.app.settingsSection = root.section;
    }
    function focusFirst(): void {
        Qt.callLater(() => {
            if (!root.panelActive) return;
            let target = wifiTile;
            if (root.section === "wifi") target = wifiToggle.enabled ? wifiToggle : body;
            else if (root.section === "bluetooth") target = bluetoothToggle.enabled ? bluetoothToggle : pairButton;
            else if (root.section === "audio") target = audioManagerButton;
            else if (root.section === "capture") target = captureRegion;
            body.contentItem.contentY = 0;
            target.forceActiveFocus(Qt.OtherFocusReason);
            body.revealItem(target);
        });
    }
    function focusDefault(): void { focusFirst(); }
    function openAudioManager(): void { root.app.close(); S.Audio.openManager(); }
    function openBluetoothManager(): void { root.app.close(); S.Bluetooth.openManager(); }
    function readBrightness(): void {
        const serial = ++root.brightnessReadSerial;
        root.brightnessLoading = true;
        root.brightnessReady = false;
        S.Desktop.action("brightness-get", [], function(ok, result, error) {
            if (serial !== root.brightnessReadSerial) return;
            root.brightnessLoading = false;
            root.brightnessReady = ok && typeof result.percent === "number" && isFinite(result.percent) && result.percent >= 0 && result.percent <= 100;
            if (root.brightnessReady) root.brightness = result.percent;
            else root.controlError = error || "Display brightness is unavailable.";
        });
    }
    function readNightLight(): void {
        const serial = ++root.nightLightSerial;
        S.Desktop.action("night-light-get", [], function(ok, result, error) {
            if (serial !== root.nightLightSerial) return;
            root.nightLightAvailable = ok && result.available === true;
            if (ok) root.nightLight = result.active === true;
            else root.controlError = error || "Night light is unavailable.";
        });
    }
    function toggleNightLight(): void {
        if (!root.nightLightAvailable || root.nightLightBusy) return;
        ++root.nightLightSerial;
        root.nightLightBusy = true;
        root.controlError = "";
        S.Desktop.action("night-light", [], function(ok, result, error) {
            root.nightLightBusy = false;
            if (ok) {
                root.nightLightAvailable = result.available === true;
                root.nightLight = result.active === true;
            } else {
                root.controlError = error || "Could not change night light.";
                root.readNightLight();
            }
        });
    }
    function refreshRecording(): void {
        if (S.Desktop.preview || root.recordingBusy) return;
        root.recordingReady = false;
        root.recordingBusy = true;
        S.Desktop.action("record", ["status"], function(ok, result, error) {
            root.recordingBusy = false;
            root.recordingReady = ok && typeof result.recording === "boolean";
            if (root.recordingReady) { root.recording = result.recording; root.recordingFile = result.file || ""; }
            else root.controlError = error || "Recording status is unavailable.";
        });
    }
    function stopRecording(): void {
        if (!root.recordingReady || !root.recording || root.recordingBusy) return;
        root.recordingBusy = true;
        root.controlError = "";
        S.Desktop.action("record", ["stop"], function(ok, result, error) {
            root.recordingBusy = false;
            if (ok) { root.recording = result.recording === true; root.recordingFile = result.file || ""; }
            else { root.controlError = error || "Could not stop recording."; root.refreshRecording(); }
        });
    }
    function activate(): void {
        root.controlError = "";
        section = root.app.settingsSection || "";
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
        updateScanning();
        root.selectedNetwork = null;
        password.clear();
        root.controlError = "";
        if (root.section === "capture" && root.panelActive) root.refreshRecording();
        focusFirst();
    }
    onPanelActiveChanged: if (!panelActive) { root.selectedNetwork = null; password.clear(); }
    Component.onCompleted: activate()
    Connections {
        target: S.Network
        function onConnectingChanged() {
            if (!S.Network.connecting && !S.Network.connectionError) root.selectedNetwork = null;
        }
    }

    Timer {
        id: brightnessCommit
        interval: 70
        onTriggered: {
            ++root.brightnessReadSerial;
            S.Desktop.action("brightness", [root.brightness], function(ok, result, error) {
                if (!ok) { root.controlError = error || "Could not change brightness."; root.readBrightness(); }
            });
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 16

        RowLayout {
            id: header
            Layout.fillWidth: true
            spacing: 10
            C.QuickButton { id: backButton; objectName: "settingsBack"; visible: root.section.length > 0; glyph: "󰁍"; quiet: true; compact: true; tooltip: "Back to controls"; onClicked: root.section = "" }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                C.Label { text: root.pageTitle; font.pixelSize: 22; font.weight: Font.DemiBold; Layout.fillWidth: true }
                C.Label { text: root.section.length > 0 ? "Your devices, in one place" : Qt.formatDateTime(S.Clock.date, "dddd, d MMMM"); color: Theme.textSoft; font.pixelSize: 12; Layout.fillWidth: true }
            }
            C.QuickButton { objectName: "settingsClose"; glyph: "󰅖"; quiet: true; compact: true; tooltip: "Close controls · Esc"; onClicked: root.app.close() }
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
                spacing: 16
                C.Label { visible: root.controlError.length > 0; text: root.controlError; color: Theme.accentWarn; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }

                ColumnLayout {
                    visible: root.section === ""
                    Layout.fillWidth: true
                    spacing: 16

                    GridLayout {
                        columns: 2
                        columnSpacing: 10
                        rowSpacing: 10
                        Layout.fillWidth: true
                        C.QuickTile {
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
                        C.QuickTile {
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
                        C.QuickTile {
                            Layout.fillWidth: true
                            text: "Do not disturb"
                            glyph: Settings.dnd ? "󰂛" : "󰂚"
                            subtitle: Settings.dnd ? "Notifications silenced" : "Notifications allowed"
                            selected: Settings.dnd
                            onClicked: S.Notifications.toggleDnd()
                        }
                        C.QuickTile {
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
                            C.QuickButton { objectName: "settingsMute"; glyph: S.Audio.muted ? "󰖁" : "󰕾"; enabled: S.Audio.hasOutput; compact: true; quiet: true; tooltip: S.Audio.muted ? "Unmute sound" : "Mute sound"; onClicked: S.Audio.toggleMute() }
                            C.Label { text: S.Audio.muted ? "Sound muted" : "Volume"; font.weight: Font.Medium; Layout.fillWidth: true }
                            C.Label { text: Math.round(S.Audio.volume * 100) + "%"; color: Theme.textSoft; font.pixelSize: 12 }
                            C.QuickButton { glyph: "󰁔"; compact: true; quiet: true; tooltip: "Choose sound devices"; onClicked: root.section = "audio" }
                        }
                        C.Label { objectName: "settingsOutputName"; text: S.Audio.outputName; color: Theme.textSoft; font.pixelSize: 11; Layout.fillWidth: true }
                        C.QuickSlider { objectName: "settingsOutputVolume"; label: "Output volume"; Layout.fillWidth: true; enabled: S.Audio.hasOutput; value: S.Audio.volume; onMoved: S.Audio.setVolume(value) }
                        RowLayout {
                            Layout.fillWidth: true
                            C.QuickButton { text: S.Audio.hasInput ? S.Audio.sourceMuted ? "Microphone muted" : "Microphone on" : "No microphone"; glyph: S.Audio.sourceMuted ? "󰍭" : "󰍬"; enabled: S.Audio.hasInput; compact: true; quiet: true; selected: S.Audio.sourceMuted; onClicked: S.Audio.toggleSourceMute() }
                            Item { Layout.fillWidth: true }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        RowLayout {
                            Layout.fillWidth: true
                            C.Label { text: "󰃠"; font.pixelSize: 20; Layout.preferredWidth: 40; horizontalAlignment: Text.AlignHCenter }
                            C.Label { text: "Brightness"; font.weight: Font.Medium; Layout.fillWidth: true }
                            C.Label { text: root.brightnessLoading ? "Loading…" : root.brightnessReady ? Math.round(root.brightness) + "%" : "Unavailable"; color: Theme.textSoft; font.pixelSize: 12 }
                        }
                        C.QuickSlider { objectName: "settingsBrightness"; label: "Display brightness"; Layout.fillWidth: true; from: 0.01; enabled: root.brightnessReady; value: root.brightness / 100; onMoved: { root.brightness = Math.round(value * 100); brightnessCommit.restart(); } }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            C.Label { text: S.Battery.charging ? "󰂄" : "󰁹"; font.pixelSize: 20 }
                            C.Label { text: S.Battery.available ? Math.round(S.Battery.percent) + "%" : "Power"; font.weight: Font.Medium }
                            C.Label { text: S.Battery.timeLabel; font.pixelSize: 11; color: Theme.textSoft; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: width < 350 ? 1 : 3
                            columnSpacing: 5
                            rowSpacing: 5
                            Repeater {
                                model: [{id: "power-saver", label: "Saver", glyph: "󰌪"}, {id: "balanced", label: "Balanced", glyph: "󰾅"}, {id: "performance", label: "Performance", glyph: "󰓅"}]
                                C.QuickButton {
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
                        spacing: 12
                        Rectangle {
                            Layout.preferredWidth: 46
                            Layout.preferredHeight: 46
                            radius: 12
                            color: Theme.bgPlaying
                            clip: true
                            C.Label { anchors.centerIn: parent; text: "󰎆"; color: Theme.accentBlue; font.pixelSize: 23 }
                            Image { anchors.fill: parent; visible: status === Image.Ready; source: S.Media.artUrl; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(92, 92); asynchronous: true }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            C.Label { text: S.Media.title; font.weight: Font.Medium; Layout.fillWidth: true }
                            C.Label { text: S.Media.artist; color: Theme.textSoft; font.pixelSize: 11; Layout.fillWidth: true }
                        }
                        C.QuickButton { glyph: S.Media.playing ? "󰏤" : "󰐊"; quiet: true; tooltip: S.Media.playing ? "Pause playback" : "Play"; onClicked: S.Media.toggle() }
                    }
                }

                ColumnLayout {
                    visible: root.section === "wifi"
                    Layout.fillWidth: true
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        C.Label { text: S.Network.wifiEnabled ? "Available networks" : "Wi-Fi is off"; font.weight: Font.Medium; Layout.fillWidth: true }
                        C.QuickButton { id: wifiToggle; text: S.Network.wifiEnabled ? "Turn off" : "Turn on"; selected: S.Network.wifiEnabled; compact: true; enabled: S.Network.wifiAvailable; onClicked: S.Network.toggleWifi() }
                    }
                    C.Label { visible: !S.Network.wifiAvailable || (S.Network.wifiEnabled && S.Network.networks.length === 0); text: !S.Network.wifiAvailable ? "No wireless adapter is available." : "Looking for nearby networks…"; color: Theme.textSoft; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    C.Label { visible: S.Network.captivePortal; text: "This network needs a browser sign-in."; color: Theme.accentWarn; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    C.Label { visible: S.Network.connecting || S.Network.connectionError.length > 0; text: S.Network.connecting ? "Connecting to " + (S.Network.pendingNetwork ? S.Network.pendingNetwork.name : "network") + "…" : S.Network.connectionError; color: S.Network.connectionError ? Theme.accentPink : Theme.textSoft; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Repeater {
                        model: S.Network.wifiEnabled ? S.Network.networks : []
                        C.QuickDeviceRow {
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
                        spacing: 12
                        C.Label { text: root.selectedNetwork ? "Connect to " + root.selectedNetwork.name : ""; font.weight: Font.Medium; Layout.fillWidth: true }
                        TextField {
                            id: password
                            Layout.fillWidth: true
                            implicitHeight: 44
                            padding: 12
                            placeholderText: "Password · leave blank for a saved network"
                            echoMode: TextInput.Password
                            color: Theme.textMain
                            placeholderTextColor: Theme.textSoft
                            font.family: Theme.font
                            font.pixelSize: 12
                            selectByMouse: true
                            Accessible.name: "Wi-Fi password"
                            onAccepted: root.connectSelected()
                            background: Rectangle { radius: 11; color: Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.06); border.width: password.activeFocus ? 2 : 1; border.color: password.activeFocus ? Theme.accentBlue : Theme.borderSoft }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            C.QuickButton { text: "Cancel"; quiet: true; onClicked: { root.selectedNetwork = null; password.clear(); } }
                            Item { Layout.fillWidth: true }
                            C.QuickButton { text: S.Network.connecting ? "Connecting…" : "Connect"; enabled: !S.Network.connecting; selected: true; onClicked: root.connectSelected() }
                        }
                    }
                }

                ColumnLayout {
                    visible: root.section === "bluetooth"
                    Layout.fillWidth: true
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        C.Label { text: S.Bluetooth.enabled ? "Your devices" : "Bluetooth is off"; font.weight: Font.Medium; Layout.fillWidth: true }
                        C.QuickButton { id: bluetoothToggle; text: S.Bluetooth.enabled ? "Turn off" : "Turn on"; selected: S.Bluetooth.enabled; compact: true; enabled: S.Bluetooth.available; onClicked: S.Bluetooth.toggle() }
                    }
                    C.Label { visible: !S.Bluetooth.available || (S.Bluetooth.enabled && S.Bluetooth.devices.length === 0); text: !S.Bluetooth.available ? "No Bluetooth adapter is available." : "Looking for nearby devices…"; color: Theme.textSoft; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Repeater {
                        model: S.Bluetooth.enabled ? S.Bluetooth.sortedDevices : []
                        C.QuickDeviceRow {
                            required property var modelData
                            Layout.fillWidth: true
                            text: modelData.name || modelData.address
                            glyph: "󰂯"
                            subtitle: modelData.connected ? "Connected · select to disconnect" : modelData.paired ? "Paired · select to connect" : "Select to pair"
                            selected: modelData.connected
                            onClicked: { if (modelData.connected) S.Bluetooth.disconnectDevice(modelData); else if (modelData.paired) S.Bluetooth.connectDevice(modelData); else { root.app.close(); S.Bluetooth.pairDevice(modelData); } }
                        }
                    }
                    C.QuickButton { id: pairButton; objectName: "settingsBluetoothManager"; text: "Open Bluetooth manager"; tooltip: "Pair devices and manage Bluetooth"; glyph: "󰂯"; Layout.fillWidth: true; onClicked: root.openBluetoothManager() }
                }

                ColumnLayout {
                    visible: root.section === "audio"
                    Layout.fillWidth: true
                    spacing: 8
                    TapHandler { acceptedButtons: Qt.RightButton; onTapped: root.openAudioManager() }
                    C.QuickButton { id: audioManagerButton; objectName: "settingsAudioManager"; text: "Open sound mixer"; glyph: "󰕾"; Layout.fillWidth: true; onClicked: root.openAudioManager() }
                    C.Label { text: "Output"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    C.Label { text: S.Audio.outputName; color: Theme.textSoft; font.pixelSize: 11; Layout.fillWidth: true }
                    C.QuickSlider { label: "Output volume"; Layout.fillWidth: true; enabled: S.Audio.hasOutput; value: S.Audio.volume; onMoved: S.Audio.setVolume(value) }
                    C.Label { visible: S.Audio.sinks.length === 0; text: "No output devices are available."; color: Theme.textSoft; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Repeater { id: outputDevices; model: S.Audio.sinks; C.QuickDeviceRow { required property var modelData; text: modelData.description || modelData.name; glyph: "󰓃"; Layout.fillWidth: true; selected: modelData === S.Audio.sink; onClicked: S.Audio.selectSink(modelData) } }
                    Item { Layout.preferredHeight: 8 }
                    C.Label { text: "Input"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    RowLayout {
                        Layout.fillWidth: true
                        C.QuickButton { text: S.Audio.sourceMuted ? "Unmute microphone" : "Mute microphone"; glyph: S.Audio.sourceMuted ? "󰍭" : "󰍬"; enabled: S.Audio.hasInput; compact: true; quiet: true; selected: S.Audio.sourceMuted; onClicked: S.Audio.toggleSourceMute() }
                        Item { Layout.fillWidth: true }
                        C.Label { text: Math.round(S.Audio.sourceVolume * 100) + "%"; color: Theme.textSoft; font.pixelSize: 12 }
                    }
                    C.Label { objectName: "settingsInputName"; text: S.Audio.inputName; color: Theme.textSoft; font.pixelSize: 11; Layout.fillWidth: true }
                    C.QuickSlider { objectName: "settingsInputVolume"; label: "Microphone level"; Layout.fillWidth: true; enabled: S.Audio.hasInput; value: S.Audio.sourceVolume; onMoved: S.Audio.setSourceVolume(value) }
                    C.Label { visible: S.Audio.sources.length === 0; text: "No input devices are available."; color: Theme.textSoft; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Repeater { id: inputDevices; model: S.Audio.sources; C.QuickDeviceRow { required property var modelData; text: modelData.description || modelData.name; glyph: "󰍬"; Layout.fillWidth: true; selected: modelData === S.Audio.source; onClicked: S.Audio.selectSource(modelData) } }
                }

                ColumnLayout {
                    visible: root.section === "capture"
                    Layout.fillWidth: true
                    spacing: 8
                    C.Label { text: "Screenshots"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    C.QuickDeviceRow { id: captureRegion; text: "Capture a region"; subtitle: "Select an area of your screen"; glyph: "󰄀"; Layout.fillWidth: true; onClicked: { root.app.close(); S.Desktop.action("capture", ["region"]); } }
                    C.QuickDeviceRow { text: "Capture & annotate"; subtitle: "Draw, highlight and crop in Satty"; glyph: "󰏫"; Layout.fillWidth: true; onClicked: { root.app.close(); S.Desktop.action("capture", ["region", "annotate"]); } }
                    Item { Layout.preferredHeight: 4 }
                    RowLayout {
                        Layout.fillWidth: true
                        C.Label { text: "Screen recording"; font.weight: Font.DemiBold; Layout.fillWidth: true }
                        C.QuickButton { text: "Refresh"; compact: true; quiet: true; enabled: !root.recordingBusy; onClicked: root.refreshRecording() }
                    }
                    C.Label { text: root.recordingBusy ? "Checking recording…" : !root.recordingReady ? "Recording status unavailable" : root.recording ? "Recording in progress" : "Ready to record"; color: root.recording ? Theme.accentWarn : Theme.textSoft; Layout.fillWidth: true }
                    C.QuickDeviceRow { objectName: "settingsRecordStart"; visible: !root.recording; enabled: root.recordingReady && !root.recordingBusy; text: "Record a region"; subtitle: "Select an area to start recording"; glyph: "󰑋"; Layout.fillWidth: true; onClicked: { root.app.close(); S.Desktop.action("record", ["start"]); } }
                    C.QuickDeviceRow { objectName: "settingsRecordStop"; visible: root.recording; enabled: root.recordingReady && !root.recordingBusy; text: "Stop recording"; subtitle: "Save the current recording"; glyph: "󰓛"; Layout.fillWidth: true; onClicked: root.stopRecording() }
                }
            }
        }

        ColumnLayout {
            id: footer
            Layout.fillWidth: true
            spacing: 10
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.borderSoft; opacity: 0.5 }
            RowLayout {
                Layout.fillWidth: true
                spacing: 5
                C.QuickButton { text: "Appearance"; glyph: "󰏘"; quiet: true; compact: true; onClicked: root.app.open("appearance", null) }
                C.QuickButton { glyph: "󰄀"; quiet: true; compact: true; tooltip: "Capture & record"; onClicked: root.section = root.section === "capture" ? "" : "capture" }
                Item { Layout.fillWidth: true }
                C.QuickButton { glyph: "󰌾"; quiet: true; compact: true; tooltip: "Lock session"; onClicked: { root.app.close(); S.Desktop.action("lock", []); } }
                C.QuickButton { glyph: "󰐥"; quiet: true; compact: true; tooltip: "Session & power"; onClicked: root.app.open("power", null) }
            }
        }
    }
}
