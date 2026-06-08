"""Verify RMF gate closure does not fabricate a simulated reviewer decision.

Step 7 / TDD red — covers Step 15 outcome (fix runner.py:1686-1695 self-fabrication bug).

Current behavior (bug): when ``human_gate_decision.json`` is absent, the runner
auto-writes a record with ``reviewer="smoke-run-simulated-reviewer"`` and
``simulated: true``, and proceeds with closure as if the decision were real.
This silently bypasses the human gate.

Expected behavior after fix:
- No artifact in the run output contains ``"simulated": true``.
- A ``human_gate_status.json`` is written with ``state="pending"``.
- ``task_ledger.json`` records ``human_adjudication_pending``.
- The runner reports ``HOLD_FOR_HUMAN_DECISION`` (not silently progressing to closure).
"""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import yaml


def _write_minimal_docx(path: Path, *, paragraphs: list[str] | None = None) -> None:
    paragraph_xml = "".join(
        f"<w:p><w:r><w:t>{value}</w:t></w:r></w:p>"
        for value in (paragraphs or [])
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraph_xml}<w:sectPr><w:pgSz w:w='11906' w:h='16838'/></w:sectPr></w:body>"
        "</w:document>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("word/document.xml", document_xml)


def _write_project_profile(profile_path: Path, input_root: Path) -> None:
    profile = {
        "project_id": "demo",
        "project_name": "Demo Project",
        "institution_profile": {
            "organization": "Example",
            "assessment_body": "BSI",
            "profile_version": "v1",
        },
        "review_scope": {
            "mode": "single_project_serial_review",
            "review_language": "en",
            "jurisdiction": "EU MDR",
            "human_gate_required": True,
        },
        "primary_review_object": "RMF",
        "device_context": {"device_name": "Demo Device"},
        "input_package": {
            "root_path": str(input_root),
            "documents": [
                {
                    "doc_type": "RMF",
                    "label": "RMF",
                    "path": str(input_root / "Risk_Management_File.docx"),
                    "required_for_p0": True,
                    "source_ref": {
                        "document_id": "rmf_main",
                        "path": str(input_root / "Risk_Management_File.docx"),
                    },
                },
                {
                    "doc_type": "FMEA",
                    "label": "DFMEA",
                    "path": str(input_root / "Design_DFMEA.docx"),
                    "required_for_p0": True,
                    "source_ref": {
                        "document_id": "dfmea_main",
                        "path": str(input_root / "Design_DFMEA.docx"),
                    },
                },
            ],
        },
        "artifact_policy": {
            "artifact_root": "/mnt/user-data/outputs/rmf_review_v1_1/demo",
            "persist_intermediate_artifacts": True,
            "final_outputs": [],
        },
    }
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")


def _build_runner(tmp_path: Path, monkeypatch):
    from deerflow.runtime.rmf_review import RMFReviewRunner

    repo_root = Path("/Users/winstonwei/Documents/Playground/deer-flow")
    deer_home = tmp_path / "deer-home"
    monkeypatch.setenv("DEER_FLOW_HOME", str(deer_home))

    input_root = tmp_path / "inputs"
    input_root.mkdir(parents=True)
    _write_minimal_docx(
        input_root / "Risk_Management_File.docx",
        paragraphs=["Demo Device Risk Management Report", "Risk analysis included."],
    )
    _write_minimal_docx(
        input_root / "Design_DFMEA.docx",
        paragraphs=["Demo DFMEA"],
    )

    profile_path = tmp_path / "project_profile.yaml"
    _write_project_profile(profile_path, input_root)

    return RMFReviewRunner(
        repo_root=repo_root,
        workflow_path=repo_root / "workflows" / "rmf_review_v1_1.yaml",
        project_profile_path=profile_path,
        input_root=input_root,
        thread_id="rmf-no-fabricate-test",
    )


