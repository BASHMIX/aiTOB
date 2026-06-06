# Changelog

All notable changes to **aiTOB** (the AI Tournament Organizer Bot) are documented in
this file. The format is based on [Keep a Changelog](https://keepachangelog.com/),
and entries are grouped by the date the work landed on `master`.

The project is not yet versioned with release tags, so sections are dated rather
than numbered. The newest changes are at the top.

---

## [Unreleased] — 2026-06-06

Broadcast-production hardening: avatar quality gates, Cloudinary hosting,
event-scoped match/dispatch logic, the stream "green-room" workflow governed
strictly by `workflows.json`, an event-driven bot command pipeline, and a sweep
of live-test hotfixes.

### Added
- **Per-event auto-dispatcher (Option A).** Each `(tournament, event)` pair is now
  its own dispatch queue, so a multi-game tournament (e.g. SF6 + Tekken 8 under one
  slug) never shares concurrency, the Top-N stop threshold, or candidate selection
  across games. New `get_dispatch_eligible_events()`; `event_id` scoping added to
  `count_active_dispatched`, `count_remaining_event_matches`, and
  `get_dispatch_candidates`; per-`(slug, event)` cooldown and one-shot stop flags
  (reset via a prefix clear when the master switch is re-enabled).
- **Stream stations (green-room).** Stations gained `event_id`, `is_stream_station`,
  `room_name_or_id`, and `room_password`. A stream-flagged match is routed only to
  an idle stream station bound to the same event; the bot opens a distinct
  `waiting_for_stream_checkin` state and delivers the broadcaster's lobby
  name/password privately by DM **only after both players check in**.
- **Broadcast avatar collection in `/verify`.** The bio-code (Path B) flow now
  collects a broadcast-quality avatar with a `[Skip for Now]` soft gate, a
  standalone `/avatar` command, and a Hub AI tool to remind players who are missing
  one. Discord-native locale drives the player's preferred language.
- **Event scoping across the Hub.** Matches and attendees are scoped by event, not
  just tournament: a Tournament → Event hierarchy (auto-selecting a lone event,
  requiring an explicit pick for multiple), a `GET /tournaments/{slug}/events`
  endpoint, and per-card Event badges + an in-panel Event filter on the Match Panel.
- Cloudinary image hosting for broadcast avatars, with a local `/static` fallback
  when `CLOUDINARY_URL` is unset.
- `start_test.py` E2E wrapper (with DB-reset logic) and a hardened `run.py`.
- **Full test purge/reset.** `start_test.py` gained a `--purge` flag (auto-applied
  on `reset`) that clears live-test residue — `bot_feed`, `hub_commands`, conflicts,
  `planned_streams`, per-`(slug, event)` dispatcher stop flags — and forces the
  auto-dispatch master switch off plus all stream/station flags back to a clean
  baseline, so each live test starts from a known-empty state.
- **Live-test runbook.** `docs/LIVE_TEST_RUNBOOK.md` documents startup, hub
  prerequisites (including the `auto_dispatch_stop_at=0` gotcha), the happy-path
  walkthrough, the fallback edge case, and a "what to check if the bot is silent"
  troubleshooting section keyed to the new event-driven pipeline.
- **Event-driven bot command pipeline.** `add_hub_command` now writes to the
  `hub_commands` outbox **and** instantly nudges the bot over its control WebSocket
  (`{"type": "drain"}`) via an in-process listener (`set_hub_command_listener`),
  replacing the previously dead/un-drained queue. The bot drains under a lock with
  claim-before-run status transitions; a 60-second `@tasks.loop` remains only as a
  fallback sweeper, not the primary path.

### Changed
- Avatars now require a **512×512** minimum with specific, actionable rejection
  reasons (format vs. resolution vs. quality) instead of a generic failure.
- Manual **Call Match** and stream-toggle routing now use the event-scoped
  stream-station finder instead of grabbing any free station; the dead
  `auto_assign_free_station` helper was removed.
- Station assignment and the stream flag are now strictly coupled (see Fixed).
- **Agent ↔ UI parity.** The AI agent's "Call Match" tool was renamed to
  `call_match_tool(set_id)` and now routes through the same `call_match_core`
  chokepoint as the UI button, so both honor the `workflows.json` state machine
  identically. The agent's match-read tool projects only a safe field set via
  `project_match_for_agent` — `discord_thread_id` and other internals are stripped
  from the LLM's context.
- **Green-room binding moved to the canonical transition.** Stream-station
  assignment now happens at the exact `not_started → … → in_progress` transition
  via a `workflows.json` overlay (`on_stream`, `overlay: true`), rather than at
  dispatch or check-in time. No custom states were invented; `_realize_in_progress_overlays`
  binds an event-matching idle stream station only when the overlay condition holds,
  and completion/auto-DQ writes release the station (`station_id = None`).
- Default vision model bumped to `gemini-2.5-flash` (via `GEMINI_VISION_MODEL`),
  resolving the `gemini-1.5-flash` 404.

### Fixed
- **Station "Unassign" was a no-op.** `PATCH /active-matches/{id}` used
  `model_dump(exclude_none=True)`, which silently dropped an explicit
  `station_id: null` before it reached the database. Switched to `exclude_unset`
  so a sent `null` actually clears the station while omitted fields stay untouched.
- **Stream flag ↔ station coupling.** Assigning a stream station flags the match
  (+ wishlist + provider queue); assigning a non-stream station to a flagged match
  force-unflags it; toggling the flag off unassigns the station; toggling it on
  routes only to a free stream station for the event (unassign keeps the flag so
  the dispatcher can re-route).
- **Check-in phase enforced.** A match can no longer jump to in-progress before
  both players have checked in; the AI referee ignores result chat until then.
- **LLM winner mapping.** The referee now maps the model-reported winner back to
  the real match players via an explicit player ↔ Discord-ID roster, fixing
  mis-attributed results.
- **Hub stays in sync on referee errors** — the dashboard no longer goes stale when
  the referee throws; the thread handler is wrapped with a guaranteed broadcast.
- **`auto_dispatch_stop_at=0` was ignored.** `int(value or 8)` coerced a TO-set `0`
  back to the default `8` (the classic Python falsy-zero trap), so the "stop
  dispatching" threshold could never be set to zero. Centralized in
  `resolve_dispatch_budget`, which uses explicit `None` checks (`0` is honored,
  genuinely-unset falls back to the defaults, concurrency is clamped to ≥ 1). This
  was **not** a settings-cache bug — the dispatcher reads the budget live from SQL
  each tick; no stale cache exists in that path.
- **Settings PATCH parity.** `PATCH /tournaments/{slug}/settings` switched from
  `exclude_none=True` to `exclude_unset=True`, matching the matches PATCH fix so an
  explicitly-sent `null` is persisted instead of silently dropped.
- **Silent Discord bot.** The `hub_commands` queue had no consumer — commands were
  written but never executed. Fixed by the event-driven drain pipeline above (see
  Added), so Call Match / dispatch actions reach the bot immediately.
- **`removeStream` provider error.** The Start.gg `removeStream` path raised on a
  mutation start.gg no longer accepts; it's now a safe no-op (`return True`) and the
  dead `REMOVE_STREAM` query was deleted.
- Verified the Cloudinary → local `/static` avatar fallback still triggers correctly
  when `CLOUDINARY_URL` is unset.

### Tests
- New suites: `test_event_scoping`, `test_image_store`, `test_avatar_gate`,
  `test_dispatch_event_scoping` (incl. `stop_at=0` falsy-zero regression),
  `test_station_stream_coupling`, `test_on_stream_overlay`,
  `test_start_test_purge`, `test_call_match_unification`, and
  `test_commit10_hotfixes`.

---

## 2026-06-04

### Added
- Broadcast-avatar **soft gate** for the bio-code verification flow (new vs.
  returning player branches).

---

## 2026-06-02

A large consolidation day: security hardening, a unified test harness, and a
sweep of structural refactors (adopting community/Jules PRs #22–#56).

### Security
- Environment-based **CORS** with a dev fallback and optional subdomain regex.
- Hardened dynamic-kwargs SQL `UPDATE`s against column injection.

### Changed
- Saved AI / Start.gg API keys are masked with a placeholder in Settings instead
  of rendering blank.
- `get_hub_status` caches the auto-dispatch master switch (perf).

### Fixed
- Sync now wipes stale local scores when a set reverts to `not_started`; the
  refresh button was renamed for clarity.

### Refactored
- Extracted table schemas/indexes/migrations out of `init_db` into
  `database_schema.py`.
- Split `EditorDashboard` into hooks + components; split the editor Sidebar into
  `AddElements` / `Animation` / `Properties`; extracted a `useDraggable` hook.
- Extracted `handle_match_state_update` from the bot's `on_message`.
- Extracted `_update_existing_match` / `_insert_new_match` from
  `sync_active_matches`.
- Streamlined `OBSViewer` with a `useOBSViewerData` hook plus `OBSElement`/utils.

### Tests
- Unified **Vitest** harness with five component/hook suites.
- Added `should_bot_manage_match` coverage (case-insensitive limit).
- Merged/de-duplicated the `image_utils` test union (PRs #21/#43/#45).

---

## 2026-06-01

### Added
- Connected **workflow configuration engine** groundwork and broad unit-test
  coverage: `generate_lobby_password`, `_extract_avatar`, `map_stream`,
  `is_active_state`, `validate_transition`, provider registry/`get_provider`,
  score reporting, `process_avatar`, `validate_avatar_safety`/`_quality`, and
  `load_workflow_transitions` exception handling.

### Changed
- Adopted Step-2 PR optimizations: N+1 query fixes, caching, and dead-code removal.
- Memoized the `MatchDashboard` mapping and indexed `active_matches`.

### Fixed
- Match-state correctness: status writes, conflict handling, and double-DQ —
  plus AI conflict investigation.

---

## 2026-05-26

### Added
- Parameterized **Idle Animations** with an intensity slider.

### Fixed
- OBS WebSocket telemetry push bug.

---

## 2026-05-25

### Changed
- Optimized backend queries and file I/O; improved editor dragging stability.

---

## 2026-05-24

### Added
- Advanced overlay styling, **undo/redo** history, and a layers panel in the editor.

### Fixed
- Photo uploader.

---

## 2026-05-22

### Changed
- Removed tracked cache and environment files from version control.

---

## 2026-05-21

### Added
- Connected workflow configuration engine; dashboard card filters.

### Fixed
- DQ logic; lazy-load LLMs on startup; active-match API 500 errors.

---

## 2026-05-20

### Added
- Bot-manager settings and player-DM scoring.

### Fixed
- Admin DQ winner reporting.

---

## 2026-05-17 — 2026-05-18

### Added
- **Spec Kit**: implementation plan, design artifacts, and analysis remediation.
- Project scaffold — FastAPI backend, Discord bot, React frontend, and the
  Start.gg integration.

---

## 2026-05-16

### Added
- Initial commit from the Specify template.
