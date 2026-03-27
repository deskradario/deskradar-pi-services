import os
import subprocess
import sys

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


MAX_RETRIES = 3


def bring_up(connection, retries=MAX_RETRIES):
    """Try to bring up a connection, retrying on failure."""
    for attempt in range(1, retries + 1):
        rc = run(["sudo", "nmcli", "connection", "up", connection])
        if rc == 0:
            return True
        print(f"Attempt {attempt}/{retries} failed for {connection}")
    return False


def main():
    active = get_active_wifi()
    if active:
        run(["sudo", "nmcli", "connection", "down", active])

    if bring_up(AP_NAME):
        print("Switched to AP mode")
        return

    # AP failed — restore the LAN connection we just tore down
    print("Failed to raise AP, falling back to previous connection", file=sys.stderr)
    if active and bring_up(active):
        print(f"Restored LAN connection: {active}", file=sys.stderr)
        sys.exit(1)

    print("CRITICAL: failed to raise AP and failed to restore LAN", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
