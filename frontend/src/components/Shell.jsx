import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import TabNav from "./TabNav";
import StatusIndicator from "./StatusIndicator";
import { crossfade } from "../lib/motion";

export default function Shell({
  activeTab,
  onTabChange,
  connected,
  escalationCount = 0,
  onOpenEscalations,
  onOpenNewCampaign,
  onOpenSettings,
  children,
}) {
  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Top bar ─────────────────────────────────── */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-[var(--color-line)]">
        {/* Left: wordmark */}
        <span className="font-[var(--font-serif)] text-[24px] text-white tracking-[-0.03em]" style={{ fontFamily: "var(--font-serif)" }}>
          autolab
        </span>

        {/* Center: tabs */}
        <TabNav active={activeTab} onChange={onTabChange} />

        {/* Right: actions */}
        <div className="flex items-center gap-5">
          {/* Escalation badge */}
          {escalationCount > 0 && (
            <button
              type="button"
              onClick={onOpenEscalations}
              className="relative bg-transparent border-none text-[13px] font-medium text-[var(--color-status-amber)] hover:text-white transition-colors"
            >
              {escalationCount} pending
            </button>
          )}

          {/* New campaign */}
          <button
            type="button"
            onClick={onOpenNewCampaign}
            className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-full px-4 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all"
          >
            New campaign
          </button>

          {/* Settings */}
          <button
            type="button"
            onClick={onOpenSettings}
            className="bg-transparent border-none text-[var(--color-secondary)] hover:text-white transition-colors text-[16px]"
            title="Settings"
          >
            ⚙
          </button>

          {/* Connection */}
          <StatusIndicator
            status={connected ? "running" : "failed"}
            pulse={connected}
          />
        </div>
      </header>

      {/* ── Tab content ─────────────────────────────── */}
      <main className="flex-1 relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            {...crossfade}
            className="w-full"
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
