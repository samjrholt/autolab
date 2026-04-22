import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import MetricCard from "./MetricCard";
import MiniChart from "./MiniChart";
import StatusIndicator from "./StatusIndicator";
import { cn, extractSpotlight, sortByCreatedDesc, statusLabel } from "../lib/helpers";
import { formatDuration, formatNumber, formatTime, postJson } from "../lib/api";
import { fadeInUp, stagger } from "../lib/motion";

export default function CampaignTab({
  campaigns,
  records,
  resources,
  etaByCampaign,
  selectedCampaignId,
  onSelectRecord,
  onOpenIntervention,
  onOpenNewCampaign,
  refresh,
}) {
  const [activeCampaignId, setActiveCampaignId] = useState(selectedCampaignId || null);

  // Sync from parent when navigating from Overview
  useEffect(() => {
    if (selectedCampaignId) setActiveCampaignId(selectedCampaignId);
  }, [selectedCampaignId]);

  // Auto-select first running campaign if none selected
  useEffect(() => {
    if (!activeCampaignId && campaigns.length) {
      const running = campaigns.find((c) => c.status === "running");
      setActiveCampaignId((running || campaigns[0]).campaign_id);
    }
  }, [activeCampaignId, campaigns]);

  const campaign = campaigns.find((c) => c.campaign_id === activeCampaignId) || null;
  const campaignRecords = useMemo(
    () => records.filter((r) => r.campaign_id === activeCampaignId),
    [records, activeCampaignId],
  );
  const recentRecords = useMemo(() => sortByCreatedDesc(campaignRecords).slice(0, 20), [campaignRecords]);
  const eta = etaByCampaign[activeCampaignId];

  // Latest result for this campaign
  const latestCompleted = useMemo(
    () => campaignRecords.find((r) => r.record_status === "completed") || null,
    [campaignRecords],
  );
  const spotlight = useMemo(() => extractSpotlight(latestCompleted, formatNumber), [latestCompleted]);

  // Group records by experiment
  const byExperiment = useMemo(() => {
    const map = new Map();
    for (const r of recentRecords) {
      const key = r.experiment_id || "default";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(r);
    }
    return map;
  }, [recentRecords]);

  // Resources used by this campaign
  const usedResources = useMemo(() => {
    const names = new Set(campaignRecords.map((r) => r.resource_name).filter(Boolean));
    return resources.filter((r) => names.has(r.name));
  }, [campaignRecords, resources]);

  // Show resource lanes
  const [showResources, setShowResources] = useState(false);

  // Lifecycle actions
  const handleLifecycle = async (action) => {
    if (!campaign) return;
    await postJson(`/campaigns/${campaign.campaign_id}/${action}`, {});
    refresh?.();
  };

  // Empty state
  if (!campaign) {
    return (
      <div className="max-w-[960px] mx-auto px-8 pt-24">
        <motion.div initial="hidden" animate="visible" variants={stagger}>
          <motion.h2
            variants={fadeInUp}
            className="text-[clamp(36px,5vw,56px)] font-normal leading-[0.95] tracking-[-0.03em] text-white"
            style={{ fontFamily: "var(--font-serif)" }}
          >
            No campaigns running.
          </motion.h2>
          <motion.p variants={fadeInUp} className="mt-4 text-[var(--color-secondary)]">
            Start one to watch the autonomous loop unfold.
          </motion.p>
          <motion.button
            variants={fadeInUp}
            type="button"
            onClick={onOpenNewCampaign}
            className="mt-8 bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-full px-6 py-2.5 text-[14px] font-medium text-white transition-all"
          >
            New campaign
          </motion.button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="max-w-[960px] mx-auto px-8 pt-16 pb-24">
      {/* Campaign header */}
      <motion.div
        className="flex items-start justify-between mb-12"
        initial="hidden"
        animate="visible"
        variants={stagger}
      >
        <div>
          <motion.div variants={fadeInUp} className="flex items-center gap-3 mb-2">
            {/* Campaign picker */}
            {campaigns.length > 1 && (
              <select
                value={activeCampaignId || ""}
                onChange={(e) => setActiveCampaignId(e.target.value)}
                className="bg-transparent border border-[var(--color-line)] rounded-lg px-3 py-1 text-[13px] text-[var(--color-secondary)]"
              >
                {campaigns.map((c) => (
                  <option key={c.campaign_id} value={c.campaign_id}>
                    {c.name} · {statusLabel(c.status)}
                  </option>
                ))}
              </select>
            )}
          </motion.div>
          <motion.h2
            variants={fadeInUp}
            className="text-[clamp(36px,5vw,56px)] font-normal leading-[0.95] tracking-[-0.03em] text-white"
            style={{ fontFamily: "var(--font-serif)" }}
          >
            {campaign.name}
          </motion.h2>
          <motion.p variants={fadeInUp} className="mt-3 text-[15px] text-[var(--color-secondary)]">
            {campaign.direction || "maximise"} {campaign.objective_key || "objective"} · budget {campaign.budget ?? "∞"}
          </motion.p>
        </div>

        {/* Lifecycle actions */}
        <motion.div variants={fadeInUp} className="flex items-center gap-3 pt-2">
          {campaign.status === "running" && (
            <>
              <LifecycleButton label="Pause" onClick={() => handleLifecycle("pause")} />
              <LifecycleButton label="Cancel" onClick={() => handleLifecycle("cancel")} danger />
            </>
          )}
          {campaign.status === "paused" && (
            <>
              <LifecycleButton label="Resume" onClick={() => handleLifecycle("resume")} />
              <LifecycleButton label="Cancel" onClick={() => handleLifecycle("cancel")} danger />
            </>
          )}
          <LifecycleButton label="Intervene" onClick={onOpenIntervention} />
          <a
            href={`/export/ro-crate?campaign_id=${activeCampaignId}`}
            download
            className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--color-secondary)] hover:text-white transition-all no-underline"
          >
            RO-Crate
          </a>
          <a
            href={`/export/prov?campaign_id=${activeCampaignId}`}
            download
            className="bg-transparent border border-[var(--color-line)] hover:border-[var(--color-line-hover)] rounded-lg px-3 py-1.5 text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--color-secondary)] hover:text-white transition-all no-underline"
          >
            PROV
          </a>
        </motion.div>
      </motion.div>

      {/* ETA */}
      {eta && (
        <motion.p
          variants={fadeInUp}
          initial="hidden"
          animate="visible"
          className="text-[13px] text-[var(--color-secondary)] mb-12"
        >
          About {formatDuration(eta.remaining_seconds)} remaining across {eta.remaining_steps ?? "?"} operations.
        </motion.p>
      )}

      {/* Plan tree */}
      <motion.section className="mb-16" initial="hidden" animate="visible" variants={stagger}>
        <motion.p
          variants={fadeInUp}
          className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-5"
        >
          Plan
        </motion.p>
        {byExperiment.size > 0 ? (
          [...byExperiment.entries()].map(([expId, expRecords]) => (
            <motion.div key={expId} variants={fadeInUp} className="mb-6">
              <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--color-tertiary)] mb-3">
                {expId}
              </p>
              <div className="flex flex-wrap gap-2">
                {expRecords.map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => onSelectRecord?.(r)}
                    className={cn(
                      "bg-transparent rounded-full px-3.5 py-1.5 text-[12px] font-medium transition-all border",
                      r.record_status === "completed" && "border-[var(--color-line-hover)] text-white opacity-100",
                      r.record_status === "running" && "border-[var(--color-status-green)] text-[var(--color-status-green)] status-dot--pulse",
                      r.record_status === "failed" && "border-[var(--color-status-red)] text-[var(--color-status-red)]",
                      r.record_status === "pending" && "border-[var(--color-line)] text-[var(--color-tertiary)] opacity-30",
                      !["completed", "running", "failed", "pending"].includes(r.record_status) && "border-[var(--color-line)] text-[var(--color-secondary)]",
                    )}
                  >
                    <span className="flex items-center gap-2">
                      <StatusIndicator
                        status={r.record_status}
                        pulse={r.record_status === "running"}
                      />
                      {r.operation}
                    </span>
                  </button>
                ))}
              </div>
            </motion.div>
          ))
        ) : (
          <p className="text-[var(--color-tertiary)]">Waiting for the first operations to be proposed.</p>
        )}
      </motion.section>

      {/* Live result */}
      {spotlight && (
        <motion.section className="mb-16" initial="hidden" animate="visible" variants={stagger}>
          <motion.p
            variants={fadeInUp}
            className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--color-secondary)] mb-5"
          >
            Latest result
          </motion.p>
          <motion.div
            variants={fadeInUp}
            className="relative rounded-2xl border border-[var(--color-line)] p-6 cursor-pointer hover:border-[var(--color-line-hover)] transition-all"
            onClick={() => latestCompleted && onSelectRecord?.(latestCompleted)}
          >
            <div className="glow-card absolute inset-0 rounded-2xl pointer-events-none" />
            <div className="relative">
              <h3
                className="text-[28px] font-normal text-white tracking-[-0.02em] mb-1"
                style={{ fontFamily: "var(--font-serif)" }}
              >
                {spotlight.title}
              </h3>
              <p className="text-[13px] text-[var(--color-secondary)] mb-5">{spotlight.subtitle}</p>
              {spotlight.points && (
                <div className="mb-5 rounded-xl overflow-hidden">
                  <MiniChart points={spotlight.points} height={160} />
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

      {/* Resources disclosure */}
      {usedResources.length > 0 && (
        <motion.section variants={fadeInUp} initial="hidden" animate="visible">
          <button
            type="button"
            onClick={() => setShowResources(!showResources)}
            className="bg-transparent border-none text-[13px] text-[var(--color-secondary)] hover:text-white transition-colors p-0 mb-4"
          >
            {showResources ? "Hide" : "Show"} resources ({usedResources.length})
            <span className="ml-2 text-[var(--color-tertiary)]">{showResources ? "↑" : "→"}</span>
          </button>
          {showResources && (
            <ResourceLanes resources={usedResources} records={campaignRecords} />
          )}
        </motion.section>
      )}
    </div>
  );
}

