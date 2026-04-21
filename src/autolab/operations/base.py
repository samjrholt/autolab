"""Operation — the atomic unit of work.

Every experimental or computational step is an Operation. Operations:

- declare the Resource `kind` they need (and optional capability `requires`)
- declare whether they `produce_sample` (mint a new Sample) and/or are
  `destructive` (consume the upstream Sample)
- implement async `run(inputs, context) → OperationResult`
- never write Records — the orchestrator does that around them

This file defines the abstract base. Concrete Operations live in
adapters under `src/autolab/tools/adapters/` (framework-bundled
adapters) or in user/example packages outside the framework.
"""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from autolab.models import OperationResult, Resource, Sample


class OperationContext(BaseModel):
    """Side-channel info handed to an Operation by the Orchestrator.

    Operations can ignore this entirely — it's there so an adapter that
    needs the Resource instance, the working Sample, or the Record id can
    pull them without us widening the `run` signature later.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    record_id: str
    operation: str
    resource: Resource | None = None
    upstream_samples: list[Sample] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Operation(ABC):
    """Abstract base — subclass to wire a real or simulated capability."""

    #: Capability name as a scientist would call it (e.g. `superellipse_hysteresis`).
    capability: str = ""

    #: Resource kind this Operation needs. `None` means no Resource gate.
    resource_kind: str | None = None

    #: Capability requirements on the matched Resource instance.
    requires: dict[str, Any] = {}

    #: True if this Operation mints a new Sample.
    produces_sample: bool = False

    #: True if this Operation consumes / destroys the upstream Sample.
    destructive: bool = False

    #: Free-form module version string stamped into every Record.
    module: str = "anonymous.v0"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Defensive copy so subclasses don't mutate the parent's dict.
        cls.requires = dict(cls.requires)

    @abstractmethod
    async def run(
        self,
        inputs: dict[str, Any],
        context: OperationContext,
    ) -> OperationResult:
        """Execute one atomic step. Must be deterministic given the same inputs."""

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @classmethod
    async def call(cls, inputs: dict[str, Any], context: OperationContext) -> OperationResult:
        instance = cls()
        result = instance.run(inputs, context)
        if inspect.isawaitable(result):
            return await result
        return result  # type: ignore[return-value]


__all__ = ["Operation", "OperationContext"]
