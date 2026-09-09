import pytest

from backend.core.providers.challonge.locator import parse_locator


@pytest.mark.parametrize("value,subdomain,expected", [
    ("18449397", None, ("18449397", None, "18449397")),
    ("https://challonge.com/AP6FJ0K1/", None, (None, None, "ap6fj0k1")),
    ("https://fnc-jo.challonge.com/ap6fj0k1", None, (None, "fnc-jo", "ap6fj0k1")),
    ("18449397@fnc-jo", None, ("18449397", "fnc-jo", "18449397")),
    ("ap6fj0k1", "fnc-jo", (None, "fnc-jo", "ap6fj0k1")),
])
def test_locator_normalizes_numeric_url_subdomain_and_legacy_forms(value, subdomain, expected):
    locator = parse_locator(value, subdomain)

    assert (locator.tournament_id, locator.subdomain, locator.resource) == expected


@pytest.mark.parametrize("value", [
    "https://user:secret@challonge.com/ap6fj0k1",
    "https://challonge.com/ap6fj0k1?api_key=secret",
    "https://evilchallonge.com/ap6fj0k1",
    "https://example.com/ap6fj0k1",
    "ftp://challonge.com/ap6fj0k1",
])
def test_locator_rejects_unsafe_or_unknown_urls_before_network(value):
    with pytest.raises(ValueError):
        parse_locator(value)


def test_same_url_variants_share_one_safe_coordination_key():
    first = parse_locator("https://FNC-JO.challonge.com/AP6FJ0K1/")
    second = parse_locator("fnc-jo.challonge.com/ap6fj0k1")

    assert first.coordination_key == second.coordination_key == "slug:fnc-jo:ap6fj0k1"
