import os
import subprocess
import sys
import time

from dotenv import load_dotenv

load_dotenv()

AP_NAME = os.getenv("AP_NAME", "deskradarAP")
WIFI_IFNAME = os.getenv("WIFI_IFNAME", "wlan0")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
CONNECT_WAIT_SECS = int(os.getenv("CONNECT_WAIT_SECS", "15"))
NM_SETTLE_SECS = float(os.getenv("NM_SETTLE_SECS", "2"))


def run(cmd, check=False):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return result


def nmcli(*args, check=False):
    return run(["sudo", "nmcli", *args], check=check)


def connection_exists(name):
    result = nmcli("-g", "NAME", "connection", "show", name)
    return result.returncode == 0 and bool(result.stdout.strip())


def get_connection_field(profile_name, field):
    result = nmcli("-g", field, "connection", "show", profile_name)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_active_wifi():
    """Get the name of the currently active non-AP wifi connection, if any."""
    result = nmcli(
        "-t",
        "-f",
        "NAME,DEVICE,TYPE,STATE",
        "connection",
        "show",
        "--active",
    )
    if result.returncode != 0:
        return None

    for line in result.stdout.strip().splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue

        name, device, conn_type, state = parts[:4]
        if (
            device == WIFI_IFNAME
            and conn_type == "wifi"
            and state == "activated"
            and name != AP_NAME
        ):
            return name

    return None


def is_connection_active(connection_name):
    result = nmcli(
        "-t",
        "-f",
        "NAME,DEVICE,TYPE,STATE",
        "connection",
        "show",
        "--active",
    )
    if result.returncode != 0:
        return False

    for line in result.stdout.strip().splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue

        name, device, conn_type, state = parts[:4]
        if (
            name == connection_name
            and device == WIFI_IFNAME
            and conn_type == "wifi"
            and state == "activated"
        ):
            return True

    return False


def wait_for_connection(connection_name, timeout=CONNECT_WAIT_SECS):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_connection_active(connection_name):
            return True
        time.sleep(1)
    return False


def set_autoconnect(name, enabled, priority=None):
    value = "yes" if enabled else "no"
    nmcli("connection", "modify", name, "connection.autoconnect", value, check=True)

    if priority is not None:
        nmcli(
            "connection",
            "modify",
            name,
            "connection.autoconnect-priority",
            str(priority),
            check=True,
        )


def bring_up(connection, retries=MAX_RETRIES, wait=True):
    """Try to bring up a connection, retrying on failure."""
    for attempt in range(1, retries + 1):
        result = nmcli("connection", "up", connection)
        if result.returncode == 0:
            if not wait or wait_for_connection(connection):
                return True

        print(f"Attempt {attempt}/{retries} failed for {connection}")
        time.sleep(NM_SETTLE_SECS)

    return False


def bring_down(connection):
    result = nmcli("connection", "down", connection)
    time.sleep(NM_SETTLE_SECS)
    return result.returncode == 0


def persist_ap_mode(previous_connection=None):
    set_autoconnect(AP_NAME, True, priority=999)

    if previous_connection and connection_exists(previous_connection):
        set_autoconnect(previous_connection, False, priority=-999)

    print(f"Persisted AP mode with '{AP_NAME}'")
    if previous_connection and connection_exists(previous_connection):
        print(f"Disabled client autoconnect for '{previous_connection}'")


def restore_client_mode(previous_connection):
    print("Restoring previous Wi-Fi connection...")

    try:
        if connection_exists(AP_NAME):
            set_autoconnect(AP_NAME, False, priority=-999)
    except Exception as e:
        print(f"Failed to disable AP autoconnect: {e}", file=sys.stderr)

    if previous_connection and connection_exists(previous_connection):
        try:
            set_autoconnect(previous_connection, True, priority=100)
        except Exception as e:
            print(f"Failed to re-enable client autoconnect: {e}", file=sys.stderr)

        if bring_up(previous_connection):
            print(f"Restored Wi-Fi connection: {previous_connection}", file=sys.stderr)
            return True

    print("Failed to restore previous Wi-Fi connection", file=sys.stderr)
    return False


def main():
    if not connection_exists(AP_NAME):
        print(f"AP connection '{AP_NAME}' does not exist", file=sys.stderr)
        sys.exit(1)

    active = get_active_wifi()

    if active:
        bring_down(active)

    try:
        if bring_up(AP_NAME):
            persist_ap_mode(previous_connection=active)
            print("Switched to AP mode")
            return

        raise RuntimeError("Failed to raise AP")

    except Exception as e:
        print(str(e), file=sys.stderr)
        print("Failed to raise AP, falling back to previous connection", file=sys.stderr)

        if active and restore_client_mode(active):
            sys.exit(1)

        print("CRITICAL: failed to raise AP and failed to restore Wi-Fi", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()