def _scan_for_simulated_reviewer(artifact_root: Path) -> list[Path]:
    """Find any artifact that contains a fabricated/simulated reviewer marker."""
    offenders: list[Path] = []
    for path in artifact_root.rglob("*.json"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if '"simulated": true' in text or '"simulated":true' in text:
            offenders.append(path)
        if "smoke-run-simulated-reviewer" in text:
            offenders.append(path)
    return offenders


def test_smoke_run_does_not_fabricate_simulated_reviewer_decision(tmp_path, monkeypatch):
    """Smoke-run must not auto-write a simulated human_gate_decision.json."""
    runner = _build_runner(tmp_path, monkeypatch)
    result = runner.run(mode="smoke-run")

    artifact_root = Path(result.artifact_root_actual)
    offenders = _scan_for_simulated_reviewer(artifact_root)
    assert not offenders, (
        f"Found {len(offenders)} artifacts with simulated reviewer fabrication: "
        f"{[str(p) for p in offenders]}. The runner must not auto-write a fake "
        "human_gate_decision.json with simulated=true."
    )


def test_closure_only_without_decision_returns_hold_for_human(tmp_path, monkeypatch):
    """Closure-only mode without human_gate_decision.json must return HOLD_FOR_HUMAN_DECISION."""
    from deerflow.runtime.rmf_review import RMFReviewRunner

    runner1 = _build_runner(tmp_path, monkeypatch)
    result1 = runner1.run(mode="smoke-run")
    artifact_root = Path(result1.artifact_root_actual)

    decision_path = artifact_root / "05_human_boundary" / "human_gate_decision.json"
    if decision_path.exists():
        decision_path.unlink()

    runner2 = RMFReviewRunner(
        repo_root=Path("/Users/winstonwei/Documents/Playground/deer-flow"),
        workflow_path=Path("/Users/winstonwei/Documents/Playground/deer-flow/workflows/rmf_review_v1_1.yaml"),
        project_profile_path=tmp_path / "project_profile.yaml",
        input_root=tmp_path / "inputs",
        thread_id="rmf-no-fabricate-test",
        run_id_override=result1.run_id,
        artifact_root_override=str(artifact_root),
    )
    result2 = runner2.run(mode="closure-only")

    assert getattr(result2, "status", None) == "HOLD_FOR_HUMAN_DECISION", (
        f"closure-only without decision should return status='HOLD_FOR_HUMAN_DECISION', "
        f"got status={getattr(result2, 'status', None)!r}"
    )

    assert not (artifact_root / "07_gate_closure" / "gate_closure_report.json").exists(), (
        "gate_closure_report.json must NOT be written when human gate decision is absent"
    )

    status_path = artifact_root / "00_manifest" / "human_gate_status.json"
    assert status_path.exists(), "human_gate_status.json must be written"
    status_doc = json.loads(status_path.read_text(encoding="utf-8"))
    assert status_doc.get("state") == "pending"


def test_task_ledger_records_human_adjudication_pending(tmp_path, monkeypatch):
    """task_ledger.json must mark human_adjudication_pending when decision missing."""
    from deerflow.runtime.rmf_review import RMFReviewRunner

    runner1 = _build_runner(tmp_path, monkeypatch)
    result1 = runner1.run(mode="smoke-run")
    artifact_root = Path(result1.artifact_root_actual)
    decision_path = artifact_root / "05_human_boundary" / "human_gate_decision.json"
    if decision_path.exists():
        decision_path.unlink()

    runner2 = RMFReviewRunner(
        repo_root=Path("/Users/winstonwei/Documents/Playground/deer-flow"),
        workflow_path=Path("/Users/winstonwei/Documents/Playground/deer-flow/workflows/rmf_review_v1_1.yaml"),
        project_profile_path=tmp_path / "project_profile.yaml",
        input_root=tmp_path / "inputs",
        thread_id="rmf-no-fabricate-test",
        run_id_override=result1.run_id,
        artifact_root_override=str(artifact_root),
    )
    runner2.run(mode="closure-only")

    ledger_path = artifact_root / "00_manifest" / "task_ledger.json"
    assert ledger_path.exists(), "task_ledger.json must exist after RMF run"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    found = False
    if isinstance(ledger, dict):
        if ledger.get("status") == "human_adjudication_pending":
            found = True
        else:
            entries = ledger.get("entries") or ledger.get("tasks") or []
            for entry in entries:
                if isinstance(entry, dict) and entry.get("status") == "human_adjudication_pending":
                    found = True
                    break
    elif isinstance(ledger, list):
        for entry in ledger:
            if isinstance(entry, dict) and entry.get("status") == "human_adjudication_pending":
                found = True
                break

    assert found, (
        f"task_ledger.json must include a human_adjudication_pending entry when decision missing; "
        f"got: {json.dumps(ledger)[:300]}"
    )
