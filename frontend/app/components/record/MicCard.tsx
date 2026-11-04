"use client";

import { useEffect, useRef, useState } from "react";
import { Waveform } from "./Waveform";

interface MicCardProps {
  micActive: boolean;
  uploading: boolean;
  elapsed: number;
  uploadError: string | null;
  onToggle: () => void;
  onPickFile: (file: File) => void;
  paused?: boolean;
  analyser?: AnalyserNode | null;
  onPause?: () => void;
  onResume?: () => void;
  recordedUrl?: string | null;
  onSubmit?: () => void;
  onDiscard?: () => void;
}

const RED = "#FF3B30";

const fmt = (s: number) =>
  `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

// The recorder card: idle → tap to record; recording → live waveform with
// Pause/Stop; stopped → review the take and choose Start processing or Re-take.
export function MicCard({
  micActive,
  uploading,
  elapsed,
  uploadError,
  onToggle,
  onPickFile,
  paused = false,
  analyser = null,
  onPause,
  onResume,
  recordedUrl = null,
  onSubmit,
  onDiscard,
}: MicCardProps) {
  const reviewing = !micActive && !uploading && !!recordedUrl;

  return (
    <div className="bg-surface rounded-3xl p-10 flex flex-col items-center justify-center gap-6 border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
      {micActive ? (
        <div className="flex flex-col items-center gap-5 w-full">
          <Waveform analyser={analyser} paused={paused} />

          <div className="flex flex-col items-center gap-1">
            <span className="text-[#1D1D1F] font-mono text-lg tabular-nums">{fmt(elapsed)}</span>
            <span className="text-sm font-semibold" style={{ color: paused ? "#86868B" : RED }}>
              {paused ? "Paused" : "Recording"}
            </span>
          </div>

          <div className="flex items-center gap-5">
            <button
              onClick={() => (paused ? onResume?.() : onPause?.())}
              aria-label={paused ? "Resume recording" : "Pause recording"}
              className="w-14 h-14 rounded-full bg-raised border border-[#E5E5EA] flex items-center justify-center text-[#1D1D1F] transition-transform active:scale-90 hover:scale-105 shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
            >
              {paused ? (
                <svg width="22" height="22" viewBox="0 0 22 22" fill="currentColor">
                  <path d="M6 4.5l12 6.5-12 6.5z" />
                </svg>
              ) : (
                <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                  <rect x="4" y="3" width="4.5" height="14" rx="1.6" />
                  <rect x="11.5" y="3" width="4.5" height="14" rx="1.6" />
                </svg>
              )}
            </button>

            <button
              onClick={onToggle}
              aria-label="Stop recording"
              className="w-14 h-14 rounded-full flex items-center justify-center text-white transition-transform active:scale-90 hover:scale-105 shadow-[0_6px_16px_rgba(255,59,48,0.35)]"
              style={{ background: RED }}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                <rect x="4" y="4" width="12" height="12" rx="3" />
              </svg>
            </button>
          </div>
        </div>
      ) : reviewing ? (
        <ReviewRecording
          url={recordedUrl!}
          elapsed={elapsed}
          onSubmit={() => onSubmit?.()}
          onDiscard={() => onDiscard?.()}
        />
      ) : (
        <>
          <button
            onClick={onToggle}
            disabled={uploading}
            aria-label="Start recording"
            className={`relative w-[104px] h-[104px] rounded-full flex items-center justify-center transition-transform active:scale-95 ${
              uploading ? "cursor-not-allowed" : "cursor-pointer hover:scale-[1.02]"
            }`}
          >
            <span className="absolute inset-0 rounded-full border-2 border-black/10" />
            <span
              className="block transition-all duration-300 ease-out shadow-[0_6px_16px_rgba(255,59,48,0.35)]"
              style={{
                width: 80,
                height: 80,
                borderRadius: 9999,
                background: uploading ? "#C7C7CC" : RED,
                boxShadow: uploading ? "none" : undefined,
              }}
            />
          </button>

          {uploading ? (
            <span className="text-base text-[#86868B]">Uploading…</span>
          ) : (
            <div className="flex flex-col items-center gap-1">
              <span className="text-lg font-semibold text-[#1D1D1F]">Tap to record</span>
              <span className="text-sm text-[#86868B]">Try: what you shipped, what&rsquo;s blocking you</span>
            </div>
          )}
        </>
      )}

      {uploadError && <p className="text-sm text-red-600 text-center">{uploadError}</p>}

      {!reviewing && (
        <label className="text-sm font-medium text-[#0071E3] hover:underline cursor-pointer underline-offset-2">
          or upload an audio file
          <input
            type="file"
            accept="audio/*"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onPickFile(file);
              e.target.value = "";
            }}
          />
        </label>
      )}
    </div>
  );
}

/** Playback + Start-processing / Re-take after a recording is stopped. */
function ReviewRecording({
  url,
  elapsed,
  onSubmit,
  onDiscard,
}: {
  url: string;
  elapsed: number;
  onSubmit: () => void;
  onDiscard: () => void;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => () => { audioRef.current?.pause(); }, []);

  function toggle() {
    const a = audioRef.current;
    if (!a) return;
    if (playing) a.pause();
    else void a.play();
  }

  return (
    <div className="flex flex-col items-center gap-6 w-full">
      <div className="flex items-center gap-4">
        <button
          onClick={toggle}
          aria-label={playing ? "Pause playback" : "Play recording"}
          className="w-14 h-14 rounded-full bg-[#0071E3] flex items-center justify-center text-white transition-transform active:scale-90 hover:scale-105 shadow-[0_6px_16px_rgba(0,113,227,0.3)]"
        >
          {playing ? (
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <rect x="4" y="3" width="4.5" height="14" rx="1.6" />
              <rect x="11.5" y="3" width="4.5" height="14" rx="1.6" />
            </svg>
          ) : (
            <svg width="22" height="22" viewBox="0 0 22 22" fill="currentColor">
              <path d="M6 4.5l12 6.5-12 6.5z" />
            </svg>
          )}
        </button>
        <div className="flex flex-col">
          <span className="text-lg font-semibold text-[#1D1D1F]">Ready to process</span>
          <span className="text-sm text-[#86868B]">Your recording · {fmt(elapsed)}</span>
        </div>
      </div>

      <audio
        ref={audioRef}
        src={url}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        className="hidden"
      />

      <div className="flex items-center gap-3">
        <button
          onClick={onDiscard}
          className="px-5 py-2.5 rounded-xl bg-raised border border-[#E5E5EA] text-[15px] font-semibold text-[#1D1D1F] hover:bg-[#ECECEE] transition"
        >
          Re-take
        </button>
        <button
          onClick={onSubmit}
          className="px-5 py-2.5 rounded-xl bg-[#1D1D1F] text-white text-[15px] font-bold hover:bg-[#2d2f36] transition"
        >
          Start processing
        </button>
      </div>
    </div>
  );
}
