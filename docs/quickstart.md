# Install and start Sumi

Sumi adds a Hyprland desktop to an **already installed Arch Linux x86_64 system**. You need a normal user account with working sudo, internet access, and working graphics drivers. The installer does not partition disks, install GPU drivers, replace your display manager, or configure disk encryption. Arch derivatives are outside this release's supported installer target.

## 1. Prepare Arch

Open a terminal, or log in at a text console using **Ctrl+Alt+F3**. Update the system and install the small tools needed to start setup:

```sh
sudo pacman -Syu --needed python git sudo
git clone https://github.com/9MidhunPM/sumi-desktop.git
cd sumi-desktop
```

Run the installer as your normal user. It requests sudo only for package and system-service operations.

## 2. Preview, then install

```sh
./install.sh --dry-run
./install.sh
```

The preview prints destinations, the official Arch package command, service actions, and prerequisite problems. It does not create directories, write configuration or private state, install packages, or start services. A preview can report a missing prerequisite; resolve it before installing.

Read the setup summary. The package operation is a full `pacman -Syu --needed` upgrade using official `core` and `extra` repositories, and pacman asks for confirmation separately.

If Sumi finds any existing destination, type the exact choice **Back up and use Sumi** to allow replacement. With no existing destinations, type **Install Sumi**. Pressing Enter or entering any other answer exits without making changes. Existing Hyprland configuration is backed up as a directory before Sumi replaces it.

Setup copies its runtime into your XDG data directory, independent of this checkout. Keep the checkout to fetch future updates. The success output prints the installed controller and backup locations. The currently running graphical session stays active; finish by logging out.

## 3. Start your first session

Choose **Hyprland** in your existing login screen and sign in. If you use a text console instead of a display manager, log in as your normal user and run:

```sh
Hyprland
```

The default keyboard layout is US. Read [customization](customization.md) before first login if you need another layout. Do not start a second Hyprland session inside your existing desktop terminal.

Sumi starts its shell, wallpaper, authentication agent, clipboard watchers, and idle service with the graphical session. Networking uses NetworkManager when available. A detected competing network manager is retained; follow the installer's migration note if you want Sumi's network controls.

## 4. Try the essentials

| Key | Action |
| --- | --- |
| Super+Space | Open the command hub |
| Super+Enter | Open Kitty |
| Super+E | Open your file manager |
| Super+B | Open your default web browser |
| Super+Q | Close the focused window |
| Super+1–9 or Super+0 | Go to workspace 1–10 |
| Super+Shift+1–9 or Super+Shift+0 | Move a window to that workspace |
| Super+comma | Open quick settings |
| Super+L | Lock the session |
| Super+/ | Show shortcut help |

**Super** means the Windows or Command key. In the command hub, type an application name, use the arrow keys to select it, and press Enter. Escape closes a panel. Tab moves between controls. Use the Actions tab to open Appearance, desktop widgets, capture tools, and power controls.

Appearance offers three original wallpapers, reusable color palettes, and adaptive, expressive, or reduced motion. Start with the default, then choose a wallpaper and press **Apply theme**. The widget editor lets you choose the visible clock, optional Spotify media, priorities, and deadline content.

The shell stores launcher learning, notification history, clipboard history, and widget content locally. You can reset launcher learning in the launcher, pause or clear clipboard history, and enable Do Not Disturb from quick settings. Uninstall intentionally preserves this personal data.

Check the installation inside your new session:

```sh
desktopctl doctor --check
```

If the command is missing from a text console's PATH, use `"$HOME/.local/bin/desktopctl"`. If startup fails, [recovery](recovery.md) explains how to inspect the installation from a text console.
