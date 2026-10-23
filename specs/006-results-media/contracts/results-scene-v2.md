# Contract: Results Scene Document v2

## Compatibility rule

The editor, PNG exporter, and OBS viewer call the same normalizer and Result Card renderer. A legacy config without `schemaVersion` normalizes from Scene v1 in memory. A first-pass Results Group keeps its template behavior while its prior Player Card template normalizes into a shared Result Card definition. Loading never writes; the next authorized save writes the canonical v2 shape.

## Minimal freeform Result Card document

```json
{
  "schemaVersion": 2,
  "canvas": {
    "width": 1920,
    "height": 1080,
    "backgroundUrl": "",
    "globalFontUrl": "",
    "globalFontFamily": "",
    "fontLibrary": [],
    "safeArea": { "top": 54, "right": 96, "bottom": 54, "left": 96 }
  },
  "dataSource": {
    "kind": "tournament-results",
    "resultVersionId": null
  },
  "rootIds": ["freeform-results"],
  "nodes": {
    "freeform-results": {
      "id": "freeform-results",
      "type": "results-cards",
      "name": "Results Cards",
      "childIds": ["result-card-1"],
      "visible": true,
      "locked": false,
      "schedule": {
        "order": "placement-desc",
        "delayBetweenStartsMs": 500,
        "keepPreviousVisible": true,
        "loop": false
      },
      "autoSequence": {
        "enabled": true,
        "stageInstanceId": "result-card-1",
        "range": "top8",
        "pageNumber": 1,
        "order": "placement-desc",
        "delayBetweenStartsMs": 500,
        "endBehavior": "card-exit"
      },
      "preview": { "dataset": "normal" }
    },
    "result-card-definition": {
      "id": "result-card-definition",
      "type": "group",
      "name": "Result Card Design",
      "definitionRole": "result-card",
      "childIds": ["card-name"],
      "width": 400,
      "height": 500,
      "visible": true,
      "locked": false
    },
    "result-card-1": {
      "id": "result-card-1",
      "type": "result-card",
      "name": "Result Card",
      "parentId": "freeform-results",
      "definitionId": "result-card-definition",
      "instanceRole": "stage",
      "standingSelector": { "kind": "ordinal", "ordinal": 1 },
      "x": 760,
      "y": 290,
      "width": 400,
      "height": 500,
      "rotation": 0,
      "zIndex": 1,
      "visible": true,
      "locked": false,
      "animation": {
        "animationType": "float-in",
        "direction": "bottom",
        "duration": 500,
        "delay": 0,
        "loop": 0,
        "tweenType": "ease-out",
        "playOn": "IN",
        "trigger": "on-load"
      }
    },
    "card-name": {
      "id": "card-name",
      "parentId": "result-card-definition",
      "type": "text",
      "name": "Player Name",
      "binding": "displayName",
      "x": 24,
      "y": 420,
      "width": 352,
      "height": 52,
      "zIndex": 3,
      "visible": true,
      "locked": false
    }
  }
}
```

## Minimal Results Group document

```json
{
  "id": "results-template",
  "type": "results-group",
  "name": "Top 8 Results",
  "x": 0,
  "y": 0,
  "width": 1920,
  "height": 1080,
  "zIndex": 1,
  "visible": true,
  "locked": false,
  "cardDefinitionId": "result-card-definition",
  "mode": "board",
  "cutoff": "top8",
  "pageNumber": 1,
  "pageSize": 16,
  "layoutPresetId": "champion-focus",
  "variantRules": [
    { "fromPlacement": 1, "toPlacement": 1, "variant": "champion" },
    { "fromPlacement": 2, "toPlacement": 4, "variant": "podium" },
    { "fromPlacement": 5, "variant": "standard" }
  ],
  "sequence": {
    "order": "placement-desc",
    "startDelayMs": 0,
    "intervalMs": 300,
    "holdMs": 0,
    "exit": "together",
    "loop": false,
    "manualCue": true
  },
  "preview": { "dataset": "normal", "count": "top8", "pageNumber": 1 }
}
```

## Persisted authoring nodes

Allowed persisted types:

- `text`
- `image`
- `rect`
- `circle`
- `group`
- `result-card`
- `results-cards`
- `results-group`

Only explicit freeform/materialized `result-card` nodes persist. Results Group template instances and Auto Sequence runtime instances are renderer values and are forbidden in `nodes`, `rootIds`, clipboard payloads, and history snapshots.

## Result Card definition and bindings

A Result Card definition is a `group` with `definitionRole: result-card`; it is not a root-rendered scene node. Its children permit only these read-only standing bindings:

- `placement`
- `displayName`
- `prefix`
- `countryCode`
- `countryFlagUrl`
- `avatarUrl`
- `characterId`
- `characterName`
- `characterImageUrl`
- `entrantName`
- `eventName`
- `gameName`

