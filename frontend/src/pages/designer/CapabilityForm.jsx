// Manual capability registration form.
// Produces a JSON declaration POSTed to /tools/register-yaml.
// Alongside the Claude-assisted "Describe" mode so scientists don't
// need an API key to register a simple script or instrument routine.
import { useState } from "react";
import { postJson } from "../../lib/api";

function Field({ label, hint, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: "block", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 5 }}>
        {label}
      </label>
      {children}
      {hint ? <div style={{ fontSize: 11, color: "var(--color-tertiary)", marginTop: 3 }}>{hint}</div> : null}
    </div>
  );
}

function Input(props) {
  return (
    <input
      {...props}
      style={{
        width: "100%",
        background: "var(--color-canvas)",
        border: "1px solid var(--color-line-strong)",
        color: "var(--color-text)",
        borderRadius: 4,
        padding: "5px 8px",
        fontSize: 13,
        ...(props.style || {}),
      }}
    />
  );
}

// Simple list-of-pairs editor for inputs/outputs schema.
function SchemaEditor({ label, hint, value, onChange }) {
  const pairs = Object.entries(value || {});
  const add = () => onChange({ ...value, "": "any" });
  const update = (oldKey, newKey, newType) => {
    const next = {};
    for (const [k, v] of Object.entries(value || {})) {
      const key = k === oldKey ? newKey : k;
      next[key] = k === oldKey ? newType : v;
    }
    onChange(next);
  };
  const remove = (k) => {
    const next = { ...(value || {}) };
    delete next[k];
    onChange(next);
  };
  return (
    <Field label={label} hint={hint}>
      {pairs.map(([k, v], i) => (
        <div key={i} style={{ display: "flex", gap: 6, marginBottom: 6 }}>
          <input
            value={k}
            placeholder="param_name"
            onChange={(e) => update(k, e.target.value, v)}
            style={{ flex: 2, background: "var(--color-canvas)", border: "1px solid var(--color-line-strong)", color: "var(--color-text)", borderRadius: 4, padding: "4px 6px", fontSize: 12, fontFamily: "var(--font-mono)" }}
          />
          <input
            value={v}
            placeholder="type"
            onChange={(e) => update(k, k, e.target.value)}
            style={{ flex: 1, background: "var(--color-canvas)", border: "1px solid var(--color-line-strong)", color: "var(--color-muted)", borderRadius: 4, padding: "4px 6px", fontSize: 11, fontFamily: "var(--font-mono)" }}
          />
          <button type="button" onClick={() => remove(k)} className="btn-ghost" style={{ fontSize: 11, padding: "2px 8px" }}>×</button>
        </div>
      ))}
      <button type="button" className="btn-ghost" onClick={add} style={{ fontSize: 11 }}>+ Add parameter</button>
    </Field>
  );
}

export default function CapabilityForm({ onDone, refresh }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [registered, setRegistered] = useState(false);

  const [capability, setCapability] = useState("");
  const [description, setDescription] = useState("");
  const [resourceKind, setResourceKind] = useState("");
  const [adapter, setAdapter] = useState("dynamic");
  const [module, setModule] = useState("dynamic_stub");
  const [inputs, setInputs] = useState({});
  const [outputs, setOutputs] = useState({});

  const register = async () => {
    if (!capability.trim()) { setError("Capability name is required."); return; }
    if (!/^[a-z_][a-z0-9_]*$/.test(capability.trim())) {
      setError("Capability name must be lowercase letters, digits, and underscores (e.g. shell_command, xrd, sintering).");
      return;
    }
    setBusy(true);
    setError("");
    const body = {
      name: capability.trim(),
      capability: capability.trim(),
      description: description.trim() || null,
      resource_kind: resourceKind.trim() || null,
      adapter: adapter.trim() || "dynamic",
      module: module.trim() || "dynamic_stub",
      inputs,
      outputs,
    };
    try {
      await postJson("/tools/register-yaml", body);
      setRegistered(true);
      if (refresh) await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel" style={{ padding: 16, maxWidth: 640 }}>
      <Field label="Capability name *" hint="Scientist-shaped noun: shell_command, xrd, sintering, magnetometry. Lowercase, underscores only.">
        <Input
          value={capability}
          onChange={(e) => setCapability(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))}
          placeholder="add_two"
          style={{ fontFamily: "var(--font-mono)" }}
        />
      </Field>
      <Field label="Description">
        <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Adds 2 to an input number." />
      </Field>
      <Field label="Resource kind" hint="Leave blank for any resource. Set to 'gpu', 'furnace', etc. to constrain scheduling.">
        <Input value={resourceKind} onChange={(e) => setResourceKind(e.target.value)} placeholder="any" />
      </Field>
      <Field label="Adapter" hint={`"dynamic" creates a stub that returns random outputs for testing. "shell_command" runs a command string. Or provide a Python import path for a real Operation class.`}>
        <select
          value={adapter}
          onChange={(e) => setAdapter(e.target.value)}
          style={{ width: "100%", background: "var(--color-canvas)", border: "1px solid var(--color-line-strong)", color: "var(--color-text)", borderRadius: 4, padding: "5px 8px", fontSize: 13 }}
        >
          <option value="dynamic">dynamic (stub — returns random outputs)</option>
          <option value="shell_command">shell_command (runs a command string)</option>
          <option value="custom">custom (enter Python import path below)</option>
        </select>
      </Field>
      {adapter === "custom" ? (
        <Field label="Python import path" hint="e.g. mylab.ops.sintering.SinteringOp">
          <Input value={module} onChange={(e) => setModule(e.target.value)} placeholder="mylab.ops.MyOperation" style={{ fontFamily: "var(--font-mono)" }} />
        </Field>
      ) : null}

      <SchemaEditor label="Inputs" hint="Named parameters this capability accepts." value={inputs} onChange={setInputs} />
      <SchemaEditor label="Outputs" hint="Named values this capability returns." value={outputs} onChange={setOutputs} />

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
        <button type="button" onClick={register} disabled={busy || !capability.trim()} className="btn-primary">
          {busy ? "Registering…" : "Register capability"}
        </button>
        {registered ? (
          <>
            <span style={{ color: "var(--color-status-green)", fontSize: 12 }}>✓ Registered</span>
            {onDone ? <button type="button" className="btn-ghost" onClick={onDone} style={{ fontSize: 12 }}>Done</button> : null}
          </>
        ) : null}
      </div>
      {error ? (
        <div style={{ marginTop: 12, padding: 10, borderRadius: 5, background: "rgba(214,102,102,0.08)", border: "1px solid rgba(214,102,102,0.3)", fontSize: 12, color: "var(--color-status-red)" }}>
          {error}
        </div>
      ) : null}
    </div>
  );
}
