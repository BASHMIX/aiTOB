"""Tournament Bracket Tree Extractor & Top 8 Topology Builder.

Extracts authoritative Top 8 Double Elimination and Top 4 Finals structures
from provider bracket snapshots (Start.gg and Challonge) without fabricating
or simulating unverified bracket progressions.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.core.tournament_format import FINALS_PATTERNS, TOP8_PATTERNS, format_to_best_of

# Regex patterns for matching canonical bracket rounds
RE_GF_RESET = re.compile(r"\bgrand\s+finals?\s*(reset|set\s*2|\[reset\]|\(reset\))\b", re.IGNORECASE)
RE_GRAND_FINALS = re.compile(r"\bgrand\s+finals?\b", re.IGNORECASE)
RE_WINNERS_FINALS = re.compile(r"\bwinners?\s+finals?\b", re.IGNORECASE)
RE_LOSERS_FINALS = re.compile(r"\blosers?\s+finals?\b", re.IGNORECASE)
RE_WINNERS_SEMIS = re.compile(r"\bwinners?\s+(semi[-\s]?finals?|semis)\b", re.IGNORECASE)
RE_LOSERS_SEMIS = re.compile(r"\blosers?\s+(semi[-\s]?finals?|semis)\b", re.IGNORECASE)
RE_LOSERS_QUARTERS = re.compile(r"\blosers?\s+(quarter[-\s]?finals?|quarters)\b", re.IGNORECASE)
RE_LOSERS_ROUND1 = re.compile(r"\blosers?\s+(round\s*1|r1|top\s*8)\b", re.IGNORECASE)

RE_CHALLONGE_ROUND = re.compile(r"round\s*(-?\d+)", re.IGNORECASE)


def _normalize_entrant(
    name: Optional[str],
    eid: Optional[str] = None,
    prefix: Optional[str] = None,
    avatar: Optional[str] = None,
    country: Optional[str] = None,
    score: Optional[int] = None,
    is_winner: bool = False,
    bracket_origin: Optional[str] = None,
    character: Optional[str] = None,
    character_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a unified entrant dictionary for the frontend."""
    clean_name = (name or "TBD").strip()
    return {
        "id": str(eid) if eid is not None else None,
        "name": clean_name if clean_name else "TBD",
        "prefix": str(prefix).strip() if prefix else None,
        "avatar_url": avatar,
        "country": country,
        "score": score if score is not None else 0,
        "is_winner": is_winner,
        "bracket_origin": bracket_origin,  # 'winners' (W) or 'losers' (L)
        "character": character,
        "character_url": character_url,
    }


