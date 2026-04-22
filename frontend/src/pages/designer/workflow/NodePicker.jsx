// Left rail: list of registered capabilities, draggable onto the canvas.
// Also hosts the "+ New capability" inline flow so a scientist can add a
// missing capability without leaving the workflow designer.

export default function NodePicker({ tools, onDragStart, onNewCapability, onClose }) {
  const sorted = [...(tools || [])].sort((a, b) => (a.capability || a.name).localeCompare(b.capability || b.name));

  return (
    <div
      style={{
        width: 240,
        borderRight: "1px solid var(--color-line)",
        background: "var(--color-panel)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      <div
        style={{
          padding: "10px 12px",
          borderBottom: "1px solid var(--color-line)",
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: 0.07,
          color: "var(--color-tertiary)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>Capabilities</span>
        {onClose ? (
          <button type="button" className="btn-ghost" onClick={onClose} style={{ fontSize: 11, padding: "2px 6px" }}>
            ×
          </button>
        ) : null}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
        {sorted.length === 0 ? (
          <div style={{ fontSize: 12, color: "var(--color-tertiary)", padding: 8 }}>
            No capabilities registered yet.
          </div>
        ) : (
          sorted.map((t) => {
            const name = t.capability || t.name;
            return (
              <div
                key={name}
                draggable
                onDragStart={(e) => onDragStart(e, t)}
                className="card"
                style={{
                  padding: 8,
                  marginBottom: 6,
                  cursor: "grab",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                }}
                title={t.description || name}
              >
                <div style={{ color: "var(--color-text)" }}>{name}</div>
                {t.resource_kind ? (
                  <div style={{ fontSize: 10, color: "var(--color-tertiary)", marginTop: 2 }}>
                    runs on: {t.resource_kind}
                  </div>
                ) : null}
              </div>
            );
          })
        )}
      </div>
      <div style={{ padding: 10, borderTop: "1px solid var(--color-line)" }}>
        <button
          type="button"
          onClick={onNewCapability}
          className="btn-secondary"
          style={{ width: "100%", fontSize: 12 }}
        >
          + New capability
        </button>
      </div>
    </div>
  );
}
