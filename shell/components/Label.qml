import QtQuick
import "../config"

Text {
    color: Theme.textMain
    font.family: Theme.font
    font.pixelSize: Theme.fontSize
    textFormat: Text.PlainText
    elide: Text.ElideRight
    verticalAlignment: Text.AlignVCenter
    renderType: Text.NativeRendering
}
