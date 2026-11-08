"use client";

import { useState } from "react";
import { Item, SECTION_COLORS, SECTION_LABELS } from "../../types";
import { confidenceLabel } from "../../lib/derive";
import { FieldRows } from "./FieldRows";
import { Snippet } from "./Snippet";

interface ReviewItemCardProps {
  item: Item;
  ts: number;
  onReview: (id: string, action: "approve" | "reject") => void;
  onPatch: (id: string, fields: Record<string, string>) => Promise<void>;
  onRestore: (id: string) => void;
  onDismiss: (id: string) => void;
}

export function ReviewItemCard({
  item,
  ts,
  onReview,
  onPatch,
  onRestore,
  onDismiss,
}: ReviewItemCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const f = item.fields ?? {};
  const title = f.accomplishment ?? f.title ?? f.task ?? item.span_text;
  const conf = confidenceLabel(item.route_confidence);
  const missingImpact = item.section === "work_log" && !f.impact;
  const isList = item.section === "list";

  // Approved "new list" → inline confirmation row.
  if (isList && item.status === "approved") {
    const listName = f.name ?? f.title ?? "New list";
    const listItems = f.items ?? f.entries ?? null;
    return (
      <div className="bg-surface rounded-2xl px-5 py-4 flex items-center justify-between gap-3 border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
        <div className="flex items-center gap-3">
          <span className="w-6 h-6 rounded-full bg-[#E7F5EC] flex items-center justify-center shrink-0">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2.5 6l2.5 2.5L9.5 3.5" stroke="#2E8B57" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <p className="text-[15px] text-[#1D1D1F]">
            <span className="font-bold">New list created:</span> {listName}
            {listItems ? `, with ${listItems}` : ""}
          </p>
        </div>
        <button
          onClick={() => onDismiss(item.id)}
          className="text-sm font-bold text-[#0071E3] hover:underline underline-offset-2"
        >
          Undo
        </button>
      </div>
    );
  }

  const reviewed = item.status !== "pending";
  const rejected = item.status === "rejected";

  function startEdit() {
    setDraft(Object.fromEntries(Object.entries(item.fields ?? {}).map(([k, v]) => [k, String(v)])));
    setEditing(true);
  }
  async function saveEdit() {
    setSaving(true);
    try { await onPatch(item.id, draft); setEditing(false); }
    finally { setSaving(false); }
  }

  const approveLabel = missingImpact
    ? "Approve without impact"
    : item.section === "task"
      ? "Approve and add to calendar"
      : isList
        ? "Approve and create list"
        : "Approve";

  return (
    <div className={`bg-surface rounded-3xl p-6 flex flex-col gap-4 border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-opacity ${rejected ? "opacity-50" : ""}`}>
      <div className="flex items-center gap-2.5 flex-wrap">
        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${SECTION_COLORS[item.section] ?? "bg-raised text-gray-500"}`}>
          {SECTION_LABELS[item.section] ?? item.section}
        </span>
        {item.section === "unsorted" ? (
          <span className="text-sm text-gray-400">Blurt wasn&rsquo;t sure where this goes</span>
        ) : (
          conf && (
            <span className="text-sm text-gray-400">
              {conf}
              {missingImpact ? " · impact missing" : ""}
            </span>
          )
        )}
        {reviewed && (
          <span className={`ml-auto text-xs font-bold px-2.5 py-1 rounded-full ${item.status === "approved" ? "bg-[#E7F5EC] text-[#2E8B57]" : "bg-red-100 text-red-700"}`}>
            {item.status}
          </span>
        )}
      </div>

      <h3 className="font-display text-[1.35rem] font-bold text-[#1D1D1F] leading-snug -mt-1">{title}</h3>

      {editing ? (
        <div className="flex flex-col gap-2.5">
          {Object.entries(draft).map(([k, v]) => (
            <div key={k} className="flex flex-col gap-1">
              <label className="text-xs text-gray-400 font-semibold capitalize">{k.replace(/_/g, " ")}</label>
              <input
                className="text-[15px] border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)] rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#0071E3]/30"
                value={v}
                onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
              />
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <button onClick={saveEdit} disabled={saving}
              className="flex-1 text-sm font-bold py-2 rounded-xl bg-[#0071E3] text-white hover:brightness-110 transition disabled:opacity-50">
              {saving ? "Saving…" : "Save"}
            </button>
            <button onClick={() => setEditing(false)} disabled={saving}
              className="flex-1 text-sm font-bold py-2 rounded-xl bg-raised text-gray-600 hover:bg-[#E8E8ED] transition">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <FieldRows item={item} />
      )}

      {!reviewed && !editing && item.followup_question && (
        <div className="bg-[#E8F1FD] rounded-2xl p-4 flex flex-col gap-3">
          <div className="flex items-center gap-2 text-[#0071E3]">
            <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
              <path d="M2 3h11v7H6l-3 2.5V10H2z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
            <span className="text-sm font-bold">Blurt asks</span>
          </div>
          <p className="text-[15px] font-bold text-[#1D1D1F]">{item.followup_question}</p>
          <div className="flex items-center gap-2.5">
            <button className="flex items-center gap-1.5 text-sm font-bold px-3.5 py-2 rounded-xl bg-[#0071E3] text-white hover:brightness-110 transition">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <rect x="4.5" y="1" width="4" height="7" rx="2" stroke="white" strokeWidth="1.3" />
                <path d="M2 6.5A4.5 4.5 0 0 0 11 6.5" stroke="white" strokeWidth="1.3" strokeLinecap="round" />
                <line x1="6.5" y1="11.5" x2="6.5" y2="9" stroke="white" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
              Answer out loud
            </button>
            <button className="text-sm font-bold px-3.5 py-2 rounded-xl bg-surface border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)] text-[#1D1D1F] hover:bg-raised transition">
              Type it
            </button>
            <button className="text-sm font-bold text-gray-400 hover:text-gray-600 transition">Skip</button>
          </div>
        </div>
      )}

      {!reviewed && !editing && item.section === "task" && (
        <div className="bg-[#FDF3E7] rounded-2xl px-4 py-3 flex items-start gap-2.5">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5">
            <rect x="2" y="3" width="12" height="11" rx="2" stroke="#C2772B" strokeWidth="1.3" />
            <path d="M2 6h12M5 1.5v2M11 1.5v2" stroke="#C2772B" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          <p className="text-sm text-[#8A5A20] leading-relaxed">
            This adds an event to your calendar. Blurt only does that after you approve it.
          </p>
        </div>
      )}

      {!reviewed && !editing && item.section === "unsorted" && (
        <div className="flex items-center gap-3">
          <span className="text-[15px] text-gray-400 font-medium">Move to</span>
          <select className="text-[15px] font-medium border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)] rounded-xl px-3 py-2 bg-surface focus:outline-none focus:ring-2 focus:ring-[#0071E3]/30">
            <option>Choose a section</option>
            <option>Work log</option>
            <option>Tasks</option>
            <option>New list</option>
          </select>
        </div>
      )}

      <Snippet ts={ts} text={item.span_text} />

      {!reviewed && !editing && item.section !== "unsorted" && (
        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => onReview(item.id, "approve")}
            className="flex items-center gap-2 text-sm font-bold px-4 py-2.5 rounded-xl bg-[#1D1D1F] text-white hover:bg-[#2d2f36] transition"
          >
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path d="M2 6.5l3 3L11 3" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {approveLabel}
          </button>
          <button onClick={startEdit}
            className="text-sm font-bold px-4 py-2.5 rounded-xl border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)] text-[#1D1D1F] hover:bg-raised transition">
            Edit
          </button>
          {item.section === "work_log" && !missingImpact && (
            <button className="text-sm font-bold px-4 py-2.5 rounded-xl border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)] text-[#1D1D1F] hover:bg-raised transition">
              Move to…
            </button>
          )}
          <button
            onClick={() => onReview(item.id, "reject")}
            className="text-sm font-bold px-4 py-2.5 rounded-xl text-gray-400 hover:text-red-500 transition ml-auto">
            Reject
          </button>
        </div>
      )}
      {reviewed && item.status === "approved" && !editing && (
        <button onClick={startEdit} className="text-sm text-gray-400 hover:text-gray-600 transition self-start">
          Edit
        </button>
      )}
      {reviewed && rejected && (
        <button
          onClick={() => onRestore(item.id)}
          className="flex items-center gap-1.5 text-sm font-bold text-[#0071E3] hover:underline underline-offset-2 self-start"
        >
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M3.5 5.5A4 4 0 1 1 2.8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            <path d="M1.5 2.5v3h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Reconsider
        </button>
      )}
    </div>
  );
}
