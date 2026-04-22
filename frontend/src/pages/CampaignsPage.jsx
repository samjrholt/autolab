import PageHeader from "../shell/PageHeader";
import EmptyState from "../shell/EmptyState";
import { formatTime } from "../lib/api";

function statusChip(status) {
  const variant = {
    running: "var(--color-status-green)",
    queued: "var(--color-status-amber)",
    paused: "var(--color-status-blue)",
    completed: "var(--color-secondary)",
    failed: "var(--color-status-red)",
    cancelled: "var(--color-secondary)",
  }[status] || "var(--color-secondary)";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: variant, fontSize: 12 }}>
      <span className="status-dot" style={{ background: variant }} /> {status || "—"}
    </span>
  );
}

function campaignGoal(c) {
  return c.objective?.description || c.name || c.campaign_id || "—";
}

function opsProgress(c) {
  const done = c.ops_completed ?? c.completed_ops ?? c.completed ?? 0;
  const total = c.ops_total ?? c.total_ops ?? c.budget ?? null;
  if (total == null) return `${done}`;
  return `${done}/${total}`;
}

export default function CampaignsPage({ campaigns, onSelectCampaign, onNewCampaign }) {
  const hasCampaigns = campaigns && campaigns.length > 0;

  return (
    <>
      <PageHeader
        title="Campaigns"
        description="Goal-driven runs. Each campaign is a chain of Operations against your Resources, planned and adapted by the Planner."
        primaryAction={
          <button type="button" onClick={onNewCampaign} className="btn-primary">
            + New campaign
          </button>
        }
      />

      {!hasCampaigns ? (
        <EmptyState
          title="No campaigns yet"
          description="Start your first campaign to watch resources fill, records stream into the ledger, and the Planner react to results in real time."
          action={
            <button type="button" onClick={onNewCampaign} className="btn-primary">
              Start your first campaign
            </button>
          }
        />
      ) : (
        <div className="panel" style={{ overflow: "hidden" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: "45%" }}>Goal</th>
                <th>Status</th>
                <th>Ops</th>
                <th>Started</th>
                <th>Planner</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <tr key={c.campaign_id} onClick={() => onSelectCampaign?.(c)}>
                  <td style={{ color: "var(--color-text)" }}>{campaignGoal(c)}</td>
                  <td>{statusChip(c.status)}</td>
                  <td style={{ color: "var(--color-muted)", fontVariantNumeric: "tabular-nums" }}>
                    {opsProgress(c)}
                  </td>
                  <td style={{ color: "var(--color-secondary)", fontSize: 12 }}>
                    {c.started_at ? formatTime(c.started_at) : "—"}
                  </td>
                  <td style={{ color: "var(--color-muted)", fontSize: 12 }}>{c.planner || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
