#!/usr/bin/env bash
set -euo pipefail

AP_CON="deskradarAP"
AP_SSID="deskradar"
AP_PSK="deskradaradsb"
AP_IP="10.42.0.50/24"

if nmcli connection show "$AP_CON" &>/dev/null; then
    echo "Connection '$AP_CON' already exists — nothing to do."
    exit 0
fi

echo "Creating AP connection '$AP_CON' (SSID: $AP_SSID)..."

sudo nmcli connection add \
    type wifi \
    con-name "$AP_CON" \
    ssid "$AP_SSID" \
    wifi.band bg \
    wifi.mode ap \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$AP_PSK" \
    ipv4.method shared \
    ipv4.addresses "$AP_IP" \
    connection.autoconnect yes \
    connection.autoconnect-priority 999

echo "Done. AP '$AP_CON' created."

sudo nmcli connection up deskradarAP