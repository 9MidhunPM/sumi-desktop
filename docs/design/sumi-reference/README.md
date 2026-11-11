# Sumi desktop design reference

Open [the offline reference](../sumi-desktop-reference.html) in a browser. It
is a design prototype with sample devices, playback, conversations and files;
its controls do not operate the desktop. It depicts an earlier layout and is
not a pixel-exact representation of the current native shell. Optional
integrations in the prototype may not be configured on your machine.

The source files are in this directory. Run `python3 build.py` here to rebuild
the self-contained HTML from the source and Sumi's original, distributable
wallpaper assets. Clicking the clock opens Controls; Ctrl+K opens Search;
Alt+Left returns; Escape closes the workspace. The All views picker explores
example routes and states.

The prototype is separate from native compositor testing. Actual hardware,
focus, screen scaling, capture, and service behavior require native validation.
