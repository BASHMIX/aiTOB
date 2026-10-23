# Quickstart: Tournament Results Media

This guide validates the feature after implementation. It does not authorize live provider mutations; standings reads against external services require explicitly disposable resources and `AITOB_ALLOW_LIVE_TESTS=true`.

## 1. Prepare disposable PostgreSQL

```powershell
$env:AITOB_PG_TEST_URL = 'postgresql://aitob:password@127.0.0.1:5433/aitob_results_media_test'
python -m pytest backend/tests/test_startgg_final_standings.py -q
python -m pytest backend/tests/test_challonge_final_standings.py -q
python -m pytest backend/tests/test_results_media_service.py -q
python -m pytest backend/tests/test_results_media_api.py -q
python -m pytest backend/tests/test_results_media_workspace_scope.py -q
python -m pytest backend/tests/test_results_overlay_session.py -q
```

Expected:

- Tests create/drop isolated databases through the existing PostgreSQL fixture.
- Active or awaiting-review provider fixtures remain Provisional.
- Completed provider fixtures create immutable Final versions.
- Ties at 8 and 16 are retained.
- Duplicate/null/partial standings fail safely.
- Concurrent identical refreshes return one observation version.
- Workspace B cannot read or control Workspace A results.

## 2. Validate the frontend scene model

```powershell
Set-Location frontend-react
npm test -- src/scene
npm test -- src/features/results
npm test -- src/features/editor
npm test -- src/features/obs
npm run build
Set-Location ..
```

Expected:

- Legacy overlays normalize without changing visual IDs, source bindings, or animation settings.
- Existing Results Groups preserve template output while using the shared Result Card definition.
- Results Group previews and freeform Auto Sequence generate no persisted runtime nodes.
- Deliberately inserted linked cards do persist without copying design children.
- One Result Card design change affects freeform, linked, Results Group, PNG, and OBS renderers.
- Placement, slot, freeform transform, stacking, and playback order remain independent.
- Delay Between Starts is tested for simultaneous, overlapping, back-to-back, and gap cases.
- Top 8 ties overflow safely.
- Existing current-match overlays keep their previous behavior.

## 3. Start the local stack

Set `DATABASE_URL` to the local development PostgreSQL database, then:

```powershell
python run.py
```

Open:

- Hub: `http://127.0.0.1:5173/admin/hub`
- Editor: use the existing station Editor action
- OBS viewer: use the revocable URL issued by the station settings

Stop with:

```powershell
python stop.py
```

## 4. Mock-only design acceptance

No provider data is needed for this section.

### 4.1 Shared Result Card editor

1. Create a new overlay preset and confirm Add exposes both **Result Card** and **Results Group** with distinct descriptions.
2. Choose **Add Result Card** and confirm Layers contains an automatically created `Results Cards` parent and one selected `Result Card`.
3. Choose **Edit Card Design** and add/position/resize placement, player name, prefix, player image, country flag, character art, background, and one custom primitive.
4. Confirm all mock images resolve locally and no request is made to an undeclared external placeholder host.
5. Choose **Done Editing Card** and confirm the card is one atomic element that can be moved, resized, rotated, stacked, and placed outside the canvas.

### 4.2 Freeform animation and Auto Sequence

1. Select the Result Card and configure it through the normal **Animation** panel used by text, images, and shapes.
2. Preview the card, then confirm it returns to its authored canvas position and remains visible when preview ends.
3. Select Top 8, 8→1, and Delay Between Starts = 500 ms.
4. Play Auto Sequence and confirm starts at 0/500/1000… ms and that several cards overlap on screen.
5. Try delay 0, 2000, and 2500 ms to confirm simultaneous, back-to-back, and gap behavior.
6. Confirm Play, Pause/Hold, Restart, Clear, Next, and Previous operate without adding Layers/history/store nodes.

### 4.3 Materialized linked cards

1. Choose **Insert Top 8 Cards on Canvas**.
2. Confirm eight linked cards appear in Layers and tied placements remain separately identifiable.
3. Move cards freely, including outside canvas; change z-index and override one card's animation.
4. Reopen Edit Card Design, change a font/color/field position, and confirm every linked card updates while their transforms remain unchanged.
5. Apply an optional Gallery/Grid arrangement once, then move a card and confirm it is not snapped back.
6. Save/reload and confirm linked cards persist, while no copied design child tree exists per card.

### 4.4 Results Group template compatibility

1. Choose **Add Results Group** and select Champion Focus + Top 8.
2. Confirm the group uses the same Result Card editor and that changes from 4.3 appear in its generated cards.
3. Confirm placement 1 remains large, 2–4 medium, and remaining placements compact according to the template.
4. Switch among Normal, Long Names, Missing Media, RTL, and Tied Placements datasets.
5. Preview the established Results Group animation modes and confirm no generated preview card appears in Layers.
6. Materialize/convert the template arrangement and confirm linked freeform cards are created with the resolved geometry and shared definition.

## 5. Static export acceptance

1. Use a locally seeded Final result version or an approved disposable provider event.
2. Bind the result version and confirm provider placements are read-only.
3. Export once from a Results Group template and once from an explicitly materialized freeform composition.
4. Select landscape `1920×1080`, then square `1080×1080`, then portrait `1080×1350`.
5. Confirm preflight reports missing media and shows deterministic fallbacks.
6. Compare preview and PNG for card count, order, crop, typography, flags, characters, tournament metadata, and sponsor/footer content.
7. Verify the export receipt and redacted audit event exist in the owning Workspace.

## 6. Live overlay acceptance

1. Create a frozen live media output from the same Final result version.
2. Bind it to a test station and issue a fresh station overlay token.
3. Open the OBS URL with no active match.
4. Run the established Results Group sequence, then the freeform Auto Sequence.
5. Use Play, Next twice, Hold, Previous, Restart, and Clear; confirm overlapping freeform cards match editor timing.
6. Confirm every command advances at most one expected revision and placements never change.
7. Restart API and refresh OBS while held; confirm the same cards and cue restore without automatic advancement.
8. Activate a normal match overlay after Clear and confirm the existing match telemetry pipeline still works.

## 7. Presentation correction acceptance

1. Choose one standing entry with a linked Player Profile.
2. Set an event-only featured-character override.
3. Refresh presentation into a new result version and confirm the old version remains unchanged.
4. Promote the override to Player Archive explicitly.
5. Create another result version and confirm it inherits the profile value.
6. Confirm the audit trail distinguishes event override, profile promotion, refresh, and export.

## 8. Two-Workspace isolation gate

Use two accounts, Workspaces, stations, and result versions.

- Attempt cross-Workspace version reads by ID: must return not found/denied without disclosing ownership.
- Attempt to bind Workspace A output to Workspace B station: must fail.
- Use Workspace A overlay token against Workspace B station: must fail.
- Run Next concurrently in both Workspaces: each session advances independently.
- Verify WebSocket messages remain scoped to their station and Workspace.

## 9. Full regression gate

```powershell
$env:AITOB_PG_TEST_URL = 'postgresql://aitob:password@127.0.0.1:5433/aitob_results_media_test'
python -m pytest backend/tests -q
Set-Location frontend-react
npm test
npm run build
Set-Location ..
```

The feature is not ready for staging until the full PostgreSQL suite, frontend suite/build, manual mock/export checks, live station restart check, and two-Workspace isolation gate all pass.
