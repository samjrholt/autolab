import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import KeyValue from "./KeyValue";
import StatusIndicator from "./StatusIndicator";
import SlideOver from "./SlideOver";
import DualModeBuilder from "./shared/DualModeBuilder";
import RefinementPrompt from "./shared/RefinementPrompt";
import { getJson, postJson } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

export default function SettingsDrawer({ open, onClose, status, refresh }) {
  return (
    <SlideOver open={open} onClose={onClose} width="max-w-xl">
      <motion.div initial="hidden" animate="visible" variants={stagger}>
        <motion.h3
          variants={fadeInUp}
          className="text-[36px] font-normal text-white tracking-[-0.02em] mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Lab setup
        </motion.h3>
        <motion.p variants={fadeInUp} className="text-[var(--color-secondary)] mb-8">
          Describe your lab and autolab will propose the resources and operations to register.
        </motion.p>

        <SetupAssistant status={status} refresh={refresh} />
        <ResourcesSection status={status} refresh={refresh} />
        <ToolsSection status={status} refresh={refresh} />
        <WorkflowsSection status={status} refresh={refresh} />
        <LabSection />
      </motion.div>
    </SlideOver>
  );
}

function Section({ title, children }) {
  const [open, setOpen] = useState(true);
  return (
    <motion.section variants={fadeInUp} className="mb-10">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 bg-transparent border-none p-0 mb-4"
      >
        <span className="text-[10px] text-[var(--color-tertiary)]">{open ? "▾" : "▸"}</span>
        <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)]">
          {title}
        </span>
      </button>
      {open && children}
    </motion.section>
  );
}

