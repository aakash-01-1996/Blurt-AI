export function Logo({ dark = false }: { dark?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="w-9 h-9 rounded-xl bg-[#0071E3] flex items-center justify-center">
        <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
          <rect x="1.0" y="6.0" width="1.3" height="4" rx="0.65" fill="white" />
          <rect x="3.1" y="4.5" width="1.3" height="7" rx="0.65" fill="white" />
          <rect x="5.2" y="3.0" width="1.3" height="10" rx="0.65" fill="white" />
          <rect x="7.3" y="1.5" width="1.3" height="13" rx="0.65" fill="white" />
          <rect x="9.4" y="3.0" width="1.3" height="10" rx="0.65" fill="white" />
          <rect x="11.5" y="4.5" width="1.3" height="7" rx="0.65" fill="white" />
          <rect x="13.6" y="6.0" width="1.3" height="4" rx="0.65" fill="white" />
        </svg>
      </div>
      <span className={`font-display text-2xl font-bold ${dark ? "text-white" : "text-[#1D1D1F]"}`}>
        blurt
      </span>
    </div>
  );
}
