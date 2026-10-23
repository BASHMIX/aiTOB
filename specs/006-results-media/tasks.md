# Tasks: Tournament Results Media — Corrective Shared Result Card

**Input**: Design documents from `specs/006-results-media/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Corrective scope**: This checklist supersedes the earlier “84/84 complete” editor checklist for the clarified Result Card experience. Existing provider-authoritative standings, immutable versions, PostgreSQL repositories, role enforcement, PNG receipts, and results-session APIs are retained and covered by regression gates rather than reimplemented.

**Tests**: Tests are required. Test tasks precede their implementation tasks and must demonstrate the missing or incorrect behavior before the implementation task is marked complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can be assigned in parallel because it changes different files and has no incomplete dependency on the paired task.
- **[US1]–[US4]**: Maps to the four user stories in `spec.md`.
- Every task names the exact implementation or evidence path.

---

## Phase 1: Setup and Corrective Baseline

**Purpose**: Make the clarified scope explicit and prepare deterministic local fixtures without changing production behavior.

- [X] T001 Record the clarified corrective scope, superseded editor assumptions, and empty verification gates in `specs/006-results-media/verification.md`
- [ ] T002 [P] Add bundled/local player, flag, and character fallback assets with attribution/usage notes in `frontend-react/public/assets/results/README.md`
- [ ] T003 [P] Add deterministic freeform, linked-card, tie, RTL, long-name, and missing-media scene fixtures in `frontend-react/src/scene/resultsSceneTestFixtures.ts`
- [X] T004 Inventory the existing Results Group save shape and document its normalization mapping to the shared Result Card contract in `specs/006-results-media/verification.md`

**Checkpoint**: The corrective work has reproducible fixtures and no test depends on a third-party placeholder URL.

---

## Phase 2: Foundational Shared Scene Contract

**Purpose**: Introduce one canonical Result Card definition, freeform instance, scheduling parent, and pure runtime resolution before changing any user-facing workflow.

**⚠️ CRITICAL**: No user-story UI work begins until the canonical scene model, normalization, and store invariants pass.

- [X] T005 [P] Add failing type/contract tests for `result-card`, `results-cards`, shared definitions, lifecycle states, and instance references in `frontend-react/src/scene/types.test.ts`
- [X] T006 [P] Add failing normalization tests for legacy Scene v1 and first-pass `results-group.templateId` compatibility in `frontend-react/src/scene/normalizeScene.test.ts`
- [ ] T007 [P] Add failing store tests proving ephemeral template/Auto Sequence instances never enter nodes, roots, clipboard, or undo history while linked cards do in `frontend-react/src/store/useEditorStore.results.test.ts`
- [X] T008 [P] Add failing shared-renderer tests for bound fields, literal children, local fallbacks, and definition reuse in `frontend-react/src/scene/ResultCardRenderer.test.tsx`
- [X] T009 Define Result Card definition, freeform instance, scheduling parent, lifecycle, scheduler, and compatibility types in `frontend-react/src/scene/types.ts`
- [X] T010 Implement non-writing normalization from legacy Player Card templates to shared definitions and canonical result nodes in `frontend-react/src/scene/normalizeScene.ts`
- [ ] T011 Implement shared-definition ownership, linked-instance actions, reference-safe deletion, clipboard exclusion, and history invariants in `frontend-react/src/store/useEditorStore.ts`
- [X] T012 Implement the shared bound/literal child renderer with local deterministic fallbacks in `frontend-react/src/scene/ResultCardRenderer.tsx`
- [X] T013 Replace external/mock placeholder sources with bundled result assets and stable datasets in `frontend-react/src/features/results/mockData.ts`
- [X] T014 Route SceneRenderer node dispatch through the shared Result Card renderer without altering current-match primitives in `frontend-react/src/scene/SceneRenderer.tsx`
- [ ] T015 Add a save/reload integration test proving canonical Scene v2 persistence and zero runtime-instance serialization in `frontend-react/src/features/editor/ResultsGroup.integration.test.tsx`
- [X] T016 Persist only shared definitions and explicit linked instances while preserving read-only normalization in `frontend-react/src/features/editor/hooks/useEditorData.ts`

**Checkpoint**: One shared card definition renders everywhere; existing scenes normalize in memory; persisted state contains only author-authored nodes.

---

## Phase 3: User Story 1 — Publish a Final Results Graphic (Priority: P1)

**Goal**: Preserve the Results Group template workflow for rapid social images while rebasing every generated card on the shared Result Card definition.

**Independent Test**: Open an existing Results Group, verify visual compatibility, edit its shared Result Card once, preview Top 8 with ties, export PNG from Champion Focus, then materialize the arrangement and export the equivalent freeform composition.

### Tests for User Story 1

- [X] T017 [P] [US1] Add failing compatibility tests proving existing Board layouts and variants render through one shared Result Card definition in `frontend-react/src/scene/ResultsGroupRenderer.test.tsx`
- [ ] T018 [P] [US1] Add failing resolver tests for tied cutoffs, paged All results, shared definition references, and template-to-linked geometry conversion in `frontend-react/src/scene/resolveResultsGroup.test.ts`
- [X] T019 [P] [US1] Add failing inspector tests for Add Results Group, template controls, Edit Result Card, and explicit materialization in `frontend-react/src/features/editor/components/ResultsGroupInspector.test.tsx`
- [ ] T020 [P] [US1] Add failing PNG parity tests for Results Group and materialized freeform compositions in `frontend-react/src/utils/resultsExport.test.ts`
- [ ] T021 [P] [US1] Add failing studio tests for frozen-version binding, provider-owned placement locks, preflight, and both export paths in `frontend-react/src/features/results/ResultsStudioPage.test.tsx`

### Implementation for User Story 1

- [X] T022 [US1] Refactor Results Group resolution to reference the shared Result Card definition while preserving layouts, variants, ties, paging, and old cue semantics in `frontend-react/src/scene/resolveResultsGroup.ts`
- [X] T023 [US1] Render Results Group template instances through `ResultCardRenderer` and keep them ephemeral in `frontend-react/src/scene/ResultsGroupRenderer.tsx`
- [X] T024 [US1] Keep template, Board, old Sequence, preview-data, and Edit Result Card controls while adding explicit materialize/convert behavior in `frontend-react/src/features/editor/components/ResultsGroupInspector.tsx`
- [ ] T025 [US1] Implement template-slot to linked-instance conversion without copying definition children in `frontend-react/src/store/useEditorStore.ts`
- [ ] T026 [US1] Export Results Group Board or explicitly materialized freeform final state through the same DOM renderer in `frontend-react/src/utils/resultsExport.ts`
- [ ] T027 [US1] Present both static composition paths and retain immutable result-version/preflight behavior in `frontend-react/src/features/results/ResultsStudioPage.tsx`

**Checkpoint**: Existing Results Group image output is preserved, uses the shared card, and can deliberately convert to editable linked cards.

---

## Phase 4: User Story 2 — Design One Shared Result Card (Priority: P2)

**Goal**: Provide an understandable freeform Result Card workflow and a focused nested card-design canvas without forcing Results Group template settings.

**Independent Test**: Add Result Card to a blank scene, edit/resize/reorder all player fields and custom primitives, leave design mode, then freely move/resize/rotate the atomic card outside the canvas and confirm a Results Group uses the same design.

### Tests for User Story 2

- [X] T028 [P] [US2] Add failing Add-panel tests that distinguish Add Result Card from Add Results Group and verify automatic scheduling-parent creation in `frontend-react/src/features/editor/components/SidebarAddElements.test.tsx`
- [ ] T029 [P] [US2] Replace constrained master-view tests with failing focused-design tests for breadcrumbs, enter/exit, child selection, sizing, ordering, and deletion in `frontend-react/src/features/editor/components/ResultCardDesignView.test.tsx`
- [X] T030 [P] [US2] Add failing field-panel tests for placement, display name, prefix, avatar, flag, character, background, literal text/image, and local fallback selection in `frontend-react/src/features/editor/components/PlayerCardFieldsPanel.test.tsx`
- [X] T031 [P] [US2] Add failing Layers tests for atomic scene cards, focused child layers, selected-row highlight, definition badges, and linked instance rows in `frontend-react/src/features/editor/components/LayersPanel.results.test.tsx`
- [ ] T032 [P] [US2] Add failing canvas tests for free move/resize/rotate/z-index/outside-canvas behavior without template snapping in `frontend-react/src/features/editor/components/DraggableElement.results.test.tsx`
- [ ] T033 [US2] Add an end-to-end editor integration test for Add Result Card → Edit Card Design → Done Editing → shared Results Group render → save/reload in `frontend-react/src/features/editor/ResultCardAuthoring.integration.test.tsx`

### Implementation for User Story 2

- [X] T034 [US2] Add the separate Result Card action and automatic Results Cards scheduling parent while retaining Add Results Group in `frontend-react/src/features/editor/components/SidebarAddElements.tsx`
- [X] T035 [US2] Implement focused Result Card design mode, breadcrumb, child canvas, and Done Editing transition in `frontend-react/src/features/editor/components/ResultCardDesignView.tsx`
- [X] T036 [US2] Route editor mode/selection between scene-level atomic cards and definition children in `frontend-react/src/features/editor/EditorDashboard.tsx`
- [X] T037 [US2] Expose bound player fields, literal primitives, asset selection, local fallbacks, and add/remove controls in `frontend-react/src/features/editor/components/PlayerCardFieldsPanel.tsx`
- [X] T038 [US2] Render atomic cards, focused definition children, shared-definition references, selection highlight, visibility, lock, and linked rows in `frontend-react/src/features/editor/components/LayersPanel.tsx`
- [X] T039 [US2] Allow freeform Result Card transform manipulation outside canvas without Results Group slot clamping in `frontend-react/src/features/editor/components/DraggableElement.tsx`
- [X] T040 [US2] Route Result Card, Results Cards scheduler, Results Group, and definition-child selection to distinct property panels in `frontend-react/src/features/editor/components/Sidebar.tsx`
- [X] T041 [US2] Add atomic Result Card transform, data preview, and Edit Card Design controls while reusing primitive controls inside design mode in `frontend-react/src/features/editor/components/SidebarProperties.tsx`
- [X] T042 [US2] Remove obsolete `Master Card` user-facing terminology while retaining compatibility exports only where required in `frontend-react/src/features/editor/components/MasterCardDesignView.tsx`

**Checkpoint**: The user can design a real card, then place it like any other canvas object; both Add actions remain clear and share the same definition.

---

## Phase 5: User Story 3 — Animate Freeform Cards and Take Results Live (Priority: P3)

**Goal**: Reuse the editor's standard Animation system for Result Cards, add overlapping Auto Sequence, explicitly materialized linked cards, group scheduling, preview transport, and shared OBS playback without breaking the established Results Group sequence.

**Independent Test**: Apply a standard editor animation to one Result Card; play Top 8 at 500 ms delay and confirm 0/500/1000… starts with overlapping cards, preview completion restores the authored card, then materialize Top 8 and take the frozen result live with no active match.

### Tests for User Story 3

- [X] T043 [P] [US3] Add failing lifecycle interpolation tests for Start, Visible, Exit, easing, hold, rotation, restart, and bounds in `frontend-react/src/scene/resolveResultCardAnimation.test.ts`
- [ ] T044 [P] [US3] Add failing fake-timer Auto Sequence tests for delay 0, overlap, back-to-back, gap, order, range, end behavior, and looping in `frontend-react/src/scene/resolveAutoSequence.test.ts`
- [X] T045 [P] [US3] Add animation-panel and preview-restoration regressions proving Result Card uses the common editor Animation panel and has no Card Motion panel in `frontend-react/src/features/editor/components/ResultCardAnimation.integration.test.tsx`
- [ ] T046 [P] [US3] Add failing transport tests for Play, Pause/Hold, Restart, Clear, Next, Previous, and non-mutating preview in `frontend-react/src/features/editor/components/ResultsSequenceControls.test.tsx`
- [ ] T047 [P] [US3] Add failing linked-card tests for Top 8/Top 16/bounded All materialization, ties, independent transforms, shared design, and one-shot Gallery/Grid in `frontend-react/src/features/editor/LinkedResultCards.integration.test.tsx`
- [ ] T048 [P] [US3] Add failing OBS tests for freeform Auto Sequence, established Results Group cues, no-active-match rendering, hold, restart, clear, and reconnect in `frontend-react/src/features/obs/hooks/useOBSViewerData.results.test.tsx`
- [ ] T049 [P] [US3] Extend projection API tests for both corrected scene consumers, frozen-version stability, stale revision rejection, and Workspace isolation in `backend/tests/test_results_overlay_projection.py`

### Implementation for User Story 3

- [X] T050 [P] [US3] Implement pure Start/Visible/Exit lifecycle interpolation and animation-scope precedence in `frontend-react/src/scene/resolveResultCardAnimation.ts`
- [X] T051 [P] [US3] Implement pure time-based Auto Sequence runtime resolution with `startTime = base + index × delay` in `frontend-react/src/scene/resolveAutoSequence.ts`
- [X] T052 [US3] Route Result Card through the existing `SidebarAnimation` controls used by images, text, and shapes; retain old outer-animation data only as a read compatibility fallback in `frontend-react/src/features/editor/components/SidebarAnimation.tsx`
- [ ] T053 [US3] Implement Auto Sequence range/order/stagger/end behavior and Play/Pause/Restart/Clear/Next/Previous controls in `frontend-react/src/features/editor/components/ResultsSequenceControls.tsx`
- [X] T054 [US3] Keep Top 8, Top 16, bounded All, tied-instance labels, and explicit insertion actions on the parent scheduler in `frontend-react/src/features/editor/components/ResultsCardsInspector.tsx`; remove the separate Result Card inspector
- [X] T055 [US3] Implement layout-neutral member order, stagger, with/after previous, keep-visible, loop, and transport controls in `frontend-react/src/features/editor/components/ResultsCardsInspector.tsx`
- [X] T056 [US3] Render simultaneous Auto Sequence runtime instances without store/history writes and retain linked instance geometry in `frontend-react/src/features/editor/EditorDashboard.tsx`
- [ ] T057 [US3] Extend stable cue resolution to distinguish Results Group template cues from Auto Sequence runtime cues without using z-index in `frontend-react/src/scene/resolveSequence.ts`
- [ ] T058 [US3] Render both Results Group and freeform Result Card consumers from frozen results projections in `frontend-react/src/features/obs/components/OBSElement.tsx`
- [ ] T059 [US3] Reconstruct corrected result playback after HTTP/WebSocket reconnect while preserving session revision semantics in `frontend-react/src/features/obs/hooks/useOBSViewerData.ts`
- [X] T060 [US3] Keep projection validation, frozen-version binding, revision conflicts, and Workspace/station authorization compatible with corrected Scene v2 in `backend/api/routers/stations.py`

**Checkpoint**: Freeform animations overlap correctly, linked cards remain editable, old group sequences remain available, and OBS stays deterministic and isolated.

---

## Phase 6: User Story 4 — Correct Player Presentation Safely (Priority: P4)

**Goal**: Ensure every shared Result Card consumer resolves the same editable player presentation fields without changing provider truth or previously frozen media.

**Independent Test**: Apply an event-only featured-character override, verify it in freeform and Results Group cards, promote it explicitly to Player Archive, freeze a new version, and confirm the old version remains unchanged.

### Tests for User Story 4

- [X] T061 [P] [US4] Add failing shared-card binding tests for prefix, country flag, avatar, featured character, source precedence, and deterministic fallbacks in `frontend-react/src/scene/ResultCardRenderer.test.tsx`
- [ ] T062 [P] [US4] Extend presentation editor tests for event-only override, explicit profile promotion, game-scoped character selection, and immutable prior versions in `frontend-react/src/features/players/__tests__/EntrantPresentationEditor.results.test.tsx`
- [ ] T063 [P] [US4] Extend backend regression tests for presentation snapshots, event overrides, promotion audit, and frozen-version immutability in `backend/tests/test_results_media_presentation.py`

### Implementation for User Story 4

- [X] T064 [US4] Resolve every Result Card binding through the frozen presentation snapshot and label featured character accurately in `frontend-react/src/scene/ResultCardRenderer.tsx`
- [ ] T065 [US4] Keep event-only edits and explicit Player Archive promotion distinct while refreshing new media versions in `frontend-react/src/features/players/EntrantPresentationEditor.tsx`
- [ ] T066 [US4] Preserve presentation precedence and game-scoped profile selection when producing result entries in `backend/core/results_media.py`

**Checkpoint**: Presentation changes appear consistently in both authoring paths and never mutate provider placements or old frozen outputs.

---

## Phase 7: Polish, Compatibility, and Release Gates

**Purpose**: Prove the corrected editor is production-safe across legacy scenes, static media, live broadcast, roles, and Workspace isolation.

- [X] T067 [P] Add current-match and legacy Scene v1 visual/serialization regressions for the shared renderer changes in `frontend-react/src/scene/normalizeScene.test.ts`
- [ ] T068 [P] Add visual boundary cases for RTL, long names, missing media, ties, outside-canvas motion, and Top 16 overlap in `frontend-react/src/features/results/ResultsVisualRegression.test.tsx`
- [ ] T069 [P] Verify unauthorized Result Card, Results Group, export, and live controls stay hidden and server-rejected in `frontend-react/src/features/hub/components/RolesPermissions.test.tsx`
- [X] T070 Update editor and operator documentation for both Add actions, animation scopes, Delay Between Starts, linked cards, and Results Group compatibility in `README.md`
- [X] T071 Execute focused frontend scene/editor/results/OBS tests and record commands/results in `specs/006-results-media/verification.md`
- [X] T072 Run the full frontend suite and production build with `npm test` and `npm run build` and record evidence in `specs/006-results-media/verification.md`
- [ ] T073 Run focused result-media and overlay backend tests against disposable PostgreSQL via `AITOB_PG_TEST_URL` and record evidence in `specs/006-results-media/verification.md`
- [ ] T074 Run the full backend PostgreSQL suite with `python -m pytest backend/tests -q` and record evidence in `specs/006-results-media/verification.md`
- [ ] T075 Execute every shared-card, freeform animation, Results Group compatibility, PNG, live/restart, presentation, and two-Workspace scenario in `specs/006-results-media/quickstart.md`
- [ ] T076 Review final diffs for secrets, external placeholder URLs, unrelated files, copied card definitions, runtime-instance serialization, and stale Master Card terminology and record the release review in `specs/006-results-media/verification.md`

**Release checkpoint**: Do not mark Spec 006 complete or deploy this correction until T067–T076 pass with evidence.

---

## Dependencies and Execution Order

### Phase dependencies

- **Phase 1 — Setup**: starts immediately.
- **Phase 2 — Foundational**: depends on Phase 1 and blocks every user-story implementation.
- **Phase 3 — US1**: depends on the shared scene contract; preserves the highest-priority publishable image workflow.
- **Phase 4 — US2**: depends on the shared scene contract and may run in parallel with US1 after T009–T016.
- **Phase 5 — US3**: depends on US2 atomic card authoring for the complete UI; pure lifecycle and Auto Sequence resolvers may begin after Phase 2.
- **Phase 6 — US4**: depends on the shared renderer and can run in parallel with late US2/US3 work.
- **Phase 7 — Release gates**: depends on every story included in the candidate.

### User-story completion order

```text
Setup
  └─ Shared Scene Contract
       ├─ US1 Results Group / Static Export Compatibility
       ├─ US2 Shared Result Card Authoring
       │    └─ US3 Freeform Animation / Auto Sequence / Live
       └─ US4 Presentation Consistency
                    └─ Cross-cutting Release Gates
