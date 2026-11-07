"use client";

import { useEffect, useState } from "react";
import { Item, Recording } from "../../types";
import { apiFetch } from "../../lib/api";
import { computeStreak } from "../../lib/derive";
import { useRecorder } from "../../hooks/useRecorder";
import { ShimmerRow } from "../Shimmer";
import { MicCard } from "../record/MicCard";
import { ThisWeekPanel } from "../record/ThisWeekPanel";
import { RecordingRow } from "../record/RecordingRow";
import { RecMeta, WeekStats } from "../record/types";

interface RecordPageProps {
  token: string;
  onNavigateReview: () => void;
}

const EMPTY_WEEK: WeekStats = { streak: 0, totalKept: 0, workLog: 0, tasks: 0, lists: 0 };

export function RecordPage({ token, onNavigateReview }: RecordPageProps) {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [recordingsLoading, setRecordingsLoading] = useState(true);
  const [metaMap, setMetaMap] = useState<Record<string, RecMeta>>({});
  const [weekStats, setWeekStats] = useState<WeekStats>(EMPTY_WEEK);
  const [refreshTick, setRefreshTick] = useState(0);

  const recorder = useRecorder({ token, onUploaded: () => setRefreshTick((n) => n + 1) });

  async function handleDelete(id: string) {
    setRecordings((prev) => prev.filter((r) => r.id !== id));
    await apiFetch(`/api/v1/recordings/${id}`, token, { method: "DELETE" }).catch(() =>
      setRefreshTick((n) => n + 1),
    );
  }

  useEffect(() => {
    async function loadRecordings() {
      try {
        const data: Recording[] = await apiFetch("/api/v1/recordings", token).then((r) => r.json());
        setRecordings(data);
        setRecordingsLoading(false);

        const ready = data.filter((r) => r.status === "ready");
        const entries = await Promise.all(
          ready.map(async (r) => {
            const items: Item[] = await apiFetch(`/api/v1/recordings/${r.id}/items`, token)
              .then((res) => res.json()).catch(() => []);
            const sections: Record<string, number> = {};
            for (const i of items) {
              if (i.status === "approved") sections[i.section] = (sections[i.section] ?? 0) + 1;
            }
            const meta: RecMeta = {
              pending: items.filter((i) => i.status === "pending").length,
              kept: items.filter((i) => i.status === "approved").length,
              firstSpan: items[0]?.span_text ?? null,
              sections,
            };
            return [r.id, meta] as [string, RecMeta];
          })
        );
        const map = Object.fromEntries(entries);
        setMetaMap(map);

        const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
        const inWeek = ready.filter((r) => new Date(r.created_at).getTime() >= weekAgo);
        let workLog = 0, tasks = 0, lists = 0, totalKept = 0;
        for (const r of inWeek) {
          const m = map[r.id];
          if (!m) continue;
          totalKept += m.kept;
          workLog += m.sections["work_log"] ?? 0;
          tasks += m.sections["task"] ?? 0;
          lists += m.sections["list"] ?? 0;
        }
        setWeekStats({ streak: computeStreak(data), totalKept, workLog, tasks, lists });
      } catch {
        setRecordingsLoading(false);
      }
    }
    void loadRecordings();
    const id = setInterval(() => void loadRecordings(), 3000);
    return () => clearInterval(id);
  }, [token, refreshTick]);

  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });

  return (
    <div className="px-6 sm:px-10 lg:px-12 py-10 max-w-[1120px]">
      <p className="text-sm text-gray-400 font-bold mb-3">{today}</p>
      <h1 className="font-display text-[2.75rem] leading-[1.05] font-bold text-[#1D1D1F] mb-3">
        What&rsquo;s on your mind? Just blurt it.
      </h1>
      <p className="text-base text-gray-500 mb-9 max-w-xl leading-relaxed">
        Talk for a minute. Blurt splits it into items and files each one. Nothing is saved until you approve it.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-5 mb-12 items-stretch">
        <MicCard
          micActive={recorder.micActive}
          uploading={recorder.uploading}
          elapsed={recorder.elapsed}
          uploadError={recorder.uploadError}
          paused={recorder.paused}
          analyser={recorder.analyser}
          onPause={recorder.pause}
          onResume={recorder.resume}
          recordedUrl={recorder.recordedUrl}
          onSubmit={() => void recorder.submit()}
          onDiscard={recorder.discard}
          onToggle={() => (recorder.micActive ? recorder.stop() : recorder.start())}
          onPickFile={(file) => void recorder.uploadFile(file)}
        />
        <ThisWeekPanel stats={weekStats} loading={recordingsLoading} onOpenWorkLog={onNavigateReview} />
      </div>

      <h2 className="font-display text-2xl font-bold text-[#1D1D1F] mb-4">Recent blurts</h2>

      {recordingsLoading ? (
        <div className="flex flex-col gap-2.5">
          {[0, 1, 2].map((i) => <ShimmerRow key={i} />)}
        </div>
      ) : recordings.length === 0 ? (
        <p className="text-sm text-gray-400">No recordings yet.</p>
      ) : (
        <div className="flex flex-col gap-2.5">
          {recordings.map((r, i) => (
            <RecordingRow
              key={r.id}
              recording={r}
              number={recordings.length - i}
              meta={metaMap[r.id] ?? null}
              onReview={onNavigateReview}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
