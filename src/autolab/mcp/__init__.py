"""The MCP gateway.

A single gateway server (`gateway.py`) reads the Tool registry and exposes
every declared capability over the Model Context Protocol. Not many MCP
servers per library — one gateway, many Tools. The Principal Agent talks
through this gateway; every tool call flows through a choke-point that
logs before it calls.
"""

from __future__ import annotations
