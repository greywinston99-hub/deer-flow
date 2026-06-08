"use client";

import { useState, useCallback } from "react";
import type { SlotWorkbenchBuildResponse, SourceSlot } from "@/core/cer_auth/v5_types";
import {
  buildSlotWorkbench,
  getSlotWorkbench,
  confirmSlot,
  reselectSlot,
  markSlotMissing,
  markOpenFileCheck,
} from "@/core/cer_auth/v5_api";

export interface UseSourceSlotWorkbenchReturn {
  slots: SourceSlot[];
  workbenchId: string | null;
  loading: boolean;
  error: string | null;
  build: (projectId: string, familyGroups: Record<string, unknown>[]) => Promise<SlotWorkbenchBuildResponse | null>;
  refresh: (projectId: string, workbenchId: string) => Promise<{ slot_workbench_id: string; slots: SourceSlot[] } | null>;
  confirm: (projectId: string, slotId: string, fileId: string) => Promise<void>;
  reselect: (projectId: string, slotId: string, fileId: string, reason: string) => Promise<void>;
  markMissing: (projectId: string, slotId: string, reason: string) => Promise<void>;
  markOpenFile: (projectId: string, slotId: string, fileIds: string[], reason: string) => Promise<void>;
}

export function useSourceSlotWorkbench(): UseSourceSlotWorkbenchReturn {
  const [slots, setSlots] = useState<SourceSlot[]>([]);
  const [workbenchId, setWorkbenchId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const build = useCallback(async (projectId: string, familyGroups: Record<string, unknown>[]) => {
    setLoading(true);
    setError(null);
    try {
      const res = await buildSlotWorkbench(projectId, familyGroups);
      setSlots(res.slots ?? []);
      setWorkbenchId(res.slot_workbench_id ?? null);
      return res;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async (projectId: string, wbId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getSlotWorkbench(projectId, wbId);
      setSlots(res.slots ?? []);
      return { slot_workbench_id: res.slot_workbench_id, slots: res.slots ?? [] };
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const confirm = useCallback(async (projectId: string, slotId: string, fileId: string) => {
    if (!workbenchId) return;
    setLoading(true);
    try {
      await confirmSlot(projectId, workbenchId, slotId, fileId);
      setSlots((prev) =>
        prev.map((s) =>
          s.slot_id === slotId ? { ...s, slot_status: "CONFIRMED" as const, confirmed_file_id: fileId } : s
        )
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [workbenchId]);

  const reselect = useCallback(async (projectId: string, slotId: string, fileId: string, reason: string) => {
    if (!workbenchId) return;
    setLoading(true);
    try {
      await reselectSlot(projectId, workbenchId, slotId, fileId, reason);
      setSlots((prev) =>
        prev.map((s) =>
          s.slot_id === slotId ? { ...s, slot_status: "RESELECTED" as const, recommended_canonical_file_id: fileId } : s
        )
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [workbenchId]);

  const markMissing = useCallback(async (projectId: string, slotId: string, reason: string) => {
    if (!workbenchId) return;
    setLoading(true);
    try {
      await markSlotMissing(projectId, workbenchId, slotId, reason);
      setSlots((prev) =>
        prev.map((s) =>
          s.slot_id === slotId ? { ...s, slot_status: "MISSING" as const, missing_reason: reason } : s
        )
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [workbenchId]);

  const markOpenFile = useCallback(async (projectId: string, slotId: string, fileIds: string[], reason: string) => {
    if (!workbenchId) return;
    setLoading(true);
    try {
      await markOpenFileCheck(projectId, workbenchId, slotId, fileIds, reason);
      setSlots((prev) =>
        prev.map((s) =>
          s.slot_id === slotId ? { ...s, slot_status: "OPEN_FILE_CHECK" as const } : s
        )
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [workbenchId]);

  return {
    slots,
    workbenchId,
    loading,
    error,
    build,
    refresh,
    confirm,
    reselect,
    markMissing,
    markOpenFile,
  };
}
