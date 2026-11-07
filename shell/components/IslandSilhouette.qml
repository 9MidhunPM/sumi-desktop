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
        const r = Math.max(0, Math.min(expanded ? 28 : notch ? 20 : 18, (right - left) / 2, (bottom - (wide ? shelf : 0)) / 2));
        const neck = Math.min(12, Math.max(0, (bodyWidth - headerWidth) / 2));
        const topRadius = Math.min(18, headerWidth / 2, headerHeight / 2);
        ctx.beginPath();
        if (notch) {
            ctx.moveTo(hr + 12, 0);
            ctx.arc(hr + 12, 12, 12, -Math.PI / 2, -Math.PI, true);
        } else {
            ctx.moveTo(hl + topRadius, inset);
            ctx.lineTo(hr - topRadius, inset);
            ctx.quadraticCurveTo(hr, inset, hr, topRadius);
        }
        if (wide) {
            ctx.lineTo(hr, shelf - neck);
            ctx.quadraticCurveTo(hr, shelf, hr + neck, shelf);
            ctx.lineTo(right - r, shelf);
            ctx.quadraticCurveTo(right, shelf, right, shelf + r);
        } else ctx.lineTo(right, bottom - r);
        ctx.lineTo(right, bottom - r);
        ctx.quadraticCurveTo(right, bottom, right - r, bottom);
        ctx.lineTo(left + r, bottom);
        ctx.quadraticCurveTo(left, bottom, left, bottom - r);
        if (wide) {
            ctx.lineTo(left, shelf + r);
            ctx.quadraticCurveTo(left, shelf, left + r, shelf);
            ctx.lineTo(hl - neck, shelf);
            ctx.quadraticCurveTo(hl, shelf, hl, shelf - neck);
        }
        if (notch) {
            ctx.lineTo(hl, 12);
            ctx.arc(hl - 12, 12, 12, 0, -Math.PI / 2, true);
        } else {
            ctx.lineTo(hl, topRadius);
            ctx.quadraticCurveTo(hl, inset, hl + topRadius, inset);
        }
        ctx.fillStyle = "#000000";
        ctx.fill();
        ctx.strokeStyle = focused ? "#a1a1aa" : outline;
        ctx.lineWidth = 1;
        // The screen bezel closes a notch; do not paint a line across it.
        if (!notch) ctx.closePath();
        ctx.stroke();
    }
}
