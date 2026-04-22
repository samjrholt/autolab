import PageHeader from "../shell/PageHeader";
import EmptyState from "../shell/EmptyState";

export default function WorkflowsPage({ workflows, onCreate, onSelectWorkflow }) {
  const has = workflows && workflows.length > 0;

  return (
    <>
      <PageHeader
        title="Workflows"
        description="Reusable recipes composing Capabilities into a DAG. A Campaign can instantiate a Workflow many times with different inputs."
        primaryAction={
          <button type="button" onClick={onCreate} className="btn-primary">
            + New workflow
          </button>
        }
      />

      {!has ? (
        <EmptyState
          title="No workflows yet"
          description="Compose registered Capabilities into a reusable recipe. Workflows are how you package a multi-step scientific procedure."
          action={
            <button type="button" onClick={onCreate} className="btn-primary">
              + New workflow
            </button>
          }
        />
      ) : (
        <div className="panel" style={{ overflow: "hidden" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Name</th>
                <th>Steps</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {workflows.map((w) => (
                <tr key={w.name} onClick={() => onSelectWorkflow?.(w)}>
                  <td style={{ color: "var(--color-text)" }}>{w.name}</td>
                  <td style={{ color: "var(--color-muted)", fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
                    {w.steps?.length ?? w.step_count ?? "—"}
                  </td>
                  <td style={{ color: "var(--color-secondary)", fontSize: 12 }}>{w.description || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
