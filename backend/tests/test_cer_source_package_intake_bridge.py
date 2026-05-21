"""Tests for CER Source Package Intake Bridge — Phase 19C.

Tests the source package scan → classify → source_documents → source_status → available-source request pipeline.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gateway.routers.cer_source_package_intake_bridge import (
    validate_safe_path,
    validate_source_package_path,
    scan_source_package,
    classify_document_candidates,
    build_source_documents_from_candidates,
    derive_source_status,
    build_available_source_request,
    build_human_confirmation_packet,
    SourceStatusOut,
    SourceDocumentOut,
    ScannedFile,
    ClassificationCandidate,
    SUPPORTED_EXTENSIONS,
)


# ── Path Validation Tests ──────────────────────────────────────────────────────


class TestPathValidation:
    """Tests for path safety validation."""

    def test_root_blocked(self):
        is_safe, _ = validate_safe_path("/")
        assert is_safe is False

    def test_system_dirs_blocked(self):
        # On macOS, some dirs are symlinks to /private/* but should still be blocked
        for path in ["/System", "/Library", "/usr", "/etc", "/sbin", "/cores"]:
            is_safe, _ = validate_safe_path(path)
            assert is_safe is False, f"{path} should be blocked"

    def test_var_allowed(self):
        """On macOS /var is symlinked to /private/var — allowed as a normal directory."""
        is_safe, _ = validate_safe_path("/var/folders")
        assert is_safe is True

    def test_ssh_pattern_blocked(self):
        is_safe, _ = validate_safe_path("/home/user/.ssh")
        assert is_safe is False

    def test_git_pattern_blocked(self):
        is_safe, _ = validate_safe_path("/project/.git")
        assert is_safe is False

    def test_credentials_pattern_blocked(self):
        is_safe, _ = validate_safe_path("/secrets/credentials.json")
        assert is_safe is False

    def test_aws_creds_pattern_blocked(self):
        is_safe, _ = validate_safe_path("/home/.aws/credentials")
        assert is_safe is False

    def test_tmp_subdirectory_allowed(self):
        is_safe, _ = validate_safe_path("/tmp/my_project")
        assert is_safe is True

    def test_var_folders_allowed(self):
        is_safe, _ = validate_safe_path("/var/folders/abc")
        assert is_safe is True

    def test_users_home_allowed(self):
        is_safe, _ = validate_safe_path("/Users/joe/Documents")
        assert is_safe is True

    def test_tmp_file_rejected(self):
        """A file path (not directory) should be rejected."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "somefile.txt"
            file_path.write_text("content")
            is_valid, err = validate_source_package_path(str(file_path))
            assert is_valid is False
            assert "not a directory" in err


# ── Scanner Tests ───────────────────────────────────────────────────────────────


class TestSourcePackageScanner:
    """Tests for source package folder scanning."""

    @pytest.fixture
    def temp_package(self, tmp_path):
        """Create a temporary source package with test files."""
        (tmp_path / "IFU_document_final.pdf").write_text("fake ifu content")
        (tmp_path / "CER_report_draft.md").write_text("fake cer content")
        (tmp_path / "equivalence_table.xlsx").write_text("fake equiv content")
        (tmp_path / "README.txt").write_text("readme")
        return tmp_path

    def test_scans_supported_files(self, temp_package):
        scanned, warnings = scan_source_package(str(temp_package))
        assert len(scanned) == 4
        filenames = {sf.file_name for sf in scanned}
        assert "IFU_document_final.pdf" in filenames
        assert "CER_report_draft.md" in filenames

    def test_respects_max_files(self, temp_package):
        _, warnings = scan_source_package(str(temp_package), max_files=2)
        assert "exceeds max_files" in warnings[0]

    def test_unsupported_extensions_flagged_in_scanned(self, tmp_path):
        """Unsupported files (.exe) are included but flagged with a warning."""
        (tmp_path / "malware.exe").write_text("binary")
        scanned, warnings = scan_source_package(str(tmp_path))
        exe_file = next((sf for sf in scanned if sf.file_name == "malware.exe"), None)
        assert exe_file is not None, "Unsupported file should be in scanned list"
        assert exe_file.scan_status == "flagged"
        assert "Unsupported" in exe_file.warning
        assert any("Unsupported" in w for w in warnings)

    def test_zero_byte_flagged(self, tmp_path):
        (tmp_path / "empty.pdf").write_text("")
        scanned, _ = scan_source_package(str(tmp_path))
        empty_file = next(sf for sf in scanned if sf.file_name == "empty.pdf")
        assert empty_file.scan_status == "flagged"
        assert "Zero-byte" in empty_file.warning

    def test_recursive_scan(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "root_file.md").write_text("root")
        (sub / "sub_file.pdf").write_text("sub")
        scanned, _ = scan_source_package(str(tmp_path), recursive=True)
        assert len(scanned) == 2
        names = {sf.file_name for sf in scanned}
        assert "root_file.md" in names
        assert "sub_file.pdf" in names

    def test_non_recursive_scan(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "root_file.md").write_text("root")
        (sub / "sub_file.pdf").write_text("sub")
        scanned, _ = scan_source_package(str(tmp_path), recursive=False)
        names = {sf.file_name for sf in scanned}
        assert "root_file.md" in names
        assert "sub_file.pdf" not in names


