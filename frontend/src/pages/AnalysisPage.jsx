import { useMemo, useState } from "react";

import PageHeader from "../shell/PageHeader";

const PALETTE = ["#c96342", "#6b8fd6", "#7fd67f", "#e8b062", "#d66666", "#b58bd9"];

function numeric(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function fmt(value, digits = 4) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return n.toPrecision(digits);
}

function campaignLabel(campaign) {
  return campaign?.name || campaign?.description || campaign?.campaign_id || "campaign";
}

function trialRows(campaign, records) {
  const key = campaign?.objective?.key;
  if (!key) return [];
  const rows = (records || [])
    .filter((record) => record.campaign_id === campaign.campaign_id)
    .filter((record) => record.record_status === "completed")
    .filter((record) => numeric(record.outputs?.[key]) != null)
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

  return rows.map((record, index) => ({
    record,
    trial: Number.isInteger(record.decision?.trial_number)
      ? Number(record.decision.trial_number) + 1
      : index + 1,
    ordinal: index + 1,
    value: numeric(record.outputs?.[key]),
    sx: numeric(record.outputs?.sx_nm ?? record.inputs?.sx_nm),
    sy: numeric(record.outputs?.sy_nm ?? record.inputs?.sy_nm),
    duration_s: numeric(record.duration_ms) == null ? null : numeric(record.duration_ms) / 1000,
  }));
}

function bestSoFar(rows, direction) {
  let best = null;
  return rows.map((row) => {
    if (
      best == null ||
      (direction === "minimise" ? row.value < best : row.value > best)
    ) {
      best = row.value;
    }
    return { ...row, value: best };
  });
}

function makeSeries(campaigns, records, mode) {
  return campaigns.map((campaign, index) => {
    const rows = trialRows(campaign, records);
    const direction = campaign.objective?.direction || "maximise";
    return {
      id: campaign.campaign_id,
      label: campaignLabel(campaign),
      color: PALETTE[index % PALETTE.length],
      rows: mode === "best" ? bestSoFar(rows, direction) : rows,
      rawRows: rows,
      direction,
      objective: campaign.objective?.key,
    };
  });
}

function bounds(values) {
  const finite = values.filter((v) => Number.isFinite(v));
  if (!finite.length) return [0, 1];
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  if (min === max) return [min - 1, max + 1];
  const pad = (max - min) * 0.08;
  return [min - pad, max + pad];
}

