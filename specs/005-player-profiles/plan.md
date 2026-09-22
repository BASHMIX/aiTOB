# Implementation Plan: Persistent Player Profiles and Tournament Overrides

**Branch**: `005-player-profiles` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

## Summary

Deliver a modular player domain that reuses confirmed workspace-owned profiles
across tournaments while keeping provider entrants, event choices, and
broadcast overrides independently scoped. Correct the participant-review path
first, then introduce a versioned read-only presentation projection for future
overlay consumers. The existing station/OBS projection remains the active
live-broadcast consumer throughout this feature.

## Technical Context

**Language/Version**: Python 3.12+, TypeScript 6  
**Primary Dependencies**: FastAPI, Pydantic v2, React 19, Vite  
**Storage**: PostgreSQL 17+ only; existing validated image store and media ledger  
**Testing**: pytest with disposable PostgreSQL; frontend unit tests and production build  
**Target Platform**: Browser organizer Hub, API, Discord bot, future authenticated overlay consumers  
**Project Type**: Web application  
**Performance Goals**: Participant review resolves a page of entrants without per-row provider requests; the hook resolves from local data in one bounded request.  
**Constraints**: Session-scoped workspace authorization; no embedded database or dual write; provider membership/progression remain authoritative; no change to live station, provider, or OBS binding paths in this delivery.  
**Scale/Scope**: Workspace-local player archive, identity links, game preferences, scoped tournament overrides, participant-review integration, and a read-only v1 presentation hook.

## Constitution Check

| Gate | Result | Design response |
|---|---|---|
| Workspace isolation | Pass | Profiles, identities, preferences, overrides, and projections are workspace scoped; the server derives workspace from the session. |
| PostgreSQL-only runtime | Pass | PostgreSQL migrations/repositories only; tests use disposable PostgreSQL databases. |
| Asset safety | Pass | Existing avatar URLs and ledger entries are retained; new images reuse validated storage. |
| Provider and broadcast safety | Pass | Provider snapshots remain authoritative for membership. The v1 hook is read-only and does not touch station ownership, `broadcast_state`, OBS URLs, or provider commands. |
| Verification before cutover | Pass | Migration, authorization, precedence, regression, and frontend-build checks are mandatory. |

## Project Structure

```text
specs/005-player-profiles/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/player-presentation.md

backend/
├── api/routers/players.py             # existing participant and player routes
├── api/routers/player_profiles.py     # archive and presentation routes
├── core/database_schema.py             # PostgreSQL migrations
├── core/database.py                    # transactional repositories
├── core/player_profiles.py             # profile aggregate facade
├── core/player_presentation.py         # pure precedence/provenance resolver
└── core/broadcast_projection.py        # unchanged active OBS consumer in v1

frontend-react/src/features/
├── players/                            # archive, cards, types, API
└── hub/components/ParticipantsTable.tsx
```

**Structure Decision**: Add a bounded player-profile domain and frontend feature
rather than extending `ParticipantsTable` or generic database helpers with more
provider-specific behavior. Keep the current broadcast projection unchanged
until a later explicit hook-consumer rollout.

## Implementation Phases

### Phase 1 — Correct the current participant review

1. Return saved `character_name`, `character_id`, and `character_image_url` in
   the existing override projection.
2. Resolve participant avatar and identity from the confirmed tournament player
   link before falling back to provider imagery.
3. Add focused precedence tests and a regression test proving a linked avatar
   appears without a fresh entrant upload.

### Phase 2 — Establish the reusable profile aggregate

1. Add a stable workspace-owned profile identity and migrate existing player
   records without deleting or re-uploading assets.
2. Add provider-identity links, game profiles, and character defaults as
   separate aggregates. They may suggest an entrant link but cannot confirm one.
3. Re-home only deterministically attributable legacy overrides into scoped
   records. Preserve ambiguous legacy rows for organizer review rather than
   guessing a tournament or player.

### Phase 3 — Scoped overrides and archive UI

1. Replace entrant-ID-global override writes with workspace + provider +
   tournament + event/bracket + entrant scope.
2. Add the Player Archive and profile detail UI, with compact cards, provenance
   labels, game chips, and explicit edit modes.
3. Add an explicit “use profile” / “use tournament override” choice so the
   organizer understands which value will be presented.

### Phase 4 — Read-only presentation hook

1. Implement the v1 resolved presentation contract in
   [contracts/player-presentation.md](contracts/player-presentation.md), with a
   resolver that has no provider calls or mutation side effects.
2. Expose it only through authenticated workspace routes and an internal domain
   facade. Do not add it to `broadcast_projection.py` in this delivery.
3. Add contract, workspace-isolation, and unchanged-OBS regression tests. A
   later feature can opt an overlay in after its own comparison and rollback plan.

## Complexity Tracking

No constitution exception is required.
