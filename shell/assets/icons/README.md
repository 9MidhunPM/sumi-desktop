# Sumi interface icons

Original, manually drawn interface SVGs on a 24 × 24 viewbox, with 1.8-unit rounded strokes. No icon font, system icon theme, or network resource is required. White strokes serve as the alpha mask; `components/Icon.qml` supplies the theme color.

`arch.svg` preserves the Arch Linux mark from the installed Arch `filesystem` package's `/usr/share/pixmaps/archlinux-logo.svg`, normalized to the same viewbox and a single-color mask. Copyright Arch Linux Contributors; its accompanying license is retained in `LICENSE.arch`. Arch Linux owns its [name and mark](https://archlinux.org/art/).

`chatgpt.svg` is the OpenAI knot mark from [Simple Icons v14.15.0](https://github.com/simple-icons/simple-icons/blob/14.15.0/icons/openai.svg), distributed under [CC0 1.0](https://github.com/simple-icons/simple-icons/blob/14.15.0/LICENSE.md). Its original 24 × 24 path is unchanged; the white fill lets the component apply the current palette. It identifies the Codex agents button.

Use `Icon { name: "wifi"; size: 20; color: Theme.textMain }` or `ActionButton { iconName: "wifi"; text: "Network" }`. Aliases: `apps` → `grid`, `assistant` → `sparkles`, `codex` → `chatgpt`. An empty name draws nothing; an unknown name draws `circle-help`.

The small Canvas.Image texture is repainted only when its asset, size, or color changes. Its source-in tint also works with Qt's software renderer, without shader effects or Qt5 compatibility modules.
