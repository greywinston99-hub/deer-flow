/** V5 Adaptive Review Engine TypeScript Types */

export type ConfidenceBand = 'HIGH' | 'MEDIUM' | 'LOW' | 'MISSING';
export type SlotStatus = 'RECOMMENDED' | 'CONFIRMED' | 'RESELECTED' | 'MISSING' | 'OPEN_FILE_CHECK' | 'HOLD';
export type BlockingLevel = 'BLOCKING' | 'WARNING' | 'INFORMATIONAL';
export type GapType =
  | 'missing_source'
  | 'outdated_source'
  | 'unreadable_source'
  | 'large_file_not_read'
  | 'version_ambiguity'
  | 'missing_linkage'
  | 'rmf_gap'
  | 'pmcf_pms_gap'
  | 'gspr_sscp_gap'
  | 'equivalence_evidence_gap';
export type FlavorName = 'BALANCED' | 'STRICT' | 'FAST_GAP_TRIAGE' | 'NB_PREFERENCE';

export interface SourceFamilyCandidate {
  file_id: string;
  file_path: string;
  file_name: string;
  document_type: string;
  confidence_score: number;
  confidence_band: ConfidenceBand;
  file_size_bytes?: number;
  version_label?: string | null;
  evidence_ref?: string | null;
  readability_status?: string;
  integrity_status?: string;
  is_large_file?: boolean;
  is_unreadable?: boolean;
  is_duplicate?: boolean;
  is_companion?: boolean;
  negative_signals?: string[];
}

export interface SourceSlot {
  slot_id: string;
  slot_type: string;
  slot_status: SlotStatus;
  recommended_canonical_file_id: string | null;
  recommended_canonical_reason: string;
  confidence_score: number;
  confidence_band: ConfidenceBand;
  evidence_basis: string[];
  risk_flags: string[];
  integrity_status: string;
  readability_status: string;
  integrity_check_summary: string;
  direct_evidence_link?: string | null;
  raw_candidate_count: number;
  primary_action_hint?: string | null;
  candidates: SourceFamilyCandidate[];
  alternatives: SourceFamilyCandidate[];
  companion_files: SourceFamilyCandidate[];
  duplicate_files: SourceFamilyCandidate[];
  open_file_required: SourceFamilyCandidate[];
  missing_reason: string | null;
  reviewer_action_taken?: string | null;
  reviewer_action_at?: string | null;
  reviewer_action_by?: string | null;
  confirmed_file_id?: string | null;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
}

export interface ConfidenceHeatmapItem {
  slot_type: string;
  confidence_band: ConfidenceBand;
  confidence_score: number;
  candidate_count: number;
  recommendation_reason: string;
  evidence_basis: string[];
  risk_flags: string[];
  integrity_status: string;
  readability_status: string;
  negative_signals: string[];
}

export interface GPointItem {
  g_point_id: string;
  gap_type: GapType;
  topic: string;
  description: string;
  evidence_refs: string[];
  business_impact: string;
  blocking_level: BlockingLevel;
  recommended_action: string;
  responsible_role: string;
  reviewer_action?: string | null;
  reviewer_notes?: string | null;
  workflow_can_continue: string;
  controlled_hold_reason?: string | null;
  next_action?: string | null;
}

export interface CopilotSuggestion {
  suggestion_id: string;
  suggestion_type: string;
  text: string;
  evidence_refs: string[];
  staged_action?: {
    action_id: string;
    action_type: string;
    target_slot_id?: string;
    payload?: Record<string, unknown>;
  } | null;
  requires_human_confirmation: boolean;
}

export interface ReviewFlavorProfile {
  flavor_name: FlavorName;
  display_name: string;
  description: string;
  parameter_overrides: Record<string, unknown>;
  strictness_level: number;
  gap_sensitivity: number;
  confidence_threshold_adjustment: number;
}

export interface ExperienceEventDraft {
  event_id: string;
  event_type: string;
  project_id: string;
  original_state: Record<string, unknown>;
  corrected_state: Record<string, unknown>;
  context: Record<string, unknown>;
  captured_at: string;
  captured_by?: string | null;
  status: string;
  sandbox_only: boolean;
}

// Response types for API client
export interface SlotWorkbenchBuildResponse {
  slot_workbench_id: string;
  slots: SourceSlot[];
  heatmap: ConfidenceHeatmapItem[];
  non_claims: Record<string, unknown>[];
}

export interface GapAnalysisResponse {
  gap_analysis_id: string;
  g_points: GPointItem[];
  workflow_can_continue: string;
  next_actions: string[];
}

export interface CopilotDraftResponse {
  draft_id: string;
  suggestions: CopilotSuggestion[];
  evidence_refs: string[];
  boundary_notes: string[];
}

export interface BatchDraftResponse {
  batch_draft_id: string;
  staged_actions: unknown[];
  requires_confirmation: boolean;
  boundary_notes: string[];
}

export interface FeedbackCaptureResponse {
  event_id: string;
  status: string;
  sandbox_only: boolean;
}

export interface ShadowBacktestRunResponse {
  backtest_id: string;
  report: {
    backtest_id: string;
    before_recommendations: Record<string, unknown>[];
    after_recommendations: Record<string, unknown>[];
    changed_source_families: string[];
    confidence_band_shifts: Record<string, unknown>[];
    drift_risk_assessment: string;
    false_positive_risk: string;
    false_negative_risk: string;
    regression_risk: string;
    rollback_plan: string;
    sandbox_only: boolean;
    approval_required: boolean;
  } | null;
  sandbox_only: boolean;
  approval_required: boolean;
}

export interface V5ProjectSummary {
  project_id: string;
  latest_workbench_id: string;
  provenance: string;
  truth_anchor_id: string;
  updated_at: string;
  slot_count: number;
  heatmap_summary: Record<string, number>;
}

// ── P0-3: Review Feedback from Authoring interrupt payload ──

export type ReviewFeedbackSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFORMATIONAL";
export type ReviewFeedbackDepth = "PRIMARY_VERBATIM" | "PRIMARY_DERIVED" | "SECONDARY_SUMMARY" | "MISSING_PRIMARY";
export type ReviewFeedbackCategory =
  | "cross_doc_inconsistency"
  | "regulatory_boundary_violation"
  | "evidence_quality_gap"
  | "claim_evidence_mismatch"
  | "terminology_non_standard"
  | "format_degradation"
  | "missing_evidence"
  | "orphan_requirement"
  | "metadata_inconsistency";
export type ReviewReworkNode =
  | "device_profile"
  | "claim_decomposition"
  | "sota_search"
  | "evidence_appraisal"
  | "writer_synthesis"
  | "risk_gspr_mapping"
  | "cer_writing";

export interface ReviewFeedbackFinding {
  finding_id: string;
  severity: ReviewFeedbackSeverity;
  evidence_depth: ReviewFeedbackDepth;
  category: ReviewFeedbackCategory;
  target_claim_id?: string | null;
  target_evidence_id?: string | null;
  description: string;
  source_artifact?: string | null;
  suggested_rework_node?: ReviewReworkNode | null;
  rationale?: string | null;
}

export interface ReviewFeedbackPayload {
  advisory_only: true;
  finding_count: number;
  findings: ReviewFeedbackFinding[];
  message: string;
  feedback_actions_schema?: {
    description: string;
    actions: string[];
    example: Array<{ finding_id: string; action: string; note: string }>;
  };
}
