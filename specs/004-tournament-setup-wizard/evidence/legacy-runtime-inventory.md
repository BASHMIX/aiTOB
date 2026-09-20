# Feature 004 legacy runtime inventory

Date: 2026-09-13

This inventory is a migration boundary, not an authorization to keep legacy
behavior enabled after cutover. Secrets and live values were not copied into
this document.

| Legacy behavior | Current location | Required boundary |
|---|---|---|
| Global active Discord workspace/account | `backend/bot/main.py` (`ACTIVE_DISCORD_WORKSPACE_ID`, `ACTIVE_DISCORD_ACCOUNT_ID`) | Resolve every inbound/outbound operation from explicit guild, channel, thread, and tournament bindings. |
| Service-global AI configuration | `backend/core/database_schema.py` (`ai_service_config`, `ai_service_secrets`), `backend/core/ai_service.py` | Use workspace AI configuration and encrypted integration credentials; any legacy assignment must be explicit, audited, and one-workspace-only. |
| Automatic-DQ timer and executor | `backend/bot/match_threads.py`, `backend/core/match_state.py`, `backend/core/auto_dispatcher/` | Remove execution and default-true settings; retain reminders and human escalation only. |
| Global registration state | `backend/bot/main.py`, `backend/bot/registration.py`, `backend/core/database.py` (`players`, pending verification tables) | Move to tournament-scoped registration windows and enrollments; retain reusable workspace identity separately. |
| Ambiguous player names | `backend/core/database.py` (`players.team`, `players.gamer_tag`) and frontend Hub/editor projections | Canonicalize to `prefix` and `gamertag`; expose `team`/`name` only through a deprecated migration adapter. |
| Start.gg locator truncation/first Event behavior | `backend/api/routers/tournaments.py`, `backend/core/providers/startgg/queries.py` | Resolve direct Event slug exactly and require explicit selection for multi-Event tournament locators. |
| Legacy provider/global settings | `backend/api/routers/settings.py`, `backend/api/routers/tournaments.py`, `frontend-react/src/features/hub/components/TournamentSettings.tsx` | Label compatibility values, stop using them for new wizard runtime, and keep replacement bindings explicit. |

## Safety observations

- `backend/core/storage.py` fails closed when a process lacks a PostgreSQL DSN.
- Runtime, tests, maintenance tools, and dependency metadata are PostgreSQL-only
  as of 2026-09-20; the former compatibility adapter has been removed.
- Existing match-thread comments and flags disarm some paths, but the
  `auto_dq_match` invocation remains a required removal target.
