# Quickstart: Validate Challonge Tournament Support

## Prerequisites

1. Use an authorized Challonge sandbox/test tournament with at least four participants and a bracket that can produce a completed match and a DQ case.
2. Keep a separate existing Start.gg test tournament for regression verification.
3. Configure the required provider credentials only through the Hub settings or local environment; never commit them.
4. Install the project dependencies with the project Python version (3.12 or newer) and frontend dependencies.

## Local run

```powershell
python run.py
```

Open the Hub through the Vite server during development:

```text
http://localhost:5173/admin/hub
```

## Phase 1 Start.gg regression baseline — 2026-09-04

**Runtime used**: `.venv\Scripts\python.exe` (Python 3.12.11). The system `python`
invocation was also attempted first and was blocked before collection by the existing
environment condition `ModuleNotFoundError: aiosqlite`; this was not changed as part of
the provider project. The project virtual environment contains the declared dependency.

**Direct-provider inventory before V2 contracts**:

| Current path | Existing behavior to preserve |
|---|---|
| `backend/core/match_state.py` | Calls `mark_in_progress`, probes remote state for auto-DQ, and invokes DQ/double-DQ provider actions. |
| `backend/core/score_reporting.py` | Reports score/winner through the supplied provider and schedules Challonge refresh by provider name. |
| `backend/api/routers/matches.py` | Directly activates, DQs, resets, and assigns/removes Start.gg stream queue entries. |
| `backend/bot/match_threads.py` | Calls native `mark_called` and transitions local Ready workflow to in-progress. |
| `backend/bot/main.py` | Drains Start.gg-specific go-live/finish command effects. |

**Baseline command**:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_startgg_provider_baseline.py backend/tests/test_startgg_workflow_baseline.py backend/tests/test_provider_feature_flags.py backend/tests/test_startgg_mark_called.py backend/tests/test_score_reporting.py backend/tests/test_on_stream_overlay.py backend/tests/test_station_stream_coupling.py backend/tests/test_call_match_unification.py backend/tests/test_check_in_source.py backend/tests/test_startgg_sync_transitions.py
```

**Recorded result**: 41 passed, 8 warnings. The warnings are existing FastAPI
`on_event` and naive-UTC `datetime.utcnow()` deprecations; neither is changed in Phase 1.
All provider-migration flags remain `false`; no new flag is read by a runtime path.

## Test-suite scope and Phase 4 identity checkpoint — 2026-09-04

The official project test command always uses the repository virtual environment and
the maintained test tree:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
```

Do **not** use bare `pytest` from the repository root as a release claim yet. It also
collects [scratch/test_startgg_fetch.py](../../scratch/test_startgg_fetch.py), a
tracked historical scratch script outside `backend/tests`. Its import failure
(`backend.core.startgg_client`) was present before this provider-isolation feature and
is neither removed nor repaired here. Phase 10 must define the full release suite
explicitly before reporting a full-suite result.

Phase 4 is intentionally identity-only. A Challonge import performs one scoped
tournament-metadata resolve through `Hub endpoint → SyncCoordinator → adapter →
client`, then stores the stable provider/account/community/canonical-ID identity. It
does not download a bracket, participants, or matches; it does not start a worker or
poll; and it never starts a tournament, changes a match, reports a score/DQ, assigns a
stream, or writes Hub workflow state. The UI therefore exposes only connection state
and identity preview; bracket and lifecycle controls remain disabled until their later
phases.

## Phase 5 read-only snapshot checkpoint — 2026-09-05

Challonge bracket reads are enabled only when `CHALLONGE_READ_ENABLED=true`; every
other provider flag remains false by default. `Sync Bracket` performs one Coordinator-
admitted full snapshot (one paginated participants collection plus one paginated matches
collection in the current adapter), then publishes its mapped SQLite projection in one
transaction. It never sends a score, DQ, lifecycle, station, or stream mutation.

Dashboard and Match Card reads use SQLite. Economy mode has no periodic poll. Its
`economy_sync_on_stale_open` setting defaults to true: a stale dashboard can schedule
one background refresh, while repeated rendering or Match Card opening joins that one
operation. Turn the setting off for a fully manual Economy workflow and use `Sync now`.
The Hub displays `Last provider sync` and the current sync status; the last healthy
snapshot remains readable if a later page or mapping fails.

## Phase 6 read-only progression checkpoint — 2026-09-05

The active-match response now adds a pure display projection. It keeps provider facts,
Hub workflow, Discord evidence, and synchronization health independent: for example a
Challonge match can display `Provider: open`, `Hub: called`, and `Sync: local_only` at
the same time. `provider_state_raw` is diagnostic-only (the chip tooltip); the
normalized state is the only provider value displayed as an operational state.

The projection does not write SQLite, contact either provider, enqueue Discord/OBS,
run Completion Service, change stations, or schedule work. Discord is shown only when
a persisted message/thread/ready timestamp exists; `hub_status=called` alone never
claims delivery. TBD and bye matches remain non-actionable, and legacy Start.gg rows
without V2 fields retain their former cards with no empty chips.

