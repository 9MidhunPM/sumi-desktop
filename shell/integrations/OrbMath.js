// Canonical orb model and drawing code for Qt Quick and the web client.
// Vite adds module exports at build time; QML imports these declarations directly.
function bounded(value) {
    return typeof value === "number" && isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
}
function normalized(value) { return Math.pow(Math.min(1, bounded(value) * 16), 0.55); }
function createState() {
    return {phase: 0, displayedLevel: 0, previousFrame: 0, nextPaintAt: 0,
            rawLevel: 0, lastMeasuredLevel: 0, holdUntil: 0};
}
function sample(state, level, now) {
    const raw = bounded(level);
    if (raw > 0) {
        state.lastMeasuredLevel = normalized(raw);
        state.holdUntil = now + 80;
    } else if (state.rawLevel > 0) state.holdUntil = now + 80;
    state.rawLevel = raw;
}
function reset(state) {
    state.displayedLevel = 0;
    state.lastMeasuredLevel = 0;
    state.rawLevel = 0;
    state.holdUntil = 0;
    state.previousFrame = 0;
    state.nextPaintAt = 0;
}
function advance(state, now, level, active, processing, reducedMotion) {
    sample(state, active ? level : 0, now);
    if (state.nextPaintAt && now + 1 < state.nextPaintAt) return false;
    const elapsed = state.previousFrame ? Math.max(0, (now - state.previousFrame) / 1000) : 0.016;
    const dt = Math.min(0.05, elapsed);
    state.nextPaintAt = state.nextPaintAt ? Math.max(state.nextPaintAt + 1000 / 60, now + 1) : now + 1000 / 60;
    state.previousFrame = now;
    const measured = active ? normalized(level) : 0;
    const target = active && measured === 0 && now < state.holdUntil ? state.lastMeasuredLevel : measured;
    const tau = target > state.displayedLevel ? 0.045 : 0.16;
    state.displayedLevel = reducedMotion ? measured : state.displayedLevel + (target - state.displayedLevel) * (1 - Math.exp(-dt / tau));
    if (state.displayedLevel < 0.0001) state.displayedLevel = 0;
    if (!reducedMotion) state.phase = (state.phase + elapsed * Math.PI * 2 / (processing ? 6 : 3.2)) % (Math.PI * 2);
    return true;
}
function radius(side, level, reducedMotion) { return side * (reducedMotion ? 0.31 : 0.25 + bounded(level) * 0.17); }
function points(count) {
    const result = [], total = Math.max(8, Math.min(300, count)), phi = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < total; ++i) {
        const y = 1 - 2 * i / (total - 1), r = Math.sqrt(1 - y * y);
        result.push([Math.cos(phi * i) * r, y, Math.sin(phi * i) * r]);
    }
    return result;
}
function project(vertices, width, height, phase, level, reducedMotion) {
    const side = Math.min(width, height), angle = reducedMotion ? 0 : phase;
    const c = Math.cos(angle), s = Math.sin(angle), r = radius(side, level, reducedMotion);
    const buckets = [[], [], [], [], [], [], [], []];
    for (let i = 0; i < vertices.length; ++i) {
        const p = vertices[i], x = p[0] * c - p[2] * s, z = p[0] * s + p[2] * c;
        const y = p[1] * 0.9553 - z * 0.2955, depth = (p[1] * 0.2955 + z * 0.9553 + 1) / 2;
        buckets[Math.min(7, Math.floor(depth * 8))].push(width / 2 + x * r, height / 2 + y * r);
    }
    return buckets;
}
function paintParticles(ctx, width, height, vertices, phase, level, reducedMotion, rgb, rendering) {
    ctx.clearRect(0, 0, width, height);
    const side = Math.min(width, height);
    if (side <= 0) return;
    const buckets = project(vertices, width, height, phase, level, reducedMotion);
    for (let b = 0; b < 8; ++b) {
        const depth = (b + 0.5) / 8, size = (side < 60 ? 0.35 : 0.8) + depth * (side < 60 ? 0.6 : 1.5);
        ctx.fillStyle = 'rgba(' + rgb + ',' + ((0.2 + depth * 0.8) * (rendering ? 1 : 0.4)) + ')';
        ctx.beginPath();
        const coordinates = buckets[b];
        for (let j = 0; j < coordinates.length; j += 2) {
            ctx.moveTo(coordinates[j] + size, coordinates[j + 1]);
            ctx.arc(coordinates[j], coordinates[j + 1], size, 0, Math.PI * 2);
        }
        ctx.fill();
    }
}
function paintGlow(ctx, side, rgb) {
    ctx.clearRect(0, 0, side, side);
    if (side <= 0) return;
    const gradient = ctx.createRadialGradient(side / 2, side / 2, 0, side / 2, side / 2, side * 0.43);
    gradient.addColorStop(0, 'rgba(' + rgb + ',0.18)');
    gradient.addColorStop(0.55, 'rgba(' + rgb + ',0.09)');
    gradient.addColorStop(1, 'rgba(' + rgb + ',0)');
    ctx.fillStyle = gradient; ctx.fillRect(0, 0, side, side);
}
