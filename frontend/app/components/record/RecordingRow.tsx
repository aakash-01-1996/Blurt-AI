"use client";

import { Recording } from "../../types";
import { formatDateTimeLabel, formatDuration, truncate } from "../../lib/format";
import { RecMeta } from "./types";

const PROCESSING_LABELS: Record<string, string> = {
  uploaded: "Processing: uploaded",
  normalizing: "Processing: normalizing",
  transcribing: "Processing: transcribing",
  splitting: "Processing: splitting into items",
  routing: "Processing: routing",
  extracting: "Processing: extracting items",
};

interface RecordingRowProps {
  recording: Recording;
  number: number;
  meta: RecMeta | null;
  onReview: (id: string) => void;
  onDelete: (id: string) => void;
  onRetry: (id: string) => void;
}

export function RecordingRow({
  recording,
  number,
  meta,
  onReview,
  onDelete,
  onRetry,
}: RecordingRowProps) {
  const timeLabel = formatDateTimeLabel(new Date(recording.created_at));
  const dur = formatDuration(recording.duration_s);
  const descriptor = meta?.firstSpan ? truncate(meta.firstSpan, 38) : null;

  const processing = recording.status !== "ready" && recording.status !== "failed";
  const hasPending = recording.status === "ready" && meta !== null && meta.pending > 0;
  const allReviewed = recording.status === "ready" && meta !== null && meta.pending === 0 && meta.kept > 0;

  return (
    <div className="bg-surface rounded-2xl px-5 py-4 flex items-center justify-between gap-4 border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-[15px] font-bold text-[#1D1D1F]">Recording {number}</span>
        <span className="text-sm text-gray-400 truncate">
          {timeLabel} · {dur}
          {descriptor ? ` · ${descriptor}` : ""}
        </span>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {hasPending && (
          <>
            <span className="text-sm font-medium text-[#0071E3] bg-[#E8F1FD] px-3 py-1.5 rounded-full">
              {meta!.pending} item{meta!.pending !== 1 ? "s" : ""} to review
            </span>
            <button
              onClick={() => onReview(recording.id)}
              className="text-sm font-bold px-4 py-2 rounded-xl bg-[#1D1D1F] text-white hover:bg-[#2d2f36] transition"
            >
              Review
            </button>
          </>
        )}
        {allReviewed && (
          <span className="text-sm font-semibold px-3 py-1.5 rounded-full bg-[#E7F5EC] text-[#2E8B57]">
            {meta!.kept} item{meta!.kept !== 1 ? "s" : ""} kept
          </span>
        )}
        {recording.status === "ready" && meta === null && (
          <button
            onClick={() => onReview(recording.id)}
            className="text-sm font-bold px-4 py-2 rounded-xl bg-[#1D1D1F] text-white hover:bg-[#2d2f36] transition"
          >
            Review
          </button>
        )}
        {processing && (
          <span className="text-sm font-medium px-3 py-1.5 rounded-full bg-raised text-gray-500">
            {PROCESSING_LABELS[recording.status] ?? "Processing"}
          </span>
        )}
        {recording.status === "failed" && (
          <>
            <span className="text-sm font-medium px-3 py-1.5 rounded-full bg-red-100 text-red-700">
              Failed
            </span>
            <button
              onClick={() => onRetry(recording.id)}
              className="text-sm font-bold px-4 py-2 rounded-xl border border-[#E5E5EA] text-[#1D1D1F] hover:bg-raised transition"
            >
              Retry
            </button>
          </>
        )}
        <button
          onClick={() => {
            if (window.confirm("Delete this recording and everything from it? This can't be undone.")) {
              onDelete(recording.id);
            }
          }}
          aria-label="Delete recording"
          className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-300 hover:text-[#FF3B30] hover:bg-red-50 transition"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2.5 4h11M6 4V2.8A.8.8 0 0 1 6.8 2h2.4a.8.8 0 0 1 .8.8V4M12.5 4l-.6 8.3a1 1 0 0 1-1 .9H5.1a1 1 0 0 1-1-.9L3.5 4M6.5 7v3.5M9.5 7v3.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}
