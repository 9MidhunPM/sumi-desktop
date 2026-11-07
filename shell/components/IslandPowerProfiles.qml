pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../services" as S

Rectangle {
    id: root
    implicitHeight: 43
    radius: 13
    color: "#2a2c33"
    RowLayout {
        anchors.fill: parent
        anchors.margins: 3
        spacing: 2
        Repeater {
            model: [{id:"power-saver", label:"Power saver", icon:"leaf"}, {id:"balanced", label:"Balanced", icon:"battery"}, {id:"performance", label:"Performance", icon:"bolt"}]
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
                background: Rectangle { radius: 10; color: option.selected ? "#474b59" : option.down || option.hovered ? "#363944" : "transparent"; border.width: option.visualFocus ? 2 : 0; border.color: "#ffffff" }
                contentItem: Item {
                    Row {
                        visible: root.width >= 390
                        anchors.centerIn: parent
                        spacing: 6
                        Icon { name: option.modelData.icon; size: 17; color: option.selected ? "#f3f5fb" : "#9ea5b7" }
                        Label { text: option.modelData.label; color: option.selected ? "#f3f5fb" : "#aeb5c6"; font.pixelSize: 11; height: 17 }
                    }
                    Column {
                        visible: root.width < 390
                        anchors.centerIn: parent
                        spacing: 1
                        Icon { anchors.horizontalCenter: parent.horizontalCenter; name: option.modelData.icon; size: 15; color: option.selected ? "#f3f5fb" : "#9ea5b7" }
                        Label { text: option.modelData.label; color: option.selected ? "#f3f5fb" : "#aeb5c6"; font.pixelSize: 10 }
                    }
                }
                onClicked: S.Battery.setProfile(modelData.id)
            }
        }
    }
}
