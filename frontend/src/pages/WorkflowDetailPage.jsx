import { useMemo, useState } from "react";

import PageHeader from "../shell/PageHeader";
import { postJson } from "../lib/api";

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

function RunModal({ workflow, open, onClose, onComplete }) {
  const stepIds = useMemo(
    () => (workflow?.steps || []).map((s, i) => s.id || s.step_id || `step-${i}`),
    [workflow],
  );
  const [overridesText, setOverridesText] = useState(() =>
    JSON.stringify(
      Object.fromEntries(stepIds.map((sid) => [sid, {}])),
      null,
      2,
    ),
  );
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  if (!open) return null;

  const submit = async () => {
    setRunning(true);
    setError("");
    setResult(null);
    let overrides = {};
    if (overridesText.trim()) {
      try {
        overrides = JSON.parse(overridesText);
      } catch (err) {
        setError(`Invalid JSON: ${err.message}`);
        setRunning(false);
        return;
      }
    }
    try {
      const res = await postJson(`/workflows/${encodeURIComponent(workflow.name)}/run`, {
        input_overrides: overrides,
      });
      setResult(res);
      onComplete?.(res);
    } catch (err) {
      setError(String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
      onClick={onClose}
    >
      <div
        className="panel"
        style={{ maxWidth: 640, width: "100%", padding: 20, maxHeight: "90vh", overflow: "auto" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ margin: 0, marginBottom: 6, fontSize: 20 }}>Run workflow</h3>
        <p style={{ color: "var(--color-secondary)", fontSize: 13, marginBottom: 12 }}>
          One-off execution of <code>{workflow.name}</code>. Each step runs with full provenance —
          this creates a new campaign-id for the run and writes Records to the ledger, but no
          Planner loop, no optimiser.
        </p>

        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 6 }}>
          Input overrides (JSON, per step_id)
        </div>
        <textarea
          value={overridesText}
          onChange={(e) => setOverridesText(e.target.value)}
          rows={10}
          spellCheck={false}
          style={{
            width: "100%",
            background: "transparent",
            border: "1px solid var(--color-line)",
            borderRadius: 8,
            padding: 10,
            color: "var(--color-text)",
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            resize: "vertical",
          }}
        />
        <p style={{ fontSize: 11, color: "var(--color-tertiary)", marginTop: 6 }}>
          Keys are step ids; values are dicts merged over the step's declared inputs. Leave an
          empty object <code>{"{}"}</code> to use the declared defaults.
        </p>

        {error && <p style={{ color: "var(--color-status-red)", fontSize: 13, marginTop: 10 }}>{error}</p>}

        {result && (
          <div
            style={{
              marginTop: 12,
              padding: 10,
              border: "1px solid var(--color-line)",
              borderRadius: 8,
              fontFamily: "var(--font-mono)",
              fontSize: 12,
            }}
          >
            <div style={{ color: result.ok ? "var(--color-status-green, #5ec27a)" : "var(--color-status-red)", marginBottom: 6 }}>
              {result.ok ? "✓ workflow completed" : "✗ workflow did not fully complete"}
            </div>
            <div style={{ color: "var(--color-secondary)", marginBottom: 6 }}>
              campaign_id: {result.campaign_id}
            </div>
            {(result.steps || []).map((s) => (
              <div key={s.record_id} style={{ padding: "4px 0", borderTop: "1px solid var(--color-line)" }}>
                <span style={{ color: "var(--color-accent)" }}>{s.operation}</span>
                {" · "}
                <span>{s.status}</span>
                {s.gate ? <span style={{ marginLeft: 8, color: "var(--color-tertiary)" }}>gate:{s.gate}</span> : null}
              </div>
            ))}
            {(result.skipped || []).length > 0 && (
              <div style={{ color: "var(--color-tertiary)", marginTop: 6 }}>skipped: {result.skipped.join(", ")}</div>
            )}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, marginTop: 16, justifyContent: "flex-end" }}>
          <button type="button" className="btn-ghost" onClick={onClose} disabled={running}>
            {result ? "Close" : "Cancel"}
          </button>
          <button type="button" className="btn-primary" onClick={submit} disabled={running}>
            {running ? "Running…" : "Run workflow"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function WorkflowDetailPage({ workflow, onBack, onEdit, refresh }) {
  const [runOpen, setRunOpen] = useState(false);

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
      <PageHeader
        title={workflow.name}
        description={workflow.description || `${steps.length} step${steps.length === 1 ? "" : "s"}`}
        primaryAction={
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn-primary" onClick={() => setRunOpen(true)}>
              ▶ Run workflow
            </button>
            {onEdit ? (
              <button type="button" className="btn-secondary" onClick={onEdit}>
                Edit on canvas
              </button>
            ) : null}
          </div>
        }
      />

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

      <RunModal
        workflow={workflow}
        open={runOpen}
        onClose={() => setRunOpen(false)}
        onComplete={() => refresh?.()}
      />
    </>
  );
}
