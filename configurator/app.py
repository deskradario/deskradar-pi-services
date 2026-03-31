import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for

load_dotenv()

app = Flask(__name__)

CONFIG_FILE = Path("/etc/deskradar/config.json")
AP_NAME = os.getenv("AP_NAME", "deskradarAP")

HIDDEN_KEYS = {"GET_URL", "LCD_SEND_URL", "MATRIX_HTTP_URL"}

CHECKBOX_KEYS = {"DRAW_RETICULE", "SHOW_CLOSEST"}


def infer_mode():
    """Check active nmcli connections to determine AP or LAN mode."""
    result = subprocess.run(
        ["sudo", "nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"],
        capture_output=True, text=True,
    )
    for line in result.stdout.strip().splitlines():
        name, conn_type = line.split(":")
        if conn_type == "802-11-wireless" and name != AP_NAME:
            return "LAN"
    return "AP"


def get_saved_wifi_connections():
    """Return list of saved wifi connection profile names, excluding the AP."""
    result = subprocess.run(
        ["sudo", "nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
        capture_output=True, text=True,
    )
    connections = []
    for line in result.stdout.strip().splitlines():
        name, conn_type = line.split(":")
        if conn_type == "802-11-wireless" and name != AP_NAME:
            connections.append(name)
    return connections


@app.route("/")
def home():
    mode = infer_mode()
    saved = get_saved_wifi_connections()
    return render_template("home.html", mode=mode, saved_connections=saved)


@app.route("/switch-to-lan", methods=["POST"])
def switch_to_lan():
    name = request.form.get("name")

    if name:
        cmd = [sys.executable, "switch_to_lan.py", "--name", name]
    else:
        ssid = request.form["ssid"]
        password = request.form["password"]
        cmd = [sys.executable, "switch_to_lan.py", "--ssid", ssid, "--password", password]

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)

    return redirect(url_for("home"))


@app.route("/switch-to-ap", methods=["POST"])
def switch_to_ap():
    result = subprocess.run(
        [sys.executable, "switch_to_ap.py"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)

    return redirect(url_for("home"))


@app.route("/config")
def config():
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
    except FileNotFoundError:
        cfg = {}
    return render_template("config.html", config=cfg)


@app.route("/config", methods=["POST"])
def config_post():
    # Read existing config so hidden keys are preserved
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
    except FileNotFoundError:
        cfg = {}

    form = request.form

    for key in form:
        if key == "CLOSEST_COLOUR":
            continue
        raw = form[key]
        if key in CHECKBOX_KEYS:
            cfg[key] = True
            continue
        # Try to coerce to the original type
        orig = cfg.get(key)
        if isinstance(orig, int):
            try:
                cfg[key] = int(raw)
            except ValueError:
                cfg[key] = float(raw)
        elif isinstance(orig, float):
            cfg[key] = float(raw)
        else:
            cfg[key] = raw

    # Checkboxes not present in form means unchecked
    for key in CHECKBOX_KEYS:
        if key not in form:
            cfg[key] = False

    # Colour picker: hex -> {r, g, b}
    hex_colour = form.get("CLOSEST_COLOUR", "#00ffff")
    hex_colour = hex_colour.lstrip("#")
    cfg["CLOSEST_COLOUR"] = {
        "r": int(hex_colour[0:2], 16),
        "g": int(hex_colour[2:4], 16),
        "b": int(hex_colour[4:6], 16),
    }

    result = subprocess.run(
        [sys.executable, "update_config.py"],
        input=json.dumps(cfg, indent=2),
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)

    return redirect(url_for("config"))


def ensure_cert():
    """Generate a self-signed cert if one doesn't exist yet."""
    cert_dir = Path(__file__).parent / "certs"
    cert_file = cert_dir / "cert.pem"
    key_file = cert_dir / "key.pem"

    if not cert_file.exists():
        cert_dir.mkdir(exist_ok=True)
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_file), "-out", str(cert_file),
            "-days", "3650", "-nodes", "-subj", "/CN=deskradar",
        ], check=True)

    return str(cert_file), str(key_file)


if __name__ == "__main__":
    cert, key = ensure_cert()
    print("Serving on https://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, ssl_context=(cert, key))
