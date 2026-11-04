"use client";

import { useSyncExternalStore } from "react";

const TOKEN_KEY = "blurt_token";
const listeners = new Set<() => void>();

function subscribe(cb: () => void) {
  listeners.add(cb);
  if (typeof window !== "undefined") window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    if (typeof window !== "undefined") window.removeEventListener("storage", cb);
  };
}

function emit() {
  listeners.forEach((l) => l());
}

function getSnapshot(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function getServerSnapshot(): string | null {
  return null;
}

// Reads the token from localStorage without a hydration mismatch (server snapshot is null).
// `hydrated` is false until the client has mounted, so callers can avoid flashing
// the login screen during SSR/first paint when localStorage hasn't been read yet.
const noopSubscribe = () => () => {};

export function useAuth() {
  const token = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  // false during SSR/first paint, true once mounted on the client — derived from
  // the store (no setState-in-effect) so there's no login flash before we've
  // read localStorage.
  const hydrated = useSyncExternalStore(noopSubscribe, () => true, () => false);

  function login(t: string) {
    try { localStorage.setItem(TOKEN_KEY, t); } catch {}
    emit();
  }

  function logout() {
    try { localStorage.removeItem(TOKEN_KEY); } catch {}
    emit();
  }

  return { token, hydrated, login, logout };
}
