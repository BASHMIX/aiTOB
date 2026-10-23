"""Domain orchestration for Tournament Results Media.

Manages provider standings fetch outside transactions, presentation resolution,
hash deduplication, advisory locking, and immutable version creation.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
import hashlib
import json
import math
import time
from typing import Any, Mapping

from backend.core.contracts import (
    ProviderEventResults,
    ProviderSnapshotRequestV2,
    SnapshotScope,
)
from backend.core import database
from backend.core.player_presentation import batch_resolve_standings_presentation
from backend.core.providers.registry import provider_registry
from backend.core import results_media_repository as repo


_refresh_locks: dict[tuple[str, str, str], asyncio.Lock] = defaultdict(asyncio.Lock)


def validate_provider_event_results(
    results: ProviderEventResults,
    *,
    expected_event_id: str,
    provider_type: str,
) -> list[str]:
    """Return blocking structural errors without inventing provider results."""
    errors: list[str] = []
    if not results.event_id:
        errors.append("provider event id is missing")
    elif provider_type == "startgg" and str(results.event_id) != str(expected_event_id):
        errors.append("provider returned standings for a different event")

    entrant_ids = [str(item.entrant_id or "") for item in results.standings]
    ordinals = [int(item.ordinal) for item in results.standings]
    placements = [int(item.placement) for item in results.standings]
    if any(not entrant_id for entrant_id in entrant_ids):
        errors.append("one or more standings are missing entrant identity")
    if len(entrant_ids) != len(set(entrant_ids)):
        errors.append("provider standings contain duplicate entrant identity")
    if len(ordinals) != len(set(ordinals)) or ordinals != list(range(1, len(ordinals) + 1)):
        errors.append("provider standings ordinals are not unique and contiguous")
    if any(placement <= 0 for placement in placements):
        errors.append("provider standings contain an invalid placement")
    if any(current < previous for previous, current in zip(placements, placements[1:])):
        errors.append("provider standings placements are not monotonic")

    if results.is_completed:
        if not results.standings:
            errors.append("completed provider event returned no standings")
        if results.page.has_more or not results.page.is_complete:
            errors.append("provider standings pagination is incomplete")
        if results.page.total_entries and results.page.total_entries != len(results.standings):
            errors.append("provider standings count does not match pagination evidence")
    return list(dict.fromkeys(errors))


def classify_readiness(
    results: ProviderEventResults,
    observed_seconds_ago: float,
    freshness_seconds: int = 3600,
) -> str:
    """Classify results readiness into final, provisional, or stale."""
    if not results.is_completed:
        return "provisional"
    if observed_seconds_ago > freshness_seconds:
        return "stale"
    return "final"


def compute_provider_payload_hash(event_id: str, standings: list[Any]) -> str:
    """Compute SHA-256 hash over canonical provider standings."""
    simplified = [
        {
            "ordinal": getattr(s, "ordinal", 0),
            "placement": getattr(s, "placement", 0),
            "entrant_id": str(getattr(s, "entrant_id", "")),
            "entrant_name": str(getattr(s, "entrant_name", "")),
            "is_tied": bool(getattr(s, "is_tied", False)),
        }
        for s in standings
    ]
    data = json.dumps({"event_id": str(event_id), "standings": simplified}, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_presentation_hash(presentations: dict[str, Any]) -> str:
    """Compute SHA-256 hash over resolved presentation payload."""
    data = json.dumps(presentations, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_observation_hash(
    event_id: str,
    standings: list[Any],
    presentations: dict[str, Any],
    *,
    is_completed: bool | None = None,
    completion_state_raw: str | None = None,
    provider_revision: str | None = None,
) -> str:
    """Hash provider content, verification evidence, and presentation.

    Completion evidence is part of an immutable publication version.  Without
    it, unchanged placements moving from active/provisional to completed/final
    would incorrectly reuse the provisional row.
    """
    p_hash = compute_provider_payload_hash(event_id, standings)
    pres_hash = compute_presentation_hash(presentations)
    combined = ":".join((
        p_hash,
        pres_hash,
        "unknown" if is_completed is None else str(bool(is_completed)).lower(),
        str(completion_state_raw or ""),
        str(provider_revision or ""),
    ))
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def result_version_readiness(version: Mapping[str, Any], freshness_seconds: int = 3600) -> str:
    if str(version.get("capture_status")) != "final":
        return "provisional"
    raw_observed = version.get("observed_at")
    try:
        observed = datetime.fromisoformat(str(raw_observed).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=UTC)
        age = max(0.0, (datetime.now(UTC) - observed.astimezone(UTC)).total_seconds())
    except (TypeError, ValueError):
        return "stale"
    return "stale" if age > freshness_seconds else "final"


def results_scene_page_size(scene: Mapping[str, Any] | None, default: int = 16) -> int:
    """Read the frozen page size used by the first Results Group.

    Media-output rows retain the selected page number while the scene retains
    its page size. Keeping this resolution in one place prevents OBS and
    operator commands from fetching a different page than the static preview.
    """
    nodes = scene.get("nodes") if isinstance(scene, Mapping) else None
    if isinstance(nodes, Mapping):
        for node in nodes.values():
            if isinstance(node, Mapping) and node.get("type") == "results-group":
                value = node.get("pageSize")
                if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 10000:
                    return value
            if isinstance(node, Mapping) and node.get("type") == "results-cards":
                auto_sequence = node.get("autoSequence")
                value = auto_sequence.get("pageSize") if isinstance(auto_sequence, Mapping) else None
                if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 10000:
                    return value
    return default


def validate_results_scene(
    scene: Mapping[str, Any],
    *,
    version_id: str,
    require_sequence: bool = False,
) -> list[str]:
    """Validate the persisted Scene v2 security and authoring boundary."""
    errors: list[str] = []
    if scene.get("schemaVersion") != 2:
        errors.append("scene_schema_version_must_be_2")
    data_source = scene.get("dataSource")
    if not isinstance(data_source, Mapping) or data_source.get("kind") != "tournament-results":
        errors.append("scene_data_source_must_be_tournament_results")
    elif str(data_source.get("resultVersionId") or "") != str(version_id):
        errors.append("scene_result_version_binding_mismatch")

    canvas = scene.get("canvas")
    if not isinstance(canvas, Mapping):
        errors.append("scene_canvas_required")
    else:
        for key in ("width", "height"):
            value = canvas.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 or value > 7680:
                errors.append(f"scene_canvas_{key}_invalid")

    nodes = scene.get("nodes")
    root_ids = scene.get("rootIds")
    if not isinstance(nodes, Mapping):
        errors.append("scene_nodes_required")
        return errors
    if len(nodes) > 1000:
        errors.append("scene_node_limit_exceeded")
    if not isinstance(root_ids, list):
        errors.append("scene_root_ids_required")
        root_ids = []

    allowed_types = {
        "text", "image", "rect", "circle", "group",
        "result-card", "results-cards", "results-group",
    }
    allowed_bindings = {
        "placement", "displayName", "prefix", "countryCode", "countryFlagUrl",
        "avatarUrl", "characterId", "characterName", "characterImageUrl",
        "entrantName", "eventName", "gameName",
    }
    graph: dict[str, list[str]] = {}
    template_ids: set[str] = set()
    results_group_count = 0
    sequence_group_count = 0
    results_cards_count = 0
    auto_sequence_count = 0
    for node_id, raw_node in nodes.items():
        if not isinstance(raw_node, Mapping):
            errors.append(f"scene_node_invalid:{node_id}")
            continue
        if str(raw_node.get("id") or "") != str(node_id):
            errors.append(f"scene_node_id_mismatch:{node_id}")
        node_type = raw_node.get("type")
        if node_type not in allowed_types:
            errors.append(f"scene_node_type_invalid:{node_id}")
        if not isinstance(raw_node.get("visible"), bool):
            errors.append(f"scene_node_visibility_invalid:{node_id}")
        if any(key in raw_node for key in ("instanceId", "generatedFrom", "generatedStanding")) or raw_node.get("generated") is True:
            errors.append(f"scene_generated_instance_forbidden:{node_id}")
        binding = raw_node.get("binding")
        if binding is not None and binding not in allowed_bindings:
            errors.append(f"scene_binding_invalid:{node_id}")
        for key in ("x", "y", "width", "height"):
            value = raw_node.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                errors.append(f"scene_node_geometry_invalid:{node_id}:{key}")
            elif key in {"width", "height"} and value <= 0:
                errors.append(f"scene_node_geometry_invalid:{node_id}:{key}")

        children = raw_node.get("childIds") if node_type in {"group", "results-cards"} else []
        if children is None:
            children = []
        if not isinstance(children, list):
            errors.append(f"scene_group_children_invalid:{node_id}")
            children = []
        graph[str(node_id)] = [str(child) for child in children]

        if node_type == "results-group":
            results_group_count += 1
            mode = raw_node.get("mode")
            if mode not in {"board", "sequence"}:
                errors.append(f"scene_results_mode_invalid:{node_id}")
            if mode == "sequence":
                sequence_group_count += 1
            if raw_node.get("cutoff") not in {"top8", "top16", "all"}:
                errors.append(f"scene_results_cutoff_invalid:{node_id}")
            for key in ("pageNumber", "pageSize"):
                value = raw_node.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 10000:
                    errors.append(f"scene_results_{key}_invalid:{node_id}")

            sequence = raw_node.get("sequence")
            if not isinstance(sequence, Mapping):
                errors.append(f"scene_results_sequence_invalid:{node_id}")
            else:
                bounds = {
                    "startDelayMs": (0, 60000),
                    "intervalMs": (1, 60000),
                    "holdMs": (0, 600000),
                }
                for key, (minimum, maximum) in bounds.items():
                    value = sequence.get(key)
                    if (
                        not isinstance(value, (int, float))
                        or isinstance(value, bool)
                        or not math.isfinite(value)
                        or value < minimum
                        or value > maximum
                    ):
                        errors.append(f"scene_results_sequence_{key}_invalid:{node_id}")
                if sequence.get("exit") not in {"together", "sequential", "none"}:
                    errors.append(f"scene_results_sequence_exit_invalid:{node_id}")
                if sequence.get("order") not in {
                    "placement-asc", "placement-desc", "champion-last",
                    "podium-first", "row-major", "column-major",
                }:
                    errors.append(f"scene_results_sequence_order_invalid:{node_id}")
                for key in ("loop", "manualCue"):
                    if not isinstance(sequence.get(key), bool):
                        errors.append(f"scene_results_sequence_{key}_invalid:{node_id}")

            custom_slots = raw_node.get("customSlots")
            if custom_slots is not None:
                if not isinstance(custom_slots, list) or len(custom_slots) > 512:
                    errors.append(f"scene_results_slots_invalid:{node_id}")
                else:
                    for index, slot in enumerate(custom_slots):
                        if not isinstance(slot, Mapping):
                            errors.append(f"scene_results_slot_invalid:{node_id}:{index}")
                            continue
                        for key in ("x", "y", "width", "height"):
                            value = slot.get(key)
                            if (
                                not isinstance(value, (int, float))
                                or isinstance(value, bool)
                                or not math.isfinite(value)
                                or (key in {"width", "height"} and value <= 0)
                            ):
                                errors.append(f"scene_results_slot_geometry_invalid:{node_id}:{index}:{key}")

            template_id = str(raw_node.get("templateId") or "")
            card_definition_id = str(raw_node.get("cardDefinitionId") or "")
            if card_definition_id:
                template_id = card_definition_id
            template = nodes.get(template_id)
            if (
                not template_id
                or not isinstance(template, Mapping)
                or template.get("type") != "group"
                or (
                    template.get("templateRole") != "player-card"
                    and template.get("definitionRole") != "result-card"
                )
            ):
                errors.append(f"scene_player_card_template_invalid:{node_id}")
            else:
                template_ids.add(template_id)
                if str(template.get("parentId") or "") != str(node_id):
                    errors.append(f"scene_player_card_parent_mismatch:{node_id}")

        if node_type == "results-cards":
            results_cards_count += 1
            schedule = raw_node.get("schedule")
            if not isinstance(schedule, Mapping):
                errors.append(f"scene_results_cards_schedule_invalid:{node_id}")
            else:
                if children:
                    sequence_group_count += 1
                delay = schedule.get("delayBetweenStartsMs")
                if (
                    not isinstance(delay, (int, float))
                    or isinstance(delay, bool)
                    or not math.isfinite(delay)
                    or delay < 0
                    or delay > 60000
                ):
                    errors.append(f"scene_results_cards_delay_invalid:{node_id}")
                if schedule.get("order") not in {"placement-asc", "placement-desc", "custom"}:
                    errors.append(f"scene_results_cards_order_invalid:{node_id}")
                if schedule.get("trigger") not in {"with-previous", "after-previous"}:
                    errors.append(f"scene_results_cards_trigger_invalid:{node_id}")
                for key in ("keepPreviousVisible", "loop"):
                    if not isinstance(schedule.get(key), bool):
                        errors.append(f"scene_results_cards_{key}_invalid:{node_id}")

            auto_sequence = raw_node.get("autoSequence")
            if auto_sequence is not None:
                if not isinstance(auto_sequence, Mapping):
                    errors.append(f"scene_auto_sequence_invalid:{node_id}")
                else:
                    if not isinstance(auto_sequence.get("enabled"), bool):
                        errors.append(f"scene_auto_sequence_enabled_invalid:{node_id}")
                    elif auto_sequence.get("enabled") is True:
                        auto_sequence_count += 1
                    if auto_sequence.get("range") not in {"top8", "top16", "all"}:
                        errors.append(f"scene_auto_sequence_range_invalid:{node_id}")
                    if auto_sequence.get("order") not in {"placement-asc", "placement-desc", "custom"}:
                        errors.append(f"scene_auto_sequence_order_invalid:{node_id}")
                    if auto_sequence.get("endBehavior") not in {"card-exit", "keep-visible", "clear-after-hold"}:
                        errors.append(f"scene_auto_sequence_end_invalid:{node_id}")
                    for key, minimum, maximum in (
                        ("pageNumber", 1, 10000),
                        ("pageSize", 1, 10000),
                        ("delayBetweenStartsMs", 0, 60000),
                    ):
                        value = auto_sequence.get(key)
                        if (
                            not isinstance(value, (int, float))
                            or isinstance(value, bool)
                            or not math.isfinite(value)
                            or value < minimum
                            or value > maximum
                        ):
                            errors.append(f"scene_auto_sequence_{key}_invalid:{node_id}")
                    stage_id = str(auto_sequence.get("stageInstanceId") or "")
                    if stage_id not in children:
                        errors.append(f"scene_auto_sequence_stage_invalid:{node_id}")

        if node_type == "result-card":
            parent_id = str(raw_node.get("parentId") or "")
            parent = nodes.get(parent_id)
            if not isinstance(parent, Mapping) or parent.get("type") != "results-cards":
                errors.append(f"scene_result_card_parent_invalid:{node_id}")
            definition_id = str(raw_node.get("definitionId") or "")
            definition = nodes.get(definition_id)
            if (
                not definition_id
                or not isinstance(definition, Mapping)
                or definition.get("type") != "group"
                or (
                    definition.get("definitionRole") != "result-card"
                    and definition.get("templateRole") != "player-card"
                )
            ):
                errors.append(f"scene_result_card_definition_invalid:{node_id}")
            else:
                template_ids.add(definition_id)
            if raw_node.get("instanceRole") not in {"stage", "linked"}:
                errors.append(f"scene_result_card_role_invalid:{node_id}")
            ordinal = raw_node.get("standingOrdinal")
            if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
                errors.append(f"scene_result_card_ordinal_invalid:{node_id}")
            lifecycle = raw_node.get("outerAnimation")
            if lifecycle is not None:
                if not isinstance(lifecycle, Mapping):
                    errors.append(f"scene_result_card_animation_invalid:{node_id}")
                else:
                    for state_name in ("start", "visible", "exit"):
                        transform = lifecycle.get(state_name)
                        if not isinstance(transform, Mapping):
                            errors.append(f"scene_result_card_animation_{state_name}_invalid:{node_id}")
                            continue
                        for key in ("x", "y", "scale", "opacity", "rotation"):
                            value = transform.get(key)
                            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                                errors.append(f"scene_result_card_animation_{state_name}_{key}_invalid:{node_id}")
                    for key in ("enterDurationMs", "visibleHoldMs", "exitDurationMs"):
                        value = lifecycle.get(key)
                        if (
                            not isinstance(value, (int, float))
                            or isinstance(value, bool)
                            or not math.isfinite(value)
                            or value < 0
                            or value > 600000
                        ):
                            errors.append(f"scene_result_card_animation_{key}_invalid:{node_id}")

    if results_group_count == 0 and results_cards_count == 0:
        errors.append("scene_results_group_required")
    if require_sequence and sequence_group_count == 0 and auto_sequence_count == 0:
        errors.append("scene_sequence_group_required")

    for root_id in root_ids:
        if str(root_id) not in nodes:
            errors.append(f"scene_root_missing:{root_id}")
    for node_id, children in graph.items():
        for child_id in children:
            if child_id not in nodes:
                errors.append(f"scene_child_missing:{node_id}:{child_id}")
            else:
                child = nodes[child_id]
                if isinstance(child, Mapping) and str(child.get("parentId") or "") != node_id:
                    errors.append(f"scene_child_parent_mismatch:{node_id}:{child_id}")
    for template_id in template_ids:
        if template_id in {str(item) for item in root_ids}:
            errors.append(f"scene_template_cannot_be_root:{template_id}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            errors.append(f"scene_cycle_detected:{node_id}")
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for child_id in graph.get(node_id, []):
            visit(child_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph:
        visit(node_id)
    return list(dict.fromkeys(errors))


async def get_provider_for_tournament(workspace_id: str, tournament_slug: str):
    """Resolve the tournament provider from tournament credentials."""
    tournament = await database.get_tournament(tournament_slug, workspace_id)
    if not tournament:
        raise ValueError("tournament_not_found")

    provider_type = tournament.get("provider_type") or "startgg"
    account_id = tournament.get("provider_account_id") or tournament.get("account_id") or "default"
    return provider_registry.resolve(provider_type, workspace_id=workspace_id, account_id=account_id)


async def refresh_event_results(
    workspace_id: str,
    tournament_slug: str,
    event_id: str,
    user_id: str,
    force: bool = False,
    presentation_mode: str = "current",
    pool: Any = None,
) -> dict[str, Any]:
    """Fetch provider standings, resolve presentations, and save or reuse an immutable version."""
    lock_key = (workspace_id, tournament_slug, event_id)
    async with _refresh_locks[lock_key]:
        # 1. Read tournament metadata
        tournament = await database.get_tournament(tournament_slug, workspace_id)
        if not tournament:
            raise ValueError(f"Tournament '{tournament_slug}' not found in workspace '{workspace_id}'.")

        provider_type = tournament.get("provider_type") or "startgg"
        account_id = tournament.get("provider_account_id") or tournament.get("account_id") or "default"
        provider_tournament_id = tournament.get("provider_tournament_id") or tournament.get("slug")

        # 2. External Provider I/O (Executed outside DB write transactions)
        provider = await get_provider_for_tournament(workspace_id, tournament_slug)

        snapshot_req = ProviderSnapshotRequestV2(
            provider_type=provider_type,
            provider_account_id=account_id,
            tournament_id=str(provider_tournament_id),
            scope=SnapshotScope.FINAL_STANDINGS,
            options={"event_id": event_id, "all_pages": True, "force": force},
        )
        snapshot = await provider.fetch_snapshot(snapshot_req)
        event_results: ProviderEventResults = snapshot.payload.get("event_results")
        if not event_results:
            raise ValueError(f"Provider returned no event results for event '{event_id}'.")

        validation_errors = validate_provider_event_results(
            event_results,
            expected_event_id=event_id,
            provider_type=provider_type,
        )
        if validation_errors:
            raise ValueError("provider_results_invalid: " + "; ".join(validation_errors))

        observed_at = snapshot.observed_at if isinstance(getattr(snapshot, "observed_at", None), str) else datetime.now(UTC).isoformat()

        # 3. Batch resolve presentation with field provenance
        game_id = event_results.game_id or tournament.get("game")
        presentations, pres_warnings, profile_ids = await batch_resolve_standings_presentation(
            workspace_id=workspace_id,
            tournament_slug=tournament_slug,
            event_id=event_id,
            standings=event_results.standings,
            provider_type=provider_type,
            game_id=game_id,
        )

        all_warnings = list(event_results.warnings)
        all_warnings.extend([w["message"] for w in pres_warnings])
        # Provider diagnostics become durable publication metadata, so bound
        # both their count and size and never persist raw response bodies.
        all_warnings = [str(warning)[:500] for warning in all_warnings[:100]]

        # Detect tied cutoff warning (e.g. ties at 7th or 8th)
        tied_at_8 = any(s.placement <= 8 and s.is_tied for s in event_results.standings if s.placement == 8 or s.ordinal == 8)
        if tied_at_8:
            all_warnings.append("Tied placements exist at the Top 8 boundary. Additional cards may be rendered.")

        # 4. Compute hashes
        p_hash = compute_provider_payload_hash(event_id, event_results.standings)
        pres_hash = compute_presentation_hash(presentations)
        base_obs_hash = compute_observation_hash(
            event_id,
            event_results.standings,
            presentations,
            is_completed=event_results.is_completed,
            completion_state_raw=event_results.completion_state_raw,
            provider_revision=event_results.revision,
        )
        capture_status = "final" if event_results.is_completed else "provisional"

        try:
            parsed_observed_at = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
            if parsed_observed_at.tzinfo is None:
                parsed_observed_at = parsed_observed_at.replace(tzinfo=UTC)
            observed_seconds_ago = max(
                0.0,
                (datetime.now(UTC) - parsed_observed_at.astimezone(UTC)).total_seconds(),
            )
        except (TypeError, ValueError):
            parsed_observed_at = datetime.now(UTC)
            observed_seconds_ago = 0.0

        readiness = classify_readiness(event_results, observed_seconds_ago=observed_seconds_ago)

        # 5. Reuse the latest identical observation while its successful
        # verification is still current.  Once it is stale, a deliberate
        # provider refresh creates a new immutable verification version.  The
        # minute bucket preserves cross-process idempotency for concurrent
        # refreshes without keeping an old version stale forever.
        latest_version = await repo.get_latest_result_version(
            workspace_id,
            tournament_slug,
            event_id,
        )
        existing_version = latest_version
        same_latest_observation = bool(
            latest_version
            and latest_version.get("provider_payload_hash") == p_hash
            and latest_version.get("presentation_hash") == pres_hash
            and latest_version.get("capture_status") == capture_status
            and latest_version.get("provider_state_raw") == (event_results.completion_state_raw or "UNKNOWN")
            and latest_version.get("provider_revision") == event_results.revision
        )
        needs_new_verification = bool(latest_version and not same_latest_observation)
        if not same_latest_observation:
            existing_version = None
        if same_latest_observation and existing_version:
            results_media_readiness = result_version_readiness(existing_version)
            if results_media_readiness == "stale" and readiness != "stale":
                existing_version = None
                needs_new_verification = True
            elif results_media_readiness != "stale":
                readiness = results_media_readiness
            else:
                # A provider/cache that still reports an old observation must
                # remain stale; creating another row would fabricate freshness.
                readiness = "stale"

        obs_hash = base_obs_hash
        if existing_version is None and needs_new_verification and readiness != "stale":
            verification_bucket = int(parsed_observed_at.timestamp() // 60)
            obs_hash = hashlib.sha256(
                f"{base_obs_hash}:verified:{verification_bucket}".encode("utf-8")
            ).hexdigest()

        if existing_version is None:
            existing_version = await repo.get_result_version_by_hash(
                workspace_id=workspace_id,
                tournament_slug=tournament_slug,
                event_id=event_id,
                observation_hash=obs_hash,
            )

        if existing_version:
            # Audit idempotent reuse
            await database.record_audit_event(
                workspace_id=workspace_id,
                actor_id=user_id,
                action="results.refresh.reuse",
                outcome="success",
                target_type="tournament_result_version",
                target_id=existing_version["id"],
                detail={"tournament_slug": tournament_slug, "event_id": event_id},
            )
            return {
                "version": existing_version,
                "reused": True,
                "readiness_state": readiness,
            }

        # 6. Prepare new immutable version payload and entries
        version_data = {
            "tournament_slug": tournament_slug,
            "provider_type": provider_type,
            "provider_account_id": account_id,
            "provider_tournament_id": str(provider_tournament_id),
            "event_id": event_id,
            "event_name": event_results.event_name or f"Event {event_id}",
            "game_id": game_id,
            "game_name": event_results.game_name or tournament.get("game_name"),
            "capture_status": capture_status,
            "provider_state_raw": event_results.completion_state_raw or "UNKNOWN",
            "provider_revision": event_results.revision,
            "provider_payload_hash": p_hash,
            "presentation_hash": pres_hash,
            "observation_hash": obs_hash,
            "observed_at": observed_at,
            "finalized_at": event_results.finalized_at or (observed_at if event_results.is_completed else None),
            "warning_json": all_warnings,
            "event_metadata_json": {
                "tournament_name": tournament.get("name"),
                "tournament_slug": tournament_slug,
                "event_id": event_id,
                "event_name": event_results.event_name,
            },
            "created_by": user_id,
            "_audit_action": "results.refresh.create",
        }

        entry_rows = []
        for s in event_results.standings:
            eid = str(s.entrant_id)
            entry_rows.append({
                "ordinal": s.ordinal,
                "placement": s.placement,
                "entrant_id": eid,
                "entrant_name": s.entrant_name,
                "provider_user_id": s.provider_user_id,
                "player_profile_id": profile_ids.get(eid),
                "is_tied": s.is_tied,
                "presentation_json": presentations.get(eid, {}),
                "provider_entry_json": getattr(s, "metadata", {}) or {},
            })

        created = await repo.create_result_version_with_entries(
            workspace_id=workspace_id,
            version_data=version_data,
            entries=entry_rows,
        )

        created_new = bool(created.pop("_created", True))
        return {
            "version": created,
            "reused": not created_new,
            "readiness_state": readiness,
        }
