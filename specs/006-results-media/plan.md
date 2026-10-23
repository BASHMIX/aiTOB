# Implementation Plan: Tournament Results Media — Shared Result Card

**Branch**: `006-results-media` | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: The existing results-media implementation plus the clarified editor workflow agreed with the product owner on 2026-09-29.

## Summary

Preserve the completed provider-authoritative standings, immutable results versions, PNG export, permissions, and dedicated results overlay. Correct the editor around one reusable **Result Card** primitive with two clear insertion paths:

1. **Add Result Card — freeform path**: insert and design one card, place and animate it freely, then either materialize Top 8/Top 16 cards on the canvas or use **Auto Sequence** to replay its animation for Top 8/Top 16/All without adding runtime layers.
2. **Add Results Group — template path**: keep the existing results-template workflow for composed social images and the previous group animation workflow, but make it consume the same new Result Card definition. The group may arrange repeated cards through a selected template; it must not own a separate “Master Card” implementation.

The shared Result Card is edited once. Freeform linked instances, template-generated cards, PNG export, preview, and OBS all render that same definition. Provider placement, result-version, Workspace-isolation, and OBS authority boundaries do not change.

## Technical Context

**Language/Version**: Python 3.12+; TypeScript/React 19 on Vite

**Primary Dependencies**: FastAPI, psycopg/PostgreSQL repositories, React, Zustand editor store, Vitest/Testing Library, existing DOM scene renderer and animation controls

**Storage**: PostgreSQL 17+ for result versions/media outputs/sessions; saved overlay scene JSON remains in the existing PostgreSQL-owned overlay configuration. No embedded or file-backed state.

**Testing**: `pytest` against `AITOB_PG_TEST_URL`; Vitest; frontend production build; browser acceptance in the editor and OBS viewer

**Target Platform**: Desktop web editor, browser-source OBS viewer, FastAPI/PostgreSQL services

**Project Type**: Existing web application with backend API, frontend editor, and browser overlay renderer

**Performance Goals**: Editor manipulation remains interactive; Top 16 mock preview starts without perceptible UI blocking; All results are paged/batched rather than mounted as an unbounded DOM; animation timing is deterministic after restart/replay.

**Constraints**: Preserve legacy/current-match overlays; no external placeholder images; no Auto Sequence or template preview card may leak into Layers, history, clipboard, or saved JSON; explicitly inserted cards are lightweight linked instances; ties preserve provider placement labels; animations may overlap; live results stay bound to a frozen results version.

**Scale/Scope**: One shared card definition per freeform card family or template group, 1–16 common visible/materialized instances, provider-sized All result sets handled by deterministic paging/batching, and multiple Workspace-isolated stations.

## Constitution Check

*GATE: Passed before research and re-checked after design.*

| Principle | Plan evidence | Gate |
|---|---|---|
| Workspace isolation | Result versions, media outputs, station bindings, commands, public tokens, and WebSocket updates retain existing Workspace/station authorization. Editor mock data remains local. | PASS |
| PostgreSQL runtime source of truth | No new store is introduced. Saved scenes remain in PostgreSQL-backed overlay configuration; tests use `AITOB_PG_TEST_URL`. | PASS |
| Secret and external-effect safety | No credential flow is added. Live commands retain authenticated, revision-checked, auditable behavior. | PASS |
| Preserve published assets and approved operations | Existing asset URLs and presentation precedence are preserved. Provider placements stay read-only and authoritative. No match/DQ behavior changes. | PASS |
| Verification before cutover | Compatibility normalization, store invariants, animation timing, static/live parity, restart, and two-Workspace gates are mandatory. | PASS |

There are no constitution exceptions.

## Product Model and Terminology

### Shared Result Card

The **Result Card** is the sole reusable player-results component. It owns a nested definition containing background, placement, display name, prefix, player image, country flag, character art, and any custom text/image/shape children. It can bind only to approved result fields.

`Edit Card Design` opens the definition as a focused mini-canvas. `Done Editing Card` returns to the parent scene and treats the card as one atomic canvas object. Editing the shared definition updates every consumer.

### Path A — Add Result Card

