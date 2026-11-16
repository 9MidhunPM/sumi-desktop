import QtQuick
import "../config"

// Reads one vivid, legible accent from the current artwork so the island's
// music visuals take their colour from the track. The image is decoded once at
// a tiny size per cover; nothing is sampled while artwork is unavailable.
Canvas {
    id: root
    property url source: ""
    property color fallback: IslandStyle.musicTint
    property color accent: fallback
    property url sampled: ""
    readonly property int sampleSize: 24
    width: 1; height: 1
    opacity: 0
    renderTarget: Canvas.Image
    Accessible.ignored: true

    function request(): void {
        if (!available) return;
        if (sampled.toString().length && sampled !== source) unloadImage(sampled);
        sampled = source;
        if (!source.toString().length) { accent = fallback; return; }
        loadImage(source, Qt.size(sampleSize, sampleSize));
        if (isImageLoaded(source)) measure();
    }
    function measure(): void {
        if (!isImageLoaded(sampled)) return;
        const pixels = getContext("2d").createImageData(sampled.toString()).data;
        const bins = [];
        for (let i = 0; i < 18; i++) bins.push({ weight: 0, r: 0, g: 0, b: 0 });
        let neutral = 0;
        for (let index = 0; index + 3 < pixels.length; index += 4) {
            if (pixels[index + 3] < 128) continue;
            const r = pixels[index] / 255, g = pixels[index + 1] / 255, b = pixels[index + 2] / 255;
            const max = Math.max(r, g, b), min = Math.min(r, g, b);
            const saturation = max > 0 ? (max - min) / max : 0;
            if (max < 0.16 || saturation < 0.18) { neutral++; continue; }
            let hue = 0;
            if (max === r) hue = ((g - b) / (max - min) + 6) % 6;
            else if (max === g) hue = (b - r) / (max - min) + 2;
            else hue = (r - g) / (max - min) + 4;
            // Prefer colour that is both saturated and bright enough to glow on black.
            const weight = saturation * saturation * max;
            const bin = bins[Math.min(17, Math.floor(hue * 3))];
            bin.weight += weight; bin.r += r * weight; bin.g += g * weight; bin.b += b * weight;
        }
        let best = bins[0];
        for (const bin of bins) if (bin.weight > best.weight) best = bin;
        if (best.weight < 0.6) { accent = neutral > 0 ? "#e2e2e8" : fallback; return; }
        const colour = Qt.rgba(best.r / best.weight, best.g / best.weight, best.b / best.weight, 1);
        accent = Qt.hsla(colour.hslHue, Math.max(0.42, Math.min(0.82, colour.hslSaturation)),
            Math.max(0.64, Math.min(0.78, colour.hslLightness)), 1);
    }
    onSourceChanged: request()
    onAvailableChanged: request()
    onImageLoaded: measure()
}
