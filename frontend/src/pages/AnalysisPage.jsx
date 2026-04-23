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

function GenericChart({ chart }) {
  if (!chart?.series?.length) {
    return (
      <section className="analysis-panel">
        <h3>{chart?.title || "No chart available"}</h3>
        <p>No matching ledger rows were found for this analysis.</p>
      </section>
    );
  }
  if (chart.type === "bar") return <BarChart chart={chart} />;
  return <PointChart chart={chart} />;
}

function PointChart({ chart }) {
  const width = 900;
  const height = 340;
  const pad = { left: 64, right: 24, top: 24, bottom: 46 };
  const allPoints = chart.series.flatMap((series) => series.points || []);
  const categories = [...new Set(allPoints.map((point) => String(point.x)).filter((x) => numeric(x) == null))];
  const xs = allPoints.map((point) => axisValue(point.x, categories));
  const ys = allPoints.map((point) => numeric(point.y)).filter((value) => value != null);
  const [minX, maxX] = chartBounds(xs);
  const [minY, maxY] = chartBounds(ys);
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const x = (value) => pad.left + ((axisValue(value, categories) - minX) / (maxX - minX || 1)) * plotW;
  const y = (value) => pad.top + (1 - (numeric(value) - minY) / (maxY - minY || 1)) * plotH;

  return (
    <section className="analysis-panel">
      <ChartHeader chart={chart} />
      <svg viewBox={`0 0 ${width} ${height}`} className="analysis-chart" role="img" aria-label={chart.title}>
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const gy = pad.top + tick * plotH;
          const value = maxY - tick * (maxY - minY);
          return (
            <g key={tick}>
              <line x1={pad.left} x2={width - pad.right} y1={gy} y2={gy} className="analysis-grid" />
              <text x={pad.left - 10} y={gy + 4} textAnchor="end" className="analysis-axis">
                {fmt(value, 3)}
              </text>
            </g>
          );
        })}
        <line x1={pad.left} x2={width - pad.right} y1={height - pad.bottom} y2={height - pad.bottom} className="analysis-axis-line" />
        <line x1={pad.left} x2={pad.left} y1={pad.top} y2={height - pad.bottom} className="analysis-axis-line" />
        <text x={width / 2} y={height - 12} textAnchor="middle" className="analysis-axis">{chart.x_label}</text>
        {chart.series.map((series) => {
          const points = series.points || [];
          const path = points
            .map((point, index) => `${index === 0 ? "M" : "L"}${x(point.x).toFixed(2)} ${y(point.y).toFixed(2)}`)
            .join(" ");
          return (
            <g key={series.label}>
              {chart.type === "line" && path ? <path d={path} fill="none" stroke={series.color} strokeWidth="2.6" /> : null}
              {points.map((point, index) => (
                <circle
                  key={`${series.label}-${point.record_id || index}`}
                  cx={x(point.x)}
                  cy={y(point.y)}
                  r={chart.type === "scatter" ? 5.5 : 4}
                  fill={series.color}
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
  const points = chart.series.flatMap((series) =>
    (series.points || []).map((point) => ({ ...point, color: series.color, series: series.label })),
  );
  const max = Math.max(1, ...points.map((point) => numeric(point.y) || 0));
  return (
    <section className="analysis-panel">
      <ChartHeader chart={chart} />
      <div className="analysis-bars">
        {points.map((point, index) => (
          <div className="analysis-bar-row" key={`${point.x}-${index}`}>
            <span>{String(point.x)}</span>
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

function ChartHeader({ chart }) {
  return (
    <div className="analysis-panel-header">
      <div>
        <h3>{chart.title || "Generated analysis"}</h3>
        <p>{chart.subtitle || `${chart.y_label || "value"} by ${chart.x_label || "x"}`}</p>
      </div>
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

function AssistantPanel({ messages, prompt, setPrompt, onRequest, busy }) {
  const suggestions = [
    "Compare campaign objectives over trial number",
    "Show the best-so-far convergence for each campaign",
    "Which campaign was fastest on average?",
    "Find any relationship between inputs and objective values",
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
          <button type="button" key={item} onClick={() => onRequest(item)} disabled={busy}>
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
          aria-label="Ask Claude for an analysis visualization"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Ask Claude to compare, correlate, aggregate, or plot any ledger field..."
        />
        <button type="submit" className="btn-primary" disabled={busy || !prompt.trim()}>
          {busy ? "Thinking" : "Ask"}
        </button>
      </form>
    </section>
  );
}

export default function AnalysisPage() {
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Ask Claude for any ledger visualization. Claude will choose the fields and chart type from the live campaign data.",
    },
  ]);

  const modelLabel = useMemo(() => {
    if (!result) return "";
    return `${result.model}${result.offline ? " offline" : ""}`;
  }, [result]);

  const runAnalysis = async (text) => {
    const query = (text || "").trim();
    if (!query || busy) return;
    setBusy(true);
    setError("");
    setMessages((previous) => [...previous, { role: "user", content: query }].slice(-8));
    try {
      const next = await postJson("/analysis/query", { prompt: query });
      setResult(next);
      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: next.answer || "Generated a visualization from the ledger." },
      ].slice(-8));
      setPrompt("");
    } catch (err) {
      setError(String(err));
      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: `Analysis failed: ${String(err)}` },
      ].slice(-8));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    runAnalysis("Compare campaign objectives over trial number");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <PageHeader
        title="Analysis"
        description="Claude-generated visualizations over live ledger records."
      />

      <div className="analysis-layout">
        <div>
          {result?.chart ? (
            <GenericChart chart={result.chart} />
          ) : (
            <section className="analysis-panel">
              <h3>{busy ? "Generating analysis" : "No analysis yet"}</h3>
              <p>{busy ? "Claude is reading the available ledger fields." : "Ask Claude for a chart to begin."}</p>
            </section>
          )}
          {result?.spec ? (
            <div className="analysis-spec">
              <span>{modelLabel}</span>
              <code>{JSON.stringify(result.spec)}</code>
            </div>
          ) : null}
          {error ? <p className="analysis-error">{error}</p> : null}
        </div>
        <AssistantPanel
          messages={messages}
          prompt={prompt}
          setPrompt={setPrompt}
          onRequest={runAnalysis}
          busy={busy}
        />
      </div>
    </>
  );
}
