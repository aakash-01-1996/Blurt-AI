"use client";

import { useEffect, useMemo, useState } from "react";
import { Item, Recording } from "../../types";
import { apiFetch } from "../../lib/api";
import { deriveTimestamps } from "../../lib/derive";
import { fmtTime } from "../../lib/format";
import { ShimmerBox, ShimmerCard } from "../Shimmer";
import { TranscriptPanel } from "../review/TranscriptPanel";
import { ReviewItemCard } from "../review/ReviewItemCard";
import { FilterSection, ReviewFilters } from "../review/ReviewFilters";

interface ReviewPageProps {
  token: string;
  onCountChange: (n: number) => void;
}

export function ReviewPage({ token, onCountChange }: ReviewPageProps) {
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [itemsMap, setItemsMap] = useState<Record<string, Item[]>>({});
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterSection>("all");
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    async function fetchAll() {
      const res = await apiFetch("/api/v1/recordings", token).then((r) => r.json()).catch(() => []);
      if (cancelled) return;
      const ready: Recording[] = (res as Recording[]).filter((r) => r.status === "ready");
      setRecordings(ready);

      const entries = await Promise.all(
        ready.map(async (r) => {
          const items: Item[] = await apiFetch(`/api/v1/recordings/${r.id}/items`, token)
            .then((res) => res.json()).catch(() => []);
          return [r.id, items] as [string, Item[]];
        })
      );
      if (cancelled) return;
      const map = Object.fromEntries(entries);
      setItemsMap(map);
      setLoading(false);
    }
    void fetchAll();
    return () => { cancelled = true; };
  }, [token]);

  // Keep the sidebar's review count in sync with loaded items. Done in an
  // effect — never inside a setState updater — so we don't update a parent
  // component (AppShell) while rendering this one.
  useEffect(() => {
    const pending = Object.values(itemsMap).flat().filter((i) => i.status === "pending").length;
    onCountChange(pending);
  }, [itemsMap, onCountChange]);

  // Focus on one recording: most recent with pending items, else most recent.
  const active = useMemo(() => {
    const withPending = recordings.find((r) => (itemsMap[r.id] ?? []).some((i) => i.status === "pending"));
    return withPending ?? recordings[0] ?? null;
  }, [recordings, itemsMap]);

  const items = useMemo(() => (active ? (itemsMap[active.id] ?? []) : []), [active, itemsMap]);
  // Prefer real segment-derived timestamps from the backend; fall back to the
  // client-side approximation only for items that lack timing (e.g. old data).
  const timestamps = useMemo(() => {
    const derived = deriveTimestamps(items, active?.duration_s ?? null);
    const out: Record<string, number> = {};
    for (const it of items) {
      out[it.id] = it.start_s ?? derived[it.id] ?? 0;
    }
    return out;
  }, [items, active]);

  const counts: Record<FilterSection, number> = {
    all: items.length,
    work_log: items.filter((i) => i.section === "work_log").length,
    task: items.filter((i) => i.section === "task").length,
    list: items.filter((i) => i.section === "list").length,
    unsorted: items.filter((i) => !i.section || i.section === "unsorted").length,
  };

  const visible = items
    .filter((i) => !dismissed.has(i.id))
    .filter((i) => filter === "all" || (filter === "unsorted" ? (!i.section || i.section === "unsorted") : i.section === filter));

  const pendingCount = items.filter((i) => i.status === "pending").length;

  async function handleReview(itemId: string, action: "approve" | "reject") {
    if (!active) return;
    const res = await apiFetch(`/api/v1/items/${itemId}/review`, token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (!res.ok) return;
    const updated: Item = await res.json();
    setItemsMap((prev) => ({
      ...prev,
      [active.id]: (prev[active.id] ?? []).map((i) => (i.id === itemId ? updated : i)),
    }));
  }

  async function handlePatch(itemId: string, fields: Record<string, string>) {
    if (!active) return;
    const res = await apiFetch(`/api/v1/items/${itemId}`, token, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields }),
    });
    if (!res.ok) return;
    const updated: Item = await res.json();
    setItemsMap((prev) => ({
      ...prev,
      [active.id]: (prev[active.id] ?? []).map((i) => (i.id === itemId ? updated : i)),
    }));
  }

  const sub = active ? buildSubtitle(active, pendingCount, items.length) : "";

  return (
    <div className="px-6 sm:px-10 lg:px-12 py-10 max-w-[1280px]">
      <div className="flex items-start justify-between gap-4 mb-2">
        <div>
          <h1 className="font-display text-4xl font-bold text-[#1D1D1F]">Review inbox</h1>
          {!loading && active && <p className="text-base text-gray-400 mt-1.5">{sub}</p>}
        </div>
        <span className="text-sm text-gray-400 flex items-center gap-1.5 mt-2 shrink-0">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1L2 3v4c0 3 2.2 5 5 6 2.8-1 5-3 5-6V3L7 1z" stroke="#9CA3AF" strokeWidth="1.2" strokeLinejoin="round" />
          </svg>
          Nothing is saved until you approve it.
        </span>
      </div>

      {!loading && <ReviewFilters counts={counts} value={filter} onChange={setFilter} />}

      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(360px,420px)_1fr] gap-6">
          <ShimmerBox className="h-96 w-full rounded-3xl" />
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => <ShimmerCard key={i} />)}
          </div>
        </div>
      ) : !active || items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
            <circle cx="18" cy="18" r="15" stroke="#E5E7EB" strokeWidth="2" />
            <path d="M11 18l4.5 4.5L25 13" stroke="#D1D5DB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <p className="text-base text-gray-400">All caught up — nothing to review.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(360px,420px)_1fr] gap-6 items-start">
          <div className="lg:sticky lg:top-6">
            <TranscriptPanel items={items} recording={active} token={token} timestamps={timestamps} />
          </div>

          <div className="flex flex-col gap-4">
            {visible.length === 0 ? (
              <p className="text-base text-gray-400 py-8 text-center">Nothing in this section.</p>
            ) : (
              visible.map((item) => (
                <ReviewItemCard
                  key={item.id}
                  item={item}
                  ts={timestamps[item.id] ?? 0}
                  onReview={handleReview}
                  onPatch={handlePatch}
                  onDismiss={(id) => setDismissed((prev) => new Set(prev).add(id))}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function buildSubtitle(active: Recording, pending: number, total: number): string {
  const d = new Date(active.created_at);
  const isToday = d.toDateString() === new Date().toDateString();
  const dayLabel = isToday ? "today" : d.toLocaleDateString("en-US", { weekday: "long" });
  const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  const dur = active.duration_s ? fmtTime(active.duration_s) : "—";
  return `From your blurt ${dayLabel} at ${time} · ${dur} · ${pending} of ${total} left to review`;
}
