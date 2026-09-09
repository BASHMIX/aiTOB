from __future__ import annotations
from backend.core.contracts import ProviderEntrant, ProviderSet, ProviderTournament, ProviderEvent
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
