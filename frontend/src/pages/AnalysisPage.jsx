import { useEffect, useMemo, useState } from "react";

import { postJson } from "../lib/api";
import PageHeader from "../shell/PageHeader";

function numeric(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function fmt(value, digits = 4) {
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value ?? "-");
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (Math.abs(n) > 0 && Math.abs(n) < 0.001) return n.toExponential(2);
  return n.toPrecision(digits);
}

function chartBounds(values) {
  const finite = values.map(numeric).filter((v) => v != null);
  if (!finite.length) return [0, 1];
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  if (min === max) return [min - 1, max + 1];
  const pad = (max - min) * 0.08;
  return [min - pad, max + pad];
}

function axisValue(value, categories) {
  const n = numeric(value);
  if (n != null) return n;
  return categories.indexOf(String(value)) + 1;
}

function chartPoints(chart) {
  return (chart?.series || []).flatMap((series) =>
    (series.points || []).map((point) => ({ ...point, series: series.label, color: series.color })),
  );
}

function GenericChart({ chart }) {
  if (!chart?.series?.length) {
    return (
      <section className="analysis-panel analysis-panel--empty">
        <h3>{chart?.title || "No chart available"}</h3>
        <p>No matching ledger rows were found for this question.</p>
      </section>
    );
  }
  if (chart.type === "bar") return <BarChart chart={chart} />;
  return <PointChart chart={chart} />;
}

