import json
import subprocess
import sys
from pathlib import Path

CONFIG_FILE = Path("/etc/deskradar/config.json")


def main():
    data = sys.stdin.read()
    cfg = json.loads(data)

    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"Config written to {CONFIG_FILE}")

    result = subprocess.run(
        ["sudo", "systemctl", "restart", "deskradar"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("deskradar service restarted")
    else:
        print(f"Failed to restart deskradar: {result.stderr}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
