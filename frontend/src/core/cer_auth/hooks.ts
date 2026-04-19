"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchCERAuthUser,
  getDevCERUser,
  isDevCEREnabled,
  DEV_ROLE_OPTIONS,
  setDevCERUser,
  clearDevCERUser,
  type CERAuthUser,
  type DevRole,
} from "./api";

export interface CERAuthState {
  user: CERAuthUser | null;
  loading: boolean;
  canSubmitDecision: boolean;
  devMode: boolean;
  devRole: DevRole | null;
  setDevRole: (role: DevRole) => void;
  disableDevMode: () => void;
}

const GATE_DECISION_ROLES = new Set(["SENIOR_REVIEWER", "ADMIN"]);

// Read initial auth state synchronously from localStorage.
// This runs before the first render, so the first render already has the correct user.
function _readInitialAuth(): { user: CERAuthUser | null; loading: boolean } {
  if (typeof window !== "undefined") {
    const devUser = getDevCERUser();
    if (devUser) return { user: devUser, loading: false };
  }
  return { user: null, loading: true };
}

export function useCERAuth(): CERAuthState {
  const [{ user, loading }, setAuth] = useState<{ user: CERAuthUser | null; loading: boolean }>(
    _readInitialAuth,
  );

  // Re-derive devMode and devRole from localStorage on every render.
  const devMode = isDevCEREnabled();
  const devRole = (function () {
    if (typeof window === "undefined") return null;
    const stored = localStorage.getItem("cer_dev_role_value") as DevRole | null;
    return stored && DEV_ROLE_OPTIONS.some((o) => o.value === stored) ? stored : null;
  })();

  // Fetch from API once on mount if no dev user was found.
  useEffect(() => {
    if (user !== null) return; // already have dev user — no API call needed
    void fetchCERAuthUser().then((u) => {
      setAuth({ user: u, loading: false });
    });
  }, [user]);

  const setDevRole = useCallback((role: DevRole) => {
    const option = DEV_ROLE_OPTIONS.find((o) => o.value === role);
    if (!option) return;
    setDevCERUser(option);
    setAuth({
      user: { user_id: option.userId, name: option.userName, role: option.value },
      loading: false,
    });
  }, []);

  const disableDevMode = useCallback(() => {
    clearDevCERUser();
    setAuth({ user: null, loading: true });
    void fetchCERAuthUser().then((u) => {
      setAuth({ user: u, loading: false });
    });
  }, []);

  const canSubmitDecision = user ? GATE_DECISION_ROLES.has(user.role) : false;

  return { user, loading, canSubmitDecision, devMode, devRole, setDevRole, disableDevMode };
}
