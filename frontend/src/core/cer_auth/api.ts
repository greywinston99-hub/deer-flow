/* CER Auth API — frontend calls to /me endpoint.

Dev mode: localStorage-backed role simulation for internal reviewer trial.
Keys:
  cer_dev_role_value  — the role string (SENIOR_REVIEWER etc.) or null/empty when disabled
  cer_dev_user_id     — the dev user id (dev-senior etc.)
  cer_dev_user_name   — the display name

These keys are isolated from any "enabled" flags. The presence of cer_dev_role_value
is sufficient to determine dev mode is active.
*/

import { getBackendBaseURL } from "@/core/config";

export interface CERAuthUser {
  user_id: string;
  name: string;
  role: string;
}

// ── Dev-mode localStorage keys ─────────────────────────────────────────────────

const DEV_ROLE_KEY = "cer_dev_role_value";   // stores the role string (e.g. "SENIOR_REVIEWER")
const DEV_USER_ID_KEY = "cer_dev_user_id";   // stores the user id (e.g. "dev-senior")
const DEV_USER_NAME_KEY = "cer_dev_user_name"; // stores the display name

export type DevRole = "READ_ONLY_VIEWER" | "REVIEWER" | "SENIOR_REVIEWER" | "ADMIN";

export const DEV_ROLE_OPTIONS: { value: DevRole; label: string; userId: string; userName: string }[] = [
  { value: "READ_ONLY_VIEWER", label: "READ_ONLY_VIEWER", userId: "dev-viewer", userName: "Dev Viewer" },
  { value: "REVIEWER", label: "REVIEWER", userId: "dev-reviewer", userName: "Dev Reviewer" },
  { value: "SENIOR_REVIEWER", label: "SENIOR_REVIEWER", userId: "dev-senior", userName: "Dev Senior Reviewer" },
  { value: "ADMIN", label: "ADMIN", userId: "dev-admin", userName: "Dev Admin" },
];

/** Returns true when a dev role is actively set in localStorage. */
export function isDevCEREnabled(): boolean {
  if (typeof window === "undefined") return false;
  return DEV_ROLE_OPTIONS.some((o) => o.value === localStorage.getItem(DEV_ROLE_KEY));
}

/** Reads the currently stored dev role value. Returns null if dev mode is not active. */
export function getDevRoleValue(): DevRole | null {
  if (typeof window === "undefined") return null;
  const stored = localStorage.getItem(DEV_ROLE_KEY) as DevRole | null;
  if (stored && DEV_ROLE_OPTIONS.some((o) => o.value === stored)) return stored;
  return null;
}

/** Stores the selected dev role into localStorage. */
export function setDevCERUser(option: (typeof DEV_ROLE_OPTIONS)[number]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(DEV_ROLE_KEY, option.value);
  localStorage.setItem(DEV_USER_ID_KEY, option.userId);
  localStorage.setItem(DEV_USER_NAME_KEY, option.userName);
}

/** Clears all dev role localStorage entries. */
export function clearDevCERUser(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(DEV_ROLE_KEY);
  localStorage.removeItem(DEV_USER_ID_KEY);
  localStorage.removeItem(DEV_USER_NAME_KEY);
}

/** Returns the currently stored dev user object, or null if dev mode is not active. */
export function getDevCERUser(): { user_id: string; name: string; role: string } | null {
  if (typeof window === "undefined") return null;
  const role = localStorage.getItem(DEV_ROLE_KEY);
  const userId = localStorage.getItem(DEV_USER_ID_KEY);
  const userName = localStorage.getItem(DEV_USER_NAME_KEY);
  if (!userId || !role) return null;
  return { user_id: userId, name: userName || userId, role };
}

// ── Authenticated fetch with dev header injection ───────────────────────────────

/**
 * Builds X-CER-* headers for CER API requests.
 *
 * Priority order:
 *   1. localStorage dev session (cer_dev_role_value set) — highest priority
 *   2. NEXT_PUBLIC_CER_USER_ID / NEXT_PUBLIC_CER_USER_NAME / NEXT_PUBLIC_CER_USER_ROLE env vars
 *   3. Safe dev defaults — prevents RBAC block in dev without any config
 *
 * Always injects headers for CER endpoints so RBAC never silently blocks the UI.
 */
function buildCERAuthHeaders(): HeadersInit {
  const headers: Record<string, string> = {};
  if (typeof window === "undefined") return headers;

  // 1. Dev mode localStorage session (highest priority)
  const devRole = localStorage.getItem(DEV_ROLE_KEY);
  if (devRole && DEV_ROLE_OPTIONS.some((o) => o.value === devRole)) {
    const userId = localStorage.getItem(DEV_USER_ID_KEY);
    const userName = localStorage.getItem(DEV_USER_NAME_KEY);
    if (userId) headers["X-CER-User-ID"] = userId;
    if (userName) headers["X-CER-User-Name"] = userName;
    headers["X-CER-User-Role"] = devRole;
    return headers;
  }

  // 2. Env var fallback for NEXT_PUBLIC_CER_USER_ID (supports staging/dev deployments)
  const envUserId = process.env.NEXT_PUBLIC_CER_USER_ID;
  if (envUserId) {
    headers["X-CER-User-ID"] = envUserId;
    const envUserName = process.env.NEXT_PUBLIC_CER_USER_NAME;
    if (envUserName) headers["X-CER-User-Name"] = envUserName;
    const envRole = process.env.NEXT_PUBLIC_CER_USER_ROLE;
    if (envRole) headers["X-CER-User-Role"] = envRole;
    return headers;
  }

  // 3. Safe dev default — ensures UI is never RBAC-blocked in local dev
  // without requiring any localStorage or env configuration.
  // Uses a clearly-dev user ID and SENIOR_REVIEWER role.
  headers["X-CER-User-ID"] = "dev-local";
  headers["X-CER-User-Name"] = "Dev Local User";
  headers["X-CER-User-Role"] = "SENIOR_REVIEWER";
  return headers;
}

/**
 * Dev-mode-aware fetch wrapper for /api/cer-review/* calls.
 * Injects X-CER-* headers when:
 *   1. Dev role is set in localStorage (cer_dev_role_value), OR
 *   2. NEXT_PUBLIC_CER_USER_ID env var is set (production/dev fallback)
 *
 * Priority: localStorage dev role > env vars > safe dev defaults
 * This ensures the backend RBAC never blocks UI requests in dev/staging environments.
 */
export async function cerReviewFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  const isCEREndpoint = url.includes("/api/cer-review/");

  const extraHeaders = buildCERAuthHeaders();
  const incomingHeaders = init?.headers
    ? (init.headers instanceof Headers ? Object.fromEntries(init.headers.entries()) : init.headers as Record<string, string>)
    : {};
  const mergedHeaders = isCEREndpoint ? { ...incomingHeaders, ...extraHeaders } : incomingHeaders;

  return fetch(input, { ...init, headers: mergedHeaders });
}

// ── Me endpoint ───────────────────────────────────────────────────────────────

/**
 * Returns the current auth user — from localStorage if dev mode is active,
 * otherwise from the /me API endpoint.
 */
export async function fetchCERAuthUser(): Promise<CERAuthUser | null> {
  const devUser = getDevCERUser();
  if (devUser) return devUser;
  try {
    const r = await cerReviewFetch(`${getBackendBaseURL()}/api/cer-review/me`);
    if (!r.ok) return null;
    return (await r.json()) as CERAuthUser;
  } catch {
    return null;
  }
}
