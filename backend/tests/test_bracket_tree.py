"""Unit tests for Tournament Bracket Tree extractor (Top 8 & Grand Finals Reset)."""
import pytest
from backend.core.bracket_tree import extract_top8_bracket, extract_player_victory_path


def test_extract_top8_standard_startgg():
    raw_sets = [
        # Winners Semis
        {"id": "s1", "fullRoundText": "Winners Semi-Final", "identifier": "A", "p1": "Daigo", "p1_eid": "101", "p2": "Tokido", "p2_eid": "102", "winner_id": "101", "state": 4},
        {"id": "s2", "fullRoundText": "Winners Semi-Final", "identifier": "B", "p1": "Knee", "p1_eid": "103", "p2": "Arslan", "p2_eid": "104", "winner_id": "103", "state": 4},
        # Winners Finals
        {"id": "s3", "fullRoundText": "Winners Final", "identifier": "C", "p1": "Daigo", "p1_eid": "101", "p2": "Knee", "p2_eid": "103", "winner_id": "101", "state": 4},
        # Losers Round 1 (Top 8 Losers)
        {"id": "s4", "fullRoundText": "Losers Round 1", "identifier": "D", "p1": "Punk", "p1_eid": "105", "p2": "MenaRD", "p2_eid": "106", "winner_id": "105", "state": 4},
        {"id": "s5", "fullRoundText": "Losers Round 1", "identifier": "E", "p1": "SonicFox", "p1_eid": "107", "p2": "ProblemX", "p2_eid": "108", "winner_id": "107", "state": 4},
        # Losers Quarters
        {"id": "s6", "fullRoundText": "Losers Quarter-Final", "identifier": "F", "p1": "Tokido", "p1_eid": "102", "p2": "Punk", "p2_eid": "105", "winner_id": "105", "state": 4},
        {"id": "s7", "fullRoundText": "Losers Quarter-Final", "identifier": "G", "p1": "Arslan", "p1_eid": "104", "p2": "SonicFox", "p2_eid": "107", "winner_id": "104", "state": 4},
        # Losers Semis
        {"id": "s8", "fullRoundText": "Losers Semi-Final", "identifier": "H", "p1": "Punk", "p1_eid": "105", "p2": "Arslan", "p2_eid": "104", "winner_id": "104", "state": 4},
        # Losers Finals
        {"id": "s9", "fullRoundText": "Losers Final", "identifier": "I", "p1": "Knee", "p1_eid": "103", "p2": "Arslan", "p2_eid": "104", "winner_id": "104", "state": 4},
        # Grand Finals
        {"id": "s10", "fullRoundText": "Grand Final", "identifier": "J", "p1": "Daigo", "p1_eid": "101", "p2": "Arslan", "p2_eid": "104", "p1_score": 3, "p2_score": 1, "winner_id": "101", "state": 4},
    ]

    result = extract_top8_bracket(raw_sets)
    assert result["has_reset"] is False
    assert result["reset_active"] is False

    matches = result["matches"]
    assert len(matches["winners_semis"]) == 2
    assert matches["winners_finals"]["id"] == "s3"
    assert len(matches["losers_round1"]) == 2
    assert len(matches["losers_quarters"]) == 2
    assert matches["losers_semis"]["id"] == "s8"
    assert matches["losers_finals"]["id"] == "s9"
    assert matches["grand_finals"]["id"] == "s10"
    assert matches["grand_finals_reset"] is None

    # Check (W) and (L) tag verification:
    # Daigo won WF (101) -> (W)
    # Arslan won LF (104) -> (L)
    gf = matches["grand_finals"]
    assert gf["p1"]["bracket_origin"] == "winners"
    assert gf["p1"]["name"] == "Daigo"
    assert gf["p2"]["bracket_origin"] == "losers"
    assert gf["p2"]["name"] == "Arslan"