function ComparisonLineChart({ series, title, yLabel }) {
  const width = 900;
  const height = 340;
  const pad = { left: 64, right: 24, top: 24, bottom: 46 };
  const all = series.flatMap((s) => s.rows.map((row) => row.value));
  const allX = series.flatMap((s) => s.rows.map((row) => row.ordinal));
  const [minY, maxY] = bounds(all);
  const [minX, maxX] = bounds(allX);
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const x = (value) => pad.left + ((value - minX) / (maxX - minX || 1)) * plotW;
  const y = (value) => pad.top + (1 - (value - minY) / (maxY - minY || 1)) * plotH;

  return (
    <section className="analysis-panel">
      <div className="analysis-panel-header">
        <div>
          <h3>{title}</h3>
          <p>{yLabel}</p>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="analysis-chart" role="img" aria-label={title}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const gy = pad.top + t * plotH;
          const value = maxY - t * (maxY - minY);
          return (
            <g key={t}>
              <line x1={pad.left} x2={width - pad.right} y1={gy} y2={gy} className="analysis-grid" />
              <text x={pad.left - 10} y={gy + 4} textAnchor="end" className="analysis-axis">
                {fmt(value, 3)}
              </text>
            </g>
          );
        })}
        <line x1={pad.left} x2={width - pad.right} y1={height - pad.bottom} y2={height - pad.bottom} className="analysis-axis-line" />
        <line x1={pad.left} x2={pad.left} y1={pad.top} y2={height - pad.bottom} className="analysis-axis-line" />
        <text x={width / 2} y={height - 12} textAnchor="middle" className="analysis-axis">Trial number</text>
        {series.map((s) => {
          const path = s.rows
            .map((row, i) => `${i === 0 ? "M" : "L"}${x(row.ordinal).toFixed(2)} ${y(row.value).toFixed(2)}`)
            .join(" ");
          return (
            <g key={s.id}>
              <path d={path} fill="none" stroke={s.color} strokeWidth="2.6" />
              {s.rows.map((row) => (
                <circle key={row.record.id} cx={x(row.ordinal)} cy={y(row.value)} r="4" fill={s.color}>
                  <title>{`${s.label}: trial ${row.ordinal}, ${fmt(row.value, 6)}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
      <Legend series={series} />
    </section>
  );
}

function ShapeScatter({ series }) {
  const width = 900;
  const height = 330;
  const pad = { left: 56, right: 28, top: 22, bottom: 46 };
  const points = series.flatMap((s) => s.rawRows.filter((row) => row.sx != null && row.sy != null).map((row) => ({ ...row, series: s })));
  const [minX, maxX] = bounds(points.map((p) => p.sx));
  const [minY, maxY] = bounds(points.map((p) => p.sy));
  const [minV, maxV] = bounds(points.map((p) => p.value));
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const x = (value) => pad.left + ((value - minX) / (maxX - minX || 1)) * plotW;
  const y = (value) => pad.top + (1 - (value - minY) / (maxY - minY || 1)) * plotH;
  const radius = (value) => 4 + ((value - minV) / (maxV - minV || 1)) * 7;

  return (
    <section className="analysis-panel">
      <div className="analysis-panel-header">
        <div>
          <h3>Shape search map</h3>
          <p>Each point is one completed FOM trial. Larger points have higher objective values.</p>
        </div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="analysis-chart" role="img" aria-label="Shape search map">
        <line x1={pad.left} x2={width - pad.right} y1={height - pad.bottom} y2={height - pad.bottom} className="analysis-axis-line" />
        <line x1={pad.left} x2={pad.left} y1={pad.top} y2={height - pad.bottom} className="analysis-axis-line" />
        <text x={width / 2} y={height - 12} textAnchor="middle" className="analysis-axis">sx_nm</text>
        <text x={15} y={height / 2} transform={`rotate(-90 15 ${height / 2})`} textAnchor="middle" className="analysis-axis">sy_nm</text>
        {points.map((point) => (
          <circle
            key={point.record.id}
            cx={x(point.sx)}
            cy={y(point.sy)}
            r={radius(point.value)}
            fill={point.series.color}
            fillOpacity="0.72"
            stroke="rgba(255,255,255,0.5)"
            strokeWidth="1"
          >
            <title>{`${point.series.label}: sx=${fmt(point.sx)}, sy=${fmt(point.sy)}, objective=${fmt(point.value, 6)}`}</title>
          </circle>
        ))}
      </svg>
      <Legend series={series} />
    </section>
  );
}

function DurationBars({ series }) {
  const rows = series.map((s) => {
    const durations = s.rawRows.map((row) => row.duration_s).filter((v) => v != null);
    const avg = durations.reduce((a, b) => a + b, 0) / (durations.length || 1);
    return { ...s, avg, count: durations.length };
  });
  const max = Math.max(1, ...rows.map((row) => row.avg));
  return (
    <section className="analysis-panel">
      <div className="analysis-panel-header">
        <div>
          <h3>Average FOM duration</h3>
          <p>Mean completed objective-step runtime by campaign.</p>
        </div>
      </div>
      <div className="analysis-bars">
        {rows.map((row) => (
          <div className="analysis-bar-row" key={row.id}>
            <span>{row.label}</span>
            <div className="analysis-bar-track">
              <div className="analysis-bar-fill" style={{ width: `${(row.avg / max) * 100}%`, background: row.color }} />
            </div>
            <strong>{fmt(row.avg, 3)} s</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function Legend({ series }) {
  return (
    <div className="analysis-legend">
      {series.map((s) => (
        <span key={s.id}>
          <i style={{ background: s.color }} /> {s.label}
        </span>
      ))}
    </div>
  );
}

function MetricStrip({ series }) {
  return (
    <div className="analysis-metrics">
      {series.map((s) => {
        const best = [...s.rawRows].sort((a, b) =>
          s.direction === "minimise" ? a.value - b.value : b.value - a.value,
        )[0];
        return (
          <div className="analysis-metric" key={s.id}>
            <span>{s.label}</span>
            <strong>{fmt(best?.value, 6)}</strong>
            <small>{best ? `trial ${best.ordinal} · sx ${fmt(best.sx)} · sy ${fmt(best.sy)}` : "no objective records"}</small>
          </div>
        );
      })}
    </div>
  );
}

function AssistantPanel({ onRequest, messages, prompt, setPrompt }) {
  const suggestions = [
    "Compare objective by trial number",
    "Show best so far",
    "Map sx and sy against Hmax",
    "Compare runtimes",
  ];
  return (
    <section className="analysis-chat">
      <div className="analysis-chat-log" aria-live="polite">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`analysis-message analysis-message--${message.role}`}>
            {message.content}
          </div>
        ))}
      </div>
      <div className="analysis-suggestions">
        {suggestions.map((item) => (
          <button type="button" key={item} onClick={() => onRequest(item)}>
            {item}
          </button>
        ))}
      </div>
      <form
        className="analysis-chat-form"
        onSubmit={(event) => {
          event.preventDefault();
          onRequest(prompt);
        }}
      >
        <input
          aria-label="Ask for an analysis visualization"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Ask to compare objective, best-so-far, geometry, or runtime..."
        />
        <button type="submit" className="btn-primary">Ask</button>
      </form>
    </section>
  );
}

export default function AnalysisPage({ campaigns, records }) {
  const [mode, setMode] = useState("objective");
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "I can compare campaign objectives over trial number, show best-so-far, map shape parameters, or summarize runtimes from the ledger.",
    },
  ]);

  const comparableCampaigns = useMemo(
    () => (campaigns || []).filter((campaign) => campaign.objective?.key),
    [campaigns],
  );
  const selectedCampaigns = useMemo(
    () => comparableCampaigns.filter((campaign) => trialRows(campaign, records).length > 0),
    [comparableCampaigns, records],
  );
  const series = useMemo(() => makeSeries(selectedCampaigns, records, mode), [selectedCampaigns, records, mode]);

  const handleRequest = (text) => {
    const query = (text || "").trim();
    if (!query) return;
    const lower = query.toLowerCase();
    let next = "objective";
    let response = "Showing objective value as a function of trial number for the completed campaign records.";
    if (lower.includes("best") || lower.includes("converge")) {
      next = "best";
      response = "Showing best-so-far by trial. This is the clearest convergence view for Optuna versus Claude.";
    } else if (lower.includes("shape") || lower.includes("geometry") || lower.includes("sx") || lower.includes("sy") || lower.includes("map")) {
      next = "scatter";
      response = "Showing the shape search map. sx_nm and sy_nm are plotted directly, with larger points marking stronger objective values.";
    } else if (lower.includes("runtime") || lower.includes("duration") || lower.includes("time") || lower.includes("faster")) {
      next = "duration";
      response = "Showing average completed FOM-step runtime for each campaign.";
    }
    setMode(next);
    setMessages((previous) => [
      ...previous,
      { role: "user", content: query },
      { role: "assistant", content: response },
    ].slice(-8));
    setPrompt("");
  };

  return (
    <>
      <PageHeader
        title="Analysis"
        description="Compare campaign performance directly from the ledger."
      />

      <MetricStrip series={series} />

      <div className="analysis-layout">
        <div>
          <div className="analysis-tabs" role="tablist" aria-label="Analysis views">
            {[
              ["objective", "Objective"],
              ["best", "Best so far"],
              ["scatter", "Shape map"],
              ["duration", "Runtime"],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={mode === id}
                className={mode === id ? "is-active" : ""}
                onClick={() => setMode(id)}
              >
                {label}
              </button>
            ))}
          </div>
          {mode === "objective" ? (
            <ComparisonLineChart series={series} title="Objective by trial" yLabel={series[0]?.objective || "objective"} />
          ) : null}
          {mode === "best" ? (
            <ComparisonLineChart series={series} title="Best objective so far" yLabel={series[0]?.objective || "objective"} />
          ) : null}
          {mode === "scatter" ? <ShapeScatter series={series} /> : null}
          {mode === "duration" ? <DurationBars series={series} /> : null}
        </div>
        <AssistantPanel
          messages={messages}
          prompt={prompt}
          setPrompt={setPrompt}
          onRequest={handleRequest}
        />
      </div>
    </>
  );
}
