import { useMemo } from "react";

function statusColor(status) {
  return (
    {
      completed: "var(--color-status-green)",
      running: "var(--color-accent)",
      failed: "var(--color-status-red)",
      pending: "var(--color-secondary)",
    }[status] || "var(--color-tertiary)"
  );
}

function statusGlyph(status) {
  return { completed: "●", running: "◐", failed: "✕", pending: "○" }[status] || "○";
}

export default function PlanTree({ campaign, records }) {
  const tree = useMemo(() => {
    const byExperiment = new Map();
    for (const r of records || []) {
      const exp = r.experiment_id || "(default)";
      if (!byExperiment.has(exp)) byExperiment.set(exp, []);
      byExperiment.get(exp).push(r);
    }
    return Array.from(byExperiment.entries());
  }, [records]);

  return (
    <div style={{ padding: 8, fontSize: 12.5 }}>
      <div style={{ color: "var(--color-text)", marginBottom: 6 }}>
        <span style={{ color: "var(--color-accent)" }}>▾</span> Campaign ·{" "}
        <span style={{ color: "var(--color-muted)" }}>
          {campaign?.objective?.description || campaign?.name || campaign?.campaign_id || "—"}
        </span>
      </div>
      {tree.length === 0 ? (
        <div style={{ color: "var(--color-tertiary)", paddingLeft: 14, fontSize: 11 }}>
          no records yet
        </div>
      ) : (
        tree.map(([expId, recs]) => (
          <div key={expId} style={{ paddingLeft: 14, marginBottom: 6 }}>
            <div style={{ color: "var(--color-muted)", marginBottom: 3 }}>
              <span>▾</span> {expId === "(default)" ? "Experiment" : expId.slice(0, 12) + "…"}
            </div>
            <div style={{ paddingLeft: 16 }}>
              {recs.slice(0, 20).map((r) => (
                <div
                  key={r.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    color: "var(--color-muted)",
                    fontSize: 11.5,
                    padding: "1px 0",
                  }}
                >
                  <span style={{ color: statusColor(r.status), width: 12 }}>
                    {statusGlyph(r.status)}
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)" }}>{r.operation || "op"}</span>
                </div>
              ))}
              {recs.length > 20 ? (
                <div style={{ color: "var(--color-tertiary)", fontSize: 11 }}>
                  + {recs.length - 20} more
                </div>
              ) : null}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
