import PageHeader from "../shell/PageHeader";
import EmptyState from "../shell/EmptyState";

function tagChips(tags) {
  if (!tags || typeof tags !== "object") return null;
  const entries = Object.entries(tags);
  if (!entries.length) return <span style={{ color: "var(--color-tertiary)", fontSize: 12 }}>—</span>;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
      {entries.slice(0, 5).map(([k, v]) => (
        <span key={k} className="chip">
          {typeof v === "boolean" ? k : `${k}=${v}`}
        </span>
      ))}
      {entries.length > 5 ? (
        <span className="chip" style={{ opacity: 0.6 }}>+{entries.length - 5}</span>
      ) : null}
    </div>
  );
}

function backendBadge(backend) {
  return <span className="chip chip--accent">{backend || "ssh_exec"}</span>;
}

export default function ResourcesPage({ resources, onAddResource, onSelectResource }) {
  const has = resources && resources.length > 0;

  return (
    <>
      <PageHeader
        title="Resources"
        description="Named things that can execute Operations — WSL hosts, SSH remotes, SLURM partitions, local workers, MCP endpoints."
        primaryAction={
          <button type="button" onClick={onAddResource} className="btn-primary">
            + Register resource
          </button>
        }
      />

      {!has ? (
        <EmptyState
          title="No resources registered"
          description="Run the Setup Assistant to describe your lab in natural language, or register a resource manually."
          action={
            <button type="button" onClick={onAddResource} className="btn-primary">
              + Register resource
            </button>
          }
        />
      ) : (
        <div className="panel" style={{ overflow: "hidden" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Name</th>
                <th>Backend</th>
                <th>Liveness</th>
                <th>State</th>
                <th>Tags</th>
              </tr>
            </thead>
            <tbody>
              {resources.map((r) => {
                const name = r.name || r.resource || r.id;
                const live = r.available ?? r.live ?? true;
                const state = r.state || r.status || (live ? "idle" : "—");
                const tags = r.tags || r.capabilities || {};
                const backend = r.backend || r.capabilities?.backend || r.kind || r.type;
                return (
                  <tr key={name} onClick={() => onSelectResource?.(r)}>
                    <td style={{ color: "var(--color-text)" }}>{name}</td>
                    <td>{backendBadge(backend)}</td>
                    <td>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: live ? "var(--color-status-green)" : "var(--color-status-red)" }}>
                        <span className={`status-dot ${live ? "status-dot--green" : "status-dot--red"}`} />
                        {live ? "live" : "unreachable"}
                      </span>
                    </td>
                    <td style={{ color: "var(--color-muted)", fontSize: 12 }}>{state}</td>
                    <td>{tagChips(tags)}</td>
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
