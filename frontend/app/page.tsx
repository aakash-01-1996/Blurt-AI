"use client";

import AuthGate from "./auth";
import { AppShell } from "./components/AppShell";
import { useAuth } from "./hooks/useAuth";

export default function Home() {
  const { token, hydrated, login, logout } = useAuth();
  // Until the client has read localStorage, show a neutral splash instead of the
  // login screen — otherwise a logged-in user sees a login flash on every refresh.
  if (!hydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface" aria-hidden="true">
        <div className="w-8 h-8 rounded-full border-2 border-[#E5E5EA] border-t-[#0071E3] animate-spin" />
      </div>
    );
  }
  if (!token) return <AuthGate onAuth={login} />;
  return <AppShell token={token} onLogout={logout} />;
}
