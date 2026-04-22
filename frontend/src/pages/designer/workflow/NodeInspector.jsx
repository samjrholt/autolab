import { useMemo } from "react";

// Right rail: edit one step's properties. All changes flow back through
// onChange(patch) which the canvas merges into node.data.
//
// The Inspector is deliberately simple — scalar inputs are edited as
// text, complex values (dicts, arrays) as JSON. Real scientists can
// always drop into the Describe tab if they want a Claude-drafted step.

function KVRow({ k, v, onEdit, onRemove }) {
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 4 }}>
      <code style={{ fontSize: 11, color: "var(--color-muted)", minWidth: 110 }}>{k}</code>
      <input
        value={typeof v === "string" ? v : JSON.stringify(v)}
        onChange={(e) => {
          const raw = e.target.value;
          // Try JSON-parse first so numbers/bools round-trip cleanly.
          let parsed = raw;
          try {
            parsed = JSON.parse(raw);
          } catch {
            parsed = raw;
          }
          onEdit(parsed);
        }}
        style={{
          flex: 1,
          background: "var(--color-canvas)",
          border: "1px solid var(--color-line)",
          color: "var(--color-text)",
          borderRadius: 4,
          padding: "3px 6px",
          fontSize: 11,
          fontFamily: "var(--font-mono)",
        }}
      />
      <button type="button" className="btn-ghost" onClick={onRemove} style={{ fontSize: 11, padding: "1px 6px" }}>
        ×
      </button>
    </div>
  );
}

export default function NodeInspector({ node, capability, edgesIntoNode, onChange, onDelete }) {
  if (!node) {
    return (
      <div
        style={{
          width: 300,
          borderLeft: "1px solid var(--color-line)",
          background: "var(--color-panel)",
          padding: 14,
          fontSize: 12,
          color: "var(--color-tertiary)",
          height: "100%",
        }}
      >
        Select a step to edit its properties.
      </div>
    );
  }

  const d = node.data || {};
  const declaredInputs = useMemo(() => Object.keys(capability?.inputs || {}), [capability]);

  const patch = (next) => onChange({ ...d, ...next });
  const patchInputs = (next) => patch({ inputs: { ...(d.inputs || {}), ...next } });

  return (
    <div
      style={{
        width: 300,
        borderLeft: "1px solid var(--color-line)",
        background: "var(--color-panel)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflowY: "auto",
      }}
    >
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--color-line)" }}>
        <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)" }}>
          Step
        </div>
        <input
          value={d.step_id}
          onChange={(e) => patch({ step_id: e.target.value })}
          style={{
            width: "100%",
            marginTop: 4,
            background: "var(--color-canvas)",
            border: "1px solid var(--color-line-strong)",
            color: "var(--color-text)",
            borderRadius: 4,
            padding: "4px 8px",
            fontSize: 13,
            fontFamily: "var(--font-mono)",
          }}
        />
        <div style={{ fontSize: 11, color: "var(--color-secondary)", marginTop: 6 }}>
          capability: <code>{d.operation}</code>
        </div>
      </div>

      <div style={{ padding: 12, borderBottom: "1px solid var(--color-line)" }}>
        <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 6 }}>
          Inputs
        </div>
        {declaredInputs.length === 0 && Object.keys(d.inputs || {}).length === 0 ? (
          <div style={{ fontSize: 11, color: "var(--color-tertiary)" }}>
            Capability declares no inputs.
          </div>
        ) : (
          <>
            {declaredInputs.map((key) => {
              const mapping = d.input_mappings?.[key];
              if (mapping) {
                return (
                  <div key={key} style={{ marginBottom: 4, fontSize: 11 }}>
                    <code style={{ color: "var(--color-muted)", minWidth: 110, display: "inline-block" }}>{key}</code>
                    <span style={{ color: "var(--color-accent)", fontFamily: "var(--font-mono)" }}>
                      ← {mapping}
                    </span>
                  </div>
                );
              }
              const v = d.inputs?.[key];
              return (
                <KVRow
                  key={key}
                  k={key}
                  v={v ?? ""}
                  onEdit={(nv) => patchInputs({ [key]: nv })}
                  onRemove={() => {
                    const next = { ...(d.inputs || {}) };
                    delete next[key];
                    patch({ inputs: next });
                  }}
                />
              );
            })}
          </>
        )}
      </div>

      {edgesIntoNode && edgesIntoNode.length > 0 ? (
        <div style={{ padding: 12, borderBottom: "1px solid var(--color-line)" }}>
          <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.07, color: "var(--color-tertiary)", marginBottom: 6 }}>
            Upstream
          </div>
          {edgesIntoNode.map((e) => (
            <div key={e.id} style={{ fontSize: 11, color: "var(--color-secondary)", fontFamily: "var(--font-mono)" }}>
              {e.source}
              {e.sourceHandle ? `.${e.sourceHandle}` : ""}
              {e.targetHandle ? ` → ${e.targetHandle}` : " (ordering)"}
            </div>
          ))}
        </div>
      ) : null}

      <div style={{ padding: 12, borderTop: "1px solid var(--color-line)", marginTop: "auto" }}>
        <button type="button" className="btn-ghost" onClick={onDelete} style={{ fontSize: 12, color: "var(--color-status-red)" }}>
          Remove step
        </button>
      </div>
    </div>
  );
}
