import { useMemo } from "react";
import { motion } from "framer-motion";

import MetricCard from "./MetricCard";
import MiniChart from "./MiniChart";
import StatusIndicator from "./StatusIndicator";
import { extractSpotlight, sortByCreatedDesc } from "../lib/helpers";
import { formatDuration, formatNumber } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

export default function Overview({
  status,
  records,
  counts,
  campaigns,
  resources,
  etaByCampaign,
  onSelectCampaign,
  onShowResources,
  onSelectRecord,
}) {
  const escalationCount = status?.escalations?.length || 0;
  const runningCampaigns = campaigns.filter((c) => c.status === "running");
  const totalCampaigns = campaigns.length;

  // Build the hero headline dynamically
  const headline = useMemo(() => {
    if (escalationCount > 0) {
      return `${escalationCount} decision${escalationCount > 1 ? "s" : ""} awaiting your call.`;
    }
    if (runningCampaigns.length === 0 && totalCampaigns === 0) {
      return "Ready to begin.";
    }
    if (runningCampaigns.length === 0) {
      return "All campaigns complete.";
    }
    if (runningCampaigns.length === 1) {
      return `Running ${runningCampaigns[0].name}.`;
    }
    return `Running ${runningCampaigns.length} campaigns across ${resources.length} resource${resources.length !== 1 ? "s" : ""}.`;
  }, [escalationCount, runningCampaigns, totalCampaigns, resources.length]);

  const subhead = useMemo(() => {
    const activeCampaign = runningCampaigns[0];
    if (!activeCampaign) return "Launch a campaign to start the autonomous loop.";
    const dir = activeCampaign.direction || "maximise";
    const key = activeCampaign.objective_key || "objective";
    return `${dir} ${key} · budget ${activeCampaign.budget ?? "∞"} · ${activeCampaign.parallelism || 1} parallel lane${(activeCampaign.parallelism || 1) > 1 ? "s" : ""}`;
  }, [runningCampaigns]);

  // Latest interesting result
  const latestRecord = useMemo(
    () => sortByCreatedDesc(records).find((r) => r.record_status === "completed") || null,
    [records],
  );
  const spotlight = useMemo(
    () => extractSpotlight(latestRecord, formatNumber),
    [latestRecord],
  );

  // Resource summary
  const runningResources = resources.filter((r) => r.state === "busy" || r.state === "running").length;
  const idleResources = resources.length - runningResources;

  return (
    <div className="max-w-[960px] mx-auto px-8">
      {/* Hero glow */}
      <div className="glow-hero absolute inset-x-0 top-0 h-[400px] pointer-events-none" />

      {/* Hero headline */}
      <motion.div
        className="pt-24 pb-16 relative"
        initial="hidden"
        animate="visible"
        variants={stagger}
      >
        <motion.h1
          variants={fadeInUp}
          className="text-[clamp(48px,7vw,88px)] font-normal leading-[0.95] tracking-[-0.03em] text-white max-w-[14ch]"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          {headline}
        </motion.h1>
        <motion.p
          variants={fadeInUp}
          className="mt-6 text-[18px] text-[var(--color-secondary)] max-w-[48ch]"
        >
          {subhead}
        </motion.p>
      </motion.div>

      {/* Stats */}
      <motion.div
        className="flex gap-12 pb-16"
        initial="hidden"
        animate="visible"
        variants={stagger}
      >
        <MetricCard label="Records" value={status?.total_records ?? 0} />
        <MetricCard label="Running" value={counts.running || 0} />
        <MetricCard label="Completed" value={counts.completed || 0} />
        <MetricCard label="Failed" value={counts.failed || 0} />
      </motion.div>

      {/* Active campaigns strip */}
      {campaigns.length > 0 && (
        <motion.section
          className="pb-16"
          initial="hidden"
          animate="visible"
          variants={stagger}
        >
          <motion.p
            variants={fadeInUp}
            className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-4"
          >
            Campaigns
          </motion.p>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
            {campaigns.slice(0, 6).map((campaign) => (
              <motion.button
                key={campaign.campaign_id}
                variants={fadeInUp}
                type="button"
                onClick={() => onSelectCampaign?.(campaign)}
                className="text-left bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-2xl p-5 transition-all group"
              >
                <div className="flex items-center justify-between mb-3">
                  <span
                    className="text-[20px] font-normal text-white tracking-[-0.02em]"
                    style={{ fontFamily: "var(--font-serif)" }}
                  >
                    {campaign.name}
                  </span>
                  <StatusIndicator
                    status={campaign.status}
                    pulse={campaign.status === "running"}
                  />
                </div>
                <div className="flex items-baseline gap-4 text-[12px] text-[var(--color-secondary)]">
                  <span>{campaign.objective_key || "objective"}</span>
                  <span>
                    {campaign.completed_count ?? "?"} / {campaign.budget ?? "∞"}
                  </span>
                  <span>
                    ETA {formatDuration(etaByCampaign[campaign.campaign_id]?.remaining_seconds)}
                  </span>
                </div>
              </motion.button>
            ))}
          </div>
        </motion.section>
      )}

      {/* Resources summary */}
      {resources.length > 0 && (
        <motion.section className="pb-16" variants={fadeInUp} initial="hidden" animate="visible">
          <button
            type="button"
            onClick={onShowResources}
            className="bg-transparent border-none text-[13px] text-[var(--color-secondary)] hover:text-white transition-colors p-0"
          >
            {resources.length} resource{resources.length !== 1 ? "s" : ""}
            {runningResources > 0 ? ` · ${runningResources} active` : ""}
            {idleResources > 0 ? ` · ${idleResources} idle` : ""}
            <span className="ml-2 text-[var(--color-tertiary)]">→</span>
          </button>
        </motion.section>
      )}

      {/* Latest result spotlight */}
      {spotlight && (
        <motion.section
          className="pb-24"
          initial="hidden"
          animate="visible"
          variants={stagger}
        >
          <motion.p
            variants={fadeInUp}
            className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-4"
          >
            Latest result
          </motion.p>
          <motion.div
            variants={fadeInUp}
            className="relative rounded-2xl border border-[var(--color-line)] p-6 cursor-pointer hover:border-[var(--color-line-hover)] transition-all"
            onClick={() => latestRecord && onSelectRecord?.(latestRecord)}
          >
            <div className="glow-card absolute inset-0 rounded-2xl pointer-events-none" />
            <div className="relative">
              <h3
                className="text-[32px] font-normal text-white tracking-[-0.02em] mb-1"
                style={{ fontFamily: "var(--font-serif)" }}
              >
                {spotlight.title}
              </h3>
              <p className="text-[13px] text-[var(--color-secondary)] mb-6">
                {spotlight.subtitle}
              </p>
              {spotlight.points && (
                <div className="mb-6 rounded-xl overflow-hidden">
                  <MiniChart points={spotlight.points} height={180} />
                </div>
              )}
              <div className="flex gap-10">
                {spotlight.metrics.map((m) => (
                  <MetricCard key={m.label} label={m.label} value={m.value} unit={m.unit} />
                ))}
              </div>
            </div>
          </motion.div>
        </motion.section>
      )}
    </div>
  );
}
