from backend.core.registration_identity import (
    detect_gamertag_collisions,
    evaluate_identity,
    normalize_gamertag,
    provider_verification_methods,
)


def test_gamertag_normalization_is_exact_and_unicode_safe():
    assert normalize_gamertag("  Ａlpha   Player ") == "alpha player"
    assert normalize_gamertag("A-LPHA") != normalize_gamertag("alpha")


def test_discord_name_matching_does_not_use_fuzzy_candidates():
    assert evaluate_identity("Alpha", {"username": "alpha"}, "exact_discord_name").matched
    result = evaluate_identity("Alpha", {"username": "alpha_player"}, "exact_discord_name")
    assert result.state == "needs_review"
    assert result.reason_code == "discord_name_mismatch"


def test_collisions_are_returned_without_choosing_first_entrant():
    collisions = detect_gamertag_collisions([
        {"id": "one", "gamertag": "Alpha"},
        {"id": "two", "gamertag": " alpha "},
    ])
    assert len(collisions) == 1
    assert collisions[0].entrant_ids == ("one", "two")


def test_bio_method_is_startgg_only():
    assert "startgg_bio" in provider_verification_methods("startgg", startgg_bio_enabled=True)
    assert "startgg_bio" not in provider_verification_methods("challonge", startgg_bio_enabled=True)
