#!/usr/bin/env python3
"""Boot script that reads IP from CIRCUITPY USB device and writes it to deskradar config."""

import json
import ipaddress
import os
import syslog
import time
import requests

# wait for shit to be alive
time.sleep(10)

MEDIA_PATH = "/media/deskradar"
CONFIG_DIR = "/etc/deskradar"
IP_FILE_NAME = "ip.txt"
DEVICE_TIMEOUT_SECS = 5
IP_FILE_TIMEOUT_SECS = 5
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CONFIG_EXAMPLE_PATH = "/opt/deskradar/config-example.json"
MATRIX_URL_CONFIG_KEY = "MATRIX_HTTP_URL"
BYPASS = os.environ.get("DESKRADAR_BYPASS_BOOT", "")
LCD_URL = "http://127.0.0.1:8010/display"


def lcd_log(line1, line2=""):
    """Send a status message to the LCD. Non-fatal on failure."""
    try:
        requests.post(LCD_URL, json={"line1": line1, "line2": line2}, timeout=5)
    except Exception:
        pass


def journal_log(msg):
    syslog.syslog(syslog.LOG_INFO, f"[boot_check] {msg}")


def journal_log_error(msg):
    syslog.syslog(syslog.LOG_ERR, f"[boot_check] {msg}")


def detect_target_volume():
    """Return the mount path of the first device with CIRCUITPY in its name, or None."""
    if not os.path.isdir(MEDIA_PATH):
        return None
    for name in os.listdir(MEDIA_PATH):
        if "CIRCUITPY" in name:
            return os.path.join(MEDIA_PATH, name)
    return None


from pathlib import Path
import os
import time

def wait_for_device():
    """Poll for a readable CIRCUITPY mount and return its path."""
    journal_log("Waiting for CIRCUITPY device...")

    def readable_circuitpy_mount():
        journal_log("checking mount path...")

        media_root = Path("/media") / os.getenv("USER", "")
        journal_log(f"media root: {media_root}")
        if not media_root.exists():
            journal_log(f"media root does not exist")
            return None
        
        journal_log(f"media root exists")

        candidates = sorted(media_root.glob("CIRCUITPY*"))
        journal_log(f"candidates: {candidates}")

        for path in candidates:
            journal_log(f"trying: {path}")

            try:
                if not path.is_dir():
                    continue
    
                next(path.iterdir(), None)

                if not (path / "boot_out.txt").exists():
                    continue

                return str(path)

            except (OSError, PermissionError):
                continue

        return None

    elapsed = 0
    while elapsed < DEVICE_TIMEOUT_SECS:
        device_path = readable_circuitpy_mount()
        if device_path:
            journal_log(f"CIRCUITPY found after {elapsed}s at {device_path}")
            return device_path

        time.sleep(1)
        elapsed += 1

    journal_log_error(f"No readable CIRCUITPY device found after {DEVICE_TIMEOUT_SECS}s.")
    raise SystemExit(1)


def wait_for_ip_file(device_path):
    """Poll for ip.txt on the device, exiting with error if it doesn't appear within the timeout."""
    ip_file = os.path.join(device_path, IP_FILE_NAME)
    journal_log(f"Waiting for {IP_FILE_NAME}...")
    elapsed = 0
    while elapsed < IP_FILE_TIMEOUT_SECS:
        if os.path.isfile(ip_file):
            journal_log(f"{IP_FILE_NAME} found after {elapsed}s")
            return ip_file
        time.sleep(1)
        elapsed += 1

    journal_log_error(f"{IP_FILE_NAME} not found after {IP_FILE_TIMEOUT_SECS}s.")
    raise SystemExit(1)


def read_ip(device_path):
    """Read and validate the IP address from ip.txt on the device."""
    ip_file = wait_for_ip_file(device_path)

    raw = open(ip_file).read().strip()
    try:
        ipaddress.IPv4Address(raw)

    except ipaddress.AddressValueError:
        journal_log_error(f"Invalid IPv4 address in ip.txt: '{raw}'")
        raise SystemExit(1)

    journal_log(f"Read IP: {raw}")
    return raw


def write_config(ip):
    """Write the MATRIX_HTTP_URL to the deskradar config, creating it if needed."""
    os.makedirs(CONFIG_DIR, exist_ok=True)

    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    else:
        if not os.path.isfile(CONFIG_EXAMPLE_PATH):
            journal_log_error(f"Config example not found at {CONFIG_EXAMPLE_PATH}")
            raise SystemExit(1)
        with open(CONFIG_EXAMPLE_PATH) as f:
            config = json.load(f)
        journal_log(f"Creating new config at {CONFIG_PATH} from {CONFIG_EXAMPLE_PATH}")

    config[MATRIX_URL_CONFIG_KEY] = f"http://{ip}:80"

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    journal_log(f"{MATRIX_URL_CONFIG_KEY} set to http://{ip}:80")


def main():
    syslog.openlog("boot_check", syslog.LOG_PID, syslog.LOG_DAEMON)
    if BYPASS.lower() == "true":
        journal_log("bypassing boot checks...")
        lcd_log("Boot check", "Bypassed")
        return

    lcd_log("Waiting for", "CIRCUITPY...")
    device_path = wait_for_device()

    lcd_log("CIRCUITPY found", "Reading IP...")
    ip = read_ip(device_path)

    lcd_log(f"IP: {ip}", "Writing config...")
    write_config(ip)

    lcd_log("Boot check", "Complete")
    journal_log("Boot check complete.")


if __name__ == "__main__":
    main()
