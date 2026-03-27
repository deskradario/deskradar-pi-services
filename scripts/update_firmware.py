#!/usr/bin/env python3
import sys
import subprocess
import os
import time

SSID = sys.argv[1]
PW = sys.argv[2]
REPO_DIR = "/home/user/adsb"
AP_NAME = "piAP"

def run(cmd, timeout=30):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        print(f"FAILED: {cmd}\nstderr: {result.stderr.strip()}")
        raise RuntimeError(result.stderr)
    return result.stdout.strip()

def reboot():
    print("Failure detected — rebooting.")
    subprocess.run("sudo reboot", shell=True)
    sys.exit(1)

try:
    print("Dropping AP...")
    run(f"sudo nmcli connection down {AP_NAME}")

    print(f"Connecting to {SSID}...")
    run(f"sudo nmcli device wifi connect '{SSID}' password '{PW}'", timeout=30)

    # Give the interface a moment to get an IP
    time.sleep(5)

    print("Running git pull...")
    run(f"git -C {REPO_DIR} pull", timeout=60)

    print("Disconnecting WiFi...")
    run("sudo nmcli device disconnect wlan0")

    print("Removing saved connection profile...")
    run(f"sudo nmcli connection delete '{SSID}'")

    print("Re-enabling AP...")
    run(f"sudo nmcli connection up {AP_NAME}")

    print("Done.")

except Exception as e:
    print(f"Error: {e}")
    reboot()