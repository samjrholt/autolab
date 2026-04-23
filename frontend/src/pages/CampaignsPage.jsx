import PageHeader from "../shell/PageHeader";
import EmptyState from "../shell/EmptyState";
import { formatTime } from "../lib/api";

function statusChip(status) {
  const variant = {
    running: "var(--color-status-green)",
    queued: "var(--color-status-amber)",
    paused: "var(--color-status-blue)",
    completed: "var(--color-secondary)",
    stopped: "var(--color-status-amber)",
    failed: "var(--color-status-red)",
    cancelled: "var(--color-secondary)",
  }[status] || "var(--color-secondary)";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: variant, fontSize: 12 }}>
      <span className="status-dot" style={{ background: variant }} /> {status || "-"}
    </span>
  );
}

function campaignGoal(c) {
  return c.description || c.name || c.objective?.key || c.campaign_id || "-";
}

function recordProgress(c) {
  const done = c.completed_records ?? c.ops_completed ?? c.completed_ops ?? 0;
  const total = c.total_records ?? c.ops_total ?? c.total_ops ?? null;
  if (total == null) return `${done}`;
  return `${done}/${total}`;
}

function trialProgress(c) {
  if (c.budget == null) return c.steps_run == null ? "-" : `${c.steps_run}`;
  return `${c.steps_run ?? 0}/${c.budget}`;
}

function formatBest(c) {
  if (c.best_value == null) return "-";
  const n = Number(c.best_value);
  return Number.isFinite(n) ? n.toPrecision(5) : String(c.best_value);
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
                <th style={{ width: "34%" }}>Goal</th>
                <th>Status</th>
                <th>Trials</th>
                <th>Records</th>
                <th>Best</th>
                <th>Started</th>
                <th>Planner</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <tr
                  key={c.campaign_id}
                  tabIndex={0}
                  role="button"
                  aria-label={`Open campaign ${campaignGoal(c)}`}
                  onClick={() => onSelectCampaign?.(c)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectCampaign?.(c);
                    }
                  }}
                >
                  <td style={{ color: "var(--color-text)" }}>{campaignGoal(c)}</td>
                  <td>{statusChip(c.status)}</td>
                  <td style={{ color: "var(--color-muted)", fontVariantNumeric: "tabular-nums" }}>
                    {trialProgress(c)}
                  </td>
                  <td style={{ color: "var(--color-muted)", fontVariantNumeric: "tabular-nums" }}>
                    {recordProgress(c)}
                  </td>
                  <td style={{ color: "var(--color-muted)", fontVariantNumeric: "tabular-nums" }}>
                    {formatBest(c)}
                  </td>
                  <td style={{ color: "var(--color-secondary)", fontSize: 12 }}>
                    {c.started_at ? formatTime(c.started_at) : "-"}
                  </td>
                  <td style={{ color: "var(--color-muted)", fontSize: 12 }}>{c.planner || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
