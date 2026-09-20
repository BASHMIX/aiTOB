"""Explicit Discord routing for workspace-owned tournament effects.

Discord delivery must carry enough durable context to identify exactly one
workspace, tournament, guild, destination, and (when applicable) match
thread.  This module is deliberately independent from the process-global bot
state.  It resolves the persisted binding and rejects missing, disabled,
cross-workspace, or ambiguous routes before a caller can send an effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from backend.core import database
from backend.core.storage import dbapi as aiosqlite


DestinationKind = Literal["match", "escalation"]


class DiscordRoutingError(LookupError):
    """Base error raised when a Discord route cannot be proven safe."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


class DiscordRouteMissing(DiscordRoutingError):
    def __init__(self, message: str = "The requested Discord route was not found."):
        super().__init__(message, code="route_missing")


class DiscordRouteAmbiguous(DiscordRoutingError):
    def __init__(self, message: str = "The requested Discord route is ambiguous."):
        super().__init__(message, code="route_ambiguous")


class DiscordRouteMismatch(DiscordRoutingError):
    def __init__(self, message: str = "The Discord route context does not match its binding."):
        super().__init__(message, code="route_mismatch")


@dataclass(frozen=True, slots=True)
class DiscordRoute:
    """Validated route projection safe for an outbound Discord operation."""

    workspace_id: str
    tournament_id: str
    discord_account_id: str
    guild_id: str
    match_destination_id: str
    escalation_destination_id: str
    destination_id: str
    destination_external_id: str
    destination_type: str
    conversation_mode: str
    status: str
    thread_id: str | None = None
    set_id: str | None = None

    @property
    def channel_id(self) -> str:
        """External Discord channel/forum ID selected for this operation."""

        return self.destination_external_id

    def as_dict(self) -> dict[str, str | None]:
        """Return the stable, non-secret route projection for callers."""

        return {
            "workspace_id": self.workspace_id,
            "tournament_id": self.tournament_id,
            "discord_account_id": self.discord_account_id,
            "guild_id": self.guild_id,
            "match_destination_id": self.match_destination_id,
            "escalation_destination_id": self.escalation_destination_id,
            "destination_id": self.destination_id,
            "destination_external_id": self.destination_external_id,
            "channel_id": self.channel_id,
            "destination_type": self.destination_type,
            "conversation_mode": self.conversation_mode,
            "status": self.status,
            "thread_id": self.thread_id,
            "set_id": self.set_id,
        }

    def __getitem__(self, key: str) -> str | None:
        """Keep the projection convenient for existing dictionary-style bot code."""

        return self.as_dict()[key]


def _required(value: object, field: str) -> str:
    if value is None or not isinstance(value, (str, int)) or not str(value).strip():
        raise DiscordRouteMissing(f"A {field} is required to resolve a Discord route.")
    return str(value).strip()


def _destination_kind(value: str) -> tuple[str, str]:
    kind = str(value or "match").strip().lower()
    if kind in {"match", "match_destination", "match_call", "match_call_channel"}:
        return "match", "match_destination_id"
    if kind in {"escalation", "escalation_destination", "organizer", "organizer_escalation"}:
        return "escalation", "escalation_destination_id"
    raise DiscordRouteMismatch("Unknown Discord destination kind.")


