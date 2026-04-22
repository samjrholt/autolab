import { Handle, Position } from "@xyflow/react";

// One node on the canvas = one WorkflowStep.
// Props:
//   data: { step_id, operation, inputs, input_mappings, acceptance, status? }
//   selected: boolean
//
// The handles are driven by the capability's declared input/output schema
// (passed in via data.schemaInputs / data.schemaOutputs — populated at render
// time in the canvas). If the schema is unknown we fall back to a single
// anonymous input and output handle.

function HandleRow({ keys, type, position }) {
  if (!keys || keys.length === 0) {
    return <Handle type={type} position={position} id={null} style={{ background: "#888" }} />;
  }
  const total = keys.length;
  return keys.map((k, i) => {
    const top = `${((i + 1) * 100) / (total + 1)}%`;
    return (
      <Handle
        key={`${type}-${k}`}
        id={k}
        type={type}
        position={position}
        style={{ top, background: "var(--color-accent)", width: 8, height: 8 }}
      >
        <span
          style={{
            position: "absolute",
            [position === Position.Left ? "left" : "right"]: 12,
            top: -6,
            fontSize: 9,
            color: "var(--color-tertiary)",
            fontFamily: "var(--font-mono)",
            whiteSpace: "nowrap",
            pointerEvents: "none",
          }}
        >
          {k}
        </span>
      </Handle>
    );
  });
}

export default function CapabilityNode({ data, selected }) {
  const status = data.status || "draft";
  const bordersByStatus = {
    draft: "var(--color-line-strong)",
    running: "var(--color-status-amber)",
    completed: "var(--color-status-green)",
    failed: "var(--color-status-red)",
    queued: "var(--color-status-blue)",
  };
  const border = selected ? "var(--color-accent)" : bordersByStatus[status] || "var(--color-line-strong)";
  const inputsCount = Object.keys(data.inputs || {}).length + Object.keys(data.input_mappings || {}).length;
  const hasAcceptance = !!data.acceptance;

  return (
    <div
      style={{
        background: "var(--color-card)",
        border: `1px solid ${border}`,
        borderRadius: 6,
        padding: "8px 12px",
        minWidth: 180,
        boxShadow: selected ? "0 0 0 2px rgba(201,99,66,0.25)" : "none",
        fontFamily: "var(--font-sans)",
      }}
    >
      <HandleRow keys={data.schemaInputs} type="target" position={Position.Left} />
      <div
        style={{
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: 0.07,
          color: "var(--color-tertiary)",
          fontFamily: "var(--font-mono)",
        }}
      >
        {data.step_id || "step"}
      </div>
      <div style={{ fontSize: 13, color: "var(--color-text)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
        {data.operation || <span style={{ color: "var(--color-status-red)" }}>— no capability —</span>}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 6, fontSize: 10, color: "var(--color-tertiary)" }}>
        {inputsCount > 0 ? <span>{inputsCount} input{inputsCount === 1 ? "" : "s"}</span> : null}
        {hasAcceptance ? <span style={{ color: "var(--color-accent)" }}>gate</span> : null}
        {data.produces_sample ? <span>→ sample</span> : null}
      </div>
      <HandleRow keys={data.schemaOutputs} type="source" position={Position.Right} />
    </div>
  );
}
