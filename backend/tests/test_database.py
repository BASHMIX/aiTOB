import pytest
from backend.core.database import should_bot_manage_match

def test_should_bot_manage_match_empty_or_off():
    # Empty strings and "off" should return False
    assert should_bot_manage_match("", "", "") == False
    assert should_bot_manage_match("Grand Final", "Top 8", "off") == False
    assert should_bot_manage_match("Round 1", "Pools", "OFF") == False
    assert should_bot_manage_match(None, None, None) == False

def test_should_bot_manage_match_all_or_on():
    # "all" or "on" should return True regardless of round/phase
    assert should_bot_manage_match("", "", "all") == True
    assert should_bot_manage_match("Grand Final", "Top 8", "on") == True
    assert should_bot_manage_match("Round 1", "Pools", "ALL") == True
    assert should_bot_manage_match("Round 1", "Pools", "ON") == True

def test_should_bot_manage_match_top8_limit():
    # True if not Top 8
    assert should_bot_manage_match("Round 1", "Pools", "top8") == True
    assert should_bot_manage_match("Winners Quarter-Final", "Bracket", "top8") == False

    # False if Top 8
    assert should_bot_manage_match("Grand Final", "Bracket", "top8") == False
    assert should_bot_manage_match("Winners Semi-Final", "Bracket", "top8") == False
    assert should_bot_manage_match("Round 1", "Top 8", "top8") == False
    assert should_bot_manage_match("Round 1", "Top8", "top8") == False
    assert should_bot_manage_match("Losers Quarter-Final", "Top 32", "top8") == False

def test_should_bot_manage_match_top16_limit():
    # True if not Top 16
    assert should_bot_manage_match("Round 1", "Pools", "top16") == True
    assert should_bot_manage_match("Round 2", "Bracket", "top16") == True

    # False if Top 16 or Top 8
    assert should_bot_manage_match("Round 1", "Top 16", "top16") == False
    assert should_bot_manage_match("Round 1", "Top16", "top16") == False
    assert should_bot_manage_match("Round 1", "Top 8", "top16") == False
    assert should_bot_manage_match("Round 1", "Top8", "top16") == False
    assert should_bot_manage_match("Grand Final", "Bracket", "top16") == False
    assert should_bot_manage_match("Winners Semi-Final", "Bracket", "top16") == False
    assert should_bot_manage_match("Winners Quarter-Final", "Bracket", "top16") == False

def test_should_bot_manage_match_custom_limit():
    # Should match custom limits in phase groups
    assert should_bot_manage_match("Round 1", "Top 32", "Top 32") == True
    assert should_bot_manage_match("Round 1", "Top 32", "top 32") == True
    assert should_bot_manage_match("Round 1", "Pools", "Top 32") == True # Default is True
    assert should_bot_manage_match("Round 1", "Pools", "pools") == True

def test_should_bot_manage_match_none_handling():
    # Function should handle None values gracefully
    assert should_bot_manage_match(None, "Pools", "top8") == True
    assert should_bot_manage_match("Round 1", None, "top8") == True
    assert should_bot_manage_match("Grand Final", None, "top8") == False
    assert should_bot_manage_match(None, "Top 8", "top8") == False
