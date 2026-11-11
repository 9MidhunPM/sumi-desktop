"""One-operation BlueZ pairing agent; JSON lines on stdio, no default-agent claim."""
from __future__ import annotations
import json
import re
import sys

ADDRESS = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")
AGENT_XML = '''<node><interface name="org.bluez.Agent1">
<method name="Release"/><method name="Cancel"/>
<method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
<method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
<method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
<method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
<method name="RequestAuthorization"><arg type="o" direction="in"/></method>
<method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
</interface></node>'''


def validate_reply(kind, value):
    if kind == "RequestPinCode":
        if not isinstance(value, str) or not 1 <= len(value) <= 16 or not value.isascii() or not value.isalnum():
            raise ValueError("Enter a PIN of 1–16 letters or numbers.")
        return "(s)", (value,)
    if kind == "RequestPasskey":
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,6}", value):
            raise ValueError("Enter a numeric passkey of up to six digits.")
        return "(u)", (int(value),)
    if value is not True:
        raise ValueError("Confirm that the passkey matches.")
    return "()", ()


def emit(**value):
    print(json.dumps(value), flush=True)


def main(address):
    if not ADDRESS.fullmatch(address):
        raise ValueError("Invalid Bluetooth device address")
    from gi.repository import Gio, GLib
    loop = GLib.MainLoop()
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    state = {"pending": None, "kind": "", "done": False, "prompt": 0}
    objects = bus.call_sync("org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects", None, GLib.VariantType.new("(a{oa{sa{sv}}})"), Gio.DBusCallFlags.NONE, 10000, None).unpack()[0]
    device = next((path for path, interfaces in objects.items() if interfaces.get("org.bluez.Device1", {}).get("Address", "").upper() == address.upper()), None)
    if not device:
        raise ValueError("Device is no longer available. Scan and try again.")
    def reject_pending():
        if state["pending"]:
            state["pending"].return_dbus_error("org.bluez.Error.Canceled", "Pairing cancelled")
            state["pending"] = None
    def finish(error=""):
        if state["done"]:
            return False
        state["done"] = True
        reject_pending()
        emit(type="done", error=error)
        loop.quit()
        return False
    def cancel(message="Pairing cancelled"):
        reject_pending()
        bus.call("org.bluez", device, "org.bluez.Device1", "CancelPairing", None, None, Gio.DBusCallFlags.NONE, 5000, None, None)
        return finish(message)
    def method(connection, sender, path, interface, name, parameters, invocation):
        args = parameters.unpack()
        if sender != bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "GetNameOwner", GLib.Variant("(s)", ("org.bluez",)), None, Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]:
            invocation.return_dbus_error("org.bluez.Error.Rejected", "Unknown caller")
            return
        if name in ("Cancel", "Release"):
            invocation.return_value(None)
            finish("Pairing cancelled by Bluetooth service")
            return
        if not args or args[0] != device or state["done"]:
            invocation.return_dbus_error("org.bluez.Error.Rejected", "Unexpected device")
            return
        state["prompt"] += 1
        value = args[1] if len(args) > 1 else ""
        if name in ("DisplayPinCode", "DisplayPasskey"):
            invocation.return_value(None)
        else:
            reject_pending()
            state["pending"] = invocation
            state["kind"] = name
        emit(type="prompt", kind=name, value=str(value).zfill(6) if isinstance(value, int) else value, entered=args[2] if len(args) > 2 else 0, prompt=state["prompt"])
    registration = bus.register_object("/org/sumi/PairingAgent", Gio.DBusNodeInfo.new_for_xml(AGENT_XML).interfaces[0], method, None, None)
    bus.call_sync("org.bluez", "/org/bluez", "org.bluez.AgentManager1", "RegisterAgent", GLib.Variant("(os)", ("/org/sumi/PairingAgent", "KeyboardDisplay")), None, Gio.DBusCallFlags.NONE, 10000, None)
    def receive(source, condition):
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            cancel()
            return False
        line = sys.stdin.readline(4097)
        if not line:
            cancel()
            return False
        try:
            data = json.loads(line)
            if data.get("command") == "cancel":
                cancel()
            elif data.get("command") == "respond" and state["pending"] and data.get("prompt") == state["prompt"]:
                signature, values = validate_reply(state["kind"], data.get("value"))
                state["pending"].return_value(GLib.Variant(signature, values))
                state["pending"] = None
                emit(type="waiting")
        except (ValueError, TypeError) as error:
            emit(type="validation", error=str(error))
        return not state["done"]
    GLib.io_add_watch(sys.stdin.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, receive)
    GLib.timeout_add_seconds(120, lambda: cancel("Pairing timed out. Try again."))
    def paired(connection, result):
        if state["done"]:
            return
        try:
            connection.call_finish(result)
        except GLib.Error as error:
            finish(error.message)
            return
        def connected(connection, result):
            try:
                connection.call_finish(result)
                finish()
            except GLib.Error as error:
                finish("Device paired; connection failed: " + error.message)
        bus.call("org.bluez", device, "org.bluez.Device1", "Connect", None, None, Gio.DBusCallFlags.NONE, 20000, None, connected)
    emit(type="waiting")
    bus.call("org.bluez", device, "org.bluez.Device1", "Pair", None, None, Gio.DBusCallFlags.NONE, 120000, None, paired)
    try:
        loop.run()
    finally:
        reject_pending()
        try:
            bus.call_sync("org.bluez", "/org/bluez", "org.bluez.AgentManager1", "UnregisterAgent", GLib.Variant("(o)", ("/org/sumi/PairingAgent",)), None, Gio.DBusCallFlags.NONE, 3000, None)
        except GLib.Error:
            pass
        bus.unregister_object(registration)


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) == 2 else "")
    except Exception as error:
        emit(type="done", error=str(error))
        sys.exit(1)
