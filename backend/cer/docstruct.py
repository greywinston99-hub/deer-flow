"""CERDocStruct — CER Review Runtime Input Schema

This module defines the CERDocStruct, the unified input object for all downstream
CER review agents. It is produced by the cer_intake_agent (Step 1) and consumed
by all subsequent steps.

This is a SKELETON implementation per D1 Phase 1 scaffolding requirements.
NOT production code.

D0C Contract: CER_D0C_DOCSTRUCT_RUNTIME_CONTRACT_CLOSURE.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# Minimum required fields for CERDocStruct validation
REQUIRED_DOCSTRUCT_FIELDS = [
    "schema_name",
    "schema_version",
    "project_id",
    "cer_run_id",
    "document_inventory",
    "section_map",
    "intended_purpose",
    "evidence_source_index",
    "missing_or_weak_section_flags",
    "extraction_confidence",
    "source_traceability",
]


@dataclass
class DocumentInventoryEntry:
    """An entry in the document inventory."""
    inventory_id: str
    document_type: str  # cer|ifu|rmf|cep|pms|sccp|other
    file_ref: str
    sha256: str


@dataclass
class SourceDocuments:
    """Source document references."""
    cer: dict[str, str]  # path, sha256
    ifu: dict[str, str]  # path, sha256
    rmf: dict[str, str]  # path, sha256


@dataclass
class IntendedPurpose:
    """Intended purpose extraction."""
    extract: str
    pico: dict[str, str]  # population, intervention, comparator, outcome
    indications: list[str] = field(default_factory=list)
    contraindications: list[str] = field(default_factory=list)
    patient_population: str = ""
    intended_users: str = ""


@dataclass
class ClinicalClaim:
    """A clinical claim extracted from the CER."""
    claim_id: str
    claim_text: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class BenefitClaim:
    """A benefit claim extracted from the CER."""
    benefit_id: str
    benefit_text: str
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class EvidenceSource:
    """An evidence source indexed from the CER."""
    source_id: str
    source_type: str  # clinical_trial|literature|registry|post_market|equivalence|bench
    location: str
    text: str


@dataclass
class LiteratureBlockIndex:
    """Literature search block index."""
    databases: list[str] = field(default_factory=list)
    date_range: dict[str, str] = field(default_factory=dict)  # from, to
    total_results: int = 0
    included_studies: int = 0


@dataclass
class EquivalenceBlockIndex:
    """Equivalence demonstration block index."""
    predicate_device: str = ""
    technical_similarity: dict[str, bool] = field(default_factory=dict)
    biological_similarity: dict[str, bool] = field(default_factory=dict)
    clinical_similarity: dict[str, bool] = field(default_factory=dict)


@dataclass
class PMSPMCFBlockIndex:
    """PMS/PMCF block index."""
    uncertainties_addressed: list[str] = field(default_factory=list)
    planned_activities: list[str] = field(default_factory=list)


@dataclass
class BenefitRiskBlockIndex:
    """Benefit-risk block index."""
    residual_risks: list[str] = field(default_factory=list)
    benefit_risk_conclusion: str = ""


@dataclass
class RMFReferenceIndex:
    """RMF cross-reference index."""
    rmf_project_id: str = ""
    acpt_status: str = ""
    residual_risk_refs: list[str] = field(default_factory=list)


@dataclass
class IFUReferenceIndex:
    """IFU cross-reference index."""
    intended_purpose_match: bool = False
    contraindication_match: bool = False
    inconsistencies: list[str] = field(default_factory=list)


@dataclass
class CrossDocumentReferenceCandidate:
    """A cross-document reference candidate."""
    entity_type: str = ""
    cer_location: str = ""
    ifu_location: str = ""
    sscp_location: str = ""
    consistent: bool = False


@dataclass
class MissingOrWeakSectionFlag:
    """A flag for a missing or weak section."""
    section_id: str = ""
    section_name: str = ""
    flag_type: str = ""  # missing|empty|weak_content|inconsistent|unverifiable
    severity: str = ""  # critical|major|minor
    description: str = ""


@dataclass
class ExtractionConfidence:
    """Extraction confidence scores."""
    overall: float = 0.0
    per_field: dict[str, float] = field(default_factory=dict)


@dataclass
class SourceTraceability:
    """Source traceability metadata."""
    extractor: str = ""
    extracted_at: str = ""
    source_files: list[str] = field(default_factory=list)


@dataclass
class CERDocStruct:
    """Unified input object for CER Review Runtime.

    This is the primary input consumed by all downstream CER review agents.
    Produced by cer_intake_agent (Step 1).

    D0C Contract: CER_D0C_DOCSTRUCT_RUNTIME_CONTRACT_CLOSURE.md
    """

    schema_name: str = "cer_docstruct"
    schema_version: str = "v1"
    project_id: str = ""
    cer_run_id: str = ""

    # Document inventory
    document_inventory: list[DocumentInventoryEntry] = field(default_factory=list)
    source_documents: SourceDocuments | None = None

    # Section mapping
    section_map: dict[str, str] = field(default_factory=dict)

    # Intended purpose
    intended_purpose: IntendedPurpose | None = None

    # Claims
    clinical_claims: list[ClinicalClaim] = field(default_factory=list)
    benefit_claims: list[BenefitClaim] = field(default_factory=list)

    # Evidence index
    evidence_source_index: list[EvidenceSource] = field(default_factory=list)

    # Literature block
    literature_block_index: LiteratureBlockIndex | None = None

    # Equivalence block
    equivalence_block_index: EquivalenceBlockIndex | None = None

    # PMS/PMCF block
    pms_pmcf_block_index: PMSPMCFBlockIndex | None = None

    # Benefit-risk block
    benefit_risk_block_index: BenefitRiskBlockIndex | None = None

    # RMF reference
    rmf_reference_index: RMFReferenceIndex | None = None

    # IFU reference
    ifu_reference_index: IFUReferenceIndex | None = None

    # Cross-document references
    cross_document_reference_candidates: list[CrossDocumentReferenceCandidate] = field(default_factory=list)

    # Section flags
    missing_or_weak_section_flags: list[MissingOrWeakSectionFlag] = field(default_factory=list)

    # Confidence
    extraction_confidence: ExtractionConfidence | None = None

    # Traceability
    source_traceability: SourceTraceability | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "cer_run_id": self.cer_run_id,
            "document_inventory": [
                {"inventory_id": e.inventory_id, "document_type": e.document_type, "file_ref": e.file_ref, "sha256": e.sha256}
                for e in self.document_inventory
            ],
            "section_map": self.section_map,
            # Additional fields omitted for skeleton brevity
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CERDocStruct:
        """Create from dictionary."""
        # Skeleton implementation - full implementation in D1 Phase 2+
        return cls(
            schema_name=data.get("schema_name", "cer_docstruct"),
            schema_version=data.get("schema_version", "v1"),
            project_id=data.get("project_id", ""),
            cer_run_id=data.get("cer_run_id", ""),
        )


def validate_minimal_docstruct(docstruct: CERDocStruct) -> tuple[bool, list[str]]:
    """Validate minimum required fields are present.

    Returns:
        (is_valid, list of error messages)
    """
    errors = []

    for field_name in REQUIRED_DOCSTRUCT_FIELDS:
        if not hasattr(docstruct, field_name):
            errors.append(f"Missing required field: {field_name}")
        elif getattr(docstruct, field_name) is None:
            errors.append(f"Field is empty: {field_name}")
        elif isinstance(getattr(docstruct, field_name), list) and len(getattr(docstruct, field_name)) == 0:
            # Allow empty lists but warn
            pass

    return len(errors) == 0, errors
