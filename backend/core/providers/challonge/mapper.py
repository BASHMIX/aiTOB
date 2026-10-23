from __future__ import annotations
from backend.core.contracts import (
    ProviderEntrant, ProviderSet, ProviderTournament, ProviderEvent,
    ProviderEventResults, ProviderStandingEntry, ProviderPageMetadata,
)
from .state_map import map_state

def attrs(item: dict) -> dict: return item.get("attributes") or {}

def map_tournament(item: dict, participants: list[dict]) -> ProviderTournament:
    a = attrs(item); tid = str(item.get("id") or a.get("id") or "")
    entrants = [ProviderEntrant(id=str(p.get("id")), name=str(attrs(p).get("name") or attrs(p).get("display_name") or f"Player {p.get('id')}")) for p in participants]
    return ProviderTournament(
        id=tid, name=str(a.get("name") or f"Challonge {tid}"),
        events=[ProviderEvent(id=tid, name=str(a.get("name") or "Main bracket"), game=a.get("game_name"), entrants=entrants)],
        starts_at=a.get("starts_at"), state=a.get("state"),
        group_stage_enabled=bool(a.get("group_stage_enabled")),
    )

def _relationship_id(item: dict, key: str) -> str | None:
    data = ((item.get("relationships") or {}).get(key) or {}).get("data")
    return str(data.get("id")) if isinstance(data, dict) and data.get("id") is not None else None


def _point_participant_ids(attributes: dict) -> list[str]:
    """Read player order from the current v2.1 match response.

    Challonge v2.1 may omit player relationships entirely and instead expose
    the two participants in ``points_by_participant``. Their list order is the
    bracket's player-one/player-two order, including before any score is set.
    """
    ids: list[str] = []
    for point in attributes.get("points_by_participant") or []:
        if not isinstance(point, dict) or point.get("participant_id") is None:
            continue
        participant_id = str(point["participant_id"])
        if participant_id not in ids:
            ids.append(participant_id)
    return ids


def _point_scores(attributes: dict) -> dict[str, int]:
    """Return the v2.1 points recorded for each participant, when present."""
    scores: dict[str, int] = {}
    for point in attributes.get("points_by_participant") or []:
        if not isinstance(point, dict) or point.get("participant_id") is None:
            continue
        value = point.get("score", point.get("points"))
        if value is None:
            series = point.get("scores")
            if isinstance(series, list) and series:
                value = series[-1]
        if value is None:
            continue
        try:
            scores[str(point["participant_id"])] = int(value)
        except (TypeError, ValueError):
            continue
    return scores


def map_match(item: dict, tournament_id: str, by_id: dict[str, ProviderEntrant], community_id: str | None = None) -> ProviderSet:
    a = attrs(item); mid = str(item.get("id") or a.get("id"))
    point_ids = _point_participant_ids(a)
    p1 = _relationship_id(item, "player1") or str(a.get("player1_id") or "") or (point_ids[0] if point_ids else None)
    p2 = _relationship_id(item, "player2") or str(a.get("player2_id") or "") or (point_ids[1] if len(point_ids) > 1 else None)
    round_value = a.get("round")
    group_id = a.get("group_id")
    stage = "Group stage" if group_id else "Final stage" if a.get("has_group_stage") else "Bracket"
    round_name = f"{stage} · Round {round_value}" if round_value is not None else stage
    key = f"challonge:{community_id}:{tournament_id}:{mid}" if community_id else f"challonge:{tournament_id}:{mid}"
    raw_state = str(a.get("state") or "pending").lower()
    scores = _point_scores(a)
    return ProviderSet(id=key, state=map_state(raw_state), round_name=round_name,
                       identifier=str(a.get("identifier") or a.get("suggested_play_order") or mid), phase_group=str(group_id or ""),
                       entrant1=by_id.get(p1 or ""), entrant2=by_id.get(p2 or ""), event_id=str(tournament_id), event_name=stage,
                       provider_set_id=mid, provider_state_raw=raw_state,
                       provider_revision=str(a.get("revision") or a.get("version") or "") or None,
                       provider_updated_at=a.get("updated_at"),
                       winner_id=str(a.get("winner_id")) if a.get("winner_id") is not None else None,
                       entrant1_score=scores.get(p1 or ""), entrant2_score=scores.get(p2 or ""))


