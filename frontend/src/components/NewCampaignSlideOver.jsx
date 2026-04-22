import { useState } from "react";
import { motion } from "framer-motion";

import KeyValue from "./KeyValue";
import SlideOver from "./SlideOver";
import { postJson } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

export default function NewCampaignSlideOver({ open, onClose, status, refresh }) {
  const defaultText = (status?.tools || []).some((t) => t.capability === "superellipse_hysteresis")
    ? "Maximise small-signal sensitivity of a superellipse sensor element. Vary Ms, K1, a, b, n. Accept when sensitivity >= 1.5 1/T. Use a simple Bayesian optimiser; budget 12 runs."
    : "Describe the next campaign in plain language. Autolab will draft the plan before anything runs.";

  const [text, setText] = useState(defaultText);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const design = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await postJson("/campaigns/design", { text });
      setDraft(res);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!draft?.campaign) return;
    const lowered = text.toLowerCase();
    const planner = lowered.includes("random")
      ? "heuristic"
      : (status?.planners_available || []).includes("bo")
        ? "bo"
        : "heuristic";

    const plannerConfig = {};
    if (planner === "bo" && (status?.tools || []).length) {
      const tool = (status.tools || []).find((t) => t.capability === "superellipse_hysteresis") || status.tools[0];
      plannerConfig.operation = tool.capability;
      if (tool.capability === "superellipse_hysteresis") {
        plannerConfig.parameter_space = {
          Ms: { type: "float", low: 6e5, high: 1.6e6 },
          K1: { type: "float", low: 0, high: 1e4 },
          a: { type: "float", low: 80, high: 240 },
          b: { type: "float", low: 60, high: 200 },
          n: { type: "float", low: 2, high: 6 },
        };
        plannerConfig.fixed_inputs = {
          A_ex: 1.3e-11,
          thickness: 5,
          H_max: 8e4,
          cell_size: 3,
          n_steps: 41,
        };
        plannerConfig.initial_random = 3;
        plannerConfig.candidate_pool = 512;
      }
    }

    try {
      await postJson("/campaigns", {
        name: draft.campaign.name || "designed-campaign",
        description: draft.campaign.description,
        objective: draft.campaign.objective,
        acceptance: draft.campaign.acceptance,
        budget: draft.campaign.budget ?? 12,
        parallelism: draft.campaign.parallelism ?? 1,
        priority: 50,
        planner,
        planner_config: plannerConfig,
        use_claude_policy: Boolean(status?.claude_configured),
      });
      setDraft(null);
      refresh?.();
      onClose();
    } catch (err) {
      setError(String(err));
    }
  };

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
          Describe what you want to optimise. Autolab will draft a plan for your approval.
        </motion.p>

        <motion.textarea
          variants={fadeInUp}
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-5 py-4 text-[15px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none"
        />

        <motion.div variants={fadeInUp} className="flex gap-3 mt-4">
          <button
            type="button"
            onClick={design}
            disabled={busy || !text.trim()}
            className="bg-transparent border border-white/20 hover:border-white/40 rounded-full px-5 py-2 text-[14px] font-medium text-white transition-all disabled:opacity-30"
          >
            {busy ? "Designing…" : "Design"}
          </button>
          {draft && (
            <button
              type="button"
              onClick={submit}
              className="bg-white text-[var(--color-bg)] rounded-full px-5 py-2 text-[14px] font-semibold hover:bg-white/90 transition-all"
            >
              Approve & start
            </button>
          )}
        </motion.div>

        {error && (
          <motion.p variants={fadeInUp} className="text-[var(--color-status-red)] text-[13px] mt-3">
            {error}
          </motion.p>
        )}

        {draft?.campaign && (
          <motion.div
            variants={fadeInUp}
            className="mt-8 border border-[var(--color-line)] rounded-2xl p-6"
          >
            <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-3">
              Draft preview
            </p>
            <h4
              className="text-[24px] font-normal text-white tracking-[-0.02em] mb-1"
              style={{ fontFamily: "var(--font-serif)" }}
            >
              {draft.campaign.name || "Campaign"}
            </h4>
            <p className="text-[13px] text-[var(--color-secondary)] mb-4">
              {draft.campaign.description}
            </p>
            <KeyValue data={{
              objective: draft.campaign.objective?.key || "--",
              budget: draft.campaign.budget,
              parallelism: draft.campaign.parallelism || 1,
            }} />
            {draft.notes && (
              <p className="mt-4 text-[13px] text-[var(--color-secondary)] italic">
                {draft.notes}
              </p>
            )}
          </motion.div>
        )}
      </motion.div>
    </SlideOver>
  );
}
