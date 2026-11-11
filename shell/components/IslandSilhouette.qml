import QtQuick
import "../config"

// A single exterior contour keeps the neck, shoulders and body seam-free.
Canvas {
    id: root
    property real bodyWidth: 176
    property real bodyHeight: 36
    property real headerWidth: bodyWidth
    property real headerHeight: 36
    property bool notch: false
    property bool expanded: false
    property bool focused: false
    property color outline: Theme.islandOutline
    antialiasing: true
    renderTarget: Canvas.Image
    onBodyWidthChanged: requestPaint()
    onBodyHeightChanged: requestPaint()
    onHeaderWidthChanged: requestPaint()
    onHeaderHeightChanged: requestPaint()
    onNotchChanged: requestPaint()
    onExpandedChanged: requestPaint()
    onFocusedChanged: requestPaint()
    onOutlineChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        const ctx = getContext("2d");
        ctx.reset();
        const inset = 0.5;
        const left = (width - bodyWidth) / 2 + inset;
        const right = (width + bodyWidth) / 2 - inset;
        const bottom = Math.max(1, bodyHeight) - inset;
        const hl = (width - headerWidth) / 2 + inset;
        const hr = (width + headerWidth) / 2 - inset;
        const wide = bodyWidth > headerWidth + 0.1;
        const shelf = Math.min(headerHeight, bottom - 1);
        const r = Math.max(0, Math.min(expanded ? IslandStyle.outerRadius : 27, (right - left) / 2, (bottom - (wide ? shelf : 0)) / 2));
        const neck = Math.min(12, Math.max(0, (bodyWidth - headerWidth) / 2));
        const topRadius = Math.min(24, headerWidth / 2, bottom / 2);
        // A sampled superellipse gives each exterior corner the continuous
        // curvature used throughout the reference, rather than a circular arc.
        function corner(cx, cy, radius, start, end) {
            const power = 2 / 2.8;
            for (let i = 1; i <= 16; i++) {
                const angle = start + (end - start) * i / 16;
                const c = Math.cos(angle), sn = Math.sin(angle);
                ctx.lineTo(cx + radius * Math.sign(c) * Math.pow(Math.abs(c), power),
                           cy + radius * Math.sign(sn) * Math.pow(Math.abs(sn), power));
            }
        }
        ctx.beginPath();
        if (notch) {
            ctx.moveTo(hr + 12, 0);
            ctx.arc(hr + 12, 12, 12, -Math.PI / 2, -Math.PI, true);
        } else {
            ctx.moveTo(hl + topRadius, inset);
            ctx.lineTo(hr - topRadius, inset);
            corner(hr - topRadius, inset + topRadius, topRadius, -Math.PI / 2, 0);
        }
        if (wide) {
            ctx.lineTo(hr, shelf - neck);
            ctx.quadraticCurveTo(hr, shelf, hr + neck, shelf);
            ctx.lineTo(right - r, shelf);
            corner(right - r, shelf + r, r, -Math.PI / 2, 0);
        } else ctx.lineTo(right, bottom - r);
        ctx.lineTo(right, bottom - r);
        corner(right - r, bottom - r, r, 0, Math.PI / 2);
        ctx.lineTo(left + r, bottom);
        corner(left + r, bottom - r, r, Math.PI / 2, Math.PI);
        if (wide) {
            ctx.lineTo(left, shelf + r);
            corner(left + r, shelf + r, r, Math.PI, 3 * Math.PI / 2);
            ctx.lineTo(hl - neck, shelf);
            ctx.quadraticCurveTo(hl, shelf, hl, shelf - neck);
        }
        if (notch) {
            ctx.lineTo(hl, 12);
            ctx.arc(hl - 12, 12, 12, 0, -Math.PI / 2, true);
        } else {
            ctx.lineTo(hl, topRadius);
            corner(hl + topRadius, inset + topRadius, topRadius, Math.PI, 3 * Math.PI / 2);
        }
        ctx.fillStyle = "#000000";
        ctx.fill();
        ctx.strokeStyle = focused ? "#a1a1aa" : outline;
        ctx.lineWidth = 0.8;
        // The screen bezel closes a notch; do not paint a line across it.
        if (!notch) ctx.closePath();
        ctx.stroke();
    }
}
