import { useMemo } from "react";

// Renders a grid of "physics cards" — one per live-renderable artefact
// (structure, loop, PXRD, etc). Operations declare an artefact kind;
// the registry here maps kind → React renderer. For now we render PNG
// artefacts inline and text artefacts as a preview.

function PngArtefact({ url, label }) {
  return (
    <div className="card" style={{ padding: 10 }}>
      <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.06, color: "var(--color-tertiary)", marginBottom: 6 }}>
        {label}
      </div>
      <div
        style={{
          width: "100%",
          aspectRatio: "1.4 / 1",
          background: "#0a0a0a",
          borderRadius: 4,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
          border: "1px solid var(--color-line)",
        }}
      >
        {url ? (
          <img
            src={url}
            alt={label}
            style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
          />
        ) : (
          <span style={{ color: "var(--color-tertiary)", fontSize: 11 }}>no artefact yet</span>
        )}
      </div>
    </div>
  );
}

function ScalarCard({ label, value, unit }) {
  return (
    <div className="card" style={{ padding: 12 }}>
      <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.06, color: "var(--color-tertiary)", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 22, color: "var(--color-text)", fontFamily: "var(--font-mono)" }}>
        {value ?? "—"}
        {unit ? <span style={{ fontSize: 11, color: "var(--color-secondary)", marginLeft: 4 }}>{unit}</span> : null}
      </div>
    </div>
  );
}

export default function PhysicsCards({ records }) {
  const cards = useMemo(() => {
    const latestByKind = new Map();
    for (const r of records || []) {
      if (!r.outputs) continue;
      for (const [key, val] of Object.entries(r.outputs)) {
        // Numeric scalar
        if (typeof val === "number") {
          if (!latestByKind.has(key)) latestByKind.set(key, { kind: "scalar", label: key, value: val });
        }
        // Artefact path or URL hint
        if (typeof val === "string" && val.match(/\.(png|jpg|jpeg|svg)$/i)) {
          latestByKind.set(key, { kind: "png", label: key, url: val });
        }
      }
    }
    return Array.from(latestByKind.values()).slice(0, 6);
  }, [records]);

  if (cards.length === 0) {
    return (
      <div style={{ padding: 18, textAlign: "center", color: "var(--color-tertiary)", fontSize: 12 }}>
        Physics panels appear here as Operations produce artefacts.
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
      {cards.map((c, i) =>
        c.kind === "scalar" ? (
          <ScalarCard key={i} label={c.label} value={c.value?.toFixed?.(3) ?? c.value} unit={c.unit} />
        ) : (
          <PngArtefact key={i} label={c.label} url={c.url} />
        ),
      )}
    </div>
  );
}
