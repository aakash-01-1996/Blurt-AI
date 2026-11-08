"use client";

import { Page } from "../types";

const NAV_ITEMS: { page: Page; label: string; icon: React.ReactNode }[] = [
  {
    page: "record",
    label: "Record",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <rect x="6" y="2" width="6" height="10" rx="3" stroke="currentColor" strokeWidth="1.6" />
        <path d="M2.5 9.5A6.5 6.5 0 0 0 15.5 9.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <line x1="9" y1="16" x2="9" y2="12.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    page: "review",
    label: "Review inbox",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M2 5.5 9 10l7-4.5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <rect x="2" y="3.5" width="14" height="11" rx="2" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    page: "work-log",
    label: "Work log",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <rect x="3" y="2.5" width="12" height="13" rx="2" stroke="currentColor" strokeWidth="1.6" />
        <path d="M6 6h6M6 9h6M6 12h3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    page: "tasks",
    label: "Tasks",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <rect x="2.5" y="2.5" width="13" height="13" rx="3" stroke="currentColor" strokeWidth="1.6" />
        <path d="M6 9l2 2 4-4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    page: "notes",
    label: "Notes",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M3 3.5A1.5 1.5 0 0 1 4.5 2h6.5l4 4V14.5A1.5 1.5 0 0 1 13.5 16h-9A1.5 1.5 0 0 1 3 14.5v-11Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M10.5 2.2V6h3.8" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    page: "lists",
    label: "Lists",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M6.5 4.5h9M6.5 9h9M6.5 13.5h9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="2.8" cy="4.5" r="1.1" fill="currentColor" />
        <circle cx="2.8" cy="9" r="1.1" fill="currentColor" />
        <circle cx="2.8" cy="13.5" r="1.1" fill="currentColor" />
      </svg>
    ),
  },
  {
    page: "settings",
    label: "Settings",
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M2.5 5.5h9M2.5 12.5h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="13.5" cy="5.5" r="2" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="9" cy="12.5" r="2" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
];

interface SidebarProps {
  activePage: Page;
  onNavigate: (page: Page) => void;
  reviewCount: number;
  onLogout: () => void;
}

export function Sidebar({ activePage, onNavigate, reviewCount, onLogout }: SidebarProps) {
  return (
    <aside className="w-[220px] min-h-screen bg-surface flex flex-col border-r border-[#E5E5EA] shrink-0">
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-[10px] bg-[#0071E3] flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1.0" y="6.0" width="1.3" height="4" rx="0.65" fill="white" />
              <rect x="3.1" y="4.5" width="1.3" height="7" rx="0.65" fill="white" />
              <rect x="5.2" y="3.0" width="1.3" height="10" rx="0.65" fill="white" />
              <rect x="7.3" y="1.5" width="1.3" height="13" rx="0.65" fill="white" />
              <rect x="9.4" y="3.0" width="1.3" height="10" rx="0.65" fill="white" />
              <rect x="11.5" y="4.5" width="1.3" height="7" rx="0.65" fill="white" />
              <rect x="13.6" y="6.0" width="1.3" height="4" rx="0.65" fill="white" />
            </svg>
          </div>
          <span className="font-display text-xl font-bold text-[#1D1D1F]">blurt</span>
        </div>
      </div>

      <nav className="flex flex-col gap-1 px-3 flex-1">
        {NAV_ITEMS.map(({ page, label, icon }) => {
          const active = activePage === page;
          const badge = page === "review" && reviewCount > 0 ? reviewCount : null;
          return (
            <button
              key={page}
              onClick={() => onNavigate(page)}
              className={`flex items-center gap-3 w-full text-left px-3 py-2.5 rounded-[10px] text-[15px] font-semibold transition-colors ${
                active
                  ? "bg-[#0071E3]/10 text-[#0071E3]"
                  : "text-[#6E6E73] hover:bg-raised hover:text-[#1D1D1F]"
              }`}
            >
              <span className={active ? "text-[#0071E3]" : "text-[#A3A7B2]"}>{icon}</span>
              <span className="flex-1">{label}</span>
              {badge !== null && (
                <span className="text-[11px] font-bold bg-[#0071E3] text-white rounded-full min-w-5 h-5 px-1.5 flex items-center justify-center leading-none">
                  {badge > 9 ? "9+" : badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="px-3 pb-10 pt-2">
        <button
          onClick={onLogout}
          className="flex items-center gap-2.5 w-full text-left px-3 py-2.5 rounded-[10px] text-sm font-semibold text-[#6E6E73] bg-raised border border-[#E5E5EA] shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:bg-[#E8E8ED] hover:text-[#1D1D1F] transition-colors"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" className="text-[#A3A7B2]">
            <path d="M7 15.5H4a1.5 1.5 0 0 1-1.5-1.5V4A1.5 1.5 0 0 1 4 2.5h3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            <path d="M11 12l3-3-3-3M14 9H6.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Log out
        </button>
      </div>
    </aside>
  );
}
