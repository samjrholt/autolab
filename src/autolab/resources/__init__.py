"""Resources — named instances with typed capabilities.

A Resource is a single, identified piece of capacity: `arc-furnace-1`,
`tube-furnace-A`, `slurm-partition-gpu`. Each instance has a `kind` and a
`capabilities` dict. Operations declare their required `kind` plus optional
capability requirements; the ResourceManager atomically acquires a free
compatible instance.

The user-level mental model is counts-per-kind ("2 × arc furnace"); the
code sees individual instances.
"""

from __future__ import annotations
