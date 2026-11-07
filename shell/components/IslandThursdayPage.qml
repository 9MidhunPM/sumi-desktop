pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../config"

// A view of the one Thursday instance owned by the shell. This component never
// constructs a transport, microphone, audio player or second conversation.
FocusScope {
    id: root
    required property var backend
    property bool active: false
    readonly property real preferredHeight: 440
    readonly property bool connected: !!backend && backend.connected === true
    readonly property bool ready: connected && backend.ready === true
    readonly property bool working: !!backend && (backend.busy === true || backend.taskActive === true || backend.sendPending === true)
    readonly property bool voiceActive: !!backend && backend.voiceActive === true
    readonly property bool recording: !!backend && backend.recording === true
    readonly property bool canSend: active && ready && !working && !voiceActive && !awaitingSubmission && composer.text.trim().length > 0
    readonly property var approvals: backend && backend.confirmations ? backend.confirmations : []
    readonly property var approval: approvals.length ? approvals[0] : null
    readonly property string approvalId: approval ? String(approval.id || "") : ""
    readonly property var resumableTask: backend && backend.resumable && backend.task ? backend.task : null
    readonly property string taskId: resumableTask ? String(resumableTask.id || "") : ""
    readonly property bool canResume: active && ready && !working && /^[\w-]+$/.test(taskId)
    readonly property string prompt: backend ? String(backend.lastPrompt || "") : ""
    readonly property string answer: backend ? String(backend.latestAnswer || "") : ""
    readonly property string transcript: backend ? String(backend.transcript || "") : ""
    readonly property string errors: {
        if (!backend) return "";
        const values = [backend.errorText || "", backend.voiceError || "", backend.speechError || "", backend.outputNotice || ""];
        return values.filter((value, index) => value.length > 0 && values.indexOf(value) === index).join("\n");
    }
    property bool decisionPending: false
    property bool awaitingSubmission: false
    property string submittedText: ""
    property string submittedInput: ""
    property var submissionBackend: null
    signal fullChatRequested()
    signal dismissRequested()
    implicitWidth: 640
    implicitHeight: preferredHeight
    enabled: active

    onBackendChanged: { decisionPending = false; resetSubmission(); }
    onApprovalIdChanged: decisionPending = false
    onConnectedChanged: if (!connected) { decisionPending = false; resetSubmission(); }
    function focusDefault(): void {
        if (active) composer.forceActiveFocus(Qt.OtherFocusReason);
    }
    function submitPrompt(): void {
        if (!canSend) return;
        submittedText = composer.text.trim();
        submittedInput = composer.text;
        submissionBackend = backend;
        awaitingSubmission = true;
        backend.submit(submittedText);
    }
    function resetSubmission(): void {
        awaitingSubmission = false;
        submittedText = "";
        submittedInput = "";
        submissionBackend = null;
    }
    function reconcileSubmission(): void {
        if (!awaitingSubmission) return;
        if (!backend || backend !== submissionBackend || !connected || backend.errorText) { resetSubmission(); return; }
        // user_message may clear sendPending before the HTTP acknowledgement.
        // The native client clears submittedDraft on acknowledgement (or error).
        if (backend.sendPending || backend.submittedDraft) return;
        if (String(backend.lastPrompt || "") === submittedText && composer.text === submittedInput) composer.clear();
        resetSubmission();
    }
    function toggleMicrophone(): void {
        if (!ready || (!recording && (working || voiceActive))) return;
        backend.toggleMicrophone();
    }
    function decide(approved): void {
        if (!active || !connected || !approvalId || decisionPending) return;
        decisionPending = true;
        backend.decide(approved);
    }
    function resumeTask(): void {
        if (canResume) backend.send({command: "task_resume", task_id: taskId});
    }
    Connections {
        target: root.backend
        ignoreUnknownSignals: true
        function onErrorTextChanged() {
            if (root.backend && root.backend.errorText) root.decisionPending = false;
            Qt.callLater(root.reconcileSubmission);
        }
        function onSubmittedDraftChanged() { Qt.callLater(root.reconcileSubmission); }
        function onSendPendingChanged() { Qt.callLater(root.reconcileSubmission); }
    }
    Keys.onEscapePressed: event => { root.dismissRequested(); event.accepted = true; }

    component Detail: TextEdit {
        color: "#f3f3f7"
        font.family: Theme.font
        font.pixelSize: 13
        textFormat: TextEdit.PlainText
        readOnly: true
        selectByMouse: true
        wrapMode: TextEdit.Wrap
        selectionColor: "#d7d8e0"
        selectedTextColor: "#17181d"
        activeFocusOnTab: false
    }
    component Caption: Label { color: "#bfc0cb"; font.pixelSize: 12 }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            spacing: 9
            Icon { name: "sparkles"; size: 23; color: "#f5f5f8" }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                Label { text: "Thursday"; color: "#f7f7fa"; font.pixelSize: 18; font.weight: Font.DemiBold }
                Caption {
                    objectName: "islandThursdayStatus"
                    text: root.backend ? String(root.backend.statusText || (root.connected ? "Starting up" : "Disconnected")) : "Thursday is unavailable"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    color: root.recording ? "#ffbdb6" : "#bfc0cb"
                }
            }
            IslandPreviewButton {
                objectName: "islandThursdayFullChat"
                text: root.width < 380 ? "Full chat" : "Open full chat"
                iconName: "arrow-right"
                iconSize: 14
                quiet: true
                enabled: !!root.backend
                tooltip: "Open the full Thursday conversation"
                onClicked: root.fullChatRequested()
            }
        }

        PanelScrollView {
            id: conversation
            objectName: "islandThursdayConversation"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 44
            ColumnLayout {
                width: conversation.availableWidth
                spacing: 12
                Caption {
                    objectName: "islandThursdayConnection"
                    visible: !root.ready
                    text: !root.backend ? "Thursday is not available in this session."
                        : !root.connected ? "Thursday is disconnected. Your draft stays here while it reconnects."
                        : "Thursday is starting up. Your draft stays here until it is ready."
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    elide: Text.ElideNone
                }
                Rectangle {
                    visible: !!root.approval
                    Layout.fillWidth: true
                    implicitHeight: approvalContent.implicitHeight + 24
                    radius: 14
                    color: "#2b2927"
                    ColumnLayout {
                        id: approvalContent
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 9
                        Label { text: root.approvals.length > 1 ? "Review action · 1 of " + root.approvals.length : "Review this action"; color: "#ffdbab"; font.weight: Font.DemiBold }
                        Detail {
                            objectName: "islandThursdayApproval"
                            Layout.fillWidth: true
                            text: root.approval ? String(root.approval.prompt || "") : ""
                            Accessible.name: "Thursday action awaiting your approval"
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Caption { visible: root.decisionPending; text: "Sending decision…"; Layout.fillWidth: true }
                            Item { visible: !root.decisionPending; Layout.fillWidth: true }
                            IslandPreviewButton { objectName: "islandThursdayReject"; text: "Reject"; enabled: root.connected && !root.decisionPending; onClicked: root.decide(false) }
                            IslandPreviewButton { objectName: "islandThursdayApprove"; text: "Approve"; selected: true; enabled: root.connected && !root.decisionPending; onClicked: root.decide(true) }
                        }
                    }
                }
                Caption { objectName: "islandThursdayError"; visible: root.errors.length > 0; text: root.errors; color: "#ffdbab"; Layout.fillWidth: true; wrapMode: Text.Wrap; elide: Text.ElideNone }
                ColumnLayout {
                    visible: root.prompt.length > 0
                    Layout.fillWidth: true
                    spacing: 4
                    Caption { text: "Last typed message"; font.weight: Font.DemiBold }
                    Detail { objectName: "islandThursdayPrompt"; Layout.fillWidth: true; text: root.prompt; Accessible.name: "Your message" }
                }
                ColumnLayout {
                    visible: root.transcript.length > 0
                    Layout.fillWidth: true
                    spacing: 4
                    Caption { text: "Latest voice transcript"; font.weight: Font.DemiBold }
                    Detail { objectName: "islandThursdayTranscript"; Layout.fillWidth: true; text: root.transcript; Accessible.name: "Voice transcript" }
                }
                ColumnLayout {
                    visible: root.answer.length > 0
                    Layout.fillWidth: true
                    spacing: 4
                    Caption { text: "Thursday"; font.weight: Font.DemiBold }
                    Detail { objectName: "islandThursdayAnswer"; Layout.fillWidth: true; text: root.answer; Accessible.name: "Thursday's response" }
                }
                Caption {
                    visible: root.ready && !root.prompt.length && !root.answer.length && !root.transcript.length && !root.approval && !root.errors.length
                    text: "What would you like to do?"
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                }
            }
        }

        Flow {
            Layout.fillWidth: true
            visible: !!root.backend && (root.backend.taskActive || root.voiceActive || root.resumableTask || root.backend.speaking || root.backend.playingAudio)
            spacing: 6
            IslandPreviewButton { objectName: "islandThursdayStop"; visible: !!root.backend && (root.backend.taskActive || root.voiceActive); text: root.voiceActive ? "Cancel voice" : "Stop task"; iconName: "stop"; iconSize: 14; enabled: root.connected; onClicked: if (root.backend) root.backend.stopTask() }
            IslandPreviewButton { objectName: "islandThursdayResume"; visible: !!root.resumableTask; text: "Resume"; enabled: root.canResume; onClicked: root.resumeTask() }
            IslandPreviewButton { objectName: "islandThursdayStopAudio"; visible: !!root.backend && (root.backend.speaking || !!root.backend.playingAudio); text: "Stop speech"; iconName: "volume-x"; iconSize: 14; enabled: root.connected; onClicked: if (root.backend) root.backend.stopAudio() }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(94, Math.max(58, composer.contentHeight + 20))
            radius: 15
            color: "#292a31"
            border.width: composer.activeFocus ? 2 : 1
            border.color: composer.activeFocus ? "#f3f3f7" : "#53545e"
            ScrollView {
                anchors.fill: parent
                anchors.margins: 5
                clip: true
                TextArea {
                    id: composer
                    objectName: "islandThursdayComposer"
                    placeholderText: root.recording ? "Listening…" : "Ask Thursday…"
                    placeholderTextColor: "#bfc0cb"
                    color: "#f5f5f8"
                    selectionColor: "#d7d8e0"
                    selectedTextColor: "#17181d"
                    font.family: Theme.font
                    font.pixelSize: 13
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    background: null
                    Accessible.name: "Message Thursday"
                    Keys.onReturnPressed: event => {
                        if (!(event.modifiers & Qt.ShiftModifier)) { root.submitPrompt(); event.accepted = true; }
                        else event.accepted = false;
                    }
                    Keys.onEnterPressed: event => {
                        if (!(event.modifiers & Qt.ShiftModifier)) { root.submitPrompt(); event.accepted = true; }
                        else event.accepted = false;
                    }
                    Keys.onEscapePressed: event => { root.dismissRequested(); event.accepted = true; }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            IslandPreviewButton {
                objectName: "islandThursdayMicrophone"
                text: root.recording ? (root.width < 380 ? "Finish" : "Finish speaking") : (root.width < 380 ? "Mic" : "Microphone")
                iconName: root.recording ? "stop" : "microphone"
                iconSize: 16
                selected: root.recording
                enabled: root.ready && (root.recording || (!root.working && !root.voiceActive))
                tooltip: root.recording ? "Finish this voice recording" : "Start a voice recording"
                onClicked: root.toggleMicrophone()
            }
            Caption { visible: root.width > 440; text: "Shift + Enter for a new line"; Layout.fillWidth: true; font.pixelSize: 10 }
            Item { visible: root.width <= 440; Layout.fillWidth: true }
            IslandPreviewButton { objectName: "islandThursdaySend"; text: root.backend && root.backend.sendPending ? "Sending…" : "Send"; selected: true; enabled: root.canSend; onClicked: root.submitPrompt() }
        }
    }
}
