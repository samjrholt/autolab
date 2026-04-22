export default function PageHeader({ title, description, primaryAction, children }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 20 }}>
      <div style={{ flex: 1 }}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 500, color: "var(--color-text)" }}>{title}</h1>
        {description ? (
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--color-muted)", maxWidth: 640 }}>
            {description}
          </p>
        ) : null}
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {children}
        {primaryAction}
      </div>
    </div>
  );
}