function LifecycleButton({ label, onClick, danger = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "bg-transparent border rounded-full px-4 py-1.5 text-[13px] font-medium transition-all",
        danger
          ? "border-[var(--color-status-red)]/30 text-[var(--color-status-red)] hover:border-[var(--color-status-red)]"
          : "border-[var(--color-line)] text-[var(--color-secondary)] hover:border-[var(--color-line-hover)] hover:text-white",
      )}
    >
      {label}
    </button>
  );
}

function ResourceLanes({ resources, records }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  const windowMs = 5 * 60 * 1000;
  const minTime = now - windowMs;
  const pct = (t) => Math.max(0, Math.min(100, ((t - minTime) / windowMs) * 100));

  const lanes = useMemo(() => {
    const map = new Map();
    for (const r of resources) map.set(r.name, { resource: r, records: [] });
    for (const r of records) {
      if (r.resource_name && map.has(r.resource_name)) {
        map.get(r.resource_name).records.push(r);
      }
    }
    return [...map.values()];
  }, [resources, records]);

  return (
    <div className="flex flex-col gap-3">
      {lanes.map(({ resource, records: laneRecords }) => (
        <div key={resource.name} className="border border-[var(--color-line)] rounded-xl p-3">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-[13px] font-medium text-white">{resource.name}</span>
            <span className="text-[11px] text-[var(--color-secondary)]">{resource.kind}</span>
            <StatusIndicator status={resource.state} pulse={resource.state === "busy"} />
          </div>
          <div className="relative h-8 rounded-lg border border-[var(--color-line)] overflow-hidden bg-[var(--color-surface)]">
            {laneRecords.slice(-30).map((r) => {
              const start = pct(new Date(r.created_at).getTime());
              const end = pct(new Date(r.finalised_at || Date.now()).getTime());
              const w = Math.max(end - start, 2);
              return (
                <div
                  key={r.id}
                  className="absolute top-1 bottom-1 rounded-full border border-[var(--color-line-hover)] flex items-center px-2 overflow-hidden"
                  style={{ left: `${start}%`, width: `${w}%` }}
                  title={`${r.operation} · ${r.record_status}`}
                >
                  <span className="text-[10px] text-[var(--color-secondary)] truncate">{r.operation}</span>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
