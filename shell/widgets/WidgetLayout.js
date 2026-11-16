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
    // Every wallpaper uses the same full-size Eww composition. Shrink only
    // when the enabled widgets cannot physically fit the available viewport.
    const sizes = {clock: [520, 222], spotify: [420, 183], priorities: [320, 168], deadline: [320, 104]};
    const margin = Math.min(width * 0.04, width < 900 ? 24 : 48);
    const top = Math.min(80, Math.max(52, height * 0.09));
    const bottom = Math.min(32, Math.max(16, height * 0.03));
    const gap = compact ? 16 : 20;
    const areaWidth = Math.max(1, width - margin * 2);
    const areaHeight = Math.max(1, height - top - bottom);
    const mode = ["left", "right", "split"].indexOf(override) >= 0 ? override
        : ["left", "right", "split"].indexOf(design.mode) >= 0 ? design.mode : "split";
    const explicit = ["left", "right", "split"].indexOf(override) >= 0;
    const paired = active.indexOf("clock") >= 0 && active.indexOf("spotify") >= 0;
    // Place the Eww clock/player stack atomically. Collision fitting must never
    // send the player to another side of the artwork or separate the two.
    const unitKeys = paired ? ["pair"].concat(active.filter(key => key !== "clock" && key !== "spotify")) : active;
    const unitSizes = Object.assign({}, sizes);
    unitSizes.pair = [Math.max(sizes.clock[0], sizes.spotify[0]), sizes.clock[1] + sizes.spotify[1]];
    const leftKeys = unitKeys.filter(key => key === "pair" || key === "clock" || key === "spotify");
    const rightKeys = unitKeys.filter(key => key === "priorities" || key === "deadline");
    const columnWidth = entries => Math.max.apply(null, entries.map(key => unitSizes[key][0]).concat([0]));
    const columnHeight = entries => entries.reduce((sum, key) => sum + unitSizes[key][1], 0) + Math.max(0, entries.length - 1) * gap;
    const twoColumns = mode === "split" && leftKeys.length > 0 && rightKeys.length > 0
        && areaWidth >= columnWidth(leftKeys) + columnWidth(rightKeys) + gap;
    const requiredHeight = twoColumns ? Math.max(columnHeight(leftKeys), columnHeight(rightKeys)) : columnHeight(unitKeys);
    const scale = Math.min(1, areaWidth / Math.max(1, columnWidth(unitKeys)), areaHeight / Math.max(1, requiredHeight));
    const pad = gap * scale;
    const result = {compact: compact, scale: scale, mode: mode, fallback: false};
    const units = {};
    keys.forEach(key => { result[key] = {x: margin, y: top, width: sizes[key][0] * scale, height: sizes[key][1] * scale}; });
    unitKeys.forEach(key => { units[key] = {x: margin, y: top, width: unitSizes[key][0] * scale, height: unitSizes[key][1] * scale}; });

    function bound(rect) {
        rect.x = clamp(rect.x, margin, width - margin - rect.width);
        rect.y = clamp(rect.y, top, height - bottom - rect.height);
        return rect;
    }
    function publish() {
        unitKeys.forEach(key => {
            if (key !== "pair") { result[key] = units[key]; return; }
            const pair = units.pair;
            result.clock.x = pair.x + (pair.width - result.clock.width) / 2;
            result.clock.y = pair.y;
            result.spotify.x = pair.x + (pair.width - result.spotify.width) / 2;
            result.spotify.y = pair.y + result.clock.height;
        });
        return result;
    }
    function pack() {
        const left = twoColumns ? leftKeys : unitKeys;
        const right = twoColumns ? rightKeys : [];
        function column(items, alignRight) {
            const total = items.reduce((sum, key) => sum + units[key].height, 0) + Math.max(0, items.length - 1) * pad;
            let y = top + Math.max(0, (areaHeight - total) * 0.32);
            items.forEach(key => {
                const rect = units[key];
                rect.x = alignRight ? width - margin - rect.width : margin;
                rect.y = y;
                y += rect.height + pad;
            });
        }
        column(left, mode === "right");
        column(right, true);
    }
    pack();
    if (explicit || !design.anchors || active.length === 0) return publish();
    const placed = [];
    for (const key of unitKeys) {
        const rect = units[key];
        const point = sourcePoint(design.anchors[key === "pair" ? "clock" : key], scene.sourceSize, width, height);
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
            return publish();
        }
        units[key] = fitting[0];
        placed.push(units[key]);
    }
    return publish();
}
