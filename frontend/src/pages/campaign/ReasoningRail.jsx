import { useMemo, useState } from "react";
import { formatTime } from "../../lib/api";
import { buildHashIndex, parseCitations, recordTooltip } from "../../utils/citeHash";

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

/**
 * Render a text string with 0x-prefixed record-hash citations highlighted.
 * Each match is wrapped in an amber monospace span with a tooltip.
 * Clicking a known hash calls onCiteClick(record).
 */
function CitedText({ text, hashIndex, onCiteClick }) {
  const parts = useMemo(() => parseCitations(text, hashIndex), [text, hashIndex]);
  if (!parts || parts.length === 0) return null;
  return (
    <>
      {parts.map((part, i) => {
        if (typeof part === "string") return <span key={i}>{part}</span>;
        const { hash, record } = part;
        const found = record !== null;
        return (
          <span
            key={i}
            title={recordTooltip(record)}
            onClick={found && onCiteClick ? () => onCiteClick(record) : undefined}
            style={{
              fontFamily: "monospace",
              fontSize: "0.9em",
              background: found ? "rgba(245, 158, 11, 0.18)" : "rgba(156, 163, 175, 0.18)",
              color: found ? "var(--color-status-amber, #f59e0b)" : "var(--color-tertiary, #9ca3af)",
              borderRadius: 3,
              padding: "0 3px",
              cursor: found && onCiteClick ? "pointer" : "default",
              textDecoration: found ? "underline dotted" : "none",
              whiteSpace: "nowrap",
            }}
          >
            {hash}
          </span>
        );
      })}
    </>
  );
}

export default function ReasoningRail({ events, campaignId, records, collapsed, onToggle, onCiteClick }) {
  const filtered = useMemo(() => {
    if (!events) return [];
    const list = campaignId
      ? events.filter((e) => {
        const payload = e.payload || {};
        const record = e.record || payload.record || {};
        const eventCampaign = e.campaign_id || payload.campaign_id || record.campaign_id;
        return !eventCampaign || eventCampaign === campaignId;
      })
      : events;
    return list.slice(-80).reverse();
  }, [events, campaignId]);

  const hashIndex = useMemo(() => buildHashIndex(records), [records]);

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
          filtered.map((e, i) => {
            const payload = e.payload || {};
            const record = e.record || payload.record || {};
            const body = payload.body || {};
            const rawText =
              e.message ||
              payload.message ||
              e.summary ||
              payload.summary ||
              e.reason ||
              payload.reason ||
              body.reason ||
              body.action ||
              e.operation ||
              payload.operation ||
              record.operation ||
              (e.record_id ? `record ${e.record_id.slice(4, 12)}…` : "");
            return (
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
                  <CitedText
                    text={rawText}
                    hashIndex={hashIndex}
                    onCiteClick={onCiteClick}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