The provider-focused regression command (the Phase 1–6 files) completed with **122
passed, 8 warnings**: the prior 117 checks plus five Phase 6 projections/API-read
checks. `npm run build` also succeeded. The broad default collection command still has
an existing filename collision between `backend/tests/core/providers/challonge/test_mapper.py`
and `backend/tests/core/providers/startgg/test_mapper.py`; it is recorded for the
Phase 10 release-suite decision and was not changed during this display-only phase.

## Phase 7A local-workflow checkpoint — 2026-09-05

With `CHALLONGE_LOCAL_WORKFLOW_ENABLED=true` only, Challonge Call, each Ready,
local Start, and local station assignment are Hub operations. Each one commits the
legacy-compatible status, V2 Hub/sync axes, reconciliation audit entry, and one or
more durable `workflow_outbox` intents in the same SQLite transaction. The bot starts
the outbox dispatcher only under that flag; its Discord/OBS work is marked complete
only after the dispatcher returns, and duplicate/recovered events are suppressed by
their `deduplication_key`.

Completion uses `stations.active_match_id` as an ownership proof. It releases a station
only when the completed match owns it, and repeated completion decisions do not emit a
second close/OBS/next-match event. Challonge Discord recipients come only from a
verified stable entrant identity link or explicit organizer override—never a matching
display name.

`CHALLONGE_SCORE_COMMANDS_ENABLED` and `CHALLONGE_DQ_COMMANDS_ENABLED` remain false
by default. With those defaults, Score, DQ, reset, and reopen reject a Challonge
request before any provider call. Any score-flag test must use mocks or a disposable
tournament, never FNC production.

## Phase 7B score-verification checkpoint — 2026-09-05

The score flag is still false by default and was tested with mocks only; FNC production
was not contacted. When a disposable environment explicitly sets
`CHALLONGE_SCORE_COMMANDS_ENABLED=true`, aiTOB sends the JSON:API v2.1 payload
`winner_id` plus `points_by_participant`—never the legacy `scores_csv` field.

A stale match first obtains one coordinator-coalesced `single_match` preflight. It
validates remote entrants/state, writes a durable ledger row, sends exactly one
mutation, then marks it `acknowledged` rather than complete. A targeted
`result_verification` snapshot must confirm completed state, both entrants, winner,
and both scores before Completion Service frees the owned station and emits its outbox
effects. Re-submitting the same pending result performs verification only; a different
pending result is rejected. Unknown timeouts are also verified before any retry.

DQ, reset, reopen, and double-DQ remain unavailable for Challonge.

## Phase 8 recovery and Live checkpoint — 2026-09-05

Recovery builds a new plan from SQLite on startup; it does not retain an old Python
object. Called/Ready timestamps, thread ID, station ownership, pending Outbox effects,
and command leases are read again by the new context. Lease claims include a durable
`lease_owner`, expiry, atomic SQLite claim, and owner-checked completion/retry. A
reclaimed remote command is verification work only—recovery never blindly repeats an
unknown mutation.

Attendance deadlines are UTC. A future deadline is rescheduled for its remaining
duration. An overdue deadline becomes `needs_review`; it never triggers an automatic
DQ after downtime. A terminal or externally completed match cancels the timer and
cannot receive a late attendance warning.

Live is still opt-in (`challonge_sync_mode=live`); Economy remains the default and
starts no polling. Live has one scheduler per tournament and records one reason per
cycle: `pending_verification`, `live_active_match`, `live_called_match`, or
`live_idle`. Its cadence is respectively 5, 5, 5, or 15 minutes, stops for completed
or archived tournaments, and is cancelled when switching back to Economy. Provider
429/backoff remains provider/account-local.

The frozen Start.gg baseline now contains **47** tests rather than the original 41:
the six extra checks are additive baseline coverage for native call, score, stream,
station, and transition compatibility; no original test was removed or changed.

## Phase 9A DQ sandbox gate — tested and unavailable

`0/-1` is implemented only as a redacted JSON:API *candidate* for one verified
winner: slot 1 produces `[0, -1]`, and slot 2 produces `[-1, 0]`. It is not a
claim about Challonge's public rendering. The candidate has tests for both slots and
rejects double-DQ/missing-winner cases, but it cannot be dispatched: the provider
capability is `unavailable` even if `CHALLONGE_DQ_COMMANDS_ENABLED=true`.

On 2026-09-05, the two-slot live test ran only against the disposable
`fnc-jo` tournament **FNCTest2026** (numeric ID `18449397`), never FNC
production or `testfnc`. It sent the candidate payload for both directions:

- match `471045156`: Snapboom winner, `[0, -1]`;
- match `471045157`: 0feras0 winner, `[-1, 0]`.

