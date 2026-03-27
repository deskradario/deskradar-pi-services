#!/usr/bin/env python3
"""Boot script that reads IP from CIRCUITPY USB device and writes it to deskradar config."""

import json
import ipaddress
import os
import syslog
import time

MEDIA_PATH = "/media/pi"
TIMEOUT_SECS = 15
CONFIG_DIR = "/etc/deskradar"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CONFIG_EXAMPLE_PATH = "/opt/deskradar/config-example.json"


def log(msg):
    syslog.syslog(syslog.LOG_INFO, f"[boot_check] {msg}")


def log_error(msg):
    syslog.syslog(syslog.LOG_ERR, f"[boot_check] {msg}")


def find_device():
    """Return the mount path of the first device with CIRCUITPY in its name, or None."""
    if not os.path.isdir(MEDIA_PATH):
        return None
    for name in os.listdir(MEDIA_PATH):
        if "CIRCUITPY" in name:
            return os.path.join(MEDIA_PATH, name)
    return None


def wait_for_device():
    """Poll for a CIRCUITPY device, exiting with error if none appears within the timeout."""
    log("Waiting for CIRCUITPY device...")
    elapsed = 0
    while elapsed < TIMEOUT_SECS:
        device_path = find_device()
        if device_path:
            log(f"Found device at {device_path}")
            return device_path
        time.sleep(1)
        elapsed += 1

    log_error(f"No CIRCUITPY device found after {TIMEOUT_SECS}s.")
    raise SystemExit(1)


def read_ip(device_path):
    """Read and validate the IP address from ip.txt on the device."""
    ip_file = os.path.join(device_path, "ip.txt")
    if not os.path.isfile(ip_file):
        log_error(f"{ip_file} not found on device")
        raise SystemExit(1)

    raw = open(ip_file).read().strip()
    try:
        ipaddress.IPv4Address(raw)
    except ipaddress.AddressValueError:
        log_error(f"Invalid IPv4 address in ip.txt: '{raw}'")
        raise SystemExit(1)

    log(f"Read IP: {raw}")
    return raw


def write_config(ip):
    """Write the MATRIX_HTTP_URL to the deskradar config, creating it if needed."""
    os.makedirs(CONFIG_DIR, exist_ok=True)

    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    else:
        if not os.path.isfile(CONFIG_EXAMPLE_PATH):
            log_error(f"Config example not found at {CONFIG_EXAMPLE_PATH}")
            raise SystemExit(1)
        with open(CONFIG_EXAMPLE_PATH) as f:
            config = json.load(f)
        log(f"Creating new config at {CONFIG_PATH} from {CONFIG_EXAMPLE_PATH}")

    config["MATRIX_HTTP_URL"] = f"http://{ip}"

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    log(f"MATRIX_HTTP_URL set to http://{ip}")


def main():
    syslog.openlog("boot_check", syslog.LOG_PID, syslog.LOG_DAEMON)
    device_path = wait_for_device()
    ip = read_ip(device_path)
    write_config(ip)
    log("Boot check complete.")


if __name__ == "__main__":
    main()