- Inserts one freely movable Result Card.
- Automatically creates a lightweight `Results Cards` parent when no suitable parent is selected.
- Uses the editor's standard Animation panel and serialized `animation` field, exactly like text, image, and shape nodes.
- Can run Auto Sequence from the single authored card.
- Can materialize linked Top 8/Top 16/bounded All-page cards for individual placement and animation.

### Path B — Add Results Group

- Preserves the current template-based results workflow for social-image composition and the previous group animation behavior.
- Creates a Results Group with one shared Result Card definition/reference and template settings.
- Generates template preview/runtime cards without placing them in Layers.
- Templates may control slots, variants, pagination, headers, footers, and the prior sequence behavior.
- It does not create or edit a separate Master Card implementation; `Edit Result Card` opens the shared card editor used by Path A.

### Instance types

- **Card definition**: one reusable nested subtree containing design and bindings.
- **Freeform stage instance**: the one card inserted by Add Result Card, with transform and base outer animation.
- **Linked materialized instance**: a persisted lightweight card with its own transform, z-index, standing selector, and optional animation override; shares the definition.
- **Template instance**: an ephemeral card resolved by Results Group slots/variants for preview, PNG, or old group animation; never a layer.
- **Auto Sequence runtime instance**: an ephemeral card resolved by scheduler time from the freeform stage card; never a layer.

## Interaction Design

### Add panel

The editor exposes two adjacent, clearly described actions:

- `+ Result Card` — “Design and animate a freely positioned player card.”
- `+ Results Group` — “Use Result Cards in a reusable results image/animation template.”

They share the Result Card editor but open different inspectors. Their icons, labels, and descriptions must make the distinction visible before insertion.

### Edit the shared card

1. Select the card or the card reference inside a Results Group.
2. Choose `Edit Card Design`.
3. Enter a focused card-design canvas/breadcrumb.
4. Add/select/remove/reorder/move/resize/style/bind background, placement, player name, prefix, player image, flag, character art, and custom primitives.
5. Use only local/bundled placeholders for mock images; no external placeholder URLs.
6. Choose `Done Editing Card` to return to the scene. The card is once again atomic.

### Freeform card animation

Outside card-design mode, the Result Card may be positioned/resized anywhere, including outside canvas bounds. Selecting it exposes the same **Animation** panel used by text, images, and shapes: animation type, direction, duration, delay, easing, trigger, idle behavior, Play On, and Play Preview. There is no Card Motion panel and no second authored lifecycle. The parent Results Cards inspector owns only range/order/stagger and transport. Legacy `outerAnimation` data is normalized at read time for compatibility and is not written for new cards.

### Auto Sequence for a freeform Result Card

- Range: `Top 8`, `Top 16`, or `All`.
- Order: `8→1`, `1→8`, or custom.
- `Delay Between Starts` is a stagger, not a wait for the previous lifecycle to finish.
- Example: 2000 ms lifecycle plus 500 ms delay starts cards at 0, 500, 1000, 1500 ms; multiple cards can remain visible simultaneously.
- `0 ms` starts together; delay shorter than lifecycle overlaps; delay longer than lifecycle creates gaps.
- End behavior: follow each card Exit, keep Visible state, or clear after hold.
- Preview transport: Play, Pause/Hold, Restart, Clear, Next, Previous.
- Playback creates runtime instances only and never mutates scene/store/history.

### Materialize freeform cards on the canvas

- `Insert Top 8 Cards`, `Insert Top 16 Cards`, or a bounded All page creates linked instances under `Results Cards`.
- The original card becomes ordinal 1; only remaining instances are added.
- Layers label cards using provider placement while retaining stable ordinal identity for ties (`5th A`, `5th B`, `7th A`, `7th B` or accessible equivalent).
- Every instance can move, resize, rotate, stack, leave the canvas, and receive an animation override.
- All instances share internal design. Definition edits propagate; instance transform/animation overrides do not.
- Optional Gallery/Grid helpers perform one-time arrangement only and never constrain later movement.

### Freeform group scheduling

The automatically created `Results Cards` parent controls member playback only:

- layer/placement execution order;
- delay/stagger;
- after previous/with previous;
- keep previous visible;
- loop;
- Play, Pause/Hold, Restart, Clear.

It does not impose a layout, slot, or visual variant.

### Results Group template workflow

