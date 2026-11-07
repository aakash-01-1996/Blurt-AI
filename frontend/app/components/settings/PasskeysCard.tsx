"use client";

import { useEffect, useState } from "react";
import { PasskeyCredential } from "../../types";
import { apiFetch } from "../../lib/api";
import { passkeysSupported, registerPasskey } from "../../lib/passkey";
import { formatDayLabel } from "../../lib/format";

/** A clean, human device name for a new passkey (never the legacy "MacIntel"). */
function deviceLabel(): string {
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  if (/iPhone/.test(ua)) return "iPhone";
  if (/iPad/.test(ua)) return "iPad";
  if (/Android/.test(ua)) return "Android";
  if (/Macintosh|Mac OS X/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows";
  if (/Linux/.test(ua)) return "Linux";
  return "This device";
}

export function PasskeysCard({ token }: { token: string }) {
  const [creds, setCreds] = useState<PasskeyCredential[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const res = await apiFetch("/api/v1/auth/passkey/credentials", token);
    if (res.ok) setCreds(await res.json());
  }

  useEffect(() => {
    let cancelled = false;
    apiFetch("/api/v1/auth/passkey/credentials", token)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => { if (!cancelled) setCreds(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [token]);

  async function add() {
    setError(null);
    if (!passkeysSupported()) {
      setError("This browser doesn't support passkeys.");
      return;
    }
    setBusy(true);
    try {
      await registerPasskey(token, deviceLabel());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add passkey");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    const prev = creds;
    setCreds((c) => c.filter((x) => x.id !== id));
    try {
      const res = await apiFetch(`/api/v1/auth/passkey/credentials/${id}`, token, {
        method: "DELETE",
      });
      if (!res.ok) setCreds(prev);
    } catch {
      setCreds(prev);
    }
  }

  return (
    <div className="bg-surface rounded-3xl p-6 border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)] flex flex-col gap-3 mt-6">
      <h2 className="font-display text-xl font-bold text-[#1D1D1F]">Passkeys</h2>
      <p className="text-sm text-gray-500 leading-relaxed">
        Sign in with Touch ID, Face ID or a security key instead of your password. Your password
        still works.
      </p>

      {creds.length > 0 && (
        <ul className="flex flex-col gap-2 my-1">
          {creds.map((c) => (
            <li
              key={c.id}
              className="flex items-center justify-between gap-4 rounded-xl border border-[#E5E5EA] px-4 py-3"
            >
              <div className="min-w-0">
                <p className="text-[15px] font-semibold text-[#1D1D1F] truncate">
                  {c.label || "Passkey"}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  Added {formatDayLabel(new Date(c.created_at))}
                  {c.last_used_at ? ` · last used ${formatDayLabel(new Date(c.last_used_at))}` : ""}
                </p>
              </div>
              <button
                onClick={() => remove(c.id)}
                className="shrink-0 text-sm font-semibold text-[#FF3B30] hover:underline"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <button
        onClick={add}
        disabled={busy}
        className="self-start text-[15px] font-bold px-4 py-2.5 rounded-xl bg-[#1D1D1F] text-white hover:bg-[#2d2f36] transition disabled:opacity-50"
      >
        {busy ? "Waiting for passkey…" : "Add a passkey"}
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
