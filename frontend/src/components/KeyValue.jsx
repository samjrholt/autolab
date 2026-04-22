import { useState } from "react";

/** Render structured data as formatted key-value pairs — no raw JSON by default. */
export default function KeyValue({ data, depth = 0 }) {
  if (data == null) return null;
  if (typeof data !== "object") {
    return <span className="text-white">{String(data)}</span>;
  }
  const entries = Array.isArray(data)
    ? data.map((v, i) => [i, v])
    : Object.entries(data);

  return (
    <div className={depth > 0 ? "ml-4 border-l border-[var(--color-line)] pl-4" : ""}>
      {entries.map(([key, value]) => (
        <KVRow key={key} label={String(key)} value={value} depth={depth} />
      ))}
    </div>
  );
}

function KVRow({ label, value, depth }) {
  const isScalar = value == null || typeof value !== "object";
  const isNumber = typeof value === "number";
  const [expanded, setExpanded] = useState(depth < 1);

  if (isScalar) {
    return (
      <div className="flex items-baseline justify-between gap-4 py-1.5">
        <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--color-secondary)] shrink-0">
          {label}
        </span>
        {isNumber ? (
          <span className="text-[20px] font-semibold text-white tabular-nums">
            {formatSmart(value)}
          </span>
        ) : (
          <span className="text-[15px] text-white truncate text-right max-w-[60%]">
            {String(value ?? "--")}
          </span>
        )}
      </div>
    );
  }

  // Array or object — collapsible
  const count = Array.isArray(value) ? value.length : Object.keys(value).length;
  return (
    <div className="py-1.5">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--color-secondary)] hover:text-white transition-colors bg-transparent border-none p-0"
      >
        <span className="text-[10px]">{expanded ? "▾" : "▸"}</span>
        {label}
        <span className="text-[var(--color-tertiary)]">{count} items</span>
      </button>
      {expanded && <KeyValue data={value} depth={depth + 1} />}
    </div>
  );
}

function formatSmart(n) {
  if (Number.isNaN(n)) return "--";
  const abs = Math.abs(n);
  if (abs !== 0 && (abs < 1e-2 || abs >= 1e4)) return n.toExponential(3);
  if (Number.isInteger(n)) return n.toLocaleString();
  return n.toFixed(3);
}
