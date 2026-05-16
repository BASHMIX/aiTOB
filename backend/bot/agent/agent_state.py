from typing import TypedDict, List, Optional

class MatchState(TypedDict):
    set_id: int
    thread_id: int
    player1_discord: int
    player2_discord: int
    player1_ready: bool
    player2_ready: bool
    chat_history: List[str]
    match_status: str # 'waiting_checkin', 'playing', 'conflict', 'completed', 'dq'
    winner_id: Optional[int]
    score_string: Optional[str]
