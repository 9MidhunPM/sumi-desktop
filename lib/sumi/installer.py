"""Public facade for setup and desktopctl installation lifecycle commands."""
from .install.workflow import main


def uninstall(*, home=None, dry_run=False):
    from .install.lifecycle import uninstall as operation
    return operation(home=home, dry_run=dry_run)


def rollback(*, home=None, dry_run=False):
    from .install.lifecycle import rollback as operation
    return operation(home=home, dry_run=dry_run)


def restore_previous(*, home=None, dry_run=False):
    from .install.lifecycle import restore_previous as operation
    return operation(home=home, dry_run=dry_run)


def diagnostics(*, home=None):
    from .install.diagnostics import diagnostics as operation
    return operation(home=home)


def recovery_available(*, home=None):
    from .install.lifecycle import recovery_available as operation
    return operation(home=home)


def recover_pending(*, home=None, dry_run=False):
    from .install import ownership
    from .install.paths import Layout
    layout = Layout.from_environment(home)
    if dry_run:
        return {"dry_run": True, "pending": layout.journal.exists()}
    with ownership.locked(layout):
        return {"recovered": ownership.recover_pending(layout)}


if __name__ == "__main__":
    raise SystemExit(main())
