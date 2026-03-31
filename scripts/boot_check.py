#!/usr/bin/env python3
"""Boot script that resolves deskradar-portal.local via mDNS and writes its IP to deskradar config."""

import json
import os
import socket
import syslog
import time
import requests

# wait for system readiness
time.sleep(10)

CONFIG_DIR = "/etc/deskradar"
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CONFIG_EXAMPLE_PATH = "/opt/deskradar/config-example.json"
MATRIX_URL_CONFIG_KEY = "MATRIX_HTTP_URL"
BYPASS = os.environ.get("DESKRADAR_BYPASS_BOOT", "")
LCD_URL = "http://127.0.0.1:8010/display"
MDNS_HOSTNAME = "deskradar-portal.local"
RESOLVE_TIMEOUT_SECS = 30


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


def resolve_ip():
    """Resolve deskradar-portal.local via mDNS with retries."""
    journal_log(f"Resolving {MDNS_HOSTNAME}...")
    elapsed = 0
    while elapsed < RESOLVE_TIMEOUT_SECS:
        try:
            results = socket.getaddrinfo(MDNS_HOSTNAME, None, socket.AF_INET)
            ip = results[0][4][0]
            journal_log(f"Resolved {MDNS_HOSTNAME} -> {ip} after {elapsed}s")
            return ip
        except socket.gaierror:
            journal_log(f"Resolution attempt failed at {elapsed}s, retrying...")
            time.sleep(2)
            elapsed += 2

    journal_log_error(f"Failed to resolve {MDNS_HOSTNAME} after {RESOLVE_TIMEOUT_SECS}s")
    lcd_log("mDNS failed", MDNS_HOSTNAME)
    raise SystemExit(1)


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

    lcd_log("Resolving", MDNS_HOSTNAME)
    ip = resolve_ip()

    lcd_log("IP found:", ip)
    time.sleep(3)

    write_config(ip)

    lcd_log("Boot check", "Complete")
    journal_log("Boot check complete.")


if __name__ == "__main__":
    main()
