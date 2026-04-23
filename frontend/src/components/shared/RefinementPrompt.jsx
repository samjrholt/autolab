import { useState } from "react";

/**
 * A small inline "refine with Claude" prompt used after an initial proposal
 * has been produced and (optionally) edited by the user.  The caller is
 * responsible for threading `previous` (the current proposal JSON) back into
 * the designer API.
 *
 * Props:
 *   onRefine(instruction) — async, called with the user's refinement text
 *   busy                  — externally controlled busy flag
 *   placeholder           — hint text (default: "e.g. 'make it 1600 K, add O2 atmosphere'")
 *   label                 — button text (default: "Refine with Claude")
 */
export default function RefinementPrompt({
  onRefine,
  busy = false,
  placeholder = "e.g. 'use workflow_name, optimise output_key, vary input_name'",
  label = "Refine with Claude",
}) {
  const [text, setText] = useState("");

  const submit = async () => {
    if (!text.trim() || busy) return;
    const value = text;
    setText("");
    await onRefine(value);
  };

  return (
    <div className="mt-4 border border-[var(--color-line)] rounded-xl p-4 bg-white/[0.01]">
      <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-2">
        Refine with Claude
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        rows={2}
        className="w-full bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-2 text-[13px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none"
      />
      <button
        type="button"
        onClick={submit}
        disabled={busy || !text.trim()}
        className="mt-2 bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-full px-4 py-1.5 text-[12px] font-medium text-[var(--color-secondary)] hover:text-white transition-all disabled:opacity-30"
      >
        {busy ? "Thinking…" : label}
      </button>
    </div>
  );
}
