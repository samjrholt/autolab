import PageHeader from "../shell/PageHeader";
import EmptyState from "../shell/EmptyState";

export default function CapabilitiesPage({ tools, onRegister }) {
  const has = tools && tools.length > 0;

  return (
    <>
      <PageHeader
        title="Capabilities"
        description="What this lab can do. Each capability is a scientist-shaped noun (`sintering`, `micromagnetics_hysteresis`, `shell_command`) backed by a declaration and an adapter."
        primaryAction={
          <button type="button" onClick={onRegister} className="btn-primary">
            + Add capability
          </button>
        }
      />

      {!has ? (
        <EmptyState
          title="No capabilities registered"
          description="Work with the Setup Assistant to turn a script, repo, or MCP server into a reusable capability."
          action={
            <button type="button" onClick={onRegister} className="btn-primary">
              + Add capability
            </button>
          }
        />
      ) : (
        <div className="panel" style={{ overflow: "hidden" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Capability</th>
                <th>Module</th>
                <th>Version</th>
                <th>Resource kind</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {tools.map((t) => {
                const isExample = t.source?.startsWith?.("example:");
                return (
                  <tr key={t.name || t.capability}>
                    <td style={{ color: "var(--color-text)", fontFamily: "var(--font-mono)", fontSize: 12 }}>
                      {t.capability || t.name}
                      {isExample ? (
                        <span className="chip chip--example" style={{ marginLeft: 8 }}>example</span>
                      ) : null}
                    </td>
                    <td style={{ color: "var(--color-muted)", fontSize: 12 }}>{t.module || "—"}</td>
                    <td style={{ color: "var(--color-muted)", fontSize: 12 }}>{t.version || "—"}</td>
                    <td style={{ color: "var(--color-muted)", fontSize: 12 }}>{t.resource_kind || "any"}</td>
                    <td style={{ color: "var(--color-secondary)", fontSize: 12 }}>{t.source || "manual"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
