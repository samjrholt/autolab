import { useState } from "react";
import SlideOver from "../../../components/SlideOver";
import { postJson } from "../../../lib/api";

// Lightweight capability designer for the "don't leave the canvas" flow.
// Same endpoints as DesignerPage but lives in a slide-over so a scientist
// can author a missing step mid-workflow and drop back onto the canvas.

export default function NewCapabilityInline({ open, onClose, onRegistered, claudeConfigured }) {
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [proposal, setProposal] = useState(null);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  const reset = () => {
    setInput("");
    setProposal(null);
    setNotes("");
    setError("");
  };

  const close = () => {
    reset();
    onClose();
  };

  const design = async () => {
    if (!input.trim()) return;
    setBusy(true);
    setError("");
    setProposal(null);
    setNotes("");
    try {
      const r = await postJson("/capabilities/design", { text: input });
      setProposal(r.tool);
      setNotes(r.notes || "");
      if (!r.tool) setError("Claude returned no concrete capability proposal — try a more specific description.");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const register = async () => {
    if (!proposal) return;
    setBusy(true);
    setError("");
    try {
      const registered = await postJson("/capabilities/register", proposal);
      reset();
      onRegistered(registered);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <SlideOver open={open} onClose={close} width="max-w-xl">
      <h2 style={{ fontSize: 20, marginBottom: 6 }}>New capability</h2>
      <p style={{ color: "var(--color-muted)", fontSize: 12, marginBottom: 14 }}>
        Describe what the lab should be able to do. Claude drafts the declaration; nothing registers without your approval.
      </p>

      {!claudeConfigured ? (
        <div className="panel empty-state" style={{ marginBottom: 12 }}>
          <p style={{ fontSize: 12 }}>
            Anthropic API key not detected. Set <code>ANTHROPIC_API_KEY</code> and restart the lab.
          </p>
        </div>
      ) : null}

      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="A Python script at ~/code/my-sim I run with `pixi run simulate` that takes a config.yaml and writes results/loop.png…"
        disabled={busy}
        rows={5}
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
        <button
          type="button"
          onClick={design}
          disabled={busy || !input.trim() || !claudeConfigured}
          className="btn-primary"
        >
          {busy && !proposal ? "Drafting…" : "Draft with Claude"}
        </button>
        {proposal ? (
          <button type="button" onClick={register} disabled={busy} className="btn-secondary">
            {busy ? "Registering…" : "Register & use"}
          </button>
        ) : null}
      </div>

      {notes ? (
        <div style={{ marginTop: 12, padding: 10, background: "var(--color-canvas)", borderRadius: 5, fontSize: 12, color: "var(--color-muted)" }}>
          {notes}
        </div>
      ) : null}

      {proposal ? (
        <div className="card" style={{ padding: 12, marginTop: 12 }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 6 }}>
            Proposed capability
          </div>
          <pre style={{ maxHeight: 260, overflowY: "auto" }}>{JSON.stringify(proposal, null, 2)}</pre>
        </div>
      ) : null}

      {error ? (
        <div style={{ marginTop: 12, padding: 10, borderRadius: 5, background: "rgba(214,102,102,0.08)", border: "1px solid rgba(214,102,102,0.3)", fontSize: 12, color: "var(--color-status-red)" }}>
          {error}
        </div>
      ) : null}
    </SlideOver>
  );
}