def infer_completed_winners(sets: List[Dict[str, Any]]) -> Dict[str, str]:
    """Infer winner entrant IDs for completed sets when winner_id is not explicitly provided.
    
    Uses double/single elimination bracket progression rules:
    - Sets with explicit winner_id or unequivocal scores are used directly.
    - Winners bracket: Entrant appearing in a later winners round (WF, GF) won this set.
    - Losers bracket: Entrant appearing in a later losers round (LSF, LF, GF) won this set.
    - Entrant dropping into the corresponding losers round lost, meaning the opponent won.
    """
    inferred: Dict[str, str] = {}
    for s in sets:
        sid = str(s.get("id") or "")
        w_id = s.get("winner_id")
        if w_id:
            inferred[sid] = str(w_id)
            continue

        st = s.get("state")
        aitob_st = str(s.get("aitob_state") or "")
        is_complete = (st == 4 or aitob_st == "complete")
        if not is_complete:
            continue

        p1_id = str(s.get("p1_eid") or "")
        p2_id = str(s.get("p2_eid") or "")
        if not p1_id or not p2_id:
            continue

        p1_score = s.get("p1_score")
        p2_score = s.get("p2_score")
        if p1_score is not None and p2_score is not None:
            if p1_score > p2_score:
                inferred[sid] = p1_id
                continue
            elif p2_score > p1_score:
                inferred[sid] = p2_id
                continue

        rnd = str(s.get("fullRoundText") or s.get("round") or "").lower()

        # Winners bracket progression:
        if "winner" in rnd or "wsf" in rnd or "wf" in rnd:
            p1_in_later_w = False
            p2_in_later_w = False
            for other in sets:
                if str(other.get("id")) == sid:
                    continue
                o_rnd = str(other.get("fullRoundText") or other.get("round") or "").lower()
                o_p1 = str(other.get("p1_eid") or "")
                o_p2 = str(other.get("p2_eid") or "")

                is_later_w = False
                if "semi" in rnd and ("winners final" in o_rnd or "grand" in o_rnd):
                    is_later_w = True
                elif "final" in rnd and "grand" in o_rnd:
                    is_later_w = True
                elif "round 1" in rnd and ("semi" in o_rnd or "final" in o_rnd or "grand" in o_rnd):
                    is_later_w = True

                if is_later_w:
                    if p1_id in (o_p1, o_p2):
                        p1_in_later_w = True
                    if p2_id in (o_p1, o_p2):
                        p2_in_later_w = True

            if p1_in_later_w and not p2_in_later_w:
                inferred[sid] = p1_id
            elif p2_in_later_w and not p1_in_later_w:
                inferred[sid] = p2_id

        # Losers bracket progression:
        elif "loser" in rnd or "lsf" in rnd or "lf" in rnd:
            p1_in_later = False
            p2_in_later = False
            for other in sets:
                if str(other.get("id")) == sid:
                    continue
                o_rnd = str(other.get("fullRoundText") or other.get("round") or "").lower()
                o_p1 = str(other.get("p1_eid") or "")
                o_p2 = str(other.get("p2_eid") or "")

                is_later = False
                if "semi" in rnd and ("losers final" in o_rnd or "grand" in o_rnd):
                    is_later = True
                elif "quarter" in rnd and ("semi" in o_rnd or "final" in o_rnd or "grand" in o_rnd):
                    is_later = True
                elif "round 1" in rnd and ("quarter" in o_rnd or "semi" in o_rnd or "final" in o_rnd or "grand" in o_rnd):
                    is_later = True
                elif "final" in rnd and "grand" in o_rnd:
                    is_later = True

                if is_later:
                    if p1_id in (o_p1, o_p2):
                        p1_in_later = True
                    if p2_id in (o_p1, o_p2):
                        p2_in_later = True

            if p1_in_later and not p2_in_later:
                inferred[sid] = p1_id
            elif p2_in_later and not p1_in_later:
                inferred[sid] = p2_id

    return inferred