```

### Within each story

- Add the failing test first and confirm it fails for the intended reason.
- Implement pure types/resolvers before store actions.
- Implement store actions before inspector/canvas wiring.
- Integrate the editor before PNG/OBS consumers.
- Preserve current-match and first-pass Results Group compatibility at every checkpoint.

---

## Parallel Execution Examples

### Shared foundation

```text
Agent A: T005, T009 — scene types and lifecycle contract
Agent B: T006, T010 — compatibility normalizer
Agent C: T008, T012, T013 — shared renderer and local fallbacks
```

Merge T009–T014 before T015–T016.

### User Story 1

```text
Agent A: T017, T022, T023 — Results Group resolver/renderer compatibility
Agent B: T019, T024, T025 — inspector and materialization
Agent C: T020, T021, T026, T027 — export and Results Studio parity
```

### User Story 2

```text
Agent A: T028, T034, T040 — insertion and sidebar routing
Agent B: T029, T035, T036 — focused card-design mode
Agent C: T030, T031, T037, T038 — fields and Layers UI
```

### User Story 3

```text
Agent A: T043, T050, T052 — lifecycle animation
Agent B: T044, T046, T051, T053 — Auto Sequence and transport
Agent C: T047, T054, T055 — linked cards and scheduling
```

Merge the frontend resolver/UI work before T048 and T058–T060 OBS integration.

### User Story 4

```text
Agent A: T061, T064 — shared-card bindings
Agent B: T062, T065 — organizer presentation workflow
Agent C: T063, T066 — backend snapshot regressions
```

---

## Implementation Strategy

### Corrective MVP

The smallest useful corrective demo is not US1 alone because the existing template output already works. Complete:

1. Phase 1 — corrective baseline.
2. Phase 2 — shared scene contract.
3. Phase 4 — US2 shared Result Card authoring.
4. The US1 compatibility tests T017–T021 to prove Results Group was not broken.
5. Stop and obtain visual/editor acceptance before starting motion work.

### Incremental delivery

1. Shared contract and compatibility normalizer.
2. Result Card design/atomic placement accepted in the editor.
3. Results Group rebased on the shared card and PNG parity confirmed.
4. Common editor Animation panel and deterministic preview restoration accepted on one card.
5. Auto Sequence overlap and linked cards accepted.
6. OBS/restart/presentation/isolation gates accepted.

### Multi-agent boundaries

- Parallel work is allowed only on the file-separated groups listed above.
- `frontend-react/src/scene/types.ts`, `frontend-react/src/store/useEditorStore.ts`, and `frontend-react/src/features/editor/EditorDashboard.tsx` are merge gates; assign one owner at a time.
- Each agent must preserve unrelated user changes and run focused tests for its touched files before handoff.

---

## Notes

- `[P]` means file-level parallelism is safe at that point, not that dependencies can be ignored.
- Result Card internal design, outer card animation, linked-instance override, Results Cards scheduling, and Results Group template animation are separate scopes.
- Provider placement remains read-only; custom playback order never changes final standings.
- Auto Sequence and Results Group preview cards are ephemeral. Only explicit linked cards are authoring nodes.
- Do not reintroduce `example.com` or any other undeclared external placeholder source.
- Commit only after a logical test/implementation slice passes; do not bundle unrelated dirty-worktree changes.