function SetupAssistant({ status, refresh }) {
  const [text, setText] = useState("");
  const [proposal, setProposal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const design = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    setProposal(null);
    setResult(null);
    try {
      const res = await postJson("/lab/setup", { text });
      setProposal(res);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!proposal) return;
    setApplying(true);
    setError("");
    try {
      const res = await postJson("/lab/setup/apply", {
        resources: proposal.resources || [],
        operations: proposal.operations || [],
      });
      setResult(res);
      if (res.ok) {
        refresh?.();
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setApplying(false);
    }
  };

  return (
    <Section title="Setup assistant">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={"Describe your lab, e.g.:\n\nI have a tube furnace (max 1400°C), a SQUID magnetometer, and a Bruker XRD. I want to synthesise and characterise Fe-Co alloys to optimise coercivity."}
        rows={5}
        className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-4 py-3 text-[14px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none mb-3"
      />
      <div className="flex gap-2 mb-3">
        <button
          type="button"
          onClick={design}
          disabled={busy || !text.trim()}
          className="bg-transparent border border-white/20 hover:border-white/40 rounded-full px-5 py-2 text-[14px] font-medium text-white transition-all disabled:opacity-30"
        >
          {busy ? "Thinking…" : "Propose setup"}
        </button>
        {proposal && !result?.ok && (
          <button
            type="button"
            onClick={apply}
            disabled={applying}
            className="bg-white text-[var(--color-bg)] rounded-full px-5 py-2 text-[14px] font-semibold hover:bg-white/90 transition-all disabled:opacity-30"
          >
            {applying ? "Applying…" : "Apply all"}
          </button>
        )}
      </div>

      {error && <p className="text-[var(--color-status-red)] text-[13px] mb-3">{error}</p>}

      {result?.ok && (
        <div className="border border-[var(--color-status-green)]/30 rounded-xl p-4 mb-3">
          <p className="text-[var(--color-status-green)] text-[14px] font-medium mb-1">Setup applied</p>
          <p className="text-[13px] text-[var(--color-secondary)]">
            {result.registered_resources?.length || 0} resources and {result.registered_operations?.length || 0} operations registered.
          </p>
        </div>
      )}

      {result?.errors?.length > 0 && (
        <div className="text-[13px] text-[var(--color-status-red)] mb-3">
          {result.errors.map((e, i) => <p key={i}>{e}</p>)}
        </div>
      )}

      {proposal && !result?.ok && (
        <div className="border border-[var(--color-line)] rounded-2xl p-5 mb-3">
          {proposal.notes && (
            <p className="text-[13px] text-[var(--color-secondary)] italic mb-4">{proposal.notes}</p>
          )}

          {proposal.resources?.length > 0 && (
            <div className="mb-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-2">
                Proposed resources
              </p>
              {proposal.resources.map((r, i) => (
                <div key={i} className="flex items-center gap-3 py-1.5 text-[14px]">
                  <span className="text-white font-medium">{r.name}</span>
                  <span className="text-[12px] text-[var(--color-secondary)]">{r.kind}</span>
                  {r.description && <span className="text-[12px] text-[var(--color-tertiary)]">— {r.description}</span>}
                </div>
              ))}
            </div>
          )}

          {proposal.operations?.length > 0 && (
            <div className="mb-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-2">
                Proposed operations
              </p>
              {proposal.operations.map((op, i) => (
                <div key={i} className="py-1.5">
                  <div className="flex items-center gap-3 text-[14px]">
                    <span className="text-white font-medium">{op.capability}</span>
                    {op.resource_kind && <span className="text-[12px] text-[var(--color-secondary)]">→ {op.resource_kind}</span>}
                  </div>
                  {op.description && <p className="text-[12px] text-[var(--color-tertiary)] mt-0.5">{op.description}</p>}
                </div>
              ))}
            </div>
          )}

          {proposal.workflow && (
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-2">
                Suggested workflow
              </p>
              <p className="text-[14px] text-white">{proposal.workflow.name}</p>
              {proposal.workflow.description && (
                <p className="text-[12px] text-[var(--color-tertiary)]">{proposal.workflow.description}</p>
              )}
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

const RESOURCE_KINDS = [
  { value: "computer", label: "Computer" },
  { value: "furnace", label: "Furnace" },
  { value: "tube_furnace", label: "Tube furnace" },
  { value: "arc_furnace", label: "Arc furnace" },
  { value: "slurm_partition", label: "SLURM partition" },
  { value: "gpu_node", label: "GPU node" },
  { value: "magnetometer", label: "Magnetometer (SQUID)" },
  { value: "xrd", label: "XRD" },
  { value: "sem", label: "SEM" },
  { value: "balance", label: "Balance" },
  { value: "vm", label: "Virtual machine" },
  { value: "custom", label: "Custom…" },
];

const KIND_PRESETS = {
  furnace:        [{ key: "max_temp_k", val: "1400" }, { key: "atmosphere", val: "Ar" }, { key: "ramp_rate_k_per_min", val: "10" }],
  tube_furnace:   [{ key: "max_temp_k", val: "1400" }, { key: "atmosphere", val: "O2,Ar,N2" }, { key: "ramp_rate_k_per_min", val: "10" }, { key: "tube_diameter_mm", val: "50" }],
  arc_furnace:    [{ key: "max_temp_k", val: "3000" }, { key: "volume_ml", val: "5" }],
  slurm_partition:[{ key: "gpu_count", val: "4" }, { key: "mem_gb", val: "80" }, { key: "partition_name", val: "gpu" }],
  gpu_node:       [{ key: "gpu_count", val: "1" }, { key: "gpu_type", val: "A100" }, { key: "mem_gb", val: "40" }],
  magnetometer:   [{ key: "max_field_t", val: "7" }, { key: "temp_range_k", val: "2-400" }],
  xrd:            [{ key: "two_theta_range", val: "5-90" }, { key: "radiation", val: "Cu-Ka" }],
  computer:       [{ key: "cores", val: "8" }, { key: "mem_gb", val: "32" }],
  vm:             [{ key: "cores", val: "4" }, { key: "mem_gb", val: "16" }],
};

function CapabilitiesEditor({ caps, onChange }) {
  const addRow = () => onChange([...caps, { key: "", val: "" }]);
  const removeRow = (i) => onChange(caps.filter((_, j) => j !== i));
  const update = (i, field, value) => {
    const next = caps.map((c, j) => (j === i ? { ...c, [field]: value } : c));
    onChange(next);
  };

  return (
    <div className="mt-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-[var(--color-secondary)] uppercase tracking-[0.15em]">Capabilities</span>
        <button type="button" onClick={addRow} className="text-[11px] text-[var(--color-tertiary)] hover:text-white transition-colors bg-transparent border-none p-0">+ Add</button>
      </div>
      {caps.map((c, i) => (
        <div key={i} className="flex gap-2 mb-1.5">
          <input value={c.key} onChange={(e) => update(i, "key", e.target.value)} placeholder="key" className="flex-1 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" style={{ fontFamily: "var(--font-mono)" }} />
          <input value={c.val} onChange={(e) => update(i, "val", e.target.value)} placeholder="value" className="flex-1 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" style={{ fontFamily: "var(--font-mono)" }} />
          <button type="button" onClick={() => removeRow(i)} className="text-[11px] text-[var(--color-tertiary)] hover:text-[var(--color-status-red)] bg-transparent border-none px-1 transition-colors">×</button>
        </div>
      ))}
    </div>
  );
}

function capsToDict(caps) {
  const d = {};
  for (const { key, val } of caps) {
    if (!key.trim()) continue;
    const n = Number(val);
    d[key.trim()] = !isNaN(n) && val.trim() !== "" && !val.includes(",") ? n : val;
  }
  return d;
}

function ResourcesSection({ status, refresh }) {
  const resources = status?.resources || [];
  // Manual form state
  const [name, setName] = useState("");
  const [kind, setKind] = useState("computer");
  const [customKind, setCustomKind] = useState("");
  const [description, setDescription] = useState("");
  const [caps, setCaps] = useState([]);
  const [count, setCount] = useState(1);
  const [adding, setAdding] = useState(false);

  // Claude mode state
  const [prompt, setPrompt] = useState("");
  const [proposal, setProposal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // Auto-fill capabilities from presets when kind changes
  const handleKindChange = (newKind) => {
    setKind(newKind);
    if (KIND_PRESETS[newKind]) {
      setCaps(KIND_PRESETS[newKind].map((p) => ({ ...p })));
    }
  };

  const effectiveKind = kind === "custom" ? customKind : kind;

  const addManual = async () => {
    if (!name.trim() || !effectiveKind.trim()) return;
    setAdding(true);
    try {
      for (let i = 0; i < count; i++) {
        const suffix = count > 1 ? `-${i + 1}` : "";
        await postJson("/resources", {
          name: `${name.trim()}${suffix}`,
          kind: effectiveKind,
          description,
          capabilities: capsToDict(caps),
        });
      }
      setName(""); setDescription(""); setCaps([]); setCount(1);
      refresh?.();
    } finally {
      setAdding(false);
    }
  };

  const designWithClaude = async () => {
    if (!prompt.trim()) return;
    setBusy(true); setError("");
    try {
      const res = await postJson("/resources/design", { text: prompt });
      setProposal(res);
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  };

  const refineProposal = async (instruction) => {
    setBusy(true); setError("");
    try {
      const res = await postJson("/resources/design", {
        text: prompt,
        previous: proposal?.resource,
        instruction,
      });
      setProposal(res);
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  };

  const applyProposal = async () => {
    if (!proposal?.resource) return;
    setAdding(true);
    try {
      await postJson("/resources", proposal.resource);
      setProposal(null); setPrompt("");
      refresh?.();
    } catch (err) { setError(String(err)); }
    finally { setAdding(false); }
  };

  // Edit proposal fields inline
  const updateProposal = (field, value) => {
    setProposal((prev) => ({ ...prev, resource: { ...prev.resource, [field]: value } }));
  };

  const manualForm = (
    <div>
      <div className="flex gap-2 mb-2">
        <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Resource name" className="flex-1 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
        <select value={kind} onChange={(e) => handleKindChange(e.target.value)} className="w-40 bg-[var(--color-bg)] border border-[var(--color-line)] rounded-lg px-2 py-1.5 text-[13px] text-white focus:outline-none focus:border-[var(--color-line-hover)]">
          {RESOURCE_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>
      </div>
      {kind === "custom" && (
        <input type="text" value={customKind} onChange={(e) => setCustomKind(e.target.value)} placeholder="Custom kind name" className="w-full mb-2 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
      )}
      <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (optional)" className="w-full mb-2 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
      <CapabilitiesEditor caps={caps} onChange={setCaps} />
      <div className="flex items-center gap-3 mt-3">
        <label className="text-[12px] text-[var(--color-secondary)]">
          Count
          <input type="number" min={1} max={20} value={count} onChange={(e) => setCount(Math.max(1, Number(e.target.value)))} className="ml-2 w-14 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] text-white focus:outline-none" />
        </label>
        <button type="button" onClick={addManual} disabled={adding || !name.trim() || !effectiveKind.trim()} className="ml-auto bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-full px-4 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all disabled:opacity-30">
          {adding ? "Adding…" : count > 1 ? `Add ${count} resources` : "Add resource"}
        </button>
      </div>
    </div>
  );

  const claudeForm = (
    <div>
      <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={"Describe your resource, e.g.:\n\n'I have a tube furnace that goes up to 1400°C with O2 and Ar atmosphere options.'"} rows={3} className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-4 py-3 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none mb-3" />
      <button type="button" onClick={designWithClaude} disabled={busy || !prompt.trim()} className="bg-transparent border border-white/20 hover:border-white/40 rounded-full px-4 py-1.5 text-[13px] font-medium text-white transition-all disabled:opacity-30">
        {busy ? "Thinking…" : proposal ? "Regenerate" : "Propose resource"}
      </button>
      {error && <p className="text-[var(--color-status-red)] text-[13px] mt-2">{error}</p>}
      {proposal?.resource && (
        <div className="mt-4 border border-[var(--color-line)] rounded-2xl p-4">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-3">Proposed resource (edit inline)</p>
          <div className="flex gap-2 mb-2">
            <input value={proposal.resource.name || ""} onChange={(e) => updateProposal("name", e.target.value)} placeholder="name" className="flex-1 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[13px] text-white focus:outline-none focus:border-[var(--color-line-hover)]" />
            <input value={proposal.resource.kind || ""} onChange={(e) => updateProposal("kind", e.target.value)} placeholder="kind" className="w-36 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[13px] text-white focus:outline-none focus:border-[var(--color-line-hover)]" />
          </div>
          {proposal.resource.capabilities && (
            <div className="mb-2">
              <span className="text-[11px] text-[var(--color-secondary)] uppercase tracking-[0.15em]">Capabilities</span>
              <KeyValue data={proposal.resource.capabilities} />
            </div>
          )}
          {proposal.notes && <p className="text-[12px] text-[var(--color-secondary)] italic mt-2">{proposal.notes}</p>}
          <RefinementPrompt onRefine={refineProposal} busy={busy} placeholder="e.g. 'add O2 atmosphere, rename to tube-furnace-A'" />
          <button type="button" onClick={applyProposal} disabled={adding} className="mt-3 bg-white text-[var(--color-bg)] rounded-full px-5 py-1.5 text-[13px] font-semibold hover:bg-white/90 transition-all disabled:opacity-30">
            {adding ? "Registering…" : "Register resource"}
          </button>
        </div>
      )}
    </div>
  );

  return (
    <Section title="Resources">
      <div className="flex flex-col gap-2 mb-4">
        {resources.map((r) => (
          <div key={r.name} className="flex items-center gap-3 py-1.5">
            <StatusIndicator status={r.state} pulse={r.state === "busy"} />
            <span className="text-[14px] text-white">{r.name}</span>
            <span className="text-[12px] text-[var(--color-secondary)]">{r.kind}</span>
            {r.capabilities && Object.keys(r.capabilities).length > 0 && (
              <span className="text-[11px] text-[var(--color-tertiary)]" style={{ fontFamily: "var(--font-mono)" }}>
                {Object.entries(r.capabilities).map(([k, v]) => `${k}=${v}`).join(", ")}
              </span>
            )}
          </div>
        ))}
        {resources.length === 0 && (
          <p className="text-[var(--color-tertiary)] text-[13px]">No resources registered.</p>
        )}
      </div>
      <DualModeBuilder manual={manualForm} withClaude={claudeForm} />
    </Section>
  );
}

function SchemaEditor({ label, schema, onChange }) {
  const addRow = () => onChange([...schema, { key: "", type: "float" }]);
  const removeRow = (i) => onChange(schema.filter((_, j) => j !== i));
  const update = (i, field, value) => {
    const next = schema.map((s, j) => (j === i ? { ...s, [field]: value } : s));
    onChange(next);
  };

  return (
    <div className="mt-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-[var(--color-secondary)] uppercase tracking-[0.15em]">{label}</span>
        <button type="button" onClick={addRow} className="text-[11px] text-[var(--color-tertiary)] hover:text-white transition-colors bg-transparent border-none p-0">+ Add</button>
      </div>
      {schema.map((s, i) => (
        <div key={i} className="flex gap-2 mb-1.5">
          <input value={s.key} onChange={(e) => update(i, "key", e.target.value)} placeholder="name" className="flex-1 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" style={{ fontFamily: "var(--font-mono)" }} />
          <select value={s.type} onChange={(e) => update(i, "type", e.target.value)} className="w-24 bg-[var(--color-bg)] border border-[var(--color-line)] rounded px-1 py-1 text-[12px] text-white focus:outline-none">
            {["float", "int", "str", "bool", "list", "dict"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button type="button" onClick={() => removeRow(i)} className="text-[11px] text-[var(--color-tertiary)] hover:text-[var(--color-status-red)] bg-transparent border-none px-1 transition-colors">×</button>
        </div>
      ))}
    </div>
  );
}

function schemaToDict(schema) {
  const d = {};
  for (const { key, type } of schema) {
    if (key.trim()) d[key.trim()] = type;
  }
  return d;
}

function ToolsSection({ status, refresh }) {
  const tools = status?.tools || [];
  const resourceKinds = [...new Set((status?.resources || []).map((r) => r.kind))];

  // Manual form
  const [capability, setCapability] = useState("");
  const [resourceKind, setResourceKind] = useState("");
  const [toolDesc, setToolDesc] = useState("");
  const [inputs, setInputs] = useState([]);
  const [outputs, setOutputs] = useState([]);
  const [producesSample, setProducesSample] = useState(false);
  const [destructive, setDestructive] = useState(false);
  const [duration, setDuration] = useState("");
  const [adding, setAdding] = useState(false);

  // Claude mode
  const [prompt, setPrompt] = useState("");
  const [proposal, setProposal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const addManual = async () => {
    if (!capability.trim()) return;
    setAdding(true);
    try {
      await postJson("/tools/register", {
        capability: capability.trim(),
        resource_kind: resourceKind || undefined,
        description: toolDesc || undefined,
        inputs: schemaToDict(inputs),
        outputs: schemaToDict(outputs),
        produces_sample: producesSample,
        destructive,
        typical_duration_s: duration ? Number(duration) : undefined,
      });
      setCapability(""); setResourceKind(""); setToolDesc(""); setInputs([]); setOutputs([]);
      setProducesSample(false); setDestructive(false); setDuration("");
      refresh?.();
    } catch (err) { setError(String(err)); }
    finally { setAdding(false); }
  };

  const designWithClaude = async () => {
    if (!prompt.trim()) return;
    setBusy(true); setError("");
    try {
      const res = await postJson("/tools/design", { text: prompt });
      setProposal(res);
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  };

  const refineProposal = async (instruction) => {
    setBusy(true); setError("");
    try {
      const res = await postJson("/tools/design", { text: prompt, previous: proposal?.tool, instruction });
      setProposal(res);
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  };

  const applyProposal = async () => {
    if (!proposal?.tool) return;
    setAdding(true);
    try {
      await postJson("/tools/register", proposal.tool);
      setProposal(null); setPrompt("");
      refresh?.();
    } catch (err) { setError(String(err)); }
    finally { setAdding(false); }
  };

  const manualForm = (
    <div>
      <input type="text" value={capability} onChange={(e) => setCapability(e.target.value)} placeholder="Capability name (e.g. sintering, xrd, hysteresis)" className="w-full mb-2 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
      <div className="flex gap-2 mb-2">
        <select value={resourceKind} onChange={(e) => setResourceKind(e.target.value)} className="flex-1 bg-[var(--color-bg)] border border-[var(--color-line)] rounded-lg px-2 py-1.5 text-[13px] text-white focus:outline-none">
          <option value="">Resource kind (optional)</option>
          {resourceKinds.map((k) => <option key={k} value={k}>{k}</option>)}
          <option value="_custom">Custom…</option>
        </select>
        <input type="text" value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="Duration (s)" className="w-28 bg-transparent border border-[var(--color-line)] rounded-lg px-2 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
      </div>
      <input type="text" value={toolDesc} onChange={(e) => setToolDesc(e.target.value)} placeholder="Description" className="w-full mb-2 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
      <SchemaEditor label="Inputs" schema={inputs} onChange={setInputs} />
      <SchemaEditor label="Outputs" schema={outputs} onChange={setOutputs} />
      <div className="flex gap-4 mt-3 mb-3">
        <label className="flex items-center gap-1.5 text-[12px] text-[var(--color-secondary)]">
          <input type="checkbox" checked={producesSample} onChange={(e) => setProducesSample(e.target.checked)} className="accent-white" /> Produces sample
        </label>
        <label className="flex items-center gap-1.5 text-[12px] text-[var(--color-secondary)]">
          <input type="checkbox" checked={destructive} onChange={(e) => setDestructive(e.target.checked)} className="accent-white" /> Destructive
        </label>
      </div>
      <button type="button" onClick={addManual} disabled={adding || !capability.trim()} className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-full px-4 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all disabled:opacity-30">
        {adding ? "Registering…" : "Register tool"}
      </button>
    </div>
  );

  const claudeForm = (
    <div>
      <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={"Describe a tool capability, e.g.:\n\n'A micromagnetics simulation that takes a grain structure and applied field range, and returns a hysteresis loop with Hc and Mr.'"} rows={3} className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-4 py-3 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none mb-3" />
      <button type="button" onClick={designWithClaude} disabled={busy || !prompt.trim()} className="bg-transparent border border-white/20 hover:border-white/40 rounded-full px-4 py-1.5 text-[13px] font-medium text-white transition-all disabled:opacity-30">
        {busy ? "Thinking…" : proposal ? "Regenerate" : "Propose tool"}
      </button>
      {error && <p className="text-[var(--color-status-red)] text-[13px] mt-2">{error}</p>}
      {proposal?.tool && (
        <div className="mt-4 border border-[var(--color-line)] rounded-2xl p-4">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-3">Proposed tool</p>
          <div className="text-[13px] text-white mb-1 font-medium">{proposal.tool.capability}</div>
          {proposal.tool.resource_kind && <div className="text-[12px] text-[var(--color-secondary)] mb-1">→ {proposal.tool.resource_kind}</div>}
          {proposal.tool.description && <div className="text-[12px] text-[var(--color-tertiary)] mb-2">{proposal.tool.description}</div>}
          {proposal.tool.inputs && <div className="mb-1"><span className="text-[11px] text-[var(--color-secondary)] uppercase">Inputs:</span> <KeyValue data={proposal.tool.inputs} /></div>}
          {proposal.tool.outputs && <div className="mb-1"><span className="text-[11px] text-[var(--color-secondary)] uppercase">Outputs:</span> <KeyValue data={proposal.tool.outputs} /></div>}
          {proposal.notes && <p className="text-[12px] text-[var(--color-secondary)] italic mt-2">{proposal.notes}</p>}
          <RefinementPrompt onRefine={refineProposal} busy={busy} placeholder="e.g. 'add an output for remanence, change resource_kind to magnetometer'" />
          <button type="button" onClick={applyProposal} disabled={adding} className="mt-3 bg-white text-[var(--color-bg)] rounded-full px-5 py-1.5 text-[13px] font-semibold hover:bg-white/90 transition-all disabled:opacity-30">
            {adding ? "Registering…" : "Register tool"}
          </button>
        </div>
      )}
    </div>
  );

  return (
    <Section title="Tools">
      <div className="flex flex-col gap-2 mb-4">
        {tools.map((t) => (
          <div key={t.capability} className="py-1.5">
            <span className="text-[14px] text-white">{t.capability}</span>
            {t.resource_kind && <span className="ml-2 text-[12px] text-[var(--color-secondary)]">→ {t.resource_kind}</span>}
            {t.description && <span className="ml-2 text-[12px] text-[var(--color-tertiary)]">{t.description}</span>}
          </div>
        ))}
        {tools.length === 0 && (
          <p className="text-[var(--color-tertiary)] text-[13px]">No tools registered.</p>
        )}
      </div>
      <DualModeBuilder manual={manualForm} withClaude={claudeForm} />
    </Section>
  );
}

function WorkflowStepEditor({ step, index, tools, onChange, onRemove, onMoveUp, onMoveDown, isFirst, isLast, allStepIds }) {
  const update = (field, value) => onChange({ ...step, [field]: value });
  const toggleDep = (depId) => {
    const deps = step.depends_on || [];
    const next = deps.includes(depId) ? deps.filter((d) => d !== depId) : [...deps, depId];
    update("depends_on", next);
  };

  return (
    <div className="border border-[var(--color-line)] rounded-xl p-3 mb-2">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[11px] text-[var(--color-tertiary)] font-mono w-6">{step.step_id}</span>
        <select value={step.operation || ""} onChange={(e) => update("operation", e.target.value)} className="flex-1 bg-[var(--color-bg)] border border-[var(--color-line)] rounded px-2 py-1 text-[13px] text-white focus:outline-none">
          <option value="">Select operation…</option>
          {tools.map((t) => <option key={t.capability} value={t.capability}>{t.capability}</option>)}
        </select>
        <div className="flex gap-1">
          {!isFirst && <button type="button" onClick={onMoveUp} className="text-[11px] text-[var(--color-tertiary)] hover:text-white bg-transparent border-none px-1">↑</button>}
          {!isLast && <button type="button" onClick={onMoveDown} className="text-[11px] text-[var(--color-tertiary)] hover:text-white bg-transparent border-none px-1">↓</button>}
          <button type="button" onClick={onRemove} className="text-[11px] text-[var(--color-tertiary)] hover:text-[var(--color-status-red)] bg-transparent border-none px-1">×</button>
        </div>
      </div>
      {/* Dependencies */}
      {allStepIds.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          <span className="text-[10px] text-[var(--color-tertiary)] self-center mr-1">depends on:</span>
          {allStepIds.filter((id) => id !== step.step_id).map((id) => (
            <button key={id} type="button" onClick={() => toggleDep(id)} className={`text-[11px] rounded-full px-2 py-0.5 transition-all bg-transparent border ${(step.depends_on || []).includes(id) ? "border-white text-white" : "border-[var(--color-line)] text-[var(--color-tertiary)] hover:border-[var(--color-line-hover)]"}`}>
              {id}
            </button>
          ))}
        </div>
      )}
      {/* Step inputs (simple key-value) */}
      <div className="flex gap-4 text-[11px] text-[var(--color-tertiary)]">
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={step.produces_sample || false} onChange={(e) => update("produces_sample", e.target.checked)} className="accent-white" /> sample
        </label>
        <label className="flex items-center gap-1">
          <input type="checkbox" checked={step.destructive || false} onChange={(e) => update("destructive", e.target.checked)} className="accent-white" /> destructive
        </label>
      </div>
    </div>
  );
}

function WorkflowsSection({ status, refresh }) {
  const workflows = status?.workflows || [];
  const tools = status?.tools || [];
  const [showBuilder, setShowBuilder] = useState(false);

  // Manual workflow builder state
  const [wfName, setWfName] = useState("");
  const [wfDesc, setWfDesc] = useState("");
  const [steps, setSteps] = useState([]);
  const [adding, setAdding] = useState(false);

  // Claude mode
  const [prompt, setPrompt] = useState("");
  const [proposal, setProposal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const addStep = () => {
    const id = `s${steps.length + 1}`;
    const deps = steps.length > 0 ? [steps[steps.length - 1].step_id] : [];
    setSteps([...steps, { step_id: id, operation: "", depends_on: deps, inputs: {}, produces_sample: false, destructive: false }]);
  };

  const updateStep = (i, step) => setSteps(steps.map((s, j) => j === i ? step : s));
  const removeStep = (i) => {
    const removed = steps[i].step_id;
    setSteps(steps.filter((_, j) => j !== i).map((s) => ({ ...s, depends_on: (s.depends_on || []).filter((d) => d !== removed) })));
  };
  const moveStep = (i, dir) => {
    const next = [...steps];
    const j = i + dir;
    [next[i], next[j]] = [next[j], next[i]];
    setSteps(next);
  };

  const saveManual = async () => {
    if (!wfName.trim() || steps.length === 0) return;
    setAdding(true); setError("");
    try {
      await postJson("/workflows", { name: wfName.trim(), description: wfDesc, steps });
      setWfName(""); setWfDesc(""); setSteps([]); setShowBuilder(false);
      refresh?.();
    } catch (err) { setError(String(err)); }
    finally { setAdding(false); }
  };

  const designWithClaude = async () => {
    if (!prompt.trim()) return;
    setBusy(true); setError("");
    try {
      const res = await postJson("/workflows/design", { text: prompt });
      setProposal(res);
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  };

  const refineProposal = async (instruction) => {
    setBusy(true); setError("");
    try {
      const res = await postJson("/workflows/design", { text: prompt, previous: proposal?.workflow, instruction });
      setProposal(res);
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  };

  const applyProposal = async () => {
    if (!proposal?.workflow) return;
    setAdding(true); setError("");
    try {
      await postJson("/workflows", proposal.workflow);
      setProposal(null); setPrompt("");
      refresh?.();
    } catch (err) { setError(String(err)); }
    finally { setAdding(false); }
  };

  // Populate builder from existing workflow (clone)
  const cloneWorkflow = (wf) => {
    setWfName(wf.name + "-copy");
    setWfDesc(wf.description || "");
    setSteps((wf.steps || []).map((s) => ({ ...s })));
    setShowBuilder(true);
  };

  const runWorkflow = async (name) => {
    await postJson(`/workflows/${name}/run`, {});
    refresh?.();
  };

  const allStepIds = steps.map((s) => s.step_id);

  const manualForm = (
    <div>
      <input type="text" value={wfName} onChange={(e) => setWfName(e.target.value)} placeholder="Workflow name" className="w-full mb-2 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
      <input type="text" value={wfDesc} onChange={(e) => setWfDesc(e.target.value)} placeholder="Description (optional)" className="w-full mb-3 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />

      <div className="mb-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] text-[var(--color-secondary)] uppercase tracking-[0.15em]">Steps</span>
          <button type="button" onClick={addStep} className="text-[11px] text-[var(--color-tertiary)] hover:text-white transition-colors bg-transparent border-none p-0">+ Add step</button>
        </div>
        {steps.map((step, i) => (
          <WorkflowStepEditor
            key={step.step_id}
            step={step} index={i} tools={tools}
            onChange={(s) => updateStep(i, s)}
            onRemove={() => removeStep(i)}
            onMoveUp={() => moveStep(i, -1)}
            onMoveDown={() => moveStep(i, 1)}
            isFirst={i === 0} isLast={i === steps.length - 1}
            allStepIds={allStepIds}
          />
        ))}
        {steps.length === 0 && <p className="text-[var(--color-tertiary)] text-[12px]">Click + Add step to begin.</p>}
      </div>

      {error && <p className="text-[var(--color-status-red)] text-[13px] mb-2">{error}</p>}
      <button type="button" onClick={saveManual} disabled={adding || !wfName.trim() || steps.length === 0} className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-full px-4 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all disabled:opacity-30">
        {adding ? "Saving…" : "Save workflow"}
      </button>
    </div>
  );

  const claudeForm = (
    <div>
      <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={"Describe your workflow, e.g.:\n\n'Relax a crystal structure with MACE, compute magnetic intrinsic properties, run finite-temperature spin dynamics, then simulate hysteresis to get Hc.'"} rows={3} className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-4 py-3 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none mb-3" />
      <button type="button" onClick={designWithClaude} disabled={busy || !prompt.trim()} className="bg-transparent border border-white/20 hover:border-white/40 rounded-full px-4 py-1.5 text-[13px] font-medium text-white transition-all disabled:opacity-30">
        {busy ? "Thinking…" : proposal ? "Regenerate" : "Propose workflow"}
      </button>
      {error && <p className="text-[var(--color-status-red)] text-[13px] mt-2">{error}</p>}
      {proposal?.workflow && (
        <div className="mt-4 border border-[var(--color-line)] rounded-2xl p-4">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-3">Proposed workflow</p>
          <div className="text-[14px] text-white font-medium mb-1">{proposal.workflow.name}</div>
          {proposal.workflow.description && <p className="text-[12px] text-[var(--color-tertiary)] mb-3">{proposal.workflow.description}</p>}
          {proposal.workflow.steps?.map((s, i) => (
            <div key={i} className="flex items-center gap-2 py-1 text-[13px]">
              <span className="text-[var(--color-tertiary)] font-mono text-[11px] w-6">{s.step_id}</span>
              <span className="text-white">{s.operation}</span>
              {s.depends_on?.length > 0 && <span className="text-[11px] text-[var(--color-tertiary)]">← {s.depends_on.join(", ")}</span>}
            </div>
          ))}
          {proposal.notes && <p className="text-[12px] text-[var(--color-secondary)] italic mt-2">{proposal.notes}</p>}
          <RefinementPrompt onRefine={refineProposal} busy={busy} placeholder="e.g. 'add an XRD characterisation step after sintering'" />
          <button type="button" onClick={applyProposal} disabled={adding} className="mt-3 bg-white text-[var(--color-bg)] rounded-full px-5 py-1.5 text-[13px] font-semibold hover:bg-white/90 transition-all disabled:opacity-30">
            {adding ? "Saving…" : "Save workflow"}
          </button>
        </div>
      )}
    </div>
  );

  return (
    <Section title="Workflows">
      <div className="flex flex-col gap-2 mb-4">
        {workflows.map((w) => (
          <div key={w.name} className="flex items-center justify-between py-1.5">
            <span className="text-[14px] text-white">{w.name}</span>
            <div className="flex gap-2">
              <button type="button" onClick={() => cloneWorkflow(w)} className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1 text-[11px] font-medium text-[var(--color-secondary)] hover:text-white transition-all">Clone</button>
              <button type="button" onClick={() => runWorkflow(w.name)} className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1 text-[11px] font-medium text-[var(--color-secondary)] hover:text-white transition-all">Run</button>
            </div>
          </div>
        ))}
        {workflows.length === 0 && (
          <p className="text-[var(--color-tertiary)] text-[13px]">No workflows registered.</p>
        )}
      </div>
      {!showBuilder ? (
        <button type="button" onClick={() => setShowBuilder(true)} className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-full px-4 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all">
          + New workflow
        </button>
      ) : (
        <div className="border border-[var(--color-line)] rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)]">Workflow builder</span>
            <button type="button" onClick={() => { setShowBuilder(false); setSteps([]); setWfName(""); setProposal(null); }} className="text-[11px] text-[var(--color-tertiary)] hover:text-white bg-transparent border-none">Close</button>
          </div>
          <DualModeBuilder manual={manualForm} withClaude={claudeForm} />
        </div>
      )}
    </Section>
  );
}

function LabSection() {
  const [verifyResult, setVerifyResult] = useState(null);
  const [verifying, setVerifying] = useState(false);

  const verify = async () => {
    setVerifying(true);
    try {
      const res = await getJson("/verify");
      setVerifyResult(res);
    } catch (err) {
      setVerifyResult({ error: String(err) });
    } finally {
      setVerifying(false);
    }
  };

  return (
    <Section title="Lab">
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={verify}
          disabled={verifying}
          className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all disabled:opacity-30"
        >
          {verifying ? "Verifying…" : "Verify integrity"}
        </button>
        <a
          href="/export/ro-crate"
          download
          className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all no-underline"
        >
          Export RO-Crate
        </a>
        <a
          href="/export/prov"
          download
          className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all no-underline"
        >
          Export PROV
        </a>
      </div>
      {verifyResult && (
        <div className="mt-3">
          <KeyValue data={verifyResult} />
        </div>
      )}
    </Section>
  );
}
