import { useState } from "react";
import PageHeader from "../shell/PageHeader";
import { postJson } from "../lib/api";
import WorkflowCanvasEditor from "./designer/workflow/WorkflowCanvasEditor";
import NewCapabilityInline from "./designer/workflow/NewCapabilityInline";
import ResourceForm from "./designer/ResourceForm";
import CapabilityForm from "./designer/CapabilityForm";

/**
 * Claude-assisted designer for a single kind of entity.
 *
 * Kinds: "workflow" | "resource" | "capability". Each kind hits its
 * existing server endpoint — /workflows/design, /resources/design,
 * /capabilities/design — and then a POST to register the approved proposal.
 *
 * Workflows additionally support a "Build" mode backed by a React Flow
 * canvas: drag capabilities, connect data edges, edit step props.
 */

const KINDS = {
  workflow: {
    label: "Workflow",
    title: "New workflow",
    description:
      "Describe the multi-step procedure you want to run, or compose it directly on the canvas.",
    placeholder: "Sinter at 1100 C for 4 hours, then measure hysteresis, then export to RO-Crate…",
    designEndpoint: "/workflows/design",
    applyEndpoint: "/workflows",
    extractProposal: (r) => r.workflow,
    buildApplyBody: (w) => w,
    supportsCanvas: true,
  },
  resource: {
    label: "Resource",
    title: "Register resource",
    description:
      "Connection info lives here — a Resource IS the connection (SSH host, local subprocess, SLURM partition, MCP endpoint). Register manually for SSH/WSL, or let Claude draft from a description.",
    placeholder: "A WSL Ubuntu instance named wsl-dev on my laptop, 8 cores, A100 GPU, used for magnetic simulations…",
    designEndpoint: "/resources/design",
    applyEndpoint: "/resources",
    extractProposal: (r) => r.resource,
    buildApplyBody: (r) => r,
    supportsForm: true,
  },
  capability: {
    label: "Capability",
    title: "Add capability",
    description:
      "What the lab can do - a script, instrument routine, WebSocket command, MCP endpoint, or simulation. Claude drafts this by default; manual registration is still available.",
    placeholder: "A Python script at ~/code/my-sim I run with pixi run simulate that takes a config.yaml and writes results/loop.png…",
    designEndpoint: "/capabilities/design",
    applyEndpoint: "/capabilities/register",
    extractProposal: (r) => r.tool,
    buildApplyBody: (t) => t,
    supportsForm: true,
  },
};

function ProposalView({ proposal, kind }) {
  if (!proposal) return null;
  return (
    <div className="card" style={{ padding: 14, marginTop: 12 }}>
      <div
        style={{
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: 0.07,
          color: "var(--color-tertiary)",
          marginBottom: 8,
        }}
      >
        Proposed {kind}
      </div>
      <pre
        style={{
          background: "var(--color-panel)",
          border: "1px solid var(--color-line)",
          borderRadius: 4,
          padding: 12,
          fontSize: 11,
          color: "var(--color-muted)",
          overflowX: "auto",
          maxHeight: 320,
        }}
      >
        {JSON.stringify(proposal, null, 2)}
      </pre>
    </div>
  );
}

