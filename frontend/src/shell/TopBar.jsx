export default function TopBar({ crumbs = [], connected, escalationCount, onOpenEscalations }) {
  return (
    <header
      style={{
        height: 52,
        borderBottom: "1px solid var(--color-line-strong)",
        display: "flex",
        alignItems: "center",
        padding: "0 20px",
        gap: 16,
        background: "var(--color-canvas)",
        flexShrink: 0,
      }}
    >
      <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
        {crumbs.map((c, i) => (
          <span key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {i > 0 ? <span style={{ color: "var(--color-tertiary)" }}>/</span> : null}
            <span style={{ color: i === crumbs.length - 1 ? "var(--color-text)" : "var(--color-muted)" }}>
              {c}
            </span>
          </span>
        ))}
      </div>

      {escalationCount > 0 ? (
        <button
          type="button"
          onClick={onOpenEscalations}
          style={{
            background: "rgba(232, 176, 98, 0.12)",
            border: "1px solid rgba(232, 176, 98, 0.3)",
            color: "var(--color-status-amber)",
            fontSize: 12,
            padding: "3px 9px",
            borderRadius: 4,
          }}
        >
          {escalationCount} pending
        </button>
      ) : null}

      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--color-muted)" }}>
        <span className={`status-dot ${connected ? "status-dot--green status-dot--pulse" : "status-dot--red"}`} />
        {connected ? "live" : "disconnected"}
      </div>
    </header>
  );
}
