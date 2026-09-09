"""Provision the local service-level MFA encryption key without printing it."""
from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet


def main() -> None:
    path = Path(".env.production")
    if not path.exists():
        raise SystemExit(".env.production is required and is intentionally ignored by Git.")
    lines = path.read_text(encoding="utf-8").splitlines()
    existing = next((line.partition("=")[2].strip() for line in lines if line.startswith("AITOB_AUTH_MASTER_KEY=")), "")
    if existing:
        print("Authentication encryption key is already configured.")
        return
    lines.append("AITOB_AUTH_MASTER_KEY=" + Fernet.generate_key().decode("ascii"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Authentication encryption key provisioned in ignored local configuration.")


if __name__ == "__main__":
    main()
