from backend.core.tournament_brand import project_tournament_brand, validate_brand_patch
from backend.core.tournament_operating_profile import expand_preset, unfinished_match_stop_reached, validate_operating_profile
from backend.core.providers.startgg.wave_monitor import project_start_in_wave


def test_brand_local_override_and_provider_fallback():
    result = project_tournament_brand({"name": {"value": "Provider Cup"}, "logo_url": {"value": "https://img"}}, {"display_name": "Local Cup", "accent_color": "#abcdef"})
    assert result.display_name == "Local Cup" and result.provenance["display_name"] == "local"
    assert result.logo_url == "https://img"


def test_operating_presets_and_stop_threshold():
    manual = expand_preset("manual")
    assisted = validate_operating_profile({"preset_key": "assisted", "automatic_call_stop_threshold": 2})
    assert manual.automatic_calls_enabled is False
    assert assisted.automatic_calls_enabled is True
    assert unfinished_match_stop_reached(2, assisted)


def test_wave_projection_truthful_states():
    assert project_start_in_wave("verified_enabled")["monitoring_state"] == "awaiting_bracket_start"
    assert project_start_in_wave("unknown", organizer_confirmed=True, bracket_started=True)["monitoring_mode"] == "organizer_confirmed"
