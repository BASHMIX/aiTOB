"""Normalize and validate the ignored production environment safely.

The command removes retired single-tenant/file-database variables, provisions
service encryption keys without printing them, and fails closed when external
credentials still need to be supplied by the deployment owner.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet


RETIRED_KEYS = {
    "DB_PATH",
    "DISCORD_GUILD_ID",
    "AITOB_DISCORD_WORKSPACE_ID",
    "PROVIDER_V2_CONTRACTS_ENABLED",
    "PROVIDER_COORDINATOR_ENABLED",
}
GENERATED_KEYS = (
    "AITOB_AUTH_MASTER_KEY",
    "AITOB_INTEGRATION_MASTER_KEY",
    "AITOB_AI_SERVICE_MASTER_KEY",
)
REQUIRED_KEYS = (
    "DATABASE_URL",
    "POSTGRES_PASSWORD",
    "DISCORD_BOT_TOKEN",
    "DISCORD_CLIENT_ID",
    "DISCORD_CLIENT_SECRET",
    "DISCORD_OAUTH_REDIRECT_URI",
    "APP_PUBLIC_URL",
    "FRONTEND_BASE_URL",
    *GENERATED_KEYS,
)


def _assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key or not key.replace("_", "").isalnum():
        return None
    return key, value.strip()


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip('"').strip("'").lower()
    return not normalized or normalized in {"change_me", "changeme"} or normalized.startswith("your_")


def prepare(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        raise ValueError(f"{path} does not exist")
    original = path.read_text(encoding="utf-8").splitlines()
    # Keep the last assignment, matching common dotenv behavior, while
    # preserving comments and the surrounding hand-written layout.
    last_index: dict[str, int] = {}
    values: dict[str, str] = {}
    for index, line in enumerate(original):
        item = _assignment(line)
        if item:
            last_index[item[0]] = index
            values[item[0]] = item[1]

    removed = sorted(key for key in RETIRED_KEYS if key in values)
    generated: list[str] = []
    for key in GENERATED_KEYS:
        if _is_placeholder(values.get(key, "")):
            values[key] = Fernet.generate_key().decode("ascii")
            generated.append(key)

    api_base = values.get("API_BASE_URL", "").strip().rstrip("/")
    app_public = values.get("APP_PUBLIC_URL", "").strip().rstrip("/")
    public_base = app_public if app_public.startswith("https://") else api_base
    if public_base.startswith("https://"):
        values["APP_PUBLIC_URL"] = public_base
        values["FRONTEND_BASE_URL"] = public_base
        values["DISCORD_OAUTH_REDIRECT_URI"] = (
            values.get("DISCORD_OAUTH_REDIRECT_URI", "").strip()
            or f"{public_base}/api/integrations/discord/callback"
        )
        values["AITOB_SESSION_COOKIE_SECURE"] = "true"
    values["DEBUG"] = "False"
    values.setdefault("AITOB_LEGACY_HUB_PASSWORD_COMPAT", "false")
    values.setdefault("ALLOW_PUBLIC_REGISTRATION", "false")
    values.setdefault("DISCORD_CLIENT_ID", "")
    values.setdefault("DISCORD_CLIENT_SECRET", "")

    managed = set(GENERATED_KEYS) | {
        "APP_PUBLIC_URL", "FRONTEND_BASE_URL", "DISCORD_OAUTH_REDIRECT_URI",
        "DISCORD_CLIENT_ID", "DISCORD_CLIENT_SECRET", "AITOB_SESSION_COOKIE_SECURE",
        "AITOB_LEGACY_HUB_PASSWORD_COMPAT", "ALLOW_PUBLIC_REGISTRATION", "DEBUG",
    }
    emitted: set[str] = set()
    output: list[str] = []
    for index, line in enumerate(original):
        item = _assignment(line)
        if not item:
            output.append(line)
            continue
        key, _value = item
        if key in RETIRED_KEYS or index != last_index.get(key):
            continue
        if key in managed:
            output.append(f"{key}={values[key]}")
            emitted.add(key)
        else:
            output.append(line)
            emitted.add(key)
    for key in managed:
        if key not in emitted:
            output.append(f"{key}={values[key]}")

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return {"removed": removed, "generated": generated}


def validate(path: Path) -> list[str]:
    values = dict(item for line in path.read_text(encoding="utf-8").splitlines() if (item := _assignment(line)))
    errors: list[str] = []
    for key in REQUIRED_KEYS:
        if _is_placeholder(values.get(key, "")):
            errors.append(f"{key} is missing")
    for key in RETIRED_KEYS:
        if key in values:
            errors.append(f"{key} is retired")
    if not values.get("DATABASE_URL", "").startswith(("postgresql://", "postgres://")):
        errors.append("DATABASE_URL must use PostgreSQL")
    for key in ("APP_PUBLIC_URL", "FRONTEND_BASE_URL", "DISCORD_OAUTH_REDIRECT_URI"):
        parsed = urlparse(values.get(key, ""))
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{key} must be an HTTPS URL")
    if values.get("AITOB_SESSION_COOKIE_SECURE", "").lower() != "true":
        errors.append("AITOB_SESSION_COOKIE_SECURE must be true")
    if values.get("DEBUG", "").lower() not in {"false", "0"}:
        errors.append("DEBUG must be disabled")
    if values.get("AITOB_LEGACY_HUB_PASSWORD_COMPAT", "").lower() not in {"false", "0"}:
        errors.append("AITOB_LEGACY_HUB_PASSWORD_COMPAT must be disabled")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        result = prepare(args.env_file)
        print("Production environment normalized; secret values were not printed.")
        print("Removed retired keys: " + (", ".join(result["removed"]) or "none"))
        print("Provisioned missing encryption keys: " + (", ".join(result["generated"]) or "none"))
    errors = validate(args.env_file)
    if errors:
        for error in errors:
            print(f"BLOCKED: {error}")
        return 2
    print("Production environment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