function PointChart({ chart }) {
  const width = 980;
  const height = 420;
  const pad = { left: 76, right: 32, top: 34, bottom: 62 };
  const allPoints = chartPoints(chart);
  const categories = [...new Set(allPoints.map((point) => String(point.x)).filter((x) => numeric(x) == null))];
  const xs = allPoints.map((point) => axisValue(point.x, categories));
  const ys = allPoints.map((point) => numeric(point.y)).filter((value) => value != null);
  const [minX, maxX] = chartBounds(xs);
  const [minY, maxY] = chartBounds(ys);
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const x = (value) => pad.left + ((axisValue(value, categories) - minX) / (maxX - minX || 1)) * plotW;
  const y = (value) => pad.top + (1 - (numeric(value) - minY) / (maxY - minY || 1)) * plotH;
  const bottom = height - pad.bottom;

  return (
    <section className="analysis-panel analysis-panel--chart">
      <ChartHeader chart={chart} />
      <ChartStats chart={chart} />
      <svg viewBox={`0 0 ${width} ${height}`} className="analysis-chart" role="img" aria-label={chart.title}>
        <defs>
          {(chart.series || []).map((series) => (
            <linearGradient key={series.label} id={`fill-${cleanId(series.label)}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={series.color} stopOpacity="0.24" />
              <stop offset="100%" stopColor={series.color} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const gy = pad.top + tick * plotH;
          const value = maxY - tick * (maxY - minY);
          return (
            <g key={tick}>
              <line x1={pad.left} x2={width - pad.right} y1={gy} y2={gy} className="analysis-grid" />
              <text x={pad.left - 12} y={gy + 4} textAnchor="end" className="analysis-axis">
                {fmt(value, 3)}
              </text>
            </g>
          );
        })}
        <line x1={pad.left} x2={width - pad.right} y1={bottom} y2={bottom} className="analysis-axis-line" />
        <line x1={pad.left} x2={pad.left} y1={pad.top} y2={bottom} className="analysis-axis-line" />
        <text x={width / 2} y={height - 18} textAnchor="middle" className="analysis-axis analysis-axis--label">
          {chart.x_label}
        </text>
        <text x={20} y={height / 2} textAnchor="middle" className="analysis-axis analysis-axis--label" transform={`rotate(-90 20 ${height / 2})`}>
          {chart.y_label}
        </text>
        {chart.series.map((series) => {
          const points = series.points || [];
          const path = points
            .map((point, index) => `${index === 0 ? "M" : "L"}${x(point.x).toFixed(2)} ${y(point.y).toFixed(2)}`)
            .join(" ");
          const area =
            chart.type === "line" && points.length > 1
              ? `${path} L${x(points[points.length - 1].x).toFixed(2)} ${bottom} L${x(points[0].x).toFixed(2)} ${bottom} Z`
              : "";
          return (
            <g key={series.label}>
              {area ? <path d={area} fill={`url(#fill-${cleanId(series.label)})`} /> : null}
              {chart.type === "line" && path ? <path d={path} fill="none" stroke={series.color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /> : null}
              {points.map((point, index) => (
                <circle
                  key={`${series.label}-${point.record_id || index}`}
                  cx={x(point.x)}
                  cy={y(point.y)}
                  r={chart.type === "scatter" ? 5.5 : 4.5}
                  fill="var(--color-canvas)"
                  stroke={series.color}
                  strokeWidth="2.4"
                >
                  <title>{point.tooltip || `${series.label}: ${point.x}, ${fmt(point.y, 6)}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
      </svg>
      <Legend series={chart.series} />
    </section>
  );
}

function BarChart({ chart }) {
  const points = chartPoints(chart);
  const max = Math.max(1, ...points.map((point) => numeric(point.y) || 0));
  return (
    <section className="analysis-panel analysis-panel--chart">
      <ChartHeader chart={chart} />
      <ChartStats chart={chart} />
      <div className="analysis-bars">
        {points.map((point, index) => (
          <div className="analysis-bar-row" key={`${point.x}-${index}`}>
            <span title={String(point.x)}>{String(point.x)}</span>
            <div className="analysis-bar-track">
              <div
                className="analysis-bar-fill"
                style={{ width: `${((numeric(point.y) || 0) / max) * 100}%`, background: point.color }}
              />
            </div>
            <strong>{fmt(point.y, 4)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function cleanId(value) {
  return String(value || "series").replace(/[^a-zA-Z0-9_-]/g, "-");
}

function ChartHeader({ chart }) {
  return (
    <div className="analysis-panel-header">
      <div>
        <span className="analysis-kicker">Generated visualization</span>
        <h3>{chart.title || "Ledger analysis"}</h3>
        <p>{chart.subtitle || `${chart.y_label || "value"} by ${chart.x_label || "x"}`}</p>
      </div>
    </div>
  );
}

function ChartStats({ chart }) {
  const points = chartPoints(chart).filter((point) => numeric(point.y) != null);
  const values = points.map((point) => numeric(point.y));
  const best = values.length ? Math.max(...values) : null;
  const xValues = points.map((point) => point.x);
  const xRange = xValues.length ? `${String(xValues[0])} to ${String(xValues[xValues.length - 1])}` : "-";
  const stats = [
    ["points", points.length],
    ["series", chart.series?.length || 0],
    ["max y", best == null ? "-" : fmt(best, 4)],
    ["x span", xRange],
  ];
  return (
    <div className="analysis-stats">
      {stats.map(([label, value]) => (
        <div className="analysis-stat" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

function Legend({ series }) {
  return (
    <div className="analysis-legend">
      {series.map((item) => (
        <span key={item.label}>
          <i style={{ background: item.color }} /> {item.label}
        </span>
      ))}
    </div>
  );
}

function AssistantPanel({ messages, prompt, setPrompt, onRequest, busy, hasRecords }) {
  const suggestions = [
    "Compare campaign objectives over trial number",
    "Show best-so-far convergence for each campaign",
    "Plot outputs.sx_nm by trial, grouped by campaign",
    "Which campaigns have failed records?",
  ];
  return (
    <section className="analysis-chat">
      <div className="analysis-chat-title">
        <span>Ask your data</span>
        <small>One question, one chart</small>
      </div>
      <div className="analysis-chat-log" aria-live="polite">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`analysis-message analysis-message--${message.role}`}>
            {message.content}
          </div>
        ))}
      </div>
      <div className="analysis-suggestions">
        {suggestions.map((item) => (
          <button type="button" key={item} onClick={() => onRequest(item)} disabled={busy || !hasRecords}>
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
        <textarea
          aria-label="Ask for a ledger visualization"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Ask about the ledger: compare campaigns, plot an output, find failures, or summarize trends..."
          rows={4}
          disabled={!hasRecords}
        />
        <button type="submit" className="btn-primary" disabled={busy || !prompt.trim() || !hasRecords}>
          {busy ? "Thinking" : "Ask"}
        </button>
      </form>
    </section>
  );
}

export default function AnalysisPage({ campaigns = [], records = [] }) {
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [autoRan, setAutoRan] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Ask a question about the ledger. I will turn it into a clear chart and a short readout.",
    },
  ]);

  const hasRecords = records.length > 0;
  const modelLabel = useMemo(() => {
    if (!result) return "";
    return `${result.model}${result.offline ? " offline" : ""}`;
  }, [result]);

  const runAnalysis = async (text) => {
    const query = (text || "").trim();
    if (!query || busy || !hasRecords) return;
    setBusy(true);
    setError("");
    setMessages((previous) => [...previous, { role: "user", content: query }].slice(-10));
    try {
      const body = { prompt: query, campaign_ids: campaigns.map(c => c.campaign_id || c.id).filter(Boolean) };
        const next = await postJson("/analysis/query", body);
      setResult(next);
      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: next.answer || "Generated a visualization from the ledger." },
      ].slice(-10));
      setPrompt("");
    } catch (err) {
      setError(String(err));
      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: `Analysis failed: ${String(err)}` },
      ].slice(-10));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (hasRecords && !autoRan) {
      setAutoRan(true);
      runAnalysis("Compare campaign objectives over trial number");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasRecords, autoRan]);

  return (
    <>
      <PageHeader
        title="Data Chat"
        description="Discuss the ledger and generate a clean visualization from the live data."
      />

      <div className="analysis-summary">
        <div>
          <span>Records</span>
          <strong>{records.length}</strong>
        </div>
        <div>
          <span>Campaigns</span>
          <strong>{campaigns.length}</strong>
        </div>
        <div>
          <span>Mode</span>
          <strong>single chat</strong>
        </div>
      </div>

      <div className="analysis-layout">
        <div className="analysis-stage">
          {result?.chart ? (
            <GenericChart chart={result.chart} />
          ) : (
            <section className="analysis-panel analysis-panel--empty">
              <h3>{busy ? "Generating visualization" : hasRecords ? "Ask a question to begin" : "No ledger records yet"}</h3>
              <p>
                {busy
                  ? "Reading the ledger fields and choosing the simplest useful chart."
                  : hasRecords
                    ? "Try a comparison, a trend, a best-so-far curve, or a failure summary."
                    : "Run a campaign first, then come back here to discuss the data."}
              </p>
            </section>
          )}
          {result?.spec ? (
            <details className="analysis-spec">
              <summary>{modelLabel || "Chart recipe"}</summary>
              <code>{JSON.stringify(result.spec)}</code>
            </details>
          ) : null}
          {error ? <p className="analysis-error">{error}</p> : null}
        </div>
        <AssistantPanel
          messages={messages}
          prompt={prompt}
          setPrompt={setPrompt}
          onRequest={runAnalysis}
          busy={busy}
          hasRecords={hasRecords}
        />
      </div>
    </>
  );
}

