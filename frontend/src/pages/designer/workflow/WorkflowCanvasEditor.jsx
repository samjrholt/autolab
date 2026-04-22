import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import CapabilityNode from "./CapabilityNode";
import NodePicker from "./NodePicker";
import NodeInspector from "./NodeInspector";
import { workflowToGraph, graphToWorkflow, validateGraph } from "./convert";
import { autoLayout } from "./layout";

const NODE_TYPES = { capability: CapabilityNode };

const uniqueStepId = (existing, base) => {
  const slug = (base || "step")
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "") || "step";
  if (!existing.has(slug)) return slug;
  let i = 2;
  while (existing.has(`${slug}_${i}`)) i++;
  return `${slug}_${i}`;
};

function enrichNodesWithSchema(nodes, toolsByName) {
  return nodes.map((n) => {
    const decl = toolsByName.get(n.data.operation);
    return {
      ...n,
      data: {
        ...n.data,
        schemaInputs: decl ? Object.keys(decl.inputs || {}) : [],
        schemaOutputs: decl ? Object.keys(decl.outputs || {}) : [],
      },
    };
  });
}

function Inner({ initial, tools, onSave, onCancel, onRequestNewCapability, saving, pickerOpen, onTogglePicker }) {
  const [name, setName] = useState(initial?.name || "");
  const [description, setDescription] = useState(initial?.description || "");
  const toolsByName = useMemo(() => {
    const m = new Map();
    for (const t of tools || []) m.set(t.capability || t.name, t);
    return m;
  }, [tools]);

  const initialGraph = useMemo(() => {
    const g = workflowToGraph(initial || { steps: [] });
    // Auto-layout if positions weren't persisted.
    const missingLayout = g.nodes.some((n) => n.position.x === 0 && n.position.y === 0);
    const positioned = missingLayout ? autoLayout(g.nodes, g.edges) : g.nodes;
    return { nodes: enrichNodesWithSchema(positioned, toolsByName), edges: g.edges };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial]);

  const [nodes, setNodes] = useState(initialGraph.nodes);
  const [edges, setEdges] = useState(initialGraph.edges);
  const [selectedId, setSelectedId] = useState(null);
  const [errors, setErrors] = useState([]);
  const wrapperRef = useRef(null);

  // Re-enrich nodes whenever the tool catalogue changes (so handles match the
  // latest schema after a user adds a new capability from the rail).
  useEffect(() => {
    setNodes((ns) => enrichNodesWithSchema(ns, toolsByName));
  }, [toolsByName]);

  const onNodesChange = useCallback((changes) => setNodes((ns) => applyNodeChanges(changes, ns)), []);
  const onEdgesChange = useCallback((changes) => setEdges((es) => applyEdgeChanges(changes, es)), []);
  const onConnect = useCallback(
    (params) => {
      const kind = params.targetHandle ? "mapping" : "depends_on";
      const id =
        kind === "mapping"
          ? `${params.source}->${params.target}:${params.targetHandle}`
          : `${params.source}->${params.target}:order`;
      setEdges((es) => addEdge({ ...params, id, data: { kind, localKey: params.targetHandle, outputKey: params.sourceHandle } }, es));
    },
    [],
  );

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const raw = event.dataTransfer.getData("application/autolab-capability");
      if (!raw) return;
      const tool = JSON.parse(raw);
      const capName = tool.capability || tool.name;
      const existing = new Set(nodes.map((n) => n.id));
      const stepId = uniqueStepId(existing, capName);
      const bounds = wrapperRef.current.getBoundingClientRect();
      const position = { x: event.clientX - bounds.left - 100, y: event.clientY - bounds.top - 40 };
      const newNode = {
        id: stepId,
        type: "capability",
        position,
        data: {
          step_id: stepId,
          operation: capName,
          inputs: {},
          input_mappings: {},
          schemaInputs: Object.keys(tool.inputs || {}),
          schemaOutputs: Object.keys(tool.outputs || {}),
        },
      };
      setNodes((ns) => ns.concat(newNode));
      setSelectedId(stepId);
    },
    [nodes],
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const handleDragStart = useCallback((event, tool) => {
    event.dataTransfer.setData("application/autolab-capability", JSON.stringify(tool));
    event.dataTransfer.effectAllowed = "move";
  }, []);

  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedId) || null, [nodes, selectedId]);
  const edgesIntoSelected = useMemo(() => edges.filter((e) => e.target === selectedId), [edges, selectedId]);
  const selectedCapability = selectedNode ? toolsByName.get(selectedNode.data.operation) : null;

  const patchSelected = useCallback(
    (nextData) => {
      setNodes((ns) =>
        ns.map((n) =>
          n.id !== selectedId
            ? n
            : { ...n, id: nextData.step_id || n.id, data: { ...nextData } },
        ),
      );
      if (nextData.step_id && nextData.step_id !== selectedId) {
        // Keep edges wired when the step_id changes.
        setEdges((es) =>
          es.map((e) => ({
            ...e,
            source: e.source === selectedId ? nextData.step_id : e.source,
            target: e.target === selectedId ? nextData.step_id : e.target,
          })),
        );
        setSelectedId(nextData.step_id);
      }
    },
    [selectedId],
  );

  const deleteSelected = useCallback(() => {
    setNodes((ns) => ns.filter((n) => n.id !== selectedId));
    setEdges((es) => es.filter((e) => e.source !== selectedId && e.target !== selectedId));
    setSelectedId(null);
  }, [selectedId]);

  const relayout = useCallback(() => {
    setNodes((ns) => autoLayout(ns, edges));
  }, [edges]);

  const save = useCallback(async () => {
    if (!name.trim()) {
      setErrors(["Workflow needs a name."]);
      return;
    }
    const validation = validateGraph({ nodes, edges, capabilitiesByName: toolsByName });
    if (validation.length) {
      setErrors(validation);
      return;
    }
    setErrors([]);
    const body = graphToWorkflow({ name: name.trim(), description: description.trim(), nodes, edges, existing: initial });
    await onSave(body);
  }, [name, description, nodes, edges, toolsByName, initial, onSave]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 120px)" }}>
      <div
        style={{
          display: "flex",
          gap: 10,
          padding: "10px 12px",
          borderBottom: "1px solid var(--color-line)",
          background: "var(--color-panel)",
          alignItems: "center",
        }}
      >
        <input
          placeholder="workflow_name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{
            flex: "0 0 260px",
            background: "var(--color-canvas)",
            border: "1px solid var(--color-line-strong)",
            color: "var(--color-text)",
            borderRadius: 4,
            padding: "5px 8px",
            fontFamily: "var(--font-mono)",
            fontSize: 13,
          }}
        />
        <input
          placeholder="One-line description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          style={{
            flex: 1,
            background: "var(--color-canvas)",
            border: "1px solid var(--color-line-strong)",
            color: "var(--color-text)",
            borderRadius: 4,
            padding: "5px 8px",
            fontSize: 13,
          }}
        />
        <button type="button" className="btn-ghost" onClick={relayout} style={{ fontSize: 12 }}>
          Auto-layout
        </button>
        {!pickerOpen ? (
          <button type="button" className="btn-ghost" onClick={onTogglePicker} style={{ fontSize: 12 }}>
            Show palette
          </button>
        ) : null}
        <button type="button" className="btn-ghost" onClick={onCancel} style={{ fontSize: 12 }}>
          Cancel
        </button>
        <button type="button" className="btn-primary" onClick={save} disabled={saving} style={{ fontSize: 12 }}>
          {saving ? "Saving…" : "Save workflow"}
        </button>
      </div>

      {errors.length ? (
        <div
          style={{
            background: "rgba(214,102,102,0.08)",
            borderBottom: "1px solid rgba(214,102,102,0.3)",
            color: "var(--color-status-red)",
            fontSize: 12,
            padding: "6px 12px",
          }}
        >
          {errors.map((e, i) => (
            <div key={i}>• {e}</div>
          ))}
        </div>
      ) : null}

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {pickerOpen ? (
          <NodePicker
            tools={tools}
            onDragStart={handleDragStart}
            onNewCapability={onRequestNewCapability}
            onClose={onTogglePicker}
          />
        ) : null}
        <div
          ref={wrapperRef}
          style={{ flex: 1, background: "var(--color-canvas)", position: "relative" }}
          onDrop={onDrop}
          onDragOver={onDragOver}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onSelectionChange={(sel) => setSelectedId(sel.nodes?.[0]?.id || null)}
            nodeTypes={NODE_TYPES}
            fitView
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{ style: { stroke: "var(--color-accent)", strokeWidth: 1.5 } }}
          >
            <Background color="#262626" gap={16} />
            <Controls
              style={{ background: "var(--color-panel)", border: "1px solid var(--color-line)" }}
              showInteractive={false}
            />
            <MiniMap
              style={{ background: "var(--color-panel)" }}
              maskColor="rgba(15,15,15,0.8)"
              nodeColor="var(--color-accent-soft)"
              nodeStrokeColor="var(--color-accent)"
            />
          </ReactFlow>
          {nodes.length === 0 ? (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                pointerEvents: "none",
              }}
            >
              <div style={{ color: "var(--color-tertiary)", fontSize: 13, textAlign: "center" }}>
                Drag a capability from the palette to add a step.
                <div style={{ fontSize: 11, marginTop: 4 }}>Missing a capability? Use <em>+ New capability</em> in the palette.</div>
              </div>
            </div>
          ) : null}
        </div>
        <NodeInspector
          node={selectedNode}
          capability={selectedCapability}
          edgesIntoNode={edgesIntoSelected}
          onChange={patchSelected}
          onDelete={deleteSelected}
        />
      </div>
    </div>
  );
}

export default function WorkflowCanvasEditor(props) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  );
}
