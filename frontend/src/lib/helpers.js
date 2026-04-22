/** Pure helpers shared across components. */

export function cn(...values) {
  return values.filter(Boolean).join(" ");
}

export function sortByCreatedDesc(records) {
  return [...records].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}

export function statusColor(status) {
  switch (status) {
    case "running":
      return "green";
    case "completed":
      return "green";
    case "failed":
      return "red";
    case "soft_fail":
    case "paused":
    case "escalated":
      return "amber";
    default:
      return "idle";
  }
}

export function statusLabel(status) {
  const map = {
    running: "Running",
    completed: "Completed",
    pending: "Pending",
    failed: "Failed",
    soft_fail: "Soft fail",
    paused: "Paused",
    queued: "Queued",
    escalated: "Escalated",
  };
  return map[status] || status;
}

export function buildSvgPath(points, width, height, padding = 16) {
  if (!points?.length) return "";
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;
  return points
    .map((p, i) => {
      const x = padding + ((p[0] - xMin) / xSpan) * (width - padding * 2);
      const y = height - padding - ((p[1] - yMin) / ySpan) * (height - padding * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

/** Extract a renderable spotlight from a record's outputs. */
export function extractSpotlight(record, formatNumber) {
  if (!record || !formatNumber) return null;
  const outputs = record.outputs || {};

  if (outputs.loop?.H && outputs.loop?.M) {
    return {
      title: "Hysteresis loop",
      subtitle: record.operation,
      points: outputs.loop.H.map((h, i) => [h, outputs.loop.M[i] ?? 0]),
      metrics: [
        { label: "Sensitivity", value: formatNumber(outputs.sensitivity, 3), unit: "1/T" },
        { label: "Hc", value: formatNumber(outputs.Hc, 2), unit: "A/m" },
        { label: "Mr / Ms", value: formatNumber(outputs.Mr_over_Ms, 3) },
      ],
    };
  }
  if (outputs.H_A_per_m && outputs.M_A_per_m) {
    return {
      title: "Micromagnetic hysteresis",
      subtitle: record.operation,
      points: outputs.H_A_per_m.map((h, i) => [h, outputs.M_A_per_m[i] ?? 0]),
      metrics: [
        { label: "Hc", value: formatNumber(outputs.Hc_A_per_m, 2), unit: "A/m" },
        { label: "Mr", value: formatNumber(outputs.Mr_A_per_m, 2), unit: "A/m" },
        { label: "Sweep", value: formatNumber(outputs.H_sweep_max_A_per_m, 2), unit: "A/m" },
      ],
    };
  }
  const scalarMetrics = Object.entries(outputs)
    .filter(([, v]) => typeof v === "number")
    .slice(0, 4)
    .map(([k, v]) => ({ label: k, value: formatNumber(v, 3) }));
  if (!scalarMetrics.length) return null;
  return {
    title: record.operation,
    subtitle: record.module || "Autolab record",
    points: null,
    metrics: scalarMetrics,
  };
}
