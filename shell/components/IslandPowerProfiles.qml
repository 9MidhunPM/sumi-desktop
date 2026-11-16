pragma ComponentBehavior: Bound
import QtQuick
import "../config"
import QtQuick.Controls
import QtQuick.Layouts
import "../services" as S

// A segmented control: one selection glides between the power profiles.
Rectangle {
    id: root
    readonly property var profiles: [{id:"power-saver", label:"Power saver", icon:"leaf"}, {id:"balanced", label:"Balanced", icon:"battery"}, {id:"performance", label:"Performance", icon:"bolt"}]
    readonly property int selectedIndex: Math.max(0, profiles.findIndex(profile => profile.id === S.Battery.profile))
    readonly property real segment: (width - 6 - (profiles.length - 1) * 2) / profiles.length
    implicitHeight: 43
    radius: 12
    color: IslandStyle.raised
    Spring { id: slide; to: 3 + root.selectedIndex * (root.segment + 2); animated: !Motion.reduced && root.width > 0; response: Motion.springResponse * 0.75; damping: Motion.springDamping; settleResponse: Motion.springResponse * 0.75; settleDamping: Motion.springDamping }
    Rectangle {
        x: slide.value; y: 3
        width: Math.max(0, root.segment); height: root.height - 6
        radius: Metrics.compactRadius
        color: IslandStyle.hover
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.07)
    }
    RowLayout {
        anchors.fill: parent
        anchors.margins: 3
        spacing: 2
        Repeater {
            model: root.profiles
            Button {
                id: option
                required property var modelData
                readonly property bool selected: S.Battery.profile === modelData.id
                objectName: "islandPowerProfile-" + modelData.id
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.fillHeight: true
                focusPolicy: Qt.StrongFocus
                hoverEnabled: true
                enabled: modelData.id !== "performance" || S.Battery.performanceAvailable
                opacity: enabled ? 1 : .35
                Accessible.name: modelData.label + " power profile" + (selected ? ", selected" : "")
                background: Rectangle { radius: Metrics.compactRadius; color: !option.selected && (option.down || option.hovered) ? Qt.rgba(1, 1, 1, 0.04) : "transparent"; border.width: option.visualFocus ? 2 : 0; border.color: IslandStyle.text }
                contentItem: Item {
                    Row {
                        visible: root.width >= 390
                        anchors.centerIn: parent
                        spacing: Metrics.space2
                        Icon { name: option.modelData.icon; size: 17; color: option.selected ? IslandStyle.text : IslandStyle.secondary }
                        Label { text: option.modelData.label; color: option.selected ? IslandStyle.text : IslandStyle.secondary; font.pixelSize: 12; font.weight: option.selected ? Font.DemiBold : Font.Medium; height: 17; verticalAlignment: Text.AlignVCenter }
                    }
                    Column {
                        visible: root.width < 390
                        anchors.centerIn: parent
                        spacing: 1
                        Icon { anchors.horizontalCenter: parent.horizontalCenter; name: option.modelData.icon; size: 15; color: option.selected ? IslandStyle.text : IslandStyle.secondary }
                        Label { text: option.modelData.label; color: option.selected ? IslandStyle.text : IslandStyle.secondary; font.pixelSize: 11; visible: root.width >= 240 }
                    }
                }
                onClicked: S.Battery.setProfile(modelData.id)
            }
        }
    }
}
