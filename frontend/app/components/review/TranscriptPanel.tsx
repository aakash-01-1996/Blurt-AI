"use client";

import { useEffect, useRef, useState } from "react";
import { Item, Recording, sectionTint } from "../../types";
import { apiFetch } from "../../lib/api";
import { fmtTime } from "../../lib/format";

interface TranscriptPanelProps {
  items: Item[];
  recording: Recording | null;
  token: string;
  timestamps: Record<string, number>;
}

/** Left "What you said" column: audio player + highlighted, timestamped transcript. */
export function TranscriptPanel({ items, recording, token, timestamps }: TranscriptPanelProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const duration = recording?.duration_s ?? 0;

  useEffect(() => {
    let cancelled = false;
    if (!recording) return;
    apiFetch(`/api/v1/recordings/${recording.id}/audio-url`, token)
      .then((r) => r.json())
      .then((d) => {
        if (cancelled || !d?.url || !audioRef.current) return;
        audioRef.current.src = d.url;
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [recording, token]);

  function toggle() {
    const a = audioRef.current;
    if (!a || !a.src) return;
    if (playing) a.pause();
    else void a.play();
  }

  const pct = duration > 0 ? Math.min(current / duration, 1) : 0;
  const bars = 42;

  return (
    <div className="bg-surface rounded-3xl p-6 border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      <h2 className="font-display text-xl font-bold text-[#1D1D1F] mb-4">What you said</h2>

      <div className="bg-raised rounded-2xl px-4 py-3 flex items-center gap-3 mb-5">
        <button
          onClick={toggle}
          className="w-9 h-9 rounded-full bg-[#0071E3] flex items-center justify-center shrink-0 hover:brightness-110 transition"
          aria-label={playing ? "Pause" : "Play"}
        >
          {playing ? (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="white">
              <rect x="3" y="2.5" width="3" height="9" rx="1" />
              <rect x="8" y="2.5" width="3" height="9" rx="1" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 14 14" fill="white">
              <path d="M4 2.5l7 4.5-7 4.5z" />
            </svg>
          )}
        </button>
        <div className="flex items-center gap-[2px] flex-1 h-7">
          {Array.from({ length: bars }).map((_, i) => {
            const filled = i / bars <= pct;
            const h = 20 + Math.round(Math.abs(Math.sin(i * 1.7)) * 70);
            return (
              <span
                key={i}
                className={`flex-1 rounded-full ${filled ? "bg-[#0071E3]" : "bg-gray-300"}`}
                style={{ height: `${h}%` }}
              />
            );
          })}
        </div>
        <span className="font-mono text-xs text-gray-400 shrink-0">
          {fmtTime(current)} / {fmtTime(duration)}
        </span>
      </div>
      <audio
        ref={audioRef}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
        className="hidden"
      />

      <div className="flex flex-col gap-3">
        {items.map((it) => (
          <div key={it.id} className="flex gap-3 text-[15px] leading-relaxed">
            <span className="font-mono text-xs text-gray-400 pt-1 w-9 shrink-0">
              {fmtTime(timestamps[it.id] ?? 0)}
            </span>
            <span className="text-[#2A2C33]">
              <span className={`rounded px-1 py-0.5 box-decoration-clone ${sectionTint(it.section)}`}>
                {it.span_text}
              </span>
            </span>
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-400 mt-5">Highlights match the item each part became.</p>
    </div>
  );
}
