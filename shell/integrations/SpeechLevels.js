.pragma library

// Independent Sumi reader for the companion's normalized measured envelope.
// Only elapsed measurements are shown, and current silence clears the trail.
function reading(envelope, positionMs, active, count) {
    var size = Math.max(1, Math.min(64, Math.floor(Number(count) || 20)));
    var bars = Array(size).fill(0);
    var empty = {available: false, level: 0, bars: bars};
    if (!active || !envelope || !Array.isArray(envelope.levels)) return empty;
    var step = Number(envelope.interval_ms), position = Number(positionMs);
    if (!isFinite(step) || step <= 0 || !isFinite(position) || position < 0) return empty;
    var current = Math.floor(position / step);
    if (current >= envelope.levels.length) return empty;
    function value(index) {
        var sample = envelope.levels[index];
        return typeof sample === "number" && isFinite(sample) ? Math.min(1, Math.max(0, sample)) : 0;
    }
    var level = value(current);
    if (level > 0) for (var i = 0; i < size; i++) {
        var at = current - size + i + 1;
        if (at >= 0) bars[i] = value(at);
    }
    return {available: true, level: level, bars: bars};
}
