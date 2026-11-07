"use client";

import { useCallback, useEffect, useState } from "react";
import { WorkLogEntry } from "../../types";
import { apiFetch } from "../../lib/api";
import { formatDayLabel } from "../../lib/format";
import { ShimmerBox, ShimmerText } from "../Shimmer";
import { EntryCard } from "../worklog/EntryCard";
import { WeekSummaryCard } from "../worklog/WeekSummaryCard";
import { WorkLogSidebar } from "../worklog/WorkLogSidebar";

type Period = "week" | "month" | "quarter";

interface DayGroup {
  label: string;
  date: string;
  items: WorkLogEntry[];
}

function groupByDay(entries: WorkLogEntry[]): DayGroup[] {
  const map = new Map<string, WorkLogEntry[]>();
  for (const entry of entries) {
    const key = new Date(entry.occurred_on ?? entry.created_at).toDateString();
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(entry);
  }
  return Array.from(map.entries()).map(([key, items]) => ({
    label: formatDayLabel(new Date(key)),
    date: key,
    items,
  }));
}

function rangeLabel(entries: WorkLogEntry[]): string {
  const dates = entries
    .map((e) => new Date(e.occurred_on ?? e.created_at))
    .sort((a, b) => a.getTime() - b.getTime());
  let start = dates[0];
  let end = dates[dates.length - 1];
  if (!start) {
    start = new Date();
    start.setDate(start.getDate() - start.getDay() + 1);
    end = new Date(start);
    end.setDate(start.getDate() + 4);
  }
  const fmt = (d: Date, withYear = false) =>
    d.toLocaleDateString("en-US", { month: "short", day: "numeric", ...(withYear ? { year: "numeric" } : {}) });
  return `${fmt(start)} – ${fmt(end, true)}`;
}

function ShimmerEntryGroup() {
  return (
    <div className="flex flex-col gap-2.5">
      <ShimmerBox className="h-3 w-24 mb-1" />
      {[0, 1].map((i) => (
        <div key={i} className="bg-surface rounded-2xl px-5 py-4 flex flex-col gap-2.5">
          <ShimmerText lines={1} className="w-2/3" />
          <ShimmerBox className="h-5 w-40 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function WorkLogPage({ token }: { token: string }) {
  const [entries, setEntries] = useState<WorkLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [period, setPeriod] = useState<Period>("week");

  const fetchEntries = useCallback(() => {
    apiFetch("/api/v1/work-log", token)
      .then((r) => r.json())
      .then((data) => { setEntries(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  useEffect(() => { fetchEntries(); }, [fetchEntries]);

  const filtered = selectedProject ? entries.filter((e) => e.project === selectedProject) : entries;
  const groups = groupByDay(filtered);

  const totalEntries = entries.length;
  const withImpact = entries.filter((e) => e.impact).length;
  const needImpact = entries.filter((e) => !e.impact).length;
  const projects = Array.from(new Set(entries.map((e) => e.project).filter(Boolean))) as string[];
  const projectCounts = projects.reduce<Record<string, number>>((acc, p) => {
    acc[p] = entries.filter((e) => e.project === p).length;
    return acc;
  }, {});

  return (
    <div className="px-6 sm:px-10 lg:px-12 py-10 max-w-[1120px]">
      <div className="flex items-start justify-between gap-4 mb-7">
        <div>
          <h1 className="font-display text-4xl font-bold text-[#1D1D1F]">Work log</h1>
          <p className="text-base text-gray-400 mt-1.5">{rangeLabel(entries)}</p>
        </div>
        <div className="flex items-center gap-1 bg-raised rounded-xl p-1">
          {(["week", "month", "quarter"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`text-sm font-bold px-4 py-2 rounded-lg transition capitalize ${
                period === p ? "bg-surface text-[#1D1D1F] shadow-sm" : "text-[#6E6E73] hover:text-[#1D1D1F]"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6 items-start">
        <div className="flex flex-col gap-5">
          {loading ? (
            <ShimmerBox className="h-52 w-full rounded-3xl" />
          ) : entries.length > 0 ? (
            <WeekSummaryCard entries={entries} />
          ) : null}

          {!loading && (
            <div className="grid grid-cols-3 gap-4">
              {[
                { value: totalEntries, label: "Entries" },
                { value: withImpact, label: "With measured impact" },
                { value: projects.length, label: "Projects" },
              ].map(({ value, label }) => (
                <div key={label} className="bg-surface rounded-2xl px-5 py-4 border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)]">
                  <p className="font-display text-3xl font-bold text-[#1D1D1F]">{value}</p>
                  <p className="text-sm text-gray-400 mt-1">{label}</p>
                </div>
              ))}
            </div>
          )}

          {loading ? (
            <div className="flex flex-col gap-6">
              <ShimmerEntryGroup />
              <ShimmerEntryGroup />
            </div>
          ) : groups.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-2">
              <p className="text-base text-gray-400">
                {selectedProject
                  ? `No entries for "${selectedProject}".`
                  : "No entries yet. Approve work log items to see them here."}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {groups.map(({ label, date, items }) => (
                <div key={date} className="flex flex-col gap-2.5">
                  <p className="text-sm font-semibold text-gray-400">{label}</p>
                  {items.map((entry) => <EntryCard key={entry.id} entry={entry} />)}
                </div>
              ))}
            </div>
          )}
        </div>

        <WorkLogSidebar
          loading={loading}
          needImpact={needImpact}
          totalEntries={totalEntries}
          projects={projects}
          projectCounts={projectCounts}
          selectedProject={selectedProject}
          onSelectProject={setSelectedProject}
        />
      </div>
    </div>
  );
}
