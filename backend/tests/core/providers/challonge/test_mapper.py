from backend.core.contracts import ProviderEntrant, ProviderSetState
from backend.core.providers.challonge.mapper import map_match


def _match(state="pending", *, p1="p1", p2="p2", revision="7", updated_at="2026-09-04T10:00:00Z"):
    points = []
    if p1:
        points.append({"participant_id": p1})
    if p2:
        points.append({"participant_id": p2})
    return {
        "id": "match-1",
        "attributes": {
            "state": state,
            "round": 1,
            "points_by_participant": points,
            "updated_at": updated_at,
            "revision": revision,
        },
    }


def test_mapper_preserves_raw_state_revision_and_two_resolved_sides():
    mapped = map_match(
        _match("open"), "18449397", {"p1": ProviderEntrant("p1", "Alpha"), "p2": ProviderEntrant("p2", "Bravo")}, "fnc-jo"
    )

    assert mapped.id == "challonge:fnc-jo:18449397:match-1"
    assert mapped.provider_set_id == "match-1"
    assert mapped.provider_state_raw == "open"
    assert mapped.state is ProviderSetState.NOT_STARTED
    assert mapped.provider_revision == "7"
    assert mapped.provider_updated_at == "2026-09-04T10:00:00Z"
    assert mapped.entrant1.name == "Alpha" and mapped.entrant2.name == "Bravo"


def test_mapper_handles_pending_complete_bye_and_unresolved_opponent_without_inventing_a_player():
    people = {"p1": ProviderEntrant("p1", "Alpha"), "p2": ProviderEntrant("p2", "Bravo")}
    pending = map_match(_match("pending"), "1", people)
    complete = map_match(_match("complete"), "1", people)
    bye = map_match(_match("bye", p2=None), "1", people)

    assert pending.state is ProviderSetState.NOT_STARTED
    assert complete.state is ProviderSetState.COMPLETE
    assert bye.state is ProviderSetState.INVALID
    assert bye.entrant1.name == "Alpha" and bye.entrant2 is None


def test_mapper_reads_the_latest_score_from_v21_score_arrays():
    people = {"p1": ProviderEntrant("p1", "Alpha"), "p2": ProviderEntrant("p2", "Bravo")}
    item = _match("complete")
    item["attributes"]["points_by_participant"] = [
        {"participant_id": "p1", "scores": [1, 2]},
        {"participant_id": "p2", "scores": [0, 0]},
    ]

    mapped = map_match(item, "1", people)

    assert (mapped.entrant1_score, mapped.entrant2_score) == (2, 0)
