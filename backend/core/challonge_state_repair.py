"""Immutable, report-first repair for legacy false-live Challonge rows."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from uuid import uuid4

from backend.core import database


@dataclass(frozen=True)
class RepairRow:
    tournament: str
    match_key: str
    previous_status: str | None
    provider_raw_state: str | None
    provider_normalized_state: str | None
    local_workflow_evidence: list[str]
    eligibility: str
    proposed_change: str | None
    reason: str


@dataclass(frozen=True)
class RepairReport:
    report_id: str
    snapshot_id: str
    snapshot_observed_at: str
    fingerprint: str
    rows: list[dict]


def _evidence(row: dict) -> list[str]:
    values = {
        "called_at": row.get("called_at"), "ready": bool(row.get("p1_ready") or row.get("p2_ready")),
        "thread": row.get("discord_thread_id") or row.get("thread_id"), "station": row.get("station_id"),
        # Legacy rows default score columns to 0/0 even when nobody reported a
        # result. Treat a nonzero value or explicit result kind as evidence.
        "score": bool(row.get("result_kind")) or bool(int(row.get("p1_score") or 0) or int(row.get("p2_score") or 0)),
        "local_audit": bool(row.get("has_local_audit")),
    }
    return [name for name, present in values.items() if present]


async def dry_run(*, snapshot_id: str, snapshot_observed_at: str, provider_states: dict[str, dict]) -> RepairReport:
    """Create a deterministic report; it never writes an active match or station."""
    if not snapshot_id or not snapshot_observed_at:
        raise ValueError("A fixed snapshot ID and UTC observation timestamp are required.")
    rows: list[RepairRow] = []
    for row in await database.list_challonge_state_repair_rows_v2():
        key = str(row["set_id"])
        remote = provider_states.get(key)
        evidence = _evidence(row)
        raw = (remote or {}).get("raw")
        normalized = (remote or {}).get("normalized")
        if not remote:
            eligibility, change, reason = "needs_review", None, "Match absent from the immutable snapshot."
        elif str(raw).lower() != "open":
            eligibility, change, reason = "excluded", None, "Remote state is not open."
        elif evidence:
            eligibility, change, reason = "excluded", None, f"Local workflow evidence: {', '.join(evidence)}."
        elif (row.get("status") or row.get("hub_status")) != "in_progress":
            eligibility, change, reason = "excluded", None, "Row is not a legacy false-live candidate."
        else:
            eligibility, change, reason = "eligible", "not_started", "Challonge open match has no local workflow evidence."
        rows.append(RepairRow(
            tournament=str(row.get("tournament_slug")), match_key=key,
            previous_status=row.get("status"), provider_raw_state=raw,
            provider_normalized_state=normalized, local_workflow_evidence=evidence,
            eligibility=eligibility, proposed_change=change, reason=reason,
        ))
    serialized = [asdict(item) for item in rows]
    fingerprint = hashlib.sha256(json.dumps({"snapshot_id": snapshot_id, "snapshot_observed_at": snapshot_observed_at, "rows": serialized}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    report = RepairReport(str(uuid4()), snapshot_id, snapshot_observed_at, fingerprint, serialized)
    await database.save_challonge_state_repair_report_v2(asdict(report))
    return report


async def apply_approved(report: RepairReport, approved_set_ids: list[str], *, organizer: str) -> int:
    """Explicitly invoked later by an organizer, never by dry run or startup."""
    return await database.apply_challonge_state_repair_v2(
        report.report_id, report.fingerprint, approved_set_ids, applied_by=organizer
    )
