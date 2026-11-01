"use client";

import { useEffect, useRef } from "react";

interface WaveformProps {
  analyser: AnalyserNode | null;
  paused: boolean;
}

const BAR_COUNT = 44;

/**
 * Siri-style live waveform. Bars grow from a centre line, driven by the live
 * mic analyser. Falls back to a gentle resting shimmer when there's no analyser
 * (e.g. before permission) and flattens when paused.
 */
export function Waveform({ analyser, paused }: WaveformProps) {
  const barsRef = useRef<(HTMLSpanElement | null)[]>([]);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const setHeights = (fn: (i: number) => number) => {
      for (let i = 0; i < BAR_COUNT; i++) {
        const el = barsRef.current[i];
        if (el) el.style.height = `${Math.max(6, Math.min(100, fn(i)))}%`;
      }
    };

    // Paused → flat line. Keeps looking "held".
    if (paused) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      setHeights(() => 6);
      return;
    }

    // No analyser → soft resting wave so the UI still feels alive.
    if (!analyser) {
      let t = 0;
      const rest = () => {
        t += 0.08;
        setHeights((i) => 10 + Math.abs(Math.sin(i * 0.5 + t)) * 14);
        rafRef.current = requestAnimationFrame(rest);
      };
      rest();
      return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    }

    const data = new Uint8Array(analyser.frequencyBinCount);
    // Use the lower ~65% of the spectrum (where speech energy lives).
    const usable = Math.floor(analyser.frequencyBinCount * 0.65);

    const draw = () => {
      analyser.getByteFrequencyData(data);
      setHeights((i) => {
        // Mirror around the centre so the shape is symmetric like Siri.
        const half = BAR_COUNT / 2;
        const dist = Math.abs(i - half) / half; // 0 centre → 1 edge
        const binIndex = Math.floor((1 - dist) * (usable - 1));
        const v = data[binIndex] / 255; // 0..1
        // Ease + centre weighting so the middle swells more.
        const centre = 1 - dist * 0.5;
        return 6 + Math.pow(v, 0.8) * 94 * centre;
      });
      rafRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [analyser, paused]);

  return (
    <div
      className="flex items-center justify-center gap-[3px] h-24 w-full max-w-[360px] px-2"
      aria-hidden="true"
    >
      {Array.from({ length: BAR_COUNT }).map((_, i) => (
        <span
          key={i}
          ref={(el) => { barsRef.current[i] = el; }}
          className="flex-1 rounded-full transition-[height] duration-75 ease-out"
          style={{
            height: "6%",
            background: "linear-gradient(180deg, #0A84FF 0%, #5E5CE6 55%, #BF5AF2 100%)",
            opacity: paused ? 0.35 : 1,
          }}
        />
      ))}
    </div>
  );
}
