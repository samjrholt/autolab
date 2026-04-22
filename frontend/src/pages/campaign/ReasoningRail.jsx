import { useMemo, useState } from "react";
import { formatTime } from "../../lib/api";

function kindLabel(kind) {
  if (!kind) return "";
  if (kind.startsWith("record.")) return kind.slice(7);
  if (kind.startsWith("campaign.")) return kind.slice(9);
  if (kind.startsWith("resource.")) return kind.slice(9);
  return kind;
}

function kindColor(kind) {
  if (!kind) return "var(--color-secondary)";
  if (kind.includes("claim") || kind.includes("interpret")) return "var(--color-accent)";
  if (kind.includes("failed") || kind.includes("error")) return "var(--color-status-red)";
  if (kind.includes("completed")) return "var(--color-status-green)";
  if (kind.includes("decision") || kind.includes("react")) return "var(--color-status-amber)";
  return "var(--color-secondary)";
}

export default function ReasoningRail({ events, campaignId, collapsed, onToggle }) {
  const filtered = useMemo(() => {
    if (!events) return [];
    const list = campaignId ? events.filter((e) => !e.campaign_id || e.campaign_id === campaignId) : events;
    return list.slice(-80).reverse();
  }, [events, campaignId]);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="btn-secondary"
        style={{ writingMode: "vertical-rl", height: "100%", padding: "10px 6px" }}
      >
        Reasoning ▸
      </button>
    );
  }

  return (
    <aside
      className="panel"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 400,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "10px 12px",
          borderBottom: "1px solid var(--color-line-strong)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: 0.07,
            color: "var(--color-muted)",
          }}
        >
          Reasoning
        </span>
        <button type="button" onClick={onToggle} className="btn-ghost" style={{ fontSize: 12 }}>
          ◂
        </button>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: 10 }}>
        {filtered.length === 0 ? (
          <div style={{ color: "var(--color-tertiary)", fontSize: 11, textAlign: "center", padding: 24 }}>
            No events yet. Claims and <code>react()</code> decisions will appear here.
          </div>
        ) : (
          filtered.map((e, i) => (
            <div
              key={i}
              style={{
                fontSize: 11,
                padding: "6px 4px",
                borderBottom: "1px solid var(--color-line)",
                color: "var(--color-muted)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: 6,
                  marginBottom: 2,
                }}
              >
                <span style={{ color: kindColor(e.kind), fontWeight: 600 }}>{kindLabel(e.kind)}</span>
                <span style={{ color: "var(--color-tertiary)", fontSize: 10, marginLeft: "auto" }}>
                  {formatTime(e.ts || e.timestamp)}
                </span>
              </div>
              <div style={{ fontSize: 11, color: "var(--color-muted)", lineHeight: 1.45 }}>
                {e.message ||
                  e.summary ||
                  e.reason ||
                  e.operation ||
                  (e.record_id ? `record ${e.record_id.slice(4, 12)}…` : "")}
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
