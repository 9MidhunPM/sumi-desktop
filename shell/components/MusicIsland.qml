pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import "../config"
import "../services" as S

Surface {
    id: island
    property bool playing: S.Media.playing
    property bool expanded: playing
    property bool compact: false
    property string timeText: S.Clock.time
    property string periodText: S.Clock.period
    property string trackText: S.Media.title
    property var samples: S.Spectrum.samples
    readonly property int expandedWidth: 400
    signal clockClicked()
    signal musicClicked()
    implicitHeight: Theme.barHeight - 2
    implicitWidth: expanded ? expandedWidth : clockFace.width + 2 * (period.implicitWidth + 18)
    radius: height / 2
    clip: true
    color: playing ? Qt.rgba(Theme.bgPlaying.r, Theme.bgPlaying.g, Theme.bgPlaying.b, Theme.barBackground.a) : Theme.barBackground
    border.color: playing ? Theme.borderStrong : Theme.borderSoft
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: "Calendar, " + timeText + " " + periodText + (playing ? "; Now playing: " + trackText : "")
    Accessible.description: "Enter opens calendar; Space opens media controls"
    Keys.onReturnPressed: clockClicked()
    Keys.onEnterPressed: clockClicked()
    Keys.onSpacePressed: musicClicked()
    Rectangle { anchors.fill: parent; color: "transparent"; radius: parent.radius; border.width: island.activeFocus ? 2 : 0; border.color: Theme.accentBlue }
    Behavior on implicitWidth { NumberAnimation { duration: Theme.effectiveReducedMotion ? 0 : Theme.batteryMotion ? Theme.motionEnter : 250; easing.type: Easing.OutCubic } }
    Behavior on color { ColorAnimation { duration: Theme.effectiveReducedMotion ? 0 : 300 } }
    Behavior on border.color { ColorAnimation { duration: Theme.effectiveReducedMotion ? 0 : 300 } }

    // Numeric time is the fixed anchor. Metadata sits beside it without
    // changing its center, including every frame of the media width animation.
    Item {
        id: clockFace
        objectName: "barClockFace"
        anchors.centerIn: parent
        width: clock.implicitWidth
        height: clock.implicitHeight
        Label {
            id: clock
            objectName: "barClockTime"
            anchors.centerIn: parent
            text: island.timeText
            font.family: Theme.fontMono
            font.pixelSize: 22
            font.weight: Font.DemiBold
            color: Theme.textMain
        }
    }
    Label {
        id: period
        objectName: "barClockPeriod"
        anchors.left: clockFace.right
        anchors.leftMargin: 6
        anchors.verticalCenter: parent.verticalCenter
        text: island.periodText
        font.family: Theme.font
        font.pixelSize: 9
        font.weight: Font.Bold
        color: Theme.accentBlue
    }
    Icon {
        objectName: "musicCalendarIcon"
        anchors.right: clockFace.left; anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        name: "calendar"; size: 12; color: Theme.textSoft
        opacity: !island.expanded && spectrum.opacity <= 0.001 ? 1 : 0
        Behavior on opacity {
            id: calendarMotion
            NumberAnimation { duration: calendarMotion.targetValue > 0 ? Theme.motionControl : 0; easing.type: Easing.OutCubic }
        }
    }
    Item {
        objectName: "musicMetadata"
        anchors.left: period.right
        anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        width: Math.max(0, island.width - x - 14)
        height: 18
        clip: true
        opacity: island.expanded ? 1 : 0
        MarqueeLabel {
            objectName: "musicTrackTitle"
            anchors.fill: parent
            text: island.trackText
            color: Theme.textMain
            font.pixelSize: 12
            animate: island.expanded && island.playing && Theme.expressiveMotion
        }
        Behavior on opacity { NumberAnimation { duration: Theme.motionEnter } }
    }
    Row {
        id: spectrum
        objectName: "musicSpectrum"
        readonly property int barCount: 20
        anchors.right: clockFace.left
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        width: Math.max(0, clockFace.x - 26)
        height: 14
        spacing: Math.min(1.5, width / (barCount * 2))
        clip: true
        opacity: island.expanded ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionExit } }
        Repeater {
            model: spectrum.barCount
            Rectangle {
                required property int index
                objectName: "musicSpectrumBar" + index
                width: Math.max(0, (spectrum.width - spectrum.spacing * (spectrum.barCount - 1)) / spectrum.barCount)
                height: Math.max(1.5, Math.min(100, Math.max(0, Number(island.samples[index]) || 0)) / 100 * spectrum.height)
                y: spectrum.height - height
                radius: Math.min(1.5, width / 2)
                color: index < 10 ? Theme.accentCyan : Theme.accentBlue
                Behavior on height { NumberAnimation { duration: Theme.effectiveReducedMotion ? 0 : 90; easing.type: Easing.OutQuad } }
            }
        }
    }
    MouseArea {
        id: hit
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: mouse => {
            if (!island.expanded || (mouse.x >= clockFace.x - 8 && mouse.x <= period.x + period.width + 8)) island.clockClicked();
            else island.musicClicked();
        }
    }
}
