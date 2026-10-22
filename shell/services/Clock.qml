pragma Singleton

import QtQuick
import Quickshell as Qs

Qs.Singleton {
    readonly property date date: safeDate(clock ? clock.date : null)
    readonly property var timeParts: formatTime(date)
    readonly property string hour: timeParts && timeParts.hour || "–"
    readonly property string minute: timeParts && timeParts.minute || "––"
    readonly property string time: timeParts && timeParts.time || "–:––"
    readonly property string period: timeParts && timeParts.period || ""
    readonly property string accessibleTime: timeParts && timeParts.accessibleTime || "Time unavailable"
    readonly property string dateShort: Qt.formatDateTime(safeDate(date), "ddd, d MMM") || ""
    readonly property string dateLabel: dateShort || ""
    readonly property string monthLabel: Qt.formatDateTime(safeDate(date), "MMMM yyyy") || ""

    function isValidDate(value): bool {
        return !!value && typeof value.getTime === "function" && isFinite(value.getTime());
    }

    function safeDate(value): date {
        return isValidDate(value) ? value : new Date();
    }

    function formatTime(value): var {
        if (!isValidDate(value))
            return { hour: "–", minute: "––", time: "–:––", period: "", accessibleTime: "Time unavailable" };
        const hour = String(value.getHours() % 12 || 12);
        const minute = (value.getMinutes() < 10 ? "0" : "") + value.getMinutes();
        const period = value.getHours() < 12 ? "AM" : "PM";
        const time = hour + ":" + minute;
        return { hour: hour, minute: minute, time: time, period: period, accessibleTime: time + " " + period };
    }

    Qs.SystemClock { id: clock; precision: Qs.SystemClock.Minutes }
}
