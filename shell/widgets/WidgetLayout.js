.pragma library

// Anchors are normalized TOP-LEFT points in the source wallpaper. awww uses
// centered cover cropping, so map through that same crop before clamping.
function finite(value, fallback) {
    return typeof value === "number" && isFinite(value) ? value : fallback;
}

function clamp(value, low, high) {
    return Math.max(low, Math.min(Math.max(low, high), value));
}

function enabled(flags, key) {
    return flags === false ? false : !flags || typeof flags !== "object" ? true : flags[key] !== false;
}

function sourcePoint(anchor, sourceSize, width, height) {
    const sw = Math.max(1, finite(sourceSize && sourceSize[0], width));
    const sh = Math.max(1, finite(sourceSize && sourceSize[1], height));
    const cover = Math.max(width / sw, height / sh);
    return {
        x: clamp(finite(anchor && anchor[0], 0.06), 0, 1) * sw * cover - (sw * cover - width) / 2,
        y: clamp(finite(anchor && anchor[1], 0.14), 0, 1) * sh * cover - (sh * cover - height) / 2
    };
}

function intersects(a, b, gap) {
    return a.x < b.x + b.width + gap && a.x + a.width + gap > b.x
        && a.y < b.y + b.height + gap && a.y + a.height + gap > b.y;
}

function layout(scene, width, height, override, flags) {
    width = Math.max(1, finite(width, 1920));
    height = Math.max(1, finite(height, 1080));
    scene = scene && typeof scene === "object" ? scene : {};
    const design = scene.layout || {};
    const keys = ["clock", "spotify", "priorities", "deadline"];
    const active = keys.filter(key => enabled(flags, key));
    const compact = !!design.compact || width < 1100 || height < 720;
    const sizes = compact
        ? {clock: [300, 112], spotify: [300, 130], priorities: [300, 154], deadline: [300, 104]}
        : {clock: [420, 150], spotify: [420, 160], priorities: [320, 168], deadline: [320, 104]};
    const margin = Math.min(width * 0.04, width < 900 ? 24 : 48);
    const top = Math.min(80, Math.max(52, height * 0.09));
    const bottom = Math.min(32, Math.max(16, height * 0.03));
    const gap = compact ? 14 : 20;
    const areaWidth = Math.max(1, width - margin * 2);
    const areaHeight = Math.max(1, height - top - bottom);
    const mode = ["left", "right", "split"].indexOf(override) >= 0 ? override
        : ["left", "right", "split"].indexOf(design.mode) >= 0 ? design.mode : "split";
    const explicit = ["left", "right", "split"].indexOf(override) >= 0;
    const widest = Math.max.apply(null, active.map(key => sizes[key][0]).concat([1]));
    const singleHeight = active.reduce((sum, key) => sum + sizes[key][1], 0) + Math.max(0, active.length - 1) * gap;
    const twoColumns = mode === "split" && areaWidth >= (compact ? 600 : 740) + gap;
    const pairHeight = Math.max(
        active.filter(key => key === "clock" || key === "spotify").reduce((sum, key) => sum + sizes[key][1] + gap, 0) - gap,
        active.filter(key => key === "priorities" || key === "deadline").reduce((sum, key) => sum + sizes[key][1] + gap, 0) - gap,
        1);
    const scale = Math.min(1, areaWidth / widest, areaHeight / Math.max(1, twoColumns ? pairHeight : singleHeight));
    const pad = gap * scale;
    const result = {compact: compact, scale: scale, mode: mode, fallback: false};
    keys.forEach(key => { result[key] = {x: margin, y: top, width: sizes[key][0] * scale, height: sizes[key][1] * scale}; });

    function bound(rect) {
        rect.x = clamp(rect.x, margin, width - margin - rect.width);
        rect.y = clamp(rect.y, top, height - bottom - rect.height);
        return rect;
    }

    function pack() {
        const left = active.filter(key => !twoColumns || key === "clock" || key === "spotify");
        const right = twoColumns ? active.filter(key => key === "priorities" || key === "deadline") : [];
        function column(items, alignRight) {
            const total = items.reduce((sum, key) => sum + result[key].height, 0) + Math.max(0, items.length - 1) * pad;
            let y = top + Math.max(0, (areaHeight - total) * 0.32);
            items.forEach(key => {
                const rect = result[key];
                rect.x = alignRight ? width - margin - rect.width : margin;
                rect.y = y;
                y += rect.height + pad;
            });
        }
        column(left, mode === "right");
        column(right, true);
    }

    pack();
    if (explicit || !design.anchors || active.length === 0) return result;
    const placed = [];
    for (let index = 0; index < active.length; index++) {
        const key = active[index];
        const rect = result[key];
        const point = sourcePoint(design.anchors[key], scene.sourceSize, width, height);
        const desired = bound({x: point.x, y: point.y, width: rect.width, height: rect.height});
        const candidates = [desired];
        const xs = [desired.x, margin, width - margin - rect.width];
        const ys = [desired.y, top, height - bottom - rect.height];
        placed.forEach(previous => {
            xs.push(previous.x - rect.width - pad, previous.x + previous.width + pad);
            ys.push(previous.y - rect.height - pad, previous.y + previous.height + pad);
        });
        xs.forEach(x => ys.forEach(y => candidates.push(bound({x: x, y: y, width: rect.width, height: rect.height}))));
        const fitting = candidates.filter(candidate => !placed.some(previous => intersects(candidate, previous, Math.max(0, pad - 0.01))));
        fitting.sort((a, b) => (a.x - desired.x) ** 2 + (a.y - desired.y) ** 2 - (b.x - desired.x) ** 2 - (b.y - desired.y) ** 2);
        if (!fitting.length) {
            result.fallback = true;
            pack();
            return result;
        }
        result[key] = fitting[0];
        placed.push(result[key]);
    }
    return result;
}
