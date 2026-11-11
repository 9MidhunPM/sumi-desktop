.pragma library

// Outer contour bounds. Natural page height chooses the size inside each range.
function profile(route) {
    const profiles = {
        controls: [640, 390, 620], media: [520, 260, 560],
        calendar: [460, 380, 540], pomodoro: [400, 260, 420], power: [400, 250, 420],
        inbox: [540, 230, 600], notification: [500, 220, 460],
        wifi: [480, 250, 580], bluetooth: [480, 260, 580], audio: [480, 280, 580],
        capture: [460, 300, 580], system: [420, 320, 500], settings: [460, 300, 540],
        launcher: [580, 240, 620], files: [580, 240, 620], clipboard: [580, 240, 620],
        thursday: [600, 320, 660], appearance: [680, 420, 660], widgets: [600, 420, 660],
        help: [580, 320, 620], codex: [680, 360, 660]
    };
    const value = profiles[route] || profiles.controls;
    return {width: value[0], minimumHeight: value[1], maximumHeight: value[2]};
}
function height(profile, natural, chrome) {
    const value = Number(natural);
    const target = Math.ceil((Math.max(0, isFinite(value) ? value : 220) + chrome) / 8) * 8;
    return Math.max(profile.minimumHeight, Math.min(profile.maximumHeight, target));
}
