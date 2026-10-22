pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Services.UPower as Up

Singleton {
    readonly property var device: Up.UPower.displayDevice
    readonly property bool available: device && device.isPresent
    readonly property bool onBattery: Up.UPower.onBattery
    readonly property real percent: available ? Math.round(device.percentage * 100) : 100
    readonly property bool charging: available && device.state === Up.UPowerDeviceState.Charging
    readonly property string profile: Up.PowerProfiles.profile === Up.PowerProfile.PowerSaver ? "power-saver" : (Up.PowerProfiles.profile === Up.PowerProfile.Performance ? "performance" : "balanced")
    readonly property bool performanceAvailable: Up.PowerProfiles.hasPerformanceProfile
    readonly property string timeLabel: {
        if (!available) return "AC power";
        if (device.state === Up.UPowerDeviceState.FullyCharged) return "Fully charged";
        if (!onBattery && !charging) return "AC power";
        const seconds = charging ? device.timeToFull : device.timeToEmpty;
        if (seconds <= 0) return charging ? "Charging" : "On battery";
        const minutes = Math.floor(seconds / 60);
        return Math.floor(minutes / 60) + "h " + (minutes % 60) + "m " + (charging ? "to full" : "remaining");
    }

    function setProfile(value: string): void {
        if (Desktop.preview) return;
        if (value === "power-saver") Up.PowerProfiles.profile = Up.PowerProfile.PowerSaver;
        else if (value === "balanced") Up.PowerProfiles.profile = Up.PowerProfile.Balanced;
        else if (value === "performance" && performanceAvailable) Up.PowerProfiles.profile = Up.PowerProfile.Performance;
    }
}
