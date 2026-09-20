from backend.core.contracts.tournament_types import ProviderEntrant, ProviderSet, ProviderSetState
from backend.core.database import apply_player_overrides_to_match
from backend.core.broadcast_projection import apply_tournament_entrant_metadata
from backend.core.provider_serialization import serialize_provider_set
from backend.core.providers.startgg.mapper import map_set


def test_player_override_projection_populates_every_broadcast_identity_field():
    match = {
        "set_id": "set-1",
        "p1_entrant_id": "entrant-1",
        "p1_name": "Provider name",
        "p1_avatar": "provider-avatar",
        "p1_team": "OLD",
        "p2_entrant_id": "entrant-2",
        "p2_name": "Player 2",
    }
    overrides = {
        "entrant-1": {
            "name": "Broadcast name",
            "prefix": "FNC",
            "country": "JO",
            "cfn": "FNC-BASH",
            "avatar_url": "https://cdn.example/avatar.png",
            "character": "Juri",
            "character_id": "2282",
            "character_image_url": "https://cdn.example/juri.png",
        }
    }

    projected = apply_player_overrides_to_match(match, overrides)

    assert projected["p1_name"] == "Broadcast name"
    assert projected["p1_avatar"] == "https://cdn.example/avatar.png"
    assert projected["p1_prefix"] == "FNC"
    assert projected["p1_team"] == "FNC"  # Compatibility for old layouts.
    assert projected["p1_country"] == "JO"
    assert projected["p1_cfn"] == "FNC-BASH"
    assert projected["p1_character"] == "Juri"
    assert projected["p1_character_id"] == "2282"
    assert projected["p1_character_image"] == "https://cdn.example/juri.png"
    assert match["p1_name"] == "Provider name"  # Projection is side-effect free.


def test_startgg_set_mapping_and_serialization_preserve_prefix_country_and_cfn():
    provider_set = map_set(
        {
            "id": "set-1",
            "state": 1,
            "slots": [
                {
                    "entrant": {
                        "id": "entrant-1",
                        "name": "FNC | Bashmix",
                        "participants": [
                            {
                                "prefix": "FNC",
                                "gamerTag": "Bashmix",
                                "connectedAccounts": {"capcom": {"value": "BASH-CFN"}},
                                "user": {
                                    "id": "user-1",
                                    "location": {"country": "JO"},
                                    "images": [{"type": "profile", "url": "https://cdn.example/p1.png"}],
                                },
                            }
                        ],
                    }
                }
            ],
        },
        event_id="event-sf6",
        event_name="Street Fighter 6",
    )

    payload = serialize_provider_set(provider_set)

    assert payload["p1_prefix"] == "FNC"
    assert payload["p1_country"] == "JO"
    assert payload["p1_cfn"] == "BASH-CFN"
    assert payload["p1_avatar"] == "https://cdn.example/p1.png"


def test_provider_serializer_keeps_profile_fields_provider_neutral():
    provider_set = ProviderSet(
        id="challonge:set-1",
        state=ProviderSetState.NOT_STARTED,
        entrant1=ProviderEntrant(
            id="entrant-1", name="Player", prefix="TAG", country="IQ", cfn="CFN-ID"
        ),
    )

    payload = serialize_provider_set(provider_set)

    assert payload["p1_prefix"] == "TAG"
    assert payload["p1_country"] == "IQ"
    assert payload["p1_cfn"] == "CFN-ID"


def test_saved_tournament_metadata_fills_missing_preview_identity_fields():
    match = {
        "set_id": "preview-1",
        "event_id": None,
        "p1_entrant_id": "entrant-1",
        "p1_name": "FNC | Bashmix",
        "p1_prefix": None,
        "p1_country": None,
        "p1_cfn": None,
        "p1_avatar": None,
    }
    tournament = {
        "raw_data": """{
          "events": [{
            "id": "event-sf6",
            "entrants": {"nodes": [{
              "id": "entrant-1",
              "name": "FNC | Bashmix",
              "prefix": "FNC",
              "country": "Jordan",
              "cfn": "56f18969",
              "participants": [{"user": {"images": [{"type": "profile", "url": "https://cdn.example/bash.png"}]}}]
            }]}
          }]
        }"""
    }

    projected = apply_tournament_entrant_metadata(match, tournament)

    assert projected["p1_prefix"] == "FNC"
    assert projected["p1_country"] == "Jordan"
    assert projected["p1_cfn"] == "56f18969"
    assert projected["p1_avatar"] == "https://cdn.example/bash.png"
    assert match["p1_country"] is None


def test_saved_tournament_metadata_never_overwrites_fresher_set_values():
    match = {
        "p1_entrant_id": "entrant-1",
        "p1_prefix": "NEW",
        "p1_country": "Iraq",
        "p1_cfn": "NEW-CFN",
    }
    tournament = {
        "raw_data": """{"events": [{"entrants": {"nodes": [{
          "id": "entrant-1", "prefix": "OLD", "country": "Jordan", "cfn": "OLD-CFN"
        }]}}]}"""
    }

    projected = apply_tournament_entrant_metadata(match, tournament)

    assert projected["p1_prefix"] == "NEW"
    assert projected["p1_country"] == "Iraq"
    assert projected["p1_cfn"] == "NEW-CFN"