Both PUT requests returned HTTP `200`, but independent full snapshots immediately after
each request still reported the matches as `open`, with no scores, no winner, and no
advancement. A new load of the public bracket showed the same unresolved first-round
pairs. An HTTP success therefore is not evidence that Challonge applied a DQ result.

The rollout decision is **DQ unavailable**. T066 stays open, the flag remains false,
and aiTOB must direct an organizer to resolve a DQ in Challonge itself until a different
documented payload proves score, winner, advancement, and public rendering. No upstream
timeout or token-expiry fault was induced on the live test tournament.

## Phase 9B repair dry-run gate

The Dry Run endpoint accepts a reviewed immutable `snapshot_id`, UTC observation time,
and provider-state map; it performs no provider request. Its persistent report exposes
tournament, match key, previous status, raw/normalized provider state, local workflow
evidence, eligibility, proposed change, and reason, plus an immutable fingerprint.

Only a Challonge row with remote `open`, legacy `in_progress`, and no Call/Ready/thread/
station/score/local-audit evidence is eligible. Start.gg, stations, and `testfnc` are
excluded. Apply code verifies the stored report fingerprint and exact eligible set.

### Approved FNCTest2026 repair — 2026-09-05

The organizer approved immutable report `17639089-d411-4c59-8196-d3fd63896a4f`
(fingerprint `0c328f2257498ded051b3eac96eee0d1e351e49ca191b2002a81f58c561119cd`).
Immediately before writing, a fresh Challonge snapshot confirmed that exactly
`471045156`, `471045157`, `471045159`, and `471045161` remained `open`, while
SQLite showed no Call/Ready/thread/station/score/local-audit evidence. The transaction
performed two coupled writes from that same immutable report evidence: it first fixed
the provider projection to `open` / `not_started`, then repaired `status` and
`hub_status` from `in_progress` to `not_started`. It recorded one `state_repair_apply`
audit record per row and sent **zero provider mutations**. It does not consult a new
provider read inside the transaction; the immediately preceding fresh read must match
the report evidence before the transaction is allowed to begin.

The repaired rows retain their provider match IDs, players, and round names, and now
store `provider_state_raw=open` plus `provider_state_normalized=not_started`. The 15
pending Challonge rows, stations, Start.gg, and `testfnc` were unchanged. Reapplying
the same report is idempotent and changes zero rows. The dashboard therefore presents
these four two-player matches as not started and eligible for the local Call workflow.

## Validation path

1. Confirm service status shows the bot connected and the selected provider connection ready.
2. Add the Start.gg test tournament and confirm its existing matches remain visible and actionable.
3. Add the Challonge test tournament, select it in the Hub, and confirm its provider label, participant names, rounds, and non-bye matches match the remote bracket.
4. Start a new browser session and confirm the import form exposes an explicit Start.gg/Challonge selector. Choose Challonge and first validate numeric ID and normal URL while the optional subdomain control is off; then enable it and validate subdomain URL and legacy `subdomain-slug` forms against the same sandbox tournament.
5. Confirm the stored record uses Challonge's numeric tournament ID and that re-importing through another URL form does not duplicate it.
6. Refresh the Challonge tournament after a remote bracket change; confirm one Hub match per remote match and preservation of Hub-only station/thread fields.
7. Call a two-player Challonge match through the Hub. Confirm the Discord-driven check-in workflow is used when native match check-in is unavailable.
8. Report a score, a Round Robin/Swiss tie, and a separate DQ scenario. Confirm remote bracket and Hub agree before continuing.
9. If the sandbox enables Challonge stations, map one to an aiTOB station and verify remote assignment without breaking local overlay routing.
10. Restart with deliberately stale local records only in a disposable test database. Immediately request current matches from the bot and verify no stale ID is returned.
11. Run the Python and frontend regression suites using the configured project runtime, then record the sandbox result in the release checklist.

## Provider-isolation validation

1. In a mixed Start.gg/Challonge test database, confirm each Match Card shows a textual
   provider badge plus separate Hub and remote state when they differ.
2. For a Challonge `open` match, call and start it in aiTOB. Confirm Discord, station,
   and overlay proceed locally while the public Challonge bracket remains `open` and no
   provider lifecycle request appears in request telemetry.
3. For a Start.gg match, repeat call/start and confirm its native lifecycle/stream
   behavior remains unchanged.
4. With a local station occupied by a Start.gg match, open the Challonge dashboard and
   confirm occupancy identifies the actual owner and no station is automatically freed
   or reassigned.
5. Run the Challonge repair migration in dry-run mode. Review every proposed row; it
   must affect only Challonge matches lacking local workflow evidence. Apply only after
   the report is accepted.
6. Keep Challonge DQ disabled until the disposable bracket proves v2.1 result payloads
   and the public `0/-1` display in both slots. A failed proof must leave local status
   unchanged and show an organizer action message.

## Recovery and remote-change validation