The existing Results Group inspector remains available for users who want a ready composition:

- Choose Top 8, Top 16, or All/page.
- Choose a layout template such as Champion Focus, Equal Grid, Ranked List, or paged layout.
- Edit the shared Result Card, template-level header/footer/background, slots, and bounded variants.
- Preview/export the composed image, or use the existing group sequence animation.
- Generated template instances stay out of Layers; selecting one may identify its resolved placement/slot but cannot create an independent card design.
- A deliberate `Convert/Insert Cards on Canvas` action may materialize the template geometry into linked freeform card instances for further manual movement.

## Data and Rendering Design

1. Extend Scene v2 so a Result Card definition is reusable by freeform and Results Group consumers. See [data-model.md](./data-model.md) and [contracts/results-scene-v2.md](./contracts/results-scene-v2.md).
2. Keep `results-group` as the template consumer. Add a freeform card instance node and an optional scheduling container.
3. Resolve content through the existing binding allowlist. Mock mode uses deterministic local rows; bound mode uses a frozen result version.
4. Produce template and Auto Sequence runtime cards as pure render values. Never dispatch store mutations during preview/playback.
5. Persist materialized instances with definition reference, transform, standing selector, z-index, visibility/lock state, and optional animation override only.
6. Use one shared Result Card renderer in editor, Results Group preview, PNG export, and OBS.
7. Static export supports both a Results Group template composition and an explicitly materialized freeform composition.
8. OBS supports both the existing Results Group sequence and the new Auto Sequence while remaining independent of active match state.

## Compatibility and Migration

- Legacy Scene v1 normalization remains unchanged.
- Existing `results-group` scenes continue to open as the template path. Their previous Player Card template is normalized into the shared Result Card definition.
- Existing layout presets, variants, preview counts, and old group animation settings remain valid inside Results Group only.
- Freeform Result Card and Auto Sequence are additive; they do not rewrite an existing Results Group unless the user explicitly converts/materializes it.
- Read-time normalization does not save automatically. The next authorized save writes the canonical Scene v2 form.
- Unknown or malformed Result Card references fail publish/take-live validation instead of being silently discarded.
- No relational database schema change is expected unless explicit saved-scene version metadata is needed; any required migration is additive and idempotent.

## Implementation Phases

### Phase A — Lock the shared card contract

- Extract/define one Result Card definition and renderer usable by freeform and Results Group paths.
- Update types, normalizer, validation, bindings, local mock placeholders, and pure resolvers.
- Add failing tests for definition sharing, ties, range/order, and runtime non-serialization.
- Gate: an existing Results Group renders identically after normalization, and a freeform card uses the same definition type.

### Phase B — Focused Result Card design mode

- Add `+ Result Card` beside the retained `+ Results Group`.
- Implement automatic scheduling parent for freeform cards.
- Replace the current constrained master-card screen with focused card design: breadcrumb, child Layers, normal primitive controls, and Done Editing.
- Gate: user can add flag, prefix, player image, character art, and custom primitives; resize/reposition them; exit; then move the atomic card.

### Phase C — Freeform card animation

- Route the atomic Result Card through the existing editor Animation UI/model.
- Keep internal child animation, atomic card animation, and group schedule scopes explicit.
- Gate: the selected card exposes the normal Animation panel, preview is deterministic, and the authored card is restored when group preview completes.

### Phase D — Auto Sequence with overlap

- Add range, order, Delay Between Starts, end behavior, and preview transport.
- Implement time-based overlapping runtime instances without layer/store/history writes.
- Gate: 2000 ms lifecycle and 500 ms stagger produces exact 0/500/1000… starts and simultaneous visible cards.

### Phase E — Linked materialized cards

- Add Insert Top 8/Top 16/bounded All-page and linked instance Layers rows.
- Add per-instance transform/z-index/animation overrides and optional one-shot Gallery/Grid arrangement.
- Gate: cards retain arbitrary positions through save/reload/export, share design edits, and play group or individual animations.

### Phase F — Results Group rebase

- Keep Add Results Group and its static templates/old animation controls.
- Make it consume the shared Result Card editor/renderer and remove duplicate master-card design state.
- Add explicit conversion/materialization to freeform cards when needed.
- Gate: old template output is preserved, card edits match freeform output, and no generated template card enters Layers.

