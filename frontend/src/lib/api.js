export async function getJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}


export async function postJson(path, body = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.error || `${response.status} ${response.statusText}`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return payload;
}


export function formatTime(iso) {
  if (!iso) {
    return "--:--:--";
  }
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}


export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(seconds)) {
    return "--";
  }
  if (seconds < 60) {
    return `${seconds.toFixed(0)}s`;
  }
  if (seconds < 3600) {
    return `${(seconds / 60).toFixed(1)}m`;
  }
  return `${(seconds / 3600).toFixed(1)}h`;
}


export function formatNumber(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) {
    return "--";
  }
  const numeric = Number(value);
  const absolute = Math.abs(numeric);
  if (absolute !== 0 && (absolute < 1e-2 || absolute >= 1e4)) {
    return numeric.toExponential(digits);
  }
  return numeric.toFixed(digits);
}


export function wsUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}${path}`;
}