# ── Document Classification Tests ──────────────────────────────────────────────


class TestDocumentClassifier:
    """Tests for document classification from filename/path."""

    @pytest.fixture
    def scanned_files(self):
        """Create a list of scanned files for classification testing."""
        return [
            ScannedFile(file_id="F1", file_name="IFU_final.pdf", source_path="/pkg/IFU_final.pdf",
                        relative_path="IFU_final.pdf", extension=".pdf", size_bytes=1000,
                        modified_time=None, scan_status="ok", warning=None),
            ScannedFile(file_id="F2", file_name="CER_draft.md", source_path="/pkg/CER_draft.md",
                        relative_path="CER_draft.md", extension=".md", size_bytes=500,
                        modified_time=None, scan_status="ok", warning=None),
            ScannedFile(file_id="F3", file_name="Risk_Analysis.docx", source_path="/pkg/Risk_Analysis.docx",
                        relative_path="Risk_Analysis.docx", extension=".docx", size_bytes=800,
                        modified_time=None, scan_status="ok", warning=None),
            ScannedFile(file_id="F4", file_name="PMCF_Plan_final.docx", source_path="/pkg/PMCF_Plan_final.docx",
                        relative_path="PMCF_Plan_final.docx", extension=".docx", size_bytes=700,
                        modified_time=None, scan_status="ok", warning=None),
            ScannedFile(file_id="F5", file_name="Equivalence_Table.xlsx", source_path="/pkg/Equivalence_Table.xlsx",
                        relative_path="Equivalence_Table.xlsx", extension=".xlsx", size_bytes=900,
                        modified_time=None, scan_status="ok", warning=None),
            ScannedFile(file_id="F6", file_name="random_notes.txt", source_path="/pkg/random_notes.txt",
                        relative_path="random_notes.txt", extension=".txt", size_bytes=100,
                        modified_time=None, scan_status="ok", warning=None),
        ]

    def test_ifu_classified(self, scanned_files):
        candidates = classify_document_candidates([scanned_files[0]])
        assert candidates[0].document_type == "ifu"
        assert candidates[0].confidence >= 0.9
        assert candidates[0].version_status == "final"

    def test_cer_classified(self, scanned_files):
        candidates = classify_document_candidates(scanned_files)
        cer_cand = next(c for c in candidates if c.file_id == "F2")
        assert cer_cand.document_type == "cer"
        assert cer_cand.confidence >= 0.9
        assert cer_cand.version_status == "draft"

    def test_risk_analysis_classified(self, scanned_files):
        candidates = classify_document_candidates(scanned_files)
        risk_cand = next(c for c in candidates if c.file_id == "F3")
        assert risk_cand.document_type in ("risk_related", "rmf")
        assert risk_cand.confidence >= 0.7

    def test_pmcf_classified(self, scanned_files):
        candidates = classify_document_candidates(scanned_files)
        pmcf_cand = next(c for c in candidates if c.file_id == "F4")
        assert pmcf_cand.document_type == "pmcf"
        assert pmcf_cand.confidence >= 0.9

    def test_equivalence_classified(self, scanned_files):
        candidates = classify_document_candidates(scanned_files)
        equiv_cand = next(c for c in candidates if c.file_id == "F5")
        assert equiv_cand.document_type == "equivalence"
        assert equiv_cand.confidence >= 0.7

    def test_unknown_classified(self, scanned_files):
        candidates = classify_document_candidates(scanned_files)
        unknown_cand = next(c for c in candidates if c.file_id == "F6")
        assert unknown_cand.document_type == "unknown"
        assert unknown_cand.confidence < 0.3
        assert unknown_cand.requires_human_confirmation is True

    def test_generated_artifact_lowered_confidence(self, tmp_path):
        # File inside "artifacts" directory should have lowered true-source confidence
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        (artifacts_dir / "CER_final.pdf").write_text("content")
        scanned, _ = scan_source_package(str(tmp_path))
        candidates = classify_document_candidates(scanned)
        cer_cand = next(c for c in candidates if c.file_id == scanned[0].file_id)
        assert cer_cand.is_true_source_candidate is False  # in artifacts/

    def test_final_in_filename_true_source(self, scanned_files):
        # File with "final" in name AND in a source directory
        sf = ScannedFile(file_id="F-test", file_name="CER_approved_final.pdf",
                         source_path="/project/source/CER_approved_final.pdf",
                         relative_path="source/CER_approved_final.pdf",
                         extension=".pdf", size_bytes=1000,
                         modified_time=None, scan_status="ok", warning=None)
        candidates = classify_document_candidates([sf])
        assert candidates[0].version_status == "final"
        assert candidates[0].is_true_source_candidate is True


