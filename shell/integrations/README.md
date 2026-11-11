# Optional Thursday companion

Sumi works without Thursday. With no configuration, this adapter launches no
helper and opens no audio device. The Thursday tab shows its unavailable state.

To opt in, install and configure your own compatible Thursday checkout separately,
including its Python virtual environment and local service configuration.

For the installed systemd user service, run:

```sh
systemctl --user edit sumi-shell.service
```

Add a service override with your absolute checkout path:

```ini
[Service]
Environment="SUMI_THURSDAY_ROOT=/path/to/Thursday"
# Optional when the checkout does not use .venv/bin/python:
Environment="SUMI_THURSDAY_PYTHON=/path/to/python"
```

Save the override, then reload and restart the shell:

```sh
systemctl --user daemon-reload
systemctl --user restart sumi-shell.service
```

For a direct foreground session, export the variables in the same terminal before
starting Quickshell:

```sh
export SUMI_THURSDAY_ROOT=/path/to/Thursday
# Optional when the checkout does not use .venv/bin/python:
export SUMI_THURSDAY_PYTHON=/path/to/python
```

A terminal export alone does not change the environment of an already installed
systemd service. Restart the appropriate session after configuration changes.
A configured session starts one
`python -m assistant.native_client` process, with the checkout as its working
directory. That external client owns its authentication and private downloads;
Sumi does not read or publish its credentials. A failed client stays disconnected
until you reopen Thursday or explicitly run `desktopctl ipc thursday connect`.
Conversation history and voice preferences stay inside the island. The optional
explicit `open_web` protocol action is retained for clients that need it.

The island receives JSON-lines events for streamed replies, task state, voice
state, and approval requests. Only clicking an approval action sends a decision,
and it targets the first pending request. No action is automatically approved.
The adapter creates no duplicate assistant window or HUD.

Speech uses helper-provided local audio files and measured `audio_levels` with
`interval_ms` timestamps. Audio devices load only when speech arrives. The trace
requires active playback and the client's observed audible output; silent,
missing, or exhausted measurements stay flat. This does not measure physical
speaker or headphone output. Voice playback requires Qt 6 Multimedia.

The adapter and envelope reader are Sumi-owned. The bundled speech visual is a
standalone rendering component; no backend, credentials or private data are
included. The independently installed application remains separate.
