"use client";

import { useEffect, useState } from "react";
import { List, ListItem } from "../../types";
import { apiFetch } from "../../lib/api";
import { ShimmerRow } from "../Shimmer";
import { ListCard } from "../lists/ListCard";

export function ListsPage({ token }: { token: string }) {
  const [lists, setLists] = useState<List[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/v1/lists", token)
      .then((r) => r.json())
      .then((data) => { setLists(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  async function toggleItem(list: List, item: ListItem) {
    const next = !item.checked;
    setLists((prev) =>
      prev.map((l) =>
        l.id === list.id
          ? { ...l, items: l.items.map((i) => (i.id === item.id ? { ...i, checked: next } : i)) }
          : l
      )
    );
    const rollback = () =>
      setLists((prev) =>
        prev.map((l) =>
          l.id === list.id
            ? { ...l, items: l.items.map((i) => (i.id === item.id ? { ...i, checked: item.checked } : i)) }
            : l
        )
      );
    try {
      const res = await apiFetch(`/api/v1/lists/${list.id}/items/${item.id}`, token, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ checked: next }),
      });
      if (!res.ok) rollback();
    } catch {
      rollback();
    }
  }

  async function remove(list: List) {
    const prev = lists;
    setLists((cur) => cur.filter((l) => l.id !== list.id));
    try {
      const res = await apiFetch(`/api/v1/lists/${list.id}`, token, { method: "DELETE" });
      if (!res.ok) setLists(prev);
    } catch {
      setLists(prev);
    }
  }

  return (
    <div className="px-6 sm:px-10 lg:px-12 py-10 max-w-[760px]">
      <h1 className="font-display text-4xl font-bold text-[#1D1D1F]">Lists</h1>
      <p className="text-base text-gray-400 mt-1.5 mb-8">
        {lists.length} {lists.length === 1 ? "list" : "lists"}
      </p>

      {loading ? (
        <div className="flex flex-col gap-2.5">
          {[0, 1, 2].map((i) => <ShimmerRow key={i} />)}
        </div>
      ) : lists.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-2 text-center">
          <p className="text-base text-gray-400">
            No lists yet. Approve a list in the review inbox and it lands here.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {lists.map((l) => (
            <ListCard key={l.id} list={l} onToggleItem={toggleItem} onDelete={remove} />
          ))}
        </div>
      )}
    </div>
  );
}