async def _binding_rows(workspace_id: str, tournament_id: str) -> list[dict[str, Any]]:
    """Fetch candidate bindings without selecting an arbitrary row.

    The joins enforce ownership all the way through the tournament, Discord
    account, and two child destinations. A legacy/unowned row therefore cannot
    become an implicit fallback route.
    """

    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT
                b.tournament_id,
                b.workspace_id,
                b.discord_account_id,
                b.guild_id,
                b.match_destination_id,
                b.escalation_destination_id,
                b.conversation_mode,
                b.status AS binding_status,
                a.external_account_id,
                a.status AS account_status,
                md.external_id AS match_destination_external_id,
                md.destination_type AS match_destination_type,
                md.workspace_id AS match_destination_workspace_id,
                md.status AS match_destination_status,
                ed.external_id AS escalation_destination_external_id,
                ed.destination_type AS escalation_destination_type,
                ed.workspace_id AS escalation_destination_workspace_id,
                ed.status AS escalation_destination_status
            FROM tournament_discord_bindings AS b
            JOIN tournaments AS t
              ON t.slug = b.tournament_id
             AND t.workspace_id = b.workspace_id
            JOIN integration_accounts AS a
              ON a.id = b.discord_account_id
             AND a.workspace_id = b.workspace_id
             AND a.external_account_id = b.guild_id
             AND a.provider_type = 'discord'
            LEFT JOIN integration_destinations AS md
              ON md.id = b.match_destination_id
             AND md.account_id = a.id
             AND md.workspace_id = b.workspace_id
            LEFT JOIN integration_destinations AS ed
              ON ed.id = b.escalation_destination_id
             AND ed.account_id = a.id
             AND ed.workspace_id = b.workspace_id
            WHERE b.workspace_id = ?
              AND b.tournament_id = ?
        """
        async with db.execute(query, (workspace_id, tournament_id)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def _thread_context(
    workspace_id: str,
    tournament_id: str,
    thread_id: str,
    set_id: str | None,
) -> dict[str, str]:
    """Resolve one thread only inside the already selected tournament scope."""

    clauses = [
        "workspace_id = ?",
        "tournament_slug = ?",
        "(discord_thread_id = ? OR thread_id = ?)",
    ]
    params: list[str] = [workspace_id, tournament_id, thread_id, thread_id]
    if set_id is not None:
        clauses.append("set_id = ?")
        params.append(set_id)

    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT set_id, discord_thread_id, thread_id FROM active_matches WHERE {' AND '.join(clauses)}",
            params,
        ) as cursor:
            rows = [dict(row) for row in await cursor.fetchall()]

    if not rows:
        raise DiscordRouteMissing("The Discord thread is not registered for this tournament.")
    if len(rows) != 1:
        raise DiscordRouteAmbiguous("The Discord thread belongs to multiple matches in this tournament.")
    row = rows[0]
    return {"set_id": str(row["set_id"]), "thread_id": thread_id}


async def resolve_discord_route(
    workspace_id: str,
    tournament_id: str,
    guild_id: str | None = None,
    channel_id: str | None = None,
    thread_id: str | None = None,
    *,
    destination_kind: str = "match",
    destination_id: str | None = None,
    set_id: str | None = None,
) -> DiscordRoute:
    """Resolve one explicit workspace/tournament Discord route.

    ``guild_id`` and ``channel_id`` are optional only for outbound callers that
    already hold the durable tournament binding. When supplied (as they are
    for inbound interactions), both values must match the persisted route.
    ``thread_id`` is checked against an active match in the same workspace and
    tournament; it is never resolved globally.

    Missing, disabled, cross-workspace, malformed, and ambiguous context raises
    a typed ``DiscordRoutingError``. Callers should surface the error and stop
    the effect rather than attempt a legacy/global fallback.
    """

    workspace = _required(workspace_id, "workspace ID")
    tournament = _required(tournament_id, "tournament ID")
    provided_guild = str(guild_id).strip() if guild_id is not None else None
    provided_channel = str(channel_id).strip() if channel_id is not None else None
    provided_thread = str(thread_id).strip() if thread_id is not None else None
    provided_set = str(set_id).strip() if set_id is not None else None
    if guild_id is not None and not provided_guild:
        raise DiscordRouteMissing("A guild ID cannot be empty.")
    if channel_id is not None and not provided_channel:
        raise DiscordRouteMissing("A channel ID cannot be empty.")
    if thread_id is not None and not provided_thread:
        raise DiscordRouteMissing("A thread ID cannot be empty.")
    if set_id is not None and not provided_set:
        raise DiscordRouteMissing("A match ID cannot be empty.")

    kind, binding_field = _destination_kind(destination_kind)
    rows = await _binding_rows(workspace, tournament)
    if not rows:
        raise DiscordRouteMissing("No workspace-owned Discord binding exists for this tournament.")
    if len(rows) != 1:
        raise DiscordRouteAmbiguous("More than one Discord binding exists for this tournament and workspace.")
    binding = rows[0]

    if binding.get("binding_status") == "disabled":
        raise DiscordRouteMissing("The Discord binding is disabled.")
    if binding.get("account_status") != "active":
        raise DiscordRouteMissing("The selected Discord account is unavailable.")
    if provided_guild is not None and provided_guild != str(binding["guild_id"]):
        raise DiscordRouteMismatch("The supplied guild is not the tournament's configured guild.")
    if str(binding.get("external_account_id") or "") != str(binding["guild_id"]):
        raise DiscordRouteMismatch("The Discord account and binding guild do not agree.")

    destination_uuid = str(binding.get(binding_field) or "").strip()
    external_key = f"{kind}_destination_external_id"
    destination_external = str(binding.get(external_key) or "").strip()
    destination_status = binding.get(f"{kind}_destination_status")
    destination_workspace = binding.get(f"{kind}_destination_workspace_id")
    if not destination_uuid or not destination_external:
        raise DiscordRouteMissing("The selected Discord destination is not configured.")
    if destination_status != "active" or str(destination_workspace or "") != workspace:
        raise DiscordRouteMissing("The selected Discord destination is unavailable in this workspace.")

    if destination_id is not None and str(destination_id).strip() not in {destination_uuid, destination_external}:
        raise DiscordRouteMismatch("The supplied destination does not match the tournament binding.")
    if provided_channel is not None and provided_channel != destination_external:
        raise DiscordRouteMismatch("The supplied channel is not the configured tournament destination.")

    thread_context: dict[str, str] = {}
    if provided_thread is not None:
        thread_context = await _thread_context(workspace, tournament, provided_thread, provided_set)
    elif provided_set is not None:
        raise DiscordRouteMismatch("A match ID requires its explicit Discord thread ID.")

    return DiscordRoute(
        workspace_id=workspace,
        tournament_id=tournament,
        discord_account_id=str(binding["discord_account_id"]),
        guild_id=str(binding["guild_id"]),
        match_destination_id=str(binding["match_destination_id"]),
        escalation_destination_id=str(binding["escalation_destination_id"]),
        destination_id=destination_uuid,
        destination_external_id=destination_external,
        destination_type=str(binding.get(f"{kind}_destination_type") or ""),
        conversation_mode=str(binding.get("conversation_mode") or "channel"),
        status=str(binding.get("binding_status") or "degraded"),
        thread_id=thread_context.get("thread_id"),
        set_id=thread_context.get("set_id"),
    )


async def try_resolve_discord_route(*args: Any, **kwargs: Any) -> DiscordRoute | None:
    """Optional boundary for callers that treat an unusable route as no route."""

    try:
        return await resolve_discord_route(*args, **kwargs)
    except DiscordRoutingError:
        return None


# Descriptive aliases keep the boundary discoverable for callers that use
# "binding" or "tournament route" terminology while retaining one resolver.
resolve_tournament_discord_route = resolve_discord_route
resolve_discord_binding = resolve_discord_route


__all__ = [
    "DiscordRoute",
    "DiscordRoutingError",
    "DiscordRouteMissing",
    "DiscordRouteAmbiguous",
    "DiscordRouteMismatch",
    "resolve_discord_route",
    "resolve_tournament_discord_route",
    "resolve_discord_binding",
    "try_resolve_discord_route",
]

