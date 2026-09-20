# Feature 004 prerequisite gate evidence

Date: 2026-09-13

## Result

**Partial / blocked for cutover.** The runtime already has a PostgreSQL-only
guard and workspace-aware paths in several services, but the feature-003
identity cutover is not complete. Feature 004 may build its additive foundation
behind disabled flags; activation must remain disabled until the failed items
below are repaired and re-tested.

| Gate | Evidence | Result |
|---|---|---|
| PostgreSQL runtime guard | `backend/core/storage.py` implements `require_runtime_database()` and rejects non-PostgreSQL runtime DSNs; `.env.example` documents `DATABASE_URL`. | PASS |
| PostgreSQL source of truth | `backend/core/database.py` still exposes the legacy SQLite `DB_PATH` and many repositories use the compatibility transport; feature-003 runtime acceptance is not demonstrated by this checkout. | BLOCKED |
| Workspace-owned tournament identity | `backend/core/database_schema.py` still defines `tournaments.slug` as the primary key while `workspace_id` is nullable. This prevents two workspaces from safely owning the same external scope. | BLOCKED |
| Non-null workspace ownership | Newer tables use required workspace foreign keys, but legacy `tournaments`, `players`, and several operational tables retain nullable workspace columns and compatibility backfill paths. | BLOCKED |
| Runtime fallback removal | `backend/bot/main.py` still defines `ACTIVE_DISCORD_WORKSPACE_ID` and `ACTIVE_DISCORD_ACCOUNT_ID`; legacy global AI and Discord settings remain present for compatibility. | BLOCKED |
| Automatic-DQ removal | `tournaments.auto_dq_enabled` still defaults to `TRUE` and `backend/bot/match_threads.py` still contains a reachable `auto_dq_match` call path. | BLOCKED |

## Required remediation before activation

1. Complete the feature-003 PostgreSQL/workspace identity migration and prove
   non-null workspace constraints with the disposable PostgreSQL suite.
2. Replace the global tournament slug identity with an internal UUID and
   workspace-scoped lookup/binding.
3. Remove or permanently disarm the automatic-DQ execution path and update its
   API/UI defaults.
4. Replace process-global Discord routing with explicit guild/tournament
   bindings before enabling the wizard activation flag.

The flags introduced by T003 remain false until these gates are rechecked.
