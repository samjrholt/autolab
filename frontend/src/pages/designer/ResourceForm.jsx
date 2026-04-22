// Manual resource registration form.
// Collects backend type + connection params; POSTs to /resources.
// Connection info lives in the Resource — that IS the connection.
import { useState } from "react";
import { postJson } from "../../lib/api";

const BACKENDS = [
  { value: "local", label: "Local (subprocess / WSL)" },
  { value: "ssh_exec", label: "SSH" },
  { value: "slurm", label: "SLURM (stub)" },
  { value: "mcp", label: "MCP endpoint" },
];

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

export default function ResourceForm({ onDone, refresh }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [registered, setRegistered] = useState(false);

  const [name, setName] = useState("");
  const [backend, setBackend] = useState("local");
  const [host, setHost] = useState("");
  const [user, setUser] = useState("");
  const [port, setPort] = useState("");
  const [remoteRoot, setRemoteRoot] = useState("");
  const [workingDir, setWorkingDir] = useState("");
  const [resourceKind, setResourceKind] = useState("");
  const [description, setDescription] = useState("");

  const register = async () => {
    if (!name.trim()) { setError("Name is required."); return; }
    setBusy(true);
    setError("");
    const body = {
      name: name.trim(),
      backend,
      description: description.trim() || null,
      kind: resourceKind.trim() || null,
    };
    if (backend === "ssh_exec") {
      if (!host.trim()) { setError("Host is required for SSH."); setBusy(false); return; }
      Object.assign(body, { host: host.trim(), user: user.trim() || null, port: port ? Number(port) : null, remote_root: remoteRoot.trim() || null });
    }
    if (backend === "local") {
      if (workingDir.trim()) body.working_dir = workingDir.trim();
    }
    try {
      await postJson("/resources", body);
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
      <Field label="Name" hint="Unique identifier for this resource — used in workflow steps and records.">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="wsl-dev" />
      </Field>
      <Field label="Description">
        <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Ubuntu WSL instance for magnetic simulations" />
      </Field>
      <Field label="Backend" hint="How autolab connects to this resource.">
        <select
          value={backend}
          onChange={(e) => setBackend(e.target.value)}
          style={{ width: "100%", background: "var(--color-canvas)", border: "1px solid var(--color-line-strong)", color: "var(--color-text)", borderRadius: 4, padding: "5px 8px", fontSize: 13 }}
        >
          {BACKENDS.map((b) => <option key={b.value} value={b.value}>{b.label}</option>)}
        </select>
      </Field>
      <Field label="Resource kind" hint="Optional label for scheduling (e.g. 'gpu', 'furnace', 'squid'). Capabilities can require a specific kind.">
        <Input value={resourceKind} onChange={(e) => setResourceKind(e.target.value)} placeholder="compute" />
      </Field>

      {backend === "ssh_exec" ? (
        <>
          <div style={{ marginBottom: 10, padding: 10, background: "var(--color-canvas)", borderRadius: 5, fontSize: 12, color: "var(--color-muted)", border: "1px solid var(--color-line)" }}>
            Connection credentials come from <code>~/.ssh/config</code> + <code>ssh-agent</code>. Set up your SSH key before registering. The <em>host</em> can be a hostname or an alias from <code>~/.ssh/config</code>.
          </div>
          <Field label="Host *">
            <Input value={host} onChange={(e) => setHost(e.target.value)} placeholder="my-server.local  or  lab-compute" />
          </Field>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <Field label="Username">
              <Input value={user} onChange={(e) => setUser(e.target.value)} placeholder="sam" />
            </Field>
            <Field label="Port">
              <Input type="number" value={port} onChange={(e) => setPort(e.target.value)} placeholder="22" />
            </Field>
          </div>
          <Field label="Remote working dir" hint="Where autolab places job files on the remote host.">
            <Input value={remoteRoot} onChange={(e) => setRemoteRoot(e.target.value)} placeholder="~/.autolab-work" />
          </Field>
        </>
      ) : null}

      {backend === "local" ? (
        <Field label="Working dir" hint="Local directory for job files and artefacts.">
          <Input value={workingDir} onChange={(e) => setWorkingDir(e.target.value)} placeholder="~/.autolab-work" />
        </Field>
      ) : null}

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
        <button type="button" onClick={register} disabled={busy || !name.trim()} className="btn-primary">
          {busy ? "Registering…" : "Register resource"}
        </button>
        {registered ? (
          <>
            <span style={{ color: "var(--color-status-green)", fontSize: 12 }}>✓ Registered</span>
            {onDone ? <button type="button" className="btn-ghost" onClick={onDone} style={{ fontSize: 12 }}>Back to Resources</button> : null}
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
