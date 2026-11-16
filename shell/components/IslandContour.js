.pragma library

// Exterior island contour as SVG path data. Convex corners use continuous
// curvature (a circular arc eased in and out by cubic segments, the same
// construction as smoothed iOS corners); notch shoulders stay circular.

function fixed(value) { return Math.round(value * 100) / 100; }

function corner(radius, smoothing, budget) {
    const r = Math.max(0, Math.min(radius, budget));
    if (r <= 0.01) return null;
    const xi = Math.max(0, Math.min(smoothing, budget / r - 1));
    const p = Math.min(budget, (1 + xi) * r);
    const arcMeasure = 90 * (1 - xi);
    const arc = Math.sin(arcMeasure / 2 * Math.PI / 180) * r * Math.SQRT2;
    const alpha = (90 - arcMeasure) / 2;
    const tangent = r * Math.tan(alpha / 2 * Math.PI / 180);
    const beta = 45 * xi;
    const c = tangent * Math.cos(beta * Math.PI / 180);
    const d = c * Math.tan(beta * Math.PI / 180);
    const b = (p - arc - c - d) / 3;
    return { r: r, p: p, a: 2 * b, b: b, c: c, d: d, arc: arc };
}

// Emits a convex, clockwise corner. The path is at corner - u * p, travelling
// along unit vector u; it leaves along unit vector v at corner + v * p.
function convex(cx, cy, ux, uy, vx, vy, k) {
    const sx = cx - ux * k.p, sy = cy - uy * k.p;
    const e1x = sx + ux * (k.a + k.b + k.c) + vx * k.d, e1y = sy + uy * (k.a + k.b + k.c) + vy * k.d;
    const e2x = e1x + (ux + vx) * k.arc, e2y = e1y + (uy + vy) * k.arc;
    return " C " + fixed(sx + ux * k.a) + " " + fixed(sy + uy * k.a)
        + " " + fixed(sx + ux * (k.a + k.b)) + " " + fixed(sy + uy * (k.a + k.b))
        + " " + fixed(e1x) + " " + fixed(e1y)
        + " A " + fixed(k.r) + " " + fixed(k.r) + " 0 0 1 " + fixed(e2x) + " " + fixed(e2y)
        + " C " + fixed(e2x + ux * k.d + vx * k.c) + " " + fixed(e2y + uy * k.d + vy * k.c)
        + " " + fixed(e2x + ux * k.d + vx * (k.b + k.c)) + " " + fixed(e2y + uy * k.d + vy * (k.b + k.c))
        + " " + fixed(cx + vx * k.p) + " " + fixed(cy + vy * k.p);
}

// width: drawing width; the body is centred horizontally and starts at y = 0.
// Returns an open path for notch mode (the bezel closes it) and a closed one
// for the floating capsule. Fill both; stroke the returned path as is.
function path(width, bodyWidth, bodyHeight, notch, bottomRadius, topRadius, shoulder, smoothing) {
    const w = Math.max(1, bodyWidth), h = Math.max(1, bodyHeight);
    const left = (width - w) / 2, right = left + w;
    const budget = Math.min(w, h) / 2;
    const s = notch ? Math.max(0, Math.min(shoulder, h / 2)) : 0;
    const bottom = corner(bottomRadius, smoothing, Math.min(budget, notch ? h - s : h / 2));
    if (notch) {
        let d = "M " + fixed(right + s) + " 0";
        if (s > 0) d += " A " + fixed(s) + " " + fixed(s) + " 0 0 0 " + fixed(right) + " " + fixed(s);
        if (bottom) {
            d += " L " + fixed(right) + " " + fixed(h - bottom.p);
            d += convex(right, h, 0, 1, -1, 0, bottom);
            d += " L " + fixed(left + bottom.p) + " " + fixed(h);
            d += convex(left, h, -1, 0, 0, -1, bottom);
        } else {
            d += " L " + fixed(right) + " " + fixed(h) + " L " + fixed(left) + " " + fixed(h);
        }
        d += " L " + fixed(left) + " " + fixed(s);
        if (s > 0) d += " A " + fixed(s) + " " + fixed(s) + " 0 0 0 " + fixed(left - s) + " 0";
        return d;
    }
    const top = corner(topRadius, smoothing, budget);
    const t = top ? top.p : 0, b = bottom ? bottom.p : 0;
    let d = "M " + fixed(left + t) + " 0 L " + fixed(right - t) + " 0";
    if (top) d += convex(right, 0, 1, 0, 0, 1, top);
    d += " L " + fixed(right) + " " + fixed(h - b);
    if (bottom) d += convex(right, h, 0, 1, -1, 0, bottom);
    d += " L " + fixed(left + b) + " " + fixed(h);
    if (bottom) d += convex(left, h, -1, 0, 0, -1, bottom);
    d += " L " + fixed(left) + " " + fixed(t);
    if (top) d += convex(left, 0, 0, -1, 1, 0, top);
    return d + " Z";
}
