import QtQuick

// A wheel-only front surface sees horizontal gestures before nested controls
// accept them. No mouse buttons are accepted, so clicking and dragging still
// reaches the controls beneath; unaccepted vertical wheel events do too.
MouseArea {
    id: root
    required property var deck
    property bool active: true
    enabled: active && !!deck && deck.active
    acceptedButtons: Qt.NoButton
    scrollGestureEnabled: true
    hoverEnabled: false
    onWheel: event => {
        event.accepted = root.deck.handleWheel(event.pixelDelta.x, event.pixelDelta.y,
            event.angleDelta.x, event.angleDelta.y, event.phase);
    }
}
