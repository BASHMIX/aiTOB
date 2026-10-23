import pytest
from backend.core.tournament_format import format_to_best_of, best_of_to_format, resolve_match_best_of


def test_format_to_best_of():
    assert format_to_best_of("ft2") == 3
    assert format_to_best_of("ft3") == 5
    assert format_to_best_of("ft4") == 7
    assert format_to_best_of("ft5") == 9
    assert format_to_best_of("invalid", default=3) == 3


def test_best_of_to_format():
    assert best_of_to_format(3) == "ft2"
    assert best_of_to_format(5) == "ft3"
    assert best_of_to_format(7) == "ft4"
    assert best_of_to_format(9) == "ft5"
    assert best_of_to_format(1) == "ft1"
    assert best_of_to_format(0) == "ft2"


def test_resolve_match_best_of_finals_only():
    # Regular rounds remain default FT2
    assert resolve_match_best_of("Winners Round 1", "ft2", "finals_only", "ft3") == 3
    assert resolve_match_best_of("Losers Round 3", "ft2", "finals_only", "ft3") == 3
    assert resolve_match_best_of("Winners Quarter-Final", "ft2", "finals_only", "ft3") == 3
    assert resolve_match_best_of("Winners Semi-Final", "ft2", "finals_only", "ft3") == 3

    # Finals upgrade to FT3
    assert resolve_match_best_of("Winners Final", "ft2", "finals_only", "ft3") == 5
    assert resolve_match_best_of("Losers Final", "ft2", "finals_only", "ft3") == 5
    assert resolve_match_best_of("Grand Final", "ft2", "finals_only", "ft3") == 5
    assert resolve_match_best_of("Grand Final Reset", "ft2", "finals_only", "ft3") == 5


def test_resolve_match_best_of_top8_finals():
    # Regular early rounds remain default FT2
    assert resolve_match_best_of("Winners Round 1", "ft2", "top8_finals", "ft3") == 3
    assert resolve_match_best_of("Losers Round 2", "ft2", "top8_finals", "ft3") == 3

    # Top 8 / Semis / Finals upgrade to FT3
    assert resolve_match_best_of("Top 8", "ft2", "top8_finals", "ft3") == 5
    assert resolve_match_best_of("Winners Semi-Final", "ft2", "top8_finals", "ft3") == 5
    assert resolve_match_best_of("Losers Semi-Final", "ft2", "top8_finals", "ft3") == 5
    assert resolve_match_best_of("Winners Final", "ft2", "top8_finals", "ft3") == 5
    assert resolve_match_best_of("Losers Final", "ft2", "top8_finals", "ft3") == 5
    assert resolve_match_best_of("Grand Final", "ft2", "top8_finals", "ft3") == 5


def test_resolve_match_best_of_disabled():
    # When disabled, all rounds remain default FT2
    assert resolve_match_best_of("Winners Round 1", "ft2", "disabled", "ft3") == 3
    assert resolve_match_best_of("Winners Final", "ft2", "disabled", "ft3") == 3
    assert resolve_match_best_of("Grand Final", "ft2", "disabled", "ft3") == 3


if __name__ == "__main__":
    test_format_to_best_of()
    test_best_of_to_format()
    test_resolve_match_best_of_finals_only()
    test_resolve_match_best_of_top8_finals()
    test_resolve_match_best_of_disabled()
    print("ALL 5 TESTS PASSED SUCCESSFULLY!")
