"""Shared fixtures for the Results Media API boundary tests."""

from __future__ import annotations


def valid_results_scene(
    version_id: str,
    *,
    width: int = 1920,
    height: int = 1080,
    mode: str = "board",
    start_delay_ms: int = 300,
    interval_ms: int = 800,
) -> dict:
    """Return the smallest valid persisted Scene v2 results document."""
    group_id = "results-group"
    template_id = "player-card-template"
    return {
        "schemaVersion": 2,
        "canvas": {"width": width, "height": height},
        "dataSource": {
            "kind": "tournament-results",
            "resultVersionId": version_id,
        },
        "rootIds": [group_id],
        "nodes": {
            group_id: {
                "id": group_id,
                "type": "results-group",
                "visible": True,
                "x": 0,
                "y": 0,
                "width": width,
                "height": height,
                "templateId": template_id,
                "mode": mode,
                "cutoff": "top8",
                "pageNumber": 1,
                "pageSize": 8,
                "layoutPresetId": "test-grid",
                "variantRules": [],
                "sequence": {
                    "order": "placement-asc",
                    "startDelayMs": start_delay_ms,
                    "intervalMs": interval_ms,
                    "holdMs": 0,
                    "exit": "none",
                    "loop": False,
                    "manualCue": False,
                },
            },
            template_id: {
                "id": template_id,
                "type": "group",
                "visible": True,
                "templateRole": "player-card",
                "parentId": group_id,
                "childIds": [],
                "x": 0,
                "y": 0,
                "width": 400,
                "height": 600,
            },
        },
    }


def valid_freeform_results_scene(version_id: str) -> dict:
    """Return the smallest valid freeform Result Card Auto Sequence scene."""
    lifecycle = {
        "start": {"x": -200, "y": 250, "scale": 0.1, "opacity": 0, "rotation": 0},
        "visible": {"x": 750, "y": 250, "scale": 1, "opacity": 1, "rotation": 0},
        "exit": {"x": 1700, "y": 250, "scale": 0.8, "opacity": 0, "rotation": 0},
        "enterDurationMs": 500,
        "visibleHoldMs": 1000,
        "exitDurationMs": 500,
        "enterEasing": "ease-out",
        "exitEasing": "ease-in",
    }
    return {
        "schemaVersion": 2,
        "canvas": {"width": 1920, "height": 1080},
        "dataSource": {"kind": "tournament-results", "resultVersionId": version_id},
        "rootIds": ["cards"],
        "nodes": {
            "cards": {
                "id": "cards", "type": "results-cards", "visible": True,
                "x": 0, "y": 0, "width": 1920, "height": 1080,
                "childIds": ["stage"],
                "schedule": {
                    "order": "placement-desc", "delayBetweenStartsMs": 275,
                    "trigger": "with-previous", "keepPreviousVisible": True, "loop": False,
                },
                "autoSequence": {
                    "enabled": True, "stageInstanceId": "stage", "range": "top16",
                    "pageNumber": 1, "pageSize": 16, "order": "placement-desc",
                    "delayBetweenStartsMs": 275, "endBehavior": "card-exit",
                },
            },
            "stage": {
                "id": "stage", "type": "result-card", "parentId": "cards", "visible": True,
                "x": 750, "y": 250, "width": 420, "height": 560,
                "definitionId": "definition", "instanceRole": "stage", "standingOrdinal": 1,
                "outerAnimation": lifecycle,
            },
            "definition": {
                "id": "definition", "type": "group", "parentId": "stage", "visible": True,
                "x": 0, "y": 0, "width": 420, "height": 560,
                "definitionRole": "result-card", "templateRole": "player-card", "childIds": [],
            },
        },
    }
