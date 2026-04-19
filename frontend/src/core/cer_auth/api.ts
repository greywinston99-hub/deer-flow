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

/** Builds X-CER-* headers from localStorage dev session. Empty if dev mode not active. */
function buildCERAuthHeaders(): HeadersInit {
  const headers: Record<string, string> = {};
  if (typeof window === "undefined") return headers;
  if (!DEV_ROLE_OPTIONS.some((o) => o.value === localStorage.getItem(DEV_ROLE_KEY))) return headers;
  const role = localStorage.getItem(DEV_ROLE_KEY);
  const userId = localStorage.getItem(DEV_USER_ID_KEY);
  const userName = localStorage.getItem(DEV_USER_NAME_KEY);
  if (userId) headers["X-CER-User-ID"] = userId;
  if (userName) headers["X-CER-User-Name"] = userName;
  if (role) headers["X-CER-User-Role"] = role;
  return headers;
}

/**
 * Dev-mode-aware fetch wrapper for /api/cer-review/* calls.
 * Injects X-CER-* headers when a dev role is set in localStorage.
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
