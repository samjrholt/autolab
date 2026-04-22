import { useState } from "react";

/**
 * Tab wrapper for builders that support both Manual and Claude-assisted paths.
 *
 * Props:
 *   manual      — node rendered when mode === "manual"
 *   withClaude  — node rendered when mode === "claude"
 *   defaultMode — "manual" | "claude" (default: "manual")
 *   claudeLabel — label for the Claude tab (default: "With Claude")
 *   onModeChange(mode) — optional callback
 */
export default function DualModeBuilder({
  manual,
  withClaude,
  defaultMode = "manual",
  claudeLabel = "With Claude",
  onModeChange,
}) {
  const [mode, setMode] = useState(defaultMode);

  const switchMode = (next) => {
    setMode(next);
    onModeChange?.(next);
  };

  const tabClass = (active) =>
    `bg-transparent border-none px-4 py-1.5 text-[13px] font-medium transition-colors ${
      active
        ? "text-white border-b border-white"
        : "text-[var(--color-tertiary)] hover:text-[var(--color-secondary)]"
    }`;

  return (
    <div>
      <div className="flex items-center gap-2 mb-5 border-b border-[var(--color-line)]">
        <button type="button" className={tabClass(mode === "manual")} onClick={() => switchMode("manual")}>
          Manual
        </button>
        <button type="button" className={tabClass(mode === "claude")} onClick={() => switchMode("claude")}>
          {claudeLabel}
        </button>
      </div>
      {mode === "manual" ? manual : withClaude}
    </div>
  );
}
