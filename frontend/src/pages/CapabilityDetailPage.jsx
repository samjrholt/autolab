import PageHeader from "../shell/PageHeader";

function SchemaTable({ title, schema }) {
  const entries = Object.entries(schema || {});
  if (!entries.length) return null;
  return (
    <div className="panel" style={{ padding: 14, marginBottom: 12 }}>
      <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>
        {title}
      </div>
      <table className="tbl">
        <thead>
          <tr>
            <th>Field</th>
            <th>Type</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, spec]) => (
            <tr key={name}>
              <td style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-text)" }}>{name}</td>
              <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--color-muted)" }}>
                {spec?.type || spec?.kind || "—"}
              </td>
              <td style={{ fontSize: 11, color: "var(--color-secondary)" }}>
                {spec?.description || (spec?.default !== undefined ? `default: ${JSON.stringify(spec.default)}` : "—")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CapabilityDetailPage({ tool, onBack }) {
  if (!tool) {
    return (
      <div className="empty-state">
        <h3>Capability not found</h3>
        <button type="button" className="btn-secondary" onClick={onBack}>
          ← Back to Capabilities
        </button>
      </div>
    );
  }

  return (
    <>
      <div style={{ marginBottom: 10 }}>
        <button type="button" className="btn-ghost" onClick={onBack} style={{ fontSize: 12 }}>
          ← Capabilities
        </button>
      </div>
      <PageHeader title={tool.capability || tool.name} description={`Module ${tool.module || "—"} · version ${tool.version || "—"}`} />

      <div className="panel" style={{ padding: 14, marginBottom: 12 }}>
        <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>
          Declaration
        </div>
        <div style={{ display: "grid", gap: 8, fontSize: 13 }}>
          <div>
            <span style={{ color: "var(--color-secondary)" }}>Capability:</span>{" "}
            <code>{tool.capability || tool.name}</code>
          </div>
          <div>
            <span style={{ color: "var(--color-secondary)" }}>Resource kind:</span>{" "}
            {tool.resource_kind || "any"}
          </div>
          <div>
            <span style={{ color: "var(--color-secondary)" }}>Produces sample:</span>{" "}
            {tool.produces_sample ? "yes" : "no"}
          </div>
          <div>
            <span style={{ color: "var(--color-secondary)" }}>Destructive:</span>{" "}
            {tool.destructive ? "yes" : "no"}
          </div>
          <div>
            <span style={{ color: "var(--color-secondary)" }}>Typical duration:</span>{" "}
            {tool.typical_duration_s || "—"}s
          </div>
          {tool.declaration_hash ? (
            <div>
              <span style={{ color: "var(--color-secondary)" }}>Declaration hash:</span>{" "}
              <code style={{ fontSize: 11 }}>{tool.declaration_hash.slice(0, 20)}…</code>
            </div>
          ) : null}
        </div>
      </div>

      <SchemaTable title="Inputs" schema={tool.inputs} />
      <SchemaTable title="Outputs" schema={tool.outputs} />
    </>
  );
}