def test_extract_top8_with_grand_finals_reset():
    raw_sets = [
        {"id": "wf", "fullRoundText": "Winners Final", "p1": "Daigo", "p1_eid": "101", "p2": "Knee", "p2_eid": "103", "winner_id": "101", "state": 4},
        {"id": "lf", "fullRoundText": "Losers Final", "p1": "Knee", "p1_eid": "103", "p2": "Arslan", "p2_eid": "104", "winner_id": "104", "state": 4},
        # GF Set 1 won by Losers finalist (Arslan)
        {"id": "gf1", "fullRoundText": "Grand Final", "p1": "Daigo", "p1_eid": "101", "p2": "Arslan", "p2_eid": "104", "p1_score": 1, "p2_score": 3, "winner_id": "104", "state": 4},
        # GF Set 2 (Reset)
        {"id": "gf2", "fullRoundText": "Grand Final Reset", "p1": "Daigo", "p1_eid": "101", "p2": "Arslan", "p2_eid": "104", "p1_score": 2, "p2_score": 2, "state": 3},
    ]

    result = extract_top8_bracket(raw_sets)
    assert result["has_reset"] is True
    assert result["reset_active"] is True

    matches = result["matches"]
    assert matches["grand_finals"]["id"] == "gf1"
    assert matches["grand_finals_reset"] is not None
    assert matches["grand_finals_reset"]["id"] == "gf2"
    assert matches["grand_finals_reset"]["state"] == "in_progress"

    # Both GF and GF Reset preserve origin tags
    for gf_node in (matches["grand_finals"], matches["grand_finals_reset"]):
        assert gf_node["p1"]["bracket_origin"] == "winners"
        assert gf_node["p2"]["bracket_origin"] == "losers"


def test_extract_top8_challonge_numeric():
    # Challonge format: Round 3 (WF), Round 4 (GF), Round -4 (LF), Round -3 (LSF), Round -2 (LQF), Round -1 (LR1)
    raw_sets = [
        {"id": "c1", "round": "Bracket · Round 2", "p1": "A", "p2": "B"},
        {"id": "c2", "round": "Bracket · Round 3", "p1": "A", "p2": "C", "winner_id": "c-id"},
        {"id": "c3", "round": "Bracket · Round 4", "p1": "C", "p2": "D"},
        {"id": "c4", "round": "Bracket · Round -4", "p1": "D", "p2": "E", "winner_id": "d-id"},
        {"id": "c5", "round": "Bracket · Round -3", "p1": "D", "p2": "F"},
        {"id": "c6", "round": "Bracket · Round -2", "p1": "F", "p2": "G"},
        {"id": "c7", "round": "Bracket · Round -1", "p1": "G", "p2": "H"},
    ]

    result = extract_top8_bracket(raw_sets)
    matches = result["matches"]
    assert matches["grand_finals"]["id"] == "c3"
    assert matches["winners_finals"]["id"] == "c2"
    assert matches["losers_finals"]["id"] == "c4"
    assert matches["losers_semis"]["id"] == "c5"


def test_extract_player_victory_path():
    raw_sets = [
        {"id": "s1", "fullRoundText": "Round 1", "p1": "Punk", "p1_eid": "105", "p1_prefix": "FLY", "p2": "Luffy", "p2_eid": "201", "p1_score": 2, "p2_score": 0, "winner_id": "105"},
        {"id": "s2", "fullRoundText": "Round 1", "p1": "Punk", "p1_eid": "105", "p1_prefix": "FLY", "p2": "Frosssty", "p2_eid": "202", "p1_score": 2, "p2_score": 0, "winner_id": "105"},
        {"id": "s3", "fullRoundText": "Round 2", "p1": "Akutagawa", "p1_eid": "203", "p2": "Punk", "p2_eid": "105", "p1_score": 0, "p2_score": 2, "winner_id": "105"},
        {"id": "s4", "fullRoundText": "Round 3", "p1": "Leshar", "p1_eid": "204", "p2": "Punk", "p2_eid": "105", "p1_score": 0, "p2_score": 2, "winner_id": "105"},
        {"id": "s5", "fullRoundText": "Top 24", "p1": "Punk", "p1_eid": "105", "p1_prefix": "FLY", "p2": "Kobayan", "p2_eid": "205", "p1_score": 2, "p2_score": 0, "winner_id": "105"},
    ]

    res = extract_player_victory_path(raw_sets, player_name="Punk")
    assert res["player_name"] == "Punk"
    assert res["prefix"] == "FLY"
    rounds = res["rounds"]
    assert len(rounds) == 4
    # Check top stage first
    assert rounds[0]["round_label"] == "TOP 24"
    assert len(rounds[0]["matches"]) == 1
    assert rounds[0]["matches"][0]["opponent_name"] == "Kobayan"
    assert rounds[0]["matches"][0]["score"] == "2-0"

    assert rounds[1]["round_label"] == "ROUND 3"
    assert rounds[2]["round_label"] == "ROUND 2"
    assert rounds[3]["round_label"] == "ROUND 1"
    assert len(rounds[3]["matches"]) == 2


