// Round-trip between a WorkflowTemplate (as the server stores it) and the
// React Flow (nodes, edges) representation used by the canvas.
//
// Step shape on the server side (src/autolab/models.py):
//   { step_id, operation, depends_on: [step_id], inputs: {}, input_mappings: { localKey: "upstreamId.outputKey" }, acceptance, description }
//
// Edges come from two sources:
//   1. input_mappings: "upstream.outputKey" -> step.inputs[localKey]   (data edge, carries mapping)
//   2. depends_on entries NOT already covered by input_mappings        (pure ordering edge)

export function workflowToGraph(workflow) {
  const steps = Array.isArray(workflow?.steps) ? workflow.steps : [];
  const layout = workflow?.metadata?.layout || {};

  const nodes = steps.map((step, idx) => {
    const id = step.step_id || `s${idx + 1}`;
    const pos = layout[id] || null;
    return {
      id,
      type: "capability",
      position: pos ? { x: pos.x, y: pos.y } : { x: 0, y: 0 },
      data: {
        step_id: id,
        operation: step.operation || "",
        description: step.description || "",
        inputs: step.inputs || {},
        input_mappings: step.input_mappings || {},
        acceptance: step.acceptance || null,
        produces_sample: !!step.produces_sample,
        destructive: !!step.destructive,
      },
    };
  });

  const edges = [];
  const seenPairs = new Set();
  for (const step of steps) {
    const to = step.step_id;
    // Data edges from input_mappings.
    for (const [localKey, ref] of Object.entries(step.input_mappings || {})) {
      const [srcId, ...rest] = String(ref).split(".");
      const outputKey = rest.join(".") || "";
      if (!srcId) continue;
      const key = `${srcId}->${to}:${localKey}`;
      seenPairs.add(`${srcId}->${to}`);
      edges.push({
        id: key,
        source: srcId,
        target: to,
        sourceHandle: outputKey || null,
        targetHandle: localKey,
        data: { kind: "mapping", localKey, outputKey },
        animated: false,
      });
    }
    // Dependency-only edges.
    for (const dep of step.depends_on || []) {
      if (seenPairs.has(`${dep}->${to}`)) continue;
      const key = `${dep}->${to}:order`;
      seenPairs.add(`${dep}->${to}`);
      edges.push({
        id: key,
        source: dep,
        target: to,
        data: { kind: "depends_on" },
        animated: false,
      });
    }
  }

  return { nodes, edges };
}

export function graphToWorkflow({ name, description, nodes, edges, existing }) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const steps = nodes.map((node) => {
    const d = node.data || {};
    const inputMappings = {};
    const dependsOn = new Set();

    for (const edge of edges.filter((e) => e.target === node.id)) {
      dependsOn.add(edge.source);
      if (edge.data?.kind === "mapping" && edge.targetHandle) {
        const outKey = edge.sourceHandle || edge.data.outputKey || "";
        inputMappings[edge.targetHandle] = outKey ? `${edge.source}.${outKey}` : `${edge.source}`;
      }
    }

    return {
      step_id: d.step_id || node.id,
      operation: d.operation || "",
      depends_on: Array.from(dependsOn),
      inputs: d.inputs || {},
      input_mappings: inputMappings,
      produces_sample: !!d.produces_sample,
      destructive: !!d.destructive,
      ...(d.acceptance ? { acceptance: d.acceptance } : {}),
    };
  });

  const layout = {};
  for (const node of nodes) {
    layout[node.id] = { x: Math.round(node.position.x), y: Math.round(node.position.y) };
  }

  const metadata = { ...(existing?.metadata || {}), layout };

  return {
    ...(existing || {}),
    name,
    description: description || null,
    steps,
    metadata,
  };
}

export function validateGraph({ nodes, edges, capabilitiesByName }) {
  const errors = [];
  const ids = new Set();
  for (const n of nodes) {
    const d = n.data || {};
    if (!d.step_id || !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(d.step_id)) {
      errors.push(`Step id "${d.step_id}" must be a simple identifier (letters, digits, underscore; not starting with a digit).`);
    }
    if (ids.has(d.step_id)) errors.push(`Duplicate step id "${d.step_id}".`);
    ids.add(d.step_id);
    if (!d.operation) errors.push(`Step "${d.step_id}" has no capability selected.`);
    else if (capabilitiesByName && !capabilitiesByName.has(d.operation)) {
      errors.push(`Step "${d.step_id}" uses capability "${d.operation}" which is not registered.`);
    }
  }

  // Cycle detection (Kahn's algorithm).
  const incoming = new Map(nodes.map((n) => [n.id, 0]));
  const adj = new Map(nodes.map((n) => [n.id, []]));
  for (const e of edges) {
    if (!incoming.has(e.target) || !adj.has(e.source)) continue;
    incoming.set(e.target, incoming.get(e.target) + 1);
    adj.get(e.source).push(e.target);
  }
  const queue = [...incoming.entries()].filter(([, v]) => v === 0).map(([k]) => k);
  let visited = 0;
  while (queue.length) {
    const n = queue.shift();
    visited++;
    for (const m of adj.get(n) || []) {
      incoming.set(m, incoming.get(m) - 1);
      if (incoming.get(m) === 0) queue.push(m);
    }
  }
  if (visited !== nodes.length) errors.push("Workflow has a cycle — remove a back-edge.");

  return errors;
}
