# Security

Sumi runs as the logged-in desktop user. Its installer uses sudo for declared Arch package and system-service operations; the shell and controller should never run as root.

For the initial release, fixes target the latest published version. Update your Arch packages and Sumi before reporting an issue that might already be fixed. Hardware, GPU drivers, display managers, disk encryption, and the operating system's PAM policy are outside Sumi's configuration scope.

## Report a vulnerability privately

Use [GitHub's private vulnerability reporting page](https://github.com/9MidhunPM/sumi-desktop/security/advisories/new) if it is available. If GitHub does not offer private reporting for this repository, open a minimal issue asking the maintainer for a private reporting channel. Do not put exploit details, credentials, notification bodies, clipboard content, or personal configuration in that public issue.

Include the affected commit or release, relevant package versions, a minimal reproduction using synthetic data, expected behavior, and the security impact. State whether the problem requires a local account, a malicious file, a desktop entry, or a service response. Redact private paths and account identifiers from logs. There is no guaranteed response time or bounty program.

## Local data and trust boundaries

Launcher learning, notification history, clipboard history, widgets, imported wallpapers, and recovery snapshots are local user data. Backups can contain configuration secrets. Keep their filesystem permissions private and do not attach complete state directories to an issue. Uninstall preserves this data deliberately.

Opening applications and files trusts the user's installed desktop entries and chosen applications. Adding a wallpaper treats it as local image input. Clipboard history can retain sensitive text; pause or clear it when appropriate. A lock-screen request and a verified locked session are different states, so suspend integration must retain its lock-notification inhibitor.

Changes to command execution, path validation, symlink handling, backup ownership, service environment propagation, session locking, or recovery need focused tests and explicit review. A dry run must not create state or run package/service mutations.