# ── Source Documents Builder Tests ─────────────────────────────────────────────


class TestSourceDocumentsBuilder:
    """Tests for building SourceDocument array from classification."""

    def test_builds_from_candidates(self):
        candidates = [
            ClassificationCandidate(
                file_id="F1", document_type="ifu", confidence=0.95,
                matched_keywords=["ifu"], reason="matched ifu",
                requires_human_confirmation=False, is_true_source_candidate=True,
                version_status="final", notes=None,
            ),
            ClassificationCandidate(
                file_id="F2", document_type="cer", confidence=0.5,
                matched_keywords=["cer"], reason="matched cer",
                requires_human_confirmation=True, is_true_source_candidate=False,
                version_status="draft", notes=None,
            ),
        ]
        scanned = [
            ScannedFile(file_id="F1", file_name="IFU.pdf", source_path="/pkg/IFU.pdf",
                        relative_path="IFU.pdf", extension=".pdf", size_bytes=1000,
                        modified_time=None, scan_status="ok", warning=None),
            ScannedFile(file_id="F2", file_name="CER.pdf", source_path="/pkg/CER.pdf",
                        relative_path="CER.pdf", extension=".pdf", size_bytes=1000,
                        modified_time=None, scan_status="ok", warning=None),
        ]
        docs = build_source_documents_from_candidates(candidates, scanned)
        assert len(docs) == 2
        ifu_doc = next(d for d in docs if d.document_type == "ifu")
        assert ifu_doc.is_true_source is True
        assert ifu_doc.version_status == "TRUE_SOURCE"
        cer_doc = next(d for d in docs if d.document_type == "cer")
        # confidence=0.5 is >= 0.5 threshold → "available"
        assert cer_doc.availability == "available"

    def test_unknown_type_no_document_type(self):
        candidates = [
            ClassificationCandidate(
                file_id="F1", document_type="unknown", confidence=0.1,
                matched_keywords=[], reason="no match",
                requires_human_confirmation=True, is_true_source_candidate=False,
                version_status="unknown", notes=None,
            ),
        ]
        scanned = [
            ScannedFile(file_id="F1", file_name="unknown.bin", source_path="/pkg/unknown.bin",
                        relative_path="unknown.bin", extension=".bin", size_bytes=1000,
                        modified_time=None, scan_status="flagged", warning="unsupported"),
        ]
        docs = build_source_documents_from_candidates(candidates, scanned)
        assert docs[0].document_type is None  # unknown maps to None


# ── Source Status Deriver Tests ─────────────────────────────────────────────────


