# US2 brand and operations evidence

Focused validation: `backend/tests/test_tournament_review_profile.py` and
`backend/tests/test_match_call_occurrences.py` passed (4 tests). The suite
covers local/provider branding provenance, Manual/Assisted preset expansion,
unfinished-match stop thresholds, truthful Start-in-wave states, and the
durable call-occurrence ledger. Provider and Dashboard observations use the
same workspace/tournament/match/version key, so duplicate delivery is ignored.

Start-in-wave remote mutation remains guarded until a documented provider write
contract is available; the UI reports that state and links the organizer to the
provider settings.
