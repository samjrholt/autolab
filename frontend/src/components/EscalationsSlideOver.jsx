import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import SlideOver from "./SlideOver";
import { getJson, postJson } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

export default function EscalationsSlideOver({ open, onClose, refresh }) {
  const [escalations, setEscalations] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    getJson("/escalations")
      .then((data) => setEscalations(data.escalations || data || []))
      .catch(() => setEscalations([]))
      .finally(() => setLoading(false));
  }, [open]);

  const resolve = async (id, choice, note = "") => {
    await postJson(`/escalations/${id}/resolve`, { choice, note });
    setEscalations((prev) => prev.filter((e) => e.id !== id));
    refresh?.();
  };

  return (
    <SlideOver open={open} onClose={onClose} width="max-w-lg">
      <motion.div initial="hidden" animate="visible" variants={stagger}>
        <motion.h3
          variants={fadeInUp}
          className="text-[36px] font-normal text-white tracking-[-0.02em] mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Escalations
        </motion.h3>
        <motion.p variants={fadeInUp} className="text-[var(--color-secondary)] mb-8">
          Decisions that need a human.
        </motion.p>

        {loading && (
          <motion.p variants={fadeInUp} className="text-[var(--color-secondary)]">Loading…</motion.p>
        )}

        {!loading && escalations.length === 0 && (
          <motion.p variants={fadeInUp} className="text-[var(--color-tertiary)]">
            Nothing needs your attention.
          </motion.p>
        )}

        {escalations.map((esc) => (
          <EscalationCard key={esc.id} escalation={esc} onResolve={resolve} />
        ))}
      </motion.div>
    </SlideOver>
  );
}

/** Find any image URL or base64 in the outputs dict. */
function findImageInOutputs(outputs) {
  if (!outputs) return null;
  for (const [key, val] of Object.entries(outputs)) {
    if (typeof val === "string") {
      if (val.startsWith("data:image/") || /\.(png|jpg|jpeg|gif|svg)$/i.test(val)) return val;
    }
    if (key === "figure_png" || key === "image" || key === "plot") {
      if (typeof val === "string") {
        // Could be base64 without prefix
        if (val.length > 100 && !val.includes(" ")) return `data:image/png;base64,${val}`;
      }
    }
  }
  return null;
}

const DEFAULT_ACTIONS = ["continue", "retry", "stop", "add_step"];

function EscalationCard({ escalation, onResolve }) {
  const [choice, setChoice] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const handleResolve = async () => {
    if (!choice) return;
    setBusy(true);
    await onResolve(escalation.id, choice, note);
    setBusy(false);
  };

  const imageUrl = findImageInOutputs(escalation.outputs);
  const options = escalation.options?.length > 0 ? escalation.options : DEFAULT_ACTIONS;

  return (
    <motion.div
      variants={fadeInUp}
      className="border border-[var(--color-line)] rounded-2xl p-5 mb-4"
    >
      <p className="text-[15px] font-semibold text-white mb-1">
        {escalation.operation || "Decision required"}
      </p>
      <p className="text-[13px] text-[var(--color-secondary)] mb-3">
        {escalation.reason || escalation.message || "The planner needs guidance."}
      </p>

      {/* Image preview from outputs */}
      {imageUrl && (
        <div className="mb-3 rounded-xl overflow-hidden border border-[var(--color-line)]">
          <img src={imageUrl} alt="Result figure" className="w-full h-auto max-h-[200px] object-contain bg-white/5" />
        </div>
      )}

      {/* Context data if present */}
      {escalation.context && Object.keys(escalation.context).length > 0 && (
        <div className="mb-3 text-[12px] text-[var(--color-tertiary)] border-l-2 border-[var(--color-line)] pl-3">
          {Object.entries(escalation.context).map(([k, v]) => (
            <div key={k}><span className="text-[var(--color-secondary)]">{k}:</span> {typeof v === "object" ? JSON.stringify(v) : String(v)}</div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-3">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => setChoice(opt)}
            className={`bg-transparent border rounded-full px-3 py-1 text-[12px] transition-all ${
              choice === opt
                ? "border-white text-white"
                : "border-[var(--color-line)] text-[var(--color-secondary)] hover:border-[var(--color-line-hover)]"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note…"
        rows={2}
        className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-3 py-2 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none mb-3"
      />
      <button
        type="button"
        onClick={handleResolve}
        disabled={busy || !choice}
        className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-full px-4 py-1.5 text-[13px] font-medium text-[var(--color-secondary)] hover:text-white transition-all disabled:opacity-30"
      >
        {busy ? "Resolving…" : "Resolve"}
      </button>
    </motion.div>
  );
}
