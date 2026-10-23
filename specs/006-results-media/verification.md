# Verification: Tournament Results Media (spec 006)

**Date**: 2026-09-29  
**Scope**: implementation review, defect repair, PostgreSQL verification, and release-gate audit

## Review outcome

The previous “84/84 complete” report was not accepted as evidence. It recorded
collection-only failures as successful execution, treated automated coverage as
a manual walkthrough, and declared the diff clean while unrelated working-tree
changes were still present.

The implementation has now been exercised against PostgreSQL and repaired.
Automated gates T080-T082 pass. Manual acceptance T083 and final scope review
T084 remain intentionally open.

## Corrective Result Card scope (2026-09-29)

The first-pass editor assumptions were superseded after visual acceptance
failed. The corrected product has two explicit actions backed by one shared
Result Card definition and renderer:

- **Add Result Card** creates one atomic freeform card under a layout-neutral
  Results Cards scheduler. Its internals are edited only in focused design
  mode; its normal editor Animation settings can be replayed for Top 8,
  Top 16, or a bounded All page with overlapping stagger timing.
- **Add Results Group** retains Board/image templates and the established group
  sequence, but consumes the same Result Card definition. Explicit
  materialization creates linked editable cards without copying the definition.

Auto Sequence and Results Group preview instances are runtime values and are
never written to scene nodes. Only the stage card and deliberately materialized
linked cards are authoring nodes.

### Compatibility normalization mapping

Existing Scene v2 `results-group.templateId` is cloned in memory to
`results-group.cardDefinitionId`; `templateId` remains readable for backward
compatibility and is not rewritten merely by loading a scene. The referenced
legacy `group[templateRole=player-card]` is treated as the shared Result Card
definition. New freeform scenes persist a `results-cards` root, authored
`result-card` children, and one referenced
`group[definitionRole=result-card]`. Generated preview/runtime cards have no
serialization shape.

The backend scene boundary now accepts and validates both corrected consumers,
including parent/definition references, lifecycle numbers, scheduling bounds,
live Auto Sequence requirements, and the existing ban on generated nodes.

## Material defects found and repaired

- Start.gg final standings now paginate beyond ten pages, preserve global
  ordinals/ties, and reject duplicate or incomplete cross-page evidence.
- Challonge two-stage tournaments accept final-stage ranks without fabricating
  ranks for group-only participants.
- Provider finality, provider revision, and completion state participate in the
  immutable observation identity. An Active-to-Completed transition therefore
  creates a Final version even when placements do not change.
- A successful refresh can replace a stale verification without rewriting an
  old immutable version; concurrent identical creation remains idempotent.
- Result-version creation, export receipts, station binding, and commands use
  PostgreSQL transaction/CAS boundaries. Conflicting export receipts cannot
  rewrite the first receipt, and concurrent Next commands advance once.
- Frozen scenes reject generated instances, invalid ownership/cycles,
  mismatched result versions/cutoffs/profiles, invalid timing/geometry, and
  Board-only live outputs.
- Nested groups and circle primitives render, the shared Result Card animation is
  reused by generated instances, and row/column cue ordering follows slot
  geometry rather than placement order.
- Square and portrait profiles reflow scene nodes, template variants, and card
  slots instead of clipping a landscape canvas.
- All-results pagination is applied exactly once. The selected page size is
  shared by output validation, OBS projection, and playback cue calculation.
- Results Studio exposes a reachable live-output workflow and server-side Play
  All persists/broadcasts each CAS revision.
- Unknown provider exceptions no longer reflect arbitrary upstream text into
  API responses or result-refresh audit details.
- The manual smoke attempt exposed unsafe launcher port cleanup. `run.py` now
  refuses to terminate Docker/WSL/unrelated processes and supports an explicit
  alternate `AITOB_API_PORT` for source-versus-Compose coexistence.

## T080 — Focused backend result-media suite

Executed with `AITOB_PG_TEST_URL` set to the disposable PostgreSQL service.

Included all `test_results_media*`, `test_results_overlay*`, provider final-
standings tests, and production migration tests.

**Result**: `42 passed, 8 warnings in 18.03s`.

The warnings are existing FastAPI lifecycle/deprecation warnings and a local
pytest cache permission warning; no focused test failed or skipped.

## T081 — Full backend PostgreSQL suite

**Command**: `python -m pytest backend/tests -q`

**Result**: `691 passed, 1 skipped, 28 warnings in 295.66s`.

The single skip is an intentional legacy AI-referee inference skip pending the
separate Result Claims feature. PostgreSQL migration tests executed because the
test URL was present. No backend test failed.

## T082 — Frontend suite and production build

**Commands**: `npm test`; `npm run build`

- Vitest: `38 passed` test files, `137 passed` tests.
- TypeScript/Vite production build: succeeded; `1912` modules transformed.
- Vite reports only the existing large-chunk advisory for the main bundle.

### Corrective frontend evidence (2026-09-29)

- Focused Result Card/editor/resolver tests: passed.
- Full Vitest run after the correction: **48 files, 168 tests passed**.
- Production TypeScript/Vite build: passed; **1923 modules transformed**.
- Added coverage includes shared contract/renderer, legacy normalization,
  separate Add actions, focused card design, selected Layers state, Top 16
  linked-card insertion, template materialization, lifecycle interpolation,
  overlapping stagger timing, and local-only media fallbacks.

Backend Python compilation and a direct freeform scene validation smoke check
passed. The repository test harness correctly refused to run without
`AITOB_PG_TEST_URL`; no application `DATABASE_URL` or embedded fallback was
used. PostgreSQL-backed reruns remain open for the final release gate.

## T083 — Manual quickstart walkthrough

**Status: OPEN**

Automated tests cover mock datasets, static-output contracts, station CAS,
restart persistence, projection isolation, and two-Workspace access rules, but
that is not the manual walkthrough required by T083. The following still need
operator observation using the steps in `quickstart.md`:

1. Editor mock-data visual review and layer-selection boundaries.
2. Browser PNG comparison for landscape, square, and portrait profiles.
3. OBS Take Live / Hold / Play All / Clear plus API restart while held.
4. Event override then explicit Player Archive promotion.
5. Two real test Workspaces/stations/tokens and WebSocket isolation.

The source API and Vite smoke checks succeed on ports 8001 and 5173. Automated
browser control could not be initialized in this environment (the UI
automation kernel could not create its assets), so no visual observation is
claimed from this correction run.

## T084 — Final release diff review

**Status: OPEN**

- `git diff --check` is clean (line-ending notices only).
- Generated cards remain render-time instances and are covered by serialization
  regression tests.
- The working tree still contains pre-existing/unrelated `scratch/` deletions,
  an untracked `.claude/` directory, and other broad changes. They were
  preserved rather than silently deleted or included.
- Rotate the PostgreSQL credential used during this review before staging,
  because it appeared in earlier terminal/test output. No credential value is
  stored in this verification record.

T084 can be checked only after the owner decides which unrelated files belong
in the feature commit and the final staged diff is reviewed for secrets and
temporary artifacts.

## Gate summary

| Gate | Status |
|---|---|
| T075-T079 | Complete; covered by passing suites |
| T080 focused PostgreSQL tests | PASS — 42 passed |
| T081 full backend PostgreSQL suite | PASS — 691 passed, 1 intentional skip |
| T082 frontend suite/build | PASS — 137 passed, build successful |
| T083 manual quickstart | OPEN |
| T084 final staged-diff review | OPEN |

The code is automation-clean, but Spec 006 is not release-closed until T083 and
T084 are completed.
