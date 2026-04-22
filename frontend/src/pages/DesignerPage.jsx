import { useState } from "react";
import PageHeader from "../shell/PageHeader";
import { postJson } from "../lib/api";

/**
 * Claude-assisted designer for a single kind of entity.
 *
 * Kinds: "workflow" | "resource" | "capability". Each kind hits its
 * existing server endpoint — /workflows/design, /resources/design,
 * /tools/design — and then a POST to register the approved proposal.
 */

const KINDS = {
  workflow: {
    label: "Workflow",
    title: "New workflow",
    description:
      "Describe the multi-step procedure you want to run. Claude will propose a workflow template; nothing registers without your approval.",
    placeholder: "Sinter at 1100 C for 4 hours, then measure hysteresis, then export to RO-Crate…",
    designEndpoint: "/workflows/design",
    applyEndpoint: "/workflows",
    extractProposal: (r) => r.workflow,
    buildApplyBody: (w) => w,
  },
  resource: {
    label: "Resource",
    title: "Register resource",
    description:
      "Describe a piece of equipment, a compute host, or a simulator. Claude drafts a Resource declaration — name, kind, capabilities, typical durations.",
    placeholder: "A WSL host named wsl-dev with 8 cores and an A100 GPU, used for magnetic simulations…",
    designEndpoint: "/resources/design",
    applyEndpoint: "/resources",
    extractProposal: (r) => r.resource,
    buildApplyBody: (r) => r,
  },
  capability: {
    label: "Capability",
    title: "Add capability",
    description:
      "Describe something the lab should be able to do — a script, an MCP tool, an instrument routine. Claude drafts the capability declaration.",
    placeholder: "A Python script at ~/code/my-sim I run with pixi run simulate that takes a config.yaml and writes results/loop.png…",
    designEndpoint: "/tools/design",
    applyEndpoint: "/tools/register-yaml",
    extractProposal: (r) => r.tool,
    buildApplyBody: (t) => t,
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

export default function DesignerPage({ kind, status, refresh, onDone }) {
  const config = KINDS[kind];
  if (!config) return null;

  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState(null);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [registered, setRegistered] = useState(false);

  const keyMissing = status && !status.claude_configured;

  const design = async () => {
    if (!input.trim()) return;
    setBusy(true);
    setError("");
    setProposal(null);
    setNotes("");
    setRegistered(false);
    try {
      const result = await postJson(config.designEndpoint, { text: input });
      const p = config.extractProposal(result);
      setProposal(p);
      setNotes(result.notes || "");
      if (!p) {
        setError("Claude returned no concrete proposal — try a more specific description.");
      }
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
      const body = config.buildApplyBody(proposal);
      await postJson(config.applyEndpoint, body);
      setRegistered(true);
      if (refresh) await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

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

      {keyMissing ? (
        <div className="panel empty-state">
          <h3>Anthropic API key not detected</h3>
          <p>
            The designer uses Claude to draft proposals. Set <code>ANTHROPIC_API_KEY</code> in
            your environment or <code>~/.autolab/env</code> and restart the lab.
          </p>
        </div>
      ) : (
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
            <button type="button" onClick={design} disabled={busy || !input.trim()} className="btn-primary">
              {busy && !proposal ? "Drafting…" : "Draft with Claude"}
            </button>
            {proposal && !registered ? (
              <button type="button" onClick={apply} disabled={busy} className="btn-secondary">
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

          <ProposalView proposal={proposal} kind={config.label} />
        </div>
      )}
    </>
  );
}
