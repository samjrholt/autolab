import { useMemo, useState } from "react";
import { postJson, formatTime } from "../lib/api";
import ResourceLanes from "./campaign/ResourceLanes";
import PlanTree from "./campaign/PlanTree";
import PhysicsCards from "./campaign/PhysicsCards";
import ReasoningRail from "./campaign/ReasoningRail";
import LedgerPage from "./LedgerPage";

function statusChip(status) {
  const color = {
    running: "var(--color-status-green)",
    queued: "var(--color-status-amber)",
    paused: "var(--color-status-blue)",
    completed: "var(--color-secondary)",
    stopped: "var(--color-status-amber)",
    failed: "var(--color-status-red)",
    cancelled: "var(--color-secondary)",
  }[status] || "var(--color-secondary)";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color, fontSize: 12 }}>
      <span className="status-dot" style={{ background: color }} /> {status || "—"}
    </span>
  );
}

function PlanTab({ campaign, records, resources, events, railCollapsed, onToggleRail }) {
  const campaignRecords = useMemo(
    () => records.filter((r) => r.campaign_id === campaign.campaign_id),
    [records, campaign],
  );

  return (
    <div
      className="campaign-plan-layout"
      style={{
        display: "grid",
        gridTemplateColumns: railCollapsed ? "1fr 40px" : "minmax(0, 2fr) minmax(260px, 1fr)",
        gap: 14,
        minHeight: 520,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
        <div
          className="campaign-visual-grid"
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 3fr) minmax(240px, 2fr)",
            gap: 12,
          }}
        >
          <div className="panel" style={{ padding: 14, minWidth: 0 }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-muted)", marginBottom: 10 }}>
              Resource lanes
            </div>
            <ResourceLanes resources={resources} records={campaignRecords} />
          </div>

          <div className="panel" style={{ padding: 14, minWidth: 0 }}>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-muted)", marginBottom: 10 }}>
              Plan tree
            </div>
            <PlanTree campaign={campaign} records={campaignRecords} />
          </div>
        </div>

        <div className="panel" style={{ padding: 14, minWidth: 0 }}>
          <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-muted)", marginBottom: 10 }}>
            Physics
          </div>
          <PhysicsCards records={campaignRecords} />
        </div>
      </div>

      <ReasoningRail
        events={events}
        campaignId={campaign.campaign_id}
        records={campaignRecords}
        collapsed={railCollapsed}
        onToggle={onToggleRail}
      />
    </div>
  );
}

function ReportTab({ campaign }) {
  const reportUrl = `/campaigns/${campaign.campaign_id}/report`;
  return (
    <div className="panel" style={{ padding: 0, overflow: "hidden", minHeight: 600 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          borderBottom: "1px solid var(--color-line-strong)",
        }}
      >
        <span style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-muted)" }}>
          Campaign report
        </span>
        <a
          href={reportUrl}
          target="_blank"
          rel="noreferrer"
          className="btn-secondary"
          style={{ fontSize: 11 }}
        >
          Open full page ↗
        </a>
      </div>
      <iframe
        src={reportUrl}
        title="Campaign report"
        style={{
          width: "100%",
          minHeight: 560,
          border: "none",
          display: "block",
          background: "#f8f9fa",
        }}
      />
    </div>
  );
}

function ConfigTab({ campaign, refresh }) {
  const [busy, setBusy] = useState(false);

  const doAction = async (verb) => {
    setBusy(true);
    try {
      await postJson(`/campaigns/${campaign.campaign_id}/${verb}`, {});
      await refresh?.();
    } finally {
      setBusy(false);
    }
  };

  const criteria = campaign.objective?.acceptance_criteria || campaign.acceptance_criteria;

  return (
    <div className="panel" style={{ padding: 20, maxWidth: 720 }}>
      <h3 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 500 }}>Configuration</h3>

      <div style={{ fontSize: 13, color: "var(--color-muted)", display: "grid", gap: 10, marginBottom: 18 }}>
        <div>
          <span style={{ color: "var(--color-secondary)" }}>Campaign ID:</span>{" "}
          <code>{campaign.campaign_id}</code>
        </div>
        <div>
          <span style={{ color: "var(--color-secondary)" }}>Planner:</span> {campaign.planner || "—"}
        </div>
        <div>
          <span style={{ color: "var(--color-secondary)" }}>Acceptance criteria:</span>{" "}
          <pre style={{ marginTop: 6, background: "var(--color-card)", border: "1px solid var(--color-line-strong)", borderRadius: 4, padding: 10 }}>
            {criteria ? JSON.stringify(criteria, null, 2) : "(none)"}
          </pre>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {campaign.status === "queued" ? (
          <button type="button" disabled={busy} onClick={() => doAction("start")} className="btn-secondary" style={{ color: "var(--color-status-green)", borderColor: "rgba(92, 164, 115, 0.3)" }}>
            Start campaign
          </button>
        ) : null}
        {campaign.status === "running" ? (
          <button type="button" disabled={busy} onClick={() => doAction("pause")} className="btn-secondary">
            Pause
          </button>
        ) : null}
        {campaign.status === "paused" ? (
          <button type="button" disabled={busy} onClick={() => doAction("resume")} className="btn-secondary">
            Resume
          </button>
        ) : null}
        {["running", "paused", "queued"].includes(campaign.status) ? (
          <button type="button" disabled={busy} onClick={() => doAction("cancel")} className="btn-secondary" style={{ color: "var(--color-status-red)", borderColor: "rgba(214, 102, 102, 0.3)" }}>
            Stop campaign
          </button>
        ) : null}
      </div>
    </div>
  );
}

export default function CampaignDetailPage({ campaign, records, resources, events, refresh, onBack, onOpenIntervention }) {
  const [tab, setTab] = useState("plan");
  const [railCollapsed, setRailCollapsed] = useState(false);

  return (
    <>
      <div style={{ marginBottom: 12 }}>
        <button type="button" className="btn-ghost" onClick={onBack} style={{ fontSize: 12, marginBottom: 6 }}>
          ← Campaigns
        </button>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: 18, fontWeight: 500 }}>
              {campaign.description || campaign.name || campaign.objective?.key || campaign.campaign_id}
            </h1>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4, fontSize: 12, color: "var(--color-secondary)" }}>
              {statusChip(campaign.status)}
              {campaign.started_at ? <span>· started {formatTime(campaign.started_at)}</span> : null}
              {campaign.planner ? <span>· {campaign.planner}</span> : null}
              {campaign.workflow ? <span>· workflow {campaign.workflow}</span> : null}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" onClick={onOpenIntervention} className="btn-secondary">
              Intervene
            </button>
          </div>
        </div>
      </div>

      <div className="tabs" style={{ marginBottom: 16 }}>
        {[
          ["plan", "Plan"],
          ["ledger", "Ledger"],
          ["report", "Report"],
          ["config", "Config"],
        ].map(([id, label]) => (
          <button key={id} type="button" onClick={() => setTab(id)} className={`tabs-item${tab === id ? " is-active" : ""}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "plan" ? (
        <PlanTab
          campaign={campaign}
          records={records}
          resources={resources}
          events={events}
          railCollapsed={railCollapsed}
          onToggleRail={() => setRailCollapsed((v) => !v)}
        />
      ) : null}

      {tab === "ledger" ? (
        <LedgerPage records={records} campaignIdFilter={campaign.campaign_id} />
      ) : null}

      {tab === "report" ? <ReportTab campaign={campaign} /> : null}

      {tab === "config" ? <ConfigTab campaign={campaign} refresh={refresh} /> : null}
    </>
  );
}
