"""Bind the two organizer-approved Discord test users to acceptance match A.

This tool never calls Discord or a tournament provider.  It only creates
explicit, stable identity links in the isolated acceptance SQLite database.
It deliberately refuses any database outside ``.acceptance`` and refuses to
overwrite an existing mapping for either Challonge participant.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import aiosqlite

from seed_acceptance_challonge_account import load_env


async def _main(database_path: Path, master_key: str, player_one: str, player_two: str) -> None:
    resolved = database_path.resolve()
    acceptance_root = (Path.cwd() / ".acceptance").resolve()
    if acceptance_root not in resolved.parents:
        raise RuntimeError("This binding tool accepts only a database under .acceptance.")
    if not master_key:
        raise RuntimeError("Acceptance integration master key is required.")

    os.environ["AITOB_INTEGRATION_MASTER_KEY"] = master_key
    from backend.core import database
    from backend.core.identity_links import save_identity_override
    from backend.core.integrations import get_integration_account, list_integration_accounts

    database.DB_PATH = str(resolved)
    await database.init_db()
    discord_accounts = [
        account for account in await list_integration_accounts("acceptance")
        if account["provider_type"] == "discord" and account["status"] == "active"
    ]
    if len(discord_accounts) != 1:
        raise RuntimeError("Acceptance requires exactly one active Discord account.")
    if not await get_integration_account(discord_accounts[0]["id"]):
        raise RuntimeError("Acceptance Discord account is not active.")

    async with aiosqlite.connect(resolved) as db:
        db.row_factory = aiosqlite.Row
        tournament = await (await db.execute(
            "SELECT slug FROM tournaments WHERE provider_type='challonge' ORDER BY created_at DESC LIMIT 1"
        )).fetchone()
        if not tournament:
            raise RuntimeError("No acceptance Challonge tournament was imported.")
        match = await (await db.execute(
            """SELECT set_id, p1_name, p1_entrant_id, p2_name, p2_entrant_id
                 FROM active_matches WHERE tournament_slug=? AND provider_state_raw='open'
                   AND p1_entrant_id IS NOT NULL AND p2_entrant_id IS NOT NULL
                 ORDER BY match_number, set_id LIMIT 1""",
            (tournament["slug"],),
        )).fetchone()
        if not match:
            raise RuntimeError("No eligible first acceptance match was found.")
        for entrant_id in (match["p1_entrant_id"], match["p2_entrant_id"]):
            existing = await (await db.execute(
                """SELECT discord_user_id FROM provider_identity_links
                     WHERE provider_type='challonge' AND tournament_slug=?
                       AND provider_entrant_id=? AND discord_user_id IS NOT NULL
                       AND verification_state IN ('verified', 'organizer_override')""",
                (tournament["slug"], entrant_id),
            )).fetchall()
            if existing:
                raise RuntimeError("A first-match participant already has a verified Discord identity link.")
        await db.execute(
            "UPDATE tournaments SET discord_account_id=? WHERE slug=?",
            (discord_accounts[0]["id"], tournament["slug"]),
        )
        await db.commit()

    for entrant_id, display_name, discord_user_id in (
        (match["p1_entrant_id"], match["p1_name"], player_one),
        (match["p2_entrant_id"], match["p2_name"], player_two),
    ):
        await save_identity_override({
            "provider_type": "challonge",
            "tournament_slug": tournament["slug"],
            "provider_participant_id": str(entrant_id),
            "provider_entrant_id": str(entrant_id),
            "discord_user_id": discord_user_id,
            "scope": "tournament",
            "display_name_snapshot": display_name,
        })
    print("acceptance_first_match_identities_bound=ok")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=".acceptance/acceptance.sqlite")
    parser.add_argument("--env", default=".env.acceptance")
    parser.add_argument("--player-one", required=True)
    parser.add_argument("--player-two", required=True)
    arguments = parser.parse_args()
    if not (arguments.player_one.isdecimal() and arguments.player_two.isdecimal()):
        raise SystemExit("Discord user IDs must be decimal snowflakes.")
    values = load_env(Path(arguments.env))
    asyncio.run(_main(Path(arguments.database), values.get("AITOB_INTEGRATION_MASTER_KEY", ""), arguments.player_one, arguments.player_two))
