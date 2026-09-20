"""Assign legacy assistant settings to one workspace without copying secrets.

This is deliberately explicit: an operator must separately enter a customer
API key through the workspace integration endpoint.  The script copies only
non-secret controls and writes an audit record.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime

from backend.core import database
from backend.core.storage import dbapi


async def assign(workspace_id: str, actor_id: str, *, selected_account_id: str | None = None) -> dict[str, object]:
    async with dbapi.connect(database.DATABASE_DSN) as db:
        db.row_factory = dbapi.Row
        row = await (await db.execute("SELECT provider_type, model, mode, request_limit, token_limit, context_char_limit, response_char_limit, request_timeout_seconds, policy_version FROM ai_service_config WHERE id=1")).fetchone()
        if not row:
            raise RuntimeError("legacy_ai_config_missing")
        data = dict(row)
        await db.execute(
            """INSERT INTO workspace_ai_configs (workspace_id, selected_account_id, provider_type, model, mode, request_limit, token_limit, context_char_limit, response_char_limit, request_timeout_seconds, policy_version, updated_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(workspace_id) DO UPDATE SET selected_account_id=excluded.selected_account_id, provider_type=excluded.provider_type, model=excluded.model, mode=excluded.mode, request_limit=excluded.request_limit, token_limit=excluded.token_limit, context_char_limit=excluded.context_char_limit, response_char_limit=excluded.response_char_limit, request_timeout_seconds=excluded.request_timeout_seconds, policy_version=excluded.policy_version, updated_by=excluded.updated_by, updated_at=CURRENT_TIMESTAMP""",
            (workspace_id, selected_account_id, data["provider_type"], data["model"], data["mode"], data["request_limit"], data["token_limit"], data["context_char_limit"], data["response_char_limit"], data["request_timeout_seconds"], data["policy_version"], actor_id),
        )
        await db.execute("INSERT INTO integration_audit (account_id, action, detail_json) VALUES (?, ?, ?)", (None, "legacy_ai_config_assigned", json.dumps({"workspace_id": workspace_id, "actor_id": actor_id, "secret_copied": False})))
        await db.commit()
    return {"workspace_id": workspace_id, "selected_account_id": selected_account_id, "secret_copied": False, "assigned_at": datetime.now(UTC).isoformat()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace_id")
    parser.add_argument("actor_id")
    parser.add_argument("--selected-account-id")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(assign(args.workspace_id, args.actor_id, selected_account_id=args.selected_account_id))))


if __name__ == "__main__":
    main()
