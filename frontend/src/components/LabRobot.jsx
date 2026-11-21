import { useId } from "react";

const ROBOT_COLORS = {
  simple_ma: "#c8f37b",
  rsi: "#7bded6",
  momentum: "#f2ba8c",
};

/**
 * Decorative representation of a rules-based strategy. The state label is
 * supplied by the recorded simulation event; it is not a prediction.
 */
export default function LabRobot({ strategy, action = "READY", selected = false }) {
  const rawId = useId();
  const id = rawId.replace(/:/g, "");
  const color = ROBOT_COLORS[strategy] ?? ROBOT_COLORS.simple_ma;
  const active = action === "BUY" || action === "SELL";

  return (
    <div
      className={`lab-robot ${selected ? "is-selected" : ""} ${active ? "is-active" : ""}`}
      style={{ "--robot-accent": color }}
      aria-hidden="true"
    >
      <svg viewBox="0 0 240 224" fill="none" className="lab-robot-svg">
        <defs>
          <linearGradient id={`shell-${id}`} x1="45" y1="28" x2="193" y2="211" gradientUnits="userSpaceOnUse">
            <stop stopColor="#3d4b40" />
            <stop offset=".46" stopColor="#1e2a24" />
            <stop offset="1" stopColor="#101914" />
          </linearGradient>
          <linearGradient id={`glass-${id}`} x1="50" y1="75" x2="174" y2="150" gradientUnits="userSpaceOnUse">
            <stop stopColor="#151f1b" />
            <stop offset="1" stopColor="#070d0a" />
          </linearGradient>
          <radialGradient id={`glow-${id}`}>
            <stop stopColor={color} stopOpacity=".28" />
            <stop offset="1" stopColor={color} stopOpacity="0" />
          </radialGradient>
        </defs>
        <ellipse cx="120" cy="191" rx="104" ry="31" fill={`url(#glow-${id})`} />
        <g className="lab-robot-orbit" stroke={color} strokeOpacity=".26">
          <circle cx="120" cy="108" r="98" strokeDasharray="2 9" />
          <path d="M19 108h16M205 108h16M120 7v12M120 197v12" />
        </g>
        <g className="lab-robot-body">
          <path d="M92 28 96 15h48l4 13" stroke="#607568" strokeWidth="4" strokeLinejoin="round" />
          <path d="M120 15V4" stroke={color} strokeWidth="2" />
          <circle cx="120" cy="4" r="3" fill={color} />
          <path d="M72 169c5-13 17-19 30-21h36c13 2 25 8 30 21l8 25c-15 10-33 15-56 15s-41-5-56-15l8-25Z" fill={`url(#shell-${id})`} stroke="#607568" strokeWidth="2" />
          <path d="M93 161h54l10 36c-11 4-23 6-37 6s-26-2-37-6l10-36Z" fill="#111c16" stroke={color} strokeOpacity=".35" />
          <path d="M105 173h30M99 180h42M106 187h28" stroke={color} strokeOpacity=".55" strokeWidth="2" strokeLinecap="round" />
          <path d="M46 70c0-27 22-46 49-46h50c27 0 49 19 49 46v52c0 28-22 46-49 46H95c-27 0-49-18-49-46V70Z" fill={`url(#shell-${id})`} stroke="#677c6d" strokeWidth="2" />
          <path d="M42 82h-7v36h7M198 82h7v36h-7" stroke={color} strokeOpacity=".75" strokeWidth="4" strokeLinecap="round" />
          <path d="M56 81c0-15 13-26 28-26h72c15 0 28 11 28 26v35c0 15-13 26-28 26H84c-15 0-28-11-28-26V81Z" fill={`url(#glass-${id})`} stroke={color} strokeOpacity=".58" strokeWidth="1.5" />
          <path d="M65 65h110" stroke="#b8cab8" strokeOpacity=".3" />
          <path d="M77 124h86" stroke={color} strokeOpacity=".18" />
          <g fill={color} className="lab-robot-eyes">
            <rect x="76" y="91" width="28" height="7" rx="3.5" />
            <rect x="136" y="91" width="28" height="7" rx="3.5" />
          </g>
          {strategy === "rsi" && <path d="M92 109h8l5-11 8 19 8-15 6 7h21" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity=".75" />}
          {strategy === "momentum" && <path d="m91 115 14-10 12 6 23-17m-7 0h7v7" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity=".75" />}
          {strategy === "simple_ma" && <><path d="m87 112 15-4 15 2 17-9 16 2" stroke={color} strokeWidth="2" strokeLinecap="round" opacity=".8" /><path d="m87 117 15-2 15-4 17-2 16-3" stroke="#dcebd4" strokeWidth="1.5" strokeLinecap="round" opacity=".65" /></>}
          <rect x="103" y="33" width="34" height="4" rx="2" fill={color} fillOpacity=".65" />
          <path d="M68 147c12 8 26 12 52 12s40-4 52-12" stroke="#91a697" strokeOpacity=".3" />
        </g>
      </svg>
    </div>
  );
}