1. Submit a provider-backed result, interrupt aiTOB after the upstream acknowledgement
   and before local completion, then restart. Confirm its command is restored and becomes
   snapshot-verified, retryable, conflict, permanent-failure, or needs-review without a
   duplicate mutation.
2. Enter a result, DQ, reset/reopen, entrant change, or cancellation directly at the
   provider. Sync and confirm aiTOB emits one idempotent completion/review decision,
   updates the correct station/Discord/overlay state, and exposes any conflict.
3. Call a Challonge `open` match locally. Confirm Discord thread, Ready timestamps,
   attendance deadline, warning, station, and OBS state survive restart while provider
   state remains independently `open`.
4. Simulate a 429, network failure, and expired token separately for both providers.
   Confirm only the affected provider's commands back off; the other provider and
   aiTOB-local operations continue, with unsent commands visibly pending/retrying.
5. Change an entrant after a local Call. Confirm the old call is invalidated, no former
   player receives a new mention, and the replacement receives one only after a verified
   provider-to-Discord identity link exists.

## API-budget and scope validation

1. Refresh the dashboard and open/close a Match Card ten times. Confirm all reads are
   SQLite-only and provider request telemetry remains unchanged.
2. Trigger compatible Sync actions concurrently from dashboard, bot, and Discord. Confirm
   one `provider + account + tournament + scope` operation runs and other callers join it.
3. Trigger Ready, Call, station assignment, thread creation, and OBS update repeatedly.
   Confirm local-only actions make no provider request.
4. Report a result where targeted match fetch is available. Confirm verification reads
   the single match and advancement neighborhood, not participants/full bracket.
5. Inspect the budget report: it includes provider/account/tournament/reason/scope/cost
   and the provider-specific 429 backoff. Confirm a provider 429 pauses only its own
   background work and a completed tournament schedules no polling.

## Failure expectations

- Invalid credentials, inaccessible tournament, expired authorization, rate limits, and unsupported actions must be visible as redacted provider errors.
- A failed initial synchronization must block match actions and bot match answers for that provider; it must not silently use prior local records.
- Challonge's lack of a Start.gg-only feature must not prevent local stations, overlays, or Discord coordination when those are otherwise configured.

## Phase 10 controlled rollout and rollback

Enable one flag at a time and observe the listed success signal before proceeding. A
rollback always stops new work first; it never rewrites already snapshot-verified data.

| Step | Flag / prerequisite | Success signal | Rollback trigger | Safe rollback / pending work |
|---|---|---|---|---|
| 1 | Foundation contracts only | Start.gg legacy baseline is unchanged | Any legacy request-shape difference | Disable V2/coordinator flags; no commands exist in this step. |
| 2 | Start.gg V2 parity | GraphQL parity suite and live read comparison agree | Different operation, variables, mutation count, or side effect | Disable `PROVIDER_V2_CONTRACTS_ENABLED` and `PROVIDER_COORDINATOR_ENABLED`; do not fall back after a mutation. |
| 3 | `CHALLONGE_READ_ENABLED` | Identity/import/snapshot telemetry is healthy and dashboard freshness is current | auth error, pagination failure, stale projection, or Challonge 429 | Disable read flag; SQLite remains readable. Let admitted snapshots finish; cancel only background schedules. |
| 4 | `CHALLONGE_LOCAL_WORKFLOW_ENABLED` | Call/Ready/Station/Discord/OBS outbox actions are exactly-once with zero Challonge lifecycle calls | duplicated outbox effect, wrong recipient, or station conflict | Disable local workflow flag after draining/reviewing outstanding outbox records. Existing calls remain persisted for manual recovery. |
| 5 | `CHALLONGE_SCORE_COMMANDS_ENABLED` in a controlled rollout | Ledger reaches `snapshot_verified` with score, winner, and advancement evidence | verification timeout, changed entrants, conflict, or provider outage | Stop new score commands; retain ledger rows and run verification/review—never re-send an unknown mutation. |
| 6 | Live mode per selected tournament | adaptive cadence, provider-isolated backoff, and completed-tournament stop all hold | unexpected provider volume, overlap, or backoff leakage | switch that tournament to Economy; pending verification retries continue independently. |
| 7 | DQ | **Not eligible**: `CHALLONGE_DQ_COMMANDS_ENABLED=false` | N/A | DQ stays disabled. The failed two-slot proof must not be replaced by `1-0`. |

Flags must never be enabled as a single first-run bundle. DQ is excluded from rollout,
and Phase 11 remains deferred until production evidence proves all consumers use the
new path safely.

### Phase 10 automated regression baseline — 2026-09-05

The release-suite command is the project virtual environment, never the system Python:

```powershell
.\.venv\Scripts\python.exe -m pytest <explicit backend test list>
```

