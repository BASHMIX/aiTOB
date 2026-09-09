"""Create a missing service-level integration encryption key without printing it."""
from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.fernet import Fernet


KEY_NAME = "AITOB_INTEGRATION_MASTER_KEY"


def provision(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    if any(line.split("=", 1)[0].strip() == KEY_NAME and line.split("=", 1)[-1].strip() for line in lines if "=" in line):
        return False
    lines.append(f"{KEY_NAME}={Fernet.generate_key().decode('ascii')}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    provision(Path(args.env_file))