def map_challonge_standings(tournament: dict, participants: list[dict]) -> ProviderEventResults:
    """Map Challonge tournament and participants to unified ProviderEventResults."""
    t_attrs = attrs(tournament)
    tid = str(tournament.get("id") or t_attrs.get("id") or "")
    tname = str(t_attrs.get("name") or f"Challonge {tid}")
    raw_state = str(t_attrs.get("state") or "").lower()
    game_name = t_attrs.get("game_name")
    group_stage_enabled = bool(t_attrs.get("group_stage_enabled"))

    warnings: list[str] = []
    is_completed = (raw_state == "complete")

    if raw_state == "awaiting_review":
        is_completed = False
        warnings.append("Tournament is awaiting_review; standings are provisional.")
    elif not is_completed:
        warnings.append(f"Tournament state is '{raw_state}'; standings are provisional.")

    # Parse and validate participant final ranks
    ranked_entries: list[dict] = []
    missing_rank_count = 0

    for p in participants:
        p_attrs = attrs(p)
        pid = str(p.get("id"))
        pname = str(p_attrs.get("name") or p_attrs.get("display_name") or f"Player {pid}").strip()
        final_rank = p_attrs.get("final_rank")

        if final_rank is None:
            missing_rank_count += 1
            continue

        try:
            placement = int(final_rank)
        except (ValueError, TypeError):
            missing_rank_count += 1
            continue

        avatar = p_attrs.get("attached_participatable_portrait_url") or p_attrs.get("icon")
        ranked_entries.append({
            "entrant_id": pid,
            "entrant_name": pname,
            "placement": placement,
            "avatar_url": avatar,
            "raw_payload": p_attrs,
        })

    if missing_rank_count > 0:
        # Challonge deliberately leaves group-only participants without a
        # final_rank in a completed two-stage tournament.  Its v2.1 contract
        # assigns final_rank to every entrant who reached the final stage, so
        # those ranked rows are the authoritative final standings.  A missing
        # rank in a normal bracket (or before completion) is still blocking.
        if raw_state == "complete" and group_stage_enabled and ranked_entries:
            warnings.append(
                f"{missing_rank_count} group-stage-only participant(s) were omitted from final standings."
            )
        else:
            is_completed = False
            warnings.append(f"{missing_rank_count} participant(s) do not have final_rank assigned.")

    # Sort participants by placement ascending, entrant_id ascending
    ranked_entries.sort(key=lambda x: (x["placement"], x["entrant_id"]))

    # Detect ties
    placement_counts: dict[int, int] = {}
    for entry in ranked_entries:
        placement_counts[entry["placement"]] = placement_counts.get(entry["placement"], 0) + 1

    standings: list[ProviderStandingEntry] = []
    for idx, entry in enumerate(ranked_entries, start=1):
        placement = entry["placement"]
        is_tied = placement_counts[placement] > 1
        standings.append(
            ProviderStandingEntry(
                ordinal=idx,
                placement=placement,
                entrant_id=entry["entrant_id"],
                entrant_name=entry["entrant_name"],
                is_tied=is_tied,
                avatar_url=entry["avatar_url"],
                metadata=entry["raw_payload"],
            )
        )

    return ProviderEventResults(
        event_id=tid,
        event_name=tname,
        game_id=None,
        game_name=game_name,
        is_completed=is_completed,
        completion_state_raw=raw_state,
        standings=standings,
        page=ProviderPageMetadata(
            number=1,
            size=len(standings) or 16,
            total_entries=len(standings),
            has_more=False,
            is_complete=True,
        ),
        warnings=warnings,
    )