The explicit provider release list is required because broad collection still has the
pre-existing duplicate `test_mapper.py` module-name collision. It ran as two groups:
**47 Start.gg baseline/parity tests** and **111 provider, migration, coordinator,
Challonge, recovery, outbox/ledger, repair, freshness, and budget tests**—all **158
passed**. React ran **33 tests**, and `npm run build` plus `git diff --check` passed.

The Phase-10 tests prove cached dashboard reads do not perform a provider operation,
the stale-open admission is separate from that read path, coordinator containment and
coalescing hold, completed tournaments do not enter the Live loop, and DQ remains an
unavailable capability. The FastAPI deprecation and aiosqlite event-loop-cleanup
warnings are recorded test-environment warnings, not failures.

### Manual acceptance still required before controlled rollout

The local Dashboard requires the Hub password, and the current test context has no
authorized Discord/OBS runtime to safely send a real Call. Before enabling any rollout
flag, an organizer must execute the mixed-provider matrix: verify the four repaired
FNCTest2026 matches render as Not Started, Call is enabled only for their two resolved
entrants, the 15 pending rows remain unavailable, and repeat the documented Discord,
OBS, provider-outage, restart, and conflict checks. T073 remains open until that
operator-run evidence is recorded.

Using the local authenticated Hub API on 2026-09-05, the four repaired rows returned
`not_started` / `open` with their original players and rounds; the remaining 15 rows
still had at least one TBD entrant. As all workflow feature flags remain disabled by
default, the live action projection intentionally omitted Call at this point. The
automated Dashboard test proves Call renders only when the server projects an eligible,
two-sided local action; the operator must repeat that check after the separate local
workflow rollout step.

### Isolated acceptance environment

Use `.env.acceptance.example` to create a local `.env.acceptance`, then run
`./scripts/run_phase10_acceptance.ps1 -Stage <1..6>`. The runner requires an
`acceptance` SQLite filename, binds only to localhost, forces DQ false, and enables
flags cumulatively by stage: contracts, coordinator, read, local workflow, score, then
Live-mode validation. `-WithBot` refuses to start without a test-only Discord token and
channel ID. Do not copy the production database, use FNC or `testfnc`, or reuse a
production Discord bot/OBS profile.

### Pre-activation regression and AI-service check — 2026-09-07

Before this check, a consistent SQLite backup was made with the SQLite backup API and
verified with `PRAGMA integrity_check`; a separate copy of the operating database was
then migrated and verified with the same check. The migration added the AI service
tables without rewriting tournament data. The account-scoped Gemini credential was
migrated into encrypted service storage only after that backup; its legacy source was
retained for rollback. No credential value, Discord identifier, or provider token is
recorded here.

The official broad backend command now has package markers for the two provider mapper
directories, so it collects correctly instead of colliding on their identical
filenames. This isolated command completed with all provider flags disabled:

```powershell
$env:DB_PATH = ".acceptance/full-suite.sqlite"
$env:CHALLONGE_READ_ENABLED = "false"
$env:CHALLONGE_LOCAL_WORKFLOW_ENABLED = "false"
$env:CHALLONGE_SCORE_COMMANDS_ENABLED = "false"
$env:CHALLONGE_DQ_COMMANDS_ENABLED = "false"
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Result: **325 passed** (16 existing deprecation warnings). React completed **41
tests**, `npm run build` completed, and `git diff --check` found no whitespace errors.
The broad suite uses an isolated SQLite file and performs no Discord, Challonge,
Start.gg, OBS, or Gemini operation.

Gemini was tested only from an isolated SQLite copy containing a synthetic tournament.
The saved key decrypted through the service master key and the explicit provider
connection check succeeded. A synthetic assistant request did not complete before the
provider/SDK timeout and was recorded as a failed isolated usage entry; it created no
proposal or operational effect. The adapter now passes the configured service timeout
to the Gemini SDK as well as enforcing it externally, with a unit test. Production
mode remains `disabled`; no API or bot service was restarted for this check.

T073 remains open. The remaining evidence is the live, test-account-only matrix:
Discord call/thread/ready and exactly-once Outbox delivery, browser-source update,
one normal disposable Challonge result with verification/advancement, provider outage,
restart recovery, conflict handling, and flag rollback. Do not start the updated API
or bot against the operating database until that controlled window is prepared: API
startup currently performs a Start.gg permission probe and tracked-tournament sync;
bot startup drains eligible work, restores local workflows when enabled, and syncs its
Discord command tree. Stop services first, confirm no unsafe pending work, use the
isolated database and test-only destinations, then enable one rollout flag at a time.

### T073 isolated acceptance evidence — 2026-09-07

A consistent preflight backup of the acceptance database was verified with `PRAGMA
integrity_check`. Its test-only services then ran cumulatively through Stages 2–6 on
`127.0.0.1:8001`; services were stopped after rollback. All identifiers below are
logical labels only—no credentials, Discord identifiers, provider tokens, or command
UUIDs are recorded.

| Scenario | Result | Evidence |
|---|---|---|
| Stage 2 cache/coordinator | Pass | The API served only the one acceptance tournament and the station overlay telemetry from SQLite. |
| Stage 3 Challonge read | Pass | An explicit bracket sync returned success and durable freshness became `ready`. |
| Discord local workflow | Pass | A synthetic local match with two existing verified test identities produced one Call, one thread, two Ready effects, and all Outbox entries completed once. A repeated Call was rejected and did not add another Call event. |
| OBS Browser Source | Pass (API data) | The live Browser Source target was `http://127.0.0.1:8001/obs?slot=station_2`; its public telemetry reflected the assigned match's two names and the score changed through the Hub endpoint. The Codex in-app browser blocked opening this localhost endpoint, so visual rendering in a browser tab was not independently witnessed. |
| Normal Challonge result | Pass | A stale local result was preflighted, submitted once, and reached `snapshot_verified`; the projected score, winner, complete state, station release, completion Outbox effects, and downstream bracket slot all agreed after a sync. |
| Provider-originated conflict | Pass | A separate acceptance match was changed through the Challonge adapter first. The conflicting Hub draft was refused with HTTP 409, became `needs_review`, and created no provider command. |
| Restart / exactly once | Pass | API and bot were stopped and recreated from SQLite. Previously completed Call, Ready, completion, and OBS effects retained one attempt each; no pending Outbox row or duplicate effect appeared. |
| Live-mode rollback | Partial | The tournament entered `live` and was returned to `economy` through its settings endpoint. The five-minute cadence was not waited through in this controlled window. |
| DQ / AI safety | Pass | DQ remained rejected while the sandbox flag was false. AI stayed disabled and had no execution or approval path. |
| Start.gg live adapter | Blocked | The acceptance database has no Start.gg account or disposable Start.gg tournament. Start.gg's automated parity and contract suite passed, but it was not exercised against a live provider. |
| Live provider outage | Blocked | The acceptance account was not deliberately corrupted; automated outage/recovery coverage passed, but no live token-failure test was performed. |

