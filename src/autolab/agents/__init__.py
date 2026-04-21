"""Two-tier Managed Agents.

The Principal Agent decomposes a Campaign goal into hypotheses and spawns a
Campaign Subagent in isolated context to pursue one. Built on Claude Managed
Agents; Skills (domain knowledge, Anthropic SKILL.md format) live alongside
in `src/autolab/skills/`.

For the hackathon demo: exactly one Campaign Subagent, visibly context-isolated
from the Principal. More looks like theatre.
"""

from __future__ import annotations