function DescribeMode({ config, status, refresh, registered, setRegistered }) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState(null);
  const [notes, setNotes] = useState("");
  const [questions, setQuestions] = useState([]);
  const [refinement, setRefinement] = useState("");
  const [readyToApply, setReadyToApply] = useState(true);
  const [error, setError] = useState("");
  const keyMissing = status && !status.claude_configured;

  const design = async (instruction = "") => {
    if (!input.trim() && !instruction.trim()) return;
    setBusy(true);
    setError("");
    if (!proposal) setProposal(null);
    setNotes("");
    setQuestions([]);
    setReadyToApply(true);
    setRegistered(false);
    try {
      const result = await postJson(config.designEndpoint, {
        text: input,
        previous: proposal || undefined,
        instruction: instruction.trim() || undefined,
      });
      const p = config.extractProposal(result);
      setProposal(p);
      setNotes(result.notes || "");
      setQuestions(result.questions || []);
      setReadyToApply(result.ready_to_apply !== false);
      setRefinement("");
      if (!p) setError("Claude returned no concrete proposal — try a more specific description.");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!proposal) return;
    setBusy(true);
    setError("");
    try {
      await postJson(config.applyEndpoint, config.buildApplyBody(proposal));
      setRegistered(true);
      if (refresh) await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  if (keyMissing) {
    return (
      <div className="panel empty-state">
        <h3>Anthropic API key not detected</h3>
        <p>
          The designer uses Claude to draft proposals. Set <code>ANTHROPIC_API_KEY</code> in
          your environment or <code>~/.autolab/env</code> and restart the lab.
        </p>
      </div>
    );
  }

  return (
    <div className="panel" style={{ padding: 16, maxWidth: 860 }}>
      <label
        style={{
          display: "block",
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: 0.07,
          color: "var(--color-tertiary)",
          marginBottom: 8,
        }}
      >
        Describe what you want
      </label>
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={config.placeholder}
        disabled={busy}
        rows={4}
        style={{
          width: "100%",
          background: "var(--color-canvas)",
          border: "1px solid var(--color-line-strong)",
          borderRadius: 5,
          padding: 10,
          color: "var(--color-text)",
          fontSize: 13,
          resize: "vertical",
          marginBottom: 10,
        }}
      />
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button type="button" onClick={() => design()} disabled={busy || !input.trim()} className="btn-primary">
          {busy && !proposal ? "Drafting…" : "Draft with Claude"}
        </button>
        {proposal && !registered ? (
          <button type="button" onClick={apply} disabled={busy || !readyToApply} className="btn-secondary">
            {busy ? "Registering…" : `Register ${config.label}`}
          </button>
        ) : null}
        {registered ? (
          <span style={{ color: "var(--color-status-green)", fontSize: 12 }}>
            ✓ {config.label} registered
          </span>
        ) : null}
      </div>

      {error ? (
        <div
          style={{
            marginTop: 12,
            padding: 10,
            borderRadius: 5,
            background: "rgba(214, 102, 102, 0.08)",
            border: "1px solid rgba(214, 102, 102, 0.3)",
            fontSize: 12,
            color: "var(--color-status-red)",
          }}
        >
          {error}
        </div>
      ) : null}

      {notes ? (
        <div
          style={{
            marginTop: 12,
            padding: 10,
            background: "var(--color-canvas)",
            borderRadius: 5,
            fontSize: 12,
            color: "var(--color-muted)",
          }}
        >
          {notes}
        </div>
      ) : null}

      {questions.length ? (
        <div
          style={{
            marginTop: 12,
            padding: 10,
            background: "rgba(232,176,98,0.08)",
            border: "1px solid rgba(232,176,98,0.28)",
            borderRadius: 5,
            fontSize: 12,
            color: "var(--color-secondary)",
          }}
        >
          {questions.map((question) => (
            <div key={question} style={{ marginBottom: 4 }}>{question}</div>
          ))}
        </div>
      ) : null}

      {proposal ? (
        <div
          style={{
            marginTop: 12,
            padding: 10,
            background: "var(--color-canvas)",
            border: "1px solid var(--color-line)",
            borderRadius: 5,
          }}
        >
          <label
            style={{
              display: "block",
              fontSize: 10,
              textTransform: "uppercase",
              letterSpacing: 0.07,
              color: "var(--color-tertiary)",
              marginBottom: 6,
            }}
          >
            Answer questions or refine the draft
          </label>
          <textarea
            value={refinement}
            onChange={(e) => setRefinement(e.target.value)}
            disabled={busy}
            rows={3}
            placeholder="Example: use the VM resource, make the final step optimize Hc, and keep the schema names exactly as registered."
            style={{
              width: "100%",
              background: "var(--color-panel)",
              border: "1px solid var(--color-line-strong)",
              borderRadius: 5,
              padding: 9,
              color: "var(--color-text)",
              fontSize: 12,
              resize: "vertical",
              marginBottom: 8,
            }}
          />
          <button
            type="button"
            onClick={() => design(refinement)}
            disabled={busy || !refinement.trim()}
            className="btn-secondary"
            style={{ fontSize: 12 }}
          >
            {busy ? "Updating…" : "Update proposal"}
          </button>
        </div>
      ) : null}

      <ProposalView proposal={proposal} kind={config.label} />
    </div>
  );
}

function BuildMode({ status, refresh, onDone, initial }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [inlineOpen, setInlineOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(true);

  const tools = status?.capabilities || status?.tools || [];

  const save = async (body) => {
    setSaving(true);
    setError("");
    try {
      await postJson("/workflows", body);
      if (refresh) await refresh();
      if (onDone) onDone();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
      {error ? (
        <div
          style={{
            background: "rgba(214,102,102,0.08)",
            borderBottom: "1px solid rgba(214,102,102,0.3)",
            color: "var(--color-status-red)",
            fontSize: 12,
            padding: "6px 12px",
          }}
        >
          {error}
        </div>
      ) : null}
      <WorkflowCanvasEditor
        initial={initial}
        tools={tools}
        saving={saving}
        pickerOpen={pickerOpen}
        onTogglePicker={() => setPickerOpen((v) => !v)}
        onSave={save}
        onCancel={onDone || (() => {})}
        onRequestNewCapability={() => setInlineOpen(true)}
      />
      <NewCapabilityInline
        open={inlineOpen}
        onClose={() => setInlineOpen(false)}
        claudeConfigured={!!status?.claude_configured}
        onRegistered={async () => {
          setInlineOpen(false);
          if (refresh) await refresh();
        }}
      />
    </div>
  );
}

export default function DesignerPage({ kind, status, refresh, onDone, initial }) {
  const config = KINDS[kind];
  if (!config) return null;

  // Workflows: default to Build when caps or initial exist.
  // Resources/Capabilities: default to Claude when configured, manual otherwise.
  const hasTools = (status?.capabilities || status?.tools || []).length > 0;
  const defaultMode = config.supportsCanvas && (initial || hasTools) ? "build"
    : config.supportsForm ? (status?.claude_configured ? "describe" : "form")
    : "describe";
  const [mode, setMode] = useState(defaultMode);
  const [registered, setRegistered] = useState(false);

  return (
    <>
      <PageHeader
        title={config.title}
        description={config.description}
        primaryAction={
          onDone ? (
            <button type="button" className="btn-ghost" onClick={onDone}>
              ← Back
            </button>
          ) : null
        }
      />

      <div style={{ display: "flex", gap: 4, marginBottom: 12 }}>
        {config.supportsForm ? (
          <button
            type="button"
            className={mode === "form" ? "btn-secondary" : "btn-ghost"}
            onClick={() => setMode("form")}
            style={{ fontSize: 12 }}
          >
            Register manually
          </button>
        ) : null}
        {config.supportsCanvas ? (
          <>
            <button
              type="button"
              className={mode === "describe" ? "btn-secondary" : "btn-ghost"}
              onClick={() => setMode("describe")}
              style={{ fontSize: 12 }}
            >
              Describe
            </button>
            <button
              type="button"
              className={mode === "build" ? "btn-secondary" : "btn-ghost"}
              onClick={() => setMode("build")}
              style={{ fontSize: 12 }}
            >
              Build
            </button>
          </>
        ) : (
          <button
            type="button"
            className={mode === "describe" ? "btn-secondary" : "btn-ghost"}
            onClick={() => setMode("describe")}
            style={{ fontSize: 12 }}
          >
            Describe with Claude
          </button>
        )}
      </div>

      {mode === "form" && kind === "resource" ? (
        <ResourceForm onDone={onDone} refresh={refresh} />
      ) : mode === "form" && kind === "capability" ? (
        <CapabilityForm onDone={onDone} refresh={refresh} />
      ) : config.supportsCanvas && mode === "build" ? (
        <BuildMode status={status} refresh={refresh} onDone={onDone} initial={initial} />
      ) : (
        <DescribeMode
          config={config}
          status={status}
          refresh={refresh}
          registered={registered}
          setRegistered={setRegistered}
        />
      )}
    </>
  );
}
