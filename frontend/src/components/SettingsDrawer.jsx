import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import KeyValue from "./KeyValue";
import StatusIndicator from "./StatusIndicator";
import SlideOver from "./SlideOver";
import { getJson, postJson } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

export default function SettingsDrawer({ open, onClose, status, refresh }) {
  return (
    <SlideOver open={open} onClose={onClose} width="max-w-xl">
      <motion.div initial="hidden" animate="visible" variants={stagger}>
        <motion.h3
          variants={fadeInUp}
          className="text-[36px] font-normal text-white tracking-[-0.02em] mb-8"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Settings
        </motion.h3>

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

function ResourcesSection({ status, refresh }) {
  const resources = status?.resources || [];
  const [name, setName] = useState("");
  const [kind, setKind] = useState("computer");
  const [adding, setAdding] = useState(false);

  const add = async () => {
    if (!name.trim()) return;
    setAdding(true);
    try {
      await postJson("/resources", { name: name.trim(), kind, capabilities: {} });
      setName("");
      refresh?.();
    } finally {
      setAdding(false);
    }
  };

  return (
    <Section title="Resources">
      <div className="flex flex-col gap-2 mb-4">
        {resources.map((r) => (
          <div key={r.name} className="flex items-center gap-3 py-1.5">
            <StatusIndicator status={r.state} pulse={r.state === "busy"} />
            <span className="text-[14px] text-white">{r.name}</span>
            <span className="text-[12px] text-[var(--color-secondary)]">{r.kind}</span>
          </div>
        ))}
        {resources.length === 0 && (
          <p className="text-[var(--color-tertiary)] text-[13px]">No resources registered.</p>
        )}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Resource name"
          className="flex-1 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors"
        />
        <input
          type="text"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          placeholder="Kind"
          className="w-28 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors"
        />
        <button
          type="button"
          onClick={add}
          disabled={adding || !name.trim()}
          className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all disabled:opacity-30"
        >
          Add
        </button>
      </div>
    </Section>
  );
}

function ToolsSection({ status, refresh }) {
  const tools = status?.tools || [];
  const [yaml, setYaml] = useState("");
  const [adding, setAdding] = useState(false);

  const add = async () => {
    if (!yaml.trim()) return;
    setAdding(true);
    try {
      await postJson("/tools/register-yaml", { yaml: yaml.trim() });
      setYaml("");
      refresh?.();
    } catch { }
    finally { setAdding(false); }
  };

  return (
    <Section title="Tools">
      <div className="flex flex-col gap-2 mb-4">
        {tools.map((t) => (
          <div key={t.capability} className="py-1.5">
            <span className="text-[14px] text-white">{t.capability}</span>
            {t.resource_kind && (
              <span className="ml-2 text-[12px] text-[var(--color-secondary)]">→ {t.resource_kind}</span>
            )}
          </div>
        ))}
        {tools.length === 0 && (
          <p className="text-[var(--color-tertiary)] text-[13px]">No tools registered.</p>
        )}
      </div>
      <textarea
        value={yaml}
        onChange={(e) => setYaml(e.target.value)}
        placeholder="Paste tool YAML…"
        rows={4}
        className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-4 py-3 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none mb-2"
        style={{ fontFamily: "var(--font-mono)" }}
      />
      <button
        type="button"
        onClick={add}
        disabled={adding || !yaml.trim()}
        className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all disabled:opacity-30"
      >
        Register tool
      </button>
    </Section>
  );
}

function WorkflowsSection({ status, refresh }) {
  const workflows = status?.workflows || [];

  const runWorkflow = async (name) => {
    await postJson(`/workflows/${name}/run`, {});
    refresh?.();
  };

  return (
    <Section title="Workflows">
      <div className="flex flex-col gap-2">
        {workflows.map((w) => (
          <div key={w.name} className="flex items-center justify-between py-1.5">
            <span className="text-[14px] text-white">{w.name}</span>
            <button
              type="button"
              onClick={() => runWorkflow(w.name)}
              className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1 text-[11px] font-medium text-[var(--color-secondary)] hover:text-white transition-all"
            >
              Run
            </button>
          </div>
        ))}
        {workflows.length === 0 && (
          <p className="text-[var(--color-tertiary)] text-[13px]">No workflows registered.</p>
        )}
      </div>
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
