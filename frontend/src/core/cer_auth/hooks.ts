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
  user: CERAuthUser;
  loading: boolean;
  canSubmitDecision: boolean;
  devMode: boolean;
  devRole: DevRole | null;
  setDevRole: (role: DevRole) => void;
  disableDevMode: () => void;
}

const GATE_DECISION_ROLES = new Set(["SENIOR_REVIEWER", "ADMIN"]);

// Default user used during SSR and as fallback to prevent hydration mismatch.
// During SSR, window is undefined so we use the default.
// On client hydration, this matches the server render.
// After hydration, useEffect may update to the real authenticated user.
const _DEFAULT_USER: CERAuthUser = {
  user_id: "dev-user",
  name: "Developer",
  role: "REVIEWER",
};

// Read initial auth state synchronously from localStorage.
// This runs before the first render so the first render already has the correct user.
// Returns a non-null default to prevent SSR/client hydration mismatch.
function _readInitialAuth(): { user: CERAuthUser; loading: boolean } {
  if (typeof window !== "undefined") {
    const devUser = getDevCERUser();
    if (devUser) return { user: devUser, loading: false };
  }
  return { user: _DEFAULT_USER, loading: false };
}

export function useCERAuth(): CERAuthState {
  const [{ user, loading }, setAuth] = useState<{ user: CERAuthUser; loading: boolean }>(
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
    if (!isDevCEREnabled()) {
      // Only fetch real auth when dev mode is OFF
      void fetchCERAuthUser().then((u) => {
        setAuth({ user: u ?? _DEFAULT_USER, loading: false });
      });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
    setAuth({ user: _DEFAULT_USER, loading: false });
    void fetchCERAuthUser().then((u) => {
      setAuth({ user: u ?? _DEFAULT_USER, loading: false });
    });
  }, []);

  const canSubmitDecision = GATE_DECISION_ROLES.has(user.role);

  return { user, loading, canSubmitDecision, devMode, devRole, setDevRole, disableDevMode };
}