### Phase G — Static/live parity and compatibility

- Use the shared resolver/renderer in editor, PNG export, OBS, and restart/reconnect restoration.
- Normalize existing result scenes and retain current-match behavior.
- Gate: one frozen results version yields identical placement/presentation in export and OBS with no active match.

### Phase H — Verification and release

- Focused store/normalizer/resolver/component tests.
- Full frontend suite and production build.
- Full PostgreSQL suite using disposable `AITOB_PG_TEST_URL`.
- Manual quickstart: shared design, Results Group image, old group animation, freeform Auto Sequence overlap, inserted layout, PNG, live station, restart, role denial, two-Workspace isolation.
- Diff/secret/temp-file review before commit/deployment.

## Project Structure

### Documentation

```text
specs/006-results-media/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── results-media-api.yaml
│   ├── results-overlay-protocol.md
│   └── results-scene-v2.md
├── tasks.md
└── verification.md
```

### Source Code

```text
backend/
├── api/{results_media_schemas.py,routers/results_media.py,routers/stations.py}
├── core/{results_media.py,results_media_repository.py}
└── tests/test_results_media_*.py

frontend-react/src/
├── scene/
│   ├── types.ts
│   ├── normalizeScene.ts
│   ├── SceneRenderer.tsx
│   ├── CardTemplateNode.tsx
│   ├── ResultsGroupRenderer.tsx
│   ├── resolveResultsGroup.ts
│   └── resolveSequence.ts
├── store/useEditorStore.ts
├── features/editor/
│   ├── EditorDashboard.tsx
│   ├── ResultsGroup.integration.test.tsx
│   └── components/
│       ├── SidebarAddElements.tsx
│       ├── LayersPanel.tsx
│       ├── SidebarProperties.tsx
│       ├── SidebarAnimation.tsx
│       ├── MasterCardDesignView.tsx
│       ├── PlayerCardFieldsPanel.tsx
│       ├── ResultsGroupInspector.tsx
│       └── ResultsSequenceControls.tsx
├── features/results/
├── features/obs/
└── utils/resultsExport.ts
```

**Structure Decision**: Keep the existing backend/frontend split. Refactor existing result components in place and extract shared Result Card primitives/resolvers under `src/scene`. Editor state/actions stay in Zustand; UI stays under `features/editor`; Results Group, PNG, and OBS consume the shared renderer.

## Test Matrix

| Area | Required proof |
|---|---|
| Shared definition | One design edit updates a freeform card, Results Group instances, linked instances, PNG, and OBS. |
| Persistence | Auto Sequence/template runtime cards never enter nodes, roots, clipboard, undo history, or saved JSON; explicitly inserted cards do. |
| Card editing | Internal primitives can be selected, resized, reordered, hidden, styled, bound, and animated in focused mode. |
| Animation | Result Card uses the common Animation panel; restart is deterministic; preview restores the authored card; scopes do not overwrite each other. |
| Stagger | Start time is `base + index × delay`; delay 0, overlap, and gap cases use fake-timer tests. |
| Results Group | Existing template layouts/old animation remain functional while using the shared card definition. |
| Placements | Provider order and tied labels remain unchanged; playback order never mutates provider placement. |
| Static composition | Materialized cards retain arbitrary positions, including outside canvas, through save/reload/export. |
| Compatibility | Legacy current-match scenes and first-pass Results Group scenes render and save safely. |
| Live/security | Frozen binding, no-active-match display, reconnect, role denial, Workspace isolation, token scope, and revision conflicts pass. |

## Release and Rollback

- Release only after quickstart, full regression, and visual editor acceptance pass.
- Preserve the old scene normalizer for at least one staging cycle.
- Rollback uses the previous frontend/backend image. Additive scene fields must remain readable without destructive database rollback.
- Existing checked tasks are not sufficient evidence for the corrected UX. Regenerate/add corrective tasks and verification after this plan is approved.

## Complexity Tracking

No constitution exception is needed. The three instance forms are intentional: ephemeral template instances preserve the existing Results Group, ephemeral Auto Sequence instances avoid layer pollution, and linked materialized instances allow explicit per-card layout/motion. All three share one Result Card definition, preventing duplicated design state.
