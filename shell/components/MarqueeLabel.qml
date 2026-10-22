import QtQuick
import "../config"

// Two identical copies make the loop continuous without changing the title.
Item {
    id: root
    objectName: "marqueeLabel"
    property string text: ""
    property color color: Theme.textMain
    property font font: Qt.font({ family: Theme.font, pixelSize: 11, weight: Font.Medium })
    property bool animate: true
    readonly property real naturalTextWidth: first.implicitWidth
    readonly property bool scrolling: animate && !Theme.effectiveReducedMotion && visible
        && width > 0 && naturalTextWidth > width + 0.5
    readonly property real offset: position
    property real position: 0
    readonly property real gap: 28
    implicitWidth: naturalTextWidth
    implicitHeight: first.implicitHeight
    clip: true
    Accessible.role: Accessible.StaticText
    Accessible.name: text

    function reset(): void {
        movement.stop();
        position = 0;
        if (scrolling) movement.start();
    }
    onScrollingChanged: reset()
    onTextChanged: reset()
    onNaturalTextWidthChanged: reset()
    onWidthChanged: reset()
    Component.onCompleted: reset()

    Text {
        anchors.fill: parent
        visible: !root.scrolling
        text: root.text
        color: root.color
        font: root.font
        textFormat: Text.PlainText
        wrapMode: Text.NoWrap
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
        renderType: Text.NativeRendering
        Accessible.ignored: true
    }
    Item {
        objectName: "marqueeTrack"
        x: -root.offset
        height: parent.height
        visible: root.scrolling
        Text {
            id: first
            text: root.text
            color: root.color
            font: root.font
            height: parent.height
            textFormat: Text.PlainText
            wrapMode: Text.NoWrap
            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
            Accessible.ignored: true
        }
        Text {
            x: root.naturalTextWidth + root.gap
            text: root.text
            color: root.color
            font: root.font
            height: parent.height
            textFormat: Text.PlainText
            wrapMode: Text.NoWrap
            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
            Accessible.ignored: true
        }
    }
    SequentialAnimation {
        id: movement
        PauseAnimation { duration: 800 }
        NumberAnimation {
            target: root
            property: "position"
            from: 0
            to: root.naturalTextWidth + root.gap
            duration: Math.max(1, Math.round((root.naturalTextWidth + root.gap) / 28 * 1000))
            loops: Animation.Infinite
            easing.type: Easing.Linear
        }
    }
}
