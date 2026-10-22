-- Sumi Desktop. Hyprland 0.55+ Lua configuration.
-- Edit this file to customize your desktop; updates preserve your edits.
-- Reference: https://wiki.hypr.land/Configuring/Start/
local controller = @CONTROLLER_LUA@
local config = @CONFIG_LUA@
local function sumi(arguments)
    return hl.dsp.exec_cmd(controller .. " " .. arguments)
end
local function include_if_present(path)
    local file = io.open(path, "r")
    if file then file:close(); dofile(path) end
end

-- Use the connected displays' preferred modes and automatic scaling/placement.
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("QT_QPA_PLATFORMTHEME", "qt6ct")
hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")
hl.on("hyprland.start", function() hl.exec_cmd(controller .. " session-start") end)
hl.on("hyprland.shutdown", function() hl.exec_cmd(controller .. " session-stop") end)

hl.config({
    general = {
        gaps_in = 5, gaps_out = 12, border_size = 2,
        layout = "dwindle", resize_on_border = true,
        col = { active_border = "rgba(93b9dcdd)", inactive_border = "rgba(53647577)" },
    },
    decoration = {
        rounding = 14, active_opacity = 0.85, inactive_opacity = 0.80,
        blur = { enabled = true, size = 6, passes = 3 },
        shadow = { enabled = true, range = 18, render_power = 3, color = "rgba(00000055)" },
    },
    input = {
        kb_layout = "us", follow_mouse = 1,
        touchpad = { natural_scroll = true, tap_to_click = true },
    },
    dwindle = { preserve_split = true },
    misc = { disable_hyprland_logo = true, force_default_wallpaper = 0 },
})
hl.layer_rule({ match = { namespace = "^sumi-.*$" }, blur = true, ignore_alpha = 0.1 })
hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })

-- Generated colors and motion are independently replaceable by Sumi themes.
include_if_present(config .. "/hypr/config/theme.lua")
include_if_present(config .. "/hypr/config/general.lua")
include_if_present(config .. "/sumi/generated/shortcuts.lua")
local palette_path = config .. "/sumi/generated/hyprland.lua"
local palette_file = io.open(palette_path, "r")
if palette_file then
    palette_file:close()
    local palette = dofile(palette_path)
    hl.config({
        general = { col = { active_border = { colors = { palette.accent_primary, palette.accent_secondary }, angle = 45 } } },
        decoration = { rounding = palette.window_rounding, shadow = { color = palette.bg_shadow } },
    })
end

-- Keyboard-first navigation. Super means the Windows/Command key.
hl.bind("SUPER + B", sumi("action browser"))
hl.bind("SUPER + A", sumi("ipc launcher toggle"))
hl.bind("SUPER + comma", sumi("ipc settings toggle"))
hl.bind("SUPER + Q", hl.dsp.window.close())
hl.bind("SUPER + F", hl.dsp.window.fullscreen({ action = "toggle" }))
hl.bind("SUPER + V", hl.dsp.window.float({ action = "toggle" }))
hl.bind("SUPER + P", hl.dsp.window.pseudo())
hl.bind("SUPER + J", hl.dsp.layout("togglesplit"))
hl.bind("SUPER + L", sumi("action lock"))
hl.bind("SUPER + SHIFT + Escape", sumi("ipc sumi toggle power"))
hl.bind("Print", sumi("action capture region"))
hl.bind("SHIFT + Print", sumi("action capture output"))
hl.bind("SUPER + Print", sumi("action record start"))
hl.bind("SUPER + SHIFT + Print", sumi("action record stop"))

for _, direction in ipairs({ "left", "right", "up", "down" }) do
    hl.bind("SUPER + " .. direction, hl.dsp.focus({ direction = direction }))
    hl.bind("SUPER + SHIFT + " .. direction, hl.dsp.window.move({ direction = direction }))
end
for workspace = 1, 10 do
    local key = workspace % 10
    hl.bind("SUPER + " .. key, hl.dsp.focus({ workspace = workspace }))
    hl.bind("SUPER + SHIFT + " .. key, hl.dsp.window.move({ workspace = workspace }))
end
hl.bind("SUPER + mouse_down", hl.dsp.focus({ workspace = "e+1" }))
hl.bind("SUPER + mouse_up", hl.dsp.focus({ workspace = "e-1" }))
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })
hl.bind("SUPER + S", hl.dsp.workspace.toggle_special("scratchpad"))
hl.bind("SUPER + ALT + S", hl.dsp.window.move({ workspace = "special:scratchpad" }))
hl.bind("SUPER + CTRL + left", hl.dsp.window.resize({ x = -40, y = 0, relative = true }), { repeating = true })
hl.bind("SUPER + CTRL + right", hl.dsp.window.resize({ x = 40, y = 0, relative = true }), { repeating = true })
hl.bind("SUPER + CTRL + up", hl.dsp.window.resize({ x = 0, y = -40, relative = true }), { repeating = true })
hl.bind("SUPER + CTRL + down", hl.dsp.window.resize({ x = 0, y = 40, relative = true }), { repeating = true })

-- A missing mixer, player, or laptop backlight makes only that key a no-op.
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), { locked = true, repeating = true })
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true })
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true })
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("brightnessctl -q -e4 -n2 set 5%+"), { locked = true, repeating = true })
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl -q -e4 -n2 set 5%-"), { locked = true, repeating = true })
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioPause", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), { locked = true })
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), { locked = true })

-- Optional personal settings load last. Sumi never writes this file.
include_if_present(config .. "/hypr/local.lua")
