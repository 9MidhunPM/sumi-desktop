import QtQuick
import QtQuick.Controls
import QtQuick.Window

// Device lists can outgrow a short output. Keyboard focus must remain visible
// just as it does when a pointer user scrolls the same list.
ScrollView {
    id: root
    contentWidth: availableWidth
    clip: true
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ScrollBar.vertical.policy: ScrollBar.AsNeeded

    function revealItem(item) {
        if (!item) return;
        const viewports = [];
        let ancestor = item.parent;
        while (ancestor && ancestor !== root) {
            if (typeof ancestor.contentY === "number" && ancestor.contentItem) viewports.push(ancestor);
            ancestor = ancestor.parent;
        }
        if (ancestor !== root) return;
        // Reveal inside a nested list first, then inside the complete panel.
        for (const flick of viewports) {
            const point = item.mapToItem(flick.contentItem, 0, 0);
            let target = flick.contentY;
            if (point.y < target + 6) target = point.y - 6;
            else if (point.y + item.height > target + flick.height - 6) target = point.y + item.height - flick.height + 6;
            flick.contentY = Math.max(0, Math.min(Math.max(0, flick.contentHeight - flick.height), target));
        }
    }
    Connections {
        target: root.Window.window
        function onActiveFocusItemChanged() {
            Qt.callLater(() => { if (root.Window.window) root.revealItem(root.Window.window.activeFocusItem); });
        }
    }
    Keys.onPressed: event => {
        if (!root.activeFocus) return;
        const flick = root.contentItem;
        let target = flick.contentY;
        if (event.key === Qt.Key_PageDown) target += flick.height * 0.8;
        else if (event.key === Qt.Key_PageUp) target -= flick.height * 0.8;
        else if (event.key === Qt.Key_Home) target = 0;
        else if (event.key === Qt.Key_End) target = flick.contentHeight;
        else return;
        flick.contentY = Math.max(0, Math.min(Math.max(0, flick.contentHeight - flick.height), target));
        event.accepted = true;
    }
}