Arbitrary object paths and executable expressions are forbidden. Literal text/image nodes remain allowed. Mock image bindings resolve to bundled/local assets and never to an undeclared third-party URL.

## Freeform Result Card contract

- `definitionId` references exactly one valid Result Card definition.
- `instanceRole` is `stage` or `linked`.
- `standingSelector` selects by stable sorted ordinal or frozen result-entry ID; it does not change provider placement.
- A linked instance stores no copied design children.
- `animationOverride` may replace only outer lifecycle/timing values; otherwise it inherits the stage/base lifecycle.
- Freeform transforms are not clamped to the canvas.

## Results Cards scheduling contract

`results-cards` is layout-neutral. It may store:

- explicit child execution order;
- `delayBetweenStartsMs`;
- after/with-previous mode;
- keep-previous-visible;
- loop;
- Auto Sequence range/order/page/end behavior.

It may not store slots, variants, or an enforced grid. Gallery/Grid commands are one-shot transform edits.

## Outer animation lifecycle

The lifecycle has three transform states:

```json
{
  "start": { "x": 0, "y": 0, "scale": 0.1, "opacity": 0, "rotation": 0 },
  "visible": { "x": 100, "y": 100, "scale": 1, "opacity": 1, "rotation": 0 },
  "exit": { "x": 1920, "y": 100, "scale": 0.8, "opacity": 0, "rotation": 0 },
  "enterDurationMs": 500,
  "visibleHoldMs": 1000,
  "exitDurationMs": 500,
  "enterEasing": "ease-out",
  "exitEasing": "ease-in"
}
```

All numeric values are finite and bounded. Internal definition-child animation runs relative to each card instance's start and cannot overwrite the instance's outer transform.

## Auto Sequence timing contract

For resolved card ordinal `i` beginning at zero:

```text
startTime(i) = baseStartTime + (i × delayBetweenStartsMs)
```

The scheduler does not add the previous card's duration. Therefore:

- delay `0` starts every card simultaneously;
- delay shorter than lifecycle duration creates overlap;
- delay equal to lifecycle duration creates back-to-back playback;
- delay longer than lifecycle duration creates a gap.

Supported freeform order values are `placement-asc`, `placement-desc`, and `custom`. Custom order contains each included stable ordinal exactly once. Runtime cue IDs combine consumer node ID, frozen entry/mock ID, and resolved ordinal.

## Results Group template contract

Results Group retains its existing board/sequence model, layout presets, optional variants, and paging. It references `cardDefinitionId` instead of owning another card implementation.

A layout preset supplies ordered slots:

```json
{
  "id": "champion-focus",
  "supportedCounts": ["top8"],
  "slots": [
    { "slotId": "champion", "ordinal": 1, "x": 100, "y": 215, "width": 550, "height": 645, "variant": "champion" },
    { "slotId": "upper-2", "ordinal": 2, "x": 680, "y": 215, "width": 350, "height": 355, "variant": "podium" }
  ]
}
```

- Ties at a cutoff may create more entries than the nominal count; overflow pages/layouts must not drop them.
- Placement, slot, old group cue order, and z-index remain independent.
- Template-generated cards remain ephemeral.
- Materialize/Convert copies resolved slot geometry and standing selectors into linked `result-card` nodes referencing the same definition.

## Mock preview contract

Mock datasets are frontend constants selected only when no frozen result version is bound or Preview Data is explicitly enabled. They use stable entrant IDs and local placeholder assets and must not be submitted to results APIs.

## Normalization invariants

- Legacy primitive IDs, `sourceId` values, z-index, and existing animation semantics are preserved.
- A first-pass Results Group `templateId` normalizes to `cardDefinitionId` without changing rendered output.
- Existing layout presets, variants, and group sequence settings stay attached to Results Group.
- Existing 1920×1080 canvas is the default when metadata is absent.
- Legacy scenes normalize to `dataSource.kind = current-match` unless explicitly saved as tournament results.
- Unknown node types make publish/take-live invalid; they are not silently discarded.

## Validation invariants

- Node IDs are unique and all parent/definition references resolve without cycles.
- Every freeform Result Card and Results Group references exactly one Result Card definition.
- A Result Card definition is not present in root rendering order.
- A Results Cards parent has only freeform Result Card children and imposes no layout geometry.
- Template and Auto Sequence runtime instances are absent from persisted state.
- Timing and transform values are finite and bounded; delay is non-negative.
- Custom order contains every included stable ordinal exactly once.
- Results scenes have `dataSource.kind = tournament-results` before publish/take-live.
- All external asset URLs pass existing asset policy/preflight or resolve to a declared local placeholder.
