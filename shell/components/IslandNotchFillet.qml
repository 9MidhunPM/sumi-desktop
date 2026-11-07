import QtQuick

// Static concave shoulder: a square minus a quarter circle, mirrored on the left.
// Canvas keeps this small, opaque bezel shape available in the software backend.
Canvas {
    id: root
    property bool mirrored: false
    width: 12
    height: 12
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onMirroredChanged: requestPaint()
    onPaint: {
        const ctx = getContext("2d");
        ctx.reset();
        if (mirrored) { ctx.translate(width,0); ctx.scale(-1,1); }
        ctx.fillStyle = "#000000";
        ctx.beginPath();
        ctx.moveTo(0,0); ctx.lineTo(width,0);
        ctx.arc(width,height,width,-Math.PI/2,-Math.PI,true);
        ctx.closePath(); ctx.fill();
    }
}
