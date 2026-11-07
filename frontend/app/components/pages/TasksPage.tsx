"use client";

import { useEffect, useState } from "react";
import { Task } from "../../types";
import { apiFetch } from "../../lib/api";
import { ShimmerRow } from "../Shimmer";
import { TaskRow } from "../tasks/TaskRow";

export function TasksPage({ token }: { token: string }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/v1/tasks", token)
      .then((r) => r.json())
      .then((data) => { setTasks(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  async function toggle(task: Task) {
    const next = task.status === "done" ? "open" : "done";
    setTasks((prev) =>
      prev.map((t) =>
        t.id === task.id
          ? { ...t, status: next, completed_at: next === "done" ? new Date().toISOString() : null }
          : t
      )
    );
    try {
      const res = await apiFetch(`/api/v1/tasks/${task.id}`, token, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next }),
      });
      if (!res.ok) {
        setTasks((prev) => prev.map((t) => (t.id === task.id ? task : t)));
        return;
      }
      const updated: Task = await res.json();
      setTasks((prev) => prev.map((t) => (t.id === task.id ? updated : t)));
    } catch {
      setTasks((prev) => prev.map((t) => (t.id === task.id ? task : t)));
    }
  }

  const open = tasks.filter((t) => t.status === "open");
  const done = tasks.filter((t) => t.status === "done");

  return (
    <div className="px-6 sm:px-10 lg:px-12 py-10 max-w-[760px]">
      <h1 className="font-display text-4xl font-bold text-[#1D1D1F]">Tasks</h1>
      <p className="text-base text-gray-400 mt-1.5 mb-8">
        {open.length} open · {done.length} done
      </p>

      {loading ? (
        <div className="flex flex-col gap-2.5">
          {[0, 1, 2].map((i) => <ShimmerRow key={i} />)}
        </div>
      ) : tasks.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-2 text-center">
          <p className="text-base text-gray-400">
            No tasks yet. Approve a task in the review inbox and it lands here.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          <section className="flex flex-col gap-2.5">
            <h2 className="text-sm font-semibold text-gray-400">To do</h2>
            {open.length === 0 ? (
              <p className="text-sm text-gray-400">Nothing to do — all caught up.</p>
            ) : (
              open.map((t) => <TaskRow key={t.id} task={t} onToggle={toggle} />)
            )}
          </section>

          {done.length > 0 && (
            <section className="flex flex-col gap-2.5">
              <h2 className="text-sm font-semibold text-gray-400">Done</h2>
              {done.map((t) => <TaskRow key={t.id} task={t} onToggle={toggle} />)}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
