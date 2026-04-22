import { useMemo, useState } from "react";
import PageHeader from "../shell/PageHeader";
import EmptyState from "../shell/EmptyState";
import { formatTime } from "../lib/api";

function statusChip(status) {
  const map = {
    completed: "var(--color-status-green)",
    running: "var(--color-status-amber)",
    failed: "var(--color-status-red)",
    pending: "var(--color-secondary)",
    soft_fail: "var(--color-status-amber)",
  };
  const color = map[status] || "var(--color-secondary)";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color, fontSize: 12 }}>
      <span className="status-dot" style={{ background: color }} /> {status || "—"}
    </span>
  );
}

export default function LedgerPage({ records, onSelectRecord, campaignIdFilter }) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const byCampaign = campaignIdFilter
      ? records.filter((r) => r.campaign_id === campaignIdFilter)
      : records;
    if (!query.trim()) return byCampaign;
    const q = query.trim().toLowerCase();
    return byCampaign.filter(
      (r) =>
        r.operation?.toLowerCase().includes(q) ||
        r.id?.toLowerCase().includes(q) ||
        r.module?.toLowerCase().includes(q) ||
        r.status?.toLowerCase().includes(q),
    );
  }, [records, query, campaignIdFilter]);

  if (!records || records.length === 0) {
    return (
      <>
        {!campaignIdFilter ? (
          <PageHeader
            title="Ledger"
            description="Append-only, hashed record of every Operation this lab has ever run. Each row is a Record; click for inputs, outputs, artefacts, and lineage."
          />
        ) : null}
        <EmptyState
          title="The ledger is empty"
          description="Records appear here as Operations run. Start a campaign to see the stream."
        />
      </>
    );
  }

  return (
    <>
      {!campaignIdFilter ? (
        <PageHeader
          title="Ledger"
          description="Append-only, hashed record of every Operation this lab has ever run. Each row is a Record; click for inputs, outputs, artefacts, and lineage."
        >
          <input
            type="text"
            placeholder="Filter…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{
              background: "var(--color-panel)",
              border: "1px solid var(--color-line-strong)",
              borderRadius: 5,
              padding: "6px 10px",
              fontSize: 13,
              color: "var(--color-text)",
              width: 220,
            }}
          />
        </PageHeader>
      ) : null}

      <div className="panel" style={{ overflow: "hidden" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 120 }}>Time</th>
              <th>Operation</th>
              <th>Status</th>
              <th>Module</th>
              <th>Campaign</th>
              <th style={{ width: 110 }}>Hash</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.id} onClick={() => onSelectRecord?.(r)}>
                <td style={{ color: "var(--color-secondary)", fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
                  {formatTime(r.finalised_at || r.created_at)}
                </td>
                <td style={{ color: "var(--color-text)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                  {r.operation || "—"}
                </td>
                <td>{statusChip(r.status)}</td>
                <td style={{ color: "var(--color-muted)", fontSize: 12 }}>{r.module || "—"}</td>
                <td style={{ color: "var(--color-muted)", fontSize: 11, fontFamily: "var(--font-mono)" }}>
                  {r.campaign_id ? r.campaign_id.slice(0, 12) + "…" : "—"}
                </td>
                <td style={{ color: "var(--color-tertiary)", fontSize: 11, fontFamily: "var(--font-mono)" }}>
                  {r.id ? r.id.slice(4, 14) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
