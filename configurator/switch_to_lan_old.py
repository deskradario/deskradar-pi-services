import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

AP_NAME = os.getenv("AP_NAME", "deskradarAP")
DEVICE_TIMEOUT_SECS = int(os.getenv("DEVICE_TIMEOUT_SECS", "60"))


def run(cmd):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode


def wait_for_device():
    """Poll for a readable CIRCUITPY mount and return its path."""
    print("Waiting for CIRCUITPY device...")

    def readable_circuitpy_mount():
        media_root = Path("/media") / os.getenv("USER", "")
        if not media_root.exists():
            return None

        candidates = sorted(media_root.glob("CIRCUITPY*"))

        for path in candidates:
            try:
                if not path.is_dir():
                    continue

                # Must be listable/readable
                next(path.iterdir(), None)

                # Optional extra guard: CIRCUITPY root should usually contain boot_out.txt
                # Remove this check if you do not want it.
                if not (path / "boot_out.txt").exists():
                    continue

                return str(path)

            except (OSError, PermissionError):
                # Stale/unreadable mount
                continue

        return None

    elapsed = 0
    while elapsed < DEVICE_TIMEOUT_SECS:
        device_path = readable_circuitpy_mount()
        if device_path:
            print(f"CIRCUITPY found after {elapsed}s at {device_path}")
            return Path(device_path)

        time.sleep(1)
        elapsed += 1

    print(f"No readable CIRCUITPY device found after {DEVICE_TIMEOUT_SECS}s.", file=sys.stderr)
    sys.exit(1)


def get_nm_credentials(profile_name):
    """Extract SSID and PSK from a saved NetworkManager profile."""
    ssid_result = subprocess.run(
        ["sudo", "nmcli", "-s", "-g", "802-11-wireless.ssid",
         "connection", "show", profile_name],
        capture_output=True, text=True,
    )
    psk_result = subprocess.run(
        ["sudo", "nmcli", "-s", "-g", "802-11-wireless-security.psk",
         "connection", "show", profile_name],
        capture_output=True, text=True,
    )
    return ssid_result.stdout.strip(), psk_result.stdout.strip()


MAX_RETRIES = 3


def bring_up(connection, retries=MAX_RETRIES):
    """Try to bring up a connection, retrying on failure."""
    for attempt in range(1, retries + 1):
        rc = run(["sudo", "nmcli", "connection", "up", connection])
        if rc == 0:
            return True
        print(f"Attempt {attempt}/{retries} failed for {connection}")
    return False


def connect_wifi(ssid, password, retries=MAX_RETRIES):
    """Try to connect to a new wifi network, retrying on failure."""
    for attempt in range(1, retries + 1):
        rc = run([
            "sudo", "nmcli", "device", "wifi", "connect", ssid,
            "password", password,
        ])
        if rc == 0:
            return True
        print(f"Attempt {attempt}/{retries} failed for {ssid}")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", help="Existing connection profile name to activate")
    parser.add_argument("--ssid", help="SSID for a new connection")
    parser.add_argument("--password", help="Password for a new connection")
    args = parser.parse_args()

    if not args.name and not (args.ssid and args.password):
        parser.error("Provide either --name or both --ssid and --password")

    mount = wait_for_device()

    if args.name:
        ssid, password = get_nm_credentials(args.name)
    else:
        ssid, password = args.ssid, args.password

    run(["sudo", "nmcli", "connection", "down", AP_NAME])

    if args.name:
        connected = bring_up(args.name)
    else:
        connected = connect_wifi(ssid, password)

    if not connected:
        print("WiFi connection failed, re-raising AP", file=sys.stderr)
        if bring_up(AP_NAME):
            print("AP restored")
        else:
            print("CRITICAL: failed to connect to WiFi and failed to restore AP", file=sys.stderr)
        sys.exit(1)

    wifi_file = mount / "wifi.txt"
    wifi_file.write_text(f"{ssid}\n{password}\n")
    print(f"Wrote wifi credentials to {wifi_file}")

    print("Switched to LAN mode, rebooting.")
    run(["sudo", "reboot"])


if __name__ == "__main__":
    main()
