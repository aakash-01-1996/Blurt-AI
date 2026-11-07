import { clearToken } from "../hooks/useAuth";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message?: string) {
    super(message ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Authenticated fetch for the Blurt API.
 *
 * Attaches the bearer token and, on a 401, clears the stored token so the app
 * drops back to the login screen instead of silently rendering broken pages
 * with an expired session. Callers handle the thrown ApiError as a normal
 * failure; the redirect to login happens via the auth store re-render.
 */
export async function apiFetch(
  path: string,
  token: string | null,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(path, { ...init, headers });

  if (res.status === 401) {
    clearToken();
    throw new ApiError(401, "Session expired");
  }
  return res;
}