def test_extract_player_victory_path_event_id_filtering():
    raw_sets = [
        {"id": "s1", "event_id": "sf6", "fullRoundText": "Round 1", "p1": "Punk", "p1_eid": "105", "p2": "Luffy", "p2_eid": "201", "p1_score": 2, "p2_score": 0, "winner_id": "105"},
        {"id": "s2", "event_id": "tekken", "fullRoundText": "Round 1", "p1": "Punk", "p1_eid": "105", "p2": "Arslan", "p2_eid": "301", "p1_score": 2, "p2_score": 0, "winner_id": "105"},
    ]

    res_sf6 = extract_player_victory_path(raw_sets, player_name="Punk", event_id="sf6")
    assert len(res_sf6["rounds"]) == 1
    assert res_sf6["rounds"][0]["matches"][0]["opponent_name"] == "Luffy"

    res_tekken = extract_player_victory_path(raw_sets, player_name="Punk", event_id="tekken")
    assert len(res_tekken["rounds"]) == 1
    assert res_tekken["rounds"][0]["matches"][0]["opponent_name"] == "Arslan"


def test_extract_player_victory_path_with_gf_reset():
    raw_sets = [
        {"id": "s1", "fullRoundText": "Grand Final", "p1": "Daigo", "p1_eid": "101", "p2": "Punk", "p2_eid": "105", "p1_score": 1, "p2_score": 3, "winner_id": "105"},
        {"id": "s2", "fullRoundText": "Grand Final Reset", "p1": "Daigo", "p1_eid": "101", "p2": "Punk", "p2_eid": "105", "p1_score": 2, "p2_score": 3, "winner_id": "105"},
    ]

    res = extract_player_victory_path(raw_sets, player_name="Punk")
    rounds = res["rounds"]
    assert len(rounds) == 2
    assert rounds[0]["round_label"] == "GF RESET"
    assert rounds[0]["sub_label"] == "RESET"
    assert rounds[0]["main_number"] == "GF"
    assert rounds[1]["round_label"] == "GRAND FINALS"
    assert rounds[1]["sub_label"] == "FINALS"
    assert rounds[1]["main_number"] == "GF"


def test_extract_player_victory_path_infer_winners():
    # Test case where winner_id is None, but progression reveals the winner
    raw_sets = [
        {"id": "s1", "fullRoundText": "Winners Semi-Final", "p1": "Ahmad21", "p1_eid": "1", "p2": "Khalil99", "p2_eid": "2", "state": 4, "aitob_state": "complete", "winner_id": None},
        {"id": "s2", "fullRoundText": "Winners Semi-Final", "p1": "FNCeSports", "p1_eid": "3", "p2": "BASHMIX", "p2_eid": "4", "state": 4, "aitob_state": "complete", "winner_id": None},
        {"id": "s3", "fullRoundText": "Winners Final", "p1": "BASHMIX", "p1_eid": "4", "p2": "Ahmad21", "p2_eid": "1", "state": 4, "aitob_state": "complete", "winner_id": None},
        {"id": "s4", "fullRoundText": "Losers Semi-Final", "p1": "FNCeSports", "p1_eid": "3", "p2": "Khalil99", "p2_eid": "2", "state": 4, "aitob_state": "complete", "winner_id": None},
        {"id": "s5", "fullRoundText": "Losers Final", "p1": "Ahmad21", "p1_eid": "1", "p2": "FNCeSports", "p2_eid": "3", "state": 1, "aitob_state": "not_started", "winner_id": None},
        {"id": "s6", "fullRoundText": "Grand Final", "p1": "BASHMIX", "p1_eid": "4", "p2": "TBD", "p2_eid": None, "state": 1, "aitob_state": "not_started", "winner_id": None},
    ]

    res_ahmad = extract_player_victory_path(raw_sets, player_name="Ahmad21")
    assert len(res_ahmad["rounds"]) == 1
    assert res_ahmad["rounds"][0]["round_label"] == "WINNERS SEMIS"
    assert res_ahmad["rounds"][0]["matches"][0]["opponent_name"] == "Khalil99"

    res_fnc = extract_player_victory_path(raw_sets, player_name="FNCeSports")
    assert len(res_fnc["rounds"]) == 1
    assert res_fnc["rounds"][0]["round_label"] == "LOSERS SEMIS"
    assert res_fnc["rounds"][0]["matches"][0]["opponent_name"] == "Khalil99"


