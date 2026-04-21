"""ResourceManager — atomic acquire/release with state-machine awareness.

Each registered :class:`~autolab.models.Resource` has a runtime
:class:`~autolab.models.ResourceState` tracked inside the manager.
The scheduler and the Gantt visualisation read this state to show what
each instrument is doing and when it will be available next.

State transitions
-----------------

::

    register ──► IDLE ──► BUSY ──► IDLE   (normal acquire/release cycle)
                         │
                         ▼
                    [COOLING | WARMING]    (set by calling code after release,
                         │                 e.g. after a high-temp sintering run)
                         ▼
                        IDLE              (auto-cleared when available_after passes)

    Any state ──► ERROR | MAINTENANCE     (set explicitly; cleared by human operator)

``set_state(name, state, available_after=...)``
    Transition a resource to a new state. ``available_after`` is used for
    states like ``COOLING`` or ``WARMING`` where the resource will recover
    automatically — the manager respects this timestamp during acquisition.

``acquire()`` context manager
    Atomically finds a free, compatible, ``IDLE`` resource and sets it
    to ``BUSY``. Blocks until one is available (or timeout expires). On
    exit, resets to ``IDLE`` unless the calling code changed the state
    inside the context (e.g., to ``COOLING`` after a furnace run).

``status()``
    Returns per-resource state dicts suitable for the Gantt / dashboard,
    including ``available_after_iso`` for scheduled cooling/warming windows.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from autolab.models import Resource, ResourceState

_OPERATORS: dict[str, Any] = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


def matches_capabilities(resource: Resource, requirements: Mapping[str, Any] | None) -> bool:
    """Return True if this Resource satisfies the requirements dict.

    Two forms per requirement key:

    - ``{"max_temp": 1500}`` — direct equality
    - ``{"max_temp": {">=": 1500}}`` — operator dict
    """
    if not requirements:
        return True
    caps = resource.capabilities
    for key, requested in requirements.items():
        if key not in caps:
            return False
        actual = caps[key]
        if isinstance(requested, Mapping):
            for op, threshold in requested.items():
                fn = _OPERATORS.get(op)
                if fn is None or not fn(actual, threshold):
                    return False
        else:
            if actual != requested:
                return False
    return True


class ResourceUnavailableError(RuntimeError):
    """Raised when no registered resource can ever satisfy the request."""


# Keep the old name as an alias so existing code doesn't break.
ResourceUnavailable = ResourceUnavailableError


class ResourceManager:
    """Tracks runtime state for every registered :class:`~autolab.models.Resource`.

    One ``asyncio.Condition`` serialises all state changes and acquisition
    checks, preventing race conditions between concurrent Operations.
    """

    def __init__(self, resources: Iterable[Resource] | None = None) -> None:
        self._resources: dict[str, Resource] = {}
        self._state: dict[str, ResourceState] = {}
        self._holders: dict[str, str | None] = {}
        self._available_after: dict[str, datetime | None] = {}
        self._cond = asyncio.Condition()
        if resources:
            for r in resources:
                self.register(r)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, resource: Resource) -> Resource:
        if resource.name in self._resources:
            raise ValueError(f"resource {resource.name!r} already registered")
        self._resources[resource.name] = resource
        self._state[resource.name] = ResourceState.IDLE
        self._holders[resource.name] = None
        self._available_after[resource.name] = None
        return resource

    def unregister(self, name: str) -> None:
        for d in (self._resources, self._state, self._holders, self._available_after):
            d.pop(name, None)

    def list(self) -> list[Resource]:
        return list(self._resources.values())

    def get(self, name: str) -> Resource:
        return self._resources[name]

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def set_state(
        self,
        name: str,
        state: ResourceState,
        *,
        available_after: datetime | None = None,
    ) -> None:
        """Transition a resource to a new state.

        ``available_after``
            For transient states like ``COOLING`` or ``WARMING``, pass the
            datetime when the resource will self-clear.  The manager will
            include this in ``status()`` so the scheduler can build ETAs.
            Pass ``None`` to indicate no automatic recovery (human must
            intervene, e.g. for ``ERROR``).
        """
        if name not in self._resources:
            raise KeyError(f"resource {name!r} not registered")
        self._state[name] = state
        self._available_after[name] = available_after

    def get_state(self, name: str) -> ResourceState:
        return self._state[name]

    def _is_available(self, name: str) -> bool:
        """True if the resource can be acquired right now."""
        state = self._state[name]
        if state == ResourceState.IDLE:
            return True
        if state in (ResourceState.COOLING, ResourceState.WARMING):
            eta = self._available_after[name]
            if eta is not None and datetime.now(UTC) >= eta:
                # Auto-clear: the cooling/warming window has passed.
                self._state[name] = ResourceState.IDLE
                self._available_after[name] = None
                return True
        return False

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def acquire(
        self,
        kind: str,
        *,
        requires: Mapping[str, Any] | None = None,
        holder: str | None = None,
        timeout: float | None = None,
    ):
        """Async context manager that yields a free compatible Resource.

        Blocks until an ``IDLE`` compatible resource is available or
        ``timeout`` (seconds) expires. Raises :class:`ResourceUnavailableError`
        immediately if *no registered resource of ``kind``* could ever
        satisfy ``requires`` (avoids an infinite wait on an impossible request).

        On entry: state → ``BUSY``, holder set.
        On exit: state → ``IDLE`` (if the code inside the ``async with``
        block didn't explicitly change it via :meth:`set_state`).
        """
        compatible = [
            r
            for r in self._resources.values()
            if r.kind == kind and matches_capabilities(r, requires)
        ]
        if not compatible:
            raise ResourceUnavailableError(
                f"no resource of kind {kind!r} satisfies requirements {dict(requires or {})!r}"
            )

        async def _wait() -> Resource:
            async with self._cond:
                while True:
                    for r in compatible:
                        if self._is_available(r.name):
                            self._state[r.name] = ResourceState.BUSY
                            self._holders[r.name] = holder
                            return r
                    await self._cond.wait()

        if timeout is None:
            resource = await _wait()
        else:
            resource = await asyncio.wait_for(_wait(), timeout=timeout)

        try:
            yield resource
        finally:
            async with self._cond:
                # Only reset to IDLE if the state is still BUSY (the context
                # body may have transitioned it to COOLING/WARMING/ERROR).
                if self._state[resource.name] == ResourceState.BUSY:
                    self._state[resource.name] = ResourceState.IDLE
                self._holders[resource.name] = None
                self._cond.notify_all()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def status(self) -> list[dict[str, Any]]:
        """Return per-resource runtime status for the dashboard / scheduler."""
        now = datetime.now(UTC)
        rows = []
        for name, r in self._resources.items():
            eta = self._available_after[name]
            rows.append(
                {
                    "name": name,
                    "kind": r.kind,
                    "asset_id": r.asset_id,
                    "capabilities": r.capabilities,
                    "state": self._state[name].value,
                    "holder": self._holders[name],
                    "available_after_iso": eta.isoformat() if eta else None,
                    "wait_seconds": max(0, (eta - now).total_seconds()) if eta else None,
                    "last_calibration_record_id": r.last_calibration_record_id,
                    "typical_operation_durations": r.typical_operation_durations,
                }
            )
        return rows


__all__ = [
    "ResourceManager",
    "ResourceUnavailable",
    "ResourceUnavailableError",
    "matches_capabilities",
]
