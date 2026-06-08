/** V5 Adaptive Review Engine API Client */

import { cerReviewFetch } from "./api";
import { getBackendBaseURL } from "@/core/config";
import type {
  BatchDraftResponse,
  ConfidenceHeatmapItem,
  CopilotDraftResponse,
  FeedbackCaptureResponse,
  GapAnalysisResponse,
  ShadowBacktestRunResponse,
  SlotWorkbenchBuildResponse,
  SourceSlot,
  V5ProjectSummary,
} from "./v5_types";

const BASE = () => `${getBackendBaseURL()}/api/cer-review/v5`;

// ── Project Listing ────────────────────────────────────────────────────────────

export async function listV5Projects(): Promise<{ projects: V5ProjectSummary[] }> {
  const r = await cerReviewFetch(`${BASE()}/projects`);
  if (!r.ok) throw new Error(`listV5Projects failed: ${r.status}`);
  return r.json();
}

// ── Slot Workbench ─────────────────────────────────────────────────────────────

export async function buildSlotWorkbench(
  projectId: string,
  sourceFamilyGroups: Record<string, unknown>[]
): Promise<SlotWorkbenchBuildResponse> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/slots/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_family_groups: sourceFamilyGroups }),
  });
  if (!r.ok) throw new Error(`buildSlotWorkbench failed: ${r.status}`);
  return r.json();
}

export async function getSlotWorkbench(projectId: string, workbenchId: string): Promise<{ slot_workbench_id: string; slots: SourceSlot[]; heatmap: ConfidenceHeatmapItem[]; generated_at: string }> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/slots/${workbenchId}`);
  if (!r.ok) throw new Error(`getSlotWorkbench failed: ${r.status}`);
  return r.json();
}

export async function confirmSlot(
  projectId: string,
  workbenchId: string,
  slotId: string,
  confirmedFileId: string,
  notes?: string
): Promise<unknown> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/slots/${workbenchId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_id: slotId, confirmed_file_id: confirmedFileId, confirmation_notes: notes }),
  });
  if (!r.ok) throw new Error(`confirmSlot failed: ${r.status}`);
  return r.json();
}

export async function reselectSlot(
  projectId: string,
  workbenchId: string,
  slotId: string,
  selectedFileId: string,
  reason: string
): Promise<unknown> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/slots/${workbenchId}/reselect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_id: slotId, selected_file_id: selectedFileId, reason }),
  });
  if (!r.ok) throw new Error(`reselectSlot failed: ${r.status}`);
  return r.json();
}

export async function markSlotMissing(
  projectId: string,
  workbenchId: string,
  slotId: string,
  missingReason: string
): Promise<unknown> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/slots/${workbenchId}/mark-missing`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_id: slotId, missing_reason: missingReason }),
  });
  if (!r.ok) throw new Error(`markSlotMissing failed: ${r.status}`);
  return r.json();
}

export async function markOpenFileCheck(
  projectId: string,
  workbenchId: string,
  slotId: string,
  fileIds: string[],
  checkReason: string
): Promise<unknown> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/slots/${workbenchId}/open-file-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_id: slotId, file_ids: fileIds, check_reason: checkReason }),
  });
  if (!r.ok) throw new Error(`markOpenFileCheck failed: ${r.status}`);
  return r.json();
}

// ── Confidence Heatmap ─────────────────────────────────────────────────────────

export async function getConfidenceHeatmap(projectId: string): Promise<{ project_id: string; heatmap: ConfidenceHeatmapItem[]; summary: Record<string, number> }> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/heatmap`);
  if (!r.ok) throw new Error(`getConfidenceHeatmap failed: ${r.status}`);
  return r.json();
}

// ── Latest Workbench Discovery ─────────────────────────────────────────────────

export async function getLatestWorkbench(
  projectId: string
): Promise<{
  workbench_id: string;
  slots: SourceSlot[];
  heatmap: ConfidenceHeatmapItem[];
  provenance: string;
  truth_anchor_id: string;
} | null> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/workbenches/latest`);
  if (!r.ok) {
    if (r.status === 404 || r.status === 409) {
      // 409 = HOLD (no workbench available), 404 = not found
      return null;
    }
    throw new Error(`getLatestWorkbench failed: ${r.status}`);
  }
  return r.json();
}

// ── G-Points ───────────────────────────────────────────────────────────────────

export async function analyzeGaps(projectId: string, workbenchId: string, flavorProfile?: string): Promise<GapAnalysisResponse> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/gaps/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_workbench_id: workbenchId, flavor_profile: flavorProfile }),
  });
  if (!r.ok) throw new Error(`analyzeGaps failed: ${r.status}`);
  return r.json();
}

// ── Copilot ────────────────────────────────────────────────────────────────────

export async function draftCopilotSuggestions(
  projectId: string,
  currentView: string,
  workbenchId?: string,
  gapAnalysisId?: string,
  reviewerQuestion?: string
): Promise<CopilotDraftResponse> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/copilot/draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_view: currentView, slot_workbench_id: workbenchId, gap_analysis_id: gapAnalysisId, reviewer_question: reviewerQuestion }),
  });
  if (!r.ok) throw new Error(`draftCopilotSuggestions failed: ${r.status}`);
  return r.json();
}

export async function draftBatchOperation(
  projectId: string,
  operation: string,
  workbenchId: string
): Promise<BatchDraftResponse> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/copilot/batch-draft`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operation, slot_workbench_id: workbenchId }),
  });
  if (!r.ok) throw new Error(`draftBatchOperation failed: ${r.status}`);
  return r.json();
}

// ── Flavor Profiles ────────────────────────────────────────────────────────────

export async function listFlavorProfiles(): Promise<{ profiles: unknown[] }> {
  const r = await cerReviewFetch(`${BASE()}/flavor-profiles`);
  if (!r.ok) throw new Error(`listFlavorProfiles failed: ${r.status}`);
  return r.json();
}

export async function selectFlavorProfile(projectId: string, flavorName: string): Promise<{ project_id: string; active_flavor: string; parameter_overrides: unknown }> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/flavor-profile/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ flavor_name: flavorName }),
  });
  if (!r.ok) throw new Error(`selectFlavorProfile failed: ${r.status}`);
  return r.json();
}

// ── Feedback ───────────────────────────────────────────────────────────────────

export async function captureFeedback(
  projectId: string,
  eventType: string,
  originalState: Record<string, unknown>,
  correctedState: Record<string, unknown>,
  context: Record<string, unknown>
): Promise<FeedbackCaptureResponse> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/feedback/capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_type: eventType, original_state: originalState, corrected_state: correctedState, context }),
  });
  if (!r.ok) throw new Error(`captureFeedback failed: ${r.status}`);
  return r.json();
}

// ── Shadow Backtest ────────────────────────────────────────────────────────────

export async function runShadowBacktest(
  projectId: string,
  workbenchId: string,
  parameterCandidates?: Record<string, unknown>
): Promise<ShadowBacktestRunResponse> {
  const r = await cerReviewFetch(`${BASE()}/${projectId}/shadow-backtest/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slot_workbench_id: workbenchId, parameter_candidates: parameterCandidates }),
  });
  if (!r.ok) throw new Error(`runShadowBacktest failed: ${r.status}`);
  return r.json();
}
