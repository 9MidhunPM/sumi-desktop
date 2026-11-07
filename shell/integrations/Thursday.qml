pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io

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
    property bool opened: false
    property bool hudDismissed: true
    property var currentScreen: Quickshell.screens[0] || null
    property bool connected: false
    property bool ready: false
    property bool busy: false
    property bool sendPending: false
    property string submittedDraft: ""
    property string lastPrompt: ""
    property string latestAnswer: ""
    property string errorText: ""
    property string voiceError: ""
    property string speechError: ""
    property string outputNotice: ""
    property string transcript: ""
    property string voiceState: "idle"
    property string voiceSession: ""
    property var task: null
    property var confirmations: []
    property int conversationId: -1
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
    readonly property int playbackPosition: audio.item ? audio.item.position : 0
    readonly property var audioEnvelope: playingAudio ? playingAudio.audio_levels || null : null
    readonly property bool playbackRunning: !!playingAudio && !muted && !!audio.item && audio.item.playing
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
        startup.stop();
        stopAudio();
        transport.running = false;
        connected = false; ready = false; busy = false; sendPending = false;
        submittedDraft = ""; voiceState = "idle"; confirmations = [];
    }
    function send(command) {
        const allowed = ["message", "voice_start", "voice_stop", "voice_cancel", "task_cancel", "task_resume", "confirm",
            "playback", "audio_release", "open_web", "settings", "health"];
        if (!command || allowed.indexOf(command.command) < 0) return false;
        if (!transport.running) {
            errorText = configured ? "Thursday is disconnected. Open Thursday again to retry." : "Thursday is not configured. Set SUMI_THURSDAY_ROOT to enable it.";
            return false;
        }
        transport.write(JSON.stringify(command) + "\n");
        return true;
    }
    function submit(text) {
        const prompt = String(text || "").trim();
        if (!prompt || !connected || !ready || busy || taskActive || sendPending) return;
        stopAudio();
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
    function openChat() { if (connectHelper()) send({command: "open_web"}); }
    function showIsland() { connectHelper(); opened = true; }
    function release(item) { if (item && item.audio_id) send({command: "audio_release", audio_id: item.audio_id}); }
    function feedback(state, id) { if (id) send({command: "playback", state: state, generation_id: id}); }
    function stopAudio() {
        if (generation) retiredGenerations = retiredGenerations.concat([generation]).slice(-64);
        const old = playingAudio;
        playingAudio = null;
        release(old);
        for (const item of audioQueue) release(item);
        audioQueue = []; speechPreparing = false; nativeAudible = false; outputNotice = "";
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
        voiceState = String(data.state || "idle");
        voiceSession = String(data.session_id || data.id || "");
        transcript = String(data.transcript || ""); voiceError = String(data.error || "");
        if (recording) { stopAudio(); latestAnswer = ""; errorText = ""; }
    }
    function handle(event) {
        if (!event || typeof event.type !== "string") return;
        const data = event.data || {};
        switch (event.type) {
        case "native_connection":
            connected = data.connected === true;
            if (connected) { startup.stop(); errorText = ""; }
            else ready = false;
            break;
        case "native_health": ready = data.model_ready === true; if (data.status === "offline") connected = false; break;
        case "native_settings":
            muted = data.muted === true; speakTyped = data.speak_typed === true;
            if (muted) stopAudio();
            break;
        case "init":
            conversationId = Number(data.conversation_id) || -1; ready = data.model_ready === true;
            busy = data.busy === true; task = data.task || null;
            confirmations = Array.isArray(data.pending_confirms) ? data.pending_confirms : [];
            if (data.voice_state) setVoice(data.voice_state);
            break;
        case "user_message":
            if (data.conversation_id) conversationId = data.conversation_id;
            latestAnswer = ""; busy = true; sendPending = false;
            break;
        case "token": latestAnswer += String(data.chunk || ""); break;
        case "final_response": latestAnswer = String(data.content || latestAnswer); busy = false; sendPending = false; break;
        case "status": busy = data.busy === true; if (!busy) sendPending = false; break;
        case "task_updated": task = data; break;
        case "confirm_required": confirmations = confirmations.filter(item => item.id !== data.id).concat([data]); break;
        case "confirm_resolved": confirmations = confirmations.filter(item => item.id !== data.id); break;
        case "voice_state": setVoice(data); break;
        case "native_output":
            nativeAudible = data.known === true && data.audible === true;
            outputNotice = data.known && !data.audible && playingAudio ? "Thursday's audio output is silent or disconnected." : "";
            break;
        case "tts_preparing":
            if (retiredGenerations.indexOf(data.generation_id) >= 0) break;
            if (data.generation_id && generation !== data.generation_id) { stopAudio(); generation = data.generation_id; }
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
            speechError = data.state === "unavailable" ? String(data.message || "Speech is unavailable.") : "";
            break;
        case "native_command_result": if (data.command === "message") { sendPending = false; submittedDraft = ""; } break;
        case "native_error":
            errorText = String(data.message || "Thursday could not complete the request.");
            sendPending = false; submittedDraft = ""; break;
        case "error": errorText = String(data.content || "Thursday could not complete the request."); busy = false; sendPending = false; submittedDraft = ""; break;
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
            startup.stop(); root.connected = false; root.ready = false; root.sendPending = false; root.submittedDraft = "";
            root.busy = false; root.voiceState = "idle"; root.confirmations = []; root.stopAudio();
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
        function connect(): void { root.connectHelper(); }
        function disconnect(): void { root.disconnect(); }
    }
    Component.onCompleted: if (configured && Quickshell.env("SUMI_PREVIEW") !== "1") connectHelper()
}
