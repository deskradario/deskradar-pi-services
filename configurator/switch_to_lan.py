import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

AP_NAME = os.getenv("AP_NAME", "deskradarAP")


def run(cmd):
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode


def find_circuitpython_mount():
    mounts = glob.glob("/media/*/CIRCUITPYTHON*")
    if not mounts:
        return None
    return Path(mounts[0])


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
            "nmcli", "device", "wifi", "connect", ssid,
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

    mount = find_circuitpython_mount()
    if mount is None:
        print("No CIRCUITPYTHON mount found, aborting", file=sys.stderr)
        sys.exit(1)

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

    print("Switched to LAN mode")


if __name__ == "__main__":
    main()