The acceptance run exposed a station-ownership defect: unassigning a match could leave
`stations.active_match_id` behind. A regression test now proves that the endpoint
clears that physical owner only when it belongs to the exact match; the full suite
passed after the fix.

Final regression after this run: **325 backend tests passed**, **41 React tests
passed**, `npm run build` passed, and `git diff --check` reported no whitespace
errors. T073 is **not marked complete** until the two blocked live cases are supplied
with disposable accounts/tournaments and the Live cadence is observed for its full
interval. Restoring the SQLite backup is only a local rollback; it does not undo the
completed Challonge test results or test-channel Discord messages.

### T073 gap follow-up — 2026-09-07

The acceptance follow-up used the same isolated database and localhost-only API. No
operating database, production Browser Source, token, or provider credential was
changed. A SQLite backup made before the check remained readable.

| Scenario | Result | Evidence |
|---|---|---|
| Manual DQ versus AI/Auto-DQ | Pass (policy separation) | The manual single-player route remains separately gated by its own explicit provider capability and maps only one forfeiting player to `-1/0` or `0/-1`. The AI tool allow-list has no DQ/approval/execution action, and Challonge Auto-DQ exits before any provider operation. With the acceptance DQ flag false, no manual DQ request is admitted; enabling AI or an attendance timer cannot change that. |
| Acceptance Browser Source in a browser | Pass | A separate acceptance Vite host proxied only to the acceptance API; the operating Browser Source on port 5173 was not edited. At 1920×1080 the page rendered the test players, placeholder images, tournament/round data, and scores. A Hub-local score update was reflected in a new browser render. After the acceptance API restart, the unchanged browser source again loaded current SQLite data. |
| OBS Studio visual check | Pending separate observation | OBS Studio has no control-WebSocket dependency in aiTOB and no test Browser Source session was open for this check. The browser rendering evidence is complete; adding the prepared acceptance URL to a test-only OBS Browser Source remains a separate visual observation, not a service requirement. |
| Five-minute Live then Economy cadence | Pass | Live mode produced coordinator-owned Challonge request telemetry during the full five-minute interval. After switching back to Economy, a second full five-minute observation recorded no scheduled provider request. The test measures request telemetry rather than only a snapshot timestamp, so an unchanged remote revision cannot create a false failure. |
| Reversible provider outage and recovery | Pass | The acceptance API alone was started with a process-local invalid proxy; a manual provider sync failed with a redacted 502 while an eligible local Call persisted with one durable Outbox intent. Restarting a normal acceptance API process recovered the same SQLite workflow state, then an explicit provider sync succeeded. No token was changed and no Discord worker was run. |
| Restart recovery (separate from scheduler switching) | Pass | The outage process was stopped, a fresh API process loaded the acceptance SQLite database, and the local Call and its single pending Outbox record survived. This proves local state recovery only; the earlier exactly-once Discord/OBS record remains separate evidence because restoring SQLite cannot undo an already external message or provider result. |
| Start.gg live acceptance | Blocked | The acceptance database has no test-only Start.gg organizer credential/account, disposable tournament/event with two resolvable test entrants, or verified entrant-to-test-Discord identity links. No real Start.gg tournament was substituted. |

