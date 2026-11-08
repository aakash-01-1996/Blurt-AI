"use client";

import { useState } from "react";
import { apiFetch } from "../../lib/api";
import { PasskeysCard } from "../settings/PasskeysCard";
import { DeleteAccountCard } from "../settings/DeleteAccountCard";

export function SettingsPage({ token }: { token: string }) {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/export", token);
      if (!res.ok) {
        setError("Export failed — please try again.");
        return;
      }
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "blurt-export.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Export failed — check your connection.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="px-6 sm:px-10 lg:px-12 py-10 max-w-[760px]">
      <h1 className="font-display text-4xl font-bold text-[#1D1D1F]">Settings</h1>
      <p className="text-base text-gray-400 mt-1.5 mb-8">Your data stays yours.</p>

      <div className="bg-surface rounded-3xl p-6 border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)] flex flex-col gap-3">
        <h2 className="font-display text-xl font-bold text-[#1D1D1F]">Export your data</h2>
        <p className="text-sm text-gray-500 leading-relaxed">
          Download everything Blurt holds for you — recordings, transcripts, items, tasks and work
          log — as a single JSON file.
        </p>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="self-start text-[15px] font-bold px-4 py-2.5 rounded-xl bg-[#1D1D1F] text-white hover:bg-[#2d2f36] transition disabled:opacity-50"
        >
          {exporting ? "Exporting…" : "Export my data"}
        </button>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      <PasskeysCard token={token} />

      <p className="text-sm text-gray-400 mt-5">
        To delete a recording and everything derived from it, use the trash icon next to it on the
        Record screen.
      </p>

      <DeleteAccountCard token={token} />
    </div>
  );
}
