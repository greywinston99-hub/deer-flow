"""V5 Shadow Backtest Engine — Before/after recommendation comparison, sandbox only."""

from __future__ import annotations

import uuid


def _band_rank(band: str) -> int:
    return {"MISSING": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(str(band or "MISSING"), 0)


def run_shadow_backtest(
    project_id: str,
    slot_workbench_id: str,
    before_slots: list[dict],
    after_slots: list[dict],
) -> dict:
    confidence_shifts = []
    changed_source_families = []
    improved = 0
    worsened = 0
    unchanged = 0

    before_map = {slot["slot_type"]: slot for slot in before_slots}
    after_map = {slot["slot_type"]: slot for slot in after_slots}

    for slot_type, before in before_map.items():
        after = after_map.get(slot_type)
        if after is None:
            continue

        before_band = before.get("confidence_band", "MISSING")
        after_band = after.get("confidence_band", "MISSING")
        before_score = float(before.get("confidence_score", 0.0))
        after_score = float(after.get("confidence_score", 0.0))

        if after_score > before_score:
            improved += 1
        elif after_score < before_score:
            worsened += 1
        else:
            unchanged += 1

        if before_band != after_band or before.get("recommended_canonical_file_id") != after.get("recommended_canonical_file_id"):
            changed_source_families.append(slot_type)
            confidence_shifts.append(
                {
                    "slot_type": slot_type,
                    "before_band": before_band,
                    "after_band": after_band,
                    "before_score": before_score,
                    "after_score": after_score,
                    "before_file_id": before.get("recommended_canonical_file_id"),
                    "after_file_id": after.get("recommended_canonical_file_id"),
                }
            )

    total = max(len(before_map), 1)
    false_positive_risk = "LOW" if worsened <= total * 0.1 else ("MEDIUM" if worsened <= total * 0.3 else "HIGH")
    false_negative_risk = "LOW" if improved >= worsened else ("MEDIUM" if improved + unchanged >= worsened else "HIGH")
    drift_count = len(changed_source_families)
    drift_risk = "LOW" if drift_count <= total * 0.2 else ("MEDIUM" if drift_count <= total * 0.5 else "HIGH")
    regression_risk = "LOW" if worsened == 0 else ("MEDIUM" if worsened <= total * 0.2 else "HIGH")

    return {
        "backtest_id": f"bt-{uuid.uuid4().hex[:8]}",
        "project_id": project_id,
        "slot_workbench_id": slot_workbench_id,
        "before_recommendations": [
            {
                "slot_type": slot["slot_type"],
                "band": slot.get("confidence_band"),
                "score": slot.get("confidence_score"),
                "recommended_canonical_file_id": slot.get("recommended_canonical_file_id"),
            }
            for slot in before_slots
        ],
        "after_recommendations": [
            {
                "slot_type": slot["slot_type"],
                "band": slot.get("confidence_band"),
                "score": slot.get("confidence_score"),
                "recommended_canonical_file_id": slot.get("recommended_canonical_file_id"),
            }
            for slot in after_slots
        ],
        "changed_source_families": changed_source_families,
        "confidence_band_shifts": confidence_shifts,
        "drift_risk_assessment": f"{drift_risk} — {drift_count} source families changed recommendation or confidence band.",
        "false_positive_risk": f"{false_positive_risk} — {worsened} source families became less confident in sandbox backtest.",
        "false_negative_risk": f"{false_negative_risk} — {improved} source families improved while {worsened} worsened.",
        "regression_risk": f"{regression_risk} — {worsened} regressive moves across {total} source families.",
        "rollback_plan": "Keep runtime review on the current active logic. Promote any candidate only after sandbox review, regression checks, and explicit human approval.",
        "sandbox_only": True,
        "approval_required": True,
    }
