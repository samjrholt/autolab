import { useState } from "react";
import { motion } from "framer-motion";

import KeyValue from "./KeyValue";
import SlideOver from "./SlideOver";
import DualModeBuilder from "./shared/DualModeBuilder";
import RefinementPrompt from "./shared/RefinementPrompt";
import { postJson } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

const PLANNER_OPTIONS = [
  { value: "heuristic", label: "Heuristic", desc: "Simple rule-based planner — good for fixed workflows" },
  { value: "bo", label: "Bayesian Optimisation", desc: "GP-EI via Optuna — best for continuous parameter spaces" },
  { value: "optuna", label: "Optuna", desc: "Tree-structured Parzen estimator — flexible sampler" },
  { value: "add_demo_optuna", label: "add_demo (Optuna + workflow chain)", desc: "Chains add_two → add_three; optimises x in [0,10]. Used for the add_demo example." },
  { value: "claude", label: "Claude (LLM)", desc: "Opus 4.7 as planner — adaptive, vision-capable, best for exploratory campaigns" },
];

const OPERATORS = [">=", "<=", ">", "<", "==", "in", "not_in"];

function AcceptanceCriteriaBuilder({ rules, onChange }) {
  const addRule = () => onChange([...rules, { key: "", op: ">=", value: "" }]);
  const removeRule = (i) => onChange(rules.filter((_, j) => j !== i));
  const update = (i, field, val) => onChange(rules.map((r, j) => j === i ? { ...r, [field]: val } : r));

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-[var(--color-secondary)] uppercase tracking-[0.15em]">Acceptance criteria</span>
        <button type="button" onClick={addRule} className="text-[11px] text-[var(--color-tertiary)] hover:text-white transition-colors bg-transparent border-none p-0">+ Add rule</button>
      </div>
      {rules.map((r, i) => (
        <div key={i} className="flex gap-2 mb-1.5 items-center">
          <input value={r.key} onChange={(e) => update(i, "key", e.target.value)} placeholder="output_key" className="flex-1 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" style={{ fontFamily: "var(--font-mono)" }} />
          <select value={r.op} onChange={(e) => update(i, "op", e.target.value)} className="w-16 bg-[var(--color-bg)] border border-[var(--color-line)] rounded px-1 py-1 text-[12px] text-white focus:outline-none" style={{ fontFamily: "var(--font-mono)" }}>
            {OPERATORS.map((op) => <option key={op} value={op}>{op}</option>)}
          </select>
          <input value={r.value} onChange={(e) => update(i, "value", e.target.value)} placeholder="threshold" className="w-24 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" style={{ fontFamily: "var(--font-mono)" }} />
          <button type="button" onClick={() => removeRule(i)} className="text-[11px] text-[var(--color-tertiary)] hover:text-[var(--color-status-red)] bg-transparent border-none px-1 transition-colors">×</button>
        </div>
      ))}
    </div>
  );
}

function rulesToAcceptance(rules) {
  const acc = {};
  for (const { key, op, value } of rules) {
    if (!key.trim()) continue;
    const n = Number(value);
    acc[key.trim()] = { [op]: isNaN(n) ? value : n };
  }
  return Object.keys(acc).length > 0 ? { rules: acc } : undefined;
}

