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
    return <p style={{ color: "var(--color-tertiary)", fontSize: 12 }}>None.</p>;
  }
  return (
    <table className="tbl" style={{ marginTop: 4 }}>
      <thead>
        <tr>
          <th style={{ width: 200 }}>Key</th>
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

function ConnectionPanel({ resource }) {
  const backend = resource.backend || resource.type || resource.kind || "local";
  const rows = [];

  if (backend === "ssh_exec" || backend === "ssh") {
    rows.push(["Host", resource.host || "(from ~/.ssh/config alias)"]);
    if (resource.user) rows.push(["User", resource.user]);
    if (resource.port) rows.push(["Port", String(resource.port)]);
    rows.push(["Remote root", resource.remote_root || "~/.autolab-work"]);
    rows.push(["Auth", "ssh-agent / ~/.ssh/config"]);
  } else if (backend === "local" || backend === "wsl") {
    rows.push(["Backend", "local subprocess"]);
    rows.push(["Working dir", resource.working_dir || "~/.autolab-work"]);
    if (resource.shell) rows.push(["Shell", resource.shell]);
  } else if (backend === "slurm") {
    rows.push(["Host", resource.host || "localhost"]);
    rows.push(["Partition", resource.partition || "(default)"]);
    rows.push(["Nodes", String(resource.nodes || 1)]);
  } else if (backend === "mcp") {
    rows.push(["Endpoint", resource.endpoint || "(not set)"]);
  } else {
    rows.push(["Backend", backend]);
  }

  if (!rows.length) return <p style={{ color: "var(--color-tertiary)", fontSize: 12 }}>No connection details stored.</p>;

  return (
    <table style={{ fontSize: 12, width: "100%", borderCollapse: "collapse" }}>
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k}>
            <td style={{ color: "var(--color-secondary)", paddingRight: 14, paddingBottom: 6, whiteSpace: "nowrap" }}>{k}</td>
            <td style={{ color: "var(--color-text)", fontFamily: "var(--font-mono)", paddingBottom: 6 }}>{v}</td>
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
  const backend = resource.backend || resource.type || "local";

  return (
    <>
      <div style={{ marginBottom: 10 }}>
        <button type="button" className="btn-ghost" onClick={onBack} style={{ fontSize: 12 }}>
          ← Resources
        </button>
      </div>
      <PageHeader
        title={resource.name}
        description={resource.description || `${backend} resource`}
        primaryAction={
          <button type="button" onClick={handleDelete} disabled={busy} className="btn-secondary" style={{ color: "var(--color-status-red)", borderColor: "rgba(214, 102, 102, 0.3)" }}>
            {busy ? "Removing…" : "Unregister"}
          </button>
        }
      />

      {err ? (
        <div style={{ marginBottom: 14, padding: 10, borderRadius: 5, background: "rgba(214,102,102,0.08)", border: "1px solid rgba(214,102,102,0.3)", fontSize: 12, color: "var(--color-status-red)" }}>
          {err}
        </div>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div className="panel" style={{ padding: 14 }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>Runtime</div>
          <div style={{ fontSize: 13, display: "grid", gap: 8 }}>
            <div><span style={{ color: "var(--color-secondary)" }}>Backend:</span> <code style={{ fontSize: 12 }}>{backend}</code></div>
            <div><span style={{ color: "var(--color-secondary)" }}>State:</span> {resource.state || "idle"}</div>
            <div>
              <span style={{ color: "var(--color-secondary)" }}>Liveness:</span>{" "}
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: live ? "var(--color-status-green)" : "var(--color-status-red)" }}>
                <span className={`status-dot ${live ? "status-dot--green" : "status-dot--red"}`} />
                {live ? "live" : "unreachable"}
              </span>
            </div>
          </div>
        </div>

        <div className="panel" style={{ padding: 14 }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>Connection</div>
          <ConnectionPanel resource={resource} />
        </div>
      </div>

      {Object.keys(tags).length > 0 ? (
        <div className="panel" style={{ padding: 14, marginTop: 14 }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>Tags</div>
          <TagTable tags={tags} />
        </div>
      ) : null}

      {resource.typical_operation_durations && Object.keys(resource.typical_operation_durations).length ? (
        <div className="panel" style={{ padding: 14, marginTop: 14 }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>Typical operation durations</div>
          <table className="tbl">
            <thead><tr><th>Operation</th><th>Seconds</th></tr></thead>
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
