from backend.core.providers.challonge.entrants import map_entrant as map_challonge
from backend.core.providers.startgg.entrants import map_entrant as map_startgg


def test_startgg_keeps_prefix_and_gamertag_separate_from_player_profile():
    entrant = map_startgg({
        "id": "e1", "name": "FOX | Alpha",
        "participants": [{"user": {"id": "u1", "player": {"prefix": "FOX", "gamerTag": "Alpha"}}}],
    })
    assert entrant.prefix == "FOX"
    assert entrant.gamertag == "Alpha"
    assert entrant.provider_user_id == "u1"


def test_challonge_uses_explicit_fields_and_only_compatibility_parsing():
    entrant = map_challonge({"id": "p1", "attributes": {"prefix": "FOX", "gamertag": "Alpha"}})
    assert entrant.prefix == "FOX"
    assert entrant.gamertag == "Alpha"
    parsed = map_challonge({"id": "p2", "attributes": {"name": "FOX | Bravo"}})
    assert parsed.prefix == "FOX"
    assert parsed.gamertag == "Bravo"
