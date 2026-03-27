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


def get_active_wifi():
    """Get the name of the currently active wifi connection, if any."""
    result = subprocess.run(
        ["sudo", "nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"],
        capture_output=True, text=True,
    )
    for line in result.stdout.strip().splitlines():
        name, conn_type, device = line.split(":")
        if conn_type == "802-11-wireless" and name != AP_NAME:
            return name
    return None


def main():
    # Bring down active WiFi connection (don't delete it)
    active = get_active_wifi()
    if active:
        run(["sudo", "nmcli", "connection", "down", active])

    # Raise AP
    rc = run(["sudo", "nmcli", "connection", "up", AP_NAME])

    if rc != 0:
        print("Failed to raise AP", file=sys.stderr)
        sys.exit(1)

    MODE_FILE.write_text("AP\n")
    print("Switched to AP mode")


if __name__ == "__main__":
    main()
