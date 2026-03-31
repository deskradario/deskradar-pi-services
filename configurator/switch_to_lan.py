import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

AP_NAME = os.getenv("AP_NAME", "deskradarAP")
WIFI_IFNAME = os.getenv("WIFI_IFNAME", "wlan0")
DEVICE_TIMEOUT_SECS = int(os.getenv("DEVICE_TIMEOUT_SECS", "60"))
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


def wait_for_device():
    """Poll for a readable CIRCUITPY mount and return its path."""
    print("Waiting for CIRCUITPY device...")

    media_root = Path("/media") / os.getenv("USER", "")
    deadline = time.time() + DEVICE_TIMEOUT_SECS

    while time.time() < deadline:
        if media_root.exists():
            candidates = sorted(media_root.glob("CIRCUITPY*"))

            for path in candidates:
                try:
                    if not path.is_dir():
                        continue

                    # Must be readable/listable
                    list(path.iterdir())

                    # Stronger guard for a real CircuitPython mount
                    if not (path / "boot_out.txt").exists():
                        continue

                    print(f"CIRCUITPY found at {path}")
                    return path

                except (OSError, PermissionError):
                    continue

        time.sleep(1)

    print(
        f"No readable CIRCUITPY device found after {DEVICE_TIMEOUT_SECS}s.",
        file=sys.stderr,
    )
    sys.exit(1)


def get_connection_field(profile_name, field):
    result = nmcli("-g", field, "connection", "show", profile_name)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_nm_credentials(profile_name):
    """Extract SSID and PSK from a saved NetworkManager profile."""
    ssid = get_connection_field(profile_name, "802-11-wireless.ssid")
    psk = get_connection_field(profile_name, "802-11-wireless-security.psk")
    return ssid, psk


def get_active_wifi_connection():
    """Return the active connection name on WIFI_IFNAME, or None."""
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

    for line in result.stdout.splitlines():
        parts = line.strip().split(":")
        if len(parts) < 4:
            continue
        name, device, conn_type, state = parts[:4]
        if device == WIFI_IFNAME and conn_type == "wifi" and state == "activated":
            return name

    return None


def get_wifi_state():
    result = nmcli("-t", "-f", "GENERAL.STATE", "device", "show", WIFI_IFNAME)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def is_wifi_connected(expected_ssid=None):
    active_conn = get_active_wifi_connection()
    if not active_conn:
        return False

    if not expected_ssid:
        return True

    active_ssid = get_connection_field(active_conn, "802-11-wireless.ssid")
    return active_ssid == expected_ssid


def wait_for_wifi_connection(expected_ssid=None, timeout=CONNECT_WAIT_SECS):
    deadline = time.time() + timeout

    while time.time() < deadline:
        if is_wifi_connected(expected_ssid):
            return True
        time.sleep(1)

    return False


def connection_exists(name):
    result = nmcli("-g", "NAME", "connection", "show", name)
    return result.returncode == 0 and bool(result.stdout.strip())


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


def disconnect_ap_if_present():
    if connection_exists(AP_NAME):
        nmcli("connection", "down", AP_NAME)
        time.sleep(NM_SETTLE_SECS)


def restore_ap():
    print("Restoring AP...")
    try:
        set_autoconnect(AP_NAME, True, priority=999)
    except Exception as e:
        print(f"Failed to re-enable AP autoconnect: {e}", file=sys.stderr)

    result = nmcli("connection", "up", AP_NAME)
    if result.returncode == 0:
        print("AP restored")
        return True

    print("Failed to restore AP", file=sys.stderr)
    return False


def bring_up_saved_connection(connection_name, expected_ssid=None, retries=MAX_RETRIES):
    for attempt in range(1, retries + 1):
        print(f"Bringing up saved connection '{connection_name}' ({attempt}/{retries})")

        result = nmcli("connection", "up", connection_name)
        if result.returncode == 0:
            if wait_for_wifi_connection(expected_ssid=expected_ssid):
                return True

        print(f"Attempt {attempt}/{retries} failed for connection '{connection_name}'")
        time.sleep(NM_SETTLE_SECS)

    return False


def connect_new_wifi(ssid, password, retries=MAX_RETRIES):
    """
    Connect to a new Wi-Fi network and let NetworkManager create/save the profile.
    Returns the saved connection name on success, else None.
    """
    for attempt in range(1, retries + 1):
        print(f"Connecting to SSID '{ssid}' ({attempt}/{retries})")

        result = nmcli(
            "device",
            "wifi",
            "connect",
            ssid,
            "password",
            password,
            "ifname",
            WIFI_IFNAME,
        )

        if result.returncode == 0 and wait_for_wifi_connection(expected_ssid=ssid):
            active_conn = get_active_wifi_connection()
            if active_conn:
                return active_conn

        print(f"Attempt {attempt}/{retries} failed for SSID '{ssid}'")
        time.sleep(NM_SETTLE_SECS)

    return None


def write_wifi_file(mount, ssid, password):
    wifi_file = mount / "wifi.txt"
    wifi_file.write_text(f"{ssid}\n{password}\n")
    print(f"Wrote wifi credentials to {wifi_file}")


def persist_client_mode(client_connection_name):
    """
    Make client Wi-Fi persistent across reboot and prevent the AP from coming back.
    """
    set_autoconnect(client_connection_name, True, priority=100)
    if connection_exists(AP_NAME):
        set_autoconnect(AP_NAME, False, priority=-999)

    print(f"Persisted client mode with '{client_connection_name}'")
    if connection_exists(AP_NAME):
        print(f"Disabled AP autoconnect for '{AP_NAME}'")


def validate_args(args):
    if not args.name and not (args.ssid and args.password):
        raise SystemExit("Provide either --name or both --ssid and --password")

    if args.name and (args.ssid or args.password):
        raise SystemExit("Use either --name or --ssid/--password, not both")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Existing connection profile name to activate")
    parser.add_argument("--ssid", help="SSID for a new connection")
    parser.add_argument("--password", help="Password for a new connection")
    args = parser.parse_args()

    validate_args(args)

    mount = wait_for_device()

    if args.name:
        client_connection_name = args.name
        ssid, password = get_nm_credentials(client_connection_name)
        if not ssid:
            print(
                f"Could not read SSID from saved profile '{client_connection_name}'",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        ssid, password = args.ssid, args.password
        client_connection_name = None

    disconnect_ap_if_present()

    try:
        if args.name:
            connected = bring_up_saved_connection(
                client_connection_name,
                expected_ssid=ssid,
            )
        else:
            client_connection_name = connect_new_wifi(ssid, password)
            connected = client_connection_name is not None

        if not connected:
            raise RuntimeError("Wi-Fi connection failed")

        persist_client_mode(client_connection_name)
        write_wifi_file(mount, ssid, password)
        print("Switched to Wi-Fi client mode")

    except Exception as e:
        print(str(e), file=sys.stderr)
        print("Wi-Fi connection failed, attempting to restore AP...", file=sys.stderr)
        if not restore_ap():
            print(
                "CRITICAL: failed to connect to Wi-Fi and failed to restore AP",
                file=sys.stderr,
            )
        sys.exit(1)


if __name__ == "__main__":
    main()