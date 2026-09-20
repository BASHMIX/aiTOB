"""Network-free provider adapters for tournament setup tests.

These fakes intentionally record only safe call metadata.  In particular,
credential arguments are never stored in calls or error messages.  They are
small enough to use in unit tests and implement the methods exercised by the
existing Start.gg and Challonge provider wrappers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from copy import deepcopy
from typing import Any

from .payloads import challonge_fixture, discord_fixture, gemini_fixture, openai_fixture, startgg_fixture


REDACTED_STARTGG_TOKEN = "<redacted-startgg-token>"
REDACTED_CHALLONGE_KEY = "<redacted-challonge-key>"
REDACTED_GEMINI_KEY = "<redacted-gemini-key>"
REDACTED_OPENAI_KEY = "<redacted-openai-key>"


@dataclass(frozen=True)
class FakeAICompletion:
    """Structural equivalent of ``backend.core.ai_service.AICompletion``.

    Keeping this tiny value object local means importing provider fixtures does
    not initialise the database-backed AI service (or require its optional
    runtime dependencies).  ``AIService`` consumes the same public fields.
    """

    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    proposal: dict[str, Any] | None = None


def _operation(query: str) -> str:
    """Extract a GraphQL operation name without retaining the query body."""

    match = re.search(r"(?:query|mutation)\s+([A-Za-z0-9_]+)", query or "")
    return match.group(1) if match else "unknown"


class FakeStartGGClient:
    """A deterministic Start.gg GraphQL transport replacement."""

    def __init__(self, payload: dict[str, Any] | None = None, *, provider_account_id: str = "fixture-startgg-account"):
        self.payload = deepcopy(payload or startgg_fixture())
        self.token = REDACTED_STARTGG_TOKEN
        self.provider_account_id = provider_account_id
        self.calls: list[dict[str, Any]] = []
        self.last_error: dict[str, Any] | None = None
        self._set_states = {
            str(set_id): int(state)
            for set_id, state in (self.payload.get("set_states") or {}).items()
        }

    async def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        operation = _operation(query)
        self.calls.append({"operation": operation, "variables": deepcopy(variables or {})})
        tournament = self.payload["tournament"]
        if operation in {"TournamentInfo", "TournamentStreams"}:
            if operation == "TournamentStreams":
                return {"tournament": {"id": tournament["id"], "streams": deepcopy(tournament.get("streams", []))}}
            return {"tournament": deepcopy(tournament)}
        if operation == "TournamentState":
            return {"tournament": deepcopy(self.payload["state"])}
        if operation == "TournamentSets":
            events = []
            for event in self.payload.get("sets", {}).get("events", []):
                events.append({
                    "id": event["id"],
                    "name": event.get("name", ""),
                    "sets": {"pageInfo": {"totalPages": 1}, "nodes": deepcopy(event.get("nodes", []))},
                })
            return {"tournament": {"events": events}}
        if operation == "SetEntrants":
            set_id = str((variables or {}).get("id", ""))
            return {"set": {"slots": [{"entrant": {"id": entrant_id}} for entrant_id in self._entrant_order(set_id)]}}
        if operation == "SetState":
            set_id = str((variables or {}).get("id", ""))
            return {"set": {"state": self._set_states.get(set_id, 1)}}
        if operation == "ReportBracketSet":
            set_id = str((variables or {}).get("setId", ""))
            self._set_states[set_id] = 4
            return {"reportBracketSet": {"id": set_id, "state": 4, "winnerId": (variables or {}).get("winnerId")}}
        if operation == "SimpleReport":
            set_id = str((variables or {}).get("setId", ""))
            self._set_states[set_id] = 4
            return {"reportBracketSet": {"id": set_id, "state": 4}}
        if operation == "MarkInProgress":
            set_id = str((variables or {}).get("setId", ""))
            self._set_states[set_id] = 3
            return {"markSetInProgress": {"id": set_id, "state": 3}}
        if operation == "MarkSetCalled":
            set_id = str((variables or {}).get("setId", ""))
            self._set_states[set_id] = 2
            return {"markSetCalled": {"id": set_id, "state": 2}}
        if operation == "MarkSetDQ":
            set_id = str((variables or {}).get("setId", ""))
            self._set_states[set_id] = 4
            return {"reportBracketSet": {"id": set_id, "state": 4, "winnerId": (variables or {}).get("winnerId")}}
        if operation == "ResetSet":
            set_id = str((variables or {}).get("setId", ""))
            self._set_states[set_id] = 1
            return {"resetSet": {"id": set_id, "state": 1}}
        if operation == "AssignStream":
            return {"assignStream": {"id": (variables or {}).get("setId"), "state": 4, "stream": {"id": (variables or {}).get("streamId")}}}
        raise AssertionError(f"Unhandled fake Start.gg operation: {operation}")

    async def fetch_set_state(self, set_id: str) -> int:
        return self._set_states.get(str(set_id), 1)

    async def fetch_set_entrant_order(self, set_id: str) -> list[str]:
        return self._entrant_order(set_id)

    def _entrant_order(self, set_id: str) -> list[str]:
        for event in self.payload.get("sets", {}).get("events", []):
            for item in event.get("nodes", []):
                if str(item.get("id")) == str(set_id):
                    return [
                        str(slot["entrant"]["id"])
                        for slot in item.get("slots", [])
                        if slot.get("entrant") and slot["entrant"].get("id") is not None
                    ]
        return []

    async def report_set_score_normal(self, set_id: str, winner_id: str, entrant1_id: str, entrant2_id: str, entrant1_score: int, entrant2_score: int) -> bool:
        await self.query("mutation ReportBracketSet { reportBracketSet { id state } }", {"setId": set_id, "winnerId": winner_id})
        return True

    async def report_set_winner_only(self, set_id: str, winner_id: str) -> bool:
        await self.query("mutation SimpleReport { reportBracketSet { id state } }", {"setId": set_id, "winnerId": winner_id})
        return True

    async def mark_in_progress(self, set_id: str) -> bool:
        await self.query("mutation MarkInProgress { markSetInProgress { id state } }", {"setId": set_id})
        return True

    async def mark_called(self, set_id: str) -> bool:
        await self.query("mutation MarkSetCalled { markSetCalled { id state } }", {"setId": set_id})
        return True

    async def mark_set_dq(self, set_id: str, winner_id: str) -> bool:
        await self.query("mutation MarkSetDQ { reportBracketSet { id state } }", {"setId": set_id, "winnerId": winner_id})
        return True

    async def mark_set_double_dq(self, set_id: str, entrant1_id: str, entrant2_id: str) -> bool:
        return False

    async def assign_stream(self, set_id: str, stream_id: str) -> bool:
        await self.query("mutation AssignStream { assignStream { id state } }", {"setId": set_id, "streamId": stream_id})
        return True

    async def fetch_streams(self, slug_or_id: str) -> list[dict[str, Any]]:
        self.calls.append({"operation": "TournamentStreams", "variables": {"slug": str(slug_or_id)}})
        return deepcopy(self.payload["tournament"].get("streams", []))

    async def remove_stream(self, set_id: str) -> bool:
        self.calls.append({"operation": "RemoveStream", "variables": {"setId": str(set_id)}})
        return False

    async def reset_set(self, set_id: str) -> bool:
        await self.query("mutation ResetSet { resetSet { id state } }", {"setId": set_id})
        return True

    async def close(self) -> None:
        return None


class FakeChallongeClient:
    """A deterministic Challonge v2.1 JSON:API transport replacement."""

    def __init__(self, payload: dict[str, Any] | None = None, *, account_id: str = "fixture-challonge-account"):
        self.payload = deepcopy(payload or challonge_fixture())
        self.api_key = REDACTED_CHALLONGE_KEY
        self.account_id = account_id
        self.calls: list[dict[str, Any]] = []

    async def get_tournament(self, tournament_id: str, community_id: str | None = None, **_: Any) -> dict[str, Any]:
        self.calls.append({"method": "GET", "resource": "tournament", "id": str(tournament_id), "community_id": community_id})
        return deepcopy(self.payload["tournament"])

    async def find_tournament(self, slug: str, subdomain: str | None = None) -> dict[str, Any] | None:
        tournament = self.payload["tournament"]
        attributes = tournament.get("attributes", {})
        if str(tournament.get("id")) == str(slug) or str(attributes.get("url", "")).lower() == str(slug).lower():
            return deepcopy(tournament)
        return None

    async def participants(self, tournament_id: str, community_id: str | None = None) -> list[dict[str, Any]]:
        self.calls.append({"method": "GET", "resource": "participants", "id": str(tournament_id), "community_id": community_id})
        return deepcopy(self.payload.get("participants", []))

    async def matches(self, tournament_id: str, community_id: str | None = None) -> list[dict[str, Any]]:
        self.calls.append({"method": "GET", "resource": "matches", "id": str(tournament_id), "community_id": community_id})
        return deepcopy(self.payload.get("matches", []))

    async def update_match(self, tournament_id: str, match_id: str, attributes: dict[str, Any], community_id: str | None = None) -> dict[str, Any]:
        self.calls.append({"method": "PUT", "resource": "match", "id": str(match_id), "community_id": community_id, "attributes": deepcopy(attributes)})
        for item in self.payload.get("matches", []):
            if str(item.get("id")) == str(match_id):
                item.setdefault("attributes", {}).update(deepcopy(attributes))
                return deepcopy(item)
        return {"id": str(match_id), "attributes": deepcopy(attributes)}

    async def change_tournament_state(self, tournament_id: str, state: str, community_id: str | None = None) -> dict[str, Any]:
        self.calls.append({"method": "PUT", "resource": "tournament_state", "id": str(tournament_id), "community_id": community_id, "state": state})
        self.payload["tournament"].setdefault("attributes", {})["state"] = state
        return deepcopy(self.payload["tournament"])

    async def close(self) -> None:
        return None


class FakeDiscordAdapter:
    """Safe in-memory Discord guild/member adapter for routing tests."""

    provider_type = "discord"

    def __init__(self, payload: dict[str, Any] | None = None):
        self.payload = deepcopy(payload or discord_fixture())
        self.account_id = "fixture-discord-account"
        self.calls: list[dict[str, Any]] = []
        self.sent_messages: list[dict[str, Any]] = []
        self.nickname_changes: dict[str, str] = {}

    async def resources(self, guild_id: str | None = None) -> dict[str, Any]:
        self.calls.append({"method": "resources", "guild_id": guild_id})
        return deepcopy(self.payload)

    async def check_permissions(self, guild_id: str, permissions: list[str] | None = None) -> dict[str, Any]:
        self.calls.append({"method": "check_permissions", "guild_id": guild_id, "permissions": list(permissions or [])})
        actual = self.payload.get("permissions", {})
        return {permission: bool(actual.get(permission, False)) for permission in (permissions or actual.keys())}

    async def resolve_member(self, guild_id: str, discord_user_id: str) -> dict[str, Any] | None:
        self.calls.append({"method": "resolve_member", "guild_id": guild_id, "discord_user_id": str(discord_user_id)})
        member = self.payload.get("member")
        return deepcopy(member) if member and str(member.get("id")) == str(discord_user_id) else None

    async def set_server_nickname(self, guild_id: str, discord_user_id: str, nickname: str) -> dict[str, Any]:
        self.calls.append({"method": "set_server_nickname", "guild_id": guild_id, "discord_user_id": str(discord_user_id)})
        self.nickname_changes[str(discord_user_id)] = str(nickname)
        return {"id": str(discord_user_id), "display_name": str(nickname)}

    async def send_message(self, guild_id: str, channel_id: str, content: str, **kwargs: Any) -> dict[str, Any]:
        message = {"guild_id": str(guild_id), "channel_id": str(channel_id), "content": str(content), "metadata": deepcopy(kwargs)}
        self.calls.append({"method": "send_message", "guild_id": str(guild_id), "channel_id": str(channel_id)})
        self.sent_messages.append(message)
        return {"id": f"fixture-message-{len(self.sent_messages)}", **message}

    async def close(self) -> None:
        return None


class FakeWorkspaceAIAdapter:
    """AIProvider-compatible fake that never stores the supplied API key."""

    def __init__(self, provider_type: str, *, payload: dict[str, Any] | None = None, error: Exception | None = None):
        if provider_type not in {"gemini", "openai"}:
            raise ValueError("Fake workspace AI provider must be gemini or openai.")
        self.provider_type = provider_type
        self.payload = deepcopy(payload or (gemini_fixture() if provider_type == "gemini" else openai_fixture()))
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def complete(self, *, api_key: str, model: str, prompt: str, timeout_seconds: int) -> FakeAICompletion:
        self.calls.append({"model": str(model), "prompt": str(prompt), "timeout_seconds": int(timeout_seconds), "api_key_present": bool(api_key)})
        if self.error:
            raise self.error
        raw = self.payload["completion"]
        return FakeAICompletion(
            text=str(raw.get("text", "")),
            input_tokens=raw.get("input_tokens"),
            output_tokens=raw.get("output_tokens"),
        )


def make_startgg_adapter(*, payload: dict[str, Any] | None = None, client: FakeStartGGClient | None = None, provider_account_id: str = "fixture-startgg-account") -> Any:
    """Build the real Start.gg wrapper around the fake transport."""

    from backend.core.providers.startgg import StartGGProvider

    return StartGGProvider(client=client or FakeStartGGClient(payload, provider_account_id=provider_account_id), provider_account_id=provider_account_id)


def make_challonge_adapter(*, payload: dict[str, Any] | None = None, client: FakeChallongeClient | None = None, provider_account_id: str = "fixture-challonge-account") -> Any:
    """Build the real Challonge wrapper around the fake transport."""

    from backend.core.providers.challonge import ChallongeProvider

    return ChallongeProvider(client=client or FakeChallongeClient(payload, account_id=provider_account_id), provider_account_id=provider_account_id)


def make_discord_adapter(*, payload: dict[str, Any] | None = None) -> FakeDiscordAdapter:
    return FakeDiscordAdapter(payload)


def make_gemini_adapter(*, payload: dict[str, Any] | None = None, error: Exception | None = None) -> FakeWorkspaceAIAdapter:
    return FakeWorkspaceAIAdapter("gemini", payload=payload, error=error)


def make_openai_adapter(*, payload: dict[str, Any] | None = None, error: Exception | None = None) -> FakeWorkspaceAIAdapter:
    return FakeWorkspaceAIAdapter("openai", payload=payload, error=error)
