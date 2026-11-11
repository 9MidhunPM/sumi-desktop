pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import "../config"

Slider {
    id: control
    property string iconName: "sun"
    property string label: "Brightness"
    property bool toggleable: false
    property bool muted: false
    property bool horizontalLayout: false
    signal toggleRequested()
    orientation: horizontalLayout ? Qt.Horizontal : Qt.Vertical
    from: 0
    to: 1
    stepSize: 0.01
    padding: 0
    topPadding: horizontalLayout ? 30 : 0
    bottomPadding: horizontalLayout ? 4 : 0
    focusPolicy: Qt.StrongFocus
    Accessible.name: label
    opacity: enabled ? 1 : 0.4
    background: Item {
        width: control.width
        height: control.height
        Item {
            anchors.fill: parent
            visible: !control.horizontalLayout
            Canvas {
                id: track
                anchors.fill: parent
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                Connections {
                    target: control
                    function onPositionChanged() { track.requestPaint(); }
                    function onVisualFocusChanged() { track.requestPaint(); }
                    function onPressedChanged() { track.requestPaint(); }
                }
                onPaint: {
                    const c = getContext("2d");
                    c.reset();
                    const r = Math.min(25, width / 2, height / 2);
                    c.beginPath(); c.moveTo(r, 0); c.lineTo(width-r, 0);
                    c.quadraticCurveTo(width,0,width,r); c.lineTo(width,height-r);
                    c.quadraticCurveTo(width,height,width-r,height); c.lineTo(r,height);
                    c.quadraticCurveTo(0,height,0,height-r); c.lineTo(0,r); c.quadraticCurveTo(0,0,r,0); c.closePath();
                    c.fillStyle = control.pressed ? "#36373d" : "#292a2f"; c.fill();
                    c.save(); c.clip();
                    c.fillStyle = "#f6f6f8";
                    c.fillRect(0,height*(1-control.position),width,height*control.position);
                    c.restore();
                    if (control.visualFocus) { c.lineWidth=3; c.strokeStyle="#ffffff"; c.stroke(); }
                }
            }
            Label {
                anchors { top: parent.top; horizontalCenter: parent.horizontalCenter; topMargin: 15 }
                text: Math.round(control.value * 100) + "%"
                font.pixelSize: 11
                font.weight: Font.Medium
                color: control.position > .85 ? "#393940" : "#d7d7dd"
            }
            Button {
                anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 8 }
                width: 50; height: 48
                visible: control.toggleable
                Accessible.name: control.muted ? "Unmute sound" : "Mute sound"
                focusPolicy: Qt.StrongFocus
                background: Rectangle { color: "transparent"; radius: 20; border.width: parent.visualFocus ? 2 : 0; border.color: control.position > .25 ? "#33343b" : "#ffffff" }
                contentItem: Item {}
                onClicked: control.toggleRequested()
            }
            // Keep the glyph legible when the fill boundary passes through it:
            // white on the track, and the same mask in charcoal over the white fill.
            Item {
                id: glyph
                anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 21 }
                width: 26; height: 26
                Icon { anchors.fill: parent; name: control.iconName; size: 26; color: "#f6f6f8" }
                Item {
                    id: filledGlyph
                    y: Math.max(0, Math.min(glyph.height, 47 - control.height * control.position))
                    width: glyph.width
                    height: glyph.height - y
                    clip: true
                    Icon { x: 0; y: -filledGlyph.y; width: glyph.width; height: glyph.height; name: control.iconName; size: 26; color: "#53545b" }
                }
            }
        }
        Item {
            anchors.fill: parent
            visible: control.horizontalLayout
            Icon { x: 0; y: 3; name: control.iconName; size: 17; color: IslandStyle.secondary }
            Label { x: 24; y: 2; width: Math.max(0, parent.width - 58); text: control.label; elide: Text.ElideRight; font.pixelSize: 11; color: IslandStyle.secondary }
            Label { anchors.right: parent.right; y: 2; text: Math.round(control.value * 100) + "%"; font.pixelSize: 11; color: IslandStyle.text }
            Button {
                visible: control.toggleable
                x: -8; y: -8; width: Metrics.target; height: Metrics.target
                focusPolicy: Qt.StrongFocus
                Accessible.name: control.muted ? "Unmute sound" : "Mute sound"
                onClicked: control.toggleRequested()
                background: Rectangle { color: "transparent"; radius: 8; border.width: parent.visualFocus ? 2 : 0; border.color: IslandStyle.text }
                contentItem: Item {}
            }
            Rectangle {
                objectName: "islandHorizontalLevelTrack"
                x: control.leftPadding
                y: control.topPadding + control.availableHeight / 2 - height / 2
                width: control.availableWidth; height: 5; radius: 2.5
                color: "#45454b"
                Rectangle { width: parent.width * control.position; height: parent.height; radius: parent.radius; color: IslandStyle.text }
            }
        }
    }
    handle: Rectangle {
        visible: control.horizontalLayout
        width: 14; height: 14; radius: 7
        x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
        y: control.topPadding + (control.availableHeight - height) / 2
        color: IslandStyle.text
        border.width: control.visualFocus ? 2 : 0
        border.color: "#8fbfff"
    }
}
