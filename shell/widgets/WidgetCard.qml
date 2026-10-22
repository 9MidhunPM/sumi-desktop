import QtQuick
import "../config"

Item {
    id: root
    property real uiScale: 1
    property bool surface: true
    readonly property color panelColor: Qt.rgba(Theme.desktopBackground.r, Theme.desktopBackground.g, Theme.desktopBackground.b, 0.94)
    readonly property color mainText: legible(Theme.textMain)
    readonly property color secondaryText: legible(Theme.textSoft)
    readonly property color warningText: legible(Theme.accentWarn)
    default property alias content: contentItem.data
    readonly property real contentWidth: width / Math.max(0.01, uiScale)
    readonly property real contentHeight: height / Math.max(0.01, uiScale)

    function luminance(value) {
        const linear = channel => channel <= 0.04045 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);
        return linear(value.r) * 0.2126 + linear(value.g) * 0.7152 + linear(value.b) * 0.0722;
    }
    function legible(foreground) {
        // White underneath the translucent panel is the worst-case wallpaper.
        const background = Qt.rgba(panelColor.r * panelColor.a + 1 - panelColor.a,
            panelColor.g * panelColor.a + 1 - panelColor.a, panelColor.b * panelColor.a + 1 - panelColor.a, 1);
        const bg = luminance(background);
        let value = foreground;
        for (let step = 0; step < 20; step++) {
            const fg = luminance(value);
            if ((Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05) >= 4.55) return value;
            value = Qt.rgba(value.r + (1 - value.r) * 0.12, value.g + (1 - value.g) * 0.12, value.b + (1 - value.b) * 0.12, 1);
        }
        return "#ffffff";
    }

    Item {
        id: contentItem
        width: root.contentWidth
        height: root.contentHeight
        scale: root.uiScale
        transformOrigin: Item.TopLeft
        Rectangle {
            anchors.fill: parent
            visible: root.surface
            radius: 22
            color: root.panelColor
            border.width: 1
            border.color: Qt.rgba(Theme.textMain.r, Theme.textMain.g, Theme.textMain.b, 0.15)
        }
    }
}
