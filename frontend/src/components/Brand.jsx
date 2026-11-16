export function BrandMark({ className = "" }) {
  return (
    <svg className={className} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <path d="M20 3 3 34h8.6L20 18.4 28.4 34H37L20 3Z" fill="currentColor" />
      <path d="M15.4 27.8h9.2L20 19.4l-4.6 8.4Z" fill="#101713" />
    </svg>
  );
}

const paths = {
  admin: <><rect x="4" y="4" width="7" height="7" rx="1" /><rect x="13" y="4" width="7" height="7" rx="1" /><rect x="4" y="13" width="7" height="7" rx="1" /><rect x="13" y="13" width="7" height="7" rx="1" /></>,
  dashboard: <><path d="M4 19V9l8-5 8 5v10H4Z" /><path d="M9 19v-6h6v6" /></>,
  arena: <><path d="M4 17.5 9 12l3 2.5L20 6" /><path d="M15.5 6H20v4.5" /><path d="M4 20h16" /></>,
  leaderboard: <><path d="M8 20v-7h3v7M13 20V7h3v13M18 20v-9h3v9M3 20h18" /></>,
  history: <><circle cx="12" cy="12" r="8" /><path d="M12 7v5l3.5 2" /></>,
  tokenomics: <><circle cx="12" cy="12" r="8" /><path d="M9.5 8.5h3.2a2 2 0 0 1 0 4h-1.4a2 2 0 0 0 0 4h3.2M12 6.5v11" /></>,
  governance: <><path d="m4 9 8-5 8 5H4ZM6 10v7m4-7v7m4-7v7m4-7v7M4 20h16M5 17h14" /></>,
  tech: <><rect x="4" y="6" width="16" height="13" rx="2" /><path d="M9 6V4h6v2M8 11h.01M16 11h.01M8 15h8" /></>,
  market: <><path d="M4 19h16M5 16l4-5 4 3 6-8" /><path d="M15 6h4v4" /></>,
};

export function NavIcon({ name }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}
