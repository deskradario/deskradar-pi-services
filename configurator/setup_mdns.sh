#!/usr/bin/env bash
set -euo pipefail

# Sets hostname to "deskradar" and ensures avahi advertises deskradar.local

HOSTNAME="deskradar"

echo "Installing avahi-daemon..."
apt-get install -y avahi-daemon

echo "Setting hostname to ${HOSTNAME}..."
hostnamectl set-hostname "$HOSTNAME"
sed -i "s/127\.0\.1\.1.*/127.0.1.1\t${HOSTNAME}/" /etc/hosts

echo "Enabling and restarting avahi-daemon..."
systemctl enable avahi-daemon
systemctl restart avahi-daemon

# Allow the service user to run nmcli without a password
SUDOERS_FILE="/etc/sudoers.d/deskradar-nmcli"
SERVICE_USER="${1:-pi}"
echo "Granting ${SERVICE_USER} passwordless sudo for nmcli..."
echo "${SERVICE_USER} ALL=(ALL) NOPASSWD: /usr/bin/nmcli" > "$SUDOERS_FILE"
chmod 440 "$SUDOERS_FILE"

echo "Done. This Pi is now reachable at ${HOSTNAME}.local"
