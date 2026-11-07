"use client";

import { useEffect, useState } from "react";
import { Note } from "../../types";
import { apiFetch } from "../../lib/api";
import { ShimmerRow } from "../Shimmer";
import { NoteCard } from "../notes/NoteCard";

export function NotesPage({ token }: { token: string }) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/v1/notes", token)
      .then((r) => r.json())
      .then((data) => { setNotes(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [token]);

  async function remove(note: Note) {
    const prev = notes;
    setNotes((cur) => cur.filter((n) => n.id !== note.id));
    try {
      const res = await apiFetch(`/api/v1/notes/${note.id}`, token, { method: "DELETE" });
      if (!res.ok) setNotes(prev);
    } catch {
      setNotes(prev);
    }
  }

  return (
    <div className="px-6 sm:px-10 lg:px-12 py-10 max-w-[760px]">
      <h1 className="font-display text-4xl font-bold text-[#1D1D1F]">Notes</h1>
      <p className="text-base text-gray-400 mt-1.5 mb-8">
        {notes.length} {notes.length === 1 ? "note" : "notes"}
      </p>

      {loading ? (
        <div className="flex flex-col gap-2.5">
          {[0, 1, 2].map((i) => <ShimmerRow key={i} />)}
        </div>
      ) : notes.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-2 text-center">
          <p className="text-base text-gray-400">
            No notes yet. Approve a note in the review inbox and it lands here.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {notes.map((n) => <NoteCard key={n.id} note={n} onDelete={remove} />)}
        </div>
      )}
    </div>
  );
}
