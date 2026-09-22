# Validation Quickstart: Player Profiles

## 1. Prerequisites and Environment

1. Set `DATABASE_URL` and point `AITOB_PG_TEST_URL` at a disposable PostgreSQL database.
2. Run focused profile, presentation, participant review, and broadcast tests:

   ```powershell
   $env:AITOB_PG_TEST_URL = 'postgresql://user:password@127.0.0.1:5433/disposable_db'
   python -m pytest backend/tests/test_participants_overrides_regression.py backend/tests/test_broadcast_projection.py backend/tests/test_player_profile_*.py backend/tests/test_player_presentation_*.py -q
   ```

3. Build the organizer UI:

   ```powershell
   Set-Location frontend-react
   npm test
   npm run build
   ```

## 2. Migration Inventory and Target Schema

The persistent player-profile foundation introduces the following additive tables:
- `player_profiles`: Stable, workspace-owned player identity (`id`, `workspace_id`, `display_name`, `prefix`, `country`, `avatar_url`, `discord_id`, `notes`, `created_at`, `updated_at`).
- `player_provider_identities`: Audited association between a `player_profile` and a provider account (`id`, `workspace_id`, `player_profile_id`, `provider`, `provider_user_id`, `provider_gamer_tag`, `verified`, `created_at`).
- `player_game_profiles`: Game-specific account data (`id`, `workspace_id`, `player_profile_id`, `game_id`, `in_game_name`, `in_game_id`, `created_at`).
- `player_character_defaults`: Default character preferences per game (`id`, `workspace_id`, `player_game_profile_id`, `character_id`, `character_name`, `character_image_url`).
- `tournament_entrant_overrides`: Scoped overrides (`id`, `workspace_id`, `provider`, `tournament_slug`, `event_id`, `entrant_id`, `display_name`, `prefix`, `country`, `avatar_url`, `character_id`, `character_name`, `character_image_url`, `created_at`, `updated_at`).

## 3. Legacy `player_overrides` Ambiguity Rule

Legacy `player_overrides` were keyed solely by an entrant ID without tournament, event, or provider scope:
- **Deterministic Re-homing**: A legacy override is converted to a `tournament_entrant_overrides` row **only if** its entrant ID is uniquely and deterministically attributable to exactly one tournament and event via `tournament_player_links` or stored tournament entrant nodes within the same workspace.
- **Ambiguous Record Preservation**: If a legacy override row matches zero or multiple tournaments/events, or lacks clear event context:
  1. It is **never** assigned by guessing or heuristically re-homed.
  2. The legacy row is preserved in `player_overrides` with `requires_review = TRUE` (or retained in legacy compatibility).
  3. The organizer can inspect and confirm or dismiss the legacy override in the Hub.

## 4. Rollback and Integrity Checks

- **Pre-migration verification**: Check count of `players`, `tournament_player_links`, and `player_overrides`.
- **Post-migration verification**:
  - Every `player_profiles` row maps to a valid workspace.
  - Avatar media assets referenced by `player_profiles` exist in `media_assets` and have not been altered or deleted.
  - All previously linked entrants in `tournament_player_links` maintain their associations.
  - Ambiguous legacy overrides remain accessible and untouched.
- **Rollback safety**:
  - The new tables are strictly additive.
  - Existing `player_overrides` and `players` tables remain intact and readable.
  - No existing station, match, or OBS query is modified to rely on the new schema in v1.

## 5. Operator Notes & OBS Boundary

- **Strict OBS Non-Adoption Boundary**:
  - No OBS route (`/obs/*`), station broadcast projection (`broadcast_projection.py`), match coordination, or provider bracket command consumes the v1 player presentation hook.
  - Projections in OBS overlays remain 100% stable on existing active match records and station schemas.
  - Future graphics consumers must explicitly opt-in when ready.
- **Player Archive in Hub**:
  - Organizers can access the dedicated Player Archive at `/admin/players` or via the top navigation bar.
  - Profiles are workspace-scoped and include game preferences (IGN, CFN) and character defaults with primary designation.
  - Entrant presentation editing in `ParticipantsTable` clearly indicates field provenance (`entrant_override`, `player_profile`, `provider_snapshot`, or `placeholder`) and supports resetting to profile defaults.

## 6. Verification Evidence and Test Suites

### Review Evidence — 2026-09-22
- Focused PostgreSQL suite: 21 tests passed before the review fixes; the 22
  affected migration, scoped-override, presentation, asset, profile-API, and
  workspace-security tests passed again after the fixes.
- Focused frontend suite: 13 Player Archive, entrant-editor, and Participants
  tests passed. The full frontend suite also passed: 14 files / 63 tests.
- Production build: `tsc && vite build` passed. Vite reports the pre-existing
  large-chunk advisory only; there are no type or build errors.
- Whole backend suite on the disposable PostgreSQL server: **606 passed, 1
  skipped, 24 warnings** in 3:57. The warnings are pre-existing framework and
  dependency deprecations; no test failed.

### Disposable Migration Go / No-Go

- The migration acceptance test starts from a disposable PostgreSQL database,
  backfills a player, provider identity, game profile, linked entrant, avatar,
  deterministic legacy override, and ambiguous legacy override. It verifies the
  resulting aggregate counts and values, preserves the avatar reference, and
  marks the ambiguous row for review rather than guessing.
- **Go**: additive schema receipts, deterministic migration, scoped override
  isolation, and asset reference protection are all green in the focused and
  full backend suites. **Rollback** remains safe because legacy rows and live
  OBS/station projections are not rewritten or made dependent on v1.
