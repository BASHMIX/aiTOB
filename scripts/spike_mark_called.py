"""Preamble spike: verify start.gg's `markSetCalled` mutation and its player-facing effect.

WHY: The Dual-Mode Check-in epic assumes that firing `markSetCalled` on a set triggers
start.gg's NATIVE check-in wave (player-facing timer + push notifications). Schema
introspection only proved the mutation EXISTS and that our token passes its auth gate —
it cannot prove the player-facing behavior. This script fires the real mutation against a
known set so we can OBSERVE on start.gg whether the two entrants actually get prompted to
check in. This is the #1 risk gate for the epic.

WHAT IT DOES (read → mutate → read):
  1. Prints the set's current state.
  2. Fires markSetCalled(setId).
  3. Prints the mutation response and re-reads the state to confirm the transition.

TARGET (from the test bracket URL .../brackets/1640502/2307972/3339325):
  setId 103780372 = "Winners Semi-Final A": FNC | BASHMIX vs FGC | FNCeSports
  (both are accounts you control, so you can watch for the check-in notification.)

Override the target by passing a setId as the first CLI arg:
  python scripts/spike_mark_called.py 103780373

The token is loaded by StartGGClient from the DB (connections.STARTGG_API_TOKEN), exactly
as the live app loads it — no separate config needed. Run from the repo root.

AFTER RUNNING: open start.gg as each player (or check their notifications) and confirm
whether a check-in prompt / countdown actually appeared. If it did NOT, start.gg's set
state and its check-in feature are decoupled and 'startgg' mode must fall back to the
documented degraded behavior (thread + embed only; TO opens check-in manually).
"""
import asyncio
import os
import sys

# Make `backend...` importable when run from the repo root.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.core.providers.startgg.client import StartGGClient

DEFAULT_SET_ID = "103780372"  # Winners Semi-Final A — FNC | BASHMIX vs FGC | FNCeSports

# Inlined on purpose: the production MARK_SET_CALLED query is added in Commit 2; the spike
# must stand alone and not depend on code the epic hasn't written yet.
MARK_SET_CALLED = """
mutation MarkSetCalled($setId: ID!) {
  markSetCalled(setId: $setId) {
    id
    state
  }
}
"""

# Human-readable start.gg ActivityState mapping (see core/providers/startgg/state_map.py).
STATE_NAMES = {
    1: "CREATED", 2: "ACTIVE", 3: "COMPLETED", 4: "READY",
    5: "INVALID", 6: "CALLED", 7: "QUEUED",
}


def _label(state) -> str:
    return f"{state} ({STATE_NAMES.get(state, '?')})"


async def main():
    set_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SET_ID
    client = StartGGClient()

    print(f"=== markSetCalled spike — set {set_id} ===\n")

    try:
        before = await client.fetch_set_state(set_id)
        print(f"[1] State BEFORE: {_label(before)}")
    except Exception as e:
        print(f"[1] Could not read state before: {e}")
        before = None

    print("[2] Firing markSetCalled ...")
    try:
        data = await client.query(MARK_SET_CALLED, {"setId": set_id})
        result = (data or {}).get("markSetCalled") or {}
        print(f"    -> response: {data}")
        if result.get("state") is not None:
            print(f"    -> returned state: {_label(result.get('state'))}")
    except Exception as e:
        print(f"    -> markSetCalled FAILED: {e}")
        print(
            "\nIf this is a state error (e.g. set must be READY), advance/seed the bracket "
            "so the set is callable, or target a READY set, then re-run."
        )
        await client.close()
        return

    try:
        after = await client.fetch_set_state(set_id)
        print(f"[3] State AFTER:  {_label(after)}")
    except Exception as e:
        print(f"[3] Could not read state after: {e}")

    print(
        "\n=== NEXT: verify the PLAYER-FACING effect on start.gg ===\n"
        "Open start.gg as FNC | BASHMIX and FGC | FNCeSports (or check their notifications)\n"
        "and confirm whether a check-in prompt / countdown actually appeared.\n"
        "  • Prompt appeared  -> 'startgg' check-in mode is viable as designed.\n"
        "  • No prompt        -> set-state and check-in are decoupled; use the degraded mode.\n"
    )

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
