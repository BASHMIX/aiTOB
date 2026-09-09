# Unified Tournament Progression Contract

## Purpose

Tournament progression answers **where this match belongs**. Match lifecycle answers **what is happening to it now**. The Hub must never use one to infer the other.

## Provider-neutral projection

```json
{
  "progression": {
    "stage": "Final Stage",
    "stage_kind": "final",
    "group": null,
    "bracket_side": "losers",
    "round": "Losers Semi-Final",
    "round_order": 6,
    "display_path": "Final Stage / Losers / Losers Semi-Final"
  },
  "hub_lifecycle_state": "available",
  "provider_normalized_state": "not_started",
  "provider_raw_state": "pending",
  "sync_status": "synced",
  "head_to_head_coordination": true
}
```

## Lifecycle mapping

| Hub lifecycle | Start.gg | Challonge | Action semantics |
|---|---|---|---|
| `not_started` | created or ready | pending or open | May appear in the Hub; `open` is ready to call but not automatically live. |
| `available` | created or ready | open | Two resolved sides can be called by aiTOB; this does not assert remote activity. |
| `called` | called | no equivalent assumed | Hub/Discord coordination state only unless an adapter validates an equivalent remote action. |
| `ready` | provider-specific | no equivalent assumed | Both sides acknowledged local attendance; it is separate from provider state. |
| `in_progress` | active | `in_progress` only when actually supplied | Hub local start and remote provider state are separate; Challonge `open` does not imply it. |
| `complete` | completed | complete | Terminal; remote result is source of truth. |
| `invalid` | invalid/bye | bye, cancelled, or non-actionable mapping | Not coordinated as a normal two-party match. |
| `queued` | queued | provider-specific future-ready state when available | Not yet actionable. |

The adapter preserves exact remote status in `provider_raw_state`; no raw state is
discarded. `hub_lifecycle_state` can be `called` or local `in_progress` while Challonge
continues to report `open`; the UI labels this explicitly and no synthetic provider
state is sent upstream.

`sync_status` is orthogonal to lifecycle: `synced`, `local_only`, `pending`,
`acknowledged_unverified`, `retrying`, `failed`, `conflict`, and `needs_review` describe
agreement/command safety, not what participants are doing. A match can therefore be
`in_progress` and `conflict` without losing either fact.

## Progression mapping rules

1. Start.gg: map event, phase, and phase group into stage context; derive bracket side and round from phase-group/round data.
2. Challonge single-stage: map the sole bracket to `stage_kind=single`; derive bracket side and round from documented match data.
3. Challonge two-stage: map group-stage matches to `stage_kind=group` and final-stage matches to `stage_kind=final`; preserve group/pool identity.
4. Free-for-all and racing modes: retain display data but set `head_to_head_coordination=false`; do not create a Discord match thread, two-side score dialog, or automated DQ action.
5. If a provider cannot supply a sort order, sort by explicit stage order, then known round order, then provider match identifier; never infer order from a localized display string.
