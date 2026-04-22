import { useMemo, useState } from "react";
import { motion } from "framer-motion";

import StatusIndicator from "./StatusIndicator";
import { sortByCreatedDesc } from "../lib/helpers";
import { formatTime } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

export default function Provenance({ records, loading, onSelectRecord, onFilter }) {
  const [filter, setFilter] = useState("");
  const [view, setView] = useState("list"); // "list" | "timeline"

  const sorted = useMemo(() => sortByCreatedDesc(records), [records]);

  const handleApply = () => {
    onFilter?.(filter.trim());
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleApply();
  };

  return (
    <div className="max-w-[960px] mx-auto px-8 pt-16 pb-24">
      {/* Header */}
      <motion.div
        className="mb-12"
        initial="hidden"
        animate="visible"
        variants={stagger}
      >
        <motion.h2
          variants={fadeInUp}
          className="text-[clamp(36px,5vw,56px)] font-normal leading-[0.95] tracking-[-0.03em] text-white mb-6"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Provenance
        </motion.h2>

        {/* Filter bar */}
        <motion.div variants={fadeInUp} className="flex gap-3">
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='outputs.score >= 0.5 and record.record_status = "completed"'
            className="flex-1 bg-transparent border border-[var(--color-line)] rounded-xl px-5 py-3 text-[14px] font-[var(--font-mono)] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors"
            style={{ fontFamily: "var(--font-mono)" }}
          />
          <button
            type="button"
            onClick={handleApply}
            className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-xl px-5 py-3 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all"
          >
            Apply
          </button>
        </motion.div>

        {/* View toggle + export */}
        <motion.div variants={fadeInUp} className="flex items-center justify-between mt-4">
          <div className="flex items-center gap-4">
            <ViewToggle active={view} onChange={setView} />
            <span className="text-[12px] text-[var(--color-tertiary)]">
              {sorted.length} record{sorted.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <ExportButton label="RO-Crate" href="/export/ro-crate" />
            <ExportButton label="PROV" href="/export/prov" />
          </div>
        </motion.div>
      </motion.div>

      {/* Content */}
      {loading ? (
        <p className="text-[var(--color-secondary)]">Loading…</p>
      ) : view === "list" ? (
        <RecordList records={sorted} onSelectRecord={onSelectRecord} />
      ) : (
        <Timeline records={sorted} onSelectRecord={onSelectRecord} />
      )}
    </div>
  );
}

function ViewToggle({ active, onChange }) {
  return (
    <div className="flex items-center gap-1 text-[12px]">
      {["list", "timeline"].map((v) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`bg-transparent border-none px-2 py-1 capitalize transition-colors ${
            active === v ? "text-white" : "text-[var(--color-tertiary)] hover:text-[var(--color-secondary)]"
          }`}
        >
          {v}
        </button>
      ))}
    </div>
  );
}

function ExportButton({ label, href }) {
  return (
    <a
      href={href}
      download
      className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--color-secondary)] hover:text-white transition-all no-underline"
    >
      {label}
    </a>
  );
}

function RecordList({ records, onSelectRecord }) {
  return (
    <motion.div
      className="flex flex-col"
      initial="hidden"
      animate="visible"
      variants={stagger}
    >
      {records.length === 0 && (
        <p className="text-[var(--color-tertiary)] py-12 text-center">No records match.</p>
      )}
      {records.map((record) => (
        <motion.button
          key={`${record.id}-${record.record_status}`}
          variants={fadeInUp}
          type="button"
          onClick={() => onSelectRecord?.(record)}
          className="flex items-center gap-4 px-0 py-3 bg-transparent border-none border-b border-b-[var(--color-line)] text-left hover:bg-white/[0.02] transition-colors w-full group"
        >
          <StatusIndicator
            status={record.record_status}
            pulse={record.record_status === "running"}
          />
          <span className="text-[15px] font-semibold text-white flex-1 truncate">
            {record.operation}
          </span>
          <span className="text-[12px] text-[var(--color-secondary)] shrink-0">
            {record.resource_name || record.campaign_id || "lab"}
          </span>
          <span
            className="text-[12px] text-[var(--color-tertiary)] shrink-0 tabular-nums"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            {formatTime(record.created_at)}
          </span>
          <span
            className="text-[11px] text-[var(--color-tertiary)] shrink-0 w-[140px] truncate"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            {(record.checksum || "").slice(0, 20)}
          </span>
          <span className="text-[var(--color-tertiary)] opacity-0 group-hover:opacity-100 transition-opacity">
            →
          </span>
        </motion.button>
      ))}
    </motion.div>
  );
}

function Timeline({ records, onSelectRecord }) {
  // Simple horizontal timeline — records as dots on a time axis
  const sorted = useMemo(() => [...records].sort((a, b) => new Date(a.created_at) - new Date(b.created_at)), [records]);
  if (!sorted.length) {
    return <p className="text-[var(--color-tertiary)] py-12 text-center">No records to display.</p>;
  }

  const earliest = new Date(sorted[0].created_at).getTime();
  const latest = new Date(sorted[sorted.length - 1].created_at).getTime();
  const span = latest - earliest || 1;

  return (
    <div className="relative pt-8 pb-16">
      {/* Axis line */}
      <div className="absolute left-0 right-0 top-1/2 h-px bg-[var(--color-line)]" />

      {/* Dots */}
      <div className="relative h-16">
        {sorted.map((record) => {
          const pct = ((new Date(record.created_at).getTime() - earliest) / span) * 100;
          return (
            <button
              key={record.id}
              type="button"
              onClick={() => onSelectRecord?.(record)}
              className="absolute -translate-x-1/2 -translate-y-1/2 top-1/2 bg-transparent border-none p-1 group"
              style={{ left: `${pct}%` }}
              title={`${record.operation} · ${formatTime(record.created_at)}`}
            >
              <StatusIndicator
                status={record.record_status}
                pulse={record.record_status === "running"}
                className="!w-3 !h-3 group-hover:!w-4 group-hover:!h-4 transition-all"
              />
            </button>
          );
        })}
      </div>

      {/* Time labels */}
      <div className="flex justify-between text-[11px] text-[var(--color-tertiary)] mt-4" style={{ fontFamily: "var(--font-mono)" }}>
        <span>{formatTime(sorted[0].created_at)}</span>
        <span>{formatTime(sorted[sorted.length - 1].created_at)}</span>
      </div>
    </div>
  );
}
