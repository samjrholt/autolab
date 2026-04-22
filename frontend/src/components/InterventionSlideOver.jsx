import { useEffect, useState } from "react";
import { motion } from "framer-motion";

import SlideOver from "./SlideOver";
import { postJson } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

export default function InterventionSlideOver({ open, onClose, campaigns, refresh }) {
  const [campaignId, setCampaignId] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!campaignId && campaigns[0]) {
      setCampaignId(campaigns[0].campaign_id);
    }
  }, [campaignId, campaigns]);

  const submit = async () => {
    if (!campaignId || !body.trim()) return;
    setBusy(true);
    setError("");
    try {
      await postJson(`/campaigns/${campaignId}/intervene`, { body });
      setBody("");
      refresh?.();
      onClose();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <SlideOver open={open} onClose={onClose} width="max-w-lg">
      <motion.div initial="hidden" animate="visible" variants={stagger}>
        <motion.h3
          variants={fadeInUp}
          className="text-[36px] font-normal text-white tracking-[-0.02em] mb-2"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Intervene
        </motion.h3>
        <motion.p variants={fadeInUp} className="text-[var(--color-secondary)] mb-8">
          Write a human intervention. It becomes a hashed record in the ledger.
        </motion.p>

        {campaigns.length > 1 && (
          <motion.select
            variants={fadeInUp}
            value={campaignId}
            onChange={(e) => setCampaignId(e.target.value)}
            className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-4 py-3 text-[14px] mb-4 focus:outline-none focus:border-[var(--color-line-hover)] transition-colors"
          >
            {campaigns.map((c) => (
              <option key={c.campaign_id} value={c.campaign_id}>
                {c.name} · {c.status}
              </option>
            ))}
          </motion.select>
        )}

        <motion.textarea
          variants={fadeInUp}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={6}
          placeholder="Restrict Co above 30%. Reduce the search space and replan around the strongest candidate."
          className="w-full bg-transparent border border-[var(--color-line)] rounded-xl px-5 py-4 text-[15px] placeholder:text-[var(--color-tertiary)] focus:outline-none focus:border-[var(--color-line-hover)] transition-colors resize-none"
        />

        <motion.div variants={fadeInUp} className="mt-4">
          <button
            type="button"
            onClick={submit}
            disabled={busy || !campaignId || !body.trim()}
            className="bg-white text-[var(--color-bg)] rounded-full px-5 py-2 text-[14px] font-semibold hover:bg-white/90 transition-all disabled:opacity-30"
          >
            {busy ? "Submitting…" : "Submit intervention"}
          </button>
        </motion.div>

        {error && (
          <motion.p variants={fadeInUp} className="text-[var(--color-status-red)] text-[13px] mt-3">
            {error}
          </motion.p>
        )}
      </motion.div>
    </SlideOver>
  );
}