export default function NewCampaignSlideOver({ open, onClose, status, refresh }) {
  // Manual form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [objectiveKey, setObjectiveKey] = useState("");
  const [direction, setDirection] = useState("maximise");
  const [workflow, setWorkflow] = useState("");
  const [planner, setPlanner] = useState("heuristic");
  const [plannerConfig, setPlannerConfig] = useState({});
  const [budget, setBudget] = useState("12");
  const [parallelism, setParallelism] = useState("1");
  const [rules, setRules] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Claude mode state
  const [text, setText] = useState("");
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);

  const workflows = status?.workflows || [];
  const planners = status?.planners_available || ["heuristic"];
  const useClaude = Boolean(status?.claude_configured);

  // -- Manual submit --
  const submitManual = async () => {
    if (!name.trim()) return;
    setSubmitting(true); setError("");
    try {
      const pc = { ...plannerConfig };
      if (planner === "bo" && !pc.operation && (status?.tools || []).length) {
        pc.operation = status.tools[0].capability;
      }
      await postJson("/campaigns", {
        name: name.trim(),
        description,
        objective: objectiveKey ? { key: objectiveKey, direction } : undefined,
        acceptance: rulesToAcceptance(rules),
        budget: Number(budget) || 12,
        parallelism: Number(parallelism) || 1,
        priority: 50,
        planner,
        planner_config: pc,
        workflow: workflow || undefined,
        use_claude_policy: useClaude,
      });
      refresh?.();
      onClose();
    } catch (err) { setError(String(err)); }
    finally { setSubmitting(false); }
  };

  // -- Claude design --
  const design = async () => {
    setBusy(true); setError("");
    try {
      const res = await postJson("/campaigns/design", { text, previous: draft?.campaign, instruction: null });
      setDraft(res);
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  };

  const refineDraft = async (instruction) => {
    setBusy(true); setError("");
    try {
      const res = await postJson("/campaigns/design", { text, previous: draft?.campaign, instruction });
      setDraft(res);
    } catch (err) { setError(String(err)); }
    finally { setBusy(false); }
  };

  const submitDraft = async () => {
    if (!draft?.campaign) return;
    setSubmitting(true); setError("");
    try {
      const lowered = text.toLowerCase();
      const pl = lowered.includes("random") ? "heuristic"
        : planners.includes("bo") ? "bo" : "heuristic";
      const pc = {};
      if (pl === "bo" && (status?.tools || []).length) {
        pc.operation = status.tools[0].capability;
      }
      await postJson("/campaigns", {
        name: draft.campaign.name || "designed-campaign",
        description: draft.campaign.description,
        objective: draft.campaign.objective,
        acceptance: draft.campaign.acceptance,
        budget: draft.campaign.budget ?? 12,
        parallelism: draft.campaign.parallelism ?? 1,
        priority: 50,
        planner: pl,
        planner_config: pc,
        use_claude_policy: useClaude,
      });
      setDraft(null);
      refresh?.();
      onClose();
    } catch (err) { setError(String(err)); }
    finally { setSubmitting(false); }
  };

  const updateDraft = (field, value) => {
    setDraft((prev) => ({ ...prev, campaign: { ...prev.campaign, [field]: value } }));
  };

  const plannerConfigFields = () => {
    if (planner === "bo") {
      return (
        <div className="mt-2 mb-3 p-3 border border-[var(--color-line)] rounded-xl">
          <span className="text-[11px] text-[var(--color-secondary)] uppercase tracking-[0.15em] block mb-2">BO config</span>
          <input value={plannerConfig.operation || ""} onChange={(e) => setPlannerConfig({ ...plannerConfig, operation: e.target.value })} placeholder="operation to optimise" className="w-full bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
        </div>
      );
    }
    if (planner === "optuna") {
      return (
        <div className="mt-2 mb-3 p-3 border border-[var(--color-line)] rounded-xl">
          <span className="text-[11px] text-[var(--color-secondary)] uppercase tracking-[0.15em] block mb-2">Optuna config</span>
          <div className="flex gap-2">
            <input value={plannerConfig.operation || ""} onChange={(e) => setPlannerConfig({ ...plannerConfig, operation: e.target.value })} placeholder="operation to optimise" className="flex-1 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
            <input value={plannerConfig.n_trials || ""} onChange={(e) => setPlannerConfig({ ...plannerConfig, n_trials: e.target.value })} placeholder="n_trials" className="w-24 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
          </div>
        </div>
      );
    }
    return null;
  };

  const fillAddDemo = () => {
    setName("find_max_add_demo");
    setDescription("Maximise x+5 via add_two → add_three chain. x ∈ [0,10], optimal result=15.");
    setObjectiveKey("result");
    setDirection("maximise");
    setPlanner("add_demo_optuna");
    setPlannerConfig({});
    setBudget("24");
    setRules([]);
  };

  const hasAddDemo = (status?.tools || []).some((t) => t.capability === "add_two");

  const manualForm = (
    <div>
      {hasAddDemo ? (
        <button
          type="button"
          onClick={fillAddDemo}
          className="w-full mb-4 border border-dashed border-[var(--color-accent)] text-[var(--color-accent)] rounded-lg px-3 py-2 text-[12px] hover:bg-[var(--color-accent-glow)] transition-all"
        >
          ⚡ Quick-fill add_demo template
        </button>
      ) : null}
      <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Campaign name" className="w-full mb-2 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
      <input type="text" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" className="w-full mb-3 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />

      <div className="flex gap-2 mb-3">
        <input type="text" value={objectiveKey} onChange={(e) => setObjectiveKey(e.target.value)} placeholder="Objective key (e.g. coercivity_kAm)" className="flex-1 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
        <select value={direction} onChange={(e) => setDirection(e.target.value)} className="w-32 bg-[var(--color-bg)] border border-[var(--color-line)] rounded-lg px-2 py-1.5 text-[13px] text-white focus:outline-none">
          <option value="maximise">Maximise</option>
          <option value="minimise">Minimise</option>
        </select>
      </div>

      {workflows.length > 0 && (
        <select value={workflow} onChange={(e) => setWorkflow(e.target.value)} className="w-full mb-3 bg-[var(--color-bg)] border border-[var(--color-line)] rounded-lg px-2 py-1.5 text-[13px] text-white focus:outline-none">
          <option value="">Workflow (optional)</option>
          {workflows.map((w) => <option key={w.name} value={w.name}>{w.name}</option>)}
        </select>
      )}

      <div className="mb-2">
        <span className="text-[11px] text-[var(--color-secondary)] uppercase tracking-[0.15em] block mb-1">Planner</span>
        <div className="flex flex-col gap-1">
          {PLANNER_OPTIONS.filter((p) => planners.includes(p.value) || p.value === "heuristic" || p.value === "claude").map((p) => (
            <label key={p.value} className={`flex items-start gap-2 p-2 rounded-lg border cursor-pointer transition-all ${planner === p.value ? "border-white/40 bg-white/[0.03]" : "border-transparent hover:bg-white/[0.02]"}`}>
              <input type="radio" name="planner" value={p.value} checked={planner === p.value} onChange={(e) => { setPlanner(e.target.value); setPlannerConfig({}); }} className="accent-white mt-0.5" />
              <div>
                <span className="text-[13px] text-white font-medium">{p.label}</span>
                <p className="text-[11px] text-[var(--color-tertiary)] mt-0.5">{p.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {plannerConfigFields()}

      <div className="flex gap-3 mb-3">
        <label className="text-[12px] text-[var(--color-secondary)]">
          Budget
          <input type="number" min={1} value={budget} onChange={(e) => setBudget(e.target.value)} className="ml-2 w-16 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] text-white focus:outline-none" />
        </label>
        <label className="text-[12px] text-[var(--color-secondary)]">
          Parallelism
          <input type="number" min={1} max={8} value={parallelism} onChange={(e) => setParallelism(e.target.value)} className="ml-2 w-16 bg-transparent border border-[var(--color-line)] rounded px-2 py-1 text-[12px] text-white focus:outline-none" />
        </label>
      </div>

      <AcceptanceCriteriaBuilder rules={rules} onChange={setRules} />

      {error && <p className="text-[var(--color-status-red)] text-[13px] mt-2">{error}</p>}
      <button type="button" onClick={submitManual} disabled={submitting || !name.trim()} className="mt-4 bg-white text-[var(--color-bg)] rounded-full px-5 py-2 text-[14px] font-semibold hover:bg-white/90 transition-all disabled:opacity-30">
        {submitting ? "Starting…" : "Start campaign"}
      </button>
    </div>
  );

  const claudeForm = (
    <div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={"Describe what you want to optimise, e.g.:\n\n'Find the best ML architecture to fit my phonon dataset. Try random forest, gradient boosting, and small neural nets. Minimise MAE on the test set, budget 20 trials.'"}
        rows={6}
        className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-5 py-4 text-[14px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none"
      />
      <div className="flex gap-3 mt-4">
        <button type="button" onClick={design} disabled={busy || !text.trim()} className="bg-transparent border border-white/20 hover:border-white/40 rounded-full px-5 py-2 text-[14px] font-medium text-white transition-all disabled:opacity-30">
          {busy ? "Designing…" : draft ? "Regenerate" : "Design"}
        </button>
        {draft && (
          <button type="button" onClick={submitDraft} disabled={submitting} className="bg-white text-[var(--color-bg)] rounded-full px-5 py-2 text-[14px] font-semibold hover:bg-white/90 transition-all disabled:opacity-30">
            {submitting ? "Starting…" : "Approve & start"}
          </button>
        )}
      </div>

      {error && <p className="text-[var(--color-status-red)] text-[13px] mt-3">{error}</p>}

      {draft?.campaign && (
        <div className="mt-6 border border-[var(--color-line)] rounded-2xl p-5">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-3">Draft preview (edit inline)</p>
          <input value={draft.campaign.name || ""} onChange={(e) => updateDraft("name", e.target.value)} placeholder="Campaign name" className="w-full mb-2 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[18px] text-white font-normal focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" style={{ fontFamily: "var(--font-serif)" }} />
          <input value={draft.campaign.description || ""} onChange={(e) => updateDraft("description", e.target.value)} placeholder="Description" className="w-full mb-3 bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1.5 text-[13px] text-[var(--color-secondary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors" />
          <KeyValue data={{
            objective: draft.campaign.objective?.key || "--",
            direction: draft.campaign.objective?.direction || "maximize",
            budget: draft.campaign.budget,
            parallelism: draft.campaign.parallelism || 1,
          }} />
          {draft.notes && <p className="mt-3 text-[13px] text-[var(--color-secondary)] italic">{draft.notes}</p>}
          <RefinementPrompt onRefine={refineDraft} busy={busy} placeholder="e.g. 'increase budget to 30, add constraint that MAE < 0.1'" />
        </div>
      )}
    </div>
  );

  return (
    <SlideOver open={open} onClose={onClose} width="max-w-xl">
      <motion.div initial="hidden" animate="visible" variants={stagger}>
        <motion.h3
          variants={fadeInUp}
          className="text-[36px] font-normal text-white tracking-[-0.02em] mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          New campaign
        </motion.h3>
        <motion.p variants={fadeInUp} className="text-[var(--color-secondary)] mb-8">
          Configure your campaign manually or let Claude design one from a description.
        </motion.p>
        <motion.div variants={fadeInUp}>
          <DualModeBuilder manual={manualForm} withClaude={claudeForm} />
        </motion.div>
      </motion.div>
    </SlideOver>
  );
}
