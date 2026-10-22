# Customize Sumi

Prefer the shell's Appearance and widget editors for everyday changes. For compositor settings, keep personal changes in `"${XDG_CONFIG_HOME:-$HOME/.config}/hypr/local.lua"`. This optional Lua file loads after Sumi's defaults and is retained by updates. Edit generated theme or motion files only if you intend Sumi to replace those edits later.

## Keyboard, monitors, and windows

Create `hypr/local.lua` under your configuration directory. For example, a UK keyboard layout:

```lua
hl.config({ input = { kb_layout = "gb" } })
```

Reload the configuration from a terminal in Hyprland:

```sh
hyprctl reload
hyprctl configerrors
```

Fix any reported errors before logging out. Sumi uses Hyprland's Lua configuration; older `hyprland.conf` examples are not interchangeable with these Lua files. Consult the [Hyprland configuration guide](https://wiki.hypr.land/Configuring/Start/) for your installed release.

Displays default to their preferred mode with automatic placement and scaling. Inspect their actual names with `hyprctl monitors`. An explicit monitor rule in `local.lua` can override the automatic rule, for example:

```lua
hl.monitor({ output = "DP-1", mode = "preferred", position = "auto", scale = 1 })
```

Replace `DP-1` with an output you actually have. Avoid copying another machine's monitor names or resolution blindly.

## Shortcuts

`desktopctl shortcuts` lists the shared shell shortcuts. The complete standalone configuration also provides the window, workspace, media, and capture keys below.

| Key | Action |
| --- | --- |
| Super+Space | Command hub |
| Super+Shift+Space | Find files |
| Super+Enter / Super+E / Super+B | Terminal / files / browser |
| Super+N | Notification history |
| Super+comma | Quick settings |
| Super+Ctrl+V | Clipboard history |
| Super+Shift+T | Appearance |
| Super+/ | Shortcut reference |
| Super+T | Restart Sumi's shell |
| Hold Right Shift | Peek at the bar when its hidden mode is enabled |
| Super+Q | Close focused window |
| Super+F / Super+V | Toggle fullscreen / floating |
| Super+P / Super+J | Toggle pseudo-tiling / split direction |
| Super+Arrow | Focus a neighboring window |
| Super+Shift+Arrow | Move the focused window |
| Super+Ctrl+Arrow | Resize the focused window |
| Super+1–9 / Super+0 | Workspace 1–10 |
| Super+Shift+1–9 / Super+Shift+0 | Move window to workspace 1–10 |
| Super+mouse wheel | Previous/next workspace |
| Super+left/right mouse drag | Move/resize a window |
| Super+S | Show or hide the scratchpad workspace |
| Super+Alt+S | Move a window to the scratchpad |
| Super+L | Lock |
| Super+Shift+Escape | Power menu |
| Super+Shift+S or Print | Capture a region |
| Super+Ctrl+Shift+S | Capture a region and annotate in Satty |
| Shift+Print | Capture an output |
| Super+Print / Super+Shift+Print | Start/stop recording |

The hardware volume, mute, microphone, brightness, and media keys use their corresponding system tools. Missing hardware disables its controls or leaves that key without a device to change.

In the launcher, **Ctrl+Tab** and **Ctrl+Shift+Tab** change tabs; **Alt+1–5** chooses a tab directly. App and action ranking learns successful selections locally. File search looks at visible folders in your home, skips hidden and dependency folders, and has a time/result limit. It does not index file contents.

## Appearance, widgets, and defaults

Open Appearance from the command hub's Actions tab. Pick a wallpaper, apply a palette, or enter a six-digit accent color such as `#d9a66a`. **Add wallpaper** copies a local image into your private Sumi library. Your imported images are not part of the public repository.

Equivalent commands are:

```sh
desktopctl theme list
desktopctl theme use sumi-ember
desktopctl theme accent sumi-ember '#d9a66a'
desktopctl theme import '/absolute/path/to/My Wallpaper.png'
```

Import prints the new theme's identifier; select it in Appearance or pass that identifier to `desktopctl theme use`. The supplied wallpapers are Ember, Tide, and Ink. Palette presets share these distributable images.

Use **Edit widgets** in Appearance to choose content and layout. Widgets stay on the desktop layer behind application windows. The desktop music widget follows Spotify through MPRIS; Spotify is optional and is not installed by this official-repository installer. The bar and Now playing panel support other MPRIS players. Default widget placement uses the first output; an advanced `sumi-shell.service` user override can set `Environment=SUMI_WIDGET_SCREEN=DP-1` to select another output, followed by `desktopctl restart`.

The browser action uses your default HTTPS handler, with Firefox as a fallback. File opening uses `xdg-open`. Kitty is the supplied terminal. The optional project action honors `VISUAL` as a literal argument list and otherwise opens the folder in your default file manager.

Screenshots go under the XDG Pictures directory's `Screenshots` folder; recordings use the XDG Videos directory's `Recordings` folder. Localized directories and spaces are supported. Annotation uses a private temporary handoff to Satty.

## Files and updates

| Purpose | Default location |
| --- | --- |
| Installed runtime | `~/.local/share/sumi/runtime` |
| Personal wallpaper library | `~/.local/share/sumi` |
| Hyprland configuration | `~/.config/hypr` |
| Personal compositor overrides | `~/.config/hypr/local.lua` |
| User services | `~/.config/systemd/user` |
| Sumi private state and backups | `~/.local/state/sumi` |
| Controller launcher | `~/.local/bin/desktopctl` |

Sumi respects `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`, and `XDG_CACHE_HOME`. Set custom values consistently in the login environment before installation and subsequent use. The installer prints the resolved paths and accepts spaces in them.

Updates replace managed defaults after taking a backup. They retain `local.lua` and unmanaged Hyprland files, but direct edits to managed files may be overwritten. Keep your own changes in the personal override and review [update and rollback](recovery.md#update-and-rollback) before updating.
