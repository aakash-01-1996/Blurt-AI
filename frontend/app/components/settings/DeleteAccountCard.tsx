"use client";

import { useState } from "react";
import { apiFetch } from "../../lib/api";
import { clearToken } from "../../hooks/useAuth";

export function DeleteAccountCard({ token }: { token: string }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/account", token, { method: "DELETE" });
      if (!res.ok) {
        setError("Could not delete your account — please try again.");
        setBusy(false);
        return;
      }
      // Account is gone; drop the token to return to the login screen.
      clearToken();
    } catch {
      setError("Could not delete your account — check your connection.");
      setBusy(false);
    }
  }

  return (
    <div className="bg-surface rounded-3xl p-6 border border-red-200 shadow-[0_1px_2px_rgba(0,0,0,0.04)] flex flex-col gap-3 mt-6">
      <h2 className="font-display text-xl font-bold text-red-700">Delete account</h2>

      {!confirming ? (
        <>
          <p className="text-sm text-gray-500 leading-relaxed">
            Permanently delete your account and all of your data.
          </p>
          <button
            onClick={() => {
              setError(null);
              setConfirming(true);
            }}
            className="self-start text-[15px] font-bold px-4 py-2.5 rounded-xl border border-red-300 text-red-700 hover:bg-red-50 transition"
          >
            Delete account
          </button>
        </>
      ) : (
        <>
          <p className="text-sm text-gray-700 leading-relaxed">
            You won&rsquo;t have access to your Blurts and your account will be deleted permanently.
            This can&rsquo;t be undone.
          </p>
          <div className="flex items-center gap-3">
            <button
              onClick={handleDelete}
              disabled={busy}
              className="text-[15px] font-bold px-4 py-2.5 rounded-xl bg-red-600 text-white hover:bg-red-700 transition disabled:opacity-50"
            >
              {busy ? "Deleting…" : "Yes, delete my account"}
            </button>
            <button
              onClick={() => setConfirming(false)}
              disabled={busy}
              className="text-[15px] font-semibold px-4 py-2.5 rounded-xl text-gray-600 hover:bg-gray-100 transition disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
