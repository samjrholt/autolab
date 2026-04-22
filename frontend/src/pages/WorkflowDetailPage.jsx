import PageHeader from "../shell/PageHeader";

function StepCard({ step, index }) {
  return (
    <div className="card" style={{ padding: 12, marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span
          style={{
            background: "var(--color-accent-soft)",
            color: "var(--color-accent)",
            fontSize: 10,
            padding: "2px 6px",
            borderRadius: 3,
            fontFamily: "var(--font-mono)",
          }}
        >
          {index + 1}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--color-text)" }}>
          {step.operation || step.capability || step.name || "step"}
        </span>
      </div>
      {step.description ? (
        <div style={{ fontSize: 12, color: "var(--color-muted)", marginBottom: 6 }}>{step.description}</div>
      ) : null}
      {step.inputs ? (
        <div style={{ fontSize: 11, color: "var(--color-secondary)", fontFamily: "var(--font-mono)" }}>
          inputs: {JSON.stringify(step.inputs).slice(0, 200)}
        </div>
      ) : null}
      {step.input_mappings ? (
        <div style={{ fontSize: 11, color: "var(--color-secondary)", fontFamily: "var(--font-mono)", marginTop: 4 }}>
          maps: {JSON.stringify(step.input_mappings).slice(0, 200)}
        </div>
      ) : null}
      {step.acceptance ? (
        <div style={{ fontSize: 11, color: "var(--color-accent)", fontFamily: "var(--font-mono)", marginTop: 4 }}>
          acceptance: {JSON.stringify(step.acceptance)}
        </div>
      ) : null}
    </div>
  );
}

export default function WorkflowDetailPage({ workflow, onBack }) {
  if (!workflow) {
    return (
      <div className="empty-state">
        <h3>Workflow not found</h3>
        <button type="button" className="btn-secondary" onClick={onBack}>
          ← Back to Workflows
        </button>
      </div>
    );
  }

  const steps = workflow.steps || [];

  return (
    <>
      <div style={{ marginBottom: 10 }}>
        <button type="button" className="btn-ghost" onClick={onBack} style={{ fontSize: 12 }}>
          ← Workflows
        </button>
      </div>
      <PageHeader title={workflow.name} description={workflow.description || `${steps.length} step${steps.length === 1 ? "" : "s"}`} />

      <div className="panel" style={{ padding: 14, maxWidth: 880 }}>
        <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 10 }}>
          Steps
        </div>
        {steps.length === 0 ? (
          <p style={{ color: "var(--color-tertiary)", fontSize: 12 }}>No steps defined.</p>
        ) : (
          steps.map((s, i) => <StepCard key={i} step={s} index={i} />)
        )}
      </div>
    </>
  );
}
