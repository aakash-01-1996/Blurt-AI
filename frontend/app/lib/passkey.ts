import { startAuthentication, startRegistration } from "@simplewebauthn/browser";
import { apiFetch } from "./api";

/** True when this browser can do WebAuthn at all. */
export function passkeysSupported(): boolean {
  return typeof window !== "undefined" && !!window.PublicKeyCredential;
}

async function detail(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  return body?.detail ?? fallback;
}

/** Sign in with a passkey for `email`; resolves to a JWT access token. */
export async function loginWithPasskey(email: string): Promise<string> {
  const begin = await fetch("/api/v1/auth/passkey/login/begin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!begin.ok) throw new Error(await detail(begin, "No passkey found for this account"));
  const { options, challenge_token } = await begin.json();

  const credential = await startAuthentication({ optionsJSON: options });

  const complete = await fetch("/api/v1/auth/passkey/login/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential, challenge_token }),
  });
  if (!complete.ok) throw new Error(await detail(complete, "Passkey sign-in failed"));
  const body = await complete.json();
  return body.access_token as string;
}

/** Register a new passkey for the signed-in user. */
export async function registerPasskey(token: string, label?: string): Promise<void> {
  const begin = await apiFetch("/api/v1/auth/passkey/register/begin", token, {
    method: "POST",
  });
  if (!begin.ok) throw new Error(await detail(begin, "Could not start passkey registration"));
  const { options, challenge_token } = await begin.json();

  const credential = await startRegistration({ optionsJSON: options });

  const complete = await apiFetch("/api/v1/auth/passkey/register/complete", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential, challenge_token, label }),
  });
  if (!complete.ok) throw new Error(await detail(complete, "Passkey registration failed"));
}
