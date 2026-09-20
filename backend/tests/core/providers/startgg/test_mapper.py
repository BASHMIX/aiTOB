import pytest
from backend.core.providers.startgg.mapper import map_stream, map_set, map_tournament, map_entrant
from backend.core.contracts.tournament_types import ProviderStream, ProviderSetState

def test_map_stream_none():
    assert map_stream(None) is None

def test_map_stream_empty_dict():
    assert map_stream({}) is None

def test_map_stream_no_id():
    assert map_stream({"streamName": "Test Stream"}) is None

def test_map_stream_missing_name():
    raw = {"id": 123, "streamSource": "TWITCH"}
    stream = map_stream(raw)
    assert stream is not None
    assert stream.id == "123"
    assert stream.name == "Unnamed Stream"
    assert stream.source == "TWITCH"
    assert stream.game is None

def test_map_stream_falsy_name():
    raw = {"id": 123, "streamName": "", "streamSource": "TWITCH"}
    stream = map_stream(raw)
    assert stream is not None
    assert stream.id == "123"
    assert stream.name == "Unnamed Stream"
    assert stream.source == "TWITCH"
    assert stream.game is None

def test_map_stream_full():
    raw = {
        "id": 456,
        "streamName": "Main Stage",
        "streamSource": "TWITCH",
        "streamGame": "Super Smash Bros. Melee"
    }
    stream = map_stream(raw)
    assert stream is not None
    assert stream.id == "456"
    assert stream.name == "Main Stage"
    assert stream.source == "TWITCH"
    assert stream.game == "Super Smash Bros. Melee"


def test_map_set_keeps_raw_provider_state_separate_from_canonical_state():
    mapped = map_set({
        "id": 123, "state": 3, "winnerId": 456,
        "completedAt": "2026-09-15T10:00:00Z",
        "fullRoundText": "Winners Round 1", "identifier": "A",
        "slots": [{"entrant": {"id": 11, "name": "Alpha"}}, {"entrant": {"id": 22, "name": "Bravo"}}],
    }, event_id="event-1", event_name="FNC")

    assert mapped.state is ProviderSetState.COMPLETE
    assert mapped.provider_state_raw == "3"
    assert mapped.provider_set_id == "123"
    assert mapped.winner_id == "456"
    assert mapped.provider_updated_at == "2026-09-15T10:00:00Z"


def test_map_tournament_preserves_provider_metadata_for_setup_review():
    mapped = map_tournament({
        "id": 7, "name": "Fixture", "startAt": 1_757_920_000, "state": 2,
        "events": [], "streams": [],
    })

    assert mapped.state == "2"
    assert mapped.starts_at and mapped.starts_at.startswith("2025-")


def test_map_entrant_does_not_infer_prefix_from_provider_name():
    mapped = map_entrant({
        "id": "entrant-1",
        "name": "FNC | BASHMIX",
        "participants": [{
            "user": {"id": "user-1"},
            "player": {"prefix": "FNC", "gamerTag": "BASHMIX"},
        }],
    })

    assert mapped is not None
    assert mapped.name == "FNC | BASHMIX"
    assert mapped.prefix == "FNC"
    assert mapped.gamertag == "BASHMIX"


def test_map_entrant_keeps_compound_name_when_provider_has_no_prefix():
    mapped = map_entrant({
        "id": "entrant-2",
        "name": "FNC | BASHMIX",
        "participants": [{"user": {"id": "user-2"}}],
    })

    assert mapped is not None
    assert mapped.name == "FNC | BASHMIX"
    assert mapped.prefix is None
    assert mapped.gamertag is None


def test_map_entrant_reads_optional_country_from_user_location():
    mapped = map_entrant({
        "id": "entrant-3",
        "name": "BASHMIX",
        "participants": [{"user": {"id": "user-3", "location": {"country": "Jordan"}}}],
    })

    assert mapped is not None
    assert mapped.country == "Jordan"
