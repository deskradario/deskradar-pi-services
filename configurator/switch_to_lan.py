import argparse
import glob
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

AP_NAME = os.getenv("AP_NAME", "piAP")
MODE_FILE = Path("/etc/deskradar-configurator/mode.txt")


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


def main():
    parser = argparse.ArgumentParser()
    # Either reconnect to a saved profile or create a new one
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

    # Bring down AP (don't delete it)
    run(["sudo", "nmcli", "connection", "down", AP_NAME])

    if args.name:
        # Activate an existing saved connection
        rc = run(["nmcli", "connection", "up", args.name])
    else:
        rc = run([
            "nmcli", "device", "wifi", "connect", ssid,
            "password", password,
        ])

    if rc != 0:
        print("WiFi connection failed, re-raising AP")
        run(["sudo", "nmcli", "connection", "up", AP_NAME])
        sys.exit(1)

    wifi_file = mount / "wifi.txt"
    wifi_file.write_text(f"{ssid}\n{password}\n")
    print(f"Wrote wifi credentials to {wifi_file}")

    MODE_FILE.write_text("LAN\n")
    print("Switched to LAN mode")


if __name__ == "__main__":
    main()
