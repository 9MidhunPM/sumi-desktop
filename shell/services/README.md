# Sumi QML services

Import `services` as `S`, and `config` as `C`. These singleton adapters use Quickshell 0.3.2's native event-driven services. They do not poll shell commands. All system-changing methods are inert with `SUMI_PREVIEW=1`; preview mode also avoids constructing the notification server.

| Singleton | Readable state | Methods |
| --- | --- | --- |
| `C.Theme` | `id`, `name`, `wallpaper`; all legacy color fields; `font`, `fontMono`, `fontSize`, `windowRounding`, `borderWidth`, `reducedMotion` | Theme follows `SUMI_STATE_DIR/theme.json` atomically; invalid JSON retains the last valid palette. |
| `C.Settings` | `barHiddenMode`, `reducedMotion`, `dnd`, `error` | `setValue(key, bool)`, `toggle(key)`, `save()` |
| `S.Audio` | `ready`, `sink`, `source`, `sinks`, `sources`, `volume`, `muted`, `sourceVolume`, `sourceMuted` | `setVolume(0..1)`, `changeVolume(delta)`, `toggleMute()`, `setSourceVolume(0..1)`, `toggleSourceMute()`, `selectSink(node)`, `selectSource(node)` |
| `S.Battery` | `available`, `percent` (0..100), `charging`, `onBattery`, `timeLabel`, `profile`, `performanceAvailable` | `setProfile("power-saver"\|"balanced"\|"performance")` |
| `S.Media` | `available`, `players`, `player`, `playing`, `title`, `artist`, `artUrl` | `select(player)`, `toggle()`, `next()`, `previous()`, `raise()`, `seek(seconds)` |
| `S.Network` | `devices`, `wifiDevice`, `wifiAvailable`, `wifiEnabled`, `networks`, `connected`, `name`, `captivePortal` | `toggleWifi()`, `setScanning(bool)`, `connect(network, psk)`, `disconnect(network)`, `forget(network)` |
| `S.Bluetooth` | `adapter`, `devices`, `available`, `enabled`, `scanning`, `connectedCount` | `toggle()`, `setScanning(bool)`, `connectDevice(device)`, `disconnectDevice(device)`, `pairDevice(device)`, `openManager()` |
| `S.Notifications` | `enabled`, `history`, `active`, `count`, `unread`, `dnd` | `dismiss(id)`, `clear()`, `invoke(id, actionIndex)`, `markRead()`, `toggleDnd()`; `received(entry)` signal |
| `S.Clock` | `date`, `time`, `dateLabel`, `monthLabel` | Native clock updates once per minute. |
| `S.Desktop` | `preview`, `controller`, `lastAction` | `action(command, args)`, `theme(id)`, `profile(id)` |

`S.Notifications.history` contains newest-first session snapshots, capped at 100: `{id,appName,summary,body,appIcon,time,critical,actions,popup}`. `active` contains snapshots eligible for a popup. Render all notification strings with `Text.PlainText`. Expired/closed notifications retain their snapshot while live action buttons are removed. Clear/dismiss calls the sending application's close handler. The profile controller must release the previous notification daemon before starting Sumi.

Network lists contain native `WifiNetwork` objects with `name`, `signalStrength`, `security`, `known`, `connected`, `state`, `stateChanging`, and `connectionFailed(reason)`. Pass a password only to `connect(network, psk)`; it goes directly to the native NetworkManager service rather than an argv or log. Enable discovery only while its panel is visible. Enterprise Wi-Fi setup can use the desktop network settings application.

Bluetooth discovery and existing-device connections are native. Pairing launches the interactive Bluetooth manager through `desktopctl action bluetooth-manager`, because Quickshell 0.3.2 does not provide a BlueZ pairing authentication agent. The manager handles passkeys and confirmation.

The controller path is `SUMI_DESKTOPCTL` or `bin/desktopctl` beside the shell directory. Actions always use an argv array. The installer must create the state directory (`$XDG_STATE_HOME/sumi` by default) before settings are written.

Run `python3 tests/qml/run-services-smoke.py` for offscreen checks. This tests defaults, loading/watching themes, invalid-theme recovery, settings persistence, notification sanitization/history/actions, and preview isolation. Sandbox tests cannot establish live DBus or PipeWire functionality; validate those in the host graphical session. Qt 6 lint is `/usr/lib/qt6/bin/qmllint`; upstream qmltypes currently emit warnings about opaque native models and singleton aliases, so the offscreen runtime test is also required.
