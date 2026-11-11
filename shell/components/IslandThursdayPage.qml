pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Layouts
import "../config"
import "../integrations" as Native

// A view of the one Thursday instance owned by the shell. This component never
// constructs a transport, microphone, audio player or second conversation.
FocusScope {
    id: root
    required property var backend
    property bool active: false
    property bool embedded: false
    property bool settingsOpen: false
    property bool draftReady: false
    property bool syncingDraft: false
    readonly property bool sharedDraft: !!backend && typeof backend.composerDraft === "string"
    function restoreDraft(force): void {
        if (!draftReady || !sharedDraft || (!force && active && composer.activeFocus)) return;
        const saved = backend.composerDraft;
        if (composer.text === saved) return;
        syncingDraft = true;
        composer.text = saved;
        composer.cursorPosition = composer.length;
        syncingDraft = false;
    }
    Component.onCompleted: { draftReady = true; restoreDraft(true); }
    onActiveChanged: if (active) restoreDraft(true)
    property bool followConversation: true
    readonly property var messageModel: backend && typeof backend.messages !== "undefined" ? backend.messages : null
    readonly property bool hasHistory: !!messageModel && messageModel.count > 0
    function back(): bool { if (settingsOpen) { settingsOpen = false; return true; } return false; }
    function showSettings() {
        settingsOpen = !settingsOpen;
        if (settingsOpen && backend && typeof backend.loadVoiceSettings === "function") backend.loadVoiceSettings();
    }
    // Natural height is measured at the destination width. The host owns the
    // viewport cap; scrolling history never feeds its allocated height back
    // into this measurement, so shape changes settle instead of oscillating.
    readonly property real minimumContentHeight: 220
    readonly property bool hasConversationPicker: !!backend && typeof backend.knownConversations !== "undefined"
    readonly property bool hasTaskActions: !!backend && !!(backend.taskActive || voiceActive || resumableTask || backend.speaking || backend.playingAudio)
    readonly property real contentHeight: Math.max(minimumContentHeight,
        statusRow.implicitHeight + (hasConversationPicker ? conversationPickerRow.implicitHeight : 0)
        + Math.max(conversation.Layout.minimumHeight, conversationBody.implicitHeight)
        + (hasTaskActions ? taskActions.implicitHeight : 0)
        + composerFrame.Layout.preferredHeight + composerActions.implicitHeight
        + pageLayout.spacing * (3 + (hasConversationPicker ? 1 : 0) + (hasTaskActions ? 1 : 0)))
    readonly property real preferredHeight: contentHeight
    readonly property var activities: backend && backend.task && backend.task.activities ? backend.task.activities.slice(-50) : []
    readonly property real measuredLevel: backend && typeof backend.visualizerLevel === "number" ? backend.visualizerLevel : 0
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
    readonly property bool canCorrectTranscript: active && ready && !working && !voiceActive && !awaitingSubmission && transcript.trim().length > 0
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

    onBackendChanged: { decisionPending = false; resetSubmission(); Qt.callLater(() => root.restoreDraft(true)); }
    onApprovalIdChanged: decisionPending = false
    onConnectedChanged: if (!connected) { decisionPending = false; resetSubmission(); }
    function scrollToLatest(): void {
        const flick = conversation.contentItem;
        if (flick && root.followConversation) flick.contentY = Math.max(0, flick.contentHeight - flick.height);
    }
    Connections {
        target: conversation.contentItem
        function onContentYChanged() {
            const flick = conversation.contentItem;
            root.followConversation = flick.contentY >= Math.max(0, flick.contentHeight - flick.height) - 40;
        }
        function onContentHeightChanged() { if (root.followConversation) Qt.callLater(root.scrollToLatest); }
    }
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
        if (!sharedDraft && String(backend.lastPrompt || "") === submittedText && composer.text === submittedInput) composer.clear();
        resetSubmission();
    }
    function editTranscript(): void {
        if (!canCorrectTranscript) return;
        composer.text = transcript;
        composer.cursorPosition = composer.length;
        composer.forceActiveFocus(Qt.OtherFocusReason);
    }
    function retryRecording(): void {
        if (canCorrectTranscript) backend.toggleMicrophone();
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
        function onComposerDraftChanged() { root.restoreDraft(false); }
        function onComposerDraftAccepted(input) {
            if (root.sharedDraft && composer.text === input && root.backend.composerDraft !== input) root.restoreDraft(true);
        }
        function onConversationIdChanged() { root.followConversation = true; Qt.callLater(root.scrollToLatest); }
        function onSubmittedDraftChanged() { Qt.callLater(root.reconcileSubmission); }
        function onSendPendingChanged() { Qt.callLater(root.reconcileSubmission); }
    }
    Keys.onEscapePressed: event => { if (!root.back()) root.dismissRequested(); event.accepted = true; }

    component Detail: TextEdit {
        color: IslandStyle.text
        font.family: Theme.font
        font.pixelSize: 14
        textFormat: TextEdit.PlainText
        readOnly: true
        selectByMouse: true
        wrapMode: TextEdit.Wrap
        selectionColor: IslandStyle.accent
        selectedTextColor: IslandStyle.accentText
        activeFocusOnTab: false
    }
    component Caption: Label { color: IslandStyle.secondary; font.pixelSize: 12 }
    // Explicit Basic controls isolate this dark surface from platform themes.
    component VoiceCombo: Basic.ComboBox {
        id: control
        implicitHeight: 40
        implicitWidth: 180
        leftPadding: 12
        rightPadding: 34
        opacity: enabled ? 1 : 0.5
        font.family: Theme.font
        font.pixelSize: 14
        background: Rectangle {
            radius: IslandStyle.controlRadius
            color: control.down ? IslandStyle.hover : control.hovered ? IslandStyle.hover : IslandStyle.raised
            border.color: control.visualFocus ? "#ffffff" : IslandStyle.line
            border.width: control.visualFocus ? 2 : 1
        }
        contentItem: Label {
            text: control.displayText
            color: IslandStyle.text
            font: control.font
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: Label {
            x: control.width - width - 12
            anchors.verticalCenter: parent.verticalCenter
            text: "⌄"
            color: IslandStyle.text
            font.pixelSize: 16
        }
        delegate: Basic.ItemDelegate {
            id: option
            required property int index
            width: control.width
            height: 40
            text: control.textAt(index)
            highlighted: control.highlightedIndex === index
            background: Rectangle { radius: 7; color: option.highlighted ? IslandStyle.hover : option.hovered ? IslandStyle.hover : "transparent" }
            contentItem: Label { text: option.text; color: IslandStyle.text; font: control.font; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
        }
        popup: Basic.Popup {
            y: control.height + 5
            width: control.width
            height: Math.min(240, contentItem.implicitHeight + 12)
            padding: 6
            background: Rectangle { color: IslandStyle.raised; radius: Metrics.controlRadius; border.width: 1; border.color: IslandStyle.line }
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: control.popup.visible ? control.delegateModel : null
                currentIndex: control.highlightedIndex
                boundsBehavior: Flickable.StopAtBounds
                ScrollIndicator.vertical: Basic.ScrollIndicator {}
            }
        }
    }
    component VoiceCheck: Basic.CheckBox {
        id: control
        implicitHeight: 40
        leftPadding: 32
        rightPadding: 8
        opacity: enabled ? 1 : 0.5
        background: Rectangle { radius: 8; color: "transparent"; border.width: control.visualFocus ? 2 : 0; border.color: "#ffffff" }
        indicator: Rectangle {
            x: 4; anchors.verticalCenter: parent.verticalCenter
            width: 20; height: 20; radius: 5
            color: control.checked ? IslandStyle.accent : IslandStyle.raised
            border.width: 1; border.color: "#858b97"
            Label { anchors.centerIn: parent; text: "✓"; color: IslandStyle.accentText; font.pixelSize: 14; visible: control.checked }
        }
        contentItem: Label { text: control.text; color: IslandStyle.text; font.family: Theme.font; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter }
    }
    component VoiceSlider: Basic.Slider {
        id: control
        implicitHeight: 40
        background: Rectangle {
            x: control.leftPadding
            y: control.topPadding + control.availableHeight / 2 - height / 2
            width: control.availableWidth; height: 5; radius: 3
            color: IslandStyle.line
            Rectangle { width: control.visualPosition * parent.width; height: parent.height; radius: 3; color: IslandStyle.accent }
        }
        handle: Rectangle {
            x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
            y: control.topPadding + control.availableHeight / 2 - height / 2
            width: 18; height: 18; radius: 9
            color: control.pressed ? "#ffffff" : "#dce0e5"
            border.width: control.visualFocus ? 2 : 0; border.color: "#ffffff"
        }
    }

    ColumnLayout {
        id: pageLayout
        anchors.fill: parent
        spacing: Metrics.space3
        RowLayout {
            id: statusRow
            Layout.fillWidth: true
            spacing: 9
            Icon { visible: !root.embedded; name: "sparkles"; size: 23; color: IslandStyle.text }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                Label { visible: !root.embedded; text: "Thursday"; color: IslandStyle.text; font.pixelSize: 18; font.weight: Font.DemiBold }
                Caption {
                    objectName: "islandThursdayStatus"
                    text: root.backend ? String((root.working && root.backend.activity) || root.backend.statusText || (root.connected ? "Starting up" : "Disconnected")) : "Thursday is unavailable"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    color: root.recording ? "#ffbdb6" : IslandStyle.secondary
                }
            }
            IslandPreviewButton {
                objectName: "islandThursdaySettings"
                text: "Voice"; iconName: "settings"; quiet: true
                enabled: root.connected
                onClicked: root.showSettings()
            }
            IslandPreviewButton {
                objectName: "islandThursdayFullChat"
                text: "History"
                iconName: "arrow-right"
                iconSize: 14
                quiet: true
                enabled: !!root.backend
                tooltip: "Show the conversation in the island"
                onClicked: { root.settingsOpen = false; root.followConversation = true; Qt.callLater(root.scrollToLatest); root.fullChatRequested(); }
            }
        }

        RowLayout {
            id: conversationPickerRow
            Layout.fillWidth: true
            visible: root.hasConversationPicker
            VoiceCombo {
                Layout.fillWidth: true
                model: root.backend && root.backend.knownConversations ? root.backend.knownConversations.map(id => "Conversation " + id) : []
                currentIndex: root.backend && root.backend.knownConversations ? root.backend.knownConversations.indexOf(root.backend.conversationId) : -1
                displayText: currentIndex < 0 ? "New conversation" : currentText
                enabled: root.ready && !root.working && !root.voiceActive
                Accessible.name: "Conversation"
                onActivated: index => root.backend.selectConversation(root.backend.knownConversations[index])
            }
            IslandPreviewButton { text: "New"; enabled: root.ready && !root.working && !root.voiceActive; onClicked: if (typeof root.backend.newConversation === "function") root.backend.newConversation() }
        }
        PanelScrollView {
            id: conversation
            objectName: "islandThursdayConversation"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 44
            ColumnLayout {
                id: conversationBody
                width: conversation.availableWidth
                spacing: Metrics.space3
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: root.settingsOpen
                    spacing: 8
                    Label { text: "Voice settings"; color: IslandStyle.text; font.weight: Font.DemiBold }
                    VoiceCombo {
                        Layout.fillWidth: true
                        model: root.backend && root.backend.voiceInputs ? root.backend.voiceInputs : []
                        textRole: "label"
                        currentIndex: root.backend && root.backend.voiceInputs ? root.backend.voiceInputs.findIndex(item => item.id === root.backend.selectedVoiceInput) : -1
                        Accessible.name: "Microphone input"
                        onActivated: index => root.backend.send({command: "voice_input", device: root.backend.voiceInputs[index].id})
                    }
                    VoiceCombo {
                        Layout.fillWidth: true
                        model: root.backend && root.backend.voiceEngines ? root.backend.voiceEngines : []
                        textRole: "label"
                        currentIndex: root.backend && root.backend.voiceEngines ? root.backend.voiceEngines.findIndex(item => item.id === root.backend.selectedVoiceEngine) : -1
                        Accessible.name: "Voice engine"
                        onActivated: index => { root.backend.selectedVoiceEngine = root.backend.voiceEngines[index].id; if (root.backend.availableVoices.length) root.backend.selectedVoice = root.backend.availableVoices[0].id; }
                    }
                    VoiceCombo {
                        Layout.fillWidth: true
                        model: root.backend && root.backend.availableVoices ? root.backend.availableVoices : []
                        textRole: "label"
                        currentIndex: root.backend && root.backend.availableVoices ? root.backend.availableVoices.findIndex(item => item.id === root.backend.selectedVoice) : -1
                        Accessible.name: "Voice"
                        onActivated: index => root.backend.selectedVoice = root.backend.availableVoices[index].id
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Caption { text: "Speed" }
                        VoiceSlider { Layout.fillWidth: true; from: 0.8; to: root.backend && root.backend.selectedVoiceEngine === "online" ? 1.5 : 1.2; stepSize: 0.05; value: root.backend && root.backend.selectedVoiceSpeed ? root.backend.selectedVoiceSpeed : 1; Accessible.name: "Voice speed"; onMoved: root.backend.selectedVoiceSpeed = value }
                        IslandPreviewButton { text: "Preview"; enabled: root.ready && !!root.backend.voiceSelectionValid && !root.working && !root.voiceActive; onClicked: if (typeof root.backend.previewVoice === "function") root.backend.previewVoice() }
                        IslandPreviewButton { text: root.backend && root.backend.voiceSettingsPending ? "Saving…" : "Save"; enabled: root.ready && !!root.backend.voiceSelectionValid && !root.backend.voiceSettingsPending; onClicked: if (typeof root.backend.saveVoiceSettings === "function") root.backend.saveVoiceSettings() }
                    }
                    Flow {
                        Layout.fillWidth: true
                        VoiceCheck { text: "Speak typed replies"; checked: !!root.backend && root.backend.speakTyped === true; onClicked: root.backend.send({command: "settings", values: {speak_typed: checked}}) }
                        VoiceCheck { text: "Mute speech"; checked: !!root.backend && root.backend.muted === true; onClicked: root.backend.send({command: "settings", values: {muted: checked}}) }
                    }
                    Caption { Layout.fillWidth: true; wrapMode: Text.Wrap; text: root.backend && root.backend.voiceSettingsNotice ? root.backend.voiceSettingsNotice : "" }
                }
                Native.SpeechOrb {
                    id: voiceOrb
                    objectName: "islandThursdayOrb"
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 64; Layout.preferredHeight: 64
                    visible: root.recording || root.working || !!root.backend && root.backend.speaking === true
                    active: root.active && root.connected && visible && (root.recording || root.working || !!root.backend && (root.backend.speaking === true || root.backend.speechPreparing === true))
                    effectsActive: root.active && visible && conversation.contentItem.contentY < voiceOrb.y + voiceOrb.height && conversation.contentItem.contentY + conversation.height > voiceOrb.y
                    level: root.measuredLevel
                    processing: root.working && !root.recording && !(root.backend && root.backend.speaking)
                    reducedMotion: Theme.effectiveReducedMotion
                }
                ColumnLayout {
                    objectName: "islandThursdayActivityTimeline"
                    Layout.fillWidth: true
                    visible: root.activities.length > 0
                    spacing: Metrics.space2
                    Caption { text: "Activity"; font.weight: Font.DemiBold }
                    Repeater {
                        model: root.activities
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 2
                            Label {
                                Layout.fillWidth: true
                                text: String(modelData.label || modelData.tool || "Action")
                                color: modelData.status === "failed" ? "#ffbdb6" : IslandStyle.text
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                            }
                            Caption {
                                Layout.fillWidth: true
                                text: String(modelData.tool || "") + " · " + String(modelData.status || "")
                                    + (typeof modelData.duration_ms === "number" ? " · " + (modelData.duration_ms / 1000).toFixed(1) + "s" : "")
                                font.pixelSize: 10
                                wrapMode: Text.Wrap
                            }
                            Caption {
                                visible: text.length > 0
                                Layout.fillWidth: true
                                text: String(modelData.summary || "")
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }
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
                        anchors.margins: Metrics.space3
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
                Repeater {
                    model: root.messageModel
                    delegate: ColumnLayout {
                        required property string speaker
                        required property string body
                        Layout.fillWidth: true
                        spacing: 5
                        Caption { text: parent.speaker === "user" ? "You" : "Thursday"; font.weight: Font.DemiBold }
                        Detail { Layout.fillWidth: true; text: parent.body; Accessible.name: parent.speaker === "user" ? "Your message" : "Thursday response" }
                        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: IslandStyle.line; Layout.topMargin: 8; Layout.bottomMargin: 6 }
                    }
                }
                Caption { visible: root.backend && typeof root.backend.historyLoading !== "undefined" && root.backend.historyLoading; text: "Loading conversation…" }
                ColumnLayout {
                    visible: !root.hasHistory && root.prompt.length > 0
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
                    Flow {
                        Layout.fillWidth: true
                        visible: !root.working && !root.voiceActive
                        spacing: Metrics.space2
                        IslandPreviewButton {
                            objectName: "islandThursdayEditTranscript"
                            text: "Edit transcript"
                            enabled: root.canCorrectTranscript
                            onClicked: root.editTranscript()
                        }
                        IslandPreviewButton {
                            objectName: "islandThursdayRetryRecording"
                            text: "Try again"
                            enabled: root.canCorrectTranscript
                            onClicked: root.retryRecording()
                        }
                    }
                }
                ColumnLayout {
                    visible: !root.hasHistory && root.answer.length > 0
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
            id: taskActions
            Layout.fillWidth: true
            visible: root.hasTaskActions
            spacing: Metrics.space2
            IslandPreviewButton { objectName: "islandThursdayStop"; visible: !!root.backend && (root.backend.taskActive || root.voiceActive); text: root.voiceActive ? "Cancel voice" : "Stop task"; iconName: "stop"; iconSize: 14; enabled: root.connected; onClicked: if (root.backend) root.backend.stopTask() }
            IslandPreviewButton { objectName: "islandThursdayResume"; visible: !!root.resumableTask; text: "Resume"; enabled: root.canResume; onClicked: root.resumeTask() }
            IslandPreviewButton { objectName: "islandThursdayStopAudio"; visible: !!root.backend && (root.backend.speaking || !!root.backend.playingAudio); text: "Stop speech"; iconName: "volume-x"; iconSize: 14; enabled: root.connected; onClicked: if (root.backend) root.backend.stopAudio() }
        }
        Rectangle {
            id: composerFrame
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(94, Math.max(58, composer.contentHeight + 20))
            radius: IslandStyle.moduleRadius
            color: IslandStyle.raised
            border.width: composer.activeFocus ? 2 : 0
            border.color: composer.activeFocus ? IslandStyle.text : IslandStyle.line
            ScrollView {
                anchors.fill: parent
                anchors.margins: 5
                clip: true
                TextArea {
                    id: composer
                    objectName: "islandThursdayComposer"
                    onTextChanged: {
                        if (root.draftReady && root.sharedDraft && !root.syncingDraft && (root.active || activeFocus))
                            root.backend.composerDraft = text;
                    }
                    placeholderText: root.recording ? "Listening…" : "Ask Thursday…"
                    placeholderTextColor: IslandStyle.secondary
                    color: IslandStyle.text
                    selectionColor: IslandStyle.accent
                    selectedTextColor: IslandStyle.accentText
                    font.family: Theme.font
                    font.pixelSize: 14
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
                    Keys.onEscapePressed: event => { if (!root.back()) root.dismissRequested(); event.accepted = true; }
                }
            }
        }
        RowLayout {
            id: composerActions
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
