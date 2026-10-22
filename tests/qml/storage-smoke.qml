import QtQuick
import Quickshell
import "../../shell/config" as C

ShellRoot {
    property int phase: 0
    Component.onCompleted: console.info("SUMI_STORAGE_INIT", C.Theme.name, C.Settings.dnd)
    Timer {
        interval: 500
        repeat: true
        running: true
        onTriggered: {
            if (phase === 0) {
                if (C.Theme.name !== "Fixture Theme") { Qt.exit(1); return; }
                C.Settings.setValue("reducedMotion", true);
                console.info("SUMI_STORAGE_WRITE_INVALID");
            } else if (phase === 1) {
                if (C.Theme.name !== "Fixture Theme") { Qt.exit(2); return; }
                console.info("SUMI_STORAGE_WRITE_VALID");
            } else {
                if (C.Theme.name !== "Updated Theme" || !C.Settings.reducedMotion) { Qt.exit(3); return; }
                console.info("SUMI_STORAGE_SMOKE_OK");
                Qt.quit();
            }
            phase += 1;
        }
    }
}