class TestSourceStatusDeriver:
    """Tests for deriving source availability flags from classification."""

    def test_ifu_available_when_ifu_present(self):
        candidates = [
            ClassificationCandidate(file_id="F1", document_type="ifu", confidence=0.95,
                                    matched_keywords=["ifu"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
        ]
        status, warnings = derive_source_status(candidates)
        assert status.ifu_available is True

    def test_ifu_not_available_when_missing(self):
        candidates = [
            ClassificationCandidate(file_id="F1", document_type="cer", confidence=0.9,
                                    matched_keywords=["cer"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=False, version_status="draft"),
        ]
        status, warnings = derive_source_status(candidates)
        assert status.ifu_available is False

    def test_cer_available_for_cep(self):
        candidates = [
            ClassificationCandidate(file_id="F1", document_type="cep", confidence=0.9,
                                    matched_keywords=["cep"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
        ]
        status, warnings = derive_source_status(candidates)
        assert status.cer_available is True

    def test_rmf_available_when_risk_related_present(self):
        candidates = [
            ClassificationCandidate(file_id="F1", document_type="risk_related", confidence=0.85,
                                    matched_keywords=["risk"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=False, version_status="draft"),
        ]
        status, warnings = derive_source_status(candidates)
        assert status.risk_related_source_available is True

    def test_warns_when_rmf_missing(self):
        candidates = [
            ClassificationCandidate(file_id="F1", document_type="ifu", confidence=0.95,
                                    matched_keywords=["ifu"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
            ClassificationCandidate(file_id="F2", document_type="cer", confidence=0.9,
                                    matched_keywords=["cer"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=False, version_status="draft"),
        ]
        status, warnings = derive_source_status(candidates)
        assert status.rmf_available is False
        assert any("RMF" in w for w in warnings)

    def test_all_nine_flags_present(self):
        candidates = [
            ClassificationCandidate(file_id="F1", document_type="ifu", confidence=0.95,
                                    matched_keywords=["ifu"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
            ClassificationCandidate(file_id="F2", document_type="cer", confidence=0.9,
                                    matched_keywords=["cer"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=False, version_status="draft"),
            ClassificationCandidate(file_id="F3", document_type="rmf", confidence=0.9,
                                    matched_keywords=["rmf"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
            ClassificationCandidate(file_id="F4", document_type="equivalence", confidence=0.8,
                                    matched_keywords=["equiv"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=False, version_status="final"),
            ClassificationCandidate(file_id="F5", document_type="pmcf", confidence=0.9,
                                    matched_keywords=["pmcf"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
            ClassificationCandidate(file_id="F6", document_type="pms", confidence=0.85,
                                    matched_keywords=["pms"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
            ClassificationCandidate(file_id="F7", document_type="gspr", confidence=0.9,
                                    matched_keywords=["gspr"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
            ClassificationCandidate(file_id="F8", document_type="sscp", confidence=0.9,
                                    matched_keywords=["sscp"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
        ]
        status, _ = derive_source_status(candidates)
        assert status.ifu_available is True
        assert status.cer_available is True
        assert status.rmf_available is True
        assert status.risk_related_source_available is True
        assert status.equivalence_available is True
        assert status.pmcf_available is True
        assert status.pms_available is True
        assert status.gspr_available is True
        assert status.sscp_available is True


# ── Available Source Request Builder Tests ──────────────────────────────────────


class TestAvailableSourceRequestBuilder:
    """Tests for building available-source workflow request."""

    def test_request_has_boundary_flags_false(self):
        status = SourceStatusOut(
            ifu_available=True, cer_available=True, rmf_available=False,
            risk_related_source_available=False, equivalence_available=True,
            pmcf_available=True, pms_available=False, gspr_available=False, sscp_available=False,
        )
        docs = []
        request, warnings = build_available_source_request(
            "TEST_PROJECT", "Test Project", "/test/path", status, docs
        )
        assert request["official_cear_allowed"] is False
        assert request["final_regulatory_decision_allowed"] is False
        assert request["production_claim_allowed"] is False

    def test_request_workflow_mode_set(self):
        status = SourceStatusOut()
        docs = []
        request, _ = build_available_source_request(
            "TEST_PROJECT", "Test Project", "/test/path", status, docs
        )
        assert request["workflow_mode"] == "AVAILABLE_SOURCE_LIMITED"

    def test_request_includes_review_scope(self):
        status = SourceStatusOut()
        docs = []
        request, _ = build_available_source_request(
            "TEST_PROJECT", "Test Project", "/test/path", status, docs
        )
        assert "source_inventory" in request["review_scope"]
        assert "ifu_cer_linkage" in request["review_scope"]
        assert "equivalence_workbench" in request["review_scope"]
        assert "pmcf_linkage_workbench" in request["review_scope"]
        assert "reviewer_packet" in request["review_scope"]

    def test_request_includes_source_status(self):
        status = SourceStatusOut(
            ifu_available=True, cer_available=False, rmf_available=False,
            risk_related_source_available=False, equivalence_available=False,
            pmcf_available=False, pms_available=False, gspr_available=False, sscp_available=False,
        )
        docs = []
        request, _ = build_available_source_request(
            "TEST_PROJECT", "Test Project", "/test/path", status, docs
        )
        assert request["ifu_available"] is True
        assert request["cer_available"] is False

    def test_request_includes_source_documents(self):
        status = SourceStatusOut()
        docs = []
        request, _ = build_available_source_request(
            "TEST_PROJECT", "Test Project", "/test/path", status, docs
        )
        assert "source_documents" in request
        assert isinstance(request["source_documents"], list)


# ── Human Confirmation Packet Tests ─────────────────────────────────────────────


class TestHumanConfirmationPacket:
    """Tests for human confirmation packet generation."""

    def test_packet_has_non_claims(self):
        candidates = [
            ClassificationCandidate(file_id="F1", document_type="ifu", confidence=0.95,
                                    matched_keywords=["ifu"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
        ]
        scanned = [
            ScannedFile(file_id="F1", file_name="IFU.pdf", source_path="/pkg/IFU.pdf",
                        relative_path="IFU.pdf", extension=".pdf", size_bytes=1000,
                        modified_time=None, scan_status="ok", warning=None),
        ]
        docs = build_source_documents_from_candidates(candidates, scanned)
        status, _ = derive_source_status(candidates)
        request, _ = build_available_source_request("TEST", "Test", "/pkg", status, docs)
        packet = build_human_confirmation_packet("TEST", "Test", "/pkg", scanned, candidates, docs, status, request, [])

        assert "official_cear_allowed" in packet.non_claims
        assert packet.non_claims["official_cear_allowed"].startswith("FALSE")
        assert packet.non_claims["final_regulatory_decision_allowed"].startswith("FALSE")
        assert packet.non_claims["production_claim_allowed"].startswith("FALSE")
        assert "NOT executed" in packet.non_claims["obsidian_backflow"]
        assert "NOT executed" in packet.non_claims["nocodb_backflow"]

    def test_packet_recommends_hold_when_core_sources_missing(self):
        candidates = [
            ClassificationCandidate(file_id="F1", document_type="unknown", confidence=0.1,
                                    matched_keywords=[], reason="", requires_human_confirmation=True,
                                    is_true_source_candidate=False, version_status="unknown"),
        ]
        scanned = [
            ScannedFile(file_id="F1", file_name="unknown.bin", source_path="/pkg/unknown.bin",
                        relative_path="unknown.bin", extension=".bin", size_bytes=1000,
                        modified_time=None, scan_status="ok", warning=None),
        ]
        docs = build_source_documents_from_candidates(candidates, scanned)
        status, _ = derive_source_status(candidates)
        request, _ = build_available_source_request("TEST", "Test", "/pkg", status, docs)
        packet = build_human_confirmation_packet("TEST", "Test", "/pkg", scanned, candidates, docs, status, request, [])

        assert "HOLD" in packet.status
        assert any("IFU" in a for a in packet.recommended_actions)

    def test_packet_counts_high_low_confidence(self):
        candidates = [
            ClassificationCandidate(file_id="F1", document_type="ifu", confidence=0.95,
                                    matched_keywords=["ifu"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=True, version_status="final"),
            ClassificationCandidate(file_id="F2", document_type="unknown", confidence=0.1,
                                    matched_keywords=[], reason="", requires_human_confirmation=True,
                                    is_true_source_candidate=False, version_status="unknown"),
            ClassificationCandidate(file_id="F3", document_type="cer", confidence=0.85,
                                    matched_keywords=["cer"], reason="", requires_human_confirmation=False,
                                    is_true_source_candidate=False, version_status="draft"),
        ]
        scanned = [
            ScannedFile(file_id="F1", file_name="IFU.pdf", source_path="/pkg/IFU.pdf",
                        relative_path="IFU.pdf", extension=".pdf", size_bytes=1000,
                        modified_time=None, scan_status="ok", warning=None),
            ScannedFile(file_id="F2", file_name="unknown.bin", source_path="/pkg/unknown.bin",
                        relative_path="unknown.bin", extension=".bin", size_bytes=1000,
                        modified_time=None, scan_status="ok", warning=None),
            ScannedFile(file_id="F3", file_name="CER.pdf", source_path="/pkg/CER.pdf",
                        relative_path="CER.pdf", extension=".pdf", size_bytes=1000,
                        modified_time=None, scan_status="ok", warning=None),
        ]
        docs = build_source_documents_from_candidates(candidates, scanned)
        status, _ = derive_source_status(candidates)
        request, _ = build_available_source_request("TEST", "Test", "/pkg", status, docs)
        packet = build_human_confirmation_packet("TEST", "Test", "/pkg", scanned, candidates, docs, status, request, [])

        assert packet.high_confidence_count == 2  # IFU=0.95, CER=0.85
        assert packet.low_confidence_count == 1  # unknown=0.1

    def test_packet_holds_for_empty_package(self):
        """Empty package (0 scanned files) must return HOLD, not READY_TO_RUN."""
        candidates: list[ClassificationCandidate] = []
        scanned: list[ScannedFile] = []
        docs: list[SourceDocumentOut] = []
        status = SourceStatusOut()
        # build_available_source_request still returns a dict (not None) for empty package
        request, _ = build_available_source_request("TEST", "Test", "/pkg", status, docs)
        packet = build_human_confirmation_packet(
            "TEST", "Test", "/pkg", scanned, candidates, docs, status, request, []
        )

        assert "HOLD" in packet.status
        assert "READY_TO_RUN" not in packet.status
        assert any(
            "at least one supported document" in a
            for a in packet.recommended_actions
        )
        assert any(
            "Do NOT run available-source workflow" in a
            for a in packet.recommended_actions
        )
        # non-claims still preserved
        assert packet.non_claims["official_cear_allowed"].startswith("FALSE")
        assert packet.non_claims["final_regulatory_decision_allowed"].startswith("FALSE")
        assert packet.non_claims["production_claim_allowed"].startswith("FALSE")


# ── Integration Test ─────────────────────────────────────────────────────────────


class TestFullPipeline:
    """Integration test for the full scan → classify → build pipeline."""

    def test_full_pipeline_produces_valid_request(self, tmp_path):
        # Setup: create a realistic source package
        (tmp_path / "CarioSense_IFU_final.pdf").write_text("ifu content")
        (tmp_path / "CarioSense_CER_draft.md").write_text("cer content")
        (tmp_path / "Equivalence_Table.xlsx").write_text("equiv content")

        # Scan
        scanned, scan_warn = scan_source_package(str(tmp_path))
        assert len(scanned) == 3

        # Classify
        candidates = classify_document_candidates(scanned)
        assert len(candidates) == 3

        # Build docs
        docs = build_source_documents_from_candidates(candidates, scanned)
        assert len(docs) == 3

        # Derive status
        status, status_warn = derive_source_status(candidates)
        assert status.ifu_available is True
        assert status.cer_available is True
        assert status.equivalence_available is True

        # Build request
        request, req_warn = build_available_source_request(
            "INTEGRATION_TEST", "Integration Test", str(tmp_path), status, docs
        )
        assert request["project_id"] == "INTEGRATION_TEST"
        assert request["official_cear_allowed"] is False
        assert request["final_regulatory_decision_allowed"] is False
        assert request["production_claim_allowed"] is False
        assert len(request["source_documents"]) == 3

        # Confirmation packet
        packet = build_human_confirmation_packet(
            "INTEGRATION_TEST", "Integration Test", str(tmp_path),
            scanned, candidates, docs, status, request, scan_warn + status_warn
        )
        assert packet.scanned_files_count == 3
        assert "FALSE" in packet.non_claims["official_cear_allowed"]
        assert packet.project_id == "INTEGRATION_TEST"
