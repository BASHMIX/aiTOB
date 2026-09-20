from backend.core.legacy_player_adapter import canonical_player_projection, legacy_player_projection


def test_prefix_and_gamertag_are_canonical_with_legacy_aliases_at_boundary():
    canonical = canonical_player_projection({"discord_id": "123", "team": "TAG", "gamer_tag": "Player"})
    assert canonical["prefix"] == "TAG" and canonical["gamertag"] == "Player"
    assert "team" not in canonical and "gamer_tag" not in canonical
    assert legacy_player_projection(canonical)["team"] == "TAG"