def _match_node(
    raw_set: Dict[str, Any],
    round_display: str,
    inferred_winner_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Format a raw snapshot set dictionary into a clean bracket match node."""
    set_id = str(raw_set.get("id") or "")
    winner_id = raw_set.get("winner_id") or inferred_winner_id
    p1_eid = raw_set.get("p1_eid")
    p2_eid = raw_set.get("p2_eid")
    
    p1_score = raw_set.get("p1_score")
    p2_score = raw_set.get("p2_score")
    
    p1_winner = bool(winner_id and str(winner_id) == str(p1_eid)) if p1_eid else False
    p2_winner = bool(winner_id and str(winner_id) == str(p2_eid)) if p2_eid else False

    # State normalization
    aitob_state = str(raw_set.get("aitob_state") or "").lower()
    if not aitob_state:
        state_code = raw_set.get("state")
        if state_code == 4:
            aitob_state = "complete"
        elif state_code in (2, 3):
            aitob_state = "in_progress"
        else:
            aitob_state = "not_started"

    # Default score for completed sets with known winner if scores are absent
    if aitob_state == "complete" and p1_score is None and p2_score is None:
        if p1_winner:
            p1_score = 2
            p2_score = 0
        elif p2_winner:
            p1_score = 0
            p2_score = 2

    return {
        "id": set_id,
        "round_name": round_display,
        "raw_round": raw_set.get("fullRoundText") or raw_set.get("round") or "",
        "identifier": str(raw_set.get("identifier") or ""),
        "state": aitob_state,
        "winner_id": str(winner_id) if winner_id is not None else None,
        "p1": _normalize_entrant(
            name=raw_set.get("p1") or raw_set.get("p1_name"),
            eid=p1_eid,
            prefix=raw_set.get("p1_prefix"),
            avatar=raw_set.get("p1_avatar"),
            country=raw_set.get("p1_country"),
            score=p1_score,
            is_winner=p1_winner,
            character=raw_set.get("p1_character"),
            character_url=raw_set.get("p1_character_url"),
        ),
        "p2": _normalize_entrant(
            name=raw_set.get("p2") or raw_set.get("p2_name"),
            eid=p2_eid,
            prefix=raw_set.get("p2_prefix"),
            avatar=raw_set.get("p2_avatar"),
            country=raw_set.get("p2_country"),
            score=p2_score,
            is_winner=p2_winner,
            character=raw_set.get("p2_character"),
            character_url=raw_set.get("p2_character_url"),
        ),
    }


def extract_top8_bracket(
    sets: List[Dict[str, Any]],
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse a tournament's sets snapshot into a structured Top 8 Double Elimination tree.
    
    Identifies:
      - Winners Semifinals (2 matches)
      - Winners Finals (1 match)
      - Losers Round 1 (Top 8 Losers, 2 matches)
      - Losers Quarters (2 matches)
      - Losers Semifinals (1 match)
      - Losers Finals (1 match)
      - Grand Finals (1 match)
      - Grand Finals Reset (1 match if triggered)
    
    Attaches (W) and (L) bracket origin tags to Grand Finals entrants based on
    originating bracket results.
    """
    if event_id:
        scoped_sets = [s for s in sets if str(s.get("event_id") or "") == str(event_id)]
    else:
        scoped_sets = list(sets)

    # Buckets for classified matches
    wsf_matches: List[Dict[str, Any]] = []
    wf_match: Optional[Dict[str, Any]] = None
    lr1_matches: List[Dict[str, Any]] = []
    lqf_matches: List[Dict[str, Any]] = []
    lsf_match: Optional[Dict[str, Any]] = None
    lf_match: Optional[Dict[str, Any]] = None
    gf_match: Optional[Dict[str, Any]] = None
    gf_reset_match: Optional[Dict[str, Any]] = None

    # First pass: classify sets using canonical names
    unclassified: List[Dict[str, Any]] = []
    for s in scoped_sets:
        round_text = str(s.get("fullRoundText") or s.get("round") or "").strip()
        
        if RE_GF_RESET.search(round_text):
            gf_reset_match = s
        elif RE_GRAND_FINALS.search(round_text):
            if gf_match is None:
                gf_match = s
            else:
                # If there are two Grand Final sets, the second one is Reset
                gf_reset_match = s
        elif RE_WINNERS_FINALS.search(round_text):
            wf_match = s
        elif RE_LOSERS_FINALS.search(round_text):
            lf_match = s
        elif RE_WINNERS_SEMIS.search(round_text):
            wsf_matches.append(s)
        elif RE_LOSERS_SEMIS.search(round_text):
            lsf_match = s
        elif RE_LOSERS_QUARTERS.search(round_text):
            lqf_matches.append(s)
        elif RE_LOSERS_ROUND1.search(round_text):
            lr1_matches.append(s)
        else:
            unclassified.append(s)

    # Second pass: if Challonge numeric rounds were present and finals weren't matched
    if not (wf_match and lf_match) and unclassified:
        # Group unclassified sets by numeric round
        round_groups: Dict[int, List[Dict[str, Any]]] = {}
        for s in unclassified:
            round_text = str(s.get("round") or s.get("fullRoundText") or "")
            m = RE_CHALLONGE_ROUND.search(round_text)
            if m:
                r_num = int(m.group(1))
                round_groups.setdefault(r_num, []).append(s)

        if round_groups:
            positive_rounds = sorted([r for r in round_groups.keys() if r > 0])
            negative_rounds = sorted([r for r in round_groups.keys() if r < 0])

            # Winners side
            if positive_rounds:
                max_pos = positive_rounds[-1]
                # If max_pos has GF / Reset
                if len(round_groups[max_pos]) >= 2 and gf_match is None:
                    gf_match = round_groups[max_pos][0]
                    gf_reset_match = round_groups[max_pos][1]
                elif gf_match is None:
                    gf_match = round_groups[max_pos][0]

                if len(positive_rounds) >= 2 and wf_match is None:
                    wf_match = round_groups[positive_rounds[-2]][0]
                if len(positive_rounds) >= 3 and not wsf_matches:
                    wsf_matches = round_groups[positive_rounds[-3]][:2]

            # Losers side (more negative = later in Challonge)
            if negative_rounds:
                # e.g. -1, -2, -3, -4, -5. -5 is Losers Finals
                min_neg = negative_rounds[0]  # most negative
                if lf_match is None:
                    lf_match = round_groups[min_neg][0]
                if len(negative_rounds) >= 2 and lsf_match is None:
                    lsf_match = round_groups[negative_rounds[1]][0]
                if len(negative_rounds) >= 3 and not lqf_matches:
                    lqf_matches = round_groups[negative_rounds[2]][:2]
                if len(negative_rounds) >= 4 and not lr1_matches:
                    lr1_matches = round_groups[negative_rounds[3]][:2]

    inferred_winners = infer_completed_winners(scoped_sets)

    # Convert classified sets to formatted match nodes
    node_wsf = [_match_node(s, f"Winners Semi-Final {i+1}", inferred_winners.get(str(s.get("id") or ""))) for i, s in enumerate(wsf_matches[:2])]
    node_wf = _match_node(wf_match, "Winners Final", inferred_winners.get(str(wf_match.get("id") or ""))) if wf_match else None
    node_lr1 = [_match_node(s, f"Losers Round 1 · Match {i+1}", inferred_winners.get(str(s.get("id") or ""))) for i, s in enumerate(lr1_matches[:2])]
    node_lqf = [_match_node(s, f"Losers Quarter-Final {i+1}", inferred_winners.get(str(s.get("id") or ""))) for i, s in enumerate(lqf_matches[:2])]
    node_lsf = _match_node(lsf_match, "Losers Semi-Final", inferred_winners.get(str(lsf_match.get("id") or ""))) if lsf_match else None
    node_lf = _match_node(lf_match, "Losers Final", inferred_winners.get(str(lf_match.get("id") or ""))) if lf_match else None
    node_gf = _match_node(gf_match, "Grand Final", inferred_winners.get(str(gf_match.get("id") or ""))) if gf_match else None
    node_gf_reset = _match_node(gf_reset_match, "Grand Final Reset", inferred_winners.get(str(gf_reset_match.get("id") or ""))) if gf_reset_match else None

    # Tag (W) and (L) on Grand Finals entrants
    wf_winner_id = node_wf.get("winner_id") if node_wf else None
    lf_winner_id = node_lf.get("winner_id") if node_lf else None

    def _assign_origins(gf_node: Optional[Dict[str, Any]]) -> None:
        if not gf_node:
            return
        p1 = gf_node["p1"]
        p2 = gf_node["p2"]
        
        # Match by ID or fallback to standard Double Elimination convention
        # (Entrant 1 in GF is usually from Winners Bracket, Entrant 2 from Losers Bracket)
        if wf_winner_id and p1.get("id") == wf_winner_id:
            p1["bracket_origin"] = "winners"
            p2["bracket_origin"] = "losers"
        elif wf_winner_id and p2.get("id") == wf_winner_id:
            p2["bracket_origin"] = "winners"
            p1["bracket_origin"] = "losers"
        elif lf_winner_id and p1.get("id") == lf_winner_id:
            p1["bracket_origin"] = "losers"
            p2["bracket_origin"] = "winners"
        elif lf_winner_id and p2.get("id") == lf_winner_id:
            p2["bracket_origin"] = "losers"
            p1["bracket_origin"] = "winners"
        else:
            # Standard convention
            p1["bracket_origin"] = "winners"
            p2["bracket_origin"] = "losers"

    _assign_origins(node_gf)
    _assign_origins(node_gf_reset)

    has_reset = node_gf_reset is not None
    reset_active = bool(
        node_gf_reset
        and (
            node_gf_reset.get("state") in ("in_progress", "complete")
            or (
                node_gf
                and node_gf.get("state") == "complete"
                and (
                    (node_gf.get("p1", {}).get("bracket_origin") == "losers" and node_gf.get("p1", {}).get("is_winner"))
                    or (node_gf.get("p2", {}).get("bracket_origin") == "losers" and node_gf.get("p2", {}).get("is_winner"))
                )
            )
        )
    )

    return {
        "event_id": event_id,
        "has_reset": has_reset,
        "reset_active": reset_active,
        "matches": {
            "winners_semis": node_wsf,
            "winners_finals": node_wf,
            "losers_round1": node_lr1,
            "losers_quarters": node_lqf,
            "losers_semis": node_lsf,
            "losers_finals": node_lf,
            "grand_finals": node_gf,
            "grand_finals_reset": node_gf_reset,
        },
    }


def extract_player_victory_path(
    sets: List[Dict[str, Any]],
    player_id: Optional[str] = None,
    player_name: Optional[str] = None,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract a player's tournament run (all won sets grouped by round).
    
    Used for the broadcast 'Victory Path' graphic overlay.
    """
    if event_id:
        scoped_sets = [s for s in sets if str(s.get("event_id") or "") == str(event_id)]
    else:
        scoped_sets = list(sets)

    if not scoped_sets:
        return {"player_name": player_name or "TBD", "prefix": None, "rounds": []}

    target_id = str(player_id).strip().lower() if player_id else None
    target_name = str(player_name).strip().lower() if player_name else None

    resolved_name: Optional[str] = None
    resolved_prefix: Optional[str] = None
    resolved_country: Optional[str] = None
    resolved_avatar: Optional[str] = None

    inferred_winners = infer_completed_winners(scoped_sets)
    won_matches: List[Dict[str, Any]] = []

    for s in scoped_sets:
        sid = str(s.get("id") or "")
        p1_name = str(s.get("p1") or "")
        p2_name = str(s.get("p2") or "")
        p1_id = str(s.get("p1_eid") or "")
        p2_id = str(s.get("p2_eid") or "")
        winner_id = str(s.get("winner_id") or inferred_winners.get(sid) or "")

        p1_is_target = (target_id and p1_id.lower() == target_id) or (target_name and p1_name.lower() == target_name)
        p2_is_target = (target_id and p2_id.lower() == target_id) or (target_name and p2_name.lower() == target_name)

        if not (p1_is_target or p2_is_target):
            continue

        # Keep player identity details
        if p1_is_target:
            resolved_name = p1_name or resolved_name
            resolved_prefix = s.get("p1_prefix") or resolved_prefix
            resolved_country = s.get("p1_country") or resolved_country
            resolved_avatar = s.get("p1_avatar") or resolved_avatar
        elif p2_is_target:
            resolved_name = p2_name or resolved_name
            resolved_prefix = s.get("p2_prefix") or resolved_prefix
            resolved_country = s.get("p2_country") or resolved_country
            resolved_avatar = s.get("p2_avatar") or resolved_avatar

        is_p1_win = bool(winner_id and winner_id == p1_id)
        is_p2_win = bool(winner_id and winner_id == p2_id)

        p1_score = s.get("p1_score")
        p2_score = s.get("p2_score")
        if not (is_p1_win or is_p2_win) and p1_score is not None and p2_score is not None:
            if p1_score > p2_score:
                is_p1_win = True
            elif p2_score > p1_score:
                is_p2_win = True

        player_won = (p1_is_target and is_p1_win) or (p2_is_target and is_p2_win)
        if not player_won:
            continue

        if p1_is_target:
            resolved_name = p1_name or resolved_name
            resolved_prefix = s.get("p1_prefix") or resolved_prefix
            resolved_country = s.get("p1_country") or resolved_country
            opp_name = p2_name
            opp_prefix = s.get("p2_prefix")
            opp_country = s.get("p2_country")
            score_str = f"{p1_score if p1_score is not None else 2}-{p2_score if p2_score is not None else 0}"
        else:
            resolved_name = p2_name or resolved_name
            resolved_prefix = s.get("p2_prefix") or resolved_prefix
            resolved_country = s.get("p2_country") or resolved_country
            opp_name = p1_name
            opp_prefix = s.get("p1_prefix")
            opp_country = s.get("p1_country")
            score_str = f"{p2_score if p2_score is not None else 2}-{p1_score if p1_score is not None else 0}"

        round_text = str(s.get("fullRoundText") or s.get("round") or "Round 1").strip()
        round_upper = round_text.upper()
        if "RESET" in round_upper:
            stage_label = "GF RESET"
            sub_label = "RESET"
            main_number = "GF"
            order_weight = 75
        elif "GRAND FINAL" in round_upper or "GRAND_FINAL" in round_upper or round_upper == "GF":
            stage_label = "GRAND FINALS"
            sub_label = "FINALS"
            main_number = "GF"
            order_weight = 70
        elif "SEMI" in round_upper or "WSF" in round_upper or "LSF" in round_upper:
            is_loser = "LOSER" in round_upper or "LSF" in round_upper
            stage_label = "LOSERS SEMIS" if is_loser else "WINNERS SEMIS"
            sub_label = "SEMIS"
            main_number = "LSF" if is_loser else "WSF"
            order_weight = 60
        elif "QUARTER" in round_upper or "LQF" in round_upper:
            is_loser = "LOSER" in round_upper or "LQF" in round_upper
            stage_label = "LOSERS QUARTERS" if is_loser else "QUARTERS"
            sub_label = "QUARTERS"
            main_number = "LQF" if is_loser else "QF"
            order_weight = 55
        elif "FINAL" in round_upper:
            is_loser = "LOSER" in round_upper or "LF" in round_upper
            stage_label = "LOSERS FINALS" if is_loser else "WINNERS FINALS"
            sub_label = "FINALS"
            main_number = "LF" if is_loser else "WF"
            order_weight = 65
        elif "TOP 8" in round_upper or "TOP8" in round_upper:
            stage_label = "TOP 8"
            sub_label = "TOP"
            main_number = "8"
            order_weight = 50
        elif "TOP 24" in round_upper or "TOP24" in round_upper:
            stage_label = "TOP 24"
            sub_label = "TOP"
            main_number = "24"
            order_weight = 40
        elif "ROUND 3" in round_upper or "R3" in round_upper:
            stage_label = "ROUND 3"
            sub_label = "ROUND"
            main_number = "3"
            order_weight = 30
        elif "ROUND 2" in round_upper or "R2" in round_upper:
            stage_label = "ROUND 2"
            sub_label = "ROUND"
            main_number = "2"
            order_weight = 20
        elif "ROUND 1" in round_upper or "R1" in round_upper:
            stage_label = "ROUND 1"
            sub_label = "ROUND"
            main_number = "1"
            order_weight = 10
        else:
            stage_label = round_text
            sub_label = re.sub(r'[0-9]', '', round_text).strip() or "ROUND"
            main_number = re.sub(r'[^0-9]', '', round_text).strip() or "1"
            order_weight = 15

        won_matches.append({
            "stage_label": stage_label,
            "sub_label": sub_label,
            "main_number": main_number,
            "order_weight": order_weight,
            "score": score_str,
            "opponent_name": opp_name,
            "opponent_prefix": opp_prefix,
            "opponent_country": opp_country,
        })

    rounds_dict: Dict[str, Dict[str, Any]] = {}
    for m in won_matches:
        lbl = m["stage_label"]
        if lbl not in rounds_dict:
            rounds_dict[lbl] = {
                "round_label": lbl,
                "sub_label": m["sub_label"],
                "main_number": m["main_number"],
                "order_weight": m["order_weight"],
                "matches": [],
            }
        rounds_dict[lbl]["matches"].append({
            "score": m["score"],
            "opponent_name": m["opponent_name"],
            "opponent_prefix": m["opponent_prefix"],
            "opponent_country": m["opponent_country"],
        })

    sorted_rounds = sorted(rounds_dict.values(), key=lambda r: r["order_weight"], reverse=True)

    return {
        "player_name": resolved_name or player_name or "TBD",
        "prefix": resolved_prefix,
        "country": resolved_country,
        "avatar_url": resolved_avatar,
        "rounds": sorted_rounds,
    }

