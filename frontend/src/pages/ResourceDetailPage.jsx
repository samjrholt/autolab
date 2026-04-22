import { useState } from "react";
import PageHeader from "../shell/PageHeader";

async function deleteResource(name) {
  const response = await fetch(`/resources/${encodeURIComponent(name)}`, { method: "DELETE" });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
}

function TagTable({ tags }) {
  const entries = Object.entries(tags || {});
  if (entries.length === 0) {
    return <p style={{ color: "var(--color-tertiary)", fontSize: 12 }}>No tags on this resource.</p>;
  }
  return (
    <table className="tbl" style={{ marginTop: 4 }}>
      <thead>
        <tr>
          <th style={{ width: 220 }}>Key</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([k, v]) => (
          <tr key={k}>
            <td style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-text)" }}>{k}</td>
            <td style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-muted)" }}>
              {typeof v === "object" ? JSON.stringify(v) : String(v)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ResourceDetailPage({ resource, refresh, onBack }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (!resource) {
    return (
      <div className="empty-state">
        <h3>Resource not found</h3>
        <button type="button" className="btn-secondary" onClick={onBack}>
          ← Back to Resources
        </button>
      </div>
    );
  }

  const handleDelete = async () => {
    if (!confirm(`Unregister resource "${resource.name}"? This does not delete any records it produced.`)) return;
    setBusy(true);
    setErr("");
    try {
      await deleteResource(resource.name);
      if (refresh) await refresh();
      onBack?.();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const tags = resource.tags || resource.capabilities || {};
  const live = resource.available ?? resource.live ?? true;

  return (
    <>
      <div style={{ marginBottom: 10 }}>
        <button type="button" className="btn-ghost" onClick={onBack} style={{ fontSize: 12 }}>
          ← Resources
        </button>
      </div>
      <PageHeader
        title={resource.name}
        description={resource.description || `Kind: ${resource.kind || "—"}`}
        primaryAction={
          <button type="button" onClick={handleDelete} disabled={busy} className="btn-secondary" style={{ color: "var(--color-status-red)", borderColor: "rgba(214, 102, 102, 0.3)" }}>
            {busy ? "Removing…" : "Unregister"}
          </button>
        }
      />

      {err ? (
        <div
          style={{
            marginBottom: 14,
            padding: 10,
            borderRadius: 5,
            background: "rgba(214, 102, 102, 0.08)",
            border: "1px solid rgba(214, 102, 102, 0.3)",
            fontSize: 12,
            color: "var(--color-status-red)",
          }}
        >
          {err}
        </div>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div className="panel" style={{ padding: 14 }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>
            Runtime
          </div>
          <div style={{ fontSize: 13, display: "grid", gap: 8 }}>
            <div>
              <span style={{ color: "var(--color-secondary)" }}>Kind:</span> {resource.kind || "—"}
            </div>
            <div>
              <span style={{ color: "var(--color-secondary)" }}>Backend:</span> {resource.backend || resource.type || "ssh_exec (default)"}
            </div>
            <div>
              <span style={{ color: "var(--color-secondary)" }}>State:</span> {resource.state || "idle"}
            </div>
            <div>
              <span style={{ color: "var(--color-secondary)" }}>Liveness:</span>{" "}
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: live ? "var(--color-status-green)" : "var(--color-status-red)" }}>
                <span className={`status-dot ${live ? "status-dot--green" : "status-dot--red"}`} />
                {live ? "live" : "unreachable"}
              </span>
            </div>
            {resource.asset_id ? (
              <div>
                <span style={{ color: "var(--color-secondary)" }}>Asset ID:</span> <code>{resource.asset_id}</code>
              </div>
            ) : null}
            {resource.wait_seconds ? (
              <div>
                <span style={{ color: "var(--color-secondary)" }}>Wait ETA:</span> {resource.wait_seconds}s
              </div>
            ) : null}
          </div>
        </div>

        <div className="panel" style={{ padding: 14 }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>
            Tags
          </div>
          <TagTable tags={tags} />
        </div>
      </div>

      {resource.typical_operation_durations && Object.keys(resource.typical_operation_durations).length ? (
        <div className="panel" style={{ padding: 14, marginTop: 14 }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>
            Typical operation durations
          </div>
          <table className="tbl">
            <thead>
              <tr><th>Operation</th><th>Seconds</th></tr>
            </thead>
            <tbody>
              {Object.entries(resource.typical_operation_durations).map(([op, s]) => (
                <tr key={op}>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{op}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-muted)" }}>{s}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  );
}
