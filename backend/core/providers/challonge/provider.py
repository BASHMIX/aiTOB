from __future__ import annotations
import time
from datetime import UTC, datetime
from backend.core.contracts import (
    ITournamentProvider, ITournamentProviderV2, ProviderSetState, ProviderSetResult,
    ProviderEntrant, ProviderActionKind, ProviderCapabilitiesV2, ProviderCapability,
    ProviderSnapshotRequestV2, ProviderSnapshotV2, SnapshotScope, SyncCostClass,
)
from backend.core.provider_feature_flags import get_provider_feature_flags
from .client import ChallongeClient, ChallongeError
from .locator import parse_locator
from .mapper import map_tournament, map_match
from .state_map import map_state
from .forfeit_policy import ForfeitPolicy

class ChallongeProvider(ITournamentProvider, ITournamentProviderV2):
    def __init__(self, client: ChallongeClient | None = None, *, provider_account_id: str = "default"):
        self._client = client or ChallongeClient(account_id=provider_account_id)
        self.provider_account_id = provider_account_id
        self._participants_cache: dict[str, tuple[float, list[dict]]] = {}
    @property
    def provider_name(self) -> str: return "challonge"
    @property
    def provider_type(self) -> str: return "challonge"
    @property
    def capabilities_v2(self) -> ProviderCapabilitiesV2:
        flags = get_provider_feature_flags()
        unavailable = ProviderCapability(ProviderActionKind.UNAVAILABLE, "Challonge mutations are disabled until their later release gates.")
        score = (
            ProviderCapability(ProviderActionKind.REMOTE)
            if flags.challonge_score_commands_enabled
            else unavailable
        )
        forfeit = (
            ProviderCapability(ProviderActionKind.REMOTE)
            if flags.challonge_score_commands_enabled and flags.challonge_dq_commands_enabled
            else ProviderCapability(ProviderActionKind.UNAVAILABLE, ForfeitPolicy.availability_reason())
        )
        return ProviderCapabilitiesV2(
            actions={
                "fetch_bracket_structure": ProviderCapability(ProviderActionKind.REMOTE),
                "fetch_participants": ProviderCapability(ProviderActionKind.REMOTE),
                "fetch_match_updates": ProviderCapability(ProviderActionKind.REMOTE),
                "report_score": score,
                "report_forfeit": forfeit,
                "reset_match": unavailable, "reopen_match": unavailable,
                "mark_called": ProviderCapability(ProviderActionKind.LOCAL, "Challonge has no per-match call."),
                "mark_in_progress": ProviderCapability(ProviderActionKind.LOCAL, "Hub workflow owns local start."),
                "assign_stream": ProviderCapability(ProviderActionKind.LOCAL, "Stations are Hub-owned."),
            },
            supports_conditional_requests=True,
            supports_targeted_match_fetch=False,
            supports_remote_revision=True,
            supports_idempotency=False,
        )
    def _split_reference(self, value: str) -> tuple[str, str | None]:
        raw = str(value).replace("challonge:", "", 1)
        return tuple(raw.split("@", 1)) if "@" in raw else (raw, None)
    def _split_set(self, set_id: str) -> tuple[str, str, str | None]:
        parts = str(set_id).split(":")
        if parts[:1] != ["challonge"]: raise ChallongeError("Invalid local Challonge match reference.")
        if len(parts) == 4: return parts[2], parts[3], parts[1]
        if len(parts) == 3: return parts[1], parts[2], None  # saved before community-aware keys
        raise ChallongeError("Invalid local Challonge match reference.")
    async def _participants(self, tournament_id: str, community: str | None) -> list[dict]:
        """Participant names change far less often than match state; cache them.

        This keeps a live Challonge poll to one request in the common case,
        which is essential for API keys with a small monthly allowance.
        """
        key = f"{community or ''}:{tournament_id}"
        cached = self._participants_cache.get(key)
        if cached and time.monotonic() - cached[0] < 1800:
            return cached[1]
        people = await self._client.participants(tournament_id, community)
        self._participants_cache[key] = (time.monotonic(), people)
        return people

    async def fetch_snapshot_v2(self, request: ProviderSnapshotRequestV2) -> ProviderSnapshotV2:
        """Read only the provider data needed for one declared snapshot scope.

        Challonge currently has no proven per-match endpoint in this integration, so
        narrow match scopes use a paginated match read and return coverage only for
        the explicitly requested entities.  It never performs a mutation.
        """
        if request.provider_type != "challonge":
            raise ValueError("Challonge adapter received another provider request.")
        tournament_id, community = self._split_reference(request.tournament_id)
        observed_at = datetime.now(UTC).isoformat()
        if request.scope is SnapshotScope.TOURNAMENT_METADATA:
            tournament = await self._client.get_tournament(tournament_id, community)
            return ProviderSnapshotV2(request=request, payload={"tournament": tournament}, observed_at=observed_at,
                                      covered_scopes=frozenset({SnapshotScope.TOURNAMENT_METADATA}), cost_class=SyncCostClass.CHEAP)
        participants_raw = await self._participants(tournament_id, community)
        participants = [ProviderEntrant(id=str(p.get("id")), name=str((p.get("attributes") or {}).get("name") or (p.get("attributes") or {}).get("display_name") or f"Player {p.get('id')}")) for p in participants_raw]
        if request.scope is SnapshotScope.PARTICIPANTS:
            return ProviderSnapshotV2(request=request, payload={"participants": participants}, observed_at=observed_at,
                                      covered_scopes=frozenset({SnapshotScope.PARTICIPANTS}), cost_class=SyncCostClass.NORMAL)
        matches = await self._client.matches(tournament_id, community)
        by_id = {person.id: person for person in participants}
        sets = [map_match(item, tournament_id, by_id, community) for item in matches]
        covered_entities = frozenset()
        if request.scope in {SnapshotScope.SINGLE_MATCH, SnapshotScope.RESULT_VERIFICATION}:
            if not request.entity_ids:
                raise ValueError("A targeted Challonge snapshot requires a match ID.")
            wanted = {str(item).split(":")[-1] for item in request.entity_ids}
            sets = [item for item in sets if item.provider_set_id in wanted]
            covered_entities = frozenset(str(item) for item in request.entity_ids)
        covered = {request.scope}
        if request.scope is SnapshotScope.FULL_SNAPSHOT:
            covered.update({SnapshotScope.PARTICIPANTS, SnapshotScope.BRACKET_STRUCTURE, SnapshotScope.ACTIVE_MATCHES, SnapshotScope.FULL_SNAPSHOT})
        revisions = [item.provider_revision for item in sets if item.provider_revision]
        remote_revision = None
        if revisions:
            remote_revision = str(max((int(item) for item in revisions if str(item).isdigit()), default=-1))
            if remote_revision == "-1":
                remote_revision = max(revisions)
        return ProviderSnapshotV2(request=request, payload={"participants": participants, "sets": sets}, observed_at=observed_at,
                                  covered_scopes=frozenset(covered), covered_entity_ids=covered_entities,
                                  revision=remote_revision, cost_class=SyncCostClass.NORMAL)

    async def execute_remote_command_v2(self, command):
        """Phase 5 is read-only: command execution remains a later ledger concern."""
        from backend.core.contracts import ProviderCommandResultV2, ProviderCommandState
        return ProviderCommandResultV2(
            command_id=command.command_id,
            state=ProviderCommandState.NEEDS_REVIEW,
            error_message="Challonge remote commands are disabled in Phase 5.",
        )
    async def resolve(self, identifier: str, subdomain: str | None = None) -> dict:
        loc = parse_locator(identifier, subdomain)
        # The v2.1 resource endpoint accepts either the numeric id or the URL
        # slug. Resolving a pasted Challonge URL directly avoids listing every
        # tournament in a community (and wasting scarce API quota) first.
        resource_id = loc.tournament_id or loc.slug
        raw = await self._client.get_tournament(resource_id or "", loc.subdomain)
        if not raw: raise ChallongeError("No accessible Challonge tournament matched that reference.")
        a = raw.get("attributes") or {}; tid = str(raw.get("id") or a.get("id"))
        return {
            "provider_type": "challonge",
            "provider_account_id": self.provider_account_id,
            "provider_tournament_id": tid,
            "name": a.get("name") or f"Challonge {tid}",
            "subdomain": loc.subdomain,
            "url_slug": a.get("url") or a.get("url_slug"),
            "state": a.get("state"),
            "format": a.get("tournament_type"),
            "locator_key": loc.coordination_key,
        }
    async def fetch_tournament(self, slug_or_id: str):
        tid, community = self._split_reference(slug_or_id)
        raw = await self._client.get_tournament(tid, community); people = await self._participants(tid, community)
        return map_tournament(raw, people) if raw else None
    async def fetch_sets(self, slug_or_id: str, **_):
        tid, community = self._split_reference(slug_or_id)
        people, matches = await self._participants(tid, community), await self._client.matches(tid, community)
        from .mapper import attrs
        by_id = {
            str(p.get("id")): ProviderEntrant(
                id=str(p.get("id")),
                name=str(attrs(p).get("name") or attrs(p).get("display_name") or f"Player {p.get('id')}")
            )
            for p in people
        }
        return [map_match(m, tid, by_id, community) for m in matches]
    async def fetch_set_state(self, set_id: str):
        tid, mid, community = self._split_set(set_id); matches = await self._client.matches(tid, community)
        from .mapper import attrs
        hit = next((m for m in matches if str(m.get("id")) == mid), None)
        return map_state(attrs(hit).get("state")) if hit else None
    async def fetch_set_entrant_order(self, set_id: str):
        tid, mid, community = self._split_set(set_id); matches = await self._client.matches(tid, community)
        hit = next((m for m in matches if str(m.get("id")) == mid), {})
        from .mapper import attrs
        a = attrs(hit); return [str(x) for x in (a.get("player1_id"), a.get("player2_id")) if x]
    async def report_score(self, set_id, winner_id, entrant1_id, entrant2_id, entrant1_score, entrant2_score):
        if not get_provider_feature_flags().challonge_score_commands_enabled:
            return ProviderSetResult(False, set_id, error_message="Challonge score reporting is disabled.")
        if not entrant1_id or not entrant2_id or winner_id not in {str(entrant1_id), str(entrant2_id)}:
            return ProviderSetResult(False, set_id, error_message="Challonge score has invalid entrant evidence.")
        if int(entrant1_score) == int(entrant2_score):
            return ProviderSetResult(False, set_id, error_message="Challonge scores cannot be tied.")
        try:
            tournament_id, match_id, community = self._split_set(set_id)
            # Challonge v2.1 accepts score submissions through match entries.
            # points_by_participant is response-only projection data: sending
            # it can return HTTP 200 while changing nothing.
            updated = await self._client.update_match(tournament_id, match_id, {
                "match": [
                    {
                        "participant_id": str(entrant1_id),
                        "score_set": str(int(entrant1_score)),
                        "advancing": str(winner_id) == str(entrant1_id),
                    },
                    {
                        "participant_id": str(entrant2_id),
                        "score_set": str(int(entrant2_score)),
                        "advancing": str(winner_id) == str(entrant2_id),
                    },
                ],
            }, community)
            state = map_state((updated.get("attributes") or {}).get("state")) if updated else None
            return ProviderSetResult(True, set_id, new_state=state)
        except ChallongeError as exc:
            return ProviderSetResult(False, set_id, error_message=str(exc))

    async def verify_reported_score(self, set_id: str, *, winner_id: str, entrant1_id: str,
                                    entrant2_id: str, entrant1_score: int, entrant2_score: int):
        """Read a narrow post-mutation snapshot and return explicit result evidence.

        The caller owns retries/backoff. This adapter performs one read-only,
        targeted snapshot and never changes local Hub state.
        """
        tournament_id, _match_id, community = self._split_set(set_id)
        request = ProviderSnapshotRequestV2(
            provider_type="challonge", provider_account_id=self.provider_account_id,
            tournament_id=f"{tournament_id}@{community}" if community else tournament_id,
            scope=SnapshotScope.RESULT_VERIFICATION, entity_ids=frozenset({set_id}),
        )
        snapshot = await self.fetch_snapshot_v2(request)
        target = next((item for item in snapshot.payload.get("sets", []) if item.id == set_id), None)
        if not target:
            return False
        return (
            target.state is ProviderSetState.COMPLETE
            and target.winner_id == str(winner_id)
            and target.entrant1_score == int(entrant1_score)
            and target.entrant2_score == int(entrant2_score)
            and target.entrant1 is not None and target.entrant1.id == str(entrant1_id)
            and target.entrant2 is not None and target.entrant2.id == str(entrant2_id)
        )
    async def report_winner_only(self, set_id, winner_id):
        return await self.report_score(set_id, winner_id, "", "", 1, 0)
    async def start_tournament(self, slug_or_id: str):
        return ProviderSetResult(False, str(slug_or_id), error_message="Challonge lifecycle actions are not enabled in Phase 4.")
    async def mark_in_progress(self, set_id):
        return ProviderSetResult(False, set_id, error_message="Challonge lifecycle actions are not enabled in Phase 4.")
    async def mark_dq(self, set_id, winner_id):
        # DQ has no verified Challonge representation yet. Do not route it
        # through score reporting or fabricate a normal 1-0 result.
        return ProviderSetResult(False, set_id, error_message=ForfeitPolicy.availability_reason())
    async def reset_set(self, set_id):
        return ProviderSetResult(False, set_id, error_message="Challonge reset/reopen is not exposed by this integration.")
    async def close(self): await self._client.close()
