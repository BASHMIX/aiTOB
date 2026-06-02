import pytest
from backend.core.providers.startgg.mapper import map_stream
from backend.core.contracts.tournament_types import ProviderStream

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