The prepared acceptance Browser Source is served by the separate acceptance frontend
while the acceptance API is running; it uses `/obs?slot=<acceptance-station>` on that
frontend host. This page uses aiTOB's FastAPI WebSocket (`/ws/overlay/<slot>`) solely
to refresh overlay data. It is not OBS WebSocket: aiTOB does not connect to, select a
profile/scene in, or otherwise control OBS Studio.

## User, session, and owner-workspace foundation

This additive foundation introduces `users`, `workspaces`,
`workspace_memberships`, and `user_sessions`. It does **not** yet migrate
tournaments, stations, provider accounts, matches, jobs, or WebSockets to a
workspace. Their existing records must therefore continue to be treated as
owner-workspace operational data until a separate ownership migration is
accepted.

There is no public registration and no default `admin` account/password. For a
new deployment, create the initial owner exactly once through the service
environment before starting the API:

```powershell
$env:AITOB_BOOTSTRAP_OWNER_EMAIL = "owner@example.com"
$env:AITOB_BOOTSTRAP_OWNER_PASSWORD = "use-a-unique-password-of-at-least-12-characters"
$env:AITOB_BOOTSTRAP_OWNER_NAME = "Primary organizer"
$env:AITOB_BOOTSTRAP_WORKSPACE_NAME = "Primary organizer workspace"
```

`init_db()` creates one user, one workspace, and one `owner` membership in a
single transaction only when there are no users. Later starts do not create
another owner. Remove the two bootstrap credential variables after the owner
has signed in; they are not a recovery or registration mechanism.

The browser uses an HttpOnly, SameSite session cookie issued by
`POST /api/session/login`; passwords and session secrets are not stored in
`localStorage` or returned by the API. `POST /api/session/logout` revokes the
server-side session. Session expiry is configured with `AITOB_SESSION_TTL_HOURS`
(default 12; 1–744 permitted). Set `AITOB_SESSION_COOKIE_SECURE=true` on HTTPS
deployments.

Role permissions are centralized but legacy operational routes are not yet
workspace-scoped. Until the ownership migration, only an Owner should be given
access to the existing Hub routes:

| Role | Foundation permissions |
|---|---|
| Owner | all workspace/settings/integration/tournament/match/result/manual-DQ/proposal actions |
| Organizer | workspace/settings/tournament/match/result/manual-DQ/proposal actions |
| Operator | workspace read and match operation |
| Viewer | workspace read only |

`AITOB_LEGACY_HUB_PASSWORD_COMPAT=true` is a temporary migration bridge for
older clients sending `X-Hub-Password`. It is **off by default**, requires an
explicit existing password (there is no fallback), and maps only to exactly one
active Owner membership. It must be removed once all clients use `/api/session`;
it is never a general session or workspace bypass. The bot has no dependency on
this HTTP header in its local workflow path.

Run workspace tests only against an isolated SQLite file:

```powershell
$env:DB_PATH = ".acceptance/workspace-auth-suite.sqlite"
.\.venv\Scripts\python.exe -m pytest backend/tests/test_workspace_sessions.py -q
```

## Backend test isolation

Pytest loads the repository [conftest.py](../../conftest.py) before importing
application or test modules. It assigns `DB_PATH` and `AITOB_TEST_DB_PATH` to
a newly-created temporary SQLite file and sets `AITOB_TESTING=1`. In that mode,
`database.py` refuses a missing `DB_PATH` fallback and refuses any database path
inside the project workspace. Tests that need their own database use pytest's
`tmp_path`; no fixture may use `backend/core/test_*.sqlite`.

External sockets are blocked by default (loopback is allowed for in-process
test servers). A real-provider test must be marked `live_external` and run only
with `AITOB_ALLOW_LIVE_TESTS=true`; it is otherwise skipped. The local backend
suite has no live test enabled by default.

The earlier identity-record incident was traced to the former
`backend/tests/conftest.py`: it imported `backend.core.database` before a test
database was selected, then its autouse setup called `init_db()`. Several older
fixtures also redirected to fixed `backend/core/test_*.sqlite` files. The
confirmed effect was one known test owner/workspace record; it was backed up and
removed by its exact test email and membership relation. The prior value of an
already-existing global password setting cannot be reconstructed from SQLite
history, so no speculative cleanup was performed.

When this guide says “migration on a read-only copy”, the **source** operating
SQLite database is opened using SQLite `mode=ro` and read with the backup API.
The backup target is a separate, writable temporary file. `init_db()` and the
migration execute only on that target; integrity and selected operational row
counts are then checked there. The source database is never migrated or written
by that verification.

### Verification — 2026-09-07

