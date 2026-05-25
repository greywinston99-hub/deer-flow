"""Rebuild CER_RMF_174 slot workbench with fixed classifier and slot engine."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add paths
BACKEND_ROOT = Path(__file__).resolve().parents[1]
HARNES_PATH = str(BACKEND_ROOT / "packages" / "harness")

sys.path.insert(0, HARNES_PATH)
sys.path.insert(0, str(BACKEND_ROOT))

# Monkeypatch auth to bypass gate
import app.gateway.routers.cer_v5_adaptive_review_engine as v5_engine

mock_auth = MagicMock()
mock_auth.user_id = "system_rebuild"
v5_engine.get_cer_auth_with_gate_role = lambda: mock_auth

from app.gateway.routers.cer_source_package_intake_bridge import (
    scan_source_package,
    classify_document_candidates,
    build_source_family_groups,
)
from app.gateway.routers.cer_v5_adaptive_review_engine import _try_build_slots
from app.gateway.routers.cer_v5_models import SlotWorkbenchBuildRequest

SOURCE_PACKAGE = "/Users/winstonwei/Desktop/AI测试项目文件/CER/03 新版 心擎 MDR测试版本文件"
PROJECT_ID = "CER_RMF_174"


def main():
    print("Scanning source package...")
    scanned_files, scan_warnings, total_files = scan_source_package(
        SOURCE_PACKAGE, recursive=True, max_files=500
    )
    print(f"Scanned {total_files} files, {len(scanned_files)} recognized")

    print("Classifying candidates...")
    candidates = classify_document_candidates(scanned_files)
    print(f"Classified {len(candidates)} candidates")

    competitor_count = sum(
        1
        for c in candidates
        if any(str(s).startswith("competitor_document") for s in c.negative_signals)
    )
    print(f"Competitor documents detected: {competitor_count}")

    print("Building source family groups...")
    groups = build_source_family_groups(candidates)
    print(f"Built {len(groups)} family groups")

    print("Building slots...")
    result = _try_build_slots(
        PROJECT_ID,
        SlotWorkbenchBuildRequest(
            source_family_groups=[g.model_dump(mode="json") for g in groups]
        ),
        provenance="REAL_EVIDENCE_DRIVEN",
    )

    if hasattr(result, "slot_workbench_id"):
        print(f"Workbench built: {result.slot_workbench_id}")
        print(f"Slots: {len(result.slots)}")
        for s in result.slots:
            print(
                f"  {s.slot_type}: {s.slot_status} | band={s.confidence_band} | score={s.confidence_score}"
            )
            if s.candidates:
                print(f"    top: {s.candidates[0].file_name}")
    else:
        print(f"Build failed: {result}")


if __name__ == "__main__":
    main()
