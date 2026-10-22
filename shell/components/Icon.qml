import QtQuick
import QtQuick.Window
import "../config"

// Local SVG alpha masks keep interface icons independent of fonts and themes.
// Canvas.Image supports the software renderer as well as accelerated backends.
Item {
    id: root
    property string name: ""
    property real size: 20
    property color color: Theme.textMain
    property bool preserveDetail: false
    readonly property bool ready: renderer.loaded
    readonly property string resolvedName: {
        const aliases = { apps: "grid" };
        const candidate = aliases[name] || name;
        const names = ["arch", "chatgpt", "grid", "sparkles", "terminal", "code", "bell", "bell-off",
            "wifi", "wifi-off", "bluetooth", "bluetooth-off", "volume", "volume-x",
            "battery", "battery-charging", "settings", "chevron-down", "chevron-up",
            "play", "pause", "music", "calendar", "arrow-right", "more-horizontal", "circle-help"];
        return names.indexOf(candidate) >= 0 ? candidate : "circle-help";
    }
    property url source: name.length ? Qt.resolvedUrl("../assets/icons/" + resolvedName + ".svg") : ""
    implicitWidth: size
    implicitHeight: size
    Accessible.ignored: true
    onColorChanged: renderer.requestPaint()
    onPreserveDetailChanged: renderer.requestPaint()

    Canvas {
        id: renderer
        anchors.centerIn: parent
        // Canvas textures use pixel dimensions. Rasterize at the screen scale
        // and map back to logical size so fractional/HiDPI screens stay crisp.
        readonly property real rasterScale: Math.max(1, Screen.devicePixelRatio)
        width: Math.max(0, Math.ceil(Math.min(root.width, root.height) * rasterScale))
        height: width
        scale: 1 / rasterScale
        renderTarget: Canvas.Image
        antialiasing: true
        smooth: true
        property bool loaded: false
        property url loadedSource: ""
        readonly property int rasterSize: Math.max(24, width)

        function load(): void {
            if (!available) return;
            if (loadedSource.toString().length) unloadImage(loadedSource);
            loadedSource = root.source;
            loaded = false;
            if (loadedSource.toString().length) {
                loadImage(loadedSource, Qt.size(rasterSize, rasterSize));
                loaded = isImageLoaded(loadedSource);
            }
            requestPaint();
        }
        onAvailableChanged: if (available) load()
        onRasterSizeChanged: load()
        onImageLoaded: {
            loaded = isImageLoaded(loadedSource);
            requestPaint();
        }
        onWidthChanged: requestPaint()
        Connections {
            target: root
            function onSourceChanged() { renderer.load(); }
        }
        onPaint: {
            const context = getContext("2d");
            context.reset();
            context.clearRect(0, 0, width, height);
            if (!loaded || !loadedSource.toString().length) return;
            if (root.preserveDetail) {
                // Opaque app logos need their internal contrast retained.
                // Read the already loaded source rather than canvas readback,
                // whose device-pixel coordinates differ on HiDPI screens.
                const image = context.createImageData(loadedSource.toString());
                const pixels = image.data;
                for (let index = 0; index < pixels.length; index += 4) {
                    const shade = 0.6 + 0.4 * (0.2126 * pixels[index]
                        + 0.7152 * pixels[index + 1] + 0.0722 * pixels[index + 2]) / 255;
                    pixels[index] = Math.round(root.color.r * 255 * shade);
                    pixels[index + 1] = Math.round(root.color.g * 255 * shade);
                    pixels[index + 2] = Math.round(root.color.b * 255 * shade);
                    pixels[index + 3] = Math.round(pixels[index + 3] * root.color.a);
                }
                context.drawImage(image, 0, 0, width, height);
            } else {
                context.drawImage(loadedSource, 0, 0, width, height);
                context.globalCompositeOperation = "source-in";
                context.fillStyle = root.color;
                context.fillRect(0, 0, width, height);
            }
        }
    }
}