The isolated local Backend suite was run with the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Result: **341 passed, 1 skipped** in 101.10 seconds. The sole skip is the
legacy AI Referee result-inference benchmark, which is intentionally disabled
until Result Claims exist. No live-provider test was enabled, and the socket
guard rejected non-loopback network access by default. `git diff --check` also
completed successfully (line-ending notices are informational only).

## PostgreSQL development migration

Development PostgreSQL runs as the isolated `postgres` Docker service on host
port `5433`; it does not replace or bind to an already-installed PostgreSQL on
port `5432`. Its credentials and `DATABASE_URL` belong only in the ignored
`.env.production` file. Do not place them in a fixture, repository file, or
chat transcript.

Use the one-way migration command only after taking a consistent SQLite backup:

```powershell
.\.venv\Scripts\python.exe scripts/migrate_sqlite_to_postgres.py `
  --source backend/core/database.sqlite
```

The command opens its source through `mode=ro`, verifies SQLite integrity,
creates the PostgreSQL schema, copies each table in dependency order, validates
row counts before commit, and never decrypts or prints credential ciphertext.
It refuses a non-empty target by default, preventing accidental merge or
dual-write behavior.

On 2026-09-07, the current operational SQLite snapshot was copied to the
isolated PostgreSQL development database: **44 tables migrated and all source
and target row counts matched**. This proves the migration path only; it does
not by itself switch the running API/Bot to PostgreSQL.

## Phase-11 attendance safety checkpoint — 2026-09-20

The pre-refactor working tree was committed on `main` as `9991bb4`. The first
implementation slice changed Start.gg organizer DQ controls into per-entrant
`withdrawn` attendance intents, removed manual Double-DQ, disabled the legacy
automatic-DQ mutation shim, and replaced the fabricated ten-minute Start.gg
countdown with provider-owned timer messaging.

Focused verification:

```text
24 passed — Start.gg attendance, activation, provider and workflow baselines
18 passed — attendance expiry, recovery, and no-automatic-DQ safety
13 passed — ActiveMatchCard provider-aware DQ/attendance behavior
frontend production build — passed
git diff --check — passed (line-ending notices only)
```

The complete backend run produced **539 passed, 35 skipped, 17 failed**. The
failures reproduce independently and concern pre-existing missing setup tables
or migration columns in test fixtures, old Start.gg V2-axis expectations, and a
tournament-removal expectation that conflicts with current blocking behavior.
The complete frontend run produced **44 passed, 6 failed**: five old
`HubDashboard` tests render a component using `useNavigate` without a Router,
and one `TopNavigation` test expects a superseded confirmation string. The
focused changed-area suites and production build are green, but these full-suite
failures prevent T075 closure.

The public Start.gg schema did not expose a documented per-entrant attendance
write. Until disposable T073 acceptance proves an authorized contract, aiTOB
stores the attendance intent with `sync_status=needs_review`, never sends a
technical winner, and treats the provider snapshot as the only bracket truth.

### Start.gg disposable native-wave evidence — 2026-09-20

The organizer authorized live observation of the disposable Start.gg tournament
`tournament/testfnc` (tournament `917260`), event `FNCtestHub` (`1640502`), and
phase group `3339325`. No aiTOB score, DQ, or technical-winner mutation was sent
during this observation.

Start.gg reported first-round sets `107981340` and `107981341` as `CALLED`, each
with two resolved test entrants and no winner. The organizer observed the native
15-minute no-show timer. Start.gg then completed both sets autonomously and
returned `displayScore="DQ"`, `state=COMPLETED`, a provider-selected `winnerId`,
and provider-owned downstream progression. Subsequent native no-show processing
completed the remaining bracket and changed the Event and phase group to
`COMPLETED`.

This proves the required **neither entrant appears** path: aiTOB sends no timeout
mutation, waits for Start.gg, and reconciles the provider result. It also proves
that `winnerId` alone cannot distinguish a played result from a provider-created
DQ; reconciliation must retain the provider's DQ evidence and must not describe
that field as an aiTOB-selected technical winner.

The live Event response exposed `checkInBuffer=900`, matching the organizer's
observed 15-minute timer, while `checkInEnabled=false` and `checkInDuration=0`.
Those latter fields therefore do not describe this match-level native wave. The
public Set schema exposed no per-set deadline and the exposed `startedAt` and
`completedAt` interval did not independently reproduce the visible 15-minute
countdown. aiTOB must treat `checkInBuffer` as provider duration evidence, not
invent an exact deadline from ambiguous timestamps; it should show an exact
countdown only after a provider-owned absolute deadline or a verified call
timestamp is available.

T073 remains open. The same disposable acceptance still needs the **both present**
score path, the two **exactly one present** directions using real test-player
check-in, and the live provider-outage/recovery case. These require authenticated
test-player sessions or an authorized per-entrant Start.gg contract; the public
schema exposes neither a per-entrant attendance write nor a match deadline.
