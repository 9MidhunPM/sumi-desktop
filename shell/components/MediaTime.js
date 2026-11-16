.pragma library

// Track times: m:ss under an hour, h:mm:ss for long mixes and streams.
function format(seconds) {
    if (!isFinite(seconds) || seconds < 0) return "--:--";
    const value = Math.floor(seconds);
    const hours = Math.floor(value / 3600), minutes = Math.floor(value % 3600 / 60);
    const rest = String(value % 60).padStart(2, "0");
    return hours > 0 ? hours + ":" + String(minutes).padStart(2, "0") + ":" + rest : minutes + ":" + rest;
}
