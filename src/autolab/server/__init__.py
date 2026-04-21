"""FastAPI + WebSocket surface.

The Lab is a long-running service. Resources, Tools, Workflows, and Campaigns
are registered against the running Lab via REST. Events — Record lifecycle,
plan-tree diffs, scheduler activity — stream over a single WebSocket to any
subscriber (the Console, the CLI, external monitors).

Entry point: `autolab.server.app:app` (FastAPI application factory).
"""

from __future__ import annotations
