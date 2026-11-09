pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts

// A local month view: no calendar account or event data is implied.
Rectangle {
    id: root
    property date today: new Date()
    property int monthOffset: 0
    readonly property date month: new Date(today.getFullYear(), today.getMonth() + monthOffset, 1)
    readonly property int firstWeekday: (month.getDay() + 6) % 7
    readonly property int daysInMonth: new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
    implicitHeight: content.implicitHeight + 24
    radius: 21
    color: "#202126"

    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            spacing: 4
            Label {
                objectName: "islandCalendarMonth"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: Qt.formatDateTime(root.month, "MMMM yyyy")
                font.pixelSize: 13; font.weight: Font.DemiBold; color: "#f2f4fa"
            }
            IslandPreviewButton {
                objectName: "islandCalendarToday"
                text: "Today"; tooltip: "Show current month"; quiet: true
                implicitHeight: 32; font.pixelSize: 11; leftPadding: 7; rightPadding: 7
                onClicked: root.monthOffset = 0
            }
            IslandPreviewButton {
                objectName: "islandCalendarPrevious"
                text: "‹"; tooltip: "Previous month"; quiet: true
                implicitWidth: 32; implicitHeight: 32; leftPadding: 4; rightPadding: 4
                onClicked: root.monthOffset--
            }
            IslandPreviewButton {
                objectName: "islandCalendarNext"
                text: "›"; tooltip: "Next month"; quiet: true
                implicitWidth: 32; implicitHeight: 32; leftPadding: 4; rightPadding: 4
                onClicked: root.monthOffset++
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 7
            columnSpacing: 3
            rowSpacing: 3
            Repeater {
                model: ["M", "T", "W", "T", "F", "S", "S"]
                Label {
                    required property string modelData
                    text: modelData
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    horizontalAlignment: Text.AlignHCenter
                    color: "#a7afc2"; font.pixelSize: 10
                }
            }
            Repeater {
                model: 42
                Rectangle {
                    id: dayCell
                    required property int index
                    readonly property int day: index - root.firstWeekday + 1
                    readonly property bool inMonth: day > 0 && day <= root.daysInMonth
                    readonly property bool isToday: inMonth && day === root.today.getDate()
                        && root.month.getMonth() === root.today.getMonth() && root.month.getFullYear() === root.today.getFullYear()
                    objectName: "islandCalendarDay" + index
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    implicitHeight: 28
                    radius: 9
                    color: isToday ? "#f5f5f8" : "transparent"
                    Accessible.role: Accessible.StaticText
                    Accessible.name: inMonth ? Qt.formatDateTime(new Date(root.month.getFullYear(), root.month.getMonth(), day), "dddd, d MMMM yyyy") + (isToday ? ", today" : "") : ""
                    Label {
                        anchors.centerIn: parent
                        text: dayCell.inMonth ? dayCell.day : ""
                        color: dayCell.isToday ? "#202027" : "#f2f4fa"
                        font.pixelSize: 12; font.weight: dayCell.isToday ? Font.DemiBold : Font.Normal
                    }
                }
            }
        }
    }
}
