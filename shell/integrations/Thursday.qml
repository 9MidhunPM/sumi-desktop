pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import "SpeechLevels.js" as SpeechLevels

// Sumi's optional JSON-lines adapter. The separately installed Thursday client
// owns authentication, local settings and private audio downloads. No HUD is
// created here: the island is the only conversation surface in this shell.
Scope {
    id: root
    property string repoRoot: Quickshell.env("SUMI_THURSDAY_ROOT") || ""
    property string pythonExecutable: Quickshell.env("SUMI_THURSDAY_PYTHON") || (repoRoot ? repoRoot + "/.venv/bin/python" : "")
    readonly property bool configured: repoRoot.startsWith("/") && pythonExecutable.startsWith("/")
    property var theme: null
    property bool reducedMotion: false
    property url cursorVisualSource: ""
    property bool opened: false
    property bool hudDismissed: true
    property var currentScreen: Quickshell.screens[0] || null
    property bool connected: false
    property bool ready: false
    property bool busy: false
    property bool sendPending: false
    property string submittedDraft: ""
    // Session-owned text survives monitor changes and cached page replacement.
    property string composerDraft: ""
    property string submittedComposerDraft: ""
    property string submittedComposerPrompt: ""
    signal composerDraftAccepted(string input)
    property string lastPrompt: ""
    property string latestAnswer: ""
    property string errorText: ""
    property string voiceError: ""
    property string speechError: ""
    property string outputNotice: ""
    property string transcript: ""
    property string partialTranscript: ""
    property string finalTranscript: ""
    property string voiceTaskId: ""
    property string voiceConversationId: ""
    property var retiredVoiceSessions: []
    property string voiceState: "idle"
    property string voiceSession: ""
    property var task: null
    property var confirmations: []
    property int conversationId: -1
    property var knownConversations: []
    property alias messages: historyModel
    property int pendingRow: -1
    property int historyRequest: 0
    property bool historyLoading: false
    property bool historyNeedsReload: false
    property real microphoneLevel: 0
    property real pcmLevel: 0
    property bool nativePlayback: false
    property real nativePosition: 0
    property string nativePlaybackGeneration: ""
    property string nativePlaybackState: "idle"
    property var nativePlaybackMetrics: ({})
    property string activity: ""
    property var cursorState: ({active: false})
    property var voiceInputs: []
    property var selectedVoiceInput: null
    property var voiceOptions: null
    property string selectedVoiceEngine: ""
    property string selectedVoice: ""
    property real selectedVoiceSpeed: 1
    property string voiceSettingsNotice: ""
    property bool voiceSettingsPending: false
    readonly property bool voiceSelectionValid: !!selectedVoiceProvider && selectedVoiceProvider.available === true && availableVoices.some(item => item.id === selectedVoice) && selectedVoiceSpeed >= 0.8 && selectedVoiceSpeed <= (selectedVoiceEngine === "online" ? 1.5 : 1.2)
    readonly property var voiceEngines: voiceOptions && voiceOptions.engines ? voiceOptions.engines : []
    readonly property var selectedVoiceProvider: voiceEngines.find(item => item.id === selectedVoiceEngine) || null
    readonly property var availableVoices: selectedVoiceProvider ? selectedVoiceProvider.voices || [] : []
    readonly property real visualizerLevel: recording ? microphoneLevel : speaking ? nativePlayback ? pcmLevel : SpeechLevels.reading(audioEnvelope, playbackPosition, true, 20).level : 0
    ListModel { id: historyModel }
    LazyLoader { id: cursorHalo; active: Quickshell.env("SUMI_PREVIEW") !== "1" && root.cursorVisualSource.toString().length > 0; source: root.cursorVisualSource }
    Binding { target: cursorHalo.item; property: "cursor"; value: root.connected ? root.cursorState : ({active: false}); when: !!cursorHalo.item }
    Binding { target: cursorHalo.item; property: "reducedMotion"; value: root.reducedMotion; when: !!cursorHalo.item }
    function appendMessage(role, content) {
        if (content && ["user", "assistant"].indexOf(role) >= 0) historyModel.append({speaker: role, body: String(content)});
    }
    function rememberConversation(id) {
        if (id > 0 && knownConversations.indexOf(id) < 0) knownConversations = knownConversations.concat([id]);
    }
    function switchConversation(id) {
        if (!id || id === conversationId) return;
        conversationId = id; rememberConversation(id);
        historyRequest++; historyNeedsReload = true; historyLoading = false;
        historyModel.clear(); pendingRow = -1; latestAnswer = "";
    }
    function refreshHistory() {
        if (!historyNeedsReload || busy || taskActive || conversationId <= 0) return;
        historyLoading = true; historyNeedsReload = false; historyRequest++;
        if (!send({command: "conversation", conversation_id: conversationId, request_id: historyRequest})) historyLoading = false;
    }
    function selectConversation(id) {
        if (busy || taskActive || voiceActive || sendPending) return;
        stopAudio(); switchConversation(Number(id)); refreshHistory();
    }
    function newConversation() {
        if (busy || taskActive || voiceActive || sendPending) return;
        stopAudio(); historyRequest++; conversationId = -1; historyLoading = false; historyNeedsReload = false;
        historyModel.clear(); pendingRow = -1; latestAnswer = ""; lastPrompt = "";
    }
    function setVoiceOptions(data) {
        if (!data || !Array.isArray(data.engines)) return;
        voiceOptions = data; selectedVoiceEngine = data.engine || "online";
        selectedVoice = data.voice || ""; selectedVoiceSpeed = Number(data.speed) || 1;
    }
    function loadVoiceSettings() { send({command: "voice_options"}); send({command: "voice_inputs"}); }
    function voiceSelection() { return {engine: selectedVoiceEngine, voice: selectedVoice, speed: selectedVoiceSpeed}; }
    function saveVoiceSettings() {
        if (!connected || voiceSettingsPending || !voiceSelectionValid) return;
        voiceSettingsPending = send({command: "voice_settings", values: voiceSelection()});
    }
    function previewVoice() {
        if (!connected || busy || voiceActive || !voiceSelectionValid) return;
        stopAudio(); send({command: "voice_preview", values: voiceSelection()});
    }
    property bool muted: false
    property bool speakTyped: false
    property bool speechPreparing: false
    property var playingAudio: null
    property var audioQueue: []
    property string generation: ""
    property var retiredGenerations: []
    property bool nativeAudible: false
    property bool requested: false
    property bool reportedPlayback: false
    readonly property bool recording: voiceState === "listening"
    readonly property bool voiceActive: voiceState === "listening" || voiceState === "transcribing"
    readonly property bool taskActive: !!task && (task.status === "running" || task.status === "awaiting_approval")
    readonly property bool resumable: !!task && ["paused", "cancelled", "interrupted", "failed"].indexOf(task.status) >= 0
    readonly property int playbackPosition: nativePlayback ? nativePosition : audio.item ? audio.item.position : 0
    readonly property var audioEnvelope: playingAudio ? playingAudio.audio_levels || null : null
    readonly property bool playbackRunning: !muted && (nativePlayback || (!!playingAudio && !!audio.item && audio.item.playing))
    readonly property bool speaking: playbackRunning && nativeAudible
    onSpeakingChanged: if (speaking && playingAudio && !reportedPlayback) {
        reportedPlayback = true; feedback("playing", playingAudio.generation_id);
    }
    readonly property string statusText: !configured ? "Thursday is not configured" : !requested ? "Thursday is disconnected"
        : !connected ? "Connecting to Thursday" : !ready ? "Thursday is starting up" : confirmations.length ? "Your approval is needed"
        : recording ? "Listening" : voiceState === "transcribing" ? "Understanding" : speaking ? "Speaking"
        : speechPreparing ? "Preparing speech" : busy || taskActive || sendPending ? "Working on it" : "Ready when you are"

    function connectHelper() {
        if (!configured) {
            errorText = "Set SUMI_THURSDAY_ROOT to your Thursday checkout, then restart Sumi. Thursday is optional.";
            return false;
        }
        if (transport.running) return true;
        errorText = "";
        requested = true;
        transport.running = true;
        startup.restart();
        return true;
    }
    function disconnect() {
        requested = false;
        submittedComposerDraft = ""; submittedComposerPrompt = "";
        startup.stop();
        stopAudio();
        transport.running = false;
        connected = false; ready = false; busy = false; sendPending = false;
        submittedDraft = ""; voiceState = "idle"; confirmations = [];
    }
    function send(command) {
        const allowed = ["message", "voice_start", "voice_stop", "voice_cancel", "task_cancel", "task_resume", "confirm",
            "playback", "audio_release", "audio_stop", "open_web", "settings", "health", "conversation", "voice_inputs", "voice_input", "voice_options", "voice_settings", "voice_preview"];
        if (!command || allowed.indexOf(command.command) < 0) return false;
        if (!transport.running) {
            errorText = configured ? "Thursday is disconnected. Open Thursday again to retry." : "Thursday is not configured. Set SUMI_THURSDAY_ROOT to enable it.";
            return false;
        }
        transport.write(JSON.stringify(command) + "\n");
        if (command.command === "message") {
            // A locally submitted typed request starts a distinct presentation.
            // Server user_message events also represent voice, so do not clear there.
            if (voiceSession) retiredVoiceSessions = retiredVoiceSessions.concat([voiceSession]).slice(-64);
            voiceSession = ""; voiceState = "idle";
            partialTranscript = ""; finalTranscript = ""; transcript = "";
            voiceTaskId = ""; voiceConversationId = ""; microphoneLevel = 0;
        }
        return true;
    }
    function submit(text) {
        const prompt = String(text || "").trim();
        if (!prompt || !connected || !ready || busy || taskActive || sendPending) return;
        stopAudio();
        submittedComposerDraft = composerDraft.trim() === prompt ? composerDraft : "";
        submittedComposerPrompt = prompt;
        lastPrompt = prompt; submittedDraft = prompt; latestAnswer = "";
        errorText = ""; voiceError = ""; sendPending = true;
        if (!send({command: "message", prompt: prompt, conversation_id: conversationId > 0 ? conversationId : null})) {
            sendPending = false; submittedDraft = "";
        }
    }
    function toggleMicrophone() {
        if (!connected || !ready) return;
        if (recording) send({command: "voice_stop", session_id: voiceSession});
        else if (!busy && !taskActive && !voiceActive) { stopAudio(); send({command: "voice_start"}); }
    }
    function decide(approved) {
        if (connected && confirmations.length)
            send({command: "confirm", id: confirmations[0].id, approved: approved === true});
    }
    function stopTask() {
        stopAudio();
        if (voiceActive) send({command: "voice_cancel", session_id: voiceSession});
        if (taskActive) send({command: "task_cancel", task_id: task.id});
    }
    function openChat() { showIsland(); }
    function showIsland() { connectHelper(); opened = true; }
    function release(item) { if (item && item.audio_id) send({command: "audio_release", audio_id: item.audio_id}); }
    function feedback(state, id) { if (id) send({command: "playback", state: state, generation_id: id}); }
    function stopAudio() {
        if (generation) retiredGenerations = retiredGenerations.concat([generation]).slice(-64);
        if (generation) send({command: "audio_stop", generation_id: generation});
        nativePlayback = false; pcmLevel = 0;
        const old = playingAudio;
        playingAudio = null;
        release(old);
        for (const item of audioQueue) release(item);
        audioQueue = []; speechPreparing = false; outputNotice = "";
        feedback("idle", generation);
    }
    function nextAudio() {
        if (playingAudio || muted || !audioQueue.length) return;
        const queue = audioQueue.slice();
        playingAudio = queue.shift(); audioQueue = queue;
        reportedPlayback = false;

    }
    function finishAudio(failed) {
        const item = playingAudio;
        if (!item) return;
        playingAudio = null;
        release(item);
        if (failed) {
            feedback("failed", item.generation_id);
            speechError = "Speech playback is unavailable. The response remains readable.";
        }
        if (audioQueue.length) nextAudio();
        else feedback("idle", item.generation_id);
    }
    function setVoice(data) {
        const nextSession = String(data.session_id || data.id || "");
        if (nextSession && retiredVoiceSessions.indexOf(nextSession) >= 0) return;
        if (nextSession && nextSession !== voiceSession) {
            if (voiceSession) retiredVoiceSessions = retiredVoiceSessions.concat([voiceSession]).slice(-64);
            partialTranscript = ""; finalTranscript = ""; transcript = "";
            voiceTaskId = ""; voiceConversationId = "";
        }
        voiceState = String(data.state || "idle");
        if (nextSession) voiceSession = nextSession;
        if (data.partial_transcript !== undefined) partialTranscript = String(data.partial_transcript || "");
        if (data.transcript !== undefined) finalTranscript = String(data.transcript || "");
        if (data.task_id) voiceTaskId = String(data.task_id);
        if (data.conversation_id) voiceConversationId = String(data.conversation_id);
        transcript = finalTranscript || partialTranscript;
        microphoneLevel = Math.max(0, Math.min(1, Number(data.level) || 0)); voiceError = String(data.error || "");
        if (recording) { stopAudio(); latestAnswer = ""; errorText = ""; }
    }
    function handle(event) {
        if (!event || typeof event.type !== "string") return;
        const data = event.data || {};
        switch (event.type) {
        case "native_connection":
            connected = data.connected === true;
            if (connected) { startup.stop(); errorText = ""; }
            else {
                if (voiceActive) { voiceState = "idle"; microphoneLevel = 0; voiceError = "Thursday disconnected while listening. Please try again."; }
                ready = false; cursorState = ({active: false}); stopAudio();
            }
            break;
        case "native_health": ready = data.model_ready === true; if (data.status === "offline") connected = false; break;
        case "native_settings":
            muted = data.muted === true; speakTyped = data.speak_typed === true;
            if (muted) stopAudio();
            break;
        case "voice_inputs": voiceInputs = [{id: null, label: "System default"}].concat(Array.isArray(data.devices) ? data.devices : []); selectedVoiceInput = data.selected; break;
        case "voice_options": setVoiceOptions(data); break;
        case "native_conversation":
            if (data.conversation_id !== conversationId || data.request_id !== historyRequest || busy || taskActive) break;
            historyLoading = false; historyModel.clear(); pendingRow = -1;
            for (const item of data.messages || []) appendMessage(item.role, item.content);
            break;
        case "init":
            historyRequest++; historyLoading = false; historyNeedsReload = false;
            historyModel.clear(); pendingRow = -1;
            for (const item of data.history || []) appendMessage(item.role, item.content);
            rememberConversation(Number(data.conversation_id));
            conversationId = Number(data.conversation_id) || -1; ready = data.model_ready === true;
            busy = data.busy === true; task = data.task || null;
            confirmations = Array.isArray(data.pending_confirms) ? data.pending_confirms : [];
            if (data.voice_state) setVoice(data.voice_state);
            if (data.voice_options) setVoiceOptions(data.voice_options);
            break;
        case "user_message":
            // The ordered server echo confirms acceptance. HTTP/status events
            // alone must never erase a draft, including a newer edited draft.
            if (submittedComposerPrompt && String(data.content || "").trim() === submittedComposerPrompt) {
                const acceptedInput = submittedComposerDraft;
                if (acceptedInput && composerDraft === acceptedInput) composerDraft = "";
                if (acceptedInput) composerDraftAccepted(acceptedInput);
                submittedComposerDraft = ""; submittedComposerPrompt = "";
            }
            switchConversation(data.conversation_id);
            historyRequest++; if (historyLoading) { historyLoading = false; historyNeedsReload = true; }
            appendMessage("user", data.content); pendingRow = -1;
            latestAnswer = ""; busy = true; sendPending = false;
            break;
        case "token":
            latestAnswer += String(data.chunk || "");
            if (pendingRow < 0) { appendMessage("assistant", latestAnswer); pendingRow = historyModel.count - 1; }
            else historyModel.setProperty(pendingRow, "body", latestAnswer);
            break;
        case "final_response":
            latestAnswer = String(data.content || latestAnswer);
            if (pendingRow >= 0) historyModel.setProperty(pendingRow, "body", latestAnswer);
            else appendMessage("assistant", latestAnswer);
            pendingRow = -1; busy = false; sendPending = false; activity = ""; refreshHistory(); break;
        case "status": busy = data.busy === true; if (!busy) sendPending = false; refreshHistory(); break;
        case "task_updated": switchConversation(data.conversation_id); task = data; activity = data.activity ? data.activity.label || "" : ""; refreshHistory(); break;
        case "confirm_required": confirmations = confirmations.filter(item => item.id !== data.id).concat([data]); break;
        case "confirm_resolved": confirmations = confirmations.filter(item => item.id !== data.id); break;
        case "voice_state": setVoice(data); break;
        case "native_cursor": cursorState = data; break;
        case "native_playback":
            if (!data.generation_id || ["playing", "idle", "failed"].indexOf(data.state) < 0 || retiredGenerations.indexOf(data.generation_id) >= 0) break;
            if (data.state === "playing") {
                if (generation !== data.generation_id) { stopAudio(); generation = data.generation_id; }
                nativePlayback = true; speechPreparing = false;
                pcmLevel = Math.max(0, Math.min(1, Number(data.level) || 0)); nativePosition = Math.max(0, Number(data.position_ms) || 0);
            } else if (generation === data.generation_id) {
                nativePlayback = false; pcmLevel = 0;
                if (data.state === "failed") speechError = "Audio could not play. Your response remains readable.";
            }
            if (generation === data.generation_id) {
                nativePosition = Math.max(0, Number(data.position_ms) || 0);
                nativePlaybackMetrics = {underruns: data.underruns || 0, underrun_ms: data.underrun_ms || 0,
                    prebuffer_ms: data.prebuffer_ms || 0, position_ms: data.position_ms || 0};
                if (nativePlaybackGeneration !== data.generation_id || nativePlaybackState !== data.state) {
                    nativePlaybackGeneration = data.generation_id; nativePlaybackState = data.state;
                    feedback(data.state, data.generation_id);
                }
            }
            break;
        case "native_output":
            nativeAudible = data.known === true && data.audible === true;
            outputNotice = data.known && !data.audible && (playingAudio || nativePlayback) ? "Thursday's audio output is silent or disconnected." : "";
            break;
        case "tts_preparing":
            if (retiredGenerations.indexOf(data.generation_id) >= 0) break;
            if (data.generation_id && generation !== data.generation_id) { stopAudio(); generation = data.generation_id; }
            speechError = "";
            speechPreparing = true;
            break;
        case "tts_audio":
            if (data.client_id !== "native" || muted || retiredGenerations.indexOf(data.generation_id) >= 0
                    || !String(data.local_url || "").startsWith("file://")) { release(data); break; }
            if (generation !== data.generation_id) { stopAudio(); generation = data.generation_id; }
            speechPreparing = false;
            if (audioQueue.length >= 8) release(data);
            else { audioQueue = audioQueue.concat([data]); nextAudio(); }
            break;
        case "tts_synthesis_done": if (generation === data.generation_id) speechPreparing = false; break;
        case "tts_stop": if (!data.generation_id || generation === data.generation_id) stopAudio(); break;
        case "tts_status":
            if (data.client_id && data.client_id !== "native") break;
            if (data.generation_id && generation && data.generation_id !== generation) break;
            speechPreparing = false;
            speechError = ["fallback", "unavailable"].indexOf(data.state) >= 0 ? String(data.message || "Speech is unavailable.") : "";
            break;
        case "native_command_result":
            if (data.command === "message") { sendPending = false; submittedDraft = ""; }
            if (data.command === "voice_settings") { voiceSettingsPending = false; voiceSettingsNotice = "Voice saved."; }
            if (data.command === "voice_preview") voiceSettingsNotice = "Playing voice preview.";
            if (data.command === "voice_input") voiceSettingsNotice = "Microphone saved.";
            break;
        case "native_error":
            if (data.command === "message") { submittedComposerDraft = ""; submittedComposerPrompt = ""; }
            voiceSettingsPending = false;
            if (data.command === "conversation") { historyLoading = false; historyNeedsReload = true; }
            errorText = String(data.message || "Thursday could not complete the request.");
            sendPending = false; submittedDraft = ""; break;
        case "error": submittedComposerDraft = ""; submittedComposerPrompt = ""; errorText = String(data.content || "Thursday could not complete the request."); busy = false; sendPending = false; submittedDraft = ""; break;
        case "shutdown": disconnect(); break;
        }
    }
    Process {
        id: transport
        command: root.configured ? [root.pythonExecutable, "-m", "assistant.native_client"] : []
        workingDirectory: root.repoRoot
        stdinEnabled: true
        stdout: SplitParser { onRead: line => { try { root.handle(JSON.parse(line)); } catch (error) { root.errorText = "Thursday sent an unreadable response."; } } }
        stderr: StdioCollector {}
        onExited: (code, status) => {
            startup.stop(); root.submittedComposerDraft = ""; root.submittedComposerPrompt = ""; root.connected = false; root.ready = false; root.sendPending = false; root.submittedDraft = "";
            root.busy = false; root.voiceSettingsPending = false; root.voiceState = "idle"; root.confirmations = []; root.stopAudio();
            if (root.requested) root.errorText = "Thursday disconnected. Open Thursday again to retry.";
            root.requested = false;
        }
    }
    Timer { id: startup; interval: 12000; onTriggered: { root.disconnect(); root.errorText = "Thursday did not connect. Check your optional Thursday configuration, then retry."; } }
    LazyLoader {
        id: audio
        active: root.playingAudio !== null || root.audioQueue.length > 0
        source: Qt.resolvedUrl("ThursdayAudio.qml")
    }
    Binding { target: audio.item; property: "source"; value: root.playingAudio ? root.playingAudio.local_url : ""; when: !!audio.item }
    Binding { target: audio.item; property: "muted"; value: root.muted; when: !!audio.item }
    Connections { target: audio.item; ignoreUnknownSignals: true; function onFinished(failed) { root.finishAudio(failed); } }
    IpcHandler {
        target: "thursday"
        function toggle(): void { if (root.opened) root.opened = false; else root.showIsland(); }
        function open(): void { root.showIsland(); }
        function focus(): void { root.showIsland(); }
        function show(): void { root.showIsland(); }
        function hide(): void { root.opened = false; }
        function audioStatus(): string { return JSON.stringify({muted: root.muted, speak_typed: root.speakTyped, playing: root.speaking, preparing: root.speechPreparing, playback_running: root.playbackRunning, native_pcm: root.nativePlayback, position_ms: root.playbackPosition, audio_level: root.visualizerLevel, measured_levels: root.nativePlayback || !!root.audioEnvelope, output_notice: root.outputNotice, pcm_metrics: root.nativePlaybackMetrics}); }
        function connect(): void { root.connectHelper(); }
        function disconnect(): void { root.disconnect(); }
    }
    Component.onCompleted: if (configured && Quickshell.env("SUMI_PREVIEW") !== "1") connectHelper()
